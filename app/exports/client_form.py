"""Fill a CLIENT-SUPPLIED schedule-of-rates / tender-form workbook from the pricing schedule using a user-written mapping. Nothing is invented:
rows are matched on the item code, only the mapped cells are written, formulas are never overwritten, and unmatched rows on either side are reported.

mapping (JSON):
  {"sheet": "Schedule of Rates", "first_row": 8, "last_row": 400 (optional), "key_column": "A",
   "columns": {"quantity": "E", "unit": "D", "unit_rate": "F", "amount": "G"},          # any of quantity, unit, unit_rate, amount, description
   "totals": {"total_pre_tax": "G410", "tax_total": "G411", "total_incl_tax": "G412"},   # optional single cells
   "banner_cell": "A1"}                                                                   # optional: receives the PRELIMINARY / status banner
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

from ..core.errors import ValidationFailed
from ..core.money import ZERO

FIELDS = {"quantity", "unit", "unit_rate", "amount", "description"}
TOTALS = {"total_pre_tax", "tax_total", "total_incl_tax"}


def validate_mapping(m: dict) -> dict:
    if not isinstance(m, dict):
        raise ValidationFailed("mapping must be a JSON object.", code="FORM_MAPPING")
    for k in ("sheet", "first_row", "key_column", "columns"):
        if m.get(k) in (None, "", {}):
            raise ValidationFailed(f"mapping needs '{k}'.", code="FORM_MAPPING")
    bad = set(m["columns"]) - FIELDS
    if bad:
        raise ValidationFailed(f"mapping.columns may only map {sorted(FIELDS)} (got {sorted(bad)}).", code="FORM_MAPPING")
    if not m["columns"]:
        raise ValidationFailed("mapping.columns is empty.", code="FORM_MAPPING")
    bad = set(m.get("totals") or {}) - TOTALS
    if bad:
        raise ValidationFailed(f"mapping.totals may only map {sorted(TOTALS)}.", code="FORM_MAPPING")
    if not isinstance(m["first_row"], int) or m["first_row"] < 1:
        raise ValidationFailed("first_row must be a positive integer.", code="FORM_MAPPING")
    return m


def fill(est, template: Path, mapping: dict, out: Path, *, banner: str | None) -> dict:
    m = validate_mapping(mapping)
    wb = load_workbook(template)
    if m["sheet"] not in wb.sheetnames:
        raise ValidationFailed(f"Template has no sheet '{m['sheet']}' (has {wb.sheetnames}).", code="FORM_MAPPING")
    ws = wb[m["sheet"]]
    sch = est.schedule
    if sch is None:
        raise ValidationFailed("There is no pricing schedule (commercial policy unresolved).", code="FORM_NO_SCHEDULE")
    by_code: dict[str, object] = {}
    for l in sch.lines:
        by_code.setdefault(str(l.item_code or l.item_key).strip(), l)
    last = m.get("last_row") or ws.max_row
    filled, no_match, skipped, used = [], [], [], set()
    total = ZERO
    for r in range(m["first_row"], last + 1):
        key = ws[f"{m['key_column']}{r}"].value
        if key is None or str(key).strip() == "":
            continue
        k = str(key).strip()
        l = by_code.get(k)
        if l is None:
            no_match.append(dict(row=r, key=k))
            continue
        used.add(k)
        if l.status in ("Unpriced", "Excluded") or l.amount is None:
            skipped.append(dict(row=r, key=k, reason=l.status))
            continue
        vals = {"quantity": l.quantity, "unit": l.unit, "unit_rate": l.unit_rate, "amount": l.amount, "description": l.description}
        for fld, col in m["columns"].items():
            cell = ws[f"{col}{r}"]
            if isinstance(cell.value, str) and cell.value.startswith("="):
                skipped.append(dict(row=r, key=k, reason=f"{fld}: template cell holds a formula; left untouched"))
                continue
            v = vals[fld]
            cell.value = float(v) if isinstance(v, Decimal) else v
        total += l.amount or ZERO
        filled.append(dict(row=r, key=k, amount=l.amount))
    unplaced = sorted(set(by_code) - used)
    t = {}
    if m.get("totals"):
        c = est.commercial
        tvals = {"total_pre_tax": sch.total_pre_tax, "tax_total": c.tax_total if c else None,
                 "total_incl_tax": (sch.total_pre_tax + c.tax_total) if (c and c.tax_total is not None) else None}
        for fld, ref in m["totals"].items():
            v = tvals[fld]
            if v is None:
                t[fld] = "unresolved (left blank)"
                continue
            ws[ref].value = float(v)
            t[fld] = ref
    if banner and m.get("banner_cell"):
        ws[m["banner_cell"]].value = banner
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return dict(file=str(out), rows_filled=len(filled), filled_amount_total=total, schedule_items_subtotal=sch.subtotal_items,
                template_rows_without_schedule_item=no_match, schedule_items_not_in_template=unplaced, skipped=skipped, totals_written=t,
                ties_out=(total == sch.subtotal_items and not unplaced and not skipped))
