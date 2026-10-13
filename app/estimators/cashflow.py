"""Contract cash flow: advance, valuations, retention, payment lags, supplier credit, bonds and financing cost. Pure Decimal, monthly.

Stated assumptions (shown with every result): value earned in a month is proportional to cost incurred in that month; amounts exclude VAT; interest is charged on
a negative opening balance each month and capitalised; positive balances earn nothing; the advance is received in month 0 and recovered pro rata from valuations.
All terms are supplied by a person (contract / bank / supplier terms)."""
from __future__ import annotations

from decimal import Decimal

from ..core.errors import ValidationFailed
from ..core.money import ZERO, D

TERM_KEYS = ("advance_pct", "retention_pct", "retention_release_at_completion_pct", "defects_months", "certification_lag_months", "payment_lag_months",
             "supplier_payment_lag_months", "financing_rate_annual_pct", "performance_bond_pct", "performance_bond_fee_annual_pct")


def build(cost_by_month: dict[int, Decimal], price: Decimal, terms: dict) -> dict:
    if not cost_by_month or sum(cost_by_month.values(), ZERO) <= 0:
        raise ValidationFailed("Cash flow needs time-phased cost (programme + calendar).", code="CASHFLOW_NO_COST")
    if price is None or price <= 0:
        raise ValidationFailed("Cash flow needs a computed selling price (complete commercial policy).", code="CASHFLOW_NO_PRICE")
    t = {k: D(terms[k]) for k in TERM_KEYS}
    adv, ret = t["advance_pct"] / 100, t["retention_pct"] / 100
    rel1 = t["retention_release_at_completion_pct"] / 100
    defects, clag, plag, slag = int(t["defects_months"]), int(t["certification_lag_months"]), int(t["payment_lag_months"]), int(t["supplier_payment_lag_months"])
    total_cost = sum(cost_by_month.values(), ZERO)
    months = sorted(cost_by_month)
    first, last = months[0], months[-1]
    horizon = max(last + clag + plag, last + defects + plag, last + slag)          # last month index
    inflow = [ZERO] * (horizon + 1)
    outflow = [ZERO] * (horizon + 1)
    val_rows = []
    retention_total = ZERO
    inflow[first] += price * adv                                         # advance, received in the first month
    for m in months:
        v = price * cost_by_month[m] / total_cost
        rec, rt = v * adv, v * ret
        retention_total += rt
        inflow[m + clag + plag] += v - rec - rt
        outflow[m + slag] += cost_by_month[m]
        val_rows.append({"month": m, "value": v, "advance_recovery": rec, "retention": rt, "net_certified": v - rec - rt})
    inflow[last + clag + plag] += retention_total * rel1
    inflow[last + defects + plag] += retention_total * (1 - rel1)
    bal, rows, interest_total, peak = ZERO, [], ZERO, ZERO
    rate_m = t["financing_rate_annual_pct"] / 100 / 12
    for m in range(horizon + 1):
        interest = -bal * rate_m if bal < 0 else ZERO
        flow = inflow[m] - outflow[m]
        bal = bal + flow - interest
        interest_total += interest
        peak = min(peak, bal)
        rows.append({"month": m, "cash_in": inflow[m], "cash_out": outflow[m], "net": flow, "interest": interest, "balance": bal})
    duration = last - first + 1
    bond_months = D(duration + defects)
    bond_cost = price * t["performance_bond_pct"] / 100 * t["performance_bond_fee_annual_pct"] / 100 * bond_months / 12
    return {"rows": rows, "valuations": val_rows, "price": price, "total_cost": total_cost, "retention_total": retention_total, "advance": price * adv,
            "interest_total": interest_total, "peak_funding": -peak, "peak_funding_month": next((r["month"] for r in rows if r["balance"] == peak), None) if peak < 0 else None,
            "performance_bond_cost": bond_cost, "bond_months": bond_months, "final_balance": rows[-1]["balance"], "terms": {k: t[k] for k in TERM_KEYS},
            "assumptions": ["Value earned in a month is proportional to cost incurred in that month (margin is not front- or back-loaded).", "Amounts exclude VAT.",
                            "Interest accrues monthly on a negative opening balance and is capitalised; positive balances earn nothing.",
                            "The advance is received in the first month and recovered pro rata from valuations; retention is released as stated in the terms."]}
