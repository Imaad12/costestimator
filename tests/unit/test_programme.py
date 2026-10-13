"""Programme engine: relationship types, lags, float, constraints, calendar dates. Expected values worked out by hand (SYNTHETIC durations)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest

from app.core.errors import ValidationFailed
from app.estimators.programme import Calendar, Link, Task, calendar_from_param, parse_predecessors, schedule, task_dates


def test_four_relationship_types_forward_and_backward_by_hand():
    #  A 0-5 ; B FS A 5-8 ; C SS(A)+2 2-6 ; D FS B, FF C+1 => ES 8 EF 10
    r = schedule([Task("A", D(5)), Task("B", D(3), [Link("A")]), Task("C", D(4), [Link("A", "SS", D(2))]),
                  Task("D", D(2), [Link("B"), Link("C", "FF", D(1))])])
    t = r.tasks
    assert (t["A"].es, t["A"].ef) == (0, 5) and (t["B"].es, t["B"].ef) == (5, 8) and (t["C"].es, t["C"].ef) == (2, 6) and (t["D"].es, t["D"].ef) == (8, 10)
    assert r.project_days == 10 and r.critical_path == ["A", "B", "D"]
    assert (t["C"].ls, t["C"].lf, t["C"].total_float, t["C"].free_float) == (5, 9, 3, 3)       # LF_C <= LF_D - 1 = 9 ; free float = EF_D - (EF_C+1) = 3
    assert not t["C"].critical and t["B"].total_float == 0


def test_start_to_finish_and_negative_lag_lead():
    # E 0-6 ; F SF(E)+1: EF_F >= ES_E+1 = 1 => ES_F = max(0, 1-3) = 0 ; G FS(E) lag -2 (lead): ES_G = 6-2 = 4
    r = schedule([Task("E", D(6)), Task("F", D(3), [Link("E", "SF", D(1))]), Task("G", D(2), [Link("E", "FS", D(-2))])])
    assert r.tasks["F"].es == 0 and r.tasks["F"].ef == 3 and r.tasks["G"].es == 4 and r.tasks["G"].ef == 6
    assert r.project_days == 6 and r.tasks["F"].total_float == 3


def test_constraints_and_negative_float():
    r = schedule([Task("A", D(5)), Task("B", D(3), [Link("A")], fnlt=D(7))])          # finishes 8 but must finish by 7 => float -1
    assert r.tasks["B"].total_float == -1 and r.negative_float == ["B", "A"] or r.negative_float == ["A", "B"]
    r2 = schedule([Task("A", D(2), snet=D(10))])                                        # start no earlier than day 10
    assert r2.tasks["A"].es == 10 and r2.project_days == 12


def test_cycle_unknown_duplicate_negative_duration_rejected():
    with pytest.raises(ValidationFailed) as e:
        schedule([Task("A", D(1), [Link("B")]), Task("B", D(1), [Link("A")])])
    assert e.value.code == "SCHEDULE_CYCLE"
    with pytest.raises(ValidationFailed):
        schedule([Task("A", D(1), [Link("X")])])
    with pytest.raises(ValidationFailed):
        schedule([Task("A", D(1)), Task("A", D(2))])
    with pytest.raises(ValidationFailed):
        schedule([Task("A", D(-1))])
    with pytest.raises(ValidationFailed):
        schedule([Task("A", D(1), [Link("A")])])


def test_parse_predecessors_handles_codes_with_dashes_and_types():
    known = {"A", "B-1", "C", "D"}
    ls = parse_predecessors("A, B-1, C-SS+2, D FF-1, A-FS", known)
    assert [(l.pred, l.type, l.lag) for l in ls] == [("A", "FS", 0), ("B-1", "FS", 0), ("C", "SS", 2), ("D", "FF", -1), ("A", "FS", 0)]
    with pytest.raises(ValidationFailed):
        parse_predecessors("Z", known)
    assert [l.text() for l in ls[:4]] == ["A", "B-1", "CSS+2", "DFF-1"]


def test_calendar_dates_skip_non_working_days_and_holidays():
    # start Sun 2026-03-01; KSA-style Sun-Thu week is the USER's input here (0=Mon): Sun=6, Mon..Thu=0..3
    cal = calendar_from_param({"start_date": "2026-03-01", "work_weekdays": [6, 0, 1, 2, 3], "holidays": ["2026-03-04"]})
    assert cal.working_date(0) == date(2026, 3, 1) and cal.working_date(3) == date(2026, 3, 5)          # Wed 4th is a holiday
    assert cal.working_date(5) == date(2026, 3, 9)                                                    # Fri/Sat skipped
    s, f = task_dates(cal, D(0), D(5))
    assert (s, f) == (date(2026, 3, 1), date(2026, 3, 8))                                             # 5 working days: 1,2,3,5,8
    assert task_dates(cal, D(5), D(5)) == (date(2026, 3, 9), date(2026, 3, 9))                         # milestone
    assert cal.offset_of(date(2026, 3, 9)) == 5
    with pytest.raises(ValidationFailed):
        cal.offset_of(date(2026, 2, 1))
