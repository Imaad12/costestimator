"""Resource loading: spread task quantities (labour hours, cost ...) uniformly over the task's working days and bucket them into periods.

Uniform spreading is a stated simplification (documented); it is exact in total: the last day takes the remainder so that the sum of any task's
spread equals its input quantity. Quantities that cannot be tied to a scheduled task are reported separately, never dropped or smeared.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

ZERO = Decimal(0)


@dataclass
class Load:
    key: str                 # series key, e.g. a craft / resource id / cost kind
    task_code: str | None    # None => cannot be tied to a task
    qty: Decimal


def spread(es: Decimal, ef: Decimal, qty: Decimal) -> dict[int, Decimal]:
    """{working-day index: quantity}. Day k spans [k, k+1). A zero-duration task puts everything on its start day."""
    first = int(math.floor(es))
    if ef <= es:
        return {first: qty}
    last = int(math.ceil(ef)) - 1
    dur = ef - es
    out: dict[int, Decimal] = {}
    acc = ZERO
    for k in range(first, last + 1):
        if k == last:
            out[k] = qty - acc
        else:
            share = qty * (min(Decimal(k + 1), ef) - max(Decimal(k), es)) / dur
            out[k] = share
            acc += share
    return out


def histogram(loads: list[Load], sched: dict[str, tuple[Decimal, Decimal]], bucket_of_day: Callable[[int], str]) -> dict:
    """Series per key over buckets (ordered by first day), peak bucket per key, and an explicit 'unscheduled' total per key."""
    series: dict[str, dict[str, Decimal]] = {}
    first_day: dict[str, int] = {}
    unscheduled: dict[str, Decimal] = {}
    for ld in loads:
        if ld.qty is None:
            continue
        if ld.task_code is None or ld.task_code not in sched:
            unscheduled[ld.key] = unscheduled.get(ld.key, ZERO) + ld.qty
            continue
        es, ef = sched[ld.task_code]
        for day, q in spread(es, ef, ld.qty).items():
            b = bucket_of_day(day)
            first_day.setdefault(b, day)
            first_day[b] = min(first_day[b], day)
            s = series.setdefault(ld.key, {})
            s[b] = s.get(b, ZERO) + q
    buckets = sorted(first_day, key=lambda b: first_day[b])
    peaks = {}
    for k, s in series.items():
        pb = max(s, key=lambda b: (s[b], -first_day[b]))
        peaks[k] = {"bucket": pb, "qty": s[pb]}
    total = {k: sum(s.values(), ZERO) for k, s in series.items()}
    all_by_bucket = {b: sum((series[k].get(b, ZERO) for k in series), ZERO) for b in buckets}
    return {"buckets": buckets, "series": series, "peaks": peaks, "totals": total, "unscheduled": unscheduled,
            "all_by_bucket": all_by_bucket,
            "peak_all": (max(all_by_bucket.items(), key=lambda kv: (kv[1], -first_day[kv[0]])) if all_by_bucket else None)}


def block_bucketer(block_days: int) -> Callable[[int], str]:
    def f(day: int) -> str:
        s = (day // block_days) * block_days
        return f"WD{s + 1:04d}-{s + block_days:04d}"
    return f
