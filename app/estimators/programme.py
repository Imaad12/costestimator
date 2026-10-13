"""Critical-path scheduling with relationship types (FS/SS/FF/SF), lags, float, simple date constraints and a working calendar.

Pure Decimal arithmetic in WORKING-DAY offsets (day k spans [k, k+1)). Durations, lags and constraints are inputs from a person; nothing is
derived or defaulted. The existing finish-to-start `duration.cpm` keeps working; this module generalises it.

  FS: ES_s >= EF_p + lag      SS: ES_s >= ES_p + lag      FF: EF_s >= EF_p + lag      SF: EF_s >= ES_p + lag
  backward pass mirrors these with the latest times; project finish = max EF (or the latest FNLT deadline for tasks that have one)
  total float = LS - ES ; free float = min over successors of the slack of the link that constrains the task
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from ..core.errors import ValidationFailed
from ..core.money import ZERO, D

REL_TYPES = ("FS", "SS", "FF", "SF")


@dataclass
class Link:
    pred: str
    type: str = "FS"
    lag: Decimal = ZERO

    def text(self) -> str:
        if self.type == "FS" and self.lag == 0:
            return self.pred
        return f"{self.pred}{self.type}{'+' if self.lag >= 0 else ''}{self.lag}"


@dataclass
class Task:
    code: str
    duration: Decimal
    links: list[Link] = field(default_factory=list)
    snet: Decimal | None = None          # start no earlier than (working-day offset)
    fnlt: Decimal | None = None          # finish no later than (working-day offset)


@dataclass
class TaskResult:
    code: str
    duration: Decimal
    es: Decimal
    ef: Decimal
    ls: Decimal
    lf: Decimal
    total_float: Decimal
    free_float: Decimal
    critical: bool


@dataclass
class ScheduleOut:
    tasks: dict[str, TaskResult]
    project_days: Decimal
    critical_path: list[str]
    driving_path: list[str]
    negative_float: list[str]


_PRED = re.compile(r"^(?P<code>.+?)(?:\s*(?P<type>FS|SS|FF|SF))?\s*(?P<lag>[+-]\s*\d+(?:\.\d+)?)?\s*[dD]?$")


def parse_predecessors(text: str | list | None, known: set[str]) -> list[Link]:
    """'A, B-SS+2, C FF-1' -> links. A token equal to a known task code is always a plain FS link (task codes may contain '-')."""
    if not text:
        return []
    toks = [t.strip() for t in (text.split(",") if isinstance(text, str) else text) if str(t).strip()]
    out: list[Link] = []
    for t in toks:
        t = str(t)
        if t in known:
            out.append(Link(t))
            continue
        m = _PRED.match(t)
        code = m.group("code").strip() if m else ""
        if code not in known and code[:-1] in known and code[-1:] in "-_":          # 'C-SS+2': the dash is a separator
            code = code[:-1]
        if not m or code not in known:
            raise ValidationFailed(f"Cannot read predecessor '{t}'. Use CODE, CODE-SS+2, CODE-FF-1 (types FS/SS/FF/SF, lag in working days).",
                                   code="SCHEDULE_UNKNOWN_PRED")
        typ = m.group("type") or "FS"
        lag = D(m.group("lag").replace(" ", "")) if m.group("lag") else ZERO
        out.append(Link(code, typ, lag))
    return out


def schedule(tasks: list[Task]) -> ScheduleOut:
    by = {t.code: t for t in tasks}
    if len(by) != len(tasks):
        raise ValidationFailed("Duplicate task code.", code="SCHEDULE_DUPLICATE_TASK")
    for t in tasks:
        if t.duration is None or t.duration < 0:
            raise ValidationFailed(f"Task {t.code} has an invalid duration.", code="SCHEDULE_DURATION")
        for l in t.links:
            if l.pred not in by:
                raise ValidationFailed(f"Task {t.code} has unknown predecessor {l.pred}.", code="SCHEDULE_UNKNOWN_PRED")
            if l.type not in REL_TYPES:
                raise ValidationFailed(f"Relationship type must be one of {REL_TYPES}.", code="SCHEDULE_REL_TYPE")
            if l.pred == t.code:
                raise ValidationFailed(f"Task {t.code} depends on itself.", code="SCHEDULE_CYCLE")
    # topological order (Kahn) with cycle report
    indeg = {c: len(t.links) for c, t in by.items()}
    succ: dict[str, list[tuple[str, Link]]] = {c: [] for c in by}
    for t in tasks:
        for l in t.links:
            succ[l.pred].append((t.code, l))
    order, ready = [], sorted(c for c, n in indeg.items() if n == 0)
    while ready:
        c = ready.pop(0)
        order.append(c)
        for s, _ in succ[c]:
            indeg[s] -= 1
            if indeg[s] == 0:
                ready.append(s)
        ready.sort()
    if len(order) != len(by):
        rest = sorted(c for c, n in indeg.items() if n > 0)
        raise ValidationFailed(f"Schedule has a dependency cycle involving: {', '.join(rest)}", code="SCHEDULE_CYCLE")
    es: dict[str, Decimal] = {}
    ef: dict[str, Decimal] = {}
    driver: dict[str, str | None] = {}
    for c in order:
        t = by[c]
        start, drv = ZERO, None
        if t.snet is not None and t.snet > start:
            start = t.snet
        for l in t.links:
            p = by[l.pred]
            if l.type == "FS":
                cand = ef[l.pred] + l.lag
            elif l.type == "SS":
                cand = es[l.pred] + l.lag
            elif l.type == "FF":
                cand = ef[l.pred] + l.lag - t.duration
            else:
                cand = es[l.pred] + l.lag - t.duration
            if cand > start or (cand == start and drv is None and cand > ZERO):
                start, drv = cand, l.pred
        es[c], ef[c], driver[c] = start, start + t.duration, drv
    end = max(ef.values()) if ef else ZERO
    ls: dict[str, Decimal] = {}
    lf: dict[str, Decimal] = {}
    for c in reversed(order):
        t = by[c]
        latest_finish = end if not succ[c] else None
        cands: list[Decimal] = []                       # candidate LS values from each successor link
        for s, l in succ[c]:
            if l.type == "FS":
                cands.append(ls[s] - l.lag - t.duration)
            elif l.type == "SS":
                cands.append(ls[s] - l.lag)
            elif l.type == "FF":
                cands.append(lf[s] - l.lag - t.duration)
            else:
                cands.append(lf[s] - l.lag)
        if latest_finish is not None:
            cands.append(latest_finish - t.duration)
        if t.fnlt is not None:
            cands.append(t.fnlt - t.duration)
        ls[c] = min(cands)
        lf[c] = ls[c] + t.duration
    res: dict[str, TaskResult] = {}
    for c in order:
        t = by[c]
        ff_c: list[Decimal] = []
        for s, l in succ[c]:
            if l.type == "FS":
                ff_c.append(es[s] - (ef[c] + l.lag))
            elif l.type == "SS":
                ff_c.append(es[s] - (es[c] + l.lag))
            elif l.type == "FF":
                ff_c.append(ef[s] - (ef[c] + l.lag))
            else:
                ff_c.append(ef[s] - (es[c] + l.lag))
        if not succ[c]:
            ff_c.append(end - ef[c])
        tf = ls[c] - es[c]
        res[c] = TaskResult(c, t.duration, es[c], ef[c], ls[c], lf[c], tf, max(min(ff_c), ZERO) if ff_c else ZERO, tf <= 0)
    crit = sorted((c for c in order if res[c].critical), key=lambda c: (res[c].es, c))
    # driving path: walk back from the latest-finishing task along the predecessors that set each start
    path: list[str] = []
    cur = max(order, key=lambda c: (ef[c], c)) if order else None
    while cur:
        path.append(cur)
        cur = driver.get(cur)
    return ScheduleOut(res, end, crit, list(reversed(path)), sorted(c for c in order if res[c].total_float < 0))


# ------------------------------------------------------------------------------------------------ calendar
@dataclass
class Calendar:
    start: date
    weekdays: frozenset[int]
    holidays: frozenset[date]

    def is_working(self, d: date) -> bool:
        return d.weekday() in self.weekdays and d not in self.holidays

    def working_date(self, k: int) -> date:
        """Date of the k-th working day (0-based) counted from `start`."""
        if k < 0:
            raise ValidationFailed("Negative working-day offset.")
        d, n = self.start, -1
        for _ in range(366 * 60):
            if self.is_working(d):
                n += 1
                if n == k:
                    return d
            d += timedelta(days=1)
        raise ValidationFailed("Calendar has no working days in range.")

    def offset_of(self, d: date) -> int:
        """Working-day offset at which date `d` begins (number of working days from start to d, exclusive)."""
        if d < self.start:
            raise ValidationFailed("Date is before the project start.")
        n, cur = 0, self.start
        while cur < d:
            if self.is_working(cur):
                n += 1
            cur += timedelta(days=1)
        return n


def calendar_from_param(data: dict) -> Calendar:
    return Calendar(date.fromisoformat(data["start_date"]), frozenset(int(x) for x in data["work_weekdays"]),
                    frozenset(date.fromisoformat(h) for h in data.get("holidays") or []))


def task_dates(cal: Calendar, es: Decimal, ef: Decimal) -> tuple[date, date]:
    """Start date = working day containing offset ES; finish date = working day containing the last instant before EF (milestone: start date)."""
    import math
    s = cal.working_date(int(math.floor(es)))
    last = max(int(math.ceil(ef)) - 1, int(math.floor(es))) if ef > es else int(math.floor(es))
    return s, cal.working_date(last)
