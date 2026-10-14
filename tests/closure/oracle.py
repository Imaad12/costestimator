"""Independent test oracle for the closure scenario.

Deliberately written WITHOUT importing app.estimators.productivity: separate arithmetic (fractions), a recursive longest-path CPM and a plain date loop for the calendar. A disagreement
with the application is a finding to explain, never something to hide by changing an expected value.
"""
from __future__ import annotations

import json
import math
from datetime import date, timedelta
from fractions import Fraction


def crew_days_and_hours(basis: str, value: str, qty: str, crew_size: int, productive_hours: str) -> tuple[Fraction, Fraction]:
    """(crew-days, labour-hours). labour_hours_per_unit: hours = Q x norm; crew-days = hours / (productive hours x crew size). crew_output_per_crew_day: crew-days = Q / norm."""
    q, v, ph = Fraction(qty), Fraction(value), Fraction(productive_hours)
    if basis == "labour_hours_per_unit":
        h = q * v
        return h / (ph * crew_size), h
    cd = q / v
    return cd, cd * crew_size * ph


def ceil_frac(x: Fraction) -> int:
    return math.ceil(x)


def activity_model(db, project_id: str, profile_row: dict) -> dict:
    """Per activity: required crew-days, labour-hours, effective crews, unconstrained working days (fixed days included), procurement ready index."""
    out = {}
    ph = profile_row["productive_hours_per_shift"]
    for a in db.all("SELECT * FROM work_activities WHERE project_id=? ORDER BY pk", (project_id,)):
        fd = json.loads(a["fixed_days_json"])
        pre = int(fd.get("mobilisation", 0)) + int(fd.get("setup", 0))
        post = int(fd.get("curing", 0)) + int(fd.get("testing", 0)) + int(fd.get("inspection", 0))
        crews = min(a["crews"], a["work_fronts"], profile_row["work_fronts"] or 10 ** 6)
        if fd.get("fixed_only") or not a["norm_id"]:
            out[a["code"]] = dict(crew_days=Fraction(0), hours=Fraction(0), crews=crews, dur=pre + post, preds=a["predecessors"], pre=pre, post=post, crew=None, fixed=True)
            continue
        n = db.one("SELECT * FROM productivity_norms WHERE id=? AND status='Approved' ORDER BY version DESC LIMIT 1", (a["norm_id"],))
        b = db.one("SELECT quantity FROM boq_items WHERE project_id=? AND item_key=?", (project_id, a["boq_item_key"]))
        crew = json.loads(n["crew_json"])
        size = sum(crew.values())
        cd, h = crew_days_and_hours(n["basis"], n["value"], b["quantity"], size, ph)
        work = ceil_frac(cd / crews) if cd > 0 else 0
        out[a["code"]] = dict(crew_days=cd, hours=h, crews=crews, dur=pre + work + post, preds=a["predecessors"], pre=pre, post=post, crew=crew, fixed=False)
    return out


def parse_preds(s: str) -> list[tuple[str, int]]:
    out = []
    for p in (s or "").split(","):
        p = p.strip()
        if p:
            code, _, lag = p.partition("+")
            out.append((code, int(lag or 0)))
    return out


def longest_path(model: dict, ready: dict | None = None, start_floor: int = 0) -> tuple[dict, dict]:
    """Recursive memoised earliest-start / earliest-finish with FS+lag and optional material-ready indices. Returns (ES, EF)."""
    ready = ready or {}
    es, ef = {}, {}

    def go(c: str) -> int:
        if c in ef:
            return ef[c]
        s = max([start_floor, ready.get(c, 0)] + [go(p) + lag for p, lag in parse_preds(model[c]["preds"])])
        es[c], ef[c] = s, s + model[c]["dur"]
        return ef[c]
    for c in model:
        go(c)
    return es, ef


def critical_path(model: dict, es: dict, ef: dict) -> list[str]:
    end = max(ef.values())
    succ = {c: [] for c in model}
    for c in model:
        for p, lag in parse_preds(model[c]["preds"]):
            succ[p].append((c, lag))
    lf: dict[str, int] = {}

    def back(c):
        if c in lf:
            return lf[c]
        lf[c] = min([back(s) - model[s]["dur"] - lag for s, lag in succ[c]] + [end]) if succ[c] else end
        return lf[c]
    for c in model:
        back(c)
    return [c for c in model if lf[c] - model[c]["dur"] - es[c] == 0 and model[c]["dur"] > 0]


def working_dates(start: date, weekdays: set[int], holidays: set[date], shutdowns: list[tuple[date, date]], n: int) -> list[date]:
    out, d = [], start
    while len(out) < n:
        sd = any(a <= d <= b for a, b in shutdowns)
        if d.weekday() in weekdays and d not in holidays and not sd:
            out.append(d)
        d += timedelta(days=1)
    return out


def calendar_data(db, project_id: str) -> dict:
    r = db.one("SELECT data_json FROM governed_params WHERE kind='calendar' AND (project_id=? OR project_id IS NULL) AND status='Approved' ORDER BY id DESC LIMIT 1", (project_id,))
    return json.loads(r["data_json"])


def role_lower_bound_days(model: dict, role_capacity: dict) -> int:
    """Work-conserving lower bound on the project duration from any single role: total crew-days x head-count per crew / (head-count available per day)."""
    need: dict[str, Fraction] = {}
    for m in model.values():
        if m["fixed"] or not m["crew"]:
            continue
        for r, k in m["crew"].items():
            need[r] = need.get(r, Fraction(0)) + m["crew_days"] * k
    return max((math.ceil(v / role_capacity[r]) for r, v in need.items() if role_capacity.get(r)), default=0)


def quote_totals(rates: dict, qty: dict) -> str:
    return str(sum(Fraction(rates[k]) * qty[k] for k in qty))


def plant_window_working_days(start: date, finish: date, weekdays: set[int], holidays: set[date], shutdowns: list[tuple[date, date]]) -> tuple[int, int]:
    """(working days, calendar days) between two dates inclusive."""
    n = 0
    d = start
    while d <= finish:
        if d.weekday() in weekdays and d not in holidays and not any(a <= d <= b for a, b in shutdowns):
            n += 1
        d += timedelta(days=1)
    return n, (finish - start).days + 1
