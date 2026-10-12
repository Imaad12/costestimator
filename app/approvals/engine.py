"""Server-side authorisation and recording of human approval decisions."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from ..config import get_settings
from ..core.errors import ApprovalBlocked, PermissionDenied
from ..core.money import D_opt
from ..core.timeutil import now_iso
from ..database import Database
from ..models.actor import Actor
from ..models.enums import Entity, Role
from ..services import audit
from .policy import ADMIN_ONLY, WRITE_ROLES, allowed_roles


def require_author(actor: Actor) -> None:
    """Creating / editing draft data requires a human with a write role."""
    if actor.is_ai or actor.role == Role.AI.value:
        raise PermissionDenied("AI principals may only create review-pending suggestions, not edit estimating data.",
                               code="AI_FORBIDDEN")
    if actor.role not in WRITE_ROLES:
        raise PermissionDenied(f"Role '{actor.role}' is read-only.")


def require_admin(actor: Actor, what: str = "this action") -> None:
    if actor.is_ai or actor.role != Role.ADMIN.value:
        raise PermissionDenied(f"Administrator role required for {what}.")


def authorize(actor: Actor, entity_type: str, action: str, *, created_by: str | None = None,
              value_sar: Decimal | str | None = None) -> None:
    """Raise unless `actor` may take `action` on `entity_type` (server-side; never trust the UI)."""
    if actor.is_ai or actor.role == Role.AI.value:
        raise PermissionDenied("AI cannot approve, reject or otherwise decide. A human reviewer must do this.",
                               code="AI_CANNOT_APPROVE")
    roles = allowed_roles(entity_type, action)
    if actor.role not in roles:
        raise PermissionDenied(
            f"Role '{actor.role}' may not '{action}' {entity_type}. Allowed: {', '.join(sorted(roles)) or 'none'}.")
    settings = get_settings()
    if (not settings.allow_self_approval and created_by and created_by == actor.username
            and action in ("approve", "approve_provisional") and actor.role != Role.ADMIN.value):
        raise ApprovalBlocked("Self-approval is disabled (KSA_ALLOW_SELF_APPROVAL=false). Another reviewer must approve.",
                              code="SELF_APPROVAL_BLOCKED")
    if entity_type == Entity.SUPPLIER_SELECTION.value and value_sar is not None:
        threshold = D_opt(settings.approval_thresholds.get("supplier_selection_commercial_approver_sar"))
        v = D_opt(value_sar)
        if threshold is not None and v is not None and v >= threshold and actor.role not in (
                Role.COMMERCIAL.value, Role.ADMIN.value):
            raise PermissionDenied(
                f"Selections valued at or above SAR {threshold:,} require a Commercial Approver "
                f"(configured threshold).", code="THRESHOLD_ROLE_REQUIRED")


def record(db: Database, actor: Actor, entity_type: str, entity_id: Any, action: str, *, project_id: str | None = None,
           version: Any = None, previous_value: Any = None, approved_value: Any = None, evidence: str | None = None,
           comments: str | None = None, override_reason: str | None = None) -> int:
    """Persist an approval record (+ audit entry). Caller must already have called `authorize`."""
    import json

    def s(v):
        return v if v is None or isinstance(v, str) else json.dumps(v, default=str, ensure_ascii=False)

    aid = db.insert("approvals", dict(
        project_id=project_id, entity_type=entity_type, entity_id=str(entity_id),
        version=None if version is None else str(version), reviewer=actor.username, reviewer_role=actor.role,
        action=action, ts=now_iso(), previous_value=s(previous_value), approved_value=s(approved_value),
        evidence=evidence, comments=comments, override_reason=override_reason))
    audit.log(db, actor, entity_type, entity_id, f"approval:{action}", before=previous_value, after=approved_value,
              comment=comments or override_reason, project_id=project_id)
    return aid


def decide(db: Database, actor: Actor, entity_type: str, entity_id: Any, action: str, **kw) -> int:
    created_by = kw.pop("created_by", None)
    value_sar = kw.pop("value_sar", None)
    authorize(actor, entity_type, action, created_by=created_by, value_sar=value_sar)
    return record(db, actor, entity_type, entity_id, action, **kw)


def approval_history(db: Database, entity_type: str, entity_id: Any) -> list[dict]:
    return [dict(r) for r in db.all(
        "SELECT * FROM approvals WHERE entity_type=? AND entity_id=? ORDER BY id", (entity_type, str(entity_id)))]
