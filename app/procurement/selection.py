"""Supplier selection (human decision) and approved-rate publication from the selected quotation."""
from __future__ import annotations

from ..approvals import engine as approvals
from ..core.errors import Conflict, NotFound, ValidationFailed
from ..core.money import ONE, D, D_opt, pct, quantize, to_text
from ..core.timeutil import now_iso
from ..database import Database, rows_to_dicts
from ..models.actor import Actor
from ..models.enums import Entity, RateType, Status
from ..services import audit, rates
from .leveling import level_package
from .quotes import get_quotation


def propose_selection(db: Database, actor: Actor, package_id: str, quotation_id: str, justification: str,
                      not_lowest_reason: str | None = None) -> int:
    approvals.require_author(actor)
    q = get_quotation(db, quotation_id)
    if q["package_id"] != package_id:
        raise ValidationFailed("Quotation does not belong to this package.")
    if q["status"] != Status.APPROVED.value:
        raise ValidationFailed("Only an approved (human-verified) quotation can be selected.", code="QUOTE_NOT_APPROVED")
    if not justification or not justification.strip():
        raise ValidationFailed("A justification is required.", code="REASON_REQUIRED")
    lv = level_package(db, package_id)
    me = next(x for x in lv["quotations"] if x["quotation_id"] == quotation_id)
    if me["validity"] == "Expired":
        raise ValidationFailed("The quotation has expired; a valid quotation is required.", code="QUOTE_EXPIRED")
    sug = lv["suggested_lowest_like_for_like"]
    if sug and sug != quotation_id and not (not_lowest_reason and not_lowest_reason.strip()):
        raise ValidationFailed(f"{sug} is the lowest like-for-like quotation; document why {quotation_id} is selected instead.",
                               code="NOT_LOWEST_REASON_REQUIRED")
    if not me["like_for_like"] and not (not_lowest_reason and not_lowest_reason.strip()):
        raise ValidationFailed("This quotation is not like-for-like (missing items, non-compliance or unresolved normalisation). "
                               "Document how the gaps will be closed.", code="NOT_LIKE_FOR_LIKE")
    val = me["normalised_total"] if me["normalised_total"] is not None else me["quoted_total"]
    pk = db.one("SELECT project_id FROM procurement_packages WHERE id=?", (package_id,))
    sid = db.insert("quote_selections", dict(project_id=pk["project_id"], package_id=package_id, quotation_id=quotation_id,
                                            justification=justification, not_lowest_reason=not_lowest_reason, value_sar=to_text(val),
                                            status=Status.PENDING.value, proposed_by=actor.username, proposed_at=now_iso()))
    audit.log(db, actor, "supplier_selection", sid, "propose", after={"quotation": quotation_id, "value": to_text(val)},
              comment=justification, project_id=pk["project_id"])
    return sid


def decide_selection(db: Database, actor: Actor, selection_id: int, approve: bool, comments: str | None = None) -> None:
    s = db.one("SELECT * FROM quote_selections WHERE id=?", (selection_id,))
    if not s:
        raise NotFound("Selection not found.")
    act = "approve" if approve else "reject"
    approvals.authorize(actor, Entity.SUPPLIER_SELECTION.value, act, created_by=s["proposed_by"], value_sar=s["value_sar"])
    if s["status"] != Status.PENDING.value:
        raise Conflict(f"Selection is {s['status']}.")
    with db.tx():
        db.update("quote_selections", {"status": Status.APPROVED.value if approve else Status.REJECTED.value,
                                       "decided_by": actor.username, "decided_at": now_iso()}, "id=?", (selection_id,))
        approvals.record(db, actor, Entity.SUPPLIER_SELECTION.value, selection_id, act, project_id=s["project_id"],
                         approved_value={"quotation": s["quotation_id"], "value": s["value_sar"]} if approve else None,
                         comments=comments, override_reason=s["not_lowest_reason"])
        if approve:
            for r in db.all("SELECT procurement_item_id FROM quotation_lines WHERE quotation_id=? AND procurement_item_id IS NOT NULL",
                            (s["quotation_id"],)):
                db.update("procurement_items", {"quotation_status": "Selected", "approval_status": "Approved"}, "id=?",
                          (r["procurement_item_id"],))


def publish_rates(db: Database, actor: Actor, selection_id: int) -> list[int]:
    """Propose resource rates from the approved selection. Rates start 'Pending Review' and must be approved separately."""
    approvals.require_author(actor)
    s = db.one("SELECT * FROM quote_selections WHERE id=?", (selection_id,))
    if not s or s["status"] != Status.APPROVED.value:
        raise ValidationFailed("Selection must be Approved before rates can be published.", code="SELECTION_NOT_APPROVED")
    if s["published_at"]:
        raise Conflict("Rates were already published from this selection.")
    q = get_quotation(db, s["quotation_id"])
    out: list[int] = []
    with db.tx():
        for ln in q["lines"]:
            if not ln["procurement_item_id"] or D_opt(ln["unit_rate"]) is None:
                continue
            it = db.one("SELECT * FROM procurement_items WHERE id=?", (ln["procurement_item_id"],))
            if not it or not it["resource_id"]:
                continue
            price = D(ln["unit_rate"]) * (ONE - (pct(ln["discount_pct"]) if D_opt(ln["discount_pct"]) else 0))
            if q["tax_treatment"] == "incl":
                tr = D_opt(q["tax_rate_pct"])
                if tr is None:
                    raise ValidationFailed("Quotation includes tax but no tax rate is recorded; cannot derive a pre-tax rate.",
                                           code="TAX_BASIS_UNCLEAR")
                price = price / (ONE + pct(tr))
            elif q["tax_treatment"] is None:
                raise ValidationFailed("Quotation tax treatment is not recorded.", code="TAX_BASIS_UNCLEAR")
            synthetic = bool(q["is_synthetic"])
            rid = rates.propose_rate(
                db, actor, it["resource_id"], unit_price=price, rate_type=(RateType.SYNTHETIC.value if synthetic else
                                                                           RateType.VERIFIED_SUPPLIER_QUOTE.value),
                currency=q["currency"], unit=ln["unit"] or it["unit"], supplier_id=q["supplier_id"], quotation_line_id=ln["id"],
                evidence=f"Quotation {q['id']} ref {q['reference']} (selection {selection_id})",
                price_date=q["quote_date"], valid_until=q["valid_until"],
                tax_basis="excl. VAT (derived)" if q["tax_treatment"] == "incl" else (q["tax_treatment"] or ""),
                delivery_basis=q["delivery_terms"], installation_included=ln["installation_included"],
                freight_included=ln["delivery_included"], confidence="Medium", is_synthetic=synthetic, submit=True,
                notes=f"Published from quotation {q['id']}; requires rate approval.")
            out.append(rid)
        db.update("quote_selections", {"published_at": now_iso()}, "id=?", (selection_id,))
    audit.log(db, actor, "publication", selection_id, "publish_rates", after={"rates": out}, project_id=s["project_id"])
    return out
