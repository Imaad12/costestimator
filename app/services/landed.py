"""Landed-cost derived rate proposals and currency exposure. A landed rate is only ever a PROPOSAL (Draft/Pending) built from an approved base rate and
approved terms; it goes through the normal rate approval. Exposure reporting shows which currencies the priced estimate depends on."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..approvals import engine as approvals
from ..core.errors import NotFound, ValidationFailed
from ..core.money import ZERO, D, D_opt, to_text
from ..core.timeutil import parse_date, today
from ..database import Database, jload, rows_to_dicts
from ..estimators import landed_cost
from ..models.actor import Actor
from . import audit, governed, rates


def fx_lookup(db: Database, as_of: date | None = None, to_ccy: str = "SAR"):
    as_of = as_of or today()
    rows = rows_to_dicts(db.all("SELECT * FROM fx_rates WHERE to_ccy=? AND status='Approved'", (to_ccy,)))

    def f(ccy: str) -> Decimal | None:
        best = None
        for r in rows:
            if r["from_ccy"] != ccy:
                continue
            rd, vu = parse_date(r["rate_date"]), parse_date(r.get("valid_until"))
            if rd and rd <= as_of and (not vu or vu >= as_of) and (best is None or rd > parse_date(best["rate_date"])):
                best = r
        return D(best["rate"]) if best else None
    return f


def _terms(db: Database, project_id: str | None, code: str) -> dict:
    rows = governed.effective(db, project_id or "", "landed_cost_terms")
    t = next((r for r in rows if r["code"] == code), None)
    if not t:
        raise NotFound(f"No approved landed-cost terms '{code}'.")
    return t


def compute(db: Database, base_price, base_currency: str, terms_code: str, *, project_id: str | None = None, as_of: date | None = None) -> dict:
    t = _terms(db, project_id, terms_code)
    d = t["data"]
    res = landed_cost.landed(D(base_price), base_currency, d["components"], d["output_currency"], fx_lookup(db, as_of, d["output_currency"]),
                             D_opt(d.get("units_per_shipment")))
    res["terms"] = dict(code=t["code"], version=t["version"], name=d["name"], incoterm=d.get("incoterm"))
    return res


def propose_landed_rate(db: Database, actor: Actor, base_rate_id: int, terms_code: str, *, project_id: str | None = None, submit: bool = False) -> dict:
    approvals.require_author(actor)
    base = rates.get_rate(db, base_rate_id)
    if base["status"] != "Approved":
        raise ValidationFailed("A landed-cost rate can only be derived from an APPROVED base rate.", code="LANDED_BASE_NOT_APPROVED")
    if base["unit_price"] is None:
        raise ValidationFailed("The base rate has no price.", code="LANDED_BASE_NO_PRICE")
    res = compute(db, base["unit_price"], base["currency"], terms_code, project_id=project_id)
    exposure_pct = {c: (a * 100 / res["landed"]) for c, a in res["exposure"].items()} if res["landed"] else {}
    comps = {"landed_cost": {"base_rate_id": base_rate_id, "base_price": base["unit_price"], "base_currency": base["currency"], "terms": res["terms"],
                              "lines": [{"name": l["name"], "kind": l["kind"], "amount": to_text(l["amount"]), "basis": l["basis"]} for l in res["lines"]],
                              "exposure_pct": {c: to_text(p) for c, p in exposure_pct.items()}}}
    rid = rates.propose_rate(db, actor, base["resource_id"], unit_price=res["landed"], rate_type=base["rate_type"], currency=res["output_currency"], unit=base["unit"],
                             region=base["region"], supplier_id=base["supplier_id"], source_id=base["source_id"], price_date=base["price_date"],
                             valid_until=base["valid_until"], tax_basis=base["tax_basis"], delivery_basis="Delivered (landed-cost build-up)", freight_included="yes",
                             confidence=base["confidence"], project_id=base["project_id"], components=comps, is_synthetic=bool(base["is_synthetic"]),
                             evidence=f"Derived from rate #{base_rate_id} + landed-cost terms {res['terms']['code']} v{res['terms']['version']}; FX at approved rates on the proposal date",
                             notes="DERIVED RATE PROPOSAL - requires normal rate approval", submit=submit)
    audit.log(db, actor, "rate", rid, "propose_landed", after={"base_rate": base_rate_id, "terms": terms_code, "landed": to_text(res["landed"])})
    return dict(rate_id=rid, landed=res["landed"], currency=res["output_currency"], lines=res["lines"], exposure=res["exposure"])


# ------------------------------------------------------------------------------------------------ currency exposure
def exposure_report(db: Database, project_id: str, *, shocks: str = "5,10", est=None, include_unapproved: bool = False) -> dict:
    """Priced direct cost by the currency the rate was quoted in (landed-derived rates are split by their recorded exposure), hedge cover and a what-if
    sensitivity (+/- shock % on each non-home currency). Sensitivity steps are what-if magnitudes, not forecasts."""
    from ..estimators.estimate import compute_estimate
    est = est or compute_estimate(db, project_id, include_unapproved=include_unapproved)
    home = est.direct.currency
    rate_by_id = {r["id"]: r for rows in est.inputs.rates.values() for r in rows}
    by: dict[str, Decimal] = {}
    for l in est.direct.lines:
        if l.amount is None:
            continue
        r = rate_by_id.get(l.rate_id) if l.rate_id else None
        comps = jload(r.get("components_json"), None) if r else None
        lc = comps.get("landed_cost") if isinstance(comps, dict) else None
        if lc and lc.get("exposure_pct"):
            for ccy, pct in lc["exposure_pct"].items():
                by[ccy] = by.get(ccy, ZERO) + l.amount * D(pct) / 100
        else:
            ccy = l.rate_currency or home
            by[ccy] = by.get(ccy, ZERO) + l.amount
    total = sum(by.values(), ZERO)
    cover = {r["data"]["currency"]: D(r["data"]["cover_pct"]) for r in governed.effective(db, project_id, "hedge_cover")}
    rows = []
    for ccy, amt in sorted(by.items()):
        foreign = ccy != home
        cov = cover.get(ccy, ZERO) if foreign else None
        unhedged = amt * (1 - cov / 100) if foreign else ZERO
        rows.append(dict(currency=ccy, amount_home=amt, share_pct=(amt * 100 / total if total else ZERO), home=not foreign, hedge_cover_pct=cov, unhedged_home=unhedged))
    steps = [D(s) for s in str(shocks).replace(";", ",").split(",") if s.strip()]
    sens = [dict(shock_pct=s, delta_unhedged_home=sum((r["unhedged_home"] for r in rows), ZERO) * s / 100) for s in steps]
    return dict(project_id=project_id, home_currency=home, total_priced_direct=total, by_currency=rows, sensitivity=sens, estimate_state=est.state,
                note="Rates quoted in the home currency carry no FX exposure in this view. Sensitivity steps are what-if magnitudes, not forecasts. "
                     "A foreign-currency rate converted at the approved FX rate is shown at its home-currency amount.")
