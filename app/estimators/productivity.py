"""PURE deterministic productivity, crew and resource-constrained programme engine (Decimal; no database).

Method (docs/WORKFORCE_PRODUCTIVITY_AND_PROGRAMME_METHOD.md):
  labour-hours basis : hours = Q x norm (labour-hours per unit) x product(factors)
                       crew-days = hours / (productive hours per worker-day x crew size)           [= hours / crew daily capacity]
  crew-output basis  : crew-days = Q / norm (units per crew-day) x product(factors)                  [the labour-hours formula is NOT applied again]
  A norm flagged `includes_productivity_factors` already contains site factors: supplying a further factor is refused (double counting).
  unconstrained duration = ceil(crew-days / effective crews) working days, effective crews = min(crews, work fronts), plus elapsed set-up / lead-in
  and curing / testing / inspection days entered by a person.
Four durations are kept apart: unconstrained, dependency-constrained (CPM), procurement-constrained (CPM + material-ready day) and resource-constrained
(daily simulation against the finite pool, work fronts, shifts, attendance, overtime, calendar hours). Nothing is divided by head-count shortcuts.
No productivity value lives in this file: norms come from approved (or explicitly provisional) rows supplied by the caller.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

from ..core.errors import ValidationFailed

D = Decimal
ZERO = D(0)
Q2 = D("0.01")
MAX_DAYS = 4000


def q2(x: Decimal) -> Decimal:
    return D(x).quantize(Q2, rounding=ROUND_HALF_UP)


def ceil_int(x: Decimal) -> int:
    return int(D(x).to_integral_value(rounding=ROUND_CEILING))


def floor_int(x: Decimal) -> int:
    return int(D(x).to_integral_value(rounding=ROUND_FLOOR))


# ------------------------------------------------------------------------------------------------ calendar
@dataclass(frozen=True)
class WorkCalendar:
    start: date
    weekdays: frozenset[int]
    holidays: frozenset[date] = frozenset()
    standard_hours: Decimal = D(8)
    reduced: tuple[tuple[date, date, Decimal], ...] = ()          # (from, to, hours) approved reduced-hour windows
    shutdowns: tuple[tuple[date, date], ...] = ()
    confirmed: bool = False                                        # False: a default profile that the project has not confirmed

    def in_shutdown(self, d: date) -> bool:
        return any(a <= d <= b for a, b in self.shutdowns)

    def is_working(self, d: date) -> bool:
        return d.weekday() in self.weekdays and d not in self.holidays and not self.in_shutdown(d)

    def hours_on(self, d: date) -> Decimal:
        if not self.is_working(d):
            return ZERO
        for a, b, h in self.reduced:
            if a <= d <= b:
                return h
        return self.standard_hours

    def day_factor(self, d: date) -> Decimal:
        """Share of a standard working day that is available on `d` (1 normally, <1 in an approved reduced-hour window, 0 on a non-working day)."""
        return self.hours_on(d) / self.standard_hours

    def working_dates(self, n: int) -> list[date]:
        """The first n working dates counted from start."""
        out, d = [], self.start
        for _ in range(366 * 40):
            if self.is_working(d):
                out.append(d)
                if len(out) == n:
                    return out
            d += timedelta(days=1)
        raise ValidationFailed("Calendar has too few working days.", code="CALENDAR_RANGE")

    def describe(self) -> dict:
        return dict(start=self.start.isoformat(), work_weekdays=sorted(self.weekdays), holidays=sorted(h.isoformat() for h in self.holidays),
                    standard_hours=str(self.standard_hours), reduced_hours=[dict(frm=a.isoformat(), to=b.isoformat(), hours=str(h)) for a, b, h in self.reduced],
                    shutdowns=[dict(frm=a.isoformat(), to=b.isoformat()) for a, b in self.shutdowns], confirmed=self.confirmed)


def calendar_from_data(data: dict, *, confirmed: bool) -> WorkCalendar:
    std = D(str(data.get("hours_per_day") or 8)) if data.get("hours_per_day") else None
    if std is None:
        raise ValidationFailed("The calendar must state hours_per_day (the standard working day) for productivity planning.", code="CALENDAR_HOURS_REQUIRED")
    return WorkCalendar(date.fromisoformat(data["start_date"]), frozenset(int(x) for x in data["work_weekdays"]),
                        frozenset(date.fromisoformat(h) for h in data.get("holidays") or []), std,
                        tuple((date.fromisoformat(w["from"]), date.fromisoformat(w["to"]), D(str(w["hours"]))) for w in data.get("reduced_hours") or []),
                        tuple((date.fromisoformat(w["from"]), date.fromisoformat(w["to"])) for w in data.get("shutdowns") or []), confirmed)


# ------------------------------------------------------------------------------------------------ inputs
@dataclass(frozen=True)
class Norm:
    id: str
    version: int
    basis: str                              # labour_hours_per_unit | crew_output_per_crew_day
    value: Decimal
    crew: dict                              # role -> head-count in ONE crew
    includes_factors: bool = False
    status: str = "Approved"
    evidence_status: str = "unverified"
    is_synthetic: bool = False
    unit: str = ""


@dataclass(frozen=True)
class Factor:
    name: str
    value: Decimal                          # multiplier on labour-hours / crew-days (>1 slower)
    source: str = ""
    approved: bool = False


@dataclass(frozen=True)
class ActivityIn:
    code: str
    name: str
    quantity: Decimal | None
    unit: str = ""
    norm: Norm | None = None
    crews: int = 1
    fronts: int = 1
    factors: tuple[Factor, ...] = ()
    setup_days: int = 0                     # elapsed before work (mobilisation / set-up / access)
    post_days: int = 0                      # elapsed after work (curing / testing / inspection)
    predecessors: tuple[tuple[str, int], ...] = ()      # (code, lag working days) finish-to-start
    ready_wd: int = 0                       # first working-day index at which the material is on site (procurement constraint)
    priority: int = 0
    fixed_only: bool = False                # a fixed-duration activity (mobilisation, commissioning window): only its set-up / post days, no work content


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    pool: dict                              # role -> head-count per shift (direct + equipment + subcontract capacity keys)
    indirect: dict = field(default_factory=dict)
    shifts: int = 1
    night_efficiency: Decimal = D(1)        # 0..1 efficiency of shifts after the first
    attendance: Decimal = D(1)              # 0..1
    availability: Decimal = D(1)            # 0..1
    productive_hours: Decimal = D(6)        # productive hours per worker per shift (a person-entered planning value)
    overtime_hours: Decimal = ZERO
    overtime_efficiency: Decimal = D(1)
    fronts_limit: int | None = None
    mobilisation_wd: int = 0
    role_day_cost: dict | None = None
    is_synthetic: bool = False
    status: str = "Approved"
    archetype: str = "custom"


# ------------------------------------------------------------------------------------------------ per-activity content
def crew_days_required(a: ActivityIn, prof: Profile) -> tuple[Decimal, Decimal, list[str]]:
    """(crew-days at standard productivity, labour-hours, problems) for activity `a`."""
    prob: list[str] = []
    n = a.norm
    if n is None or a.quantity is None:
        return ZERO, ZERO, ["no norm" if n is None else "no quantity"]
    fac = D(1)
    if a.factors:
        if n.includes_factors:
            prob.append("DOUBLE_COUNT: the norm already includes productivity factors; a further factor was supplied and is ignored")
        else:
            for f in a.factors:
                fac *= f.value
    crew_size = D(sum(int(v) for v in n.crew.values()))
    if crew_size <= 0:
        return ZERO, ZERO, ["norm crew is empty"]
    if n.basis == "labour_hours_per_unit":
        hours = a.quantity * n.value * fac
        return hours / (prof.productive_hours * crew_size), hours, prob
    # crew output basis: units per crew-day -> do not re-apply labour-hours
    cd = a.quantity / n.value * fac
    return cd, cd * crew_size * prof.productive_hours, prob


def shift_multiplier(p: Profile) -> Decimal:
    return D(1) + (p.night_efficiency * (p.shifts - 1) if p.shifts > 1 else ZERO)


def day_output_per_crew(p: Profile, day_factor: Decimal) -> Decimal:
    """Crew-days delivered by one crew on one working day: calendar hours share x (1 + overtime gain) x shift multiplier."""
    ot = (p.overtime_hours * p.overtime_efficiency / p.productive_hours) if p.productive_hours > 0 else ZERO
    return day_factor * (D(1) + ot) * shift_multiplier(p)


def usable_pool(p: Profile) -> dict:
    """Head-count available per shift. Attendance and availability apply to own labour only: equipment ('eq:') and contracted subcontract capacity ('sub:') are counted as stated."""
    f = p.attendance * p.availability
    return {r: (int(n) if r.startswith(("eq:", "sub:")) else floor_int(D(int(n)) * f)) for r, n in p.pool.items()}


# ------------------------------------------------------------------------------------------------ CPM (finish-to-start with lags)
def _topo(acts: list[ActivityIn]) -> list[str]:
    codes = {a.code for a in acts}
    seen: dict[str, int] = {}
    order: list[str] = []
    by = {a.code: a for a in acts}

    def visit(c: str, stack: tuple):
        if seen.get(c) == 2:
            return
        if seen.get(c) == 1:
            raise ValidationFailed(f"Dependency loop: {' -> '.join(stack + (c,))}", code="PROGRAMME_LOOP")
        seen[c] = 1
        for p, _ in by[c].predecessors:
            if p not in codes:
                raise ValidationFailed(f"{c}: unknown predecessor {p}", code="PROGRAMME_UNKNOWN_PRED")
            visit(p, stack + (c,))
        seen[c] = 2
        order.append(c)
    for a in sorted(acts, key=lambda x: x.code):
        visit(a.code, ())
    return order


def cpm(acts: list[ActivityIn], dur: dict[str, int], *, use_ready: bool, floor_start: int = 0) -> dict:
    order = _topo(acts)
    by = {a.code: a for a in acts}
    es, ef = {}, {}
    for c in order:
        a = by[c]
        s = max([floor_start] + ([a.ready_wd] if use_ready else []) + [ef[p] + lag for p, lag in a.predecessors])
        es[c], ef[c] = s, s + dur[c]
    end = max(ef.values()) if ef else 0
    succ: dict[str, list] = {c: [] for c in by}
    for c in by:
        for p, lag in by[c].predecessors:
            succ[p].append((c, lag))
    ls, lf = {}, {}
    for c in reversed(order):
        f = min([ls[s] - lag for s, lag in succ[c]] + [end])
        lf[c], ls[c] = f, f - dur[c]
    flt = {c: ls[c] - es[c] for c in by}
    crit = [c for c in order if flt[c] == 0 and dur[c] > 0]
    return dict(es=es, ef=ef, ls=ls, lf=lf, float=flt, end=end, critical=crit)


# ------------------------------------------------------------------------------------------------ main run
@dataclass
class ActivityResult:
    code: str
    name: str
    status: str                       # OK | MISSING_NORM | NORM_NOT_APPROVED(provisional) | MISSING_QUANTITY | INFEASIBLE_RESOURCE
    labour_hours: Decimal
    crew_days: Decimal
    effective_crews: int
    unconstrained_wd: int
    dependency_es: int
    dependency_ef: int
    procurement_es: int
    procurement_ef: int
    resource_start: int | None
    resource_finish: int | None
    resource_delay_wd: int
    total_float_wd: int
    critical: bool
    resource_limited: bool
    problems: list[str]
    provisional: bool = False
    synthetic: bool = False


def run(acts: list[ActivityIn], prof: Profile, cal: WorkCalendar, *, allow_provisional: bool = False, progress: dict | None = None,
        status_wd: int = 0, actual_start: dict | None = None) -> dict:
    """Schedule `acts` for workforce `prof` on calendar `cal`. `progress` = {code: percent complete} at working-day index `status_wd` (re-forecast)."""
    if not acts:
        raise ValidationFailed("No activities.", code="NO_ACTIVITIES")
    if prof.productive_hours <= 0:
        raise ValidationFailed("Profile productive_hours must be > 0.", code="PROFILE_INCOMPLETE")
    progress = {k: D(str(v)) for k, v in (progress or {}).items()}
    actual_start = actual_start or {}
    by = {a.code: a for a in acts}
    gaps: list[dict] = []
    status: dict[str, str] = {}
    content: dict[str, Decimal] = {}
    hours: dict[str, Decimal] = {}
    problems: dict[str, list[str]] = {}
    eff: dict[str, int] = {}
    dur: dict[str, int] = {}
    pool = usable_pool(prof)
    for a in acts:
        st = "OK"
        n = a.norm
        if a.fixed_only:
            status[a.code], problems[a.code], content[a.code], hours[a.code], eff[a.code] = "OK", [], ZERO, ZERO, 1
            dur[a.code] = a.setup_days + a.post_days
            continue
        if n is None:
            st = "MISSING_NORM"
        elif a.quantity is None:
            st = "MISSING_QUANTITY"
        elif n.status != "Approved" and not allow_provisional:
            st = "MISSING_NORM"
            gaps.append(dict(code=a.code, kind="NORM_NOT_APPROVED", detail=f"norm {n.id} v{n.version} is '{n.status}'; excluded (no provisional scenario)"))
        cd, hr, pr = (ZERO, ZERO, [])
        if st == "OK":
            cd, hr, pr = crew_days_required(a, prof)
            if n.status != "Approved":
                st = "NORM_NOT_APPROVED"
                gaps.append(dict(code=a.code, kind="PROVISIONAL_NORM", detail=f"norm {n.id} v{n.version} is '{n.status}' (provisional scenario)"))
            if n.evidence_status != "verified":
                gaps.append(dict(code=a.code, kind="NORM_EVIDENCE_" + n.evidence_status.upper(), detail=f"norm {n.id} v{n.version}: evidence '{n.evidence_status}'"))
            lim = [r for r, c in n.crew.items() if pool.get(r, 0) < int(c)]
            if lim:
                st = "INFEASIBLE_RESOURCE"
                gaps.append(dict(code=a.code, kind="RESOURCE_UNAVAILABLE", detail=f"profile {prof.id} cannot field one crew: short of {sorted(lim)}"))
        elif st in ("MISSING_NORM", "MISSING_QUANTITY"):
            gaps.append(dict(code=a.code, kind=st, detail="no approved norm / quantity: duration cannot be calculated and is carried as 0 (effect: programme under-stated)"))
        status[a.code], problems[a.code] = st, pr
        content[a.code], hours[a.code] = cd, hr
        fr = prof.fronts_limit if prof.fronts_limit is not None else 10 ** 6
        eff[a.code] = max(1, min(a.crews, a.fronts, fr)) if st in ("OK", "NORM_NOT_APPROVED", "INFEASIBLE_RESOURCE") else 0
        rem = content[a.code] * (D(1) - progress.get(a.code, ZERO) / D(100))
        if st in ("OK", "NORM_NOT_APPROVED"):
            work = ceil_int(rem / eff[a.code] / day_output_per_crew(prof, D(1))) if rem > 0 else 0
            dur[a.code] = (a.setup_days if code_started(a.code, progress, actual_start) is False else 0) + work + (a.post_days if rem > 0 or progress.get(a.code, ZERO) < 100 else 0)
        else:
            dur[a.code] = 0
    # --- unconstrained / dependency / procurement CPM
    base = {c: dur[c] for c in dur}
    dep = cpm(acts, base, use_ready=False, floor_start=prof.mobilisation_wd)
    pro = cpm(acts, base, use_ready=True, floor_start=prof.mobilisation_wd)
    # --- resource-constrained daily simulation
    sim = _simulate(acts, prof, cal, status, content, eff, pool, pro, progress, status_wd, actual_start)
    dates = cal.working_dates(max(sim["end"], pro["end"], dep["end"], 1) + 1)
    res_end = sim["end"]
    out_acts: list[ActivityResult] = []
    for a in acts:
        c = a.code
        rs, rf = sim["start"].get(c), sim["finish"].get(c)
        delay = (rs - pro["es"][c] - (a.setup_days if status[c] in ("OK", "NORM_NOT_APPROVED") else 0)) if rs is not None else 0
        out_acts.append(ActivityResult(c, a.name, status[c], q2(hours[c]), q2(content[c]), eff[c], base[c], dep["es"][c], dep["ef"][c], pro["es"][c], pro["ef"][c],
                                       rs, rf, max(0, delay), pro["float"][c], c in pro["critical"], sim["limited"].get(c, False), problems[c],
                                       provisional=(status[c] == "NORM_NOT_APPROVED"), synthetic=bool(a.norm and a.norm.is_synthetic)))
    peak = max(sim["workers_by_day"].values(), default=0)
    cost = _cost(prof, sim, dates)
    n_days = max(res_end, 0)
    complete = not any(g["kind"] in ("MISSING_NORM", "MISSING_QUANTITY", "NORM_NOT_APPROVED", "PROVISIONAL_NORM", "RESOURCE_UNAVAILABLE") for g in gaps) and not sim["unfinished"]
    cal_days = ((dates[min(len(dates) - 1, max(n_days - 1, 0))] - cal.start).days + 1) if n_days else 0
    return dict(
        profile=dict(id=prof.id, name=prof.name, archetype=prof.archetype, pool=prof.pool, indirect=prof.indirect, shifts=prof.shifts,
                     usable_pool=pool, productive_hours=str(prof.productive_hours), is_synthetic=prof.is_synthetic, status=prof.status),
        calendar=cal.describe(), activities=out_acts, gaps=gaps,
        unconstrained_project_wd=max((r.unconstrained_wd for r in out_acts), default=0),
        dependency_constrained_wd=dep["end"], procurement_constrained_wd=pro["end"], resource_constrained_wd=res_end,
        working_days=res_end, calendar_days=cal_days,
        start_date=dates[0].isoformat() if res_end else None,
        finish_date=dates[min(len(dates) - 1, max(res_end - 1, 0))].isoformat() if res_end else None,
        critical_path=pro["critical"], resource_limited=[r.code for r in out_acts if r.resource_limited],
        peak_workers=peak, labour_hours=q2(sum((hours[c] for c in hours), ZERO)), indirect_headcount=sum(int(v) for v in prof.indirect.values()),
        schedulable=not sim["unfinished"], cost=cost, complete=complete, provisional=any(r.provisional for r in out_acts) or prof.status != "Approved",
        synthetic=any(r.synthetic for r in out_acts) or prof.is_synthetic, unfinished=sim["unfinished"],
        reforecast=dict(status_wd=status_wd) if progress else None,
        workers_by_day={str(k): v for k, v in sorted(sim["workers_by_day"].items())})


def code_started(code: str, progress: dict, actual_start: dict) -> bool:
    return progress.get(code, ZERO) > 0 or code in actual_start


def _simulate(acts, prof, cal, status, content, eff, pool, pro, progress, status_wd, actual_start) -> dict:
    by = {a.code: a for a in acts}
    run_codes = [a.code for a in acts if status[a.code] in ("OK", "NORM_NOT_APPROVED")]
    remaining = {c: content[c] * (D(1) - progress.get(c, ZERO) / D(100)) for c in run_codes}
    start: dict[str, int] = {}
    finish: dict[str, int] = {}
    work_done_day: dict[str, int] = {}
    limited: dict[str, bool] = {}
    workers_by_day: dict[int, int] = {}
    crew_use: dict[int, dict] = {}
    for a in acts:
        c = a.code
        pass
    in_progress: set[str] = set()
    pre_start: dict[str, int] = {}
    max_day = MAX_DAYS
    day = status_wd
    unfinished: list[str] = []
    pending = {a.code for a in acts}

    def preds_done(c) -> int | None:
        t = 0
        for p, lag in by[c].predecessors:
            if p not in finish:
                return None
            t = max(t, finish[p] + lag)
        return t

    dates = None
    while pending and day < max_day:
        if dates is None or day >= len(dates):
            dates = cal.working_dates(min(len(dates or []) + 600, 366 * 30) if dates else 600)
        factor = cal.day_factor(dates[day])
        pool_left = dict(pool)
        # resolve instantaneous (zero-content) activities whose predecessors are finished
        changed = True
        while changed:
            changed = False
            for c in sorted(pending):
                if (c in remaining and remaining[c] > 0) or status[c] == "INFEASIBLE_RESOURCE":
                    continue
                t = preds_done(c)
                if t is None:
                    continue
                s = max(t, by[c].ready_wd, prof.mobilisation_wd, status_wd)
                if progress.get(c, ZERO) >= 100 and c not in remaining:
                    s = min(s, status_wd)
                start[c] = s
                finish[c] = s + (by[c].post_days if progress.get(c, ZERO) < 100 and status[c] in ("OK", "NORM_NOT_APPROVED") else 0)
                pending.discard(c)
                changed = True
        # candidates for work today
        cand = []
        for c in sorted(pending):
            if c not in remaining or remaining[c] <= 0:
                continue
            if c in in_progress:
                cand.append((0, pro["lf"][c], by[c].priority, c))
                continue
            t = preds_done(c)
            if t is None:
                continue
            elig = max(t, by[c].ready_wd, prof.mobilisation_wd, status_wd)
            if c not in pre_start:
                if elig > day:
                    continue
                pre_start[c] = day
            skip_pre = code_started(c, progress, actual_start)
            if day < pre_start[c] + (0 if skip_pre else by[c].setup_days):
                continue
            cand.append((1, pro["lf"][c], by[c].priority, c))
        cand.sort()
        used_today = 0
        for _, _, _, c in cand:
            a = by[c]
            n = a.norm
            target = eff[c]
            fit = min([target] + [pool_left.get(r, 0) // int(k) for r, k in n.crew.items() if int(k) > 0])
            if fit < target:
                limited[c] = True
            if fit <= 0 or factor <= 0:
                continue
            for r, k in n.crew.items():
                pool_left[r] = pool_left.get(r, 0) - fit * int(k)
            used_today += fit * sum(int(v) for r, v in n.crew.items() if not r.startswith("eq:"))       # equipment keys ('eq:...') are not manpower
            if c not in start:
                start[c] = day
            in_progress.add(c)
            remaining[c] -= fit * day_output_per_crew(prof, factor)
            crew_use.setdefault(day, {})[c] = (fit, n.crew)
            if remaining[c] <= 0:
                remaining[c] = ZERO
                in_progress.discard(c)
                work_done_day[c] = day
                finish[c] = day + 1 + a.post_days
                pending.discard(c)
        workers_by_day[day] = used_today
        # stop when everything left is blocked forever (e.g. predecessor can never run)
        if day - status_wd > 1 and not cand and not in_progress and all(preds_done(c) is None for c in pending):
            break
        day += 1
    unfinished = sorted(pending)
    end = max(list(finish.values()) + [0])
    return dict(start=start, finish=finish, end=end, limited=limited, workers_by_day=workers_by_day, crew_use=crew_use, unfinished=unfinished)


def _cost(prof: Profile, sim: dict, dates: list[date]) -> dict:
    rc = prof.role_day_cost
    if not rc:
        return dict(computed=False, reason="no approved role day-cost on the profile: cost impact not computed", direct_labour=None, indirect_staff=None, total=None)
    gaps: set[str] = set()
    direct = ZERO
    for day, use in sim["crew_use"].items():
        for _c, (fit, crew) in use.items():
            for r, k in crew.items():
                if r.startswith("eq:"):          # equipment is priced as plant in the estimate, not as a staff day-cost here
                    continue
                if r in rc:
                    direct += D(str(rc[r])) * int(k) * fit
                else:
                    gaps.add(r)
    ind = ZERO
    span = sim["end"]
    for r, n in prof.indirect.items():
        if r in rc:
            ind += D(str(rc[r])) * int(n) * span
        else:
            gaps.add(r)
    return dict(computed=not gaps, direct_labour=q2(direct), indirect_staff=q2(ind), total=q2(direct + ind), role_cost_gaps=sorted(gaps),
                note="cost uses person-entered role day-costs; it is a planning comparison, not an estimate of price")
