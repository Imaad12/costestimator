"""Programme services: human-entered tasks with relationship types, schedule report with float and dates, time-phased resource loading and
man-hour aggregation. All durations/links/constraints are inputs from a person; results are analysis, never approved cost."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..approvals import engine as approvals
from ..core.errors import ValidationFailed
from ..core.money import ZERO, D, D_opt
from ..database import Database, rows_to_dicts
from ..estimators import loading, programme
from ..models.actor import Actor
from . import analysis, audit, governed, projects


def calendar_for(db: Database, project_id: str, include_unapproved: bool = False) -> programme.Calendar | None:
    rows = governed.effective(db, project_id, "calendar", include_unapproved=include_unapproved)
    if not rows:
        return None
    pick = next((r for r in rows if r["code"] == "PROJECT"), rows[0])
    return programme.calendar_from_param(pick["data"])


def _constraint(val, cal: programme.Calendar | None, what: str) -> Decimal | None:
    if val in (None, ""):
        return None
    s = str(val).strip()
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        if cal is None:
            raise ValidationFailed(f"{what} is a date but the project has no approved calendar.", code="CALENDAR_REQUIRED")
        return Decimal(cal.offset_of(date.fromisoformat(s)))
    d = D_opt(s)
    if d is None or d < 0:
        raise ValidationFailed(f"{what} must be a working-day offset >= 0 or an ISO date.", code="SCHEDULE_CONSTRAINT")
    return d


def to_engine_tasks(rows: list[dict], cal: programme.Calendar | None) -> list[programme.Task]:
    known = {r["task_code"] for r in rows}
    return [programme.Task(r["task_code"], D(r["duration_days"]), programme.parse_predecessors(r.get("predecessors"), known),
                           snet=_constraint(r.get("snet"), cal, f"{r['task_code']} SNET"), fnlt=_constraint(r.get("fnlt"), cal, f"{r['task_code']} FNLT"))
            for r in rows]


def validate_tasks(tasks: list[dict], cal: programme.Calendar | None = None) -> programme.ScheduleOut:
    codes = [t["task_code"] for t in tasks]
    if len(codes) != len(set(codes)):
        raise ValidationFailed("Duplicate task_code in the task list.", code="SCHEDULE_DUPLICATE_TASK")
    rows = [{**t, "predecessors": t.get("predecessors")} for t in tasks]
    return programme.schedule(to_engine_tasks(rows, cal))


def schedule_report(db: Database, project_id: str, *, include_unapproved: bool = False) -> dict:
    rows = rows_to_dicts(db.all("SELECT * FROM schedule_tasks WHERE project_id=? ORDER BY id", (project_id,)))
    if not rows:
        raise ValidationFailed("No schedule tasks.", code="NO_SCHEDULE")
    cal = calendar_for(db, project_id, include_unapproved)
    out = programme.schedule(to_engine_tasks(rows, cal))
    names = {r["task_code"]: r for r in rows}
    tasks = []
    for r in rows:
        t = out.tasks[r["task_code"]]
        row = dict(task_code=t.code, name=r["name"], duration=t.duration, es=t.es, ef=t.ef, ls=t.ls, lf=t.lf, total_float=t.total_float,
                   free_float=t.free_float, critical=t.critical, predecessors=r["predecessors"], wbs_code=r.get("wbs_code"), cost_code=r.get("cost_code"))
        if cal:
            row["start_date"], row["finish_date"] = (d.isoformat() for d in programme.task_dates(cal, t.es, t.ef))
        tasks.append(row)
    rep = dict(project_id=project_id, project_working_days=out.project_days, critical_path=out.critical_path, driving_path=out.driving_path,
               negative_float=out.negative_float, tasks=tasks, calendar=None if not cal else dict(start=cal.start.isoformat(), weekdays=sorted(cal.weekdays),
                                                                                                   holidays=sorted(h.isoformat() for h in cal.holidays)))
    if cal:
        rep["finish_date"] = programme.task_dates(cal, out.project_days, out.project_days)[0].isoformat() if out.project_days else None
        rep["project_finish_date"] = max(t["finish_date"] for t in tasks)
    return rep


# ------------------------------------------------------------------------------------------ line -> task allocation
def assign_lines_to_tasks(task_rows: list[dict], line_cost_code: str | None, wbs_chain: set[str], dur_by_task: dict[str, Decimal]) -> list[tuple[str, Decimal]]:
    """A task is a candidate only if it declares a cost-code prefix and/or a WBS node and the line matches every scope it declares. The most specific
    candidates win (longest cost-code prefix, then a WBS-scoped task over an unscoped-WBS one). Several equally specific tasks share the quantity
    in proportion to their durations (equally if all durations are zero)."""
    best_score, best = None, []
    for t in task_rows:
        pre, w = t.get("cost_code") or "", t.get("wbs_code") or ""
        if not pre and not w:
            continue
        if pre and not (line_cost_code or "").startswith(pre):
            continue
        if w and w not in wbs_chain:
            continue
        score = (len(pre), 1 if w else 0)
        if best_score is None or score > best_score:
            best_score, best = score, [t]
        elif score == best_score:
            best.append(t)
    if not best:
        return []
    weights = [dur_by_task.get(t["task_code"], ZERO) for t in best]
    tot = sum(weights, ZERO)
    if tot == 0:
        return [(t["task_code"], Decimal(1) / len(best)) for t in best]
    return [(t["task_code"], w / tot) for t, w in zip(best, weights)]


def _wbs_chain(inp, item_key: str) -> set[str]:
    from ..estimators.direct_cost import _wbs_chain as chain
    return chain(inp, item_key)


def _bucketer(cal: programme.Calendar | None, period: str, block_days: int):
    if cal is None or period == "block":
        return loading.block_bucketer(block_days)

    def f(day: int) -> str:
        d = cal.working_date(day)
        return f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}" if period == "week" else d.strftime("%Y-%m")
    return f


def loading_report(db: Database, project_id: str, *, measure: str = "labour_hours", period: str = "week", block_days: int = 5,
                   est=None, include_unapproved: bool = False, line_filter=None) -> dict:
    """Time-phase labour hours / plant hours / cost over the programme. Uniform spread over each task's working days (stated simplification)."""
    from ..estimators.estimate import compute_estimate
    if measure not in ("labour_hours", "plant_hours", "cost"):
        raise ValidationFailed("measure must be labour_hours, plant_hours or cost.")
    if period not in ("week", "month", "block"):
        raise ValidationFailed("period must be week, month or block.")
    est = est or compute_estimate(db, project_id, include_unapproved=include_unapproved)
    rows = rows_to_dicts(db.all("SELECT * FROM schedule_tasks WHERE project_id=? ORDER BY id", (project_id,)))
    if not rows:
        raise ValidationFailed("Loading needs a programme: enter schedule tasks first.", code="NO_SCHEDULE")
    cal = calendar_for(db, project_id, include_unapproved)
    sch = programme.schedule(to_engine_tasks(rows, cal))
    sched = {c: (t.es, t.ef) for c, t in sch.tasks.items()}
    durs = {c: t.duration for c, t in sch.tasks.items()}
    loads, source_total = [], ZERO
    for l in est.direct.lines:
        if line_filter is not None and not line_filter(l):
            continue
        if measure == "labour_hours":
            if l.kind != "labour" or l.hours is None:
                continue
            q, key = l.hours, l.resource_id or "(labour)"
        elif measure == "plant_hours":
            if l.kind != "plant" or l.hours is None or l.amount is None:
                continue
            q, key = l.hours, l.resource_id or "(plant)"
        else:
            if l.amount is None:
                continue
            q, key = l.amount, l.kind
        source_total += q
        alloc = assign_lines_to_tasks(rows, l.cost_code, _wbs_chain(est.inputs, l.item_key), durs)
        if not alloc:
            loads.append(loading.Load(key, None, q))
        else:
            for tc, w in alloc:
                loads.append(loading.Load(key, tc, q * w))
    h = loading.histogram(loads, sched, _bucketer(cal, period, block_days))
    scheduled = sum(h["totals"].values(), ZERO)
    uns = sum(h["unscheduled"].values(), ZERO)
    names = {r["resource_id"]: r["description"] for r in db.all("SELECT id resource_id, description FROM resources")} if measure != "cost" else {}
    return dict(project_id=project_id, measure=measure, period=period if cal or period == "block" else "block", calendar_used=bool(cal),
                note="Uniform spread of each quantity over its task's working days; lines allocated to tasks by cost-code prefix / WBS scope.",
                **h, source_total=source_total, scheduled_total=scheduled, unscheduled_total=uns,
                tie_out=abs(source_total - scheduled - uns) < Decimal("0.0001"), names=names, estimate_state=est.state)


def manhours_report(db: Database, project_id: str, *, est=None, include_unapproved: bool = False) -> dict:
    """Labour man-hours from the priced estimate, by craft (resource), cost code, division, WBS and kind of work. Hours exist only for self-performed
    labour lines; subcontract/lump-sum items carry no hours and are listed so nobody mistakes the total for project man-hours."""
    from ..estimators.estimate import compute_estimate
    est = est or compute_estimate(db, project_id, include_unapproved=include_unapproved)
    by_res: dict[str, Decimal] = {}
    by_cc: dict[str, Decimal] = {}
    by_div: dict[str, Decimal] = {}
    by_wbs: dict[str, Decimal] = {}
    by_item: dict[str, Decimal] = {}
    unpriced_hours = ZERO
    total = ZERO
    for l in est.direct.lines:
        if l.kind != "labour" or l.hours is None:
            continue
        h = l.hours
        total += h
        by_res[l.resource_id or "(labour)"] = by_res.get(l.resource_id or "(labour)", ZERO) + h
        cc = l.cost_code or "(none)"
        by_cc[cc] = by_cc.get(cc, ZERO) + h
        by_div[cc.split(".")[0]] = by_div.get(cc.split(".")[0], ZERO) + h
        w = est.inputs.item_wbs.get(l.item_key) or "(unassigned)"
        by_wbs[w] = by_wbs.get(w, ZERO) + h
        by_item[l.item_key] = by_item.get(l.item_key, ZERO) + h
        if l.amount is None:
            unpriced_hours += h
    names = {r["id"]: r["description"] for r in db.all("SELECT id, description FROM resources")}
    no_hours_items = [k for k, ic in est.direct.items.items() if ic.pricing_method in ("subcontract_lump", "allowance", "provisional_sum", "prime_cost_sum")
                      and k not in by_item]
    return dict(project_id=project_id, total_hours=total, hours_on_unpriced_lines=unpriced_hours, by_resource=by_res, resource_names={k: names.get(k, "") for k in by_res},
                by_cost_code=by_cc, by_division=by_div, by_wbs=by_wbs, by_item=by_item, items_without_hours=no_hours_items,
                note="Own-labour hours only. Subcontract, allowance and lump-sum items contain labour that is NOT counted here.",
                tie_out=sum(by_res.values(), ZERO) == total == sum(by_wbs.values(), ZERO) == sum(by_cc.values(), ZERO), estimate_state=est.state)
