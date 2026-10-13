"""Employer-side statutory / mobilisation labour cost components and workforce-mix checks. Pure.

All rules (levies, social-insurance rates, end-of-service accruals, visa/iqama costs ...) are supplied by the company and approved as governed parameters; the
software contains none. basis: pct_of_base_wage | per_head_month | per_head_year | per_head_once (amortised over the contract months)."""
from __future__ import annotations

from decimal import Decimal

from ..core.errors import ValidationFailed
from ..core.money import ZERO, D

BASES = ("pct_of_base_wage", "per_head_month", "per_head_year", "per_head_once")


def statutory_monthly(base_wage: Decimal, rules: list[dict], group: str, contract_months: Decimal | None) -> dict:
    """rules: [{code, name, basis, value, applies_to: 'all'|group}] (approved only). Returns monthly total and the breakdown."""
    total, rows = ZERO, []
    for r in rules:
        if r["applies_to"] not in ("all", group):
            continue
        v, b = D(r["value"]), r["basis"]
        if b == "pct_of_base_wage":
            m = base_wage * v / 100
        elif b == "per_head_month":
            m = v
        elif b == "per_head_year":
            m = v / 12
        elif b == "per_head_once":
            if not contract_months or contract_months <= 0:
                raise ValidationFailed(f"Rule {r['code']} is a one-off per head cost: contract_months (> 0) is required to amortise it.", code="LABOUR_CONTRACT_MONTHS")
            m = v / contract_months
        else:
            raise ValidationFailed(f"Unknown basis {b}")
        total += m
        rows.append({"code": r["code"], "name": r["name"], "basis": b, "value": str(v), "monthly": m, "version": r.get("version")})
    return {"monthly_total": total, "rows": rows}


def blend(groups: list[dict]) -> dict:
    """groups: [{name, headcount, hourly_cost, saudi: bool}] -> headcount-weighted hourly cost and the Saudi share."""
    hc = sum((D(g["headcount"]) for g in groups), ZERO)
    if hc <= 0:
        raise ValidationFailed("Workforce mix needs a positive headcount.", code="WORKFORCE_EMPTY")
    cost = sum((D(g["headcount"]) * D(g["hourly_cost"]) for g in groups), ZERO) / hc
    saudi = sum((D(g["headcount"]) for g in groups if g.get("saudi")), ZERO)
    return {"headcount": hc, "blended_hourly_cost": cost, "saudi_headcount": saudi, "saudi_pct": saudi * 100 / hc}


def national_target_check(saudi_pct: Decimal, required_pct: Decimal) -> dict:
    gap = required_pct - saudi_pct
    return {"required_pct": required_pct, "actual_pct": saudi_pct, "meets": saudi_pct >= required_pct, "shortfall_pct_points": max(gap, ZERO)}
