"""Unit registry: canonical codes, synonym lookup, and explicit conversions.

Principles
* Only convertible dimensions (length, area, volume, mass) convert automatically, by fixed physical factors.
* Time units (hr/day/week/month) NEVER convert implicitly: that requires an approved working-calendar assumption.
* Ambiguous spellings (e.g. 'cm', 'ton', 'sum') are never normalised silently: `resolve` reports them as ambiguous.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from ..database import Database
from .errors import ValidationFailed
from .money import D


@dataclass(frozen=True)
class UnitDef:
    code: str
    name: str
    dimension: str
    to_base: Decimal


@dataclass(frozen=True)
class UnitResolution:
    status: str  # ok / ambiguous / unknown / missing
    code: str | None
    original: str | None
    candidates: tuple[str, ...] = ()
    message: str = ""


def _norm(s: str) -> str:
    s = s.strip().lower().replace("²", "2").replace("³", "3")
    s = re.sub(r"\s+", " ", s)
    return s


class UnitRegistry:
    def __init__(self, units: list[dict]):
        self.units: dict[str, UnitDef] = {}
        self._syn: dict[str, str] = {}
        self._amb: dict[str, list[str]] = {}
        for u in units:
            ud = UnitDef(u["code"], u["name"], u["dimension"], D(u["to_base"]))
            self.units[ud.code] = ud
            self._syn[_norm(ud.code)] = ud.code
            for s in (u.get("synonyms") or "").split("|"):
                if s.strip():
                    self._syn.setdefault(_norm(s), ud.code)
            for s in (u.get("ambiguous_synonyms") or "").split("|"):
                if s.strip():
                    self._amb.setdefault(_norm(s), []).append(ud.code)
        # An ambiguous spelling must not also be an unambiguous synonym.
        for k in list(self._amb):
            self._syn.pop(k, None)

    @classmethod
    def from_db(cls, db: Database) -> "UnitRegistry":
        return cls([dict(r) for r in db.all("SELECT * FROM units WHERE active=1")])

    def resolve(self, text: str | None) -> UnitResolution:
        if text is None or str(text).strip() == "":
            return UnitResolution("missing", None, text, message="Unit is missing.")
        key = _norm(str(text))
        if key in self._amb:
            c = tuple(self._amb[key])
            return UnitResolution("ambiguous", None, text, c,
                                  f"Unit '{text}' is ambiguous (possible: {', '.join(c)}). Estimator must confirm.")
        if key in self._syn:
            return UnitResolution("ok", self._syn[key], text)
        key2 = key.rstrip(".")
        if key2 in self._syn:
            return UnitResolution("ok", self._syn[key2], text)
        return UnitResolution("unknown", None, text, message=f"Unsupported unit '{text}'.")

    def get(self, code: str) -> UnitDef:
        try:
            return self.units[code]
        except KeyError:
            raise ValidationFailed(f"Unknown unit code '{code}'.", code="UNKNOWN_UNIT")

    def can_convert(self, src: str, dst: str) -> bool:
        if src == dst:
            return True
        a, b = self.units.get(src), self.units.get(dst)
        return bool(a and b and a.dimension == b.dimension and a.dimension in CONVERTIBLE)

    def factor(self, src: str, dst: str) -> Decimal:
        """Multiply a quantity in `src` by this to get `dst`. Raises if not convertible without an assumption."""
        if src == dst:
            return Decimal(1)
        if not self.can_convert(src, dst):
            raise ValidationFailed(
                f"No automatic conversion from '{src}' to '{dst}'. An explicit approved conversion assumption is required.",
                code="UNIT_CONVERSION_UNAVAILABLE")
        return self.get(src).to_base / self.get(dst).to_base

    def convert(self, qty: Decimal, src: str, dst: str) -> Decimal:
        return qty * self.factor(src, dst)


CONVERTIBLE = {"length", "area", "volume", "mass"}

_cache: dict[int, UnitRegistry] = {}


def registry(db: Database) -> UnitRegistry:
    key = id(db)
    n = db.scalar("SELECT COUNT(*) FROM units")
    c = _cache.get(key)
    if c is None or len(c.units) != n:
        c = _cache[key] = UnitRegistry.from_db(db)
    return c
