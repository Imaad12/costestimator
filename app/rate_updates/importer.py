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
    "source_name": ["source_name", "source name", "supplier", "vendor", "publisher"],
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


def read_rows(path: Path, sheet: str | None = None) -> list[tuple[int, dict]]:
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
    sh = sheet or ("Rate Dataset" if path.suffix.lower() == ".xlsx" and "Rate Dataset" in list_sheets(path) else None)
    rs = read_sheet(path, sh)
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
    if hidx is None:
        raise ValidationFailed("No header row found: need a price column and a resource id or description column.", code="NO_HEADER")
    out = []
    for rn, cells in rs.rows[hidx + 1:]:
        if all(c in (None, "") for c in cells):
            continue
        out.append((rn, {f: _cell(cells[i]) if i < len(cells) else None for f, i in cmap.items()}))
    return out


def import_rates_file(db: Database, actor, path: Path, *, source_id: str | None = None, source_name: str | None = None, source_url: str | None = None,
                      source_type: str = "Manual dataset", description: str = "", dry_run: bool = False, retrieved_at: str | None = None,
                      sheet: str | None = None, adapter: str = "manual-file", extra_flags: list[str] | None = None,
                      confidence: str = "Unverified") -> dict:
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
    rows = read_rows(path, sheet)
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
    for rn, r in rows:
        d = dict(r)
        d.setdefault("source_type", source_type)
        d["source_type"] = source_type
        d["source_name"] = d.get("source_name") or source_name
        d["source_id"] = source_id
        d["source_url"] = d.get("source_url") or source_url or ref
        d["retrieved_at"] = d.get("retrieved_at") or retrieved
        d["extraction_method"] = f"File import ({path.suffix.lstrip('.').upper()}) row {rn}"
        d["confidence"] = confidence
        d["flags"] = list(extra_flags or [])
        d["evidence_snippet"] = d.get("evidence_snippet") or f"{path.name} row {rn}"
        if not d.get("price_kind"):
            d["price_kind"] = "Quoted" if source_type == "Quotation" else "List price"
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
        ok_rows.append((rn, d))
    ids: list[int] = []
    if not dry_run:
        with db.tx():
            for rn, d in ok_rows:
                try:
                    ids.append(cand.create_candidate(db, actor, d, manifest_id=None))
                except (ValidationFailed, Conflict) as e:
                    errors.append({"row": rn, "errors": [e.message]})
    parsing = {"file": path.name, "format": path.suffix.lstrip("."), "rows_read": len(rows), "source_type": source_type, "columns": sorted({k for _, r in rows for k in r})}
    mid = mf.write_manifest(db, actor, kind="rates", adapter=adapter, source_id=source_id, source_name=source_name, source_url=source_url,
                            original_path=str(path), stored_path=stored, sha=sha, description=description, dry_run=dry_run, parsing=parsing,
                            accepted=len(ids) if not dry_run else len(ok_rows), rejected=len(errors), errors=errors, candidate_ids=ids)
    if ids:
        db.execute(f"UPDATE rate_candidates SET manifest_id=? WHERE id IN ({','.join('?' * len(ids))})", [mid, *ids])
    return {"manifest_id": mid, "dry_run": dry_run, "rows_read": len(rows), "accepted": len(ids) if not dry_run else len(ok_rows),
            "rejected": len(errors), "errors": errors, "candidate_ids": ids, "sha256": sha}
