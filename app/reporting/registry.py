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


@report("classification", "Estimate classification and maturity", "Class and accuracy range from the APPROVED classification scheme and the estimator's stated maturity, next to measured maturity facts.",
        group="Basis of estimate")
def _classification(db, pid):
    from ..services import profiles
    return profiles.classification_report(db, pid)


@report("compliance", "Client profile compliance matrix", "Requirements loaded from the owner's controlled documents, evaluated against measured facts or human attestations.",
        group="Basis of estimate")
def _compliance(db, pid):
    from ..services import profiles
    return profiles.compliance_report(db, pid)


@report("mto_status", "Take-off derivation status", "Applications of take-off templates and whether their factors / drivers have changed since.", group="Structure")
def _mto_status(db, pid):
    from ..services import mto
    return mto.status_report(db, pid)


@report("mto_preview", "Take-off derivation preview", "What a template would derive for an item (nothing is written).",
        [("item_key", "", "BOQ item key"), ("template", "", "template code"), ("driver_qty", "", "measured driver quantity (optional)"),
         ("driver_source", "", "source of the driver quantity when given")], group="Structure")
def _mto_preview(db, pid, item_key="", template="", driver_qty="", driver_source=""):
    from ..services import mto
    return mto.preview(db, pid, item_key, template, driver_qty or None, driver_source or None)


@report("boe", "Basis of Estimate (facts)", "Structured facts for the Basis of Estimate; generate the document with the generate_boe action.", group="Basis of estimate")
def _boe(db, pid):
    from ..services import boe
    return boe.build_boe(db, pid)
