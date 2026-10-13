"""Time-phased escalation: compound an annual rate from a base date to the middle of each period. Pure Decimal.

factor(t) = (1 + annual_pct/100) ** (months_from_base / 12). Fractional exponents are evaluated with Decimal.ln/exp (28-digit precision).
Nothing here forecasts: the annual percentage and base date are entered by a person (an official index series may be shown beside them as information)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..core.errors import ValidationFailed


def months_between(base: date, d: date) -> Decimal:
    return Decimal((d.year - base.year) * 12 + (d.month - base.month)) + Decimal(d.day - base.day) / Decimal(30)


def factor(annual_pct: Decimal, months: Decimal) -> Decimal:
    if annual_pct <= -100:
        raise ValidationFailed("annual escalation must be above -100%.", code="ESC_RATE")
    if months <= 0:
        return Decimal(1)
    g = Decimal(1) + annual_pct / 100
    return (g.ln() * (months / 12)).exp()


def phase(period_amounts: dict[str, Decimal], period_mid: dict[str, date], base: date, annual_pct: Decimal) -> dict:
    rows, tot_base, tot_esc = [], Decimal(0), Decimal(0)
    for p in sorted(period_amounts, key=lambda k: period_mid[k]):
        f = factor(annual_pct, months_between(base, period_mid[p]))
        a = period_amounts[p]
        rows.append({"period": p, "mid": period_mid[p].isoformat(), "base_amount": a, "factor": f, "escalated": a * f, "escalation": a * f - a})
        tot_base += a
        tot_esc += a * f
    return {"rows": rows, "base_total": tot_base, "escalated_total": tot_esc, "escalation_total": tot_esc - tot_base, "annual_pct": annual_pct, "base_date": base.isoformat()}
