from decimal import Decimal

import pytest

from app.core.errors import ValidationFailed
from app.estimators.duration import cpm, days_to_months, labour_derived_months
from app.estimators.indirect import compute_indirects


def it(code, method, amount, qty="1", status="Approved", **kw):
    d = dict(code=code, category="cat", description=f"{code} item", method=method, amount=amount, quantity=qty, allocation_method="pro_rata_direct",
             allocation_target=None, status=status, included_in_subcontract=0, duration_override_months=None)
    d.update(kw)
    return d


def run(items, **kw):
    base = dict(direct_cost_total=Decimal("1000000"), duration_months=Decimal("10"), duration_status="Approved",
                working_days_per_month=Decimal("26"), working_days_per_week=Decimal("6"))
    base.update(kw)
    return compute_indirects(items, **base)


def test_methods_hand_calculated():
    r = run([it("A", "fixed", "5000", "2"), it("B", "percent_of_direct", "0.5"), it("C", "per_month", "20000", "2"),
             it("D", "per_week", "1000", "1"), it("E", "per_day", "300", "2")])
    got = {l.code: l.amount for l in r.lines}
    assert got["A"] == Decimal("10000.00")
    assert got["B"] == Decimal("5000.00")                       # 0.5% x 1,000,000
    assert got["C"] == Decimal("400000.00")                     # 20,000 x 2 x 10
    assert got["D"] == Decimal("43333.33")                      # 1000 x 10 x 26/6
    assert got["E"] == Decimal("156000.00")                     # 300 x 2 x 10 x 26
    assert r.total == sum(got.values()) and r.resolved


def test_duration_not_approved_blocks_duration_costs_but_not_fixed():
    r = run([it("A", "per_month", "100"), it("B", "fixed", "50")], duration_status="Pending Review")
    got = {l.code: l.amount for l in r.lines}
    assert got["A"] is None and got["B"] == Decimal("50.00")
    assert any(e.code == "DURATION_NOT_APPROVED" for e in r.exceptions) and not r.resolved


def test_unapproved_and_missing_amount_never_zero():
    r = run([it("A", "fixed", "10", status="Draft"), it("B", "fixed", None)])
    assert all(l.amount is None for l in r.lines) and r.total == 0 and not r.resolved
    r2 = run([it("A", "fixed", "10", status="Draft")], include_unapproved=True)
    assert r2.lines[0].amount == Decimal("10.00") and "UNAPPROVED_USED_PRELIMINARY" in r2.lines[0].flags


def test_included_in_subcontract_excluded_to_avoid_double_count():
    r = run([it("S", "per_month", "6000", included_in_subcontract=1)])
    assert r.lines[0].amount == 0 and r.lines[0].excluded_reason and r.resolved and r.total == 0


def test_calendar_missing_flags():
    r = run([it("W", "per_week", "10")], working_days_per_week=None)
    assert r.lines[0].amount is None and any(e.code == "CALENDAR_MISSING" for e in r.exceptions)


def test_cpm():
    res = cpm([dict(task_code="A", duration_days="10", predecessors=[]), dict(task_code="B", duration_days="20", predecessors=["A"]),
               dict(task_code="C", duration_days="5", predecessors=["A"]), dict(task_code="D", duration_days="7", predecessors=["B", "C"])])
    assert res.project_days == Decimal("37") and res.critical_path == ["A", "B", "D"]
    assert days_to_months(Decimal("260"), Decimal("26")) == Decimal("10")
    with pytest.raises(ValidationFailed) as e:
        cpm([dict(task_code="A", duration_days="1", predecessors=["B"]), dict(task_code="B", duration_days="1", predecessors=["A"])])
    assert e.value.code == "SCHEDULE_CYCLE"
    with pytest.raises(ValidationFailed):
        cpm([dict(task_code="A", duration_days="1", predecessors=["Z"])])
    with pytest.raises(ValidationFailed):
        days_to_months(Decimal(10), Decimal(0))


def test_labour_derived_duration_is_a_formula():
    assert labour_derived_months(Decimal("52000"), Decimal("20"), Decimal("10"), Decimal("26")) == Decimal("10")
