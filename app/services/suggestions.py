"""Human review of AI / heuristic suggestions. Accepting creates DRAFT or explicitly human-made records - never approvals by AI."""
from __future__ import annotations

from ..approvals import engine as approvals
from ..core.errors import Conflict, NotFound, ValidationFailed
from ..core.timeutil import now_iso
from ..database import Database, jload, rows_to_dicts
from ..models.actor import Actor
from ..models.enums import Entity
from ..procurement import quotes
from . import assemblies as asm_service
from . import audit, boq, registers


def list_suggestions(db: Database, project_id: str | None = None, status: str | None = "Pending Review", kind: str | None = None) -> list[dict]:
    sql, p = "SELECT * FROM ai_suggestions WHERE 1=1", []
    if project_id:
        sql += " AND project_id=?"; p.append(project_id)
    if status:
        sql += " AND status=?"; p.append(status)
    if kind:
        sql += " AND kind=?"; p.append(kind)
    out = rows_to_dicts(db.all(sql + " ORDER BY id DESC", p))
    for r in out:
        r["payload"] = jload(r["payload_json"], {})
    return out


def get_suggestion(db: Database, sid: int) -> dict:
    r = db.one("SELECT * FROM ai_suggestions WHERE id=?", (sid,))
    if not r:
        raise NotFound(f"Suggestion {sid} not found.")
    d = dict(r)
    d["payload"] = jload(d["payload_json"], {})
    return d


def accept(db: Database, actor: Actor, sid: int, *, comment: str, supplier_id: str | None = None) -> dict:
    s = get_suggestion(db, sid)
    approvals.authorize(actor, Entity.AI_SUGGESTION.value, "approve")
    if s["status"] != "Pending Review":
        raise Conflict(f"Suggestion is already {s['status']}.")
    if not comment or not comment.strip():
        raise ValidationFailed("Reviewer comment required.", code="REASON_REQUIRED")
    p, pid, result = s["payload"], s["project_id"], {}
    with db.tx():
        kind = s["kind"]
        if kind == "mapping":
            a = asm_service.get_approved(db, p["assembly_code"], pid)
            if a is None:
                raise ValidationFailed("Only approved assemblies can be mapped.")
            boq.map_to_assembly(db, actor, pid, p["item_key"], p["assembly_code"], source="manual",
                                comment=f"Accepted {s['produced_by']} suggestion #{sid}: {comment}")
            result = {"mapped": p["item_key"]}
        elif kind == "clarifications":
            cid = registers.add_clarification(db, actor, pid, p["question"], boq_item_key=p.get("boq_item_key"), reason=p.get("reason"),
                                              proposed_wording=p.get("proposed_wording"), suggested_by=s["produced_by"])
            result = {"clarification": cid}
        elif kind == "scope_gap":
            cid = registers.add_clarification(db, actor, pid, f"Possible {p['kind']}: {p['description']}", reason="Suggested scope gap",
                                              suggested_by=s["produced_by"])
            result = {"clarification": cid}
        elif kind == "quote_extraction":
            if not supplier_id:
                raise ValidationFailed("Choose the supplier (from the directory) this quotation belongs to; the AI does not pick suppliers.",
                                       code="SUPPLIER_REQUIRED")
            qid = quotes.create_quotation(db, actor, supplier_id=supplier_id, project_id=pid, reference=p.get("reference"), quote_date=p.get("quote_date"),
                                          valid_until=p.get("valid_until"), currency=p.get("currency") or "SAR", payment_terms=p.get("payment_terms"),
                                          tax_treatment=p.get("tax_treatment"), tax_rate_pct=p.get("tax_rate_pct"), exclusions=p.get("exclusions"),
                                          deviations=p.get("deviations"), extracted_by_ai=True,
                                          lines=[dict(description=l["description"], specification=l.get("specification"), quantity=l.get("quantity"),
                                                      unit=l.get("unit"), unit_rate=l.get("unit_rate"), discount_pct=l.get("discount_pct"),
                                                      lead_time_days=l.get("lead_time_days"), delivery_included=l.get("delivery_included", "Unknown"),
                                                      comments=f"AI evidence: {l.get('evidence_quote', '')[:300]}") for l in p["lines"]])
            result = {"quotation": qid, "note": "Draft quotation created; a Procurement Reviewer must verify it against the source document."}
        else:
            result = {"note": "Informational suggestion acknowledged; no records were changed."}
        db.update("ai_suggestions", {"status": "Approved", "reviewed_by": actor.username, "reviewed_at": now_iso(), "review_comment": comment}, "id=?", (sid,))
        approvals.record(db, actor, Entity.AI_SUGGESTION.value, sid, "approve", project_id=pid, approved_value={"kind": kind, **result},
                         comments=comment, evidence=f"produced_by={s['produced_by']}")
    return result


def reject(db: Database, actor: Actor, sid: int, comment: str) -> None:
    s = get_suggestion(db, sid)
    approvals.authorize(actor, Entity.AI_SUGGESTION.value, "reject")
    if s["status"] != "Pending Review":
        raise Conflict(f"Suggestion is already {s['status']}.")
    db.update("ai_suggestions", {"status": "Rejected", "reviewed_by": actor.username, "reviewed_at": now_iso(), "review_comment": comment}, "id=?", (sid,))
    approvals.record(db, actor, Entity.AI_SUGGESTION.value, sid, "reject", project_id=s["project_id"], comments=comment)
