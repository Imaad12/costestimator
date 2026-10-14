"""Day-priced plant: working days vs calendar days, minimum hire, standby, mobilisation/demobilisation, programme delay and missing hire terms. SYNTHETIC; hand-worked values.

Fixture (tests/unit/test_time_allocation.py): crane 4 day x 500 = 2,000 ; forklift 5 day x 200 = 1,000 ; others 2,500 ; direct 5,500. Calendar Mon-Fri from Monday 2026-03-02."""
from __future__ import annotations

from decimal import Decimal as D

from app.estimators.estimate import compute_estimate
from app.reconciliation import engine as recon
from app.services import governed, indirects, plant_hire
from tests.conftest import COMMERCIAL, ESTIMATOR
from tests.unit.test_time_allocation import approve, proj  # noqa: F401


def tasks(db, pid, d1=5, d2=5):
    indirects.set_tasks(db, ESTIMATOR, pid, [dict(task_code="T1", name="Pipe work", duration_days=str(d1), cost_code="E.06"),
                                             dict(task_code="T2", name="Handover", duration_days=str(d2), predecessors="T1", cost_code="Z.99")])


def terms(db, pid, rid="R-CRN", code="CRANE", **kw):
    return approve(db, "plant_hire_terms", code, {"resource_id": rid, **kw}, pid)


def test_day_priced_plant_without_hire_terms_is_a_high_exception_that_blocks_the_gate(proj):
    db, pid = proj
    est = compute_estimate(db, pid)
    miss = {e.resource_id for e in est.direct.exceptions if e.code == "PLANT_TERMS_MISSING"}
    assert miss == {"R-CRN", "R-FRK"} and all(e.severity == "High" for e in est.direct.exceptions if e.code == "PLANT_TERMS_MISSING")
    assert not any(e.code == "PLANT_UNIT" for e in est.direct.exceptions)                                 # factor_unit='day' declared on the assembly line: the day basis is explicit
    gate = recon.final_gate(db, COMMERCIAL, pid)
    assert gate["blocked"] and any(b["rule_code"] == "SYSTEM_EXCEPTION" and "no approved hire terms" in (b["detail"] or b["title"]) for b in gate["blockers"])
    terms(db, pid, "R-CRN", "CRANE", min_hire_qty="1")
    terms(db, pid, "R-FRK", "FORK", min_hire_qty="1")
    assert not any(e.code == "PLANT_TERMS_MISSING" for e in compute_estimate(db, pid).direct.exceptions)


def test_minimum_hire_standby_mobilisation_and_demobilisation_are_separate_hand_checked_lines(proj):
    db, pid = proj
    terms(db, pid, "R-FRK", "FORK", min_hire_qty="1")
    # crane: charged 4 day ; minimum hire 10 -> top-up 6 x 500 = 3,000 ; standby 2 day at 50 % = 2 x 500 x 0.5 = 500 ; mobilisation 1 day + demobilisation 1 day at the full rate = 500 + 500
    terms(db, pid, "R-CRN", "CRANE", min_hire_qty="10", standby_qty="2", standby_pct_of_rate="50", mobilisation_qty="1", demobilisation_qty="1")
    est = compute_estimate(db, pid)
    by = {l.kind: l.amount for l in est.direct.lines if l.resource_id == "R-CRN"}
    assert by == {"plant": D("2000.00"), "plant_min_hire_top_up": D("3000.00"), "plant_standby": D("500.00"), "plant_mob_days": D("500.00"), "plant_demob_days": D("500.00")}
    assert est.direct.direct_cost_total == D("5500.00") + D("3000.00") + D("500.00") + D("500.00") + D("500.00")           # 10,000
    assert next(l for l in est.direct.lines if l.kind == "plant_mob_days").basis.startswith("mobilisation days 1 day at the full rate")


def test_working_days_and_calendar_days_are_different_and_the_window_comes_from_the_programme(proj):
    db, pid = proj
    tasks(db, pid)                                                                                          # T1 5 wd then T2 5 wd: Mon 2026-03-02 .. Fri 2026-03-13 = 10 working days, 12 calendar days
    terms(db, pid, "R-FRK", "FORK", min_hire_qty="1")
    terms(db, pid, "R-CRN", "CRANE", min_hire_qty="1", billing_basis="working_day", programme_tasks="T1, T2")
    r = next(x for x in plant_hire.plant_hire_report(db, pid)["rows"] if x["resource_id"] == "R-CRN")
    assert (r["window_start"], r["window_finish"], r["working_days"], r["calendar_days"], r["working_dates_in_window"]) == ("2026-03-02", "2026-03-13", D(10), 12, 10)
    assert r["required_billable_days"] == D(10) and r["billed_on_site_days"] == D(4) and r["difference"] == D(6) and r["exposure"] == D(3000) and r["status"] == "PRICED_BELOW_PROGRAMME_WINDOW"
    # the same window on a calendar-day contract bills 12 days: the difference grows (never "all hire days equal working days")
    terms(db, pid, "R-CRN", "CRANE", min_hire_qty="1", billing_basis="calendar_day", programme_tasks=["T1", "T2"])
    r = next(x for x in plant_hire.plant_hire_report(db, pid)["rows"] if x["resource_id"] == "R-CRN")
    assert r["required_billable_days"] == D(12) and r["difference"] == D(8) and r["exposure"] == D(4000)
    f = {(x["rule_code"], x["severity"]) for x in recon.get_run(db, recon.run_reconciliation(db, ESTIMATOR, pid)["run_id"])["findings"]}
    assert ("PLANT_HIRE_DAYS", "High") in f
    # matching it (BOQ quantity = 12 calendar days) clears the finding: nothing was adjusted for the user
    db.execute("UPDATE boq_items SET quantity='12' WHERE project_id=? AND item_key='CRN'", (pid,))
    r = next(x for x in plant_hire.plant_hire_report(db, pid)["rows"] if x["resource_id"] == "R-CRN")
    assert r["status"] == "MATCHES" and r["difference"] == 0


def test_programme_delay_extends_the_window_and_exposure(proj):
    db, pid = proj
    terms(db, pid, "R-FRK", "FORK", min_hire_qty="1")
    terms(db, pid, "R-CRN", "CRANE", min_hire_qty="1", billing_basis="calendar_day", programme_tasks=["T1", "T2"])
    tasks(db, pid, 5, 5)
    base = next(x for x in plant_hire.plant_hire_report(db, pid)["rows"] if x["resource_id"] == "R-CRN")
    tasks(db, pid, 8, 5)                                                                                    # T1 slips by 3 working days: 13 wd from Mon 03-02 -> Wed 03-18 = 17 calendar days
    late = next(x for x in plant_hire.plant_hire_report(db, pid)["rows"] if x["resource_id"] == "R-CRN")
    assert (base["calendar_days"], late["calendar_days"], late["window_finish"], late["working_days"]) == (12, 17, "2026-03-18", D(13))
    assert late["exposure"] - base["exposure"] == D(5) * D(500)


def test_terms_validation_and_unlinked_terms_are_reported_not_guessed(proj):
    db, pid = proj
    import pytest
    from app.core.errors import ValidationFailed
    for data in ({"resource_id": "R-CRN", "programme_tasks": ["T1"]}, {"resource_id": "R-CRN", "billing_basis": "fortnight"}, {"resource_id": "R-CRN", "standby_qty": "1"}):
        with pytest.raises(ValidationFailed):
            governed.propose(db, ESTIMATOR, "plant_hire_terms", "BAD", data, project_id=pid, source="s", is_synthetic=True)
    terms(db, pid, "R-CRN", "CRANE", min_hire_qty="1")
    terms(db, pid, "R-FRK", "FORK", min_hire_qty="1", billing_basis="working_day", programme_tasks=["T9"])
    rows = {x["resource_id"]: x for x in plant_hire.plant_hire_report(db, pid)["rows"]}
    assert rows["R-CRN"]["status"] == "NO_PROGRAMME_LINK" and rows["R-FRK"]["status"] == "PROGRAMME_UNAVAILABLE"
