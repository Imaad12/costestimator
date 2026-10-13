"""Kinds of governed parameters: user-supplied numeric inputs that must be validated, versioned and human-approved before use.

Pure module (no DB). A validator receives the raw dict and returns a normalised dict of JSON-safe values (Decimals as exact text) or raises
ValidationFailed. NO kind has default values - the library ships empty; every number comes from a person and an approval.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Callable

from ..core.errors import ValidationFailed
from ..models.enums import Role

E, P, C, A = Role.ESTIMATOR.value, Role.PROCUREMENT.value, Role.COMMERCIAL.value, Role.ADMIN.value


def dec(data: dict, key: str, *, required: bool = True, gt: str | None = None, ge: str | None = None, le: str | None = None) -> str | None:
    """Exact-decimal field as normalised text; None when optional and absent."""
    v = data.get(key)
    if v in (None, ""):
        if required:
            raise ValidationFailed(f"'{key}' is required.", code="PARAM_FIELD")
        return None
    try:
        d = Decimal(str(v).strip())
    except InvalidOperation:
        raise ValidationFailed(f"'{key}' must be a number (got {v!r}).", code="PARAM_FIELD")
    if not d.is_finite():
        raise ValidationFailed(f"'{key}' must be finite.", code="PARAM_FIELD")
    if gt is not None and not d > Decimal(gt):
        raise ValidationFailed(f"'{key}' must be > {gt}.", code="PARAM_FIELD")
    if ge is not None and not d >= Decimal(ge):
        raise ValidationFailed(f"'{key}' must be >= {ge}.", code="PARAM_FIELD")
    if le is not None and not d <= Decimal(le):
        raise ValidationFailed(f"'{key}' must be <= {le}.", code="PARAM_FIELD")
    return format(d.normalize(), "f") if d != 0 else "0"


def text(data: dict, key: str, *, required: bool = True, choices: tuple | None = None) -> str | None:
    v = data.get(key)
    if v in (None, ""):
        if required:
            raise ValidationFailed(f"'{key}' is required.", code="PARAM_FIELD")
        return None
    v = str(v).strip()
    if choices and v not in choices:
        raise ValidationFailed(f"'{key}' must be one of {list(choices)} (got {v!r}).", code="PARAM_FIELD")
    return v


def _no_extra(data: dict, allowed: set[str], kind: str) -> None:
    extra = set(data) - allowed
    if extra:
        raise ValidationFailed(f"Unknown field(s) for {kind}: {sorted(extra)}. Allowed: {sorted(allowed)}.", code="PARAM_FIELD")


@dataclass(frozen=True)
class ParamKind:
    name: str
    label: str
    validate: Callable[[dict], dict]
    approvers: frozenset[str]
    description: str = ""


KINDS: dict[str, ParamKind] = {}


def kind(name: str, label: str, approvers: set[str], description: str = ""):
    def deco(fn):
        KINDS[name] = ParamKind(name, label, fn, frozenset(approvers), description)
        return fn
    return deco


PRODUCTIVITY_CATEGORIES = ("height", "congestion", "climate_heat", "shift_pattern", "remote_site", "learning_curve", "access_restriction",
                           "permit_to_work", "weather", "other")


@kind("productivity_factor", "Productivity adjustment factor", {E, C, A},
      "Multiplier on labour hours for conditions such as work at height, congestion, heat, shift pattern, remote site or learning curve. "
      "Value and basis come from the company's own records or an approved source - none is supplied.")
def _productivity(d: dict) -> dict:
    _no_extra(d, {"category", "factor", "scope_cost_prefix", "scope_wbs", "applies_to"}, "productivity_factor")
    out = {"category": text(d, "category", choices=PRODUCTIVITY_CATEGORIES), "factor": dec(d, "factor", gt="0"),
           "scope_cost_prefix": text(d, "scope_cost_prefix", required=False), "scope_wbs": text(d, "scope_wbs", required=False),
           "applies_to": text(d, "applies_to", required=False, choices=("labour",)) or "labour"}
    return out


@kind("plant_hire_terms", "Plant minimum-hire / standby terms", {P, C, A},
      "Per plant resource: minimum chargeable quantity (in the resource's rate unit) over the project and a standby quantity charged at a "
      "percentage of the approved rate. Values come from the hire contract or quotation.")
def _plant_terms(d: dict) -> dict:
    _no_extra(d, {"resource_id", "min_hire_qty", "standby_qty", "standby_pct_of_rate"}, "plant_hire_terms")
    out = {"resource_id": text(d, "resource_id"), "min_hire_qty": dec(d, "min_hire_qty", required=False, ge="0") or "0",
           "standby_qty": dec(d, "standby_qty", required=False, ge="0") or "0",
           "standby_pct_of_rate": dec(d, "standby_pct_of_rate", required=False, ge="0", le="100")}
    if Decimal(out["standby_qty"]) > 0 and out["standby_pct_of_rate"] is None:
        raise ValidationFailed("standby_qty > 0 requires standby_pct_of_rate (from the hire terms).", code="PARAM_FIELD")
    return out


@kind("calendar", "Project calendar", {E, C, A},
      "Start date, working weekdays (0=Mon..6=Sun) and non-working dates. Working weekdays and holidays are entered by the estimator from the "
      "contract / client calendar - none are assumed.")
def _calendar(d: dict) -> dict:
    _no_extra(d, {"start_date", "work_weekdays", "holidays", "hours_per_day"}, "calendar")
    sd = text(d, "start_date")
    try:
        date.fromisoformat(sd)
    except ValueError:
        raise ValidationFailed("start_date must be YYYY-MM-DD.", code="PARAM_FIELD")
    wd = d.get("work_weekdays")
    if isinstance(wd, str):
        wd = [x for x in re.split(r"[,\s]+", wd) if x != ""]
    try:
        wd = sorted({int(x) for x in (wd or [])})
    except (TypeError, ValueError):
        raise ValidationFailed("work_weekdays must be integers 0..6.", code="PARAM_FIELD")
    if not wd or any(x < 0 or x > 6 for x in wd):
        raise ValidationFailed("work_weekdays must list at least one weekday 0..6 (0=Monday).", code="PARAM_FIELD")
    hol = d.get("holidays") or []
    if isinstance(hol, str):
        hol = [x for x in re.split(r"[,\s]+", hol) if x]
    for h in hol:
        try:
            date.fromisoformat(str(h))
        except ValueError:
            raise ValidationFailed(f"holiday {h!r} must be YYYY-MM-DD.", code="PARAM_FIELD")
    return {"start_date": sd, "work_weekdays": wd, "holidays": sorted({str(h) for h in hol}),
            "hours_per_day": dec(d, "hours_per_day", required=False, gt="0")}
