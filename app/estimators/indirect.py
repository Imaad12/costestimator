"""Indirect-cost engine: fixed, percentage, and duration-based costs with explicit allocation methods.

Duration-based formulas (duration M = APPROVED project months):
  per_month / per_duration_month : amount x quantity x M
  per_week                       : amount x quantity x M x (working_days_per_month / working_days_per_week)
  per_day                        : amount x quantity x M x working_days_per_month
  percent_of_direct              : amount% x total direct cost
  fixed                          : amount x quantity
Items flagged included_in_subcontract are excluded (shown with a reason) to avoid double counting.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from decimal import Decimal

from ..core.money import ZERO, D, D_opt, pct, quantize
from . import eligibility as elig
from .types import EngineException


@dataclass
class IndirectLine:
    code: str
    category: str
    description: str
    method: str
    amount: Decimal | None
    basis: str
    allocation_method: str
    allocation_target: str | None
    status: str
    flags: list[str] = field(default_factory=list)
    excluded_reason: str | None = None
    provisional: bool = False
    eligibility: dict | None = None            # audit breakdown of the base for percentage methods (never part of the fingerprint)


@dataclass
class IndirectResult:
    lines: list[IndirectLine]
    total: Decimal
    exceptions: list[EngineException]
    duration_months: Decimal | None
    duration_status: str | None

    @property
    def resolved(self) -> bool:
        return not any(l.amount is None and not l.excluded_reason for l in self.lines)


def compute_indirects(items: list[dict], *, direct_cost_total: Decimal, duration_months: Decimal | None,
                      duration_status: str | None, working_days_per_month: Decimal | None,
                      working_days_per_week: Decimal | None, money_dp: int = 2, include_unapproved: bool = False,
                      direct_lines: list[dict] | None = None) -> IndirectResult:
    out: list[IndirectLine] = []
    exc: list[EngineException] = []
    dur_ok = duration_months is not None and (duration_status == "Approved" or include_unapproved)
    for it in items:
        if it.get("status") == "Superseded":
            continue
        ln = IndirectLine(it["code"], it["category"], it["description"], it["method"], None, "",
                          it["allocation_method"], it.get("allocation_target"), it["status"])
        out.append(ln)
        if it.get("included_in_subcontract"):
            ln.amount = ZERO
            ln.excluded_reason = "Included in subcontract quotation/assembly - excluded to avoid double counting."
            ln.basis = ln.excluded_reason
            continue
        if it["status"] != "Approved" and not (include_unapproved and it["status"] in ("Pending Review", "Draft")):
            ln.flags.append("INDIRECT_NOT_APPROVED")
            exc.append(EngineException("INDIRECT_NOT_APPROVED", "High",
                                       f"Indirect {it['code']} ({it['description'][:40]}) is '{it['status']}'.",
                                       exposure=None))
            continue
        if it["status"] != "Approved":
            ln.flags.append("UNAPPROVED_USED_PRELIMINARY")
        amount = D_opt(it.get("amount"))
        qty = D_opt(it.get("quantity")) or Decimal(1)
        if amount is None:
            ln.flags.append("AMOUNT_MISSING")
            exc.append(EngineException("INDIRECT_AMOUNT_MISSING", "High",
                                       f"Indirect {it['code']} has no rate/amount (input required, not defaulted to zero)."))
            continue
        m = it["method"]
        months = D_opt(it.get("duration_override_months")) if it.get("duration_override_months") else duration_months
        if m == "fixed":
            val, basis = amount * qty, f"fixed {amount} x {qty}"
        elif m == "percent_of_direct":
            spec = elig.validate_spec(json.loads(it["eligibility_json"])) if it.get("eligibility_json") else None
            if spec is None or direct_lines is None:
                base, bd = direct_cost_total, None
                if direct_lines is not None:
                    bd = elig.eligible_base(direct_lines, None)
            else:
                bd = elig.eligible_base(direct_lines, spec)
                base = bd["eligible"]
            if bd is not None:
                bd = {**bd, "rate_pct": amount}
            ln.eligibility = bd
            val = pct(amount) * base
            basis = (f"{amount}% x direct cost {direct_cost_total}" if spec is None else
                     f"{amount}% x eligible direct cost {base} (of {direct_cost_total}; excluded {bd['excluded']}, unclassified {bd['unclassified']})")
        else:
            if months is None or not (dur_ok or it.get("duration_override_months")):
                ln.flags.append("DURATION_NOT_APPROVED")
                exc.append(EngineException("DURATION_NOT_APPROVED", "High",
                                           f"Indirect {it['code']} is duration-based but project duration is not approved."))
                continue
            if m in ("per_month", "per_duration_month"):
                val, basis = amount * qty * months, f"{amount} x {qty} x {months} months"
            elif m in ("per_week", "per_day"):
                if not working_days_per_month or (m == "per_week" and not working_days_per_week):
                    ln.flags.append("CALENDAR_MISSING")
                    exc.append(EngineException("CALENDAR_MISSING", "High",
                                               f"Indirect {it['code']} needs approved working-calendar assumptions."))
                    continue
                if m == "per_day":
                    val = amount * qty * months * working_days_per_month
                    basis = f"{amount} x {qty} x {months} months x {working_days_per_month} working days/month"
                else:
                    val = amount * qty * months * working_days_per_month / working_days_per_week
                    basis = (f"{amount} x {qty} x {months} months x {working_days_per_month}/{working_days_per_week} "
                             "working weeks/month")
            else:
                continue
        ln.amount = quantize(val, money_dp)
        ln.basis = basis
    total = sum((l.amount for l in out if l.amount is not None), ZERO)
    return IndirectResult(out, total, exc, duration_months, duration_status)
