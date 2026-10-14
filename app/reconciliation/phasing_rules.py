"""Reconciliation findings for time-phasing completeness, percentage-indirect bases and day-priced plant (severities in config/reconciliation_rules.json)."""
from __future__ import annotations

from ..database import Database
from .engine import Finding


def collect_phasing(db: Database, project_id: str, est) -> list[Finding]:
    from ..services import governed, indirect_base, plant_hire, programme
    F: list[Finding] = []
    # ---- cost with no time allocation, whenever a time-phased analysis is configured
    has_schedule = bool(db.one("SELECT 1 FROM schedule_tasks WHERE project_id=?", (project_id,)))
    configured = [k for k in ("payment_terms", "escalation_profile") if governed.effective(db, project_id, k)]
    if has_schedule and configured:
        try:
            rep = programme.loading_report(db, project_id, measure="cost", period="month", est=est)
            if rep["unscheduled_total"] != 0:
                worst = sorted(rep["unscheduled_lines"], key=lambda u: -u["amount"])[:4]
                F.append(Finding("TIMEPHASING_INCOMPLETE", f"SAR {rep['unscheduled_total']:,.2f} of direct cost is allocated to no programme activity or time_allocation rule, so the "
                                 f"{' and '.join(configured).replace('_', ' ')} analysis is incomplete: " + "; ".join(f"{u['item_key']} {u['kind']} {u['amount']:,.2f} ({u['reason']})" for u in worst),
                                 "timephasing", project_id, rep["unscheduled_total"]))
        except Exception:
            pass
    # ---- percentage indirect bases
    ib = indirect_base.indirect_base_report(db, project_id, est=est)
    for code in ib["unspecified"]:
        F.append(Finding("INDIRECT_ELIGIBILITY_UNSPECIFIED", f"Percentage indirect {code} applies to the whole direct cost: no eligibility base has been stated.", "indirect", f"{project_id}/{code}"))
    for o in ib["overlaps"]:
        F.append(Finding("INDIRECT_BASE_OVERLAP", f"Percentage indirect {o['code']} includes {len(o['preliminaries_in_base'])} preliminaries line(s) "
                         f"({', '.join(r['item_key'] for r in o['preliminaries_in_base'][:5])}) that are already priced as BOQ items: possible double count of "
                         f"SAR {o['overlap_exposure']:,.2f}. Exclude them with an eligibility rule or accept the finding with a reason.", "indirect", f"{project_id}/{o['code']}", o["overlap_exposure"]))
    # ---- day-priced plant against the programme
    for r in plant_hire.plant_hire_report(db, project_id, est=est)["mismatches"]:
        F.append(Finding("PLANT_HIRE_DAYS", f"Plant {r['resource_id']} ({r['billing_basis']} basis): " + "; ".join(r["problems"]), "plant", r["resource_id"], r["exposure"] or None))
    return F
