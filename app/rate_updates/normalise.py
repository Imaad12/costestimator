"""Price normalisation: only when every input is known and recorded.  The original price is never modified.

Steps (each optional, each recorded in `steps` with the exact factor and where it came from):
  1. currency -> SAR with an APPROVED, date-specific FX rate (`fx_rates`, status Approved, rate_date <= price date, not past valid_until)
  2. unit -> resource unit with the registry's fixed physical factor (length/area/volume/mass only; never time or count)
  3. VAT: tax-inclusive -> exclusive with an APPROVED tax category valid on the price date (rates are stored VAT-exclusive)
Not done, by design: regional multipliers, index-based inflation of a unit price, quantity-break or delivery/installation adjustments
without explicit recorded amounts.  If any needed input is missing the result is `complete=False` with the reasons; nothing is guessed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from ..core.money import D_opt
from ..core.timeutil import parse_date
from ..core.units import registry
from ..database import Database

DEFAULT_TAX_CATEGORY = "VAT-STD"


@dataclass
class Normalisation:
    price: Decimal | None
    currency: str
    unit: str | None
    complete: bool
    steps: list[dict] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    changed: bool = False

    @property
    def method(self) -> str:
        if not self.steps:
            return "none (original price already in SAR, resource unit, VAT-exclusive)" if self.complete else "not normalised"
        return "; ".join(s["text"] for s in self.steps)

    def as_json(self) -> dict:
        return {"price": None if self.price is None else str(self.price), "currency": self.currency, "unit": self.unit, "complete": self.complete,
                "steps": self.steps, "unresolved": self.unresolved}


def approved_fx(db: Database, frm: str, to: str, on: date) -> dict | None:
    rows = db.all("SELECT * FROM fx_rates WHERE from_ccy=? AND to_ccy=? AND status='Approved' ORDER BY rate_date DESC", (frm, to))
    for r in rows:
        rd, vu = parse_date(r["rate_date"]), parse_date(r["valid_until"])
        if rd and rd <= on and (vu is None or vu >= on):
            return dict(r)
    return None


def normalise(db: Database, *, price, currency: str | None, unit: str | None, target_unit: str | None, tax_basis: str | None,
              price_date: str | None, tax_category: str = DEFAULT_TAX_CATEGORY) -> Normalisation:
    p = D_opt(price)
    cur = (currency or "").upper()
    res = Normalisation(price=p, currency=cur or "?", unit=unit, complete=False)
    if p is None or p <= 0:
        res.unresolved.append("no positive price to normalise")
        return res
    on = parse_date(price_date)
    if on is None:
        res.unresolved.append("price date unknown - date-specific FX / tax cannot be selected")
        return res
    val = p
    # 1 currency
    if not cur:
        res.unresolved.append("currency unknown")
    elif cur != "SAR":
        fx = approved_fx(db, cur, "SAR", on)
        if fx is None:
            res.unresolved.append(f"no APPROVED {cur}->SAR FX rate valid on {on} (record and approve one in Settings)")
        else:
            val = val * D_opt(fx["rate"])
            res.steps.append({"step": "currency", "text": f"x{fx['rate']} {cur}->SAR (FX #{fx['id']} dated {fx['rate_date']}, source: {fx['source']})",
                              "factor": str(fx["rate"]), "fx_id": fx["id"]})
            res.changed = True
        res.currency = "SAR" if fx else cur
    else:
        res.currency = "SAR"
    # 2 unit
    reg = registry(db)
    if target_unit and unit and unit != target_unit:
        if reg.can_convert(unit, target_unit):
            f = reg.factor(unit, target_unit)               # 1 `unit` = f `target_unit`  ->  price per target = price / f
            val = val / f
            res.steps.append({"step": "unit", "text": f"/{f.normalize():f} per {unit}->{target_unit} (fixed physical factor)", "factor": str(f)})
            res.unit = target_unit
            res.changed = True
        else:
            res.unresolved.append(f"unit '{unit}' is not convertible to '{target_unit}' without an approved conversion assumption")
    elif not unit:
        res.unresolved.append("unit unknown")
    # 3 VAT
    tb = (tax_basis or "Unknown")
    if tb == "Included":
        from ..estimators.estimate import tax_rate_for
        rate, status, note = tax_rate_for(db, tax_category, on, include_unapproved=False)
        if rate is None:
            res.unresolved.append(f"price is VAT-inclusive but no APPROVED {tax_category} rate is valid on {on}: {note}")
        else:
            val = val / (1 + rate / 100)
            res.steps.append({"step": "tax", "text": f"/(1+{rate}%) VAT-inclusive -> VAT-exclusive ({tax_category}, approved)", "rate_pct": str(rate)})
            res.changed = True
    elif tb != "Excluded":
        res.unresolved.append("VAT treatment unknown (included / excluded must be confirmed)")
    if res.unresolved:
        res.price = None
        res.complete = False
        return res
    res.price = val.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    res.complete = True
    return res
