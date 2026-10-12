"""Global assumption library + project-level overrides, with versioning and approval gating."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..approvals import engine as approvals
from ..core.errors import Conflict, ImmutableRecord, NotFound, ValidationFailed
from ..core.money import D_opt
from ..core.timeutil import now_iso, parse_date, today_iso
from ..database import Database, rows_to_dicts
from ..models.actor import Actor
from ..models.enums import Entity, Status
from . import audit

FAMILIES = {
    "A": "Scope and design basis", "B": "Quantity and measurement", "C": "Materials", "D": "Labour and productivity",
    "E": "Plant", "F": "Logistics", "G": "Location and site conditions", "H": "Indirects", "I": "Commercial",
    "J": "Tax", "K": "Testing and handover", "L": "Risk and confidence",
}


@dataclass
class ResolvedAssumption:
    id: str
    name: str
    value: str | None
    unit: str | None
    value_type: str
    status: str                 # effective status of the value actually returned
    origin: str                 # project_override / global_default / unset
    engine_key: str | None = None
    override_reason: str | None = None
    version: int | None = None

    @property
    def approved(self) -> bool:
        return self.status == Status.APPROVED.value and self.value not in (None, "")

    @property
    def has_value(self) -> bool:
        return self.value not in (None, "")


def get_latest(db: Database, aid: str) -> dict:
    r = db.one("SELECT * FROM assumptions WHERE id=? ORDER BY version DESC LIMIT 1", (aid,))
    if not r:
        raise NotFound(f"Assumption {aid} not found.")
    return dict(r)


def get_current_approved(db: Database, aid: str) -> dict | None:
    r = db.one("SELECT * FROM assumptions WHERE id=? AND status='Approved' ORDER BY version DESC LIMIT 1", (aid,))
    return dict(r) if r else None


def list_assumptions(db: Database, family: str | None = None, status: str | None = None, q: str | None = None) -> list[dict]:
    sql = ("SELECT a.* FROM assumptions a WHERE a.version=(SELECT MAX(version) FROM assumptions WHERE id=a.id)")
    params: list[Any] = []
    if family:
        sql += " AND a.family=?"; params.append(family)
    if status:
        sql += " AND a.status=?"; params.append(status)
    if q:
        sql += " AND (a.name LIKE ? OR a.description LIKE ? OR a.id LIKE ?)"; params += [f"%{q}%"] * 3
    return rows_to_dicts(db.all(sql + " ORDER BY a.id", params))


def create_assumption(db: Database, actor: Actor, *, id: str, family: str, name: str, description: str = "",
                      applies_to: str = "ALL", value_type: str = "number", default_value: str | None = None,
                      unit: str | None = None, engine_key: str | None = None, source: str | None = None,
                      evidence: str | None = None, confidence: str = "Low", mandatory_for_projects: bool = False,
                      valid_from: str | None = None, valid_to: str | None = None, is_synthetic: bool = False,
                      applicability: str | None = None, notes: str | None = None) -> str:
    approvals.require_author(actor)
    if family not in FAMILIES:
        raise ValidationFailed(f"family must be one of {list(FAMILIES)}")
    if db.one("SELECT 1 FROM assumptions WHERE id=?", (id,)):
        raise Conflict(f"Assumption {id} already exists; use revise_assumption.")
    if value_type in ("number", "percent") and default_value not in (None, "") and D_opt(default_value) is None:
        raise ValidationFailed("default_value must be numeric for numeric assumptions.")
    db.insert("assumptions", dict(
        id=id, version=1, family=family, name=name, description=description, applies_to=applies_to,
        applicability=applicability, value_type=value_type, default_value=default_value or None, unit=unit,
        engine_key=engine_key, mandatory_for_projects=int(mandatory_for_projects), confidence=confidence,
        source=source, evidence=evidence, valid_from=valid_from, valid_to=valid_to, status=Status.DRAFT.value,
        notes=notes, is_synthetic=int(is_synthetic), created_by=actor.username, created_at=now_iso()))
    audit.log(db, actor, "assumption", id, "create", after={"name": name, "default": default_value})
    return id


def revise_assumption(db: Database, actor: Actor, aid: str, **changes) -> int:
    """Approved assumptions are immutable: any change creates a new Draft version."""
    approvals.require_author(actor)
    cur = get_latest(db, aid)
    allowed = {"name", "description", "default_value", "unit", "source", "evidence", "confidence", "valid_from",
               "valid_to", "notes", "applicability", "applies_to", "mandatory_for_projects"}
    bad = set(changes) - allowed
    if bad:
        raise ValidationFailed(f"Not editable: {sorted(bad)}")
    if cur["status"] in (Status.DRAFT.value, Status.PENDING.value, Status.REJECTED.value):
        db.update("assumptions", {**changes, "status": Status.DRAFT.value}, "pk=?", (cur["pk"],))
        audit.log(db, actor, "assumption", aid, "edit_draft", before={k: cur[k] for k in changes}, after=changes)
        return cur["version"]
    new = {k: v for k, v in cur.items() if k not in ("pk",)}
    new.update(changes)
    new.update(version=cur["version"] + 1, status=Status.DRAFT.value, created_by=actor.username,
               created_at=now_iso(), approved_by=None, approved_at=None)
    db.insert("assumptions", new)
    audit.log(db, actor, "assumption", aid, "revise", before={k: cur[k] for k in changes}, after=changes,
              comment=f"new version {new['version']}")
    return new["version"]


def submit_assumption(db: Database, actor: Actor, aid: str) -> None:
    approvals.require_author(actor)
    cur = get_latest(db, aid)
    if cur["status"] not in (Status.DRAFT.value, Status.REJECTED.value):
        raise Conflict(f"Cannot submit assumption in status {cur['status']}.")
    db.update("assumptions", {"status": Status.PENDING.value}, "pk=?", (cur["pk"],))
    audit.log(db, actor, "assumption", aid, "submit", after=Status.PENDING.value)


def approve_assumption(db: Database, actor: Actor, aid: str, *, comments: str | None = None,
                       evidence: str | None = None) -> None:
    cur = get_latest(db, aid)
    approvals.authorize(actor, Entity.ASSUMPTION.value, "approve", created_by=cur["created_by"])
    if cur["status"] != Status.PENDING.value:
        raise Conflict(f"Assumption must be Pending Review (is {cur['status']}).", code="NOT_PENDING")
    with db.tx():
        for old in db.all("SELECT pk FROM assumptions WHERE id=? AND status='Approved' AND version<?", (aid, cur["version"])):
            db.update("assumptions", {"status": Status.SUPERSEDED.value}, "pk=?", (old["pk"],))
        db.update("assumptions", {"status": Status.APPROVED.value, "approved_by": actor.username,
                                  "approved_at": now_iso()}, "pk=?", (cur["pk"],))
        approvals.record(db, actor, Entity.ASSUMPTION.value, aid, "approve", version=cur["version"],
                         approved_value=cur["default_value"], evidence=evidence or cur["evidence"], comments=comments)


def reject_assumption(db: Database, actor: Actor, aid: str, reason: str) -> None:
    cur = get_latest(db, aid)
    approvals.authorize(actor, Entity.ASSUMPTION.value, "reject")
    if cur["status"] in (Status.APPROVED.value, Status.SUPERSEDED.value):
        raise ImmutableRecord("Approved assumptions cannot be rejected; revise to create a new version.")
    db.update("assumptions", {"status": Status.REJECTED.value}, "pk=?", (cur["pk"],))
    approvals.record(db, actor, Entity.ASSUMPTION.value, aid, "reject", version=cur["version"], comments=reason)


# ----------------------------------------------------------------------------- project level
def adopt(db: Database, actor: Actor, project_id: str, aid: str) -> None:
    approvals.require_author(actor)
    if db.one("SELECT 1 FROM project_assumptions WHERE project_id=? AND assumption_id=?", (project_id, aid)):
        return
    g = get_latest(db, aid)
    db.insert("project_assumptions", dict(project_id=project_id, assumption_id=aid, base_version=g["version"],
                                          version_no=1, has_override=0, status=Status.DRAFT.value,
                                          created_by=actor.username, created_at=now_iso()))


def adopt_mandatory(db: Database, actor: Actor | str, project_id: str) -> int:
    n = 0
    for a in list_assumptions(db):
        if a["mandatory_for_projects"] and not db.one(
                "SELECT 1 FROM project_assumptions WHERE project_id=? AND assumption_id=?", (project_id, a["id"])):
            db.insert("project_assumptions", dict(project_id=project_id, assumption_id=a["id"], base_version=a["version"],
                                                  version_no=1, has_override=0, status=Status.DRAFT.value,
                                                  created_by=getattr(actor, "username", actor), created_at=now_iso()))
            n += 1
    return n


def _latest_project_row(db: Database, project_id: str, aid: str) -> dict | None:
    r = db.one("SELECT * FROM project_assumptions WHERE project_id=? AND assumption_id=? "
               "AND status<>'Superseded' ORDER BY version_no DESC LIMIT 1", (project_id, aid))
    return dict(r) if r else None


def set_override(db: Database, actor: Actor, project_id: str, aid: str, value: str, reason: str) -> int:
    """Propose a project-specific value. Does NOT touch the global library; needs approval to take effect."""
    approvals.require_author(actor)
    if not reason or not reason.strip():
        raise ValidationFailed("A reason is required for a project override.", code="REASON_REQUIRED")
    g = get_latest(db, aid)
    if g["value_type"] in ("number", "percent") and D_opt(value) is None:
        raise ValidationFailed(f"'{value}' is not numeric.")
    cur = _latest_project_row(db, project_id, aid)
    vno = (db.scalar("SELECT MAX(version_no) FROM project_assumptions WHERE project_id=? AND assumption_id=?",
                     (project_id, aid)) or 0) + 1
    if cur and cur["status"] in (Status.DRAFT.value, Status.PENDING.value, Status.REJECTED.value) and cur["has_override"]:
        db.update("project_assumptions", {"override_value": value, "reason": reason, "status": Status.PENDING.value},
                  "pk=?", (cur["pk"],))
        pk = cur["pk"]
    else:
        # previous approved override stays in force until the new one is approved
        pk = db.insert("project_assumptions", dict(
            project_id=project_id, assumption_id=aid, base_version=g["version"], version_no=vno, override_value=value,
            has_override=1, reason=reason, status=Status.PENDING.value, created_by=actor.username, created_at=now_iso()))
    audit.log(db, actor, "project_assumption", f"{project_id}/{aid}", "propose_override",
              before=cur["override_value"] if cur else None, after=value, comment=reason, project_id=project_id)
    return pk


def approve_override(db: Database, actor: Actor, project_id: str, aid: str, *, comments: str | None = None) -> None:
    row = db.one("SELECT * FROM project_assumptions WHERE project_id=? AND assumption_id=? AND status='Pending Review' "
                 "ORDER BY version_no DESC LIMIT 1", (project_id, aid))
    if not row:
        raise NotFound("No pending override for this assumption.")
    approvals.authorize(actor, Entity.PROJECT_ASSUMPTION.value, "approve", created_by=row["created_by"])
    with db.tx():
        prev = db.one("SELECT * FROM project_assumptions WHERE project_id=? AND assumption_id=? AND status='Approved'",
                      (project_id, aid))
        if prev:
            db.update("project_assumptions", {"status": Status.SUPERSEDED.value}, "pk=?", (prev["pk"],))
        db.update("project_assumptions", {"status": Status.APPROVED.value, "approved_by": actor.username,
                                          "approved_at": now_iso()}, "pk=?", (row["pk"],))
        approvals.record(db, actor, Entity.PROJECT_ASSUMPTION.value, f"{project_id}/{aid}", "approve", project_id=project_id,
                         version=row["version_no"], previous_value=prev["override_value"] if prev else None,
                         approved_value=row["override_value"], comments=comments, override_reason=row["reason"])


def reject_override(db: Database, actor: Actor, project_id: str, aid: str, reason: str) -> None:
    approvals.authorize(actor, Entity.PROJECT_ASSUMPTION.value, "reject")
    n = db.update("project_assumptions", {"status": Status.REJECTED.value},
                  "project_id=? AND assumption_id=? AND status='Pending Review'", (project_id, aid))
    if not n:
        raise NotFound("No pending override.")
    approvals.record(db, actor, Entity.PROJECT_ASSUMPTION.value, f"{project_id}/{aid}", "reject", project_id=project_id,
                     comments=reason)


def resolve(db: Database, project_id: str | None, aid: str, as_of: str | None = None) -> ResolvedAssumption:
    """Effective value for a project: approved override > pending/draft override (flagged) > approved global default
    > unapproved global default (flagged) > unset."""
    g = get_latest(db, aid)
    ga = get_current_approved(db, aid)
    gv = ga or g
    as_of = as_of or today_iso()
    if project_id:
        rows = rows_to_dicts(db.all("SELECT * FROM project_assumptions WHERE project_id=? AND assumption_id=? "
                                    "ORDER BY version_no DESC", (project_id, aid)))
        approved = next((r for r in rows if r["has_override"] and r["status"] == Status.APPROVED.value), None)
        if approved:
            return ResolvedAssumption(aid, g["name"], approved["override_value"], g["unit"], g["value_type"],
                                      Status.APPROVED.value, "project_override", g["engine_key"], approved["reason"],
                                      approved["version_no"])
        pending = next((r for r in rows if r["has_override"] and r["status"] in (
            Status.PENDING.value, Status.DRAFT.value)), None)
        if pending:
            return ResolvedAssumption(aid, g["name"], pending["override_value"], g["unit"], g["value_type"],
                                      pending["status"], "project_override", g["engine_key"], pending["reason"],
                                      pending["version_no"])
    # global default
    valid_to = parse_date(gv.get("valid_to"))
    st = gv["status"]
    if valid_to and valid_to < parse_date(as_of):
        st = Status.EXPIRED.value
    return ResolvedAssumption(aid, g["name"], gv["default_value"], g["unit"], g["value_type"], st,
                              "global_default" if gv["default_value"] not in (None, "") else "unset",
                              g["engine_key"], None, gv["version"])


def resolve_key(db: Database, project_id: str | None, engine_key: str, as_of: str | None = None) -> ResolvedAssumption | None:
    r = db.one("SELECT id FROM assumptions WHERE engine_key=? ORDER BY version DESC LIMIT 1", (engine_key,))
    return resolve(db, project_id, r["id"], as_of) if r else None


def project_assumption_status(db: Database, project_id: str) -> list[dict]:
    """All adopted assumptions with their effective value/status (for UI + reconciliation)."""
    out = []
    for r in db.all("SELECT DISTINCT assumption_id FROM project_assumptions WHERE project_id=? ORDER BY assumption_id",
                    (project_id,)):
        ra = resolve(db, project_id, r["assumption_id"])
        out.append(dict(id=ra.id, name=ra.name, value=ra.value, unit=ra.unit, status=ra.status, origin=ra.origin,
                        engine_key=ra.engine_key, reason=ra.override_reason))
    return out
