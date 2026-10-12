"""Deterministic rate build-ups for labour and plant (pure functions, Decimal arithmetic).

No default wages or hire rates exist anywhere: every number comes from the component dict supplied by the user
and is stored on the rate record (components_json) for traceability.

Labour:   hourly_cost = (sum of monthly cost components) / normal_hours_per_month
          overtime premium applies to the base-wage portion only:
              base_hourly = monthly_base_wage / normal_hours_per_month
              blended = hourly_cost + ot_share * (ot_multiplier - 1) * base_hourly
Plant:    per-hour hire derived from the stated hire basis using the SUPPLIED calendar (hours/day, days/week, days/month);
          nothing is assumed.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..core.errors import ValidationFailed
from ..core.money import ZERO, D, D_opt, pct

LABOUR_MONTHLY_KEYS = ["monthly_base_wage", "allowances_monthly", "accommodation_monthly", "transport_monthly",
                       "employer_costs_monthly", "other_monthly"]


@dataclass
class LabourBuild:
    hourly_cost: Decimal
    base_hourly: Decimal
    monthly_total: Decimal
    normal_hours_per_month: Decimal
    ot_multiplier: Decimal | None


def build_labour(components: dict) -> LabourBuild:
    hrs = D_opt(components.get("normal_hours_per_month"))
    if hrs is None or hrs <= 0:
        raise ValidationFailed("Labour build-up requires normal_hours_per_month > 0.", code="LABOUR_HOURS_REQUIRED")
    base = D_opt(components.get("monthly_base_wage"))
    if base is None:
        raise ValidationFailed("Labour build-up requires monthly_base_wage.", code="LABOUR_BASE_REQUIRED")
    total = ZERO
    for k in LABOUR_MONTHLY_KEYS:
        v = D_opt(components.get(k))
        if v is not None:
            if v < 0:
                raise ValidationFailed(f"{k} cannot be negative.")
            total += v
    ot = D_opt(components.get("overtime_multiplier"))
    return LabourBuild(total / hrs, base / hrs, total, hrs, ot)


def blended_labour_rate(components: dict, overtime_share_pct: Decimal | str | None) -> Decimal:
    b = build_labour(components)
    share = pct(overtime_share_pct) if overtime_share_pct not in (None, "") else ZERO
    if share == 0:
        return b.hourly_cost
    if b.ot_multiplier is None:
        raise ValidationFailed("Overtime share given but the labour rate has no overtime_multiplier.",
                               code="OT_MULTIPLIER_MISSING")
    return b.hourly_cost + share * (b.ot_multiplier - 1) * b.base_hourly


@dataclass
class PlantBuild:
    hire_per_hour: Decimal
    operator_per_hour: Decimal
    fuel_per_hour: Decimal
    maintenance_per_hour: Decimal
    standby_pct: Decimal
    mobilisation: Decimal
    demobilisation: Decimal

    @property
    def hourly_cost_charged(self) -> Decimal:
        """Cost per CHARGED hour (hire + operator + maintenance)."""
        return self.hire_per_hour + self.operator_per_hour + self.maintenance_per_hour

    @property
    def hourly_cost_full(self) -> Decimal:
        return self.hourly_cost_charged + self.fuel_per_hour


def build_plant(components: dict) -> PlantBuild:
    basis = (components.get("hire_basis") or "hour").lower()
    hire = D_opt(components.get("hire_rate"))
    if hire is None:
        raise ValidationFailed("Plant build-up requires hire_rate.", code="PLANT_HIRE_REQUIRED")
    hpd = D_opt(components.get("hours_per_day"))
    dpw = D_opt(components.get("days_per_week"))
    dpm = D_opt(components.get("days_per_month"))

    def need(v, name):
        if v is None or v <= 0:
            raise ValidationFailed(f"Plant hire basis '{basis}' needs {name} (approved calendar value).",
                                   code="PLANT_CALENDAR_REQUIRED")
        return v

    if basis == "hour":
        per_hour = hire
    elif basis == "day":
        per_hour = hire / need(hpd, "hours_per_day")
    elif basis == "week":
        per_hour = hire / (need(hpd, "hours_per_day") * need(dpw, "days_per_week"))
    elif basis == "month":
        per_hour = hire / (need(hpd, "hours_per_day") * need(dpm, "days_per_month"))
    else:
        raise ValidationFailed(f"Unsupported hire_basis '{basis}'.")
    op = D_opt(components.get("operator_hourly")) or ZERO
    fuel = (D_opt(components.get("fuel_litres_per_hour")) or ZERO) * (D_opt(components.get("fuel_price_per_litre")) or ZERO)
    maint = per_hour * pct(components.get("maintenance_pct_of_hire") or 0)
    return PlantBuild(per_hour, op, fuel, maint, D(components.get("standby_pct") or 0),
                      D(components.get("mobilisation_lump") or 0), D(components.get("demobilisation_lump") or 0))
