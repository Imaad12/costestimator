"""BOQ item management: change requests (quantity/unit/description), assembly mapping, non-assembly pricing."""
from __future__ import annotations

from decimal import Decimal

from ..approvals import engine as approvals
from ..core.errors import Conflict, NotFound, ValidationFailed
from ..core.money import D, D_opt, to_text
from ..core.timeutil import now_iso
from ..core.units import registry
from ..database import Database, jload, rows_to_dicts
from ..models.actor import Actor
from ..models.enums import PRICING_METHODS, Entity, Status
from . import assemblies as asm_service
from . import audit, projects


def get_item(db: Database, project_id: str, item_key: str) -> dict:
    r = db.one("SELECT * FROM boq_items WHERE project_id=? AND item_key=?", (project_id, item_key))
    if not r:
        raise NotFound(f"BOQ item {item_key} not found in {project_id}.")
    return dict(r)


def list_items(db: Database, project_id: str, *, q: str | None = None, trade: str | None = None,
               mapping_status: str | None = None, only_items: bool = True) -> list[dict]:
    sql = "SELECT * FROM boq_items WHERE project_id=?"
    p: list = [project_id]
    if only_items:
        sql += " AND item_type='item'"
    if q:
        sql += " AND (description LIKE ? OR item_code LIKE ?)"; p += [f"%{q}%"] * 2
    if trade:
        sql += " AND (trade=? OR cost_code LIKE ?)"; p += [trade, trade + "%"]
    if mapping_status:
        sql += " AND mapping_status=?"; p.append(mapping_status)
    rows = rows_to_dicts(db.all(sql + " ORDER BY id", p))
    for r in rows:
        r["issues"] = jload(r.get("issues_json"), [])
    return rows


# ----------------------------------------------------------------------------- change requests
def pending_changes(db: Database, project_id: str) -> list[dict]:
    return rows_to_dicts(db.all("SELECT * FROM change_requests WHERE project_id=? AND status='Pending Review' ORDER BY id",
                                (project_id,)))


def request_quantity_change(db: Database, actor: Actor, project_id: str, item_key: str, new_quantity, reason: str,
                            evidence: str | None = None) -> int:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    it = get_item(db, project_id, item_key)
    q = D_opt(new_quantity)
    if q is None or q < 0:
        raise ValidationFailed("New quantity must be a non-negative number.")
    if not reason:
        raise ValidationFailed("A reason is required for a quantity change.", code="REASON_REQUIRED")
    cid = db.insert("change_requests", dict(project_id=project_id, entity_type="boq_quantity", entity_id=item_key,
                                            field="quantity", old_value=it["quantity"], new_value=to_text(q), reason=reason,
                                            evidence=evidence, status="Pending Review", requested_by=actor.username,
                                            requested_at=now_iso()))
    audit.log(db, actor, "boq_quantity", item_key, "request_change", before=it["quantity"], after=to_text(q),
              comment=reason, project_id=project_id)
    return cid


def decide_change(db: Database, actor: Actor, change_id: int, approve: bool, *, comment: str | None = None,
                  unit_code: str | None = None) -> None:
    ch = db.one("SELECT * FROM change_requests WHERE id=?", (change_id,))
    if not ch:
        raise NotFound(f"Change request {change_id} not found.")
    if ch["status"] != "Pending Review":
        raise Conflict(f"Change request already {ch['status']}.")
    etype = ch["entity_type"]
    action = "approve" if approve else "reject"
    approvals.authorize(actor, etype, action, created_by=ch["requested_by"])
    projects.require_active(db, ch["project_id"])
    with db.tx():
        new_value = ch["new_value"]
        if approve:
            item = get_item(db, ch["project_id"], ch["entity_id"])
            if ch["field"] == "quantity":
                db.update("boq_items", {"quantity": new_value}, "id=?", (item["id"],))
            elif ch["field"] == "description":
                db.update("boq_items", {"description": new_value}, "id=?", (item["id"],))
            elif ch["field"] == "unit":
                code = unit_code or new_value
                res = registry(db).resolve(code)
                if res.status != "ok":
                    raise ValidationFailed("A concrete, unambiguous canonical unit code must be chosen to approve a "
                                           f"unit correction ({res.message or 'ambiguous'}).", code="UNIT_REQUIRED")
                new_value = res.code
                db.update("boq_items", {"unit": res.code, "unit_status": "approved_correction"}, "id=?", (item["id"],))
                _clear_issue(db, item["id"], prefix="UNIT_")
            else:
                raise ValidationFailed(f"Unsupported change field {ch['field']}")
        db.update("change_requests", {"status": "Approved" if approve else "Rejected", "decided_by": actor.username,
                                      "decided_at": now_iso(), "decision_comment": comment, "new_value": new_value},
                  "id=?", (change_id,))
        approvals.record(db, actor, etype, ch["entity_id"], action, project_id=ch["project_id"], previous_value=ch["old_value"],
                         approved_value=new_value if approve else None, evidence=ch["evidence"], comments=comment,
                         override_reason=ch["reason"])


def _clear_issue(db: Database, item_id: int, prefix: str) -> None:
    r = db.one("SELECT issues_json FROM boq_items WHERE id=?", (item_id,))
    issues = [i for i in jload(r["issues_json"], []) if not i["code"].startswith(prefix)]
    status = "Needs Review" if any(i["level"] == "error" for i in issues) else "OK"
    db.update("boq_items", {"issues_json": issues, "validation_status": status}, "id=?", (item_id,))


# ----------------------------------------------------------------------------- mapping
def map_to_assembly(db: Database, actor: Actor, project_id: str, item_key: str, assembly_code: str, *,
                    source: str = "manual", comment: str | None = None) -> None:
    """Estimator maps a BOQ item to an assembly. Heuristic/AI-sourced mappings stay 'Suggested' until a human approves."""
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    it = get_item(db, project_id, item_key)
    asm = asm_service.get(db, assembly_code)
    if it["item_type"] != "item":
        raise ValidationFailed("Headings cannot be mapped.")
    reg = registry(db)
    if it["unit"] and not reg.can_convert(it["unit"], asm["unit"]):
        raise ValidationFailed(f"BOQ unit '{it['unit']}' is not compatible with assembly unit '{asm['unit']}'. "
                               "Fix the unit (approved correction) or choose a different assembly.", code="UNIT_MISMATCH")
    status = Status.APPROVED.value if source == "manual" else "Suggested"
    db.update("boq_items", {"assembly_code": assembly_code, "assembly_version": None, "mapping_status": status,
                            "mapping_source": source, "pricing_method": "assembly"}, "id=?", (it["id"],))
    if source == "manual":
        approvals.record(db, actor, Entity.BOQ_MAPPING.value, item_key, "approve", project_id=project_id,
                         previous_value=it["assembly_code"], approved_value=assembly_code, comments=comment)
    audit.log(db, actor, "boq_mapping", item_key, f"map:{source}", before=it["assembly_code"], after=assembly_code,
              project_id=project_id)


def approve_mapping(db: Database, actor: Actor, project_id: str, item_key: str, *, comment: str | None = None) -> None:
    it = get_item(db, project_id, item_key)
    approvals.authorize(actor, Entity.BOQ_MAPPING.value, "approve")
    if it["mapping_status"] not in ("Suggested", Status.PENDING.value):
        raise Conflict(f"Mapping is '{it['mapping_status']}', nothing to approve.")
    db.update("boq_items", {"mapping_status": Status.APPROVED.value}, "id=?", (it["id"],))
    approvals.record(db, actor, Entity.BOQ_MAPPING.value, item_key, "approve", project_id=project_id,
                     approved_value=it["assembly_code"], comments=comment)


def reject_mapping(db: Database, actor: Actor, project_id: str, item_key: str, reason: str) -> None:
    it = get_item(db, project_id, item_key)
    approvals.authorize(actor, Entity.BOQ_MAPPING.value, "reject")
    db.update("boq_items", {"assembly_code": None, "mapping_status": "Unmapped", "mapping_source": None,
                            "pricing_method": "unpriced"}, "id=?", (it["id"],))
    approvals.record(db, actor, Entity.BOQ_MAPPING.value, item_key, "reject", project_id=project_id,
                     previous_value=it["assembly_code"], comments=reason)


def set_cost_code(db: Database, actor: Actor, project_id: str, item_key: str, cost_code: str) -> None:
    approvals.require_author(actor)
    if not db.one("SELECT 1 FROM cost_codes WHERE code=?", (cost_code,)):
        raise ValidationFailed(f"Unknown cost code {cost_code}.")
    it = get_item(db, project_id, item_key)
    db.update("boq_items", {"cost_code": cost_code}, "id=?", (it["id"],))
    audit.log(db, actor, "boq_item", item_key, "set_cost_code", before=it["cost_code"], after=cost_code, project_id=project_id)


# ----------------------------------------------------------------------------- non-assembly pricing
def set_pricing(db: Database, actor: Actor, project_id: str, item_key: str, method: str, *,
                resource_id: str | None = None, amount=None, currency: str = "SAR", note: str | None = None) -> None:
    """Choose a non-assembly pricing method. Sums/allowances start Pending Review and need explicit approval."""
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    if method not in PRICING_METHODS:
        raise ValidationFailed(f"method must be one of {PRICING_METHODS}")
    it = get_item(db, project_id, item_key)
    status = Status.APPROVED.value
    if method == "subcontract_lump":
        if not resource_id or not db.one("SELECT 1 FROM resources WHERE id=? AND resource_type='subcontract'", (resource_id,)):
            raise ValidationFailed("subcontract_lump needs a subcontract resource (rate comes from its approved rate).")
        amount = None
    elif method in ("provisional_sum", "prime_cost_sum", "allowance"):
        if D_opt(amount) is None or D(amount) < 0:
            raise ValidationFailed(f"{method} needs a non-negative amount.")
        if not note:
            raise ValidationFailed(f"{method} needs a basis note/source.")
        status = Status.PENDING.value
    elif method in ("assembly", "takeoff_resources"):
        raise ValidationFailed("Use map_to_assembly / takeoff import for this method.")
    db.update("boq_items", {"pricing_method": method, "pricing_resource_id": resource_id,
                            "pricing_amount": to_text(D_opt(amount)), "pricing_currency": currency,
                            "pricing_status": status, "pricing_note": note,
                            "assembly_code": None if method != "assembly" else it["assembly_code"]}, "id=?", (it["id"],))
    audit.log(db, actor, "boq_item", item_key, f"set_pricing:{method}", before=it["pricing_method"],
              after={"amount": to_text(D_opt(amount)), "resource": resource_id}, comment=note, project_id=project_id)


def decide_pricing(db: Database, actor: Actor, project_id: str, item_key: str, decision: str, *, comment: str) -> None:
    """decision: approve | approve_provisional | reject (for sums & allowances)."""
    it = get_item(db, project_id, item_key)
    act = {"approve": "approve", "approve_provisional": "approve_provisional", "reject": "reject"}[decision]
    approvals.authorize(actor, Entity.PRICING_DECISION.value, act, created_by=None)
    if it["pricing_status"] != Status.PENDING.value:
        raise Conflict(f"Pricing is '{it['pricing_status']}', not pending review.")
    if not comment:
        raise ValidationFailed("A comment/reason is required.", code="REASON_REQUIRED")
    new = {"approve": Status.APPROVED.value, "approve_provisional": Status.PROVISIONAL.value,
           "reject": Status.REJECTED.value}[decision]
    db.update("boq_items", {"pricing_status": new}, "id=?", (it["id"],))
    approvals.record(db, actor, Entity.PRICING_DECISION.value, item_key, act, project_id=project_id,
                     approved_value={"method": it["pricing_method"], "amount": it["pricing_amount"]}, comments=comment,
                     override_reason=comment if decision == "approve_provisional" else None)
