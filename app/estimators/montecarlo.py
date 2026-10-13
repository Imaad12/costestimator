"""Quantified risk: expected value and seeded Monte Carlo over a human-entered risk register (and optional range-estimated cost items).

Method (stated, so the output can be challenged):
  * every risk is independent; it occurs with probability p; if it occurs its cost is drawn from a triangular(low, likely, high) distribution
  * range items (optional) are triangular(low, likely, high) draws that are always present (uncertainty in the base, entered by the estimator)
  * schedule impacts are summed as days when the risk occurs (no critical-path logic)
  * results are reproducible: same inputs + seed -> identical output (Python's Mersenne Twister)
The simulation PROPOSES a contingency figure at the confidence level the user chooses; it never changes the commercial policy.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from decimal import Decimal

from ..core.errors import ValidationFailed
from ..core.money import ZERO, D


@dataclass
class RiskIn:
    id: str
    title: str
    p: Decimal            # 0..1
    low: Decimal
    likely: Decimal
    high: Decimal
    days: Decimal = ZERO


@dataclass
class RangeIn:
    name: str
    low: Decimal
    likely: Decimal
    high: Decimal


def triangular_mean(low: Decimal, likely: Decimal, high: Decimal) -> Decimal:
    return (low + likely + high) / 3


def validate(risks: list[RiskIn], ranges: list[RangeIn]) -> None:
    for r in risks:
        if not (ZERO <= r.p <= 1):
            raise ValidationFailed(f"{r.id}: probability must be between 0 and 100%.", code="RISK_PROB")
        if not (r.low <= r.likely <= r.high):
            raise ValidationFailed(f"{r.id}: need low <= most likely <= high.", code="RISK_RANGE")
        if r.low < 0:
            raise ValidationFailed(f"{r.id}: costs cannot be negative (model opportunities as separate negative ranges explicitly).", code="RISK_RANGE")
    for x in ranges:
        if not (x.low <= x.likely <= x.high):
            raise ValidationFailed(f"{x.name}: need low <= most likely <= high.", code="RISK_RANGE")


def expected_value(risks: list[RiskIn], ranges: list[RangeIn]) -> dict:
    per = {r.id: r.p * triangular_mean(r.low, r.likely, r.high) for r in risks}
    rng = {x.name: triangular_mean(x.low, x.likely, x.high) for x in ranges}
    return {"per_risk": per, "per_range": rng, "total": sum(per.values(), ZERO) + sum(rng.values(), ZERO)}


def _pct(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    i = q / 100 * (len(sorted_vals) - 1)
    lo, hi = int(i), min(int(i) + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (i - lo)


def simulate(risks: list[RiskIn], ranges: list[RangeIn], trials: int, seed: int, percentiles: tuple[int, ...] = (10, 50, 80, 90), bins: int = 20) -> dict:
    if trials < 100 or trials > 1_000_000:
        raise ValidationFailed("trials must be between 100 and 1,000,000.", code="MC_TRIALS")
    validate(risks, ranges)
    rnd = random.Random(seed)
    rp = [(float(r.p), float(r.low), float(r.likely), float(r.high), float(r.days)) for r in risks]
    rg = [(float(x.low), float(x.likely), float(x.high)) for x in ranges]
    totals, days, contrib = [], [], [0.0] * len(risks)
    occurred = [0] * len(risks)
    for _ in range(trials):
        t, d = 0.0, 0.0
        for i, (p, lo, li, hi, dy) in enumerate(rp):
            if rnd.random() < p:
                v = lo if hi == lo else rnd.triangular(lo, hi, li)
                t += v
                d += dy
                contrib[i] += v
                occurred[i] += 1
        for lo, li, hi in rg:
            t += lo if hi == lo else rnd.triangular(lo, hi, li)
        totals.append(t)
        days.append(d)
    s = sorted(totals)
    mean = sum(totals) / trials
    var = sum((x - mean) ** 2 for x in totals) / trials
    sd = sorted(days)
    lo_, hi_ = s[0], s[-1]
    width = (hi_ - lo_) / bins if hi_ > lo_ else 1.0
    hist = [0] * bins
    for x in totals:
        hist[min(int((x - lo_) / width), bins - 1) if hi_ > lo_ else 0] += 1
    out = {
        "trials": trials, "seed": seed, "mean": D(repr(mean)), "std_dev": D(repr(var ** 0.5)), "min": D(repr(lo_)), "max": D(repr(hi_)),
        "percentiles": {f"P{q}": D(repr(_pct(s, q))) for q in percentiles},
        "schedule_days": {f"P{q}": D(repr(_pct(sd, q))) for q in percentiles} if any(r.days for r in risks) else None,
        "histogram": [{"from": D(repr(lo_ + i * width)), "to": D(repr(lo_ + (i + 1) * width)), "count": c} for i, c in enumerate(hist)] if hi_ > lo_ else [],
        "per_risk": [{"id": r.id, "title": r.title, "p": r.p, "occurred_pct": D(occurred[i]) * 100 / trials, "mean_contribution": D(repr(contrib[i] / trials))}
                     for i, r in enumerate(risks)],
    }
    return out
