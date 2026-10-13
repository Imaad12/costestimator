"""Registry of read-only project reports / analyses that are exposed identically by the REST API, the web UI and the CLI.
A report is a function (db, project_id, **params) -> dict. Reports never change an estimate and never approve anything; parameters arrive as strings."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..core.errors import ValidationFailed
from ..database import Database


@dataclass
class Report:
    name: str
    label: str
    description: str
    fn: Callable
    params: list[tuple[str, str, str]] = field(default_factory=list)      # (name, default, help)
    group: str = "Analysis"


REPORTS: dict[str, Report] = {}


def report(name: str, label: str, description: str, params: list[tuple[str, str, str]] | None = None, group: str = "Analysis"):
    def deco(fn):
        REPORTS[name] = Report(name, label, description, fn, params or [], group)
        return fn
    return deco


def run_report(db: Database, name: str, project_id: str, params: dict | None = None) -> dict:
    if name not in REPORTS:
        raise ValidationFailed(f"Unknown report '{name}'. Known: {sorted(REPORTS)}", code="UNKNOWN_REPORT")
    r = REPORTS[name]
    clean = {}
    for pname, default, _ in r.params:
        v = (params or {}).get(pname)
        clean[pname] = default if v in (None, "") else v
    extra = set(params or {}) - {p[0] for p in r.params}
    if extra:
        raise ValidationFailed(f"Unknown parameter(s) {sorted(extra)} for report {name}.", code="UNKNOWN_PARAM")
    return r.fn(db, project_id, **clean)


def listing() -> list[dict]:
    return [dict(name=r.name, label=r.label, description=r.description, group=r.group, params=[dict(name=n, default=d, help=h) for n, d, h in r.params])
            for r in REPORTS.values()]


# ------------------------------------------------------------------------------------------------ registrations
@report("rollup", "Cost roll-up (CBS / WBS / client cross-walk)", "Direct cost rolled up by cost-code tree, WBS, WBS x division matrix and each client code system; ties out to the estimate.",
        [("preliminary", "0", "1 = include unapproved inputs (flagged)")], group="Structure")
def _rollup(db, pid, preliminary="0"):
    from ..services import wbs
    return wbs.rollup_report(db, pid, include_unapproved=str(preliminary) in ("1", "true", "yes"))


@report("schedule", "Programme: dates, float, critical path", "CPM with relationship types, lags and an optional working calendar.", group="Programme")
def _schedule(db, pid):
    from ..services import programme
    return programme.schedule_report(db, pid)


@report("loading", "Resource loading histogram", "Labour hours, plant hours or cost spread over the programme and bucketed by week / month / block.",
        [("measure", "labour_hours", "labour_hours | plant_hours | cost"), ("period", "week", "week | month | block"), ("block_days", "5", "working days per block when no calendar"),
         ("preliminary", "0", "1 = include unapproved inputs")], group="Programme")
def _loading(db, pid, measure="labour_hours", period="week", block_days="5", preliminary="0"):
    from ..services import programme
    return programme.loading_report(db, pid, measure=measure, period=period, block_days=int(block_days), include_unapproved=str(preliminary) in ("1", "true", "yes"))


@report("manhours", "Man-hour aggregation", "Own-labour hours by craft, cost code, division and WBS (subcontract labour is not included).",
        [("preliminary", "0", "1 = include unapproved inputs")], group="Programme")
def _manhours(db, pid, preliminary="0"):
    from ..services import programme
    return programme.manhours_report(db, pid, include_unapproved=str(preliminary) in ("1", "true", "yes"))
