"""Projects: creation, archiving, file-area management."""
from __future__ import annotations

import shutil
from pathlib import Path

from ..approvals import engine as approvals
from ..config import get_settings
from ..core.errors import Conflict, NotFound, ValidationFailed
from ..core.timeutil import now_iso
from ..database import Database, row_to_dict, rows_to_dicts
from ..models.actor import Actor
from . import assumptions as asm_service
from . import audit


def next_project_id(db: Database) -> str:
    n = db.scalar("SELECT COUNT(*) FROM projects") or 0
    while True:
        n += 1
        pid = f"PRJ-{n:04d}"
        if not db.one("SELECT 1 FROM projects WHERE id=?", (pid,)):
            return pid


def project_dir(project_id: str, sub: str = "") -> Path:
    p = get_settings().projects_dir / project_id / sub
    p.mkdir(parents=True, exist_ok=True)
    return p


def output_dir(project_id: str) -> Path:
    p = get_settings().outputs_dir / project_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def create_project(db: Database, actor: Actor, *, name: str, client: str = "", location: str = "",
                   region: str = "KSA-ALL", currency: str = "SAR", design_stage: str = "", tax_category: str | None = None,
                   is_demo: bool = False, tender_ref: str = "", notes: str = "", id: str | None = None,
                   rate_as_of_date: str | None = None) -> str:
    approvals.require_author(actor)
    if not name.strip():
        raise ValidationFailed("Project name is required.")
    if not db.one("SELECT 1 FROM regions WHERE code=?", (region,)):
        raise ValidationFailed(f"Unknown region '{region}'.")
    pid = id or next_project_id(db)
    if db.one("SELECT 1 FROM projects WHERE id=?", (pid,)):
        raise Conflict(f"Project {pid} already exists.")
    with db.tx():
        db.insert("projects", dict(id=pid, name=name, client=client, location=location, region=region,
                                   currency=currency, design_stage=design_stage, status="Active", is_demo=int(is_demo),
                                   tax_category=tax_category, tender_ref=tender_ref, notes=notes,
                                   rate_as_of_date=rate_as_of_date, created_by=actor.username, created_at=now_iso()))
        n = asm_service.adopt_mandatory(db, actor, pid)
        audit.log(db, actor, "project", pid, "create", after={"name": name, "adopted_assumptions": n}, project_id=pid)
    project_dir(pid)
    return pid


def get_project(db: Database, pid: str) -> dict:
    r = db.one("SELECT * FROM projects WHERE id=?", (pid,))
    if not r:
        raise NotFound(f"Project {pid} not found.")
    return dict(r)


def require_active(db: Database, pid: str) -> dict:
    p = get_project(db, pid)
    if p["status"] == "Archived":
        raise Conflict(f"Project {pid} is archived (read-only). Unarchive it to make changes.", code="PROJECT_ARCHIVED")
    return p


def list_projects(db: Database, include_archived: bool = False) -> list[dict]:
    sql = "SELECT * FROM projects" + ("" if include_archived else " WHERE status<>'Archived'") + " ORDER BY id"
    return rows_to_dicts(db.all(sql))


def update_project(db: Database, actor: Actor, pid: str, **changes) -> None:
    approvals.require_author(actor)
    require_active(db, pid)
    allowed = {"name", "client", "location", "region", "design_stage", "tax_category", "rate_as_of_date",
               "tender_ref", "submission_date", "notes", "commercial_policy_id"}
    bad = set(changes) - allowed
    if bad:
        raise ValidationFailed(f"Not editable: {sorted(bad)}")
    before = get_project(db, pid)
    db.update("projects", changes, "id=?", (pid,))
    audit.log(db, actor, "project", pid, "update", before={k: before[k] for k in changes}, after=changes, project_id=pid)


def archive_project(db: Database, actor: Actor, pid: str, reason: str) -> None:
    approvals.authorize(actor, "estimate", "approve")  # Commercial Approver / Administrator
    if not reason:
        raise ValidationFailed("Archive reason required.")
    require_active(db, pid)
    db.update("projects", {"status": "Archived", "archived_at": now_iso()}, "id=?", (pid,))
    audit.log(db, actor, "project", pid, "archive", comment=reason, project_id=pid)


def unarchive_project(db: Database, actor: Actor, pid: str, reason: str) -> None:
    approvals.authorize(actor, "estimate", "approve")
    db.update("projects", {"status": "Active", "archived_at": None}, "id=?", (pid,))
    audit.log(db, actor, "project", pid, "unarchive", comment=reason, project_id=pid)
