"""Benchmark reasonableness checks, reserve / provision rules, engineering-effort costing and home-office overhead allocation.
Every range, percentage, hour and pool figure is a governed parameter entered by the company and approved; results are checks or Draft proposals."""
from __future__ import annotations

from decimal import Decimal

from ..approvals import engine as approvals
from ..core.errors import ValidationFailed
from ..core.money import ZERO, D, D_opt, quantize, to_text
from ..core.units import registry
from ..database import Database
from ..estimators.resource_pricing import price_resource_hours
from ..models.actor import Actor
from . import audit, governed, indirects, projects


# ------------------------------------------------------------------------------------------------ benchmarks
def benchmark_report(db: Database, project_id: str, *, est=None, include_unapproved: bool = False) -> dict:
    from ..estimators.estimate import compute_estimate
    bms = governed.effective(db, project_id, "benchmark_range", include_unapproved=include_unapproved)
    est = est or compute_estimate(db, project_id, include_unapproved=include_unapproved)
    if not bms:
        return dict(project_id=project_id, rows=[], outside=[], note="No approved benchmark ranges are on record: no reasonableness check was made.", estimate_state=est.state)
    reg = registry(db)
    cur = est.direct.currency
    rows = []
    total = est.direct.direct_cost_total
    by_kind = est.direct.by_kind()
    hours_by_item: dict[str, Decimal] = {}
    item_cc: dict[str, str | None] = {}
    for l in est.direct.lines:
        item_cc.setdefault(l.item_key, l.cost_code)                         # the cost code the engine used (item's own, else the assembly's)
        if l.kind == "labour" and l.hours is not None:
            hours_by_item[l.item_key] = hours_by_item.get(l.item_key, ZERO) + l.hours
    for b in bms:
        d = b["data"]
        lo, hi = D(d["low"]), D(d["high"])
        base = dict(benchmark=b["code"], name=d["name"], metric=d["metric"], low=lo, high=hi, source=d["source_note"], version=b["version"])
        if d["metric"] == "share_of_direct":
            if total <= 0:
                rows.append({**base, "subject": d["kind"], "value": None, "status": "Not comparable", "note": "no priced direct cost"})
                continue
            v = by_kind.get(d["kind"], ZERO) * 100 / total
            rows.append({**base, "subject": f"{d['kind']} share of direct %", "value": v, "status": _band(v, lo, hi)})
            continue
        for k, ic in est.direct.items.items():
            if not ic.complete or ic.quantity in (None, 0) or not (ic.cost_code or item_cc.get(k) or "").startswith(d["cost_prefix"]):
                continue
            try:
                qty = ic.quantity * (reg.factor(ic.unit, d["unit"]) if ic.unit != d["unit"] else Decimal(1))
            except ValidationFailed:
                continue
            if qty == 0:
                continue
            if d["metric"] == "item_unit_cost":
                if d.get("currency") != cur:
                    rows.append({**base, "subject": k, "value": None, "status": "Not comparable", "note": f"range is in {d.get('currency')}, estimate in {cur}"})
                    continue
                v = ic.direct_cost / qty
            else:
                if k not in hours_by_item:
                    continue
                v = hours_by_item[k] / qty
            rows.append({**base, "subject": k, "value": v, "status": _band(v, lo, hi)})
    out = [r for r in rows if r["status"] in ("Below range", "Above range")]
    return dict(project_id=project_id, rows=rows, outside=out, compared=len([r for r in rows if r["value"] is not None]),
                note="A value outside a range is a prompt to check the rate, quantity or productivity - not an error and not an adjustment. Ranges are the company's own records.",
                estimate_state=est.state)


def _band(v: Decimal, lo: Decimal, hi: Decimal) -> str:
    return "Below range" if v < lo else ("Above range" if v > hi else "Within range")


# ------------------------------------------------------------------------------------------------ reserves / engineering / overhead -> Draft indirects
def _propose(db: Database, actor: Actor, project_id: str, code: str, category: str, description: str, amount: Decimal, source: str, notes: str) -> str:
    if db.one("SELECT 1 FROM indirect_items WHERE project_id=? AND code=?", (project_id, code)):
        indirects.revise_indirect(db, actor, project_id, code, amount=to_text(amount), notes=notes)
        return "revised"
    indirects.add_indirect(db, actor, project_id, code=code, category=category, description=description, method="fixed", amount=to_text(amount),
                           allocation_method="pro_rata_direct", notes=notes, source=source)
    return "created"


def reserve_proposals(db: Database, actor: Actor, project_id: str, *, est=None) -> list[dict]:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    from ..estimators.estimate import compute_estimate
    rules = governed.effective(db, project_id, "reserve_rule")
    if not rules:
        raise ValidationFailed("No approved reserve rules: enter them as governed 'reserve_rule' parameters first.", code="RESERVE_NONE")
    est = est or compute_estimate(db, project_id)
    out = []
    for r in rules:
        d = r["data"]
        if d["base"] == "direct":
            base = est.direct.direct_cost_total
        elif d["base"] == "direct_indirect":
            base = est.direct.direct_cost_total + est.indirect.total
        else:
            if not est.commercial:
                raise ValidationFailed("selling_price base needs a computable commercial result.", code="RESERVE_BASE")
            base = est.commercial.net_price
        amt = quantize(base * D(d["pct"]) / 100, 2)
        code = f"RSV-{r['code']}"[:40]
        act = _propose(db, actor, project_id, code, d["category"], f"{d['name']} ({d['pct']}% of {d['base']})", amt, "reserve rule",
                       f"Proposed from reserve rule {r['code']} v{r['version']}: {d['pct']}% x {base} ({d['basis']})")
        out.append(dict(code=code, amount=amt, base=base, pct=D(d["pct"]), action=act))
    audit.log(db, actor, "reserve", project_id, "propose_indirects", after={"codes": [o["code"] for o in out]}, project_id=project_id)
    return out


def engineering_report(db: Database, project_id: str) -> dict:
    """Hours and cost of the declared engineering / design effort, charged at each labour resource's strictly eligible approved rate (unpriced if none)."""
    rows = governed.effective(db, project_id, "engineering_basis")
    if not rows:
        raise ValidationFailed("No approved engineering basis: enter deliverables and hours as governed 'engineering_basis' parameters.", code="ENG_NONE")
    out, by_disc = [], {}
    tot_h = tot_c = ZERO
    unpriced = 0
    for r in rows:
        d = r["data"]
        hours = D(d["count"]) * D(d["hours_each"])
        rate = price_resource_hours(db, project_id, d["resource_id"])
        amt = None if rate is None else quantize(hours * rate, 2)
        if amt is None:
            unpriced += 1
        else:
            tot_c += amt
        tot_h += hours
        s = by_disc.setdefault(d["discipline"], {"hours": ZERO, "cost": ZERO, "unpriced_hours": ZERO})
        s["hours"] += hours
        if amt is None:
            s["unpriced_hours"] += hours
        else:
            s["cost"] += amt
        out.append(dict(code=r["code"], discipline=d["discipline"], deliverable=d["deliverable"], count=D(d["count"]), hours_each=D(d["hours_each"]), hours=hours,
                        resource_id=d["resource_id"], rate=rate, amount=amt, basis=d["basis"]))
    return dict(project_id=project_id, lines=out, by_discipline=by_disc, total_hours=tot_h, total_cost=tot_c, unpriced_lines=unpriced,
                note="Cost excludes any line whose labour resource has no eligible approved hourly rate (shown as unpriced, never zero).")


def propose_engineering_indirects(db: Database, actor: Actor, project_id: str) -> list[dict]:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    rep = engineering_report(db, project_id)
    if rep["unpriced_lines"]:
        raise ValidationFailed(f"{rep['unpriced_lines']} engineering line(s) have no eligible approved labour rate: cost cannot be proposed.", code="ENG_UNPRICED")
    out = []
    for disc, s in sorted(rep["by_discipline"].items()):
        code = ("ENG-" + "".join(ch for ch in disc.upper() if ch.isalnum())[:20])
        act = _propose(db, actor, project_id, code, "Engineering and design", f"Engineering - {disc} ({s['hours']} h)", s["cost"], "engineering basis",
                       f"Proposed from engineering basis: {s['hours']} h")
        out.append(dict(code=code, hours=s["hours"], amount=s["cost"], action=act))
    audit.log(db, actor, "engineering", project_id, "propose_indirects", after={"codes": [o["code"] for o in out]}, project_id=project_id)
    return out


def overhead_report(db: Database, project_id: str, *, est=None, pool_code: str | None = None) -> dict:
    """Project share of each approved annual overhead pool = recovery rate x the project's own base, where recovery rate = annual pool cost / annual base and the base
    kind (direct cost, labour hours or selling price) is the one the company recovers the pool over."""
    from ..estimators.estimate import compute_estimate
    pools = [p for p in governed.effective(db, project_id, "overhead_pool") if pool_code in (None, "", p["code"])]
    if not pools:
        raise ValidationFailed("No approved overhead pool: enter the annual pool cost and base as a governed 'overhead_pool'.", code="POOL_NONE")
    est = est or compute_estimate(db, project_id)
    hours = sum((l.hours for l in est.direct.lines if l.kind == "labour" and l.hours is not None), ZERO)
    rows = []
    for p in pools:
        d = p["data"]
        kind = d["base_kind"]
        pb = est.direct.direct_cost_total if kind == "direct_cost" else (hours if kind == "labour_hours" else (est.commercial.net_price if est.commercial else None))
        if pb is None:
            rows.append(dict(pool=p["code"], name=d["name"], share=None, note="project base unavailable (no computable commercial result)"))
            continue
        rate = D(d["annual_cost"]) / D(d["annual_base"])
        rows.append(dict(pool=p["code"], name=d["name"], base_kind=kind, project_base=pb, annual_cost=D(d["annual_cost"]), annual_base=D(d["annual_base"]),
                         recovery_rate_pct=rate * 100, share=quantize(rate * pb, 2), basis=d["basis"]))
    return dict(project_id=project_id, rows=rows, total=sum((r["share"] for r in rows if r.get("share") is not None), ZERO), estimate_state=est.state,
                note="Recovery rate = annual pool cost / annual base, applied to the project's own base. The result is a proposal for a Draft indirect item.")


def propose_overhead_indirects(db: Database, actor: Actor, project_id: str) -> list[dict]:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    rep = overhead_report(db, project_id)
    out = []
    for r in rep["rows"]:
        if r.get("share") is None:
            raise ValidationFailed(f"Pool {r['pool']}: {r.get('note')}.", code="POOL_BASE")
        code = f"OH-{r['pool']}"[:40]
        act = _propose(db, actor, project_id, code, "Head-office overhead", f"Overhead pool: {r['name']}", r["share"], "overhead pool",
                       f"Proposed from pool {r['pool']}: recovery {r['recovery_rate_pct']:.4f}% of {r['base_kind']}")
        out.append(dict(code=code, amount=r["share"], action=act))
    audit.log(db, actor, "overhead", project_id, "propose_indirects", after={"codes": [o["code"] for o in out]}, project_id=project_id)
    return out
