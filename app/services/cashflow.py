"""Cash-flow / financing analysis service: time-phases the priced cost over the programme, applies approved payment terms and PROPOSES financing and bond
costs as Draft indirect items (a person submits and approves them)."""
from __future__ import annotations

from decimal import Decimal

from ..approvals import engine as approvals
from ..core.errors import ValidationFailed
from ..core.money import ZERO, to_text
from ..database import Database
from ..estimators import cashflow as engine
from ..models.actor import Actor
from . import audit, governed, indirects, programme, projects


def cashflow_report(db: Database, project_id: str, *, terms_code: str | None = None, est=None, include_unapproved: bool = False) -> dict:
    from ..estimators.estimate import compute_estimate
    rows = governed.effective(db, project_id, "payment_terms", include_unapproved=include_unapproved)
    if not rows:
        raise ValidationFailed("No approved payment terms: enter the contract/bank/supplier terms as a governed 'payment_terms' parameter.", code="TERMS_NONE")
    pt = next((r for r in rows if terms_code in (None, "", r["code"])), None)
    if pt is None:
        raise ValidationFailed(f"Payment terms '{terms_code}' not found.", code="TERMS_NONE")
    est = est or compute_estimate(db, project_id, include_unapproved=include_unapproved)
    if est.commercial is None:
        raise ValidationFailed("The estimate has no computable commercial result (policy missing/invalid).", code="CASHFLOW_NO_PRICE")
    rep = programme.loading_report(db, project_id, measure="cost", period="month", est=est, include_unapproved=include_unapproved)
    if not rep["calendar_used"]:
        raise ValidationFailed("Cash flow needs an approved project calendar to place cost in months.", code="CALENDAR_REQUIRED")
    by_label: dict[str, Decimal] = {}
    for k, s in rep["series"].items():
        for b, v in s.items():
            by_label[b] = by_label.get(b, ZERO) + v
    labels = sorted(by_label)
    y0, m0 = int(labels[0][:4]), int(labels[0][5:7])
    cost_by_month = {(int(b[:4]) - y0) * 12 + int(b[5:7]) - m0: v for b, v in by_label.items()}
    direct_total = est.direct.direct_cost_total
    allocated = sum(cost_by_month.values(), ZERO)
    unallocated = rep["unscheduled_total"]
    complete = unallocated == 0 and abs(allocated - direct_total) < Decimal("0.01")
    indirect_total = est.indirect.total or ZERO
    # ACCOUNTING CONVENTIONS (stated with every result): cash-out = allocated direct cost x (1 + indirect/direct), i.e. indirect cost follows the direct cost it is a percentage of;
    # contingency, risk allowances and margin are NOT cash-out (reserve / profit); only the ALLOCATED share of the price is valued (cost that no period claims is neither paid
    # nor valued), so cash-out, valuations, retention and the closing balance are always on one base.
    factor = (1 + indirect_total / direct_total) if direct_total else Decimal(1)
    price_full = est.commercial.net_price
    valued_price = price_full * allocated / direct_total if direct_total else price_full
    out = engine.build({m: v * factor for m, v in cost_by_month.items()}, valued_price, pt["data"])
    t = out["terms"]
    out["performance_bond_cost"] = price_full * t["performance_bond_pct"] / 100 * t["performance_bond_fee_annual_pct"] / 100 * out["bond_months"] / 12     # bond is on the full contract value
    out["total_cost"] = allocated                                                    # direct cost placed in periods; cash-out total (incl. indirects) is in `reconciliation`
    cash_in = sum((r["cash_in"] for r in out["rows"]), ZERO)
    cash_out = sum((r["cash_out"] for r in out["rows"]), ZERO)
    interest = out["interest_total"]
    checks = [("valuations sum to the valued price", abs(sum((v["value"] for v in out["valuations"]), ZERO) - valued_price) < Decimal("0.01")),
              ("cash received equals the valued price", abs(cash_in - valued_price) < Decimal("0.01")),
              ("cash paid equals allocated direct cost x (1 + indirect/direct)", abs(cash_out - allocated * factor) < Decimal("0.01")),
              ("closing balance = valued price - cash paid - interest", abs(out["final_balance"] - (valued_price - cash_out - interest)) < Decimal("0.01"))]
    status = "COMPLETE" if complete else (f"INCOMPLETE - NOT FOR RELIANCE: SAR {unallocated:,.2f} of direct cost is allocated to no period (see unallocated_lines); "
                                           f"SAR {price_full - valued_price:,.2f} of the price is not valued and the closing balance excludes it")
    out.update(project_id=project_id, terms=dict(code=pt["code"], version=pt["version"], name=pt["data"]["name"], **{k: v for k, v in out["terms"].items()}),
               first_month=labels[0], unscheduled_cost=unallocated, unallocated_lines=rep["unscheduled_lines"], allocated_by_rule=rep["allocated_by_rule"], complete=complete,
               status=status, estimate_state=est.state,
               reconciliation=dict(net_price=price_full, valued_price=valued_price, unallocated_price_share=price_full - valued_price, direct_cost=direct_total, allocated_direct_cost=allocated,
                                   unallocated_direct_cost=unallocated, indirect_cost=indirect_total, indirect_cash_factor=factor, cash_out_total=cash_out, cash_in_total=cash_in,
                                   retention_total=out["retention_total"], interest_total=interest, closing_balance=out["final_balance"], contingency_and_risk_reserve_not_cash_out=est.commercial.contingency + est.commercial.risk,
                                   checks=[dict(check=c, ok=ok) for c, ok in checks]),
               note="Analysis only. Conventions: indirects are paid with the direct cost they follow; contingency/risk/margin are not cash-out; only allocated cost is valued. "
                    + ("" if complete else f"INCOMPLETE: {unallocated} of direct cost has no time allocation - add an approved 'time_allocation' rule or tie it to a programme activity. ")
                    + "Financing and bond cost may be proposed as Draft indirect items (refused while incomplete).")
    out["assumptions"] = out["assumptions"] + ["Indirect cost is paid in proportion to the direct cost it is calculated from; contingency, risk allowances and margin are not cash-out.",
                                               "Only cost allocated to a period (by an activity's scope or an approved time_allocation rule) is paid and valued."]
    return out


def propose_financing_indirects(db: Database, actor: Actor, project_id: str, *, terms_code: str | None = None) -> dict:
    """Create Draft indirect items for the performance-bond cost and the financing (interest) cost from the cash-flow analysis. Not approved, not in the price
    until a person submits and approves them."""
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    cf = cashflow_report(db, project_id, terms_code=terms_code)
    if not cf["complete"]:
        raise ValidationFailed(f"The cash flow is incomplete ({cf['unscheduled_cost']} of direct cost has no time allocation): financing and bond costs cannot be proposed from it.", code="TIMEPHASING_INCOMPLETE")
    made = []
    for code, cat, desc, amt in (("FIN-BOND", "Bonds and insurances", "Performance bond fee (cash-flow analysis)", cf["performance_bond_cost"]),
                                 ("FIN-INTEREST", "Financing", "Financing cost of negative cash position (cash-flow analysis)", cf["interest_total"])):
        if amt <= 0:
            continue
        existing = db.one("SELECT 1 FROM indirect_items WHERE project_id=? AND code=?", (project_id, code))
        if existing:
            indirects.revise_indirect(db, actor, project_id, code, amount=to_text(amt), notes=f"Re-proposed from cash flow, terms {cf['terms']['code']} v{cf['terms']['version']}")
        else:
            indirects.add_indirect(db, actor, project_id, code=code, category=cat, description=desc, method="fixed", amount=to_text(amt), allocation_method="pro_rata_direct",
                                   notes=f"Proposed from cash-flow analysis, payment terms {cf['terms']['code']} v{cf['terms']['version']}; peak funding {cf['peak_funding']:,.2f}",
                                   source="cash-flow analysis")
        made.append(code)
    audit.log(db, actor, "cashflow", project_id, "propose_indirects", after={"codes": made}, project_id=project_id)
    return {"indirect_codes": made, "interest": cf["interest_total"], "bond": cf["performance_bond_cost"]}
