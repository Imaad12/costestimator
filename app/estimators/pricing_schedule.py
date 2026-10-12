"""Pricing schedule: spreads indirects and commercial adders onto BOQ items and reconciles to the commercial total.

Allocation (explicit, reported):
  * indirect lines with allocation 'pro_rata_direct' -> spread over all priced items by direct-cost weight
  * 'direct_trade'                                    -> spread over items whose cost code starts with the target
  * 'separate_line'                                   -> kept as its own schedule line (not spread)
  * contingency, risk, escalation, markup/margin, discount -> spread over items by (direct + allocated indirect) weight
  Spreading uses largest-remainder allocation, so the unrounded item amounts sum EXACTLY to the commercial net price.
  Tendered unit rates are then rounded to `rate_dp`; amount = round(qty x rate). Any difference to the commercial
  net price is reported as `rounding_variance` (never hidden).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ..core.money import ONE, ZERO, D_opt, largest_remainder_allocate, quantize
from .commercial import CommercialResult
from .direct_cost import DirectCostResult
from .indirect import IndirectResult


@dataclass
class ScheduleLine:
    item_key: str
    item_code: str | None
    description: str
    unit: str | None
    quantity: Decimal | None
    cost_code: str | None
    status: str                       # Priced / Unpriced / Excluded / Provisional
    direct_cost: Decimal
    allocated_indirect: Decimal
    allocated_adders: Decimal         # contingency + risk + escalation
    allocated_margin: Decimal         # markup / margin
    allocated_discount: Decimal
    net_unrounded: Decimal
    unit_rate: Decimal | None
    amount: Decimal | None
    tax_category: str | None
    pricing_method: str
    flags: list[str] = field(default_factory=list)


@dataclass
class PricingSchedule:
    lines: list[ScheduleLine]
    separate_lines: list[dict]        # indirects shown as their own lines
    subtotal_items: Decimal
    subtotal_separate: Decimal
    total_pre_tax: Decimal
    commercial_net_price: Decimal
    rounding_variance: Decimal
    indirect_allocation: list[dict]   # per indirect line: how it was allocated
    complete: bool
    tax_shares: dict[str, Decimal]
    max_rounding_variance: Decimal = ZERO   # worst case from rounding unit rates to rate_dp and amounts to money_dp


def build_schedule(direct: DirectCostResult, indirect: IndirectResult, com_inputs: dict, commercial_ratio: dict,
                   items_meta: dict[str, dict], *, money_dp: int = 2, rate_dp: int = 2, default_tax: str | None = None
                   ) -> PricingSchedule:
    """commercial_ratio: {'adders': Decimal total, 'margin': Decimal, 'discount': Decimal (positive), 'net': Decimal}"""
    keys = [k for k, ic in direct.items.items() if ic.pricing_method != "excluded"]
    priced = [k for k in keys if direct.items[k].complete]
    dw = [direct.items[k].direct_cost for k in priced]

    ind_alloc: dict[str, Decimal] = {k: ZERO for k in keys}
    separate: list[dict] = []
    alloc_report: list[dict] = []
    for l in indirect.lines:
        if l.amount is None or l.amount == 0:
            alloc_report.append({"code": l.code, "description": l.description, "amount": l.amount, "allocation": l.allocation_method,
                                 "note": l.excluded_reason or ("unresolved" if l.amount is None else "zero")})
            continue
        if l.allocation_method == "separate_line":
            separate.append({"code": l.code, "description": l.description, "amount": l.amount})
            alloc_report.append({"code": l.code, "description": l.description, "amount": l.amount, "allocation": "separate_line",
                                 "note": "shown as its own pricing schedule line"})
            continue
        if l.allocation_method == "direct_trade":
            targets = [k for k in priced if (direct.items[k].cost_code or "").startswith(l.allocation_target or "\0")]
            if not targets:
                targets = priced
        else:
            targets = priced
        parts = largest_remainder_allocate(l.amount, [direct.items[k].direct_cost for k in targets], money_dp) if targets else []
        for k, p in zip(targets, parts):
            ind_alloc[k] += p
        alloc_report.append({"code": l.code, "description": l.description, "amount": l.amount, "allocation": l.allocation_method,
                             "target": l.allocation_target, "items": len(targets), "note": "spread by direct-cost weight"})

    # weights for commercial adders: direct + allocated indirect; separate indirect lines take part as pseudo-items
    # so that the schedule reconciles to the commercial net price.
    w = [direct.items[k].direct_cost + ind_alloc[k] for k in priced] + [s["amount"] for s in separate]
    n_items = len(priced)
    if w:
        adders = largest_remainder_allocate(commercial_ratio["adders"], w, money_dp)
        margin_parts = largest_remainder_allocate(commercial_ratio["margin"], w, money_dp)
        disc_parts = largest_remainder_allocate(commercial_ratio["discount"], w, money_dp)
    else:
        adders = margin_parts = disc_parts = []
    for j, sline in enumerate(separate):
        n = n_items + j
        sline["adders"], sline["margin"], sline["discount"] = adders[n], margin_parts[n], disc_parts[n]
        sline["net"] = sline["amount"] + adders[n] + margin_parts[n] - disc_parts[n]
        sline["price"] = quantize(sline["net"], money_dp)
    idx = {k: i for i, k in enumerate(priced)}

    lines: list[ScheduleLine] = []
    tax_amounts: dict[str, Decimal] = {}
    for k in direct.items:
        ic = direct.items[k]
        meta = items_meta.get(k, {})
        tc = meta.get("tax_category") or default_tax
        if ic.pricing_method == "excluded":
            lines.append(ScheduleLine(k, ic.item_code, ic.description or "", ic.unit, ic.quantity, ic.cost_code, "Excluded",
                                      ZERO, ZERO, ZERO, ZERO, ZERO, ZERO, None, None, tc, ic.pricing_method,
                                      ["EXCLUDED_FROM_PRICE"]))
            continue
        if k not in idx:
            lines.append(ScheduleLine(k, ic.item_code, ic.description or "", ic.unit, ic.quantity, ic.cost_code, "Unpriced",
                                      ic.direct_cost, ZERO, ZERO, ZERO, ZERO, ZERO, None, None, tc, ic.pricing_method,
                                      ["UNPRICED_OR_INCOMPLETE"]))
            continue
        i = idx[k]
        net = direct.items[k].direct_cost + ind_alloc[k] + adders[i] + margin_parts[i] - disc_parts[i]
        qty = ic.quantity
        rate = amount = None
        if qty and qty > 0:
            rate = quantize(net / qty, rate_dp)
            amount = quantize(qty * rate, money_dp)
        else:
            amount = quantize(net, money_dp)
        flags = []
        if ic.provisional:
            flags.append("PROVISIONAL_INPUTS")
        if ic.synthetic:
            flags.append("SYNTHETIC_DATA")
        status = "Provisional" if ic.pricing_method in ("provisional_sum", "prime_cost_sum", "allowance") else "Priced"
        lines.append(ScheduleLine(k, ic.item_code, ic.description or "", ic.unit, qty, ic.cost_code, status, ic.direct_cost,
                                  ind_alloc[k], adders[i], margin_parts[i], disc_parts[i], net, rate, amount, tc,
                                  ic.pricing_method, flags))
        tax_amounts[tc or ""] = tax_amounts.get(tc or "", ZERO) + (amount or ZERO)

    sub_items = sum((l.amount for l in lines if l.amount is not None), ZERO)
    # separate lines carry their own commercial uplift proportionally so the schedule still reconciles
    sep_total = sum((s["price"] for s in separate), ZERO)
    if sep_total:
        tax_amounts[default_tax or ""] = tax_amounts.get(default_tax or "", ZERO) + sep_total
    total = sub_items + sep_total
    variance = quantize(total - commercial_ratio["net"], money_dp)
    half = Decimal(1).scaleb(-rate_dp) / 2
    max_rv = sum(((l.quantity or ONE) * half + Decimal(1).scaleb(-money_dp) / 2 for l in lines if l.amount is not None), ZERO) \
        + sum((Decimal(1).scaleb(-money_dp) / 2 for _ in separate), ZERO) + Decimal(1).scaleb(-money_dp)
    complete = all(l.status in ("Priced", "Provisional", "Excluded") for l in lines) and indirect.resolved
    shares = {c: a for c, a in tax_amounts.items() if a}
    return PricingSchedule(lines, separate, sub_items, sep_total, total, commercial_ratio["net"], variance, alloc_report,
                           complete, shares, max_rv)
