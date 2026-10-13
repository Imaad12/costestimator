"""Quantified risk analysis (expected value + seeded Monte Carlo) and time-phased escalation. Both are ANALYSES: they propose figures with their method
and inputs and never change the commercial policy or any estimate."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..core.errors import ValidationFailed
from ..core.money import ZERO, D, D_opt
from ..database import Database, rows_to_dicts
from ..estimators import escalation as esc
from ..estimators import montecarlo as mc
from ..rate_updates import index_import
from . import analysis, governed, programme


def risk_inputs(db: Database, project_id: str, include_unapproved: bool = False) -> tuple[list[mc.RiskIn], list[mc.RangeIn], list[str]]:
    notes = []
    rows = rows_to_dicts(db.all("SELECT * FROM risks WHERE project_id=? AND status='Open' ORDER BY id", (project_id,)))
    risks, skipped = [], []
    for r in rows:
        if r["prob_pct"] is None or r["cost_likely"] is None:
            skipped.append(r["id"])
            continue
        risks.append(mc.RiskIn(r["id"], r["title"], D(r["prob_pct"]) / 100, D(r["cost_low"]), D(r["cost_likely"]), D(r["cost_high"]), D_opt(r["schedule_days"]) or ZERO))
    if skipped:
        notes.append(f"{len(skipped)} open risk(s) have no quantification and are NOT in the simulation: {', '.join(skipped)}.")
    ranges = [mc.RangeIn(p["data"]["name"], D(p["data"]["low"]), D(p["data"]["likely"]), D(p["data"]["high"]))
              for p in governed.effective(db, project_id, "range_item", include_unapproved=include_unapproved)]
    return risks, ranges, notes


def risk_report(db: Database, project_id: str, *, trials: int = 10000, seed: int = 20260101, target_pct: int = 80, est=None, include_unapproved: bool = False) -> dict:
    from ..estimators.estimate import compute_estimate
    risks, ranges, notes = risk_inputs(db, project_id, include_unapproved)
    if not risks and not ranges:
        raise ValidationFailed("No quantified risks or cost ranges: quantify register entries (probability and three-point cost) or add range items first.", code="RISK_NONE")
    if not (1 <= int(target_pct) <= 99):
        raise ValidationFailed("target_pct must be between 1 and 99.")
    # ranges enter as deviations from their most-likely value (that value is already in the estimate)
    dev = [mc.RangeIn(x.name, x.low - x.likely, ZERO, x.high - x.likely) for x in ranges]
    ev = mc.expected_value(risks, [mc.RangeIn(d.name, d.low, d.likely, d.high) for d in dev])
    sim = mc.simulate(risks, dev, int(trials), int(seed), percentiles=(10, 50, int(target_pct), 90))
    est = est or compute_estimate(db, project_id, include_unapproved=include_unapproved)
    c = est.commercial
    pol = (c.contingency + c.risk) if c else None
    key = f"P{int(target_pct)}"
    prop = sim["percentiles"][key]
    return dict(project_id=project_id, method=("Independent risks: Bernoulli(p) x triangular(low, likely, high); range items: triangular deviation from the value in the estimate. "
                                               "No correlation; schedule impacts summed (no critical-path logic)."),
                inputs=dict(risks=[dict(id=r.id, title=r.title, p_pct=r.p * 100, low=r.low, likely=r.likely, high=r.high, days=r.days) for r in risks],
                            ranges=[dict(name=x.name, low=x.low, likely=x.likely, high=x.high) for x in ranges], trials=int(trials), seed=int(seed)),
                expected_value=ev, simulation=sim, target=key, proposed_provision=prop,
                policy_provision=pol, difference_vs_policy=None if pol is None else prop - pol,
                note=f"PROPOSAL ONLY: the simulation suggests a provision of {prop:,.2f} at {key}. The contingency and risk amounts in the commercial policy are decided and approved by people.",
                notes=notes, estimate_state=est.state)


# ------------------------------------------------------------------------------------------------ escalation
def escalation_report(db: Database, project_id: str, *, est=None, include_unapproved: bool = False, index_dataset: str | None = None) -> dict:
    from ..estimators.estimate import compute_estimate
    profs = governed.effective(db, project_id, "escalation_profile", include_unapproved=include_unapproved)
    if not profs:
        raise ValidationFailed("No approved escalation profile: enter the annual percentage, base date and scope as a governed 'escalation_profile'.", code="ESC_NONE")
    est = est or compute_estimate(db, project_id, include_unapproved=include_unapproved)
    cal = programme.calendar_for(db, project_id, include_unapproved)
    if cal is None:
        raise ValidationFailed("Time-phased escalation needs the programme and an approved project calendar.", code="CALENDAR_REQUIRED")

    def scope_of(p):
        d = p["data"]
        return lambda l: (d["scope_kind"] in ("all", l.kind)) and (not d.get("scope_cost_prefix") or (l.cost_code or "").startswith(d["scope_cost_prefix"]))
    scopes = [(p, scope_of(p)) for p in profs]
    over = sorted({f"{l.item_key}:{l.kind}" for l in est.direct.lines if l.amount is not None and sum(1 for _, f in scopes if f(l)) > 1})
    if over:
        raise ValidationFailed(f"Escalation profiles overlap on {len(over)} cost line(s), e.g. {over[:3]}: escalation would be applied twice. Narrow the scopes.", code="ESC_OVERLAP")
    rows, tot_base, tot_esc, covered = [], ZERO, ZERO, ZERO
    for p, f in scopes:
        rep = programme.loading_report(db, project_id, measure="cost", period="month", est=est, include_unapproved=include_unapproved, line_filter=f)
        amounts = {b: sum((rep["series"][k].get(b, ZERO) for k in rep["series"]), ZERO) for b in rep["buckets"]}
        mid = {b: date(int(b[:4]), int(b[5:7]), 15) for b in amounts}
        d = p["data"]
        res = esc.phase(amounts, mid, date.fromisoformat(d["base_date"]), D(d["annual_pct"]))
        unsched = rep["unscheduled_total"]
        rows.append(dict(profile=p["code"], name=d["name"], annual_pct=D(d["annual_pct"]), base_date=d["base_date"], basis=d["basis"], scope_kind=d["scope_kind"],
                         scope_cost_prefix=d.get("scope_cost_prefix"), periods=res["rows"], base_total=res["base_total"], escalation_total=res["escalation_total"],
                         escalated_total=res["escalated_total"], unscheduled_not_escalated=unsched))
        tot_base += res["base_total"]
        tot_esc += res["escalation_total"]
        covered += res["base_total"] + unsched
    direct = est.direct.direct_cost_total
    idx = []
    if index_dataset:
        for o in index_import.latest_observations(db, index_dataset, "Y-o-Y")[-12:]:
            idx.append(dict(series=o["series"], period=o["period"], value=o["value"]))
    c = est.commercial
    return dict(project_id=project_id, profiles=rows, escalation_total=tot_esc, scheduled_base_total=tot_base, direct_cost_total=direct,
                not_covered_by_any_profile=direct - covered, policy_escalation=(c.escalation if c else None),
                index_reference=idx, note="Escalation is compounded from each profile's base date to mid-month of each programme month. Cost not tied to a task by cost-code/WBS scope "
                "is NOT escalated and is listed. Index values (if shown) are information; the percentages are the company's decision.", estimate_state=est.state)
