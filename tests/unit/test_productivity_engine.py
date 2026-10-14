"""Productivity / crew / resource-constrained programme engine. Expected values are computed by hand in each test (SYNTHETIC inputs)."""
from datetime import date
from decimal import Decimal as D

import pytest

from app.core.errors import ValidationFailed
from app.estimators import productivity as p

CAL = p.WorkCalendar(date(2027, 1, 3), frozenset({6, 0, 1, 2, 3}), standard_hours=D(8), confirmed=True)       # Sun-Thu


def norm(basis="labour_hours_per_unit", value="2", crew=None, **kw):
    return p.Norm("N", 1, basis, D(value), crew or {"fitter": 2, "helper": 1}, **kw)


def prof(**kw):
    base = dict(id="P", name="p", pool={"fitter": 4, "helper": 2}, productive_hours=D(6))
    base.update(kw)
    return p.Profile(**base)


def act(code="A", q="1200", n=None, **kw):
    return p.ActivityIn(code, code, D(q), "m", n if n is not None else norm(), **kw)


def test_labour_hours_formula():
    # 1200 m x 2 h/m = 2400 h; crew of 3 x 6 productive h = 18 h per crew-day -> 133.33 crew-days -> 134 working days
    r = p.run([act()], prof(), CAL)
    a = r["activities"][0]
    assert a.labour_hours == D("2400.00") and a.crew_days == D("133.33") and a.unconstrained_wd == 134 and r["working_days"] == 134
    assert len(CAL.working_dates(134)) == 134


def test_work_fronts_limit_crews():
    two = p.run([act(crews=2, fronts=2)], prof(), CAL)["working_days"]     # 133.33 / 2 = 66.67 -> 67
    one = p.run([act(crews=2, fronts=1)], prof(), CAL)["working_days"]     # only one front -> 134
    assert two == 67 and one == 134


def test_crew_output_basis_does_not_reapply_labour_hours():
    n = norm("crew_output_per_crew_day", "25")
    r = p.run([act(q="500", n=n, crews=2, fronts=2)], prof(), CAL)          # 500/25 = 20 crew-days; 2 crews -> 10 days
    a = r["activities"][0]
    assert a.crew_days == D("20.00") and r["working_days"] == 10
    assert a.labour_hours == D("360.00")                                    # informational: 20 x 3 workers x 6 h


def test_double_counting_of_factors_is_flagged_and_ignored():
    n = norm("crew_output_per_crew_day", "25", includes_factors=True)
    f = (p.Factor("height", D("1.2"), "x", True),)
    r = p.run([act(q="500", n=n, factors=f)], prof(), CAL)
    assert r["activities"][0].crew_days == D("20.00") and any("DOUBLE_COUNT" in x for x in r["activities"][0].problems)
    r2 = p.run([act(q="500", n=norm("crew_output_per_crew_day", "25"), factors=f)], prof(), CAL)
    assert r2["activities"][0].crew_days == D("24.00")                      # factor applied once when the norm excludes it


def test_pool_limits_crews_and_flags_resource_limited():
    # pool allows floor(4/2)=2 fitter crews but only 2 helpers -> 2 crews; ask for 3
    r = p.run([act(q="1200", crews=3, fronts=3)], prof(), CAL)
    assert r["working_days"] == 67 and r["resource_limited"] == ["A"] and r["activities"][0].unconstrained_wd == 45     # 133.33/3 -> 44.4 -> 45
    assert r["resource_constrained_wd"] > r["dependency_constrained_wd"]


def test_attendance_and_availability_reduce_pool():
    r = p.run([act(crews=2, fronts=2)], prof(attendance=D("0.5")), CAL)    # usable fitters 2, helpers 1 -> one crew
    assert r["working_days"] == 134 and r["profile"]["usable_pool"] == {"fitter": 2, "helper": 1}


def test_overtime_shift_and_reduced_hours_capacity():
    ot = p.run([act(q="21", n=norm("crew_output_per_crew_day", "1"))], prof(overtime_hours=D(2), overtime_efficiency=D("0.5")), CAL)
    assert ot["working_days"] == 18                                         # 21 crew-days / (1 + 2*0.5/6 = 1.1667) = 18.0 -> 18
    ns = p.run([act(q="18", n=norm("crew_output_per_crew_day", "1"))], prof(shifts=2, night_efficiency=D("0.8")), CAL)
    assert ns["working_days"] == 10                                         # 18 / 1.8
    red = p.WorkCalendar(CAL.start, CAL.weekdays, frozenset(), D(8), ((date(2027, 1, 1), date(2027, 12, 31), D(6)),), confirmed=True)
    rr = p.run([act(q="12", n=norm("crew_output_per_crew_day", "1"))], prof(), red)
    assert rr["working_days"] == 16                                         # 12 / 0.75


def test_dependencies_procurement_and_float():
    a = act("A", "100", norm("crew_output_per_crew_day", "10"))              # 10 days
    b = act("B", "50", norm("crew_output_per_crew_day", "10"), predecessors=(("A", 0),), ready_wd=15)        # 5 days, material ready day 15
    c = act("C", "30", norm("crew_output_per_crew_day", "10"), predecessors=(("A", 2),))                       # 3 days after lag
    r = p.run([a, b, c], prof(pool={"fitter": 10, "helper": 5}), CAL)
    by = {x.code: x for x in r["activities"]}
    assert r["dependency_constrained_wd"] == 15 and r["procurement_constrained_wd"] == 20 and r["resource_constrained_wd"] == 20
    assert by["B"].resource_start == 15 and by["C"].resource_start == 12 and by["C"].total_float_wd == 5     # C ends day 15, project ends day 20
    assert r["critical_path"] == ["B"] and by["A"].total_float_wd == 5       # material arrival (day 15) drives B; A has 5 days of float


def test_resource_conflict_delays_second_activity_by_priority():
    n = norm("crew_output_per_crew_day", "10", crew={"fitter": 4, "helper": 2})
    a = act("A", "100", n, priority=1)
    b = act("B", "100", n, priority=2)
    r = p.run([a, b], prof(), CAL)             # only one crew of 4+2 exists: A first (10 d) then B (10 d)
    by = {x.code: x for x in r["activities"]}
    assert r["dependency_constrained_wd"] == 10 and r["resource_constrained_wd"] == 20
    assert by["A"].resource_finish == 10 and by["B"].resource_start == 10 and by["B"].resource_delay_wd == 10 and by["B"].resource_limited


def test_fixed_days_setup_curing():
    r = p.run([act("A", "100", norm("crew_output_per_crew_day", "10"), setup_days=2, post_days=3)], prof(), CAL)
    a = r["activities"][0]
    assert a.unconstrained_wd == 15 and r["working_days"] == 15 and a.resource_start == 2


def test_missing_and_unapproved_norms_are_gaps_not_zero_cost():
    miss = p.ActivityIn("A", "A", D("10"), "m", None)
    r = p.run([miss, act("B", "100", norm("crew_output_per_crew_day", "10"), predecessors=(("A", 0),))], prof(), CAL)
    assert not r["complete"] and any(g["kind"] == "MISSING_NORM" for g in r["gaps"])
    draft = norm("crew_output_per_crew_day", "10", status="Draft")
    r1 = p.run([act("A", "100", draft)], prof(), CAL)
    assert r1["activities"][0].status == "MISSING_NORM" and not r1["complete"] and r1["working_days"] == 0
    r2 = p.run([act("A", "100", draft)], prof(), CAL, allow_provisional=True)
    assert r2["working_days"] == 10 and r2["provisional"] and not r2["complete"]


def test_zero_duration_activity_and_zero_quantity():
    r = p.run([act("A", "0", norm("crew_output_per_crew_day", "10")), act("B", "10", norm("crew_output_per_crew_day", "10"), predecessors=(("A", 0),))], prof(), CAL)
    by = {x.code: x for x in r["activities"]}
    assert by["A"].unconstrained_wd == 0 and by["B"].resource_start == 0 and r["working_days"] == 1


def test_infeasible_role_and_loop_detected():
    n = norm(crew={"welder": 1})
    r = p.run([act("A", "10", n), act("B", "10", norm(), predecessors=(("A", 0),))], prof(), CAL)
    assert any(g["kind"] == "RESOURCE_UNAVAILABLE" for g in r["gaps"]) and "A" in r["unfinished"] and not r["complete"]
    with pytest.raises(ValidationFailed) as e:
        p.run([act("A", "1", predecessors=(("B", 0),)), act("B", "1", predecessors=(("A", 0),))], prof(), CAL)
    assert e.value.code == "PROGRAMME_LOOP"


def test_reforecast_from_progress():
    a = act("A", "100", norm("crew_output_per_crew_day", "10"))              # 10 days
    r = p.run([a], prof(), CAL, progress={"A": 60}, status_wd=8)               # 4 crew-days left from day 8
    assert r["working_days"] == 12 and r["reforecast"]["status_wd"] == 8


def test_doubling_workforce_does_not_halve_programme():
    a = act("A", "100", norm("crew_output_per_crew_day", "10", crew={"fitter": 2, "helper": 1}))
    b = act("B", "100", norm("crew_output_per_crew_day", "10"), predecessors=(("A", 0),))
    small = p.run([a, b], prof(pool={"fitter": 2, "helper": 1}), CAL)["working_days"]
    big = p.run([a, b], prof(pool={"fitter": 4, "helper": 2}), CAL)["working_days"]
    assert small == 20 and big == 20            # sequential and single-front: more people change nothing
