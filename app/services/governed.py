"""Governed parameters: versioned, validated, human-approved numeric inputs (see estimators/param_kinds.py).

Lifecycle: propose (Draft) -> submit (Pending Review) -> approve/reject by a permitted human (server-side `authorize`). Approved rows are
immutable; a change is a new version and the approved one stays in force until the new one is approved. No defaults are ever supplied.
"""
from __future__ import annotations

import json

from ..approvals import engine as approvals
from ..core.errors import Conflict, NotFound, ValidationFailed
from ..core.timeutil import now_iso
from ..database import Database
from ..estimators.param_kinds import KINDS
from ..models.actor import Actor
from ..models.enums import Status
from . import audit, projects

OPEN = (Status.DRAFT.value, Status.PENDING.value)


def _entity(kind: str) -> str:
    return f"param:{kind}"


def _kind(kind: str):
    if kind not in KINDS:
        raise ValidationFailed(f"Unknown parameter kind '{kind}'. Known: {sorted(KINDS)}", code="PARAM_KIND")
    return KINDS[kind]


def kinds() -> list[dict]:
    from ..estimators.param_kinds import EXAMPLES
    return [dict(kind=k.name, label=k.label, approvers=sorted(k.approvers), description=k.description, fields=EXAMPLES.get(k.name, {})) for k in KINDS.values()]


def _db_checks(db: Database, kind: str, code: str, clean: dict) -> None:
    """Checks that need reference data (resources, templates)."""
    if kind == "plant_hire_terms" and not db.one("SELECT 1 FROM resources WHERE id=? AND resource_type IN ('plant','equipment')", (clean["resource_id"],)):
        raise ValidationFailed(f"resource_id {clean['resource_id']} is not a plant/equipment resource.", code="PARAM_FIELD")
    if kind == "mto_factor":
        from . import mto
        mto.check_factor(db, code, clean)
    if kind == "method_alternative":
        from . import methods
        methods.check_alternative(db, clean)


def propose(db: Database, actor: Actor, kind: str, code: str, data: dict, *, project_id: str | None = None, source: str | None = None,
            basis_note: str | None = None, is_synthetic: bool = False, submit: bool = False) -> int:
    approvals.require_author(actor)
    k = _kind(kind)
    if project_id:
        projects.require_active(db, project_id)
    code = (code or "").strip()
    if not code:
        raise ValidationFailed("code is required.", code="PARAM_FIELD")
    clean = k.validate(dict(data or {}))
    if not (source or "").strip() and not is_synthetic:
        raise ValidationFailed("A source / basis is required: say where this number comes from (company record, contract, approved document).",
                               code="PARAM_SOURCE")
    _db_checks(db, kind, code, clean)
    with db.tx():
        prev = db.one("SELECT MAX(version) v FROM governed_params WHERE COALESCE(project_id,'')=? AND kind=? AND code=?",
                      (project_id or "", kind, code))
        version = (prev["v"] or 0) + 1
        for r in db.all("SELECT id FROM governed_params WHERE COALESCE(project_id,'')=? AND kind=? AND code=? AND status IN (?,?,?)",
                        (project_id or "", kind, code, *OPEN, Status.REJECTED.value)):
            db.update("governed_params", {"status": Status.SUPERSEDED.value}, "id=?", (r["id"],))
        pid = db.insert("governed_params", dict(
            project_id=project_id, kind=kind, code=code, version=version, status=Status.PENDING.value if submit else Status.DRAFT.value,
            data_json=json.dumps(clean, sort_keys=True), source=source, basis_note=basis_note, is_synthetic=int(is_synthetic),
            created_by=actor.username, created_at=now_iso()))
        audit.log(db, actor, _entity(kind), f"{project_id or 'GLOBAL'}/{code}", "propose", after={"version": version, "data": clean}, project_id=project_id)
    return pid


class _DryRun(Exception):
    pass


def import_csv(db: Database, actor: Actor, path, *, project_id: str | None = None, dry_run: bool = False) -> dict:
    """Load governed-parameter PROPOSALS from a CSV (columns: kind, code, source, basis_note, project_id, data_json).

    Every valid row becomes a Draft; nothing is submitted or approved here, and any status column is ignored. Invalid rows are reported,
    not loaded. Rows flagged is_synthetic are loaded as synthetic. No value is defaulted."""
    import csv
    from pathlib import Path
    approvals.require_author(actor)
    created, errors = [], []
    with Path(path).open(newline="", encoding="utf-8-sig") as fh:
        for n, row in enumerate(csv.DictReader(fh), start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            if not any(row.values()):
                continue
            try:
                data = json.loads(row.get("data_json") or "{}")
                if not isinstance(data, dict):
                    raise ValueError("data_json must be a JSON object")
                args = (db, actor, row.get("kind", ""), row.get("code", ""), data)
                kw = dict(project_id=row.get("project_id") or project_id, source=row.get("source") or None, basis_note=row.get("basis_note") or None,
                          is_synthetic=row.get("is_synthetic", "").lower() in ("1", "true", "yes"))
                if dry_run:                                   # validate inside a transaction that is always rolled back: nothing is kept
                    try:
                        with db.tx():
                            propose(*args, **kw)
                            raise _DryRun()
                    except _DryRun:
                        created.append(0)
                else:
                    created.append(propose(*args, **kw))
            except (ValidationFailed, ValueError, NotFound, Conflict) as e:
                errors.append({"row": n, "code": row.get("code", ""), "error": str(e)})
    if dry_run:
        return {"would_create": len(created), "errors": errors, "dry_run": True}
    return {"created_ids": created, "errors": errors, "status": "Draft"}


def _get(db: Database, pid: int) -> dict:
    r = db.one("SELECT * FROM governed_params WHERE id=?", (pid,))
    if not r:
        raise NotFound(f"Parameter {pid} not found.")
    return dict(r)


def submit(db: Database, actor: Actor, pid: int) -> None:
    approvals.require_author(actor)
    r = _get(db, pid)
    if r["status"] != Status.DRAFT.value:
        raise Conflict("Only a Draft parameter can be submitted for review.")
    db.update("governed_params", {"status": Status.PENDING.value}, "id=?", (pid,))
    audit.log(db, actor, _entity(r["kind"]), f"{r['project_id'] or 'GLOBAL'}/{r['code']}", "submit", project_id=r["project_id"])


def approve(db: Database, actor: Actor, pid: int, *, comments: str | None = None) -> None:
    r = _get(db, pid)
    if r["status"] != Status.PENDING.value:
        raise Conflict("Only a Pending Review parameter can be approved.")
    approvals.authorize(actor, _entity(r["kind"]), "approve", created_by=r["created_by"])
    if r["project_id"]:
        projects.require_active(db, r["project_id"])
    with db.tx():
        for old in db.all("SELECT id FROM governed_params WHERE COALESCE(project_id,'')=? AND kind=? AND code=? AND status='Approved'",
                          (r["project_id"] or "", r["kind"], r["code"])):
            db.update("governed_params", {"status": Status.SUPERSEDED.value}, "id=?", (old["id"],))
        db.update("governed_params", {"status": Status.APPROVED.value, "approved_by": actor.username, "approved_at": now_iso()}, "id=?", (pid,))
        approvals.record(db, actor, _entity(r["kind"]), f"{r['project_id'] or 'GLOBAL'}/{r['code']}", "approve", project_id=r["project_id"],
                         version=r["version"], approved_value=json.loads(r["data_json"]), evidence=r["source"], comments=comments)


def reject(db: Database, actor: Actor, pid: int, *, comments: str) -> None:
    r = _get(db, pid)
    if r["status"] != Status.PENDING.value:
        raise Conflict("Only a Pending Review parameter can be rejected.")
    approvals.authorize(actor, _entity(r["kind"]), "reject", created_by=r["created_by"])
    if not (comments or "").strip():
        raise ValidationFailed("A rejection needs a reason.")
    db.update("governed_params", {"status": Status.REJECTED.value}, "id=?", (pid,))
    approvals.record(db, actor, _entity(r["kind"]), f"{r['project_id'] or 'GLOBAL'}/{r['code']}", "reject", project_id=r["project_id"],
                     version=r["version"], comments=comments)


def _row(r) -> dict:
    d = dict(r)
    d["data"] = json.loads(d["data_json"])
    d["scope"] = "project" if d["project_id"] else "global"
    return d


def list_params(db: Database, kind: str | None = None, project_id: str | None = None, include_global: bool = True) -> list[dict]:
    q, a = "SELECT * FROM governed_params WHERE status<>'Superseded'", []
    if kind:
        q += " AND kind=?"; a.append(kind)
    if project_id is not None:
        q += " AND (project_id=?" + (" OR project_id IS NULL" if include_global else "") + ")"; a.append(project_id)
    return [_row(r) for r in db.all(q + " ORDER BY kind, code, version", tuple(a))]


def effective(db: Database, project_id: str, kind: str, *, include_unapproved: bool = False) -> list[dict]:
    """One row per code in force for the project: project-scoped over company-wide; Approved only, unless a preliminary view is asked for
    (then a newer Draft/Pending revision replaces the approved one and is flagged `unapproved`)."""
    rows = [_row(r) for r in db.all("SELECT * FROM governed_params WHERE kind=? AND (project_id=? OR project_id IS NULL) "
                                    "AND status IN ('Approved','Draft','Pending Review') ORDER BY version", (kind, project_id))]
    best: dict[str, dict] = {}
    for scope in ("global", "project"):                   # project rows override global rows of the same code
        by: dict[str, dict] = {}
        for r in rows:
            if r["scope"] != scope:
                continue
            if r["status"] == Status.APPROVED.value or include_unapproved:
                cur = by.get(r["code"])
                if cur is None or r["version"] > cur["version"]:
                    by[r["code"]] = r
        for code, r in by.items():
            r["unapproved"] = r["status"] != Status.APPROVED.value
            best[code] = r
    return sorted(best.values(), key=lambda r: r["code"])
