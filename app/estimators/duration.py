"""Deterministic duration helpers. All outputs are PROPOSALS until a human approves project duration."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..core.errors import ValidationFailed
from ..core.money import ZERO, D, D_opt


@dataclass
class ScheduleResult:
    project_days: Decimal
    critical_path: list[str]
    early_finish: dict[str, Decimal]


def cpm(tasks: list[dict]) -> ScheduleResult:
    """Forward-pass critical path. tasks: [{task_code, duration_days, predecessors: [codes]}]. Detects cycles."""
    by = {t["task_code"]: t for t in tasks}
    for t in tasks:
        for p in t.get("predecessors") or []:
            if p not in by:
                raise ValidationFailed(f"Task {t['task_code']} has unknown predecessor {p}.", code="SCHEDULE_UNKNOWN_PRED")
    ef: dict[str, Decimal] = {}
    best_pred: dict[str, str | None] = {}
    state: dict[str, int] = {}

    def visit(code: str, trail: tuple[str, ...]):
        if state.get(code) == 2:
            return
        if state.get(code) == 1:
            raise ValidationFailed(f"Schedule has a dependency cycle: {' > '.join(trail + (code,))}", code="SCHEDULE_CYCLE")
        state[code] = 1
        t = by[code]
        es = ZERO
        bp = None
        for p in t.get("predecessors") or []:
            visit(p, trail + (code,))
            if ef[p] > es or bp is None:
                if ef[p] >= es:
                    es, bp = ef[p], p
        dur = D_opt(t["duration_days"])
        if dur is None or dur < 0:
            raise ValidationFailed(f"Task {code} has an invalid duration.")
        ef[code] = es + dur
        best_pred[code] = bp
        state[code] = 2

    for c in by:
        visit(c, ())
    if not ef:
        return ScheduleResult(ZERO, [], {})
    end = max(ef, key=lambda k: ef[k])
    path, cur = [], end
    while cur:
        path.append(cur)
        cur = best_pred.get(cur)
    return ScheduleResult(ef[end], list(reversed(path)), ef)


def days_to_months(days: Decimal, working_days_per_month: Decimal) -> Decimal:
    if working_days_per_month is None or working_days_per_month <= 0:
        raise ValidationFailed("working_days_per_month (approved calendar assumption) is required.")
    return days / working_days_per_month


def labour_derived_months(total_labour_hours: Decimal, crew_size: Decimal, hours_per_day: Decimal,
                          working_days_per_month: Decimal) -> Decimal:
    """Proposal for self-performed work: hours / (crew x hours/day) / working days per month."""
    for n, v in (("crew_size", crew_size), ("hours_per_day", hours_per_day), ("working_days_per_month", working_days_per_month)):
        if v is None or v <= 0:
            raise ValidationFailed(f"{n} must be > 0.")
    return total_labour_hours / (crew_size * hours_per_day) / working_days_per_month
