"""Manual public-dataset / supplier-list import -> rate candidates, with a manifest, validation report and dry-run.

Supports CSV, XLSX and JSON.  Rows that fail validation are rejected with their reason (never silently fixed); rows that pass become
review-queue candidates - not rates.  Importing the exact same file twice is refused.  Original files are stored untouched.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from ..approvals import engine as approvals
from ..core.errors import Conflict, ValidationFailed
from ..core.timeutil import today_iso
from ..database import Database
from ..imports.readers import read_sheet, sha256_file
from ..core.units import registry
from ..services import rates as rates_svc
from . import candidates as cand
from . import manifest as mf

SYN = {
    "resource_id": ["resource id", "resource_id", "resource", "res id"],
    "description": ["description", "desc", "item", "product", "product name", "name", "description (for new resources)"],
    "specification": ["specification", "spec", "specs", "specification / notes", "technical specification"],
    "unit": ["unit", "uom"],
    "original_price": ["unit price", "unit_price", "rate", "price", "unit rate", "original price", "price (sar)"],
    "currency": ["currency", "ccy"],
    "effective_date": ["price_date", "price date", "effective date", "effective_date", "date"],
    "valid_until": ["valid_until", "valid until", "validity", "expiry", "expiry date"],
    "retrieved_at": ["retrieved_at", "retrieved", "retrieval date", "date retrieved", "accessed"],
    "source_published_at": ["publication date", "published", "published_at", "date published"],
    "source_url": ["source_url", "source url", "url", "link", "source"],
    "source_name": ["source_name", "source name", "supplier", "vendor", "publisher", "supplier / source name"],
    "source_type": ["source type"],
    "new_item_type": ["new item type"],
    "cost_code": ["trade code", "cost code"],
    "confidence": ["confidence"],
    "tax_basis": ["tax_basis", "tax basis", "vat", "vat basis", "vat treatment"],
    "delivery_basis": ["delivery_basis", "delivery basis", "delivery", "incoterm"],
    "installation_included": ["installation_included", "installation", "installed"],
    "price_kind": ["price_kind", "price kind", "price type"],
    "evidence_snippet": ["evidence", "evidence / reference", "snippet", "note", "notes", "remarks"],
}
FIELDS_REQUIRED_HEADER = ("original_price",)


def _cell(v: Any) -> Any:
    if hasattr(v, "date") and callable(v.date):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return None if v in (None, "") else (str(v).strip() if not isinstance(v, (int, float)) else v)


def read_rows(path: Path, sheet: str | None = None, mapping: dict | None = None, header_row: int | None = None) -> list[tuple[int, dict]]:
    path = Path(path)
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as e:
            raise ValidationFailed(f"Malformed JSON: {e}", code="MALFORMED_FILE")
        if isinstance(data, dict):
            data = data.get("rates") or data.get("candidates") or data.get("data") or data.get("results") or []
        if not isinstance(data, list) or not data:
            raise ValidationFailed("No rows found in the JSON file (expected a list or {'rates': [...]}).", code="NO_RECORDS")
        out = []
        for i, rec in enumerate(data, 1):
            norm = {}
            for f, syns in SYN.items():
                for k, v in rec.items():
                    if k.strip().lower() in syns or k == f:
                        norm[f] = _cell(v)
                        break
            out.append((i, norm))
        return out
    from ..imports.readers import list_sheets
    if sheet is None and mapping is None and path.suffix.lower() == ".xlsx" and "Rate Dataset" not in list_sheets(path):        # a sheet named 'Rate Dataset' is the ingestion sheet of the shipped template
        found = []                                                    # every sheet that has a price column and a resource id / description column (one sheet per trade is the norm)
        for n in list_sheets(path):
            rs_n = read_sheet(path, n)
            h, c = _detect(rs_n)
            if h is not None:
                found.append((n, rs_n, h, c))
        if len(found) > 1:
            out_all = []
            for n, rs_n, h, c in found:
                for rn, cells in rs_n.rows[h + 1:]:
                    if all(x in (None, "") for x in cells):
                        continue
                    out_all.append((f"{n}!{rn}", {f: _cell(cells[i]) if i < len(cells) else None for f, i in c.items()}))
            return out_all
        if found:
            sheet = found[0][0]
    sh = sheet or ("Rate Dataset" if path.suffix.lower() == ".xlsx" and "Rate Dataset" in list_sheets(path) else None)
    rs = read_sheet(path, sh)
    if mapping is not None:                                           # the person mapped the columns by hand
        cmap = {f: int(i) for f, i in mapping.items() if i not in (None, "")}
        if "original_price" not in cmap or not ({"resource_id", "description"} & set(cmap)):
            raise ValidationFailed("Map at least the unit price column and a resource id or description column.", code="MAPPING_INCOMPLETE")
        hidx = next((i for i, (rn, _) in enumerate(rs.rows) if rn == header_row), -1) if header_row else -1
    else:
        hidx, cmap = _detect(rs)
        if hidx is None:
            raise ValidationFailed("No header row found: need a price column and a resource id or description column. Use the column-mapping step to point at the right columns.", code="NO_HEADER")
    out = []
    for rn, cells in rs.rows[hidx + 1:]:
        if all(c in (None, "") for c in cells):
            continue
        out.append((rn, {f: _cell(cells[i]) if i < len(cells) else None for f, i in cmap.items()}))
    return out


def _detect(rs) -> tuple[int | None, dict]:
    hidx, cmap = None, {}
    for idx, (rn, cells) in enumerate(rs.rows[:40]):
        m: dict[str, int] = {}
        for f, syns in SYN.items():
            for ci, c in enumerate(cells):
                if str(c or "").strip().lower() in syns and ci not in m.values():
                    m[f] = ci
                    break
        if "original_price" in m and ("resource_id" in m or "description" in m) and (hidx is None or len(m) >= len(cmap)):
            hidx, cmap = idx, m
    return hidx, cmap


MAP_FIELDS = [("resource_id", "Resource ID"), ("description", "Description"), ("specification", "Specification"), ("unit", "Unit"), ("original_price", "Unit price"),
              ("currency", "Currency"), ("effective_date", "Price date"), ("valid_until", "Valid until"), ("source_url", "Source URL or reference"), ("source_name", "Supplier / source name"),
              ("tax_basis", "Tax (VAT) basis"), ("delivery_basis", "Delivery basis"), ("installation_included", "Installation included"), ("price_kind", "Price kind"), ("evidence_snippet", "Evidence / notes"),
              ("source_type", "Source type"), ("new_item_type", "New item type (create a catalogue item)"), ("cost_code", "Trade code (cost code)"), ("confidence", "Confidence")]


# Keyword suggestions for headings that are not an exact synonym (never used to import by themselves: the person confirms the mapping).
_KEYWORDS = [("original_price", ("price", "rate", "cost per", "cost/unit", "amount")), ("currency", ("currency", "ccy")), ("resource_id", ("resource id", "item no", "item code", "item #", "code", "mat id", "sku")),
             ("description", ("description", "product", "item name", "name", "material")), ("unit", ("uom", "unit of", "measure", "unit")), ("valid_until", ("valid", "expiry", "expires")),
             ("effective_date", ("date",)), ("tax_basis", ("vat", "tax")), ("delivery_basis", ("delivery", "incoterm")), ("evidence_snippet", ("note", "remark", "evidence", "comment")),
             ("source_url", ("quote ref", "reference", "ref", "url", "link"))]


def _suggest(header_cells: list) -> dict:
    out: dict[str, int] = {}
    taken: set[int] = set()
    for f, words in _KEYWORDS:
        for w in words:
            hit = next((i for i, c in enumerate(header_cells) if i not in taken and w in str(c or "").strip().lower() and str(c or "").strip()), None)
            if hit is not None:
                out[f] = hit
                taken.add(hit)
                break
    return out


def _guess_header(rs) -> int:
    """Index of the most heading-like row among the first 40: the row with the most non-empty text cells (title rows have one)."""
    best, best_n = 0, -1
    for i, (_, cells) in enumerate(rs.rows[:40]):
        n = sum(1 for c in cells if isinstance(c, str) and c.strip())
        if n > best_n:
            best, best_n = i, n
    return best


def inspect_file(path: Path, sheet: str | None = None, header_row: int | None = None, max_sample: int = 5) -> dict:
    """What a person needs to map the columns of any rate file: sheets, the (detected or chosen) header row, each column with sample values and the automatically
    matched field. Never changes the file."""
    from ..imports.readers import list_sheets
    path = Path(path)
    if path.suffix.lower() == ".json":
        raise ValidationFailed("Column mapping applies to Excel and CSV files; JSON rows are read by field name.", code="MAPPING_NA")
    sheets = list_sheets(path)
    sh = sheet
    if sh is None and path.suffix.lower() == ".xlsx" and "Rate Dataset" not in sheets:
        sh = next((n for n in sheets if _detect(read_sheet(path, n))[0] is not None), "Rate Dataset" if "Rate Dataset" in sheets else None)      # first sheet that holds a price table
    if sh is None and "Rate Dataset" in sheets:
        sh = "Rate Dataset"
    rs = read_sheet(path, sh)
    hidx, auto = _detect(rs)
    if header_row:
        hidx = next((i for i, (rn, _) in enumerate(rs.rows) if rn == header_row), hidx)
        auto = {}
        syn_hit = {}
        for ci, c in enumerate(rs.rows[hidx][1] if hidx is not None else []):
            for f, syns in SYN.items():
                if f not in syn_hit and str(c or "").strip().lower() in syns:
                    syn_hit[f] = ci
        auto = syn_hit
    suggested = False
    if hidx is None:                                                  # nothing recognised exactly: guess the heading row and suggest columns by keyword
        hidx = _guess_header(rs) if rs.rows else 0
        auto = _suggest(rs.rows[hidx][1]) if rs.rows else {}
        suggested = bool(auto)
    hrow = rs.rows[hidx] if rs.rows else (0, [])
    width = max((len(c) for _, c in rs.rows[:60]), default=0)
    body = [c for _, c in rs.rows[hidx + 1:] if any(x not in (None, "") for x in c)]
    cols = []
    for i in range(width):
        head = hrow[1][i] if i < len(hrow[1]) else None
        cols.append(dict(index=i, header=("" if head is None else str(head)), sample=[_cell(r[i]) for r in body[:max_sample] if i < len(r) and r[i] not in (None, "")][:max_sample],
                         field=next((f for f, ci in auto.items() if ci == i), "")))
    price_sheets = [n for n in sheets if path.suffix.lower() == ".xlsx" and "Rate Dataset" not in sheets and _detect(read_sheet(path, n))[0] is not None]
    return dict(price_sheets=price_sheets, multi=len(price_sheets) > 1, sheets=sheets, sheet=rs.name, header_row=hrow[0], columns=cols, auto=auto, rows=len(body), suggested=suggested,
                detected=bool(not suggested and "original_price" in auto and ({"resource_id", "description"} & set(auto))),
                warnings=list(rs.warnings))


def import_rates_file(db: Database, actor, path: Path, *, source_id: str | None = None, source_name: str | None = None, source_url: str | None = None,
                      source_type: str = "Manual dataset", description: str = "", dry_run: bool = False, retrieved_at: str | None = None,
                      sheet: str | None = None, adapter: str = "manual-file", extra_flags: list[str] | None = None,
                      confidence: str = "Unverified", mapping: dict | None = None, header_row: int | None = None,
                      default_currency: str | None = None, default_date: str | None = None, default_tax_basis: str | None = None) -> dict:
    if hasattr(actor, "is_ai"):
        approvals.require_author(actor)
    path = Path(path)
    if source_id and not db.one("SELECT 1 FROM sources WHERE source_id=?", (source_id,)):
        raise ValidationFailed(f"Source {source_id} is not in the Source Register (data/sources/source_register.csv).", code="SOURCE_UNKNOWN")
    if source_id:
        basis = str(db.scalar("SELECT unit_price_basis FROM sources WHERE source_id=?", (source_id,)) or "").strip().lower()
        stype = str(db.scalar("SELECT type FROM sources WHERE source_id=?", (source_id,)) or "").strip().lower()
        if basis.startswith("index") or "official statistics" in stype:
            raise ValidationFailed(f"Source {source_id} publishes index/statistical series, not unit prices; its data cannot be imported as rate candidates. Use `index import` "
                                   "(index data is reference only and can never price a line).", code="SOURCE_NOT_PRICE")
    rows = read_rows(path, sheet, mapping, header_row)
    sha = sha256_file(path)
    if not dry_run:
        mf.refuse_duplicate(db, sha, "rates")
    retrieved = retrieved_at or today_iso()
    stored = None
    if not dry_run:
        stored, _ = mf.store_original(path)
    ref = f"uploaded-file:{(stored or path).name}"
    errors: list[dict] = []
    ok_rows: list[tuple[int, dict]] = []
    seen: set[str] = set()
    not_filled = unchanged = replaces = 0
    replace_map: dict = {}
    new_items: dict = {}
    for rn, r in rows:
        d = dict(r)
        if d.get("resource_id") and str(d.get("original_price") if d.get("original_price") is not None else "").strip() == "":
            not_filled += 1                                   # a pre-listed resource whose price was left blank: stays missing, is not a candidate and not an error
            continue
        new_item = None
        if not d.get("resource_id") and d.get("new_item_type"):                       # the person asked, row by row, for a new catalogue item to be created for this price
            nt = str(d["new_item_type"]).strip().lower()
            ures = registry(db).resolve(d.get("unit"))
            if nt not in rates_svc.RESOURCE_TYPES or not d.get("description") or ures.status != "ok":
                errors.append({"row": rn, "errors": ["a new item needs a type (material, labour, plant, equipment or subcontract), a description and a unit the system understands"]})
                continue
            if d.get("cost_code") and not db.one("SELECT 1 FROM cost_codes WHERE code=?", (d["cost_code"],)):
                errors.append({"row": rn, "errors": [f"trade code '{d['cost_code']}' is not a known cost code"]})
                continue
            found = db.one("SELECT id FROM resources WHERE is_active=1 AND resource_type=? AND description=? AND unit=?", (nt, d["description"], ures.code))
            if found:
                d["resource_id"] = found["id"]                                      # the same item was created by an earlier upload: reuse it
            else:
                new_item = (nt, d["description"], ures.code, d.get("cost_code") or None)
        d.pop("new_item_type", None)
        d["source_type"] = d["source_type"] if d.get("source_type") in cand.SOURCE_TYPES else source_type          # a 'Source type' column in the file wins; otherwise the one chosen for the upload
        d["source_name"] = d.get("source_name") or source_name
        d["source_id"] = source_id
        d["source_url"] = d.get("source_url") or source_url or ref
        d["retrieved_at"] = d.get("retrieved_at") or retrieved
        d["extraction_method"] = f"File import ({path.suffix.lstrip('.').upper()}) row {rn}"
        d["confidence"] = d["confidence"] if d.get("confidence") in ("High", "Medium", "Low", "Unverified") else confidence
        d["flags"] = list(extra_flags or [])
        d["evidence_snippet"] = d.get("evidence_snippet") or f"{path.name} row {rn}"
        if not d.get("price_kind"):
            d["price_kind"] = "Quoted" if source_type == "Quotation" else "List price"
        if default_currency and not d.get("currency"):
            d["currency"] = default_currency.strip().upper()              # stated explicitly by the person for the whole file (recorded in the manifest), never assumed
        if default_tax_basis in ("Included", "Excluded") and not d.get("tax_basis"):
            d["tax_basis"] = default_tax_basis                            # stated by the person for the whole file (recorded in the manifest)
        if default_date and not d.get("effective_date"):
            d["effective_date"] = default_date
        if not d.get("currency"):
            errors.append({"row": rn, "errors": ["currency is required (never assumed)"]})
            continue
        errs, _ = cand.validate(db, d)
        if errs:
            errors.append({"row": rn, "errors": errs})
            continue
        key = cand._row_hash({**d, "original_price": d.get("original_price"), "original_currency": d["currency"].upper(), "original_unit": d.get("unit")})
        if key in seen:
            errors.append({"row": rn, "errors": ["duplicate row within this file"]})
            continue
        seen.add(key)
        verdict, prior_ids = cand.compare_with_earlier_upload(db, d)
        if verdict == "unchanged":
            unchanged += 1                                              # the same price from the same source was already uploaded: nothing to do
            continue
        replaces += len(prior_ids)
        ok_rows.append((rn, d))
        replace_map[rn] = prior_ids
        if new_item:
            new_items[rn] = new_item
    ids: list[int] = []
    if not dry_run:
        with db.tx():
            for rn, d in ok_rows:
                try:
                    if rn in new_items:
                        nt, desc, un, cc = new_items[rn]
                        d["resource_id"] = rates_svc.create_resource(db, actor, resource_type=nt, description=desc, unit=un, cost_code=cc)
                    new_id = cand.create_candidate(db, actor, d, manifest_id=None)
                    ids.append(new_id)
                    for old_id in replace_map.get(rn, []):
                        cand.supersede(db, actor, old_id, new_id)
                except (ValidationFailed, Conflict) as e:
                    errors.append({"row": rn, "errors": [e.message]})
    parsing = {"file": path.name, "format": path.suffix.lstrip("."), "rows_read": len(rows), "source_type": source_type, "columns": sorted({k for _, r in rows for k in r}),
               "not_filled_rows": not_filled, "unchanged_rows": unchanged, "new_items": len(new_items), "replaced_rows": replaces, "mapping": mapping, "header_row": header_row, "default_currency": default_currency, "default_date": default_date, "default_tax_basis": default_tax_basis}
    mid = mf.write_manifest(db, actor, kind="rates", adapter=adapter, source_id=source_id, source_name=source_name, source_url=source_url,
                            original_path=str(path), stored_path=stored, sha=sha, description=description, dry_run=dry_run, parsing=parsing,
                            accepted=len(ids) if not dry_run else len(ok_rows), rejected=len(errors), errors=errors, candidate_ids=ids)
    if ids:
        db.execute(f"UPDATE rate_candidates SET manifest_id=? WHERE id IN ({','.join('?' * len(ids))})", [mid, *ids])
    return {"manifest_id": mid, "dry_run": dry_run, "rows_read": len(rows), "accepted": len(ids) if not dry_run else len(ok_rows),
            "rejected": len(errors), "not_filled": not_filled, "unchanged": unchanged, "replaces": replaces, "new_items": len(new_items), "errors": errors, "candidate_ids": ids, "sha256": sha,
            "needs_vat": sum(1 for _, d in ok_rows if d.get("tax_basis") not in ("Included", "Excluded"))}
