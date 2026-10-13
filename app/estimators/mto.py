"""Material-take-off derivation: (human-measured driver quantity) x (company-approved factor) -> resource quantities.

Pure. It never measures anything and never supplies a factor: a slot without an approved factor is reported as MISSING and produces no quantity.
qty = driver x factor x (1 + waste%/100), rounded half-up to QTY_DP decimals (stated, so results are reproducible).
"""
from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from ..core.errors import ValidationFailed
from ..core.money import ZERO, D

QTY_DP = 6


def load_templates(data_dir: Path) -> dict[str, dict]:
    p = Path(data_dir) / "mto" / "templates.json"
    if not p.exists():
        return {}
    return {t["code"]: t for t in json.loads(p.read_text(encoding="utf-8"))["templates"]}


def derive(template: dict, driver_qty: Decimal, factors: dict[str, dict], skip: set[str] | None = None) -> dict:
    """factors: slot -> {'resource_id','factor','waste_pct','ref'} (approved only; the caller filters). Returns lines, missing slots and skipped slots."""
    if driver_qty is None or driver_qty < 0:
        raise ValidationFailed("Driver quantity must be a non-negative number entered by the estimator.", code="MTO_DRIVER")
    skip = skip or set()
    unknown_skip = skip - {s["slot"] for s in template["slots"]}
    if unknown_skip:
        raise ValidationFailed(f"Unknown slot(s) to skip: {sorted(unknown_skip)}", code="MTO_SLOT")
    lines, missing, skipped = [], [], []
    q = Decimal(1).scaleb(-QTY_DP)
    for s in template["slots"]:
        sl = s["slot"]
        if sl in skip:
            skipped.append(sl)
            continue
        f = factors.get(sl)
        if f is None:
            missing.append(sl)
            continue
        fac, waste = D(f["factor"]), D(f.get("waste_pct") or "0")
        qty = (driver_qty * fac * (ZERO + 1 + waste / 100)).quantize(q, ROUND_HALF_UP)
        lines.append(dict(slot=sl, description=s["description"], resource_id=f["resource_id"], qty=qty, factor=fac, waste_pct=waste, ref=f.get("ref"),
                          basis=f"{driver_qty} {template['driver_unit']} x {fac}" + (f" x (1+{waste}%)" if waste else "") + f" = {qty}"))
    return {"template": template["code"], "driver_qty": driver_qty, "driver_unit": template["driver_unit"], "lines": lines, "missing": missing, "skipped": skipped}
