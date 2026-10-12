"""Pure rate-eligibility resolution: which stored rate (if any) may price a resource in a given project/date.

Outcome codes (RateResolution.eligibility):
  ELIGIBLE      approved, in date, correct region, a real price type
  PROVISIONAL   project-scoped 'Provisional — Approved for This Estimate'
  EXPIRED       approved rate exists but valid_until < as_of
  FUTURE        only rates with price_date after as_of
  UNAPPROVED    only Draft / Pending Review rates exist
  REGION        only rates for other regions exist
  NON_PRICE     only an official index / benchmark exists (never a unit price)
  MISSING       no price at all
Indicative (non-eligible) prices are returned only to quantify exposure; they must never enter totals.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from ..core.money import D_opt
from ..core.timeutil import parse_date
from ..models.enums import NON_PRICE_RATE_TYPES, Status

ELIGIBLE, PROVISIONAL, EXPIRED, FUTURE, UNAPPROVED, REGION, NON_PRICE, MISSING = (
    "ELIGIBLE", "PROVISIONAL", "EXPIRED", "FUTURE", "UNAPPROVED", "REGION", "NON_PRICE", "MISSING")
USABLE = {ELIGIBLE, PROVISIONAL}


@dataclass
class RateResolution:
    eligibility: str
    rate: dict | None = None
    indicative_rate: dict | None = None
    warnings: list[str] = field(default_factory=list)
    message: str = ""

    @property
    def usable(self) -> bool:
        return self.eligibility in USABLE


def region_applies(rate_region: str | None, project_region: str, parents: dict[str, str | None] | None = None) -> bool:
    rr = rate_region or "KSA-ALL"
    if rr == "KSA-ALL" or rr == project_region:
        return True
    # rate recorded for a parent region of the project region
    p = parents or {}
    cur = project_region
    seen = set()
    while cur and cur not in seen:
        seen.add(cur)
        cur = p.get(cur)
        if cur == rr:
            return True
    return False


def resolve_rate(rates: list[dict], *, project_id: str | None, project_region: str, as_of: date,
                 region_parents: dict[str, str | None] | None = None, age_warning_days: int | None = None
                 ) -> RateResolution:
    live = [r for r in rates if r["status"] not in (Status.SUPERSEDED.value, Status.REJECTED.value)
            and (r.get("project_id") in (None, "", project_id))]
    if not live:
        return RateResolution(MISSING, message="No rate on record.")
    real = [r for r in live if r["rate_type"] not in NON_PRICE_RATE_TYPES and D_opt(r.get("unit_price")) is not None]
    if not real:
        if any(r["rate_type"] == "Official Index or Benchmark" for r in live):
            return RateResolution(NON_PRICE, message="Only an official index/benchmark exists; it is not a unit price.")
        return RateResolution(MISSING, message="Rate is recorded as missing (no price).")

    in_region = [r for r in real if region_applies(r.get("region"), project_region, region_parents)]
    if not in_region:
        return RateResolution(REGION, indicative_rate=real[0],
                              message=f"Rates exist only for other regions (project region {project_region}).")

    def key(r):
        return (1 if r.get("project_id") == project_id and project_id else 0,
                parse_date(r.get("price_date")) or date.min, r["version"])

    ok, expired, future, unapproved = [], [], [], []
    for r in in_region:
        pd, vu = parse_date(r.get("price_date")), parse_date(r.get("valid_until"))
        st = r["status"]
        if st == Status.EXPIRED.value:
            expired.append(r)
            continue
        if st not in (Status.APPROVED.value, Status.PROVISIONAL.value):
            unapproved.append(r)
            continue
        if st == Status.PROVISIONAL.value and r.get("project_id") != project_id:
            unapproved.append(r)
            continue
        if pd and pd > as_of:
            future.append(r)
        elif vu and vu < as_of:
            expired.append(r)
        else:
            ok.append(r)
    if ok:
        best = sorted(ok, key=key, reverse=True)[0]
        warns: list[str] = []
        pd = parse_date(best.get("price_date"))
        if age_warning_days is not None and pd and (as_of - pd).days > age_warning_days:
            warns.append(f"Rate is {(as_of - pd).days} days old (> {age_warning_days} day warning threshold).")
        if best.get("confidence") in ("Low", "Unverified"):
            warns.append(f"Rate confidence is {best.get('confidence')}.")
        if best.get("is_synthetic"):
            warns.append("SYNTHETIC / DEMO / NOT A MARKET QUOTE.")
        elig = PROVISIONAL if best["status"] == Status.PROVISIONAL.value else ELIGIBLE
        return RateResolution(elig, rate=best, warnings=warns)
    if expired:
        return RateResolution(EXPIRED, indicative_rate=sorted(expired, key=key, reverse=True)[0],
                              message="Approved rate has expired (valid_until before estimate date).")
    if future:
        return RateResolution(FUTURE, indicative_rate=future[0], message="Rate is dated after the estimate date.")
    return RateResolution(UNAPPROVED, indicative_rate=sorted(unapproved, key=key, reverse=True)[0],
                          message="Rate exists but is not approved (Draft / Pending Review).")
