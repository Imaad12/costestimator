"""Decimal-safe arithmetic helpers. All money/quantity maths in the engine goes through here."""
from __future__ import annotations

from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from typing import Any

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")

_ROUNDING = {"half_up": ROUND_HALF_UP, "half_even": ROUND_HALF_EVEN}


def D(value: Any, default: Decimal | None = None) -> Decimal:
    """Convert to Decimal without binary-float artefacts. Raises ValueError for non-numeric when no default."""
    if isinstance(value, Decimal):
        return value
    if value is None or (isinstance(value, str) and value.strip() == ""):
        if default is not None:
            return default
        raise ValueError("empty numeric value")
    if isinstance(value, bool):
        raise ValueError("boolean is not numeric")
    if isinstance(value, float):
        return Decimal(repr(value))
    if isinstance(value, str):
        s = value.strip().replace(",", "").replace(" ", "")
        if s.endswith("%"):
            s = s[:-1]
        try:
            d = Decimal(s)
        except InvalidOperation:
            if default is not None:
                return default
            raise ValueError(f"not a number: {value!r}")
        if not d.is_finite():
            raise ValueError(f"not a finite number: {value!r}")
        return d
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        if default is not None:
            return default
        raise ValueError(f"not a number: {value!r}")


def D_opt(value: Any) -> Decimal | None:
    """Like D but returns None for empty/non-numeric."""
    try:
        return D(value)
    except (ValueError, TypeError):
        return None


def to_text(value: Decimal | None) -> str | None:
    """Canonical text form stored in SQLite (no exponent, normalised trailing zeros kept minimal)."""
    if value is None:
        return None
    with localcontext() as ctx:
        ctx.prec = 60
        s = format(value, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def quantize(value: Decimal, dp: int, mode: str = "half_up") -> Decimal:
    q = Decimal(1).scaleb(-dp)
    with localcontext() as ctx:
        ctx.prec = 60
        return value.quantize(q, rounding=_ROUNDING[mode])


def pct(value: Decimal | str | int | float) -> Decimal:
    """Convert a percent-point value (5 meaning 5%) to a fraction."""
    return D(value) / HUNDRED


def fmt(value: Decimal | None, dp: int = 2) -> str:
    if value is None:
        return "—"
    return f"{quantize(value, dp):,.{dp}f}"


def largest_remainder_allocate(total: Decimal, weights: list[Decimal], dp: int = 2) -> list[Decimal]:
    """Allocate `total` across weights proportionally so rounded parts sum exactly to rounded total.

    Used for spreading indirects/markup into the pricing schedule without losing/creating cents.
    """
    n = len(weights)
    if n == 0:
        return []
    total_q = quantize(total, dp)
    w_sum = sum(weights, ZERO)
    unit = Decimal(1).scaleb(-dp)
    if w_sum == 0:
        # no basis to allocate pro-rata: equal split
        raw = [total_q / n for _ in weights]
    else:
        raw = [total * w / w_sum for w in weights]
    floors = [(r // unit) * unit for r in raw]
    remainder_units = int((total_q - sum(floors, ZERO)) / unit)
    order = sorted(range(n), key=lambda i: (raw[i] - floors[i]), reverse=True)
    out = list(floors)
    step = unit if remainder_units >= 0 else -unit
    for k in range(abs(remainder_units)):
        out[order[k % n]] += step
    return out


def quantise_tree(obj: Any, dp: int = 2) -> Any:
    """Presentation precision for time-phased reports: every Decimal in a nested report is rounded half-up to `dp` places. Calculation precision is kept inside the engines;
    only the returned report is quantised (a 28-digit residue such as 3E-21 is never shown to a reader)."""
    from decimal import ROUND_HALF_UP
    q = Decimal(1).scaleb(-dp)
    if isinstance(obj, Decimal):
        return obj.quantize(q, rounding=ROUND_HALF_UP) if obj.is_finite() else obj
    if isinstance(obj, dict):
        return {k: quantise_tree(v, dp) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(quantise_tree(v, dp) for v in obj)
    return obj
