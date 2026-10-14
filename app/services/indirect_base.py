"""Audit of what every percentage-based indirect is applied to: eligible vs excluded vs unclassified direct cost by cost code, BOQ line and cost kind, plus the
double-count check against preliminaries (division A) lines that are already priced as BOQ items."""
from __future__ import annotations

from decimal import Decimal

from ..core.money import ZERO, pct
from ..database import Database

PRELIM_PREFIX = "A"          # cost-code division A = preliminaries and general requirements (mobilisation, supervision, site establishment ...)


def indirect_base_report(db: Database, project_id: str, *, est=None, include_unapproved: bool = False) -> dict:
    from ..estimators.estimate import compute_estimate
    est = est or compute_estimate(db, project_id, include_unapproved=include_unapproved)
    out = []
    for l in est.indirect.lines:
        if l.method != "percent_of_direct" or l.eligibility is None:
            continue
        bd = l.eligibility
        rate = pct(bd["rate_pct"])
        prelim = [r for r in bd["rows"] if (r["cost_code"] or "").startswith(PRELIM_PREFIX) and r["eligible_amount"] > 0]
        out.append(dict(code=l.code, category=l.category, status=l.status, amount=l.amount, specified=bd["specified"], base_total=bd["total"], eligible_base=bd["eligible"],
                        excluded=bd["excluded"], unclassified=bd["unclassified"], spec=bd["spec"],
                        by_cost_code={k: v for k, v in sorted(bd["by_cost_code"].items())}, by_item={k: v for k, v in sorted(bd["by_item"].items())}, by_kind=bd["by_kind"],
                        preliminaries_in_base=[dict(item_key=r["item_key"], cost_code=r["cost_code"], eligible_amount=r["eligible_amount"], exposure=r["eligible_amount"] * rate) for r in prelim],
                        overlap_exposure=sum((r["eligible_amount"] * rate for r in prelim), ZERO)))
    return dict(project_id=project_id, indirects=out, overlaps=[o for o in out if o["preliminaries_in_base"]], unspecified=[o["code"] for o in out if not o["specified"]],
                note="A percentage indirect applies to the eligible part of the direct cost. 'specified' False = legacy whole-direct-cost base. Preliminaries (cost-code division A) inside the base may "
                     "duplicate costs the percentage is meant to cover; exclude them with an eligibility rule or accept the finding with a reason.", estimate_state=est.state)
