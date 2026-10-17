"""Productivity norms, workforce profiles, work activities, resource-constrained programme and crew scenarios.

Everything numeric is entered by a person and carried as a versioned, sourced, approvable record. Nothing here supplies a productivity value, a crew split or a
cost: a missing norm is a reported gap (with its effect on the programme), never a default. Quantities are read from the human-measured BOQ.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal

from ..approvals import engine as approvals
from ..core.errors import Conflict, ImmutableRecord, NotFound, ValidationFailed
from ..core.money import D_opt
from ..core.timeutil import now_iso
from ..database import Database, rows_to_dicts
from ..estimators import productivity as eng
from ..models.actor import Actor
from ..models.enums import Entity, Status
from . import audit, governed, projects

D = Decimal
NORM_STATES = ("Draft", "Proposed", "Imported - Unverified", "Pending Review", "Approved", "Rejected", "Superseded")
# Initial company planning bands from the business brief. Configurable planning assumptions - NOT industry-standard categories.
ARCHETYPE_BANDS = {"sme": (4, 15, "SME / small contractor"), "mid": (15, 25, "Mid-sized contractor"), "large": (26, 50, "Large contractor"),
                   "enterprise": (51, None, "Enterprise / major-project contractor")}
DIRECT_ROLE_HINTS = ("skilled", "semi_skilled", "labourer", "operator", "driver", "specialist_sub")
INDIRECT_ROLE_HINTS = ("foreman", "supervisor", "engineer", "technical", "qc", "inspector", "hse")


def _j(x) -> str:
    return json.dumps(x, sort_keys=True, ensure_ascii=False)


def _pos_dec(v, name: str, *, allow_zero=False, le: str | None = None) -> str:
    d = D_opt(v)
    if d is None or d < 0 or (d == 0 and not allow_zero):
        raise ValidationFailed(f"{name} must be a {'non-negative' if allow_zero else 'positive'} number.", code="NORM_FIELD")
    if le is not None and d > D(le):
        raise ValidationFailed(f"{name} must be <= {le}.", code="NORM_FIELD")
    return format(d.normalize(), "f")


def _crew(v) -> dict:
    if isinstance(v, str):
        v = json.loads(v)
    if not isinstance(v, dict) or not v:
        raise ValidationFailed("crew must be a non-empty {role: head-count} map.", code="NORM_FIELD")
    out = {}
    for r, n in v.items():
        if not str(r).strip() or not isinstance(n, int) or isinstance(n, bool) or n <= 0:
            raise ValidationFailed(f"crew head-count for '{r}' must be a positive integer.", code="NORM_FIELD")
        out[str(r)] = n
    return out


# ================================================================================================ productivity norms
def get_norm(db: Database, nid: str, version: int | None = None) -> dict:
    sql, par = "SELECT * FROM productivity_norms WHERE id=?", [nid]
    if version is not None:
        sql, par = sql + " AND version=?", par + [version]
    r = db.one(sql + " ORDER BY version DESC LIMIT 1", par)
    if not r:
        raise NotFound(f"Productivity norm {nid} not found.")
    return dict(r)


def create_norm(db: Database, actor: Actor, *, id: str, trade: str, activity: str, output_unit: str, basis: str, value, crew, cost_prefix: str | None = None,
                includes_productivity_factors: bool = False, applicability: dict | None = None, exclusions: str | None = None, source: str | None = None,
                evidence: str | None = None, confidence: str = "Low", evidence_status: str = "unverified", origin: str = "user", effective_from: str | None = None,
                review_by: str | None = None, is_synthetic: bool = False, notes: str | None = None) -> str:
    """A new norm is never approved on creation. origin 'import' lands as 'Imported - Unverified', 'system' as 'Proposed' (system principals only), otherwise 'Draft'."""
    approvals.require_author(actor)
    if basis not in ("labour_hours_per_unit", "crew_output_per_crew_day"):
        raise ValidationFailed("basis must be labour_hours_per_unit or crew_output_per_crew_day.", code="NORM_FIELD")
    if evidence_status not in ("unverified", "verified", "synthetic"):
        raise ValidationFailed("evidence_status must be unverified, verified or synthetic.", code="NORM_EVIDENCE")
    if origin not in ("user", "system", "import", "synthetic"):
        raise ValidationFailed("origin must be user, system, import or synthetic.", code="NORM_ORIGIN")
    if origin == "system" and not actor.username.startswith("system:"):
        raise ValidationFailed("origin 'system' is reserved for system principals.", code="NORM_ORIGIN")
    if evidence_status == "verified" or origin == "synthetic":
        if evidence_status == "verified" and is_synthetic:
            raise ValidationFailed("A synthetic norm can never carry evidence_status 'verified'.", code="NORM_EVIDENCE")
    if db.one("SELECT 1 FROM productivity_norms WHERE id=?", (id,)):
        raise Conflict(f"Norm {id} already exists; use revise_norm.")
    if is_synthetic:
        evidence_status, origin = "synthetic", "synthetic"
    status = {"import": "Imported - Unverified", "system": "Proposed"}.get(origin, "Draft")
    db.insert("productivity_norms", dict(
        id=id, version=1, trade=trade, activity=activity, cost_prefix=cost_prefix, output_unit=output_unit, basis=basis, value=_pos_dec(value, "value"),
        includes_productivity_factors=int(includes_productivity_factors), crew_json=_j(_crew(crew)), applicability_json=_j(applicability or {}), exclusions=exclusions,
        source=source, evidence=evidence, confidence=confidence, evidence_status=evidence_status, origin=origin, status=status, effective_from=effective_from,
        review_by=review_by, is_synthetic=int(is_synthetic), notes=notes, created_by=actor.username, created_at=now_iso()))
    audit.log(db, actor, "productivity_norm", id, "create", after={"basis": basis, "value": str(value), "status": status})
    return id


def revise_norm(db: Database, actor: Actor, nid: str, **changes) -> int:
    approvals.require_author(actor)
    cur = get_norm(db, nid)
    allowed = {"value", "crew", "source", "evidence", "confidence", "evidence_status", "applicability", "exclusions", "effective_from", "review_by", "notes",
               "includes_productivity_factors", "basis", "output_unit", "trade", "activity", "cost_prefix"}
    if set(changes) - allowed:
        raise ValidationFailed(f"Not editable: {sorted(set(changes) - allowed)}")
    if "evidence_status" in changes and changes["evidence_status"] == "verified" and cur["is_synthetic"]:
        raise ValidationFailed("A synthetic norm can never be 'verified'.", code="NORM_EVIDENCE")
    c = dict(changes)
    if "value" in c:
        c["value"] = _pos_dec(c["value"], "value")
    if "crew" in c:
        c["crew_json"] = _j(_crew(c.pop("crew")))
    if "applicability" in c:
        c["applicability_json"] = _j(c.pop("applicability"))
    if "includes_productivity_factors" in c:
        c["includes_productivity_factors"] = int(c["includes_productivity_factors"])
    if cur["status"] in ("Draft", "Proposed", "Imported - Unverified", "Pending Review", "Rejected"):
        db.update("productivity_norms", {**c, "status": "Draft" if cur["status"] != "Imported - Unverified" else "Imported - Unverified"}, "pk=?", (cur["pk"],))
        audit.log(db, actor, "productivity_norm", nid, "edit_draft", after=changes)
        return cur["version"]
    new = {k: v for k, v in cur.items() if k != "pk"}
    new.update(c)
    new.update(version=cur["version"] + 1, status="Draft", created_by=actor.username, created_at=now_iso(), approved_by=None, approved_at=None, reviewed_by=None)
    db.insert("productivity_norms", new)
    audit.log(db, actor, "productivity_norm", nid, "revise", after=changes, comment=f"new version {new['version']}")
    return new["version"]


def propose_norm(db: Database, actor: Actor, nid: str) -> None:
    """A user states 'I propose this' (Draft -> Proposed) before formal submission."""
    approvals.require_author(actor)
    cur = get_norm(db, nid)
    if cur["status"] != "Draft":
        raise Conflict(f"Only a Draft can be proposed (is {cur['status']}).")
    db.update("productivity_norms", {"status": "Proposed"}, "pk=?", (cur["pk"],))
    audit.log(db, actor, "productivity_norm", nid, "propose")


def submit_norm(db: Database, actor: Actor, nid: str) -> None:
    approvals.require_author(actor)
    cur = get_norm(db, nid)
    if cur["status"] not in ("Draft", "Proposed", "Imported - Unverified", "Rejected"):
        raise Conflict(f"Cannot submit a norm in status {cur['status']}.")
    if not (cur["source"] or "").strip():
        raise ValidationFailed("A source is required before a norm can be submitted for review.", code="NORM_SOURCE_REQUIRED")
    db.update("productivity_norms", {"status": "Pending Review", "reviewed_by": None}, "pk=?", (cur["pk"],))
    audit.log(db, actor, "productivity_norm", nid, "submit")


def approve_norm(db: Database, actor: Actor, nid: str, *, comments: str | None = None, evidence_verified: bool = False) -> None:
    cur = get_norm(db, nid)
    approvals.authorize(actor, Entity.PRODUCTIVITY_NORM.value, "approve", created_by=cur["created_by"])
    if cur["status"] != "Pending Review":
        raise Conflict(f"Norm must be Pending Review (is {cur['status']}).", code="NOT_PENDING")
    if not (cur["source"] or "").strip() or not (cur["effective_from"] or "").strip():
        raise ValidationFailed("Approval needs a source and an effective date on the norm.", code="NORM_PROVENANCE")
    if evidence_verified and cur["is_synthetic"]:
        raise ValidationFailed("Synthetic evidence cannot be marked verified.", code="NORM_EVIDENCE")
    with db.tx():
        for old in db.all("SELECT pk FROM productivity_norms WHERE id=? AND status='Approved' AND version<?", (nid, cur["version"])):
            db.update("productivity_norms", {"status": "Superseded"}, "pk=?", (old["pk"],))
        upd = {"status": "Approved", "approved_by": actor.username, "approved_at": now_iso(), "reviewed_by": actor.username}
        if evidence_verified:
            upd["evidence_status"] = "verified"
        db.update("productivity_norms", upd, "pk=?", (cur["pk"],))
        approvals.record(db, actor, Entity.PRODUCTIVITY_NORM.value, nid, "approve", version=cur["version"], approved_value=cur["value"], evidence=cur["evidence"], comments=comments)


def reject_norm(db: Database, actor: Actor, nid: str, reason: str) -> None:
    cur = get_norm(db, nid)
    approvals.authorize(actor, Entity.PRODUCTIVITY_NORM.value, "reject")
    if cur["status"] in ("Approved", "Superseded"):
        raise ImmutableRecord("Approved norms cannot be rejected; revise to create a new version.")
    db.update("productivity_norms", {"status": "Rejected"}, "pk=?", (cur["pk"],))
    approvals.record(db, actor, Entity.PRODUCTIVITY_NORM.value, nid, "reject", version=cur["version"], comments=reason)


def list_norms(db: Database, status: str | None = None) -> list[dict]:
    sql = "SELECT * FROM productivity_norms n WHERE version=(SELECT MAX(version) FROM productivity_norms WHERE id=n.id)"
    par: list = []
    if status:
        sql += " AND status=?"
        par.append(status)
    return rows_to_dicts(db.all(sql + " ORDER BY id", par))


def _norm_in(row: dict) -> eng.Norm:
    return eng.Norm(row["id"], row["version"], row["basis"], D(row["value"]), json.loads(row["crew_json"]), bool(row["includes_productivity_factors"]), row["status"],
                    row["evidence_status"], bool(row["is_synthetic"]), row["output_unit"])


def norm_for_run(db: Database, nid: str, allow_provisional: bool) -> dict | None:
    r = db.one("SELECT * FROM productivity_norms WHERE id=? AND status='Approved' ORDER BY version DESC LIMIT 1", (nid,))
    if r:
        return dict(r)
    if allow_provisional:
        r = db.one("SELECT * FROM productivity_norms WHERE id=? AND status<>'Rejected' AND status<>'Superseded' ORDER BY version DESC LIMIT 1", (nid,))
        return dict(r) if r else None
    return None


# ================================================================================================ workforce profiles
def get_profile(db: Database, pid: str, version: int | None = None) -> dict:
    sql, par = "SELECT * FROM workforce_profiles WHERE id=?", [pid]
    if version is not None:
        sql, par = sql + " AND version=?", par + [version]
    r = db.one(sql + " ORDER BY version DESC LIMIT 1", par)
    if not r:
        raise NotFound(f"Workforce profile {pid} not found.")
    return dict(r)


def total_headcount(row: dict) -> int:
    return sum(int(v) for k, v in json.loads(row["roles_json"]).items() if not k.startswith("eq:")) + sum(int(v) for v in json.loads(row["indirect_json"]).values())


def create_profile(db: Database, actor: Actor, *, id: str, archetype: str, name: str, roles: dict, indirect: dict | None = None, shifts: int = 1,
                   night_shift_efficiency_pct=None, attendance_pct, availability_pct, productive_hours_per_shift, overtime_hours_per_day="0",
                   overtime_efficiency_pct="0", work_fronts: int | None = None, mobilisation_wd: int = 0, subcontract_capacity: dict | None = None,
                   role_day_cost: dict | None = None, min_workers: int | None = None, max_workers: int | None = None, source: str | None = None,
                   is_synthetic: bool = False, notes: str | None = None) -> str:
    approvals.require_author(actor)
    if archetype not in (*ARCHETYPE_BANDS, "custom"):
        raise ValidationFailed(f"archetype must be one of {[*ARCHETYPE_BANDS, 'custom']}", code="PROFILE_FIELD")
    if db.one("SELECT 1 FROM workforce_profiles WHERE id=?", (id,)):
        raise Conflict(f"Profile {id} already exists; use revise_profile.")
    lo, hi = (min_workers, max_workers) if min_workers is not None else (ARCHETYPE_BANDS[archetype][:2] if archetype != "custom" else (None, None))
    if shifts < 1 or shifts > 3:
        raise ValidationFailed("shifts must be 1..3.", code="PROFILE_FIELD")
    if shifts > 1 and night_shift_efficiency_pct in (None, ""):
        raise ValidationFailed("night_shift_efficiency_pct is required when shifts > 1 (a person-entered planning value).", code="PROFILE_FIELD")
    for k, v in roles.items():
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise ValidationFailed(f"roles['{k}'] must be a non-negative integer.", code="PROFILE_FIELD")
    row = dict(id=id, version=1, archetype=archetype, name=name, min_workers=lo, max_workers=hi, roles_json=_j(roles), indirect_json=_j(indirect or {}), shifts=shifts,
               night_shift_efficiency_pct=None if night_shift_efficiency_pct in (None, "") else _pos_dec(night_shift_efficiency_pct, "night_shift_efficiency_pct", allow_zero=True, le="100"),
               attendance_pct=_pos_dec(attendance_pct, "attendance_pct", le="100"), availability_pct=_pos_dec(availability_pct, "availability_pct", le="100"),
               productive_hours_per_shift=_pos_dec(productive_hours_per_shift, "productive_hours_per_shift", le="24"),
               overtime_hours_per_day=_pos_dec(overtime_hours_per_day, "overtime_hours_per_day", allow_zero=True, le="12"),
               overtime_efficiency_pct=_pos_dec(overtime_efficiency_pct, "overtime_efficiency_pct", allow_zero=True, le="100"), work_fronts=work_fronts,
               mobilisation_wd=int(mobilisation_wd), subcontract_capacity_json=_j(subcontract_capacity or {}),
               role_day_cost_json=_j(role_day_cost) if role_day_cost else None, source=source, is_synthetic=int(is_synthetic), status="Draft", notes=notes,
               created_by=actor.username, created_at=now_iso())
    if archetype != "custom" and lo is not None:
        n = total_headcount(row)
        if n < lo or (hi is not None and n > hi):
            raise ValidationFailed(f"Profile head-count {n} is outside the configured '{archetype}' planning band {lo}-{hi if hi else '+'}; adjust the band explicitly or use 'custom'.", code="ARCHETYPE_BAND")
    db.insert("workforce_profiles", row)
    audit.log(db, actor, "workforce_profile", id, "create", after={"archetype": archetype, "headcount": total_headcount(row)})
    return id


def submit_profile(db: Database, actor: Actor, pid: str) -> None:
    approvals.require_author(actor)
    cur = get_profile(db, pid)
    if cur["status"] not in ("Draft", "Rejected"):
        raise Conflict(f"Cannot submit a profile in status {cur['status']}.")
    db.update("workforce_profiles", {"status": "Pending Review"}, "pk=?", (cur["pk"],))
    audit.log(db, actor, "workforce_profile", pid, "submit")


def approve_profile(db: Database, actor: Actor, pid: str, *, comments: str | None = None) -> None:
    cur = get_profile(db, pid)
    approvals.authorize(actor, Entity.WORKFORCE_PROFILE.value, "approve", created_by=cur["created_by"])
    if cur["status"] != "Pending Review":
        raise Conflict(f"Profile must be Pending Review (is {cur['status']}).", code="NOT_PENDING")
    with db.tx():
        for old in db.all("SELECT pk FROM workforce_profiles WHERE id=? AND status='Approved' AND version<?", (pid, cur["version"])):
            db.update("workforce_profiles", {"status": "Superseded"}, "pk=?", (old["pk"],))
        db.update("workforce_profiles", {"status": "Approved", "approved_by": actor.username, "approved_at": now_iso()}, "pk=?", (cur["pk"],))
        approvals.record(db, actor, Entity.WORKFORCE_PROFILE.value, pid, "approve", version=cur["version"], approved_value=total_headcount(cur), comments=comments)


def revise_profile(db: Database, actor: Actor, pid: str, **changes) -> int:
    approvals.require_author(actor)
    cur = get_profile(db, pid)
    if cur["status"] in ("Approved", "Superseded"):
        new = {k: v for k, v in cur.items() if k != "pk"}
        for k, v in changes.items():
            new[k + "_json" if k in ("roles", "indirect", "subcontract_capacity") else k] = _j(v) if k in ("roles", "indirect", "subcontract_capacity") else v
        new.update(version=cur["version"] + 1, status="Draft", created_by=actor.username, created_at=now_iso(), approved_by=None, approved_at=None)
        db.insert("workforce_profiles", new)
        audit.log(db, actor, "workforce_profile", pid, "revise", after=changes)
        return new["version"]
    upd = {(k + "_json" if k in ("roles", "indirect", "subcontract_capacity") else k): (_j(v) if k in ("roles", "indirect", "subcontract_capacity") else v) for k, v in changes.items()}
    db.update("workforce_profiles", {**upd, "status": "Draft"}, "pk=?", (cur["pk"],))
    audit.log(db, actor, "workforce_profile", pid, "edit_draft", after=changes)
    return cur["version"]


def list_profiles(db: Database) -> list[dict]:
    return rows_to_dicts(db.all("SELECT * FROM workforce_profiles p WHERE version=(SELECT MAX(version) FROM workforce_profiles WHERE id=p.id) ORDER BY id"))


def _profile_in(row: dict) -> eng.Profile:
    pool = {**json.loads(row["roles_json"]), **{(k if k.startswith("sub:") else "sub:" + k): v for k, v in json.loads(row["subcontract_capacity_json"]).items()}}
    return eng.Profile(row["id"], row["name"], pool, json.loads(row["indirect_json"]), row["shifts"], D(row["night_shift_efficiency_pct"] or 0) / 100,
                       D(row["attendance_pct"]) / 100, D(row["availability_pct"]) / 100, D(row["productive_hours_per_shift"]), D(row["overtime_hours_per_day"] or 0),
                       D(row["overtime_efficiency_pct"] or 0) / 100, row["work_fronts"], row["mobilisation_wd"],
                       json.loads(row["role_day_cost_json"]) if row["role_day_cost_json"] else None, bool(row["is_synthetic"]), row["status"], row["archetype"])


# ================================================================================================ activities
def set_activities(db: Database, actor: Actor, project_id: str, activities: list[dict]) -> int:
    """Replace the project's work-activity list (a person's programme input). Quantity is NEVER typed here: it is read from the BOQ item at run time."""
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    codes = [a["code"] for a in activities]
    if len(codes) != len(set(codes)):
        raise ValidationFailed("Duplicate activity code.", code="ACTIVITY_DUPLICATE")
    known = set(codes)
    for a in activities:
        for p in _split_preds(a.get("predecessors")):
            if p[0] not in known:
                raise ValidationFailed(f"{a['code']}: unknown predecessor {p[0]}.", code="PROGRAMME_UNKNOWN_PRED")
        if a.get("boq_item_key") and not db.one("SELECT 1 FROM boq_items WHERE project_id=? AND item_key=?", (project_id, a["boq_item_key"])):
            raise ValidationFailed(f"{a['code']}: BOQ item {a['boq_item_key']} not found.", code="ACTIVITY_BOQ")
    with db.tx():
        db.execute("DELETE FROM work_activities WHERE project_id=?", (project_id,))
        for a in activities:
            db.insert("work_activities", dict(
                project_id=project_id, code=a["code"], name=a["name"], wbs_code=a.get("wbs_code"), cost_code=a.get("cost_code"), boq_item_key=a.get("boq_item_key"),
                norm_id=a.get("norm_id"), crews=int(a.get("crews", 1)), work_fronts=int(a.get("work_fronts", 1)), fixed_days_json=_j(a.get("fixed_days") or {}),
                predecessors=",".join(f"{c}{'+' + str(l) if l else ''}" for c, l in _split_preds(a.get("predecessors"))), long_lead_id=a.get("long_lead_id"),
                priority=int(a.get("priority", 0)), notes=a.get("notes"), created_by=actor.username, created_at=now_iso()))
    audit.log(db, actor, "work_activities", project_id, "set", after={"count": len(activities)}, project_id=project_id)
    return len(activities)


def _split_preds(v) -> list[tuple[str, int]]:
    if not v:
        return []
    items = v if isinstance(v, list) else str(v).split(",")
    out = []
    for it in items:
        it = str(it).strip()
        if not it:
            continue
        lag = 0
        if "+" in it:
            it, l = it.split("+", 1)
            lag = int(l)
        out.append((it.strip(), lag))
    return out


def list_activities(db: Database, project_id: str) -> list[dict]:
    return rows_to_dicts(db.all("SELECT * FROM work_activities WHERE project_id=? ORDER BY pk", (project_id,)))


def work_calendar(db: Database, project_id: str, *, allow_unconfirmed: bool = False) -> tuple[eng.WorkCalendar, bool]:
    rows = governed.effective(db, project_id, "calendar", include_unapproved=allow_unconfirmed)
    if not rows:
        raise ValidationFailed("The project has no approved work calendar (Saudi calendars are not assumed; confirm one for the project).", code="CALENDAR_REQUIRED")
    pick = next((r for r in rows if r["code"] == "PROJECT"), rows[0])
    confirmed = pick.get("status") == "Approved" and not pick["data"].get("requires_confirmation")
    return eng.calendar_from_data(pick["data"], confirmed=confirmed), confirmed


def _ready_wd(db: Database, ll_id: str | None, cal: eng.WorkCalendar, gaps: list[dict], code: str) -> int:
    if not ll_id:
        return 0
    r = db.one("SELECT * FROM long_lead_items WHERE id=?", (ll_id,))
    if not r:
        gaps.append(dict(code=code, kind="LONG_LEAD_UNKNOWN", detail=f"long-lead item {ll_id} not found"))
        return 0
    od = r["actual_order_date"] or r["planned_order_date"]
    if not od:
        gaps.append(dict(code=code, kind="LONG_LEAD_NO_ORDER_DATE", detail=f"long-lead {ll_id} has no planned/actual order date: material-ready day unknown"))
        return 0
    wk = D_opt(r["lead_time_weeks"]) or D(0)
    ready = date.fromisoformat(od) + timedelta(days=int(wk * 7))
    if r["required_on_site"] and ready > date.fromisoformat(r["required_on_site"]):
        gaps.append(dict(code=code, kind="LONG_LEAD_LATE", detail=f"long-lead {ll_id}: ready {ready.isoformat()} is after required-on-site {r['required_on_site']}"))
    if ready <= cal.start:
        return 0
    n = 0
    d = cal.start
    while d < ready:
        if cal.is_working(d):
            n += 1
        d += timedelta(days=1)
    return n


def _acts_in(db: Database, project_id: str, cal: eng.WorkCalendar, allow_provisional: bool, factors: dict | None) -> tuple[list[eng.ActivityIn], list[dict]]:
    rows = list_activities(db, project_id)
    if not rows:
        raise ValidationFailed("No work activities have been defined for the project.", code="NO_ACTIVITIES")
    gaps: list[dict] = []
    out = []
    for r in rows:
        norm = None
        if r["norm_id"]:
            nr = norm_for_run(db, r["norm_id"], allow_provisional)
            norm = _norm_in(nr) if nr else None
        qty, unit = None, ""
        if r["boq_item_key"]:
            b = db.one("SELECT quantity, unit FROM boq_items WHERE project_id=? AND item_key=?", (project_id, r["boq_item_key"]))
            qty, unit = D_opt(b["quantity"]) if b else None, (b["unit"] if b else "")
            if norm and qty is not None and unit and norm.unit and unit != norm.unit:
                gaps.append(dict(code=r["code"], kind="UNIT_MISMATCH", detail=f"BOQ unit '{unit}' differs from the norm's unit '{norm.unit}': activity excluded"))
                norm = None
        fx = tuple(eng.Factor(f["name"], D(str(f["value"])), f.get("source", ""), bool(f.get("approved"))) for f in (factors or {}).get(r["code"], []))
        fd = json.loads(r["fixed_days_json"])
        out.append(eng.ActivityIn(r["code"], r["name"], qty, unit, norm, r["crews"], r["work_fronts"], fx, int(fd.get("mobilisation", 0)) + int(fd.get("setup", 0)),
                                  int(fd.get("curing", 0)) + int(fd.get("testing", 0)) + int(fd.get("inspection", 0)), tuple(_split_preds(r["predecessors"])),
                                  _ready_wd(db, r["long_lead_id"], cal, gaps, r["code"]), r["priority"], bool(fd.get("fixed_only"))))
    return out, gaps


def _serialise(res: dict) -> dict:
    r = dict(res)
    r["activities"] = [vars(a) if not isinstance(a, dict) else a for a in res["activities"]]
    return json.loads(json.dumps(r, default=str))


def build_programme(db: Database, project_id: str, profile_id: str, *, profile_version: int | None = None, allow_provisional: bool = False,
                    allow_unconfirmed_calendar: bool = False, factors: dict | None = None, progress: dict | None = None, status_wd: int = 0) -> dict:
    """Read-only calculation: the resource-constrained programme of the project's activities for one workforce profile."""
    cal, confirmed = work_calendar(db, project_id, allow_unconfirmed=allow_unconfirmed_calendar)
    prow = get_profile(db, profile_id, profile_version)
    prof = _profile_in(prow)
    if prow["status"] != "Approved" and not allow_provisional:
        raise ValidationFailed(f"Workforce profile {profile_id} is '{prow['status']}': approve it or run an explicit provisional scenario.", code="PROFILE_NOT_APPROVED")
    acts, gaps = _acts_in(db, project_id, cal, allow_provisional, factors)
    res = eng.run(acts, prof, cal, allow_provisional=allow_provisional, progress=progress, status_wd=status_wd)
    res["gaps"] = gaps + res["gaps"]
    if not confirmed:
        res["gaps"].append(dict(code="*", kind="CALENDAR_UNCONFIRMED", detail="the project calendar is not an approved, confirmed calendar"))
        res["complete"] = False
        res["provisional"] = True
    for r in res["activities"]:                              # BOQ quantity provenance
        pass
    res["project_id"] = project_id
    res["profile_version"] = prow["version"]
    ser = _serialise(res)
    ser["fingerprint"] = hashlib.sha256(json.dumps({k: ser[k] for k in ("profile", "calendar", "activities", "working_days")}, sort_keys=True).encode()).hexdigest()
    ser["claims"] = claim_status(ser)
    return ser


def claim_status(res: dict) -> str:
    if not res.get("schedulable", True):
        return "NOT SCHEDULABLE - NOT FOR RELIANCE: the profile cannot field a crew for " + ", ".join(res["unfinished"]) + "; durations shown stop at the blocked work"
    if res["complete"] and not res["provisional"] and not res["synthetic"]:
        return "BASED ON APPROVED NORMS, PROFILE AND CALENDAR"
    why = []
    if not res["complete"]:
        why.append(f"{len(res['gaps'])} gap(s)")
    if res["provisional"]:
        why.append("provisional (unapproved norm/profile/calendar)")
    if res["synthetic"]:
        why.append("synthetic test inputs")
    return "PROVISIONAL - NOT FOR RELIANCE: " + "; ".join(why)


def crew_scenarios(db: Database, project_id: str, profile_ids: list[str], *, allow_provisional: bool = False, allow_unconfirmed_calendar: bool = False) -> dict:
    """The same project scheduled for several workforce profiles; reports duration, staffing, labour-hours, critical path, cost and binding constraints."""
    rows = []
    for pid in profile_ids:
        r = build_programme(db, project_id, pid, allow_provisional=allow_provisional, allow_unconfirmed_calendar=allow_unconfirmed_calendar)
        pool = r["profile"]["pool"]
        own = sum(int(v) for k, v in pool.items() if not k.startswith(("eq:", "sub:")))             # own direct labour; equipment and subcontract capacity are not head-count
        rows.append(dict(profile=pid, archetype=r["profile"]["archetype"], headcount=own + r["indirect_headcount"], subcontract_capacity=sum(int(v) for k, v in pool.items() if k.startswith("sub:")),
                         productive_hours=r["profile"]["productive_hours"], shifts=r["profile"]["shifts"], labour_hours=r["labour_hours"],
                         unconstrained_wd=r["unconstrained_project_wd"], dependency_wd=r["dependency_constrained_wd"], procurement_wd=r["procurement_constrained_wd"],
                         working_days=r["working_days"], calendar_days=r["calendar_days"], start=r["start_date"], finish=r["finish_date"], peak_workers=r["peak_workers"],
                         indirect_headcount=r["indirect_headcount"], critical_path=r["critical_path"], resource_limited=r["resource_limited"], cost=r["cost"],
                         complete=r["complete"], schedulable=r["schedulable"], unfinished=r["unfinished"], claim=r["claims"], gaps=len(r["gaps"])))
    return dict(project_id=project_id, scenarios=rows, calendar=build_programme(db, project_id, profile_ids[0], allow_provisional=allow_provisional,
                                                                                allow_unconfirmed_calendar=allow_unconfirmed_calendar)["calendar"],
                note="Scenario results compare workforce profiles on the same activities, calendar and norms. They are not an industry benchmark; a doubled workforce does not halve the programme because of "
                     "dependencies, finite work fronts, shared equipment and rounding of crews.")


# ================================================================================================ baselines
def save_baseline(db: Database, actor: Actor, project_id: str, profile_id: str, *, allow_provisional: bool = False, allow_unconfirmed_calendar: bool = False) -> int:
    approvals.require_author(actor)
    res = build_programme(db, project_id, profile_id, allow_provisional=allow_provisional, allow_unconfirmed_calendar=allow_unconfirmed_calendar)
    vno = (db.scalar("SELECT MAX(version_no) FROM programme_baselines WHERE project_id=?", (project_id,)) or 0) + 1
    pk = db.insert("programme_baselines", dict(project_id=project_id, version_no=vno, profile_id=profile_id, profile_version=res["profile_version"], start_date=res["start_date"],
                                               result_json=json.dumps(res, default=str), fingerprint=res["fingerprint"], provisional=int(res["provisional"] or not res["complete"]),
                                               status="Pending Review", created_by=actor.username, created_at=now_iso()))
    audit.log(db, actor, "programme_baseline", f"{project_id}/v{vno}", "save", after={"working_days": res["working_days"]}, project_id=project_id)
    return vno


def approve_baseline(db: Database, actor: Actor, project_id: str, version_no: int, *, comments: str | None = None) -> None:
    row = db.one("SELECT * FROM programme_baselines WHERE project_id=? AND version_no=?", (project_id, version_no))
    if not row:
        raise NotFound("Programme baseline not found.")
    approvals.authorize(actor, Entity.PROGRAMME_BASELINE.value, "approve", created_by=row["created_by"])
    if row["status"] != "Pending Review":
        raise Conflict(f"Baseline must be Pending Review (is {row['status']}).", code="NOT_PENDING")
    if row["provisional"]:
        raise ValidationFailed("A baseline built on provisional/unapproved norms, an unconfirmed calendar or with gaps cannot be approved; resolve the gaps and rebuild.", code="BASELINE_PROVISIONAL")
    with db.tx():
        for old in db.all("SELECT pk FROM programme_baselines WHERE project_id=? AND status='Approved'", (project_id,)):
            db.update("programme_baselines", {"status": "Superseded"}, "pk=?", (old["pk"],))
        db.update("programme_baselines", {"status": "Approved", "approved_by": actor.username, "approved_at": now_iso()}, "pk=?", (row["pk"],))
        approvals.record(db, actor, Entity.PROGRAMME_BASELINE.value, f"{project_id}/v{version_no}", "approve", project_id=project_id, version=version_no,
                         approved_value=row["fingerprint"], comments=comments)


def latest_baseline(db: Database, project_id: str, approved_only: bool = False) -> dict | None:
    sql = "SELECT * FROM programme_baselines WHERE project_id=?" + (" AND status='Approved'" if approved_only else "") + " ORDER BY version_no DESC LIMIT 1"
    r = db.one(sql, (project_id,))
    if not r:
        return None
    d = dict(r)
    d["result"] = json.loads(d.pop("result_json"))
    return d


def forecast_vs_baseline(db: Database, project_id: str, progress: dict, status_wd: int, *, allow_provisional: bool = False, allow_unconfirmed_calendar: bool = False) -> dict:
    """Re-forecast from progress (% complete by activity at working-day `status_wd`) and compare with the approved (or latest) baseline."""
    base = latest_baseline(db, project_id, approved_only=True) or latest_baseline(db, project_id)
    if not base:
        raise ValidationFailed("No baseline to compare with.", code="NO_BASELINE")
    fc = build_programme(db, project_id, base["profile_id"], profile_version=base["profile_version"], allow_provisional=allow_provisional,
                         allow_unconfirmed_calendar=allow_unconfirmed_calendar, progress=progress, status_wd=status_wd)
    return dict(baseline_version=base["version_no"], baseline_status=base["status"], baseline_wd=base["result"]["working_days"], forecast_wd=fc["working_days"],
                variance_wd=fc["working_days"] - base["result"]["working_days"], forecast_finish=fc["finish_date"], baseline_finish=base["result"]["finish_date"],
                forecast=fc)


def baseline_to_schedule_tasks(db: Database, actor: Actor, project_id: str, version_no: int) -> int:
    """Bridge into the existing CPM schedule model (Draft tasks): each activity keeps its resource-constrained start (SNET) and span."""
    from . import indirects
    b = db.one("SELECT * FROM programme_baselines WHERE project_id=? AND version_no=?", (project_id, version_no))
    if not b:
        raise NotFound("Baseline not found.")
    res = json.loads(b["result_json"])
    acts = {a["code"]: a for a in list_activities(db, project_id)}
    tasks = []
    for a in res["activities"]:
        if a["resource_start"] is None:
            continue
        span = max(a["resource_finish"] - a["resource_start"], 0)
        row = acts[a["code"]]
        tasks.append(dict(task_code=a["code"], name=a["name"], duration_days=str(span), predecessors=row["predecessors"] or "", cost_code=row["cost_code"], wbs_code=row["wbs_code"],
                          snet=str(a["resource_start"])))
    indirects.set_tasks(db, actor, project_id, tasks)
    return len(tasks)
