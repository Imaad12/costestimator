"""Earned-value arithmetic (standard definitions). Pure Decimal.
  CV = EV - AC ; SV = EV - PV ; CPI = EV / AC ; SPI = EV / PV
  EAC (CPI method) = BAC / CPI ; EAC (remaining at budget rate) = AC + (BAC - EV) ; ETC = EAC - AC ; VAC = BAC - EAC ; TCPI = (BAC - EV) / (BAC - AC)
Undefined ratios are None - never zero or infinity."""
from __future__ import annotations

from decimal import Decimal

from ..core.money import ZERO


def metrics(bac: Decimal, pv: Decimal, ev: Decimal, ac: Decimal) -> dict:
    cpi = ev / ac if ac > 0 else None
    spi = ev / pv if pv > 0 else None
    eac_cpi = bac / cpi if cpi else None
    eac_rem = ac + (bac - ev)
    return {"BAC": bac, "PV": pv, "EV": ev, "AC": ac, "CV": ev - ac, "SV": ev - pv, "CPI": cpi, "SPI": spi, "EAC_cpi": eac_cpi, "EAC_remaining_at_budget": eac_rem,
            "ETC_cpi": None if eac_cpi is None else eac_cpi - ac, "VAC_cpi": None if eac_cpi is None else bac - eac_cpi, "VAC_remaining_at_budget": bac - eac_rem,
            "TCPI": (bac - ev) / (bac - ac) if bac != ac else None, "percent_complete": ev * 100 / bac if bac > 0 else None}


def planned_pct(offset: Decimal, es: Decimal, ef: Decimal) -> Decimal:
    """Share of a task planned complete when `offset` working days have elapsed (linear)."""
    if ef <= es:
        return Decimal(1) if offset >= es else ZERO
    return min(max((offset - es) / (ef - es), ZERO), Decimal(1))
