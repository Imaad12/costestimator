"""Programme service: task storage with relationship syntax, calendar from a governed parameter, time-phased loading and man-hours (hand-calculated)."""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.core.errors import ValidationFailed
from app.estimators import loading
from app.services import governed, indirects, programme, wbs
from tests.conftest import COMMERCIAL, ESTIMATOR
from tests.helpers import build_mini


def test_loading_spread_is_exact_and_fractional_edges_hand_checked():
    s = loading.spread(D("1.5"), D("4"), D(100))
    assert s == {1: D(20), 2: D(40), 3: D(40)} and sum(s.values()) == 100
    t = loading.spread(D("0.3"), D("0.7"), D(10))                       # inside one day -> all on that day
    assert t == {0: D(10)}
    assert loading.spread(D(3), D(3), D(7)) == {3: D(7)}                 # milestone
    third = loading.spread(D(0), D(3), D(1))
    assert sum(third.values()) == D(1)                                    # remainder lands on the last day: exact total


def test_histogram_unscheduled_and_peak():
    h = loading.histogram([loading.Load("L", "T1", D(10)), loading.Load("L", None, D(4)), loading.Load("M", "T1", D(2))],
                          {"T1": (D(0), D(2))}, loading.block_bucketer(1))
    assert h["series"]["L"] == {"WD0001-0001": D(5), "WD0002-0002": D(5)} and h["unscheduled"] == {"L": D(4)}
    assert h["peaks"]["M"]["qty"] == D(1) and h["peak_all"][1] == D(6)


@pytest.fixture()
def proj(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    wbs.add_node(seeded, ESTIMATOR, pid, "A1", "Area 1"); wbs.add_node(seeded, ESTIMATOR, pid, "A2", "Area 2")
    wbs.assign_items(seeded, ESTIMATOR, pid, {"1.1": "A1", "1.2": "A2"})
    indirects.set_tasks(seeded, ESTIMATOR, pid, [
        {"task_code": "T1", "name": "Area 1 works", "duration_days": "4", "wbs_code": "A1", "cost_code": "C"},
        {"task_code": "T2", "name": "Area 2 works", "duration_days": "5", "predecessors": "T1", "wbs_code": "A2", "cost_code": "C"}])
    return pid


def test_task_storage_syntax_and_validation(seeded, proj):
    indirects.set_tasks(seeded, ESTIMATOR, proj, [{"task_code": "A", "name": "a", "duration_days": "3"},
                                                    {"task_code": "B", "name": "b", "duration_days": "2", "predecessors": ["A-SS+1"]}])
    rep = programme.schedule_report(seeded, proj)
    assert rep["project_working_days"] == D(3) and {t["task_code"]: (t["es"], t["ef"]) for t in rep["tasks"]}["B"] == (D(1), D(3))
    with pytest.raises(ValidationFailed):
        indirects.set_tasks(seeded, ESTIMATOR, proj, [{"task_code": "A", "name": "a", "duration_days": "3", "predecessors": "B"},
                                                        {"task_code": "B", "name": "b", "duration_days": "2", "predecessors": "A"}])
    with pytest.raises(ValidationFailed):
        indirects.set_tasks(seeded, ESTIMATOR, proj, [{"task_code": "A", "name": "a", "duration_days": "3", "wbs_code": "NOPE"}])
    with pytest.raises(ValidationFailed):                              # a date constraint needs an approved calendar
        indirects.set_tasks(seeded, ESTIMATOR, proj, [{"task_code": "A", "name": "a", "duration_days": "3", "snet": "2026-04-01"}])
        programme.schedule_report(seeded, proj)


def _calendar(db, pid):
    c = governed.propose(db, ESTIMATOR, "calendar", "PROJECT", {"start_date": "2026-03-01", "work_weekdays": [6, 0, 1, 2, 3], "holidays": []},
                         project_id=pid, source="Contract programme requirements (test)", submit=True)
    governed.approve(db, COMMERCIAL, c)


def test_manhours_by_craft_wbs_division_hand_calculated(seeded, proj):
    mh = programme.manhours_report(seeded, proj)
    # 10 m3 x 2 h = 20 h (item 1.1) ; 5 m3 x 2 h = 10 h (item 1.2)
    assert mh["total_hours"] == D(30) and mh["by_resource"] == {"DEMO-LAB-001": D(30)}
    assert mh["by_wbs"] == {"A1": D(20), "A2": D(10)} and mh["by_division"] == {"C": D(30)} and mh["tie_out"]


def test_loading_blocks_without_calendar_and_weeks_with_calendar(seeded, proj):
    r = programme.loading_report(seeded, proj, measure="labour_hours", period="block", block_days=5)
    # T1 days 0-3 at 5 h/day (20 h) ; T2 days 4-8 at 2 h/day (10 h)  => block 1 = 20 + 2 ; block 2 = 8
    assert r["series"]["DEMO-LAB-001"] == {"WD0001-0005": D(22), "WD0006-0010": D(8)} and r["tie_out"] and r["unscheduled_total"] == 0
    assert r["peaks"]["DEMO-LAB-001"] == {"bucket": "WD0001-0005", "qty": D(22)}
    _calendar(seeded, proj)                                            # work week Sun-Thu, entered by the user
    w = programme.loading_report(seeded, proj, measure="labour_hours", period="week")
    # day0 = Sun 1 Mar (ISO W09) ; days1-4 = Mon 2..Thu 5 Mar (W10) ; day5 = Sun 8 Mar (W10) ; days6-8 = Mon 9..Wed 11 Mar (W11)
    assert w["series"]["DEMO-LAB-001"] == {"2026-W09": D(5), "2026-W10": D(19), "2026-W11": D(6)} and w["tie_out"]
    m = programme.loading_report(seeded, proj, measure="cost", period="month")
    assert set(m["series"]) == {"labour", "material"} and m["tie_out"] and list(m["series"]["labour"]) == ["2026-03"]
    rep = programme.schedule_report(seeded, proj)
    assert rep["tasks"][0]["start_date"] == "2026-03-01" and rep["tasks"][1]["finish_date"] == "2026-03-11"


def test_untied_quantities_are_reported_not_smeared(seeded, proj):
    indirects.set_tasks(seeded, ESTIMATOR, proj, [{"task_code": "X", "name": "Unscoped task", "duration_days": "3"}])      # declares no scope
    r = programme.loading_report(seeded, proj, measure="labour_hours", period="block")
    assert r["scheduled_total"] == 0 and r["unscheduled_total"] == D(30) and r["tie_out"]


def test_equally_specific_tasks_share_in_proportion_to_duration(seeded, proj):
    indirects.set_tasks(seeded, ESTIMATOR, proj, [{"task_code": "P", "name": "p", "duration_days": "1", "cost_code": "C"},
                                                    {"task_code": "Q", "name": "q", "duration_days": "3", "cost_code": "C"}])
    r = programme.loading_report(seeded, proj, measure="labour_hours", period="block", block_days=1)
    s = r["series"]["DEMO-LAB-001"]                                    # 30 h : P gets 7.5 h on day 1 ; Q gets 22.5 h over 3 days (7.5/day) -> day1 = 15
    assert s["WD0001-0001"] == D("15") and s["WD0002-0002"] == D("7.5") and r["tie_out"]
    # a more specific task wins over a general one
    indirects.set_tasks(seeded, ESTIMATOR, proj, [{"task_code": "G", "name": "general", "duration_days": "2", "cost_code": "C"},
                                                    {"task_code": "S", "name": "specific", "duration_days": "2", "predecessors": "G", "cost_code": "C.01"}])
    r2 = programme.loading_report(seeded, proj, measure="labour_hours", period="block", block_days=2)
    assert r2["series"]["DEMO-LAB-001"] == {"WD0003-0004": D(30)}
