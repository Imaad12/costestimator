from decimal import Decimal

import pytest

from app.core.errors import ValidationFailed
from app.estimators.rate_build import blended_labour_rate, build_labour, build_plant

LAB = {"monthly_base_wage": "1800", "allowances_monthly": "400", "accommodation_monthly": "300", "transport_monthly": "150",
       "employer_costs_monthly": "250", "normal_hours_per_month": "208", "overtime_multiplier": "1.5"}


def test_labour_hourly():
    b = build_labour(LAB)
    assert b.monthly_total == Decimal("2900") and b.hourly_cost == Decimal("2900") / Decimal("208")
    assert b.base_hourly == Decimal("1800") / Decimal("208")


def test_labour_overtime_premium_on_base_wage_only():
    # 25% of hours at overtime: premium = 0.25 * 0.5 * base_hourly
    base_h = Decimal("1800") / Decimal("208")
    expected = Decimal("2900") / Decimal("208") + Decimal("0.25") * Decimal("0.5") * base_h
    assert blended_labour_rate(LAB, "25") == expected
    assert blended_labour_rate(LAB, 0) == build_labour(LAB).hourly_cost
    bad = dict(LAB); del bad["overtime_multiplier"]
    with pytest.raises(ValidationFailed):
        blended_labour_rate(bad, "10")


def test_labour_requires_hours_and_wage():
    with pytest.raises(ValidationFailed):
        build_labour({"monthly_base_wage": "1000"})
    with pytest.raises(ValidationFailed):
        build_labour({"normal_hours_per_month": "208"})


def test_plant_day_basis_uses_supplied_calendar():
    p = build_plant({"hire_rate": "600", "hire_basis": "day", "hours_per_day": "8", "operator_hourly": "25", "fuel_litres_per_hour": "12",
                     "fuel_price_per_litre": "2", "maintenance_pct_of_hire": "5", "mobilisation_lump": "800", "demobilisation_lump": "800"})
    assert p.hire_per_hour == Decimal("75") and p.maintenance_per_hour == Decimal("3.75")
    assert p.hourly_cost_charged == Decimal("103.75") and p.fuel_per_hour == Decimal("24") and p.hourly_cost_full == Decimal("127.75")
    with pytest.raises(ValidationFailed) as e:
        build_plant({"hire_rate": "600", "hire_basis": "day"})        # no assumed 8 h day
    assert e.value.code == "PLANT_CALENDAR_REQUIRED"
    assert build_plant({"hire_rate": "26000", "hire_basis": "month", "hours_per_day": "10", "days_per_month": "26"}).hire_per_hour == Decimal("100")
    assert build_plant({"hire_rate": "7000", "hire_basis": "week", "hours_per_day": "10", "days_per_week": "7"}).hire_per_hour == Decimal("100")
