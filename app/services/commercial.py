"""Commercial policies, tax categories, FX rates: versioned and approval-gated."""
from __future__ import annotations

import json

from ..approvals import engine as approvals
from ..core.errors import Conflict, ImmutableRecord, NotFound, ValidationFailed
from ..core.money import D, D_opt, to_text
from ..core.timeutil import now_iso, parse_date
from ..database import Database, jload, rows_to_dicts
from ..estimators import commercial as com
from ..models.actor import Actor
from ..models.enums import Entity, Status
from . import audit, projects


def create_policy(db: Database, actor: Actor, *, code: str, name: str, config: dict, project_id: str | None = None,
                  is_synthetic: bool = False, notes: str | None = None) -> int:
    approvals.require_author(actor)
    probs = com.validate_policy(config)
    if probs:
        raise ValidationFailed("Policy invalid: " + " ".join(probs), code="POLICY_INVALID", details=probs)
    v = (db.scalar("SELECT MAX(version) FROM commercial_policies WHERE code=?", (code,)) or 0) + 1
    pid = db.insert("commercial_policies", dict(code=code, version=v, name=name, config_json=config, status=Status.DRAFT.value,
                                                project_id=project_id, is_synthetic=int(is_synthetic), notes=notes,
                                                created_by=actor.username, created_at=now_iso()))
    audit.log(db, actor, "commercial_policy", f"{code}@{v}", "create", after=config, project_id=project_id)
    return pid


def get_policy(db: Database, policy_id: int) -> dict:
    r = db.one("SELECT * FROM commercial_policies WHERE id=?", (policy_id,))
    if not r:
        raise NotFound("Commercial policy not found.")
    d = dict(r)
    d["config"] = jload(d["config_json"], {})
    return d


def edit_policy(db: Database, actor: Actor, policy_id: int, config: dict) -> int:
    """Draft policies are edited in place; approved policies are immutable (a new version is created)."""
    approvals.require_author(actor)
    p = get_policy(db, policy_id)
    probs = com.validate_policy(config)
    if probs:
        raise ValidationFailed("Policy invalid: " + " ".join(probs), code="POLICY_INVALID", details=probs)
    if p["status"] in (Status.DRAFT.value, Status.PENDING.value, Status.REJECTED.value):
        db.update("commercial_policies", {"config_json": config, "status": Status.DRAFT.value}, "id=?", (policy_id,))
        audit.log(db, actor, "commercial_policy", f"{p['code']}@{p['version']}", "edit_draft", before=p["config"], after=config)
        return policy_id
    return create_policy(db, actor, code=p["code"], name=p["name"], config=config, project_id=p["project_id"],
                         is_synthetic=bool(p["is_synthetic"]), notes=f"Revision of v{p['version']}")


def submit_policy(db: Database, actor: Actor, policy_id: int) -> None:
    approvals.require_author(actor)
    n = db.update("commercial_policies", {"status": Status.PENDING.value}, "id=? AND status='Draft'", (policy_id,))
    if not n:
        raise Conflict("Only Draft policies can be submitted.")


def approve_policy(db: Database, actor: Actor, policy_id: int, *, comments: str | None = None) -> None:
    p = get_policy(db, policy_id)
    approvals.authorize(actor, Entity.COMMERCIAL_POLICY.value, "approve", created_by=p["created_by"])
    if p["status"] != Status.PENDING.value:
        raise Conflict(f"Policy is {p['status']}; must be Pending Review.", code="NOT_PENDING")
    with db.tx():
        for old in db.all("SELECT id FROM commercial_policies WHERE code=? AND status='Approved'", (p["code"],)):
            db.update("commercial_policies", {"status": Status.SUPERSEDED.value}, "id=?", (old["id"],))
        db.update("commercial_policies", {"status": Status.APPROVED.value, "approved_by": actor.username, "approved_at": now_iso()},
                  "id=?", (policy_id,))
        approvals.record(db, actor, Entity.COMMERCIAL_POLICY.value, f"{p['code']}@{p['version']}", "approve", version=p["version"],
                         approved_value=p["config"], comments=comments)


def assign_policy(db: Database, actor: Actor, project_id: str, policy_id: int) -> None:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    get_policy(db, policy_id)
    projects.update_project(db, actor, project_id, commercial_policy_id=policy_id)


# ---------------------------------------------------------------------------- tax
def propose_tax_category(db: Database, actor: Actor, *, code: str, name: str, rate_pct, valid_from: str,
                         valid_to: str | None = None, source_ref: str | None = None, verification_note: str | None = None,
                         recoverable: bool = True, is_synthetic: bool = False) -> int:
    approvals.require_author(actor)
    if D_opt(rate_pct) is None or not (0 <= D(rate_pct) <= 100):
        raise ValidationFailed("rate_pct must be between 0 and 100.")
    if not parse_date(valid_from):
        raise ValidationFailed("valid_from must be a date.")
    tid = db.insert("tax_categories", dict(code=code, name=name, rate_pct=to_text(D(rate_pct)), valid_from=valid_from,
                                           valid_to=valid_to, recoverable=int(recoverable), source_ref=source_ref,
                                           verification_note=verification_note, status=Status.PENDING.value,
                                           is_synthetic=int(is_synthetic), created_by=actor.username))
    audit.log(db, actor, "tax_category", f"{code}@{valid_from}", "propose", after={"rate": rate_pct})
    return tid


def approve_tax_category(db: Database, actor: Actor, tax_id: int, *, evidence: str, comments: str | None = None) -> None:
    r = db.one("SELECT * FROM tax_categories WHERE id=?", (tax_id,))
    if not r:
        raise NotFound("Tax category not found.")
    approvals.authorize(actor, Entity.TAX_CATEGORY.value, "approve", created_by=r["created_by"])
    if not evidence or not evidence.strip():
        raise ValidationFailed("Evidence (e.g. official guidance reference and date) is required to approve a tax rate.",
                               code="EVIDENCE_REQUIRED")
    if r["status"] not in (Status.PENDING.value, Status.DRAFT.value):
        raise Conflict(f"Tax category is {r['status']}.")
    with db.tx():
        db.update("tax_categories", {"status": Status.APPROVED.value, "approved_by": actor.username, "approved_at": now_iso(),
                                     "verification_note": (r["verification_note"] or "") + f" | Verified: {evidence}"},
                  "id=?", (tax_id,))
        approvals.record(db, actor, Entity.TAX_CATEGORY.value, f"{r['code']}@{r['valid_from']}", "approve",
                         approved_value={"rate_pct": r["rate_pct"]}, evidence=evidence, comments=comments)


def list_tax_categories(db: Database) -> list[dict]:
    return rows_to_dicts(db.all("SELECT * FROM tax_categories ORDER BY code, valid_from DESC"))


# ---------------------------------------------------------------------------- fx
def propose_fx(db: Database, actor: Actor, from_ccy: str, to_ccy: str, rate, rate_date: str, source: str,
               valid_until: str | None = None, is_synthetic: bool = False) -> int:
    approvals.require_author(actor)
    if D_opt(rate) is None or D(rate) <= 0:
        raise ValidationFailed("FX rate must be > 0.")
    if not source:
        raise ValidationFailed("FX source is required.")
    fid = db.insert("fx_rates", dict(from_ccy=from_ccy.upper(), to_ccy=to_ccy.upper(), rate=to_text(D(rate)),
                                     rate_date=rate_date, valid_until=valid_until, source=source,
                                     status=Status.PENDING.value, is_synthetic=int(is_synthetic), created_by=actor.username))
    audit.log(db, actor, "fx_rate", fid, "propose", after={"pair": f"{from_ccy}/{to_ccy}", "rate": rate})
    return fid


def approve_fx(db: Database, actor: Actor, fx_id: int, *, comments: str | None = None) -> None:
    r = db.one("SELECT * FROM fx_rates WHERE id=?", (fx_id,))
    if not r:
        raise NotFound("FX rate not found.")
    approvals.authorize(actor, Entity.FX_RATE.value, "approve", created_by=r["created_by"])
    db.update("fx_rates", {"status": Status.APPROVED.value, "approved_by": actor.username, "approved_at": now_iso()}, "id=?", (fx_id,))
    approvals.record(db, actor, Entity.FX_RATE.value, fx_id, "approve", approved_value={"rate": r["rate"]}, comments=comments)
