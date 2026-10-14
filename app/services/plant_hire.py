"""Day-priced plant: billable days against the programme hire window.

For every approved `plant_hire_terms` that names `programme_tasks` and a `billing_basis`, the on-site window is READ FROM THE PROGRAMME (earliest start to latest finish of those
activities, on the approved calendar). Working days (the programme's working-day count) and calendar days (every date from the first start to the last finish, including
non-working days) are different quantities; the contract's billing basis picks the one that is billable. The result is compared with what the estimate actually charges
(BOQ plant quantity, minimum-hire top-up). Mobilisation, demobilisation and standby are separate terms and never part of the on-site count.
Nothing is adjusted silently: a difference is reported with its exposure and becomes a reconciliation finding."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from ..core.money import ZERO, D
from ..database import Database
from . import governed, programme


def plant_hire_report(db: Database, project_id: str, *, est=None, include_unapproved: bool = False) -> dict:
    from ..estimators.estimate import compute_estimate
    est = est or compute_estimate(db, project_id, include_unapproved=include_unapproved)
    terms = governed.effective(db, project_id, "plant_hire_terms", include_unapproved=include_unapproved)
    cal = programme.calendar_for(db, project_id, include_unapproved)
    try:
        sched = programme.schedule_report(db, project_id, include_unapproved=include_unapproved)
        tasks = {t["task_code"]: t for t in sched["tasks"]}
    except Exception:
        sched, tasks = None, {}
    rows = []
    for p in terms:
        d = p["data"]
        rid = d["resource_id"]
        lines = [l for l in est.direct.lines if l.kind == "plant" and l.resource_id == rid and l.amount is not None]
        if not lines:
            continue
        unit = lines[0].unit
        rate = lines[0].rate or ZERO
        charged = sum((l.quantity or ZERO for l in lines), ZERO)
        minq = D(d.get("min_hire_qty") or "0")
        row = dict(terms=p["code"], version=p["version"], resource_id=rid, unit=unit, rate=rate, billing_basis=d.get("billing_basis"), programme_tasks=d.get("programme_tasks") or [],
                   charged_qty=charged, min_hire_qty=minq, min_hire_top_up=max(ZERO, minq - charged), standby_qty=D(d.get("standby_qty") or "0"),
                   standby_pct_of_rate=d.get("standby_pct_of_rate"), mobilisation_qty=D(d.get("mobilisation_qty") or "0"), demobilisation_qty=D(d.get("demobilisation_qty") or "0"),
                   status="NO_PROGRAMME_LINK", problems=[])
        if not row["programme_tasks"]:
            row["problems"].append("terms name no programme activities: the on-site window is not traceable to the programme (the approved terms are the only basis)")
            rows.append(row)
            continue
        if unit != "day":
            row["status"] = "UNIT_NOT_SUPPORTED"
            row["problems"].append(f"plant is priced per '{unit}': billable-day comparison supports day-priced plant only")
            rows.append(row)
            continue
        missing = [t for t in row["programme_tasks"] if t not in tasks]
        if missing or cal is None or sched is None:
            row["status"] = "PROGRAMME_UNAVAILABLE"
            row["problems"].append(f"programme tasks {missing or ''} or the approved calendar are not available")
            rows.append(row)
            continue
        es = min(D(str(tasks[t]["es"])) for t in row["programme_tasks"])
        ef = max(D(str(tasks[t]["ef"])) for t in row["programme_tasks"])
        start, finish = programme.programme.task_dates(cal, es, ef)
        working = ef - es
        cal_days = (finish - start).days + 1
        wd_dates = sum(1 for i in range(cal_days) if cal.is_working(start + timedelta(days=i)))
        required = working if d["billing_basis"] == "working_day" else Decimal(cal_days)
        billed_on_site = max(charged, minq)
        diff = required - billed_on_site
        row.update(window_start=start.isoformat(), window_finish=finish.isoformat(), working_days=working, working_dates_in_window=wd_dates, calendar_days=cal_days,
                   required_billable_days=required, billed_on_site_days=billed_on_site, difference=diff,
                   exposure=(diff * rate if diff > 0 else ZERO),
                   status="MATCHES" if diff == 0 else ("PRICED_BELOW_PROGRAMME_WINDOW" if diff > 0 else "PRICED_ABOVE_PROGRAMME_WINDOW"))
        if diff != 0:
            row["problems"].append(f"{d['billing_basis']} basis over {start}..{finish} needs {required} day(s); the estimate bills {billed_on_site} (difference {diff})")
        rows.append(row)
    return dict(project_id=project_id, rows=rows, mismatches=[r for r in rows if r["status"] in ("PRICED_BELOW_PROGRAMME_WINDOW", "PRICED_ABOVE_PROGRAMME_WINDOW")],
                note="Working days and calendar days are different: a calendar-day contract bills every day on site incl. non-working days. Nothing is changed by this report.",
                estimate_state=est.state)
