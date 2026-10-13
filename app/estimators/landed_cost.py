"""Landed-cost build-up from a supplier base price and user-supplied terms (freight, insurance, duty, clearance, port, local haulage ...).

Pure Decimal arithmetic. Every percentage, amount and currency comes from the terms the company supplied and a person approved; nothing is assumed.
Components are applied in the order given:
  pct         amount = value% x reference, where reference = 'base' | 'cumulative' (base + everything so far) | a list of earlier component names (and/or 'base')
  per_unit    amount = value per unit of the priced quantity
  per_shipment amount = value / units_per_shipment
Amounts are converted into the output currency with the supplied FX function. Exposure by currency is tracked through percentage components pro rata.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Callable

from ..core.errors import ValidationFailed
from ..core.money import ZERO, D

KINDS = ("pct", "per_unit", "per_shipment")


def validate_components(components: list[dict]) -> list[dict]:
    if not isinstance(components, list) or not components:
        raise ValidationFailed("components must be a non-empty list.", code="PARAM_FIELD")
    seen: list[str] = []
    out = []
    for c in components:
        if set(c) - {"name", "kind", "value", "currency", "applies_to"}:
            raise ValidationFailed(f"Unknown component field(s): {sorted(set(c) - {'name', 'kind', 'value', 'currency', 'applies_to'})}", code="PARAM_FIELD")
        name = str(c.get("name", "")).strip()
        if not name or name in seen or name in ("base", "cumulative"):
            raise ValidationFailed(f"Component name missing, reserved or duplicated: '{name}'.", code="PARAM_FIELD")
        if c.get("kind") not in KINDS:
            raise ValidationFailed(f"{name}: kind must be one of {KINDS}.", code="PARAM_FIELD")
        try:
            v = Decimal(str(c.get("value")))
        except Exception:
            raise ValidationFailed(f"{name}: value must be a number.", code="PARAM_FIELD")
        if not v.is_finite() or v < 0:
            raise ValidationFailed(f"{name}: value must be >= 0.", code="PARAM_FIELD")
        ref = c.get("applies_to", "base")
        if c["kind"] == "pct":
            refs = [ref] if isinstance(ref, str) and ref in ("base", "cumulative") else ([r.strip() for r in ref.split(",")] if isinstance(ref, str) else list(ref))
            for r in refs:
                if r not in ("base", "cumulative") and r not in seen:
                    raise ValidationFailed(f"{name}: applies_to '{r}' is not an earlier component.", code="PARAM_FIELD")
            ref = refs[0] if len(refs) == 1 and refs[0] in ("base", "cumulative") else refs
        out.append({"name": name, "kind": c["kind"], "value": format(v.normalize(), "f") if v else "0", "currency": c.get("currency") or None, "applies_to": ref})
        seen.append(name)
    return out


def landed(base_price: Decimal, base_currency: str, components: list[dict], output_currency: str, fx: Callable[[str], Decimal | None],
           units_per_shipment: Decimal | None = None) -> dict:
    """Returns {'landed': Decimal, 'base_out', 'lines': [...], 'exposure': {ccy: amount}}. Raises if an FX rate is missing for a currency actually used."""
    def rate(ccy: str | None) -> Decimal:
        c = ccy or base_currency
        if c == output_currency:
            return Decimal(1)
        r = fx(c)
        if r is None:
            raise ValidationFailed(f"No approved FX rate {c}->{output_currency}.", code="FX_MISSING")
        return r

    base_out = D(base_price) * rate(base_currency)
    amounts: dict[str, Decimal] = {"base": base_out}
    expo: dict[str, dict[str, Decimal]] = {"base": {base_currency: base_out}}
    cum = base_out
    lines = []
    for c in components:
        k, v = c["kind"], D(c["value"])
        if k == "pct":
            refs = ["base", *list(amounts)[1:]] if c["applies_to"] == "cumulative" else ([c["applies_to"]] if isinstance(c["applies_to"], str) else c["applies_to"])
            ref_amt = sum((amounts[r] for r in refs), ZERO)
            amt = ref_amt * v / 100
            e: dict[str, Decimal] = {}
            for r in refs:
                for ccy, a in expo[r].items():
                    e[ccy] = e.get(ccy, ZERO) + (a * v / 100)
            basis = f"{v}% of {'+'.join(refs)} ({ref_amt})"
        elif k == "per_unit":
            amt = v * rate(c.get("currency"))
            e = {(c.get("currency") or base_currency): amt}
            basis = f"{v} {c.get('currency') or base_currency} per unit"
        else:
            if not units_per_shipment or units_per_shipment <= 0:
                raise ValidationFailed(f"{c['name']}: per_shipment needs units_per_shipment > 0 in the terms.", code="LANDED_SHIPMENT_UNITS")
            amt = v * rate(c.get("currency")) / units_per_shipment
            e = {(c.get("currency") or base_currency): amt}
            basis = f"{v} {c.get('currency') or base_currency} per shipment / {units_per_shipment} units"
        amounts[c["name"]] = amt
        expo[c["name"]] = e
        cum += amt
        lines.append({"name": c["name"], "kind": k, "amount": amt, "basis": basis})
    exposure: dict[str, Decimal] = {}
    for d in expo.values():
        for ccy, a in d.items():
            exposure[ccy] = exposure.get(ccy, ZERO) + a
    return {"landed": cum, "base_out": base_out, "lines": lines, "exposure": exposure, "output_currency": output_currency}
