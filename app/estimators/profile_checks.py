"""Evaluation of client-profile requirements against measured project facts. Pure. A requirement with a `check` is evaluated automatically; one without
needs a recorded human attestation. Unknown facts are 'Not assessable' - never silently 'Met'."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from ..core.errors import ValidationFailed

OPS = ("eq", "ne", "gt", "gte", "lt", "lte", "true", "false", "in")

FACT_HELP = {
    "estimate_state": "Complete / Provisional / Preliminary state of the estimate",
    "blockers": "number of blocking items on the estimate",
    "items_total": "number of BOQ items", "items_unpriced_pct": "percentage of BOQ items unpriced or incomplete",
    "synthetic_used": "true if any synthetic (demonstration) rate is used", "provisional_used": "true if a provisional rate is used",
    "contingency_pct": "contingency percentage in the commercial policy", "has_approved_duration": "true if a project duration is approved",
    "schedule_tasks": "number of programme tasks", "wbs_assigned_pct": "percentage of BOQ items assigned to a WBS node",
    "crosswalk_systems": "list of client coding systems with a cross-walk", "risks_quantified": "number of risks with quantified exposure",
    "classification_present": "true if an estimate classification has been determined", "boe_generated": "true if a Basis of Estimate has been generated",
    "reconciliation_clean": "true if the latest reconciliation has no unresolved Critical/High finding", "tax_approved": "true if all tax categories used are approved",
    "open_clarifications": "number of open clarifications", "scope_register_approved": "number of approved scope-register entries",
    "mto_stale": "number of MTO applications with changed factors/driver", "cost_codes_unassigned_pct": "percentage of direct cost without a cost code",
}


def validate_check(check: dict | None) -> dict | None:
    if not check:
        return None
    if set(check) - {"fact", "op", "value"}:
        raise ValidationFailed("check may only contain fact, op, value.", code="PROFILE_CHECK")
    if check.get("fact") not in FACT_HELP:
        raise ValidationFailed(f"Unknown fact '{check.get('fact')}'. Known: {sorted(FACT_HELP)}", code="PROFILE_CHECK")
    if check.get("op") not in OPS:
        raise ValidationFailed(f"op must be one of {OPS}", code="PROFILE_CHECK")
    if check["op"] not in ("true", "false") and check.get("value") in (None, ""):
        raise ValidationFailed("This operator needs a value (taken from the owner's document).", code="PROFILE_CHECK")
    return {"fact": check["fact"], "op": check["op"], "value": check.get("value")}


def _num(x):
    try:
        return Decimal(str(x))
    except (InvalidOperation, ValueError):
        return None


def evaluate(check: dict, facts: dict) -> tuple[str, str]:
    """(status, detail): 'Met' | 'Not met' | 'Not assessable'."""
    f, op, val = check["fact"], check["op"], check.get("value")
    if f not in facts or facts[f] is None:
        return "Not assessable", f"fact '{f}' is not available"
    actual = facts[f]
    if op == "true":
        return ("Met" if actual is True else "Not met"), f"{f} = {actual}"
    if op == "false":
        return ("Met" if actual is False else "Not met"), f"{f} = {actual}"
    if op == "in":
        pool = actual if isinstance(actual, (list, tuple, set)) else [actual]
        return ("Met" if str(val) in {str(x) for x in pool} else "Not met"), f"{f} = {actual}; required to contain {val}"
    if op in ("eq", "ne"):
        eq = str(actual) == str(val)
        return ("Met" if eq == (op == "eq") else "Not met"), f"{f} = {actual}; required {op} {val}"
    a, b = _num(actual), _num(val)
    if a is None or b is None:
        return "Not assessable", f"{f}={actual!r} or {val!r} is not numeric"
    ok = {"gt": a > b, "gte": a >= b, "lt": a < b, "lte": a <= b}[op]
    return ("Met" if ok else "Not met"), f"{f} = {actual}; required {op} {val}"
