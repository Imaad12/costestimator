"""Clarification register, scope (inclusion/exclusion/qualification) register, and tender risk register."""
from __future__ import annotations

from ..approvals import engine as approvals
from ..core.errors import Conflict, NotFound, ValidationFailed
from ..core.money import D_opt, to_text
from ..core.timeutil import now_iso, today_iso
from ..database import Database, rows_to_dicts
from ..models.actor import Actor
from ..models.enums import Entity, Status
from . import audit, projects


# ---------------------------------------------------------------------------- clarifications
def _next(db: Database, table: str, prefix: str, project_id: str) -> str:
    n = (db.scalar(f"SELECT COUNT(*) FROM {table} WHERE project_id=?", (project_id,)) or 0) + 1
    return f"{prefix}-{project_id}-{n:03d}"


def add_clarification(db: Database, actor: Actor | str, project_id: str, question: str, *, trade: str | None = None,
                      boq_item_key: str | None = None, doc_ref: str | None = None, reason: str | None = None,
                      commercial_impact: str | None = None, cost_exposure=None, proposed_wording: str | None = None,
                      owner: str | None = None, suggested_by: str | None = None) -> str:
    """Create an OPEN clarification. AI/heuristic sources may call this (via suggestions); it is never created resolved."""
    if not isinstance(actor, str):
        approvals.require_author(actor)
    projects.require_active(db, project_id)
    if not question.strip():
        raise ValidationFailed("Question is required.")
    cid = _next(db, "clarifications", "CLR", project_id)
    db.insert("clarifications", dict(id=cid, project_id=project_id, question=question, trade=trade, boq_item_key=boq_item_key,
                                     doc_ref=doc_ref, reason=reason, commercial_impact=commercial_impact,
                                     cost_exposure=to_text(D_opt(cost_exposure)), proposed_wording=proposed_wording, owner=owner,
                                     status="Open", suggested_by=suggested_by, created_by=getattr(actor, "username", actor),
                                     created_at=now_iso()))
    audit.log(db, actor, "clarification", cid, "create", after={"question": question[:120]}, project_id=project_id)
    return cid


def resolve_clarification(db: Database, actor: Actor, cid: str, client_response: str, evidence: str) -> None:
    c = db.one("SELECT * FROM clarifications WHERE id=?", (cid,))
    if not c:
        raise NotFound(f"Clarification {cid} not found.")
    approvals.authorize(actor, Entity.CLARIFICATION.value, "approve")
    if not client_response or not evidence:
        raise ValidationFailed("Resolution needs the client response AND supporting evidence (e.g. addendum / email reference).",
                               code="EVIDENCE_REQUIRED")
    if c["status"] == "Resolved":
        raise Conflict("Already resolved.")
    db.update("clarifications", {"status": "Resolved", "client_response": client_response, "resolution_evidence": evidence,
                                 "resolution_date": today_iso(), "resolved_by": actor.username}, "id=?", (cid,))
    approvals.record(db, actor, Entity.CLARIFICATION.value, cid, "approve", project_id=c["project_id"],
                     approved_value={"status": "Resolved"}, evidence=evidence, comments=client_response)


def set_clarification_status(db: Database, actor: Actor, cid: str, status: str) -> None:
    approvals.require_author(actor)
    if status not in ("Open", "Submitted", "Withdrawn"):
        raise ValidationFailed("Use resolve_clarification() to resolve; allowed here: Open, Submitted, Withdrawn.")
    db.update("clarifications", {"status": status}, "id=?", (cid,))
    audit.log(db, actor, "clarification", cid, "status", after=status)


def list_clarifications(db: Database, project_id: str, status: str | None = None) -> list[dict]:
    sql, p = "SELECT * FROM clarifications WHERE project_id=?", [project_id]
    if status:
        sql += " AND status=?"; p.append(status)
    return rows_to_dicts(db.all(sql + " ORDER BY id", p))


# ---------------------------------------------------------------------------- scope register
def add_scope_entry(db: Database, actor: Actor | str, project_id: str, kind: str, description: str, *, trade: str | None = None,
                    boq_item_key: str | None = None, cost_code: str | None = None, rationale: str | None = None) -> str:
    if not isinstance(actor, str):
        approvals.require_author(actor)
    if kind not in ("inclusion", "exclusion", "qualification"):
        raise ValidationFailed("kind must be inclusion, exclusion or qualification.")
    if not description.strip():
        raise ValidationFailed("Description required.")
    sid = _next(db, "scope_register", {"inclusion": "INC", "exclusion": "EXC", "qualification": "QUA"}[kind], project_id)
    db.insert("scope_register", dict(id=sid, project_id=project_id, kind=kind, description=description, trade=trade,
                                     boq_item_key=boq_item_key, cost_code=cost_code, rationale=rationale, status=Status.DRAFT.value,
                                     created_by=getattr(actor, "username", actor), created_at=now_iso()))
    audit.log(db, actor, "scope_entry", sid, "create", after={"kind": kind, "desc": description[:100]}, project_id=project_id)
    return sid


def approve_scope_entry(db: Database, actor: Actor, sid: str, comments: str | None = None) -> None:
    r = db.one("SELECT * FROM scope_register WHERE id=?", (sid,))
    if not r:
        raise NotFound(f"Scope entry {sid} not found.")
    approvals.authorize(actor, Entity.EXCLUSION.value, "approve", created_by=r["created_by"])
    if r["kind"] == "exclusion" and not (r["rationale"] or comments):
        raise ValidationFailed("Material exclusions need a rationale or approver comment.", code="REASON_REQUIRED")
    db.update("scope_register", {"status": Status.APPROVED.value, "approved_by": actor.username, "approved_at": now_iso()}, "id=?", (sid,))
    approvals.record(db, actor, Entity.EXCLUSION.value, sid, "approve", project_id=r["project_id"],
                     approved_value={"kind": r["kind"], "description": r["description"]}, comments=comments or r["rationale"])


def list_scope(db: Database, project_id: str, kind: str | None = None) -> list[dict]:
    sql, p = "SELECT * FROM scope_register WHERE project_id=?", [project_id]
    if kind:
        sql += " AND kind=?"; p.append(kind)
    return rows_to_dicts(db.all(sql + " ORDER BY id", p))


# ---------------------------------------------------------------------------- risks
def add_risk(db: Database, actor: Actor, project_id: str, title: str, *, description: str = "", trade: str | None = None,
             probability: str | None = None, impact: str | None = None, cost_exposure=None, mitigation: str | None = None,
             owner: str | None = None) -> str:
    approvals.require_author(actor)
    rid = _next(db, "risks", "RSK", project_id)
    db.insert("risks", dict(id=rid, project_id=project_id, title=title, description=description, trade=trade,
                            probability=probability, impact=impact, cost_exposure=to_text(D_opt(cost_exposure)),
                            mitigation=mitigation, owner=owner, status="Open", created_by=actor.username, created_at=now_iso()))
    audit.log(db, actor, "risk", rid, "create", after={"title": title}, project_id=project_id)
    return rid


def list_risks(db: Database, project_id: str) -> list[dict]:
    return rows_to_dicts(db.all("SELECT * FROM risks WHERE project_id=? ORDER BY id", (project_id,)))
