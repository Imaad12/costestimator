"""Indirect cost items, project duration proposals/approval, and the optional deterministic schedule model."""
from __future__ import annotations

from decimal import Decimal

from ..approvals import engine as approvals
from ..core.errors import Conflict, NotFound, ValidationFailed
from ..core.money import D, D_opt, to_text
from ..core.timeutil import now_iso
from ..database import Database, jload, rows_to_dicts
from ..estimators import duration as dur
from ..models.actor import Actor
from ..models.enums import Entity, Status
from . import assumptions as asm_service
from . import audit, projects

METHODS = ("fixed", "percent_of_direct", "per_day", "per_week", "per_month", "per_duration_month")
ALLOCATIONS = ("pro_rata_direct", "separate_line", "direct_trade")


def add_indirect(db: Database, actor: Actor, project_id: str, *, code: str, category: str, description: str, method: str,
                 amount=None, quantity="1", allocation_method: str = "pro_rata_direct", allocation_target: str | None = None,
                 included_in_subcontract: bool = False, duration_override_months=None, notes: str | None = None,
                 source: str | None = None, is_synthetic: bool = False) -> int:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    if method not in METHODS:
        raise ValidationFailed(f"method must be one of {METHODS}")
    if allocation_method not in ALLOCATIONS:
        raise ValidationFailed(f"allocation_method must be one of {ALLOCATIONS}")
    if allocation_method == "direct_trade" and not allocation_target:
        raise ValidationFailed("direct_trade allocation needs allocation_target (cost code prefix).")
    if amount not in (None, "") and (D_opt(amount) is None or D(amount) < 0):
        raise ValidationFailed("amount must be a non-negative number.")
    if db.one("SELECT 1 FROM indirect_items WHERE project_id=? AND code=?", (project_id, code)):
        raise Conflict(f"Indirect {code} exists; use revise_indirect().")
    iid = db.insert("indirect_items", dict(
        project_id=project_id, code=code, category=category, description=description, method=method,
        amount=to_text(D_opt(amount)), quantity=str(quantity), allocation_method=allocation_method,
        allocation_target=allocation_target, included_in_subcontract=int(included_in_subcontract),
        duration_override_months=to_text(D_opt(duration_override_months)), status=Status.DRAFT.value, version=1,
        notes=notes, source=source, is_synthetic=int(is_synthetic), created_by=actor.username, created_at=now_iso()))
    audit.log(db, actor, "indirect", f"{project_id}/{code}", "create", after={"method": method, "amount": amount}, project_id=project_id)
    return iid


def revise_indirect(db: Database, actor: Actor, project_id: str, code: str, **changes) -> int:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    cur = db.one("SELECT * FROM indirect_items WHERE project_id=? AND code=? AND status<>'Superseded' ORDER BY version DESC LIMIT 1",
                 (project_id, code))
    if not cur:
        raise NotFound(f"Indirect {code} not found.")
    allowed = {"category", "description", "method", "amount", "quantity", "allocation_method", "allocation_target",
               "included_in_subcontract", "duration_override_months", "notes", "source"}
    bad = set(changes) - allowed
    if bad:
        raise ValidationFailed(f"Not editable: {sorted(bad)}")
    if "amount" in changes and changes["amount"] not in (None, ""):
        changes["amount"] = to_text(D(changes["amount"]))
    if cur["status"] in (Status.DRAFT.value, Status.PENDING.value, Status.REJECTED.value):
        db.update("indirect_items", {**changes, "status": Status.DRAFT.value}, "id=?", (cur["id"],))
        audit.log(db, actor, "indirect", f"{project_id}/{code}", "edit_draft", before={k: cur[k] for k in changes}, after=changes, project_id=project_id)
        return cur["id"]
    new = {k: v for k, v in dict(cur).items() if k != "id"}
    new.update(changes)
    new.update(version=cur["version"] + 1, status=Status.DRAFT.value, created_by=actor.username, created_at=now_iso(),
               approved_by=None, approved_at=None)
    nid = db.insert("indirect_items", new)
    audit.log(db, actor, "indirect", f"{project_id}/{code}", "revise", before={k: cur[k] for k in changes}, after=changes, project_id=project_id)
    return nid


def submit_indirect(db: Database, actor: Actor, project_id: str, code: str) -> None:
    approvals.require_author(actor)
    n = db.update("indirect_items", {"status": Status.PENDING.value}, "project_id=? AND code=? AND status='Draft'", (project_id, code))
    if not n:
        raise Conflict("Only a Draft indirect can be submitted.")


def approve_indirect(db: Database, actor: Actor, project_id: str, code: str, *, comments: str | None = None) -> None:
    cur = db.one("SELECT * FROM indirect_items WHERE project_id=? AND code=? AND status='Pending Review' ORDER BY version DESC LIMIT 1",
                 (project_id, code))
    if not cur:
        raise NotFound("No pending indirect with that code.")
    approvals.authorize(actor, Entity.INDIRECT.value, "approve", created_by=cur["created_by"])
    if cur["amount"] is None:
        raise ValidationFailed("An indirect without an amount cannot be approved.")
    with db.tx():
        for old in db.all("SELECT id FROM indirect_items WHERE project_id=? AND code=? AND status='Approved'", (project_id, code)):
            db.update("indirect_items", {"status": Status.SUPERSEDED.value}, "id=?", (old["id"],))
        db.update("indirect_items", {"status": Status.APPROVED.value, "approved_by": actor.username, "approved_at": now_iso()},
                  "id=?", (cur["id"],))
        approvals.record(db, actor, Entity.INDIRECT.value, f"{project_id}/{code}", "approve", project_id=project_id,
                         version=cur["version"], approved_value={"method": cur["method"], "amount": cur["amount"],
                                                                 "allocation": cur["allocation_method"]}, comments=comments)


def list_indirects(db: Database, project_id: str) -> list[dict]:
    return rows_to_dicts(db.all("SELECT * FROM indirect_items WHERE project_id=? AND status<>'Superseded' ORDER BY code", (project_id,)))


# ---------------------------------------------------------------------------- duration
def propose_duration(db: Database, actor: Actor, project_id: str, months, source_type: str, basis_note: str) -> int:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    if source_type not in ("estimator_input", "labour_derived", "schedule_model", "ai_proposal"):
        raise ValidationFailed("Invalid duration source_type.")
    m = D_opt(months)
    if m is None or m <= 0:
        raise ValidationFailed("Duration (months) must be > 0.")
    pid = db.insert("project_durations", dict(project_id=project_id, months=to_text(m), source_type=source_type,
                                              basis_note=basis_note, status=Status.PENDING.value, proposed_by=actor.username,
                                              proposed_at=now_iso()))
    audit.log(db, actor, "project_duration", project_id, "propose", after={"months": to_text(m), "source": source_type},
              comment=basis_note, project_id=project_id)
    return pid


def approve_duration(db: Database, actor: Actor, duration_id: int, *, comments: str | None = None) -> None:
    r = db.one("SELECT * FROM project_durations WHERE id=?", (duration_id,))
    if not r:
        raise NotFound("Duration proposal not found.")
    approvals.authorize(actor, Entity.PROJECT_DURATION.value, "approve", created_by=r["proposed_by"])
    if r["source_type"] == "ai_proposal" and not comments:
        raise ValidationFailed("An AI-proposed duration needs an explicit reviewer comment confirming the basis.")
    if r["status"] != Status.PENDING.value:
        raise Conflict(f"Duration proposal is {r['status']}.")
    with db.tx():
        for old in db.all("SELECT id FROM project_durations WHERE project_id=? AND status='Approved'", (r["project_id"],)):
            db.update("project_durations", {"status": Status.SUPERSEDED.value}, "id=?", (old["id"],))
        db.update("project_durations", {"status": Status.APPROVED.value, "approved_by": actor.username,
                                        "approved_at": now_iso()}, "id=?", (duration_id,))
        approvals.record(db, actor, Entity.PROJECT_DURATION.value, r["project_id"], "approve", project_id=r["project_id"],
                         approved_value={"months": r["months"], "source": r["source_type"]}, comments=comments)


def list_durations(db: Database, project_id: str) -> list[dict]:
    return rows_to_dicts(db.all("SELECT * FROM project_durations WHERE project_id=? ORDER BY id DESC", (project_id,)))


# ---------------------------------------------------------------------------- schedule model
def set_tasks(db: Database, actor: Actor, project_id: str, tasks: list[dict]) -> None:
    """Replace the draft task list (human-entered). Predecessors may carry a relationship type and lag ('A', 'B-SS+2', 'C-FF-1');
    optional per-task wbs_code, snet / fnlt constraints. Validates dependencies (no cycles, no unknown predecessors)."""
    from . import programme as prog_service
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    codes = [t["task_code"] for t in tasks]
    if len(codes) != len(set(codes)):
        raise ValidationFailed("Duplicate task_code in the task list.", code="SCHEDULE_DUPLICATE_TASK")
    norm = []
    for t in tasks:
        pre = t.get("predecessors") or []
        norm.append({**t, "predecessors": ",".join(pre) if isinstance(pre, list) else pre})
    prog_service.validate_tasks(norm, prog_service.calendar_for(db, project_id, include_unapproved=True))
    with db.tx():
        db.execute("DELETE FROM schedule_tasks WHERE project_id=?", (project_id,))
        for t in norm:
            if t.get("wbs_code") and not db.one("SELECT 1 FROM wbs_nodes WHERE project_id=? AND code=?", (project_id, t["wbs_code"])):
                raise ValidationFailed(f"Task {t['task_code']}: WBS {t['wbs_code']} not found.", code="WBS_PARENT")
            db.insert("schedule_tasks", dict(project_id=project_id, task_code=t["task_code"], name=t["name"],
                                             duration_days=str(t["duration_days"]),
                                             predecessors=t["predecessors"], cost_code=t.get("cost_code"), wbs_code=t.get("wbs_code"),
                                             snet=None if t.get("snet") in (None, "") else str(t["snet"]),
                                             fnlt=None if t.get("fnlt") in (None, "") else str(t["fnlt"]), status=Status.DRAFT.value))
    audit.log(db, actor, "schedule", project_id, "set_tasks", after={"count": len(tasks)}, project_id=project_id)


def propose_duration_from_schedule(db: Database, actor: Actor, project_id: str) -> int:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    from . import programme as prog_service
    rows = rows_to_dicts(db.all("SELECT * FROM schedule_tasks WHERE project_id=?", (project_id,)))
    if not rows:
        raise ValidationFailed("No schedule tasks.")
    out = prog_service.programme.schedule(prog_service.to_engine_tasks(rows, prog_service.calendar_for(db, project_id, include_unapproved=False)))
    res = dur.ScheduleResult(out.project_days, out.critical_path, {c: t.ef for c, t in out.tasks.items()})
    tasks = rows
    wdpm = asm_service.resolve_key(db, project_id, "calendar.working_days_per_month")
    if not wdpm or not wdpm.has_value or not wdpm.approved:
        raise ValidationFailed("Approved assumption calendar.working_days_per_month is required to convert days to months.",
                               code="CALENDAR_REQUIRED")
    months = dur.days_to_months(res.project_days, D(wdpm.value))
    return propose_duration(db, actor, project_id, months, "schedule_model",
                            f"CPM over {len(tasks)} tasks: {res.project_days} working days; critical path {' > '.join(res.critical_path)}")
