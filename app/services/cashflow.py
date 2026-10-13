"""Cash-flow / financing analysis service: time-phases the priced cost over the programme, applies approved payment terms and PROPOSES financing and bond
costs as Draft indirect items (a person submits and approves them)."""
from __future__ import annotations

from datetime import date
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
    out = engine.build(cost_by_month, est.commercial.net_price, pt["data"])
    out.update(project_id=project_id, terms=dict(code=pt["code"], version=pt["version"], name=pt["data"]["name"], **{k: v for k, v in out["terms"].items()}),
               first_month=labels[0], unscheduled_cost=rep["unscheduled_total"], estimate_state=est.state,
               note="Analysis only. Unscheduled cost (not tied to a task) is excluded from the time-phasing and listed. Financing and bond cost may be proposed as Draft indirect items.")
    if rep["unscheduled_total"] != 0:
        out["note"] += f" Unscheduled cost: {rep['unscheduled_total']}."
    return out


def propose_financing_indirects(db: Database, actor: Actor, project_id: str, *, terms_code: str | None = None) -> dict:
    """Create Draft indirect items for the performance-bond cost and the financing (interest) cost from the cash-flow analysis. Not approved, not in the price
    until a person submits and approves them."""
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    cf = cashflow_report(db, project_id, terms_code=terms_code)
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
