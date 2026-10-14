"""BOQ / takeoff import: preview, header detection, mapping, validation, traceable persistence, re-import diff.

Rules enforced here
* Quantities are never invented or altered: `quantity_original` keeps the imported text forever; on re-import any
  difference becomes a PENDING change request, never an overwrite.
* Nothing is silently discarded: blank rows are counted, headings preserved, invalid rows land in boq_rejected_rows
  with a reason, ambiguous/unknown units are flagged (unit stays NULL until a human confirms).
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from ..approvals import engine as approvals
from ..core.errors import ValidationFailed
from ..core.money import D, D_opt, to_text
from ..core.timeutil import now_iso
from ..core.units import registry
from ..database import Database
from ..models.actor import Actor
from ..services import audit, projects
from .readers import RawSheet, list_sheets, read_sheet, sha256_file

FIELDS = ["item_code", "description", "trade", "unit", "quantity", "client_rate", "client_amount", "drawing_ref",
          "spec_ref", "cost_code", "revision"]
REQUIRED = ["description", "unit", "quantity"]

HEADER_SYNONYMS: dict[str, list[str]] = {
    "item_code": ["item", "item no", "item no.", "item number", "item code", "code", "boq code", "boq ref", "ref",
                  "ref.", "no", "no.", "s.no", "s/n", "sr", "sr no", "sl no", "serial", "bill item", "رقم البند", "البند"],
    "description": ["description", "desc", "desc.", "item description", "description of work", "particulars",
                    "work item", "details", "scope", "الوصف", "البيان", "وصف البند"],
    "trade": ["trade", "discipline", "section", "package", "division", "work package", "التخصص"],
    "unit": ["unit", "units", "uom", "u.o.m", "u/m", "measure", "unit of measure", "الوحدة"],
    "quantity": ["qty", "qty.", "quantity", "quantities", "qnty", "quant", "total qty", "الكمية"],
    "client_rate": ["rate", "unit rate", "client rate", "price", "unit price", "rate (sar)", "السعر", "سعر الوحدة"],
    "client_amount": ["amount", "total", "total amount", "value", "amount (sar)", "line total", "الاجمالي", "المبلغ"],
    "drawing_ref": ["drawing", "drawing ref", "dwg", "dwg ref", "drawing no", "drawing reference"],
    "spec_ref": ["spec", "spec ref", "specification", "specification ref", "spec section", "clause", "spec clause"],
    "cost_code": ["cost code", "costcode", "wbs", "internal code", "cost_code"],
    "revision": ["rev", "rev.", "revision"],
}


def _norm_header(h: Any) -> str:
    return re.sub(r"[\s_]+", " ", str(h or "").strip().lower())


@dataclass
class Preview:
    sheets: list[str]
    sheet: str
    header_row: int | None
    columns: list[str]
    proposed_mapping: dict[str, int | None]       # field -> column index (0-based)
    sample_rows: list[list[Any]]
    missing_required: list[str]
    ambiguous_columns: list[str]
    warnings: list[str] = field(default_factory=list)


def mapping_from_row(cells: list[Any]) -> dict[str, int | None]:
    """Column mapping from one explicit header row (used for re-importing generated workbooks)."""
    mapping: dict[str, int | None] = {}
    used: set[int] = set()
    for f, syns in HEADER_SYNONYMS.items():
        hit = None
        for ci, c in enumerate(cells):
            if ci not in used and _norm_header(c) in syns:
                hit = ci
                break
        mapping[f] = hit
        if hit is not None:
            used.add(hit)
    return mapping


def detect_header(rows: list[tuple[int, list[Any]]], scan: int = 40) -> tuple[int | None, dict[str, int | None], list[str]]:
    best = (0, None, {})
    ambiguous: list[str] = []
    for idx, (rn, cells) in enumerate(rows[:scan]):
        mapping: dict[str, int | None] = {}
        used = set()
        score = 0
        for f, syns in HEADER_SYNONYMS.items():
            hit = None
            for ci, c in enumerate(cells):
                if ci in used:
                    continue
                if _norm_header(c) in syns:
                    hit = ci
                    break
            mapping[f] = hit
            if hit is not None:
                used.add(hit)
                score += 1
        if score > best[0]:
            best = (score, idx, mapping)
    if best[0] < 2 or best[1] is None:
        return None, {f: None for f in FIELDS}, []
    # columns whose header matches several fields (e.g. 'no' vs 'item') are reported
    cells = rows[best[1]][1]
    for ci, c in enumerate(cells):
        matches = [f for f, syns in HEADER_SYNONYMS.items() if _norm_header(c) in syns]
        if len(matches) > 1:
            ambiguous.append(f"Column {ci + 1} '{c}' matches {matches}")
    return best[1], best[2], ambiguous


def preview(path: Path, sheet: str | None = None, max_rows: int = 15) -> Preview:
    sheets = list_sheets(Path(path))
    rs = read_sheet(Path(path), sheet)
    hidx, mapping, amb = detect_header(rs.rows)
    cols = [str(c) if c is not None else "" for c in (rs.rows[hidx][1] if hidx is not None else [])]
    sample = [r for _, r in rs.rows[(hidx + 1 if hidx is not None else 0):][:max_rows]]
    missing = [f for f in REQUIRED if mapping.get(f) is None]
    warns = list(rs.warnings)
    if hidx is None:
        warns.append("Could not detect a header row; map columns manually.")
    return Preview(sheets, rs.name, rs.rows[hidx][0] if hidx is not None else None, cols, mapping, sample, missing, amb, warns)


@dataclass
class ParsedRow:
    source_row: int
    kind: str                     # blank / heading / item / rejected
    data: dict
    issues: list[dict]
    raw: dict
    reject_code: str | None = None
    reject_reason: str | None = None


def _cell(cells: list[Any], idx: int | None):
    if idx is None or idx >= len(cells):
        return None
    v = cells[idx]
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def _issue(code: str, msg: str, level: str = "warning") -> dict:
    return {"code": code, "message": msg, "level": level}


def parse_rows(rs: RawSheet, mapping: dict[str, int | None], header_row_number: int | None, reg, *,
               allow_negative: bool = False) -> list[ParsedRow]:
    out: list[ParsedRow] = []
    header_cells = []
    for rn, cells in rs.rows:
        if rn == header_row_number:
            header_cells = [str(c) if c is not None else f"col{i + 1}" for i, c in enumerate(cells)]
    for rn, cells in rs.rows:
        if header_row_number is not None and rn <= header_row_number:
            continue
        raw = {(header_cells[i] if i < len(header_cells) else f"col{i + 1}"): (None if v is None else
               (v.isoformat() if hasattr(v, "isoformat") else v)) for i, v in enumerate(cells)}
        if all(c is None or (isinstance(c, str) and not c.strip()) for c in cells):
            out.append(ParsedRow(rn, "blank", {}, [], raw))
            continue
        d: dict[str, Any] = {f: _cell(cells, mapping.get(f)) for f in FIELDS}
        issues: list[dict] = []
        desc = d["description"]
        qty_raw, unit_raw = d["quantity"], d["unit"]
        has_qty = qty_raw is not None
        has_unit = unit_raw is not None
        if not has_qty and not has_unit and d["client_amount"] is None and d["client_rate"] is None:
            if desc or d["item_code"]:
                out.append(ParsedRow(rn, "heading", d, [], raw))
            else:
                out.append(ParsedRow(rn, "blank", {}, [], raw))
            continue
        # ---- quantity
        qty: Decimal | None = None
        if not has_qty:
            out.append(ParsedRow(rn, "rejected", d, [], raw, "MISSING_QUANTITY",
                                 "Row has a unit/price but no quantity."))
            continue
        try:
            qty = D(qty_raw)
        except ValueError:
            out.append(ParsedRow(rn, "rejected", d, [], raw, "INVALID_QUANTITY",
                                 f"Quantity '{qty_raw}' is not a valid number."))
            continue
        if qty < 0 and not allow_negative:
            out.append(ParsedRow(rn, "rejected", d, [], raw, "NEGATIVE_QUANTITY",
                                 f"Negative quantity {qty} rejected (re-import with allow_negative if a credit is intended)."))
            continue
        d["_qty"] = qty
        if qty == 0:
            issues.append(_issue("ZERO_QUANTITY", "Quantity is zero."))
        # ---- unit
        res = reg.resolve(None if unit_raw is None else str(unit_raw))
        d["_unit_res"] = res
        if res.status != "ok":
            issues.append(_issue("UNIT_" + res.status.upper(), res.message, "error"))
        # ---- description
        if not desc:
            issues.append(_issue("MISSING_DESCRIPTION", "Description is missing.", "error"))
        # ---- rate / amount cross-check
        cr, ca = D_opt(d["client_rate"]), D_opt(d["client_amount"])
        if d["client_rate"] is not None and cr is None:
            issues.append(_issue("INVALID_CLIENT_RATE", f"Client rate '{d['client_rate']}' is not numeric."))
        if cr is not None and ca is not None and abs(cr * qty - ca) > Decimal("0.01") * max(Decimal(1), abs(ca)) / 100:
            issues.append(_issue("CLIENT_AMOUNT_MISMATCH", f"Client amount {ca} differs from qty × rate = {cr * qty}."))
        if not d["item_code"]:
            issues.append(_issue("MISSING_CODE", "No item code; a row-based key was generated."))
        out.append(ParsedRow(rn, "item", d, issues, raw))
    return out


def _clean(v):
    return None if v is None else str(v).strip()


def import_boq(db: Database, actor: Actor, project_id: str, path: Path, *, mapping: dict[str, int | None] | None = None,
               sheet: str | None = None, header_row: int | None = None, revision: str | None = None,
               allow_negative: bool = False, derived_from: dict | None = None) -> dict:
    """Import a measured BOQ. Returns an import summary. Source file is copied (never moved/modified).

    The application does not read PDFs or images (by design: no OCR / PDF-table extraction). A person - or any outside tool - extracts the table into CSV/XLSX and imports THAT file;
    `derived_from` records where it came from: {'source_file', 'source_sha256', 'method', 'note'?}. Such an import is flagged as an UNVERIFIED TRANSCRIPTION until a second person records a check
    (`record_transcription_check`)."""
    approvals.require_author(actor)
    if derived_from is not None:
        need = [k for k in ("source_file", "source_sha256", "method") if not str(derived_from.get(k) or "").strip()]
        if need:
            raise ValidationFailed(f"derived_from needs {need}: say which document the values were taken from, its SHA-256 and how.", code="DERIVED_FROM_INCOMPLETE")
    projects.require_active(db, project_id)
    path = Path(path)
    reg = registry(db)
    rs = read_sheet(path, sheet)
    if header_row is not None and mapping is None:
        mapping = mapping_from_row(next((c for rn, c in rs.rows if rn == header_row), []))
    if header_row is None or mapping is None:
        hidx, auto_map, amb = detect_header(rs.rows)
        if hidx is None and mapping is None:
            raise ValidationFailed("No header row detected. Provide an explicit column mapping.", code="NO_HEADER")
        mapping = mapping or auto_map
        header_row = header_row if header_row is not None else (rs.rows[hidx][0] if hidx is not None else None)
    missing = [f for f in REQUIRED if mapping.get(f) is None]
    if missing:
        raise ValidationFailed(f"Required column(s) not mapped: {missing}. Provide a mapping.", code="MAPPING_INCOMPLETE",
                               details={"missing": missing})
    parsed = parse_rows(rs, mapping, header_row, reg, allow_negative=allow_negative)
    sha = sha256_file(path)
    updir = projects.project_dir(project_id, "uploads")
    stored = updir / f"{sha[:10]}_{path.name}"
    if not stored.exists():
        shutil.copy2(path, stored)  # original upload kept untouched alongside the copy used for the audit trail
    with db.tx():
        iid = db.insert("boq_imports", dict(project_id=project_id, revision=revision, source_file=path.name,
                                            stored_path=str(stored), sha256=sha, sheet=rs.name,
                                            mapping_json=json.dumps(mapping), status="Imported",
                                            imported_by=actor.username, imported_at=now_iso()))
        summary = _persist(db, actor, project_id, iid, path.name, rs.name, parsed, revision)
        summary["warnings"] = rs.warnings
        summary["mapping"] = mapping
        summary["sha256"] = sha
        if derived_from is not None:
            summary["derived_from"] = {k: derived_from.get(k) for k in ("source_file", "source_sha256", "method", "note")}
            summary["unverified_transcription"] = True
        db.update("boq_imports", {"summary_json": summary}, "id=?", (iid,))
        audit.log(db, actor, "boq_import", iid, "import", after={k: summary[k] for k in (
            "rows_read", "items_new", "items_unchanged", "rejected", "change_requests")}, project_id=project_id)
    summary["import_id"] = iid
    return summary


def record_transcription_check(db: Database, actor: Actor, import_id: int, comment: str) -> None:
    """A SECOND person states that the transcribed quantities were compared with the source document. The importer cannot check their own import."""
    approvals.require_author(actor)
    row = db.one("SELECT * FROM boq_imports WHERE id=?", (import_id,))
    if not row:
        raise ValidationFailed(f"Import {import_id} not found.", code="NOT_FOUND")
    summary = json.loads(row["summary_json"] or "{}")
    if not summary.get("unverified_transcription"):
        raise ValidationFailed("This import was not flagged as a transcription.", code="NOT_A_TRANSCRIPTION")
    if not (comment or "").strip():
        raise ValidationFailed("State what was compared with what.", code="FIELD_REQUIRED")
    if actor.username == row["imported_by"]:
        raise ValidationFailed("The person who imported the transcription cannot be the one who checks it.", code="SELF_CHECK_BLOCKED")
    summary["transcription_check"] = {"by": actor.username, "at": now_iso(), "comment": comment.strip()}
    summary["unverified_transcription"] = False
    db.update("boq_imports", {"summary_json": summary}, "id=?", (import_id,))
    audit.log(db, actor, "boq_import", import_id, "transcription_check", after=summary["transcription_check"], project_id=row["project_id"])


def _persist(db: Database, actor: Actor, pid: str, iid: int, fname: str, sheet: str, parsed: list[ParsedRow],
             revision: str | None) -> dict:
    s = dict(rows_read=len(parsed), blank=0, headings=0, items=0, items_new=0, items_unchanged=0, rejected=0,
             needs_review=0, duplicates=0, change_requests=0, missing_in_revision=0, rejected_rows=[],
             total_client_amount="0", by_trade={})
    seen_codes: dict[str, int] = {}
    section = None
    keys_in_file: set[str] = set()
    total_amt = Decimal(0)
    for p in parsed:
        if p.kind == "blank":
            s["blank"] += 1
            continue
        if p.kind == "heading":
            s["headings"] += 1
            section = _clean(p.data.get("description")) or _clean(p.data.get("item_code"))
            hkey = f"H{p.source_row}:{_clean(p.data.get('item_code')) or ''}"
            if not db.one("SELECT 1 FROM boq_items WHERE project_id=? AND item_key=?", (pid, hkey)):
                db.insert("boq_items", dict(project_id=pid, import_id=iid, item_key=hkey, item_code=_clean(p.data.get("item_code")),
                                            item_type="heading", description=_clean(p.data.get("description")),
                                            source_file=fname, source_sheet=sheet, source_row=p.source_row,
                                            original_json=p.raw, revision=revision, created_at=now_iso(),
                                            validation_status="OK", pricing_method="unpriced"))
            continue
        if p.kind == "rejected":
            s["rejected"] += 1
            db.insert("boq_rejected_rows", dict(import_id=iid, project_id=pid, source_file=fname, source_sheet=sheet,
                                                source_row=p.source_row, reason_code=p.reject_code, reason=p.reject_reason,
                                                original_json=p.raw))
            s["rejected_rows"].append({"row": p.source_row, "code": p.reject_code, "reason": p.reject_reason})
            continue
        # ---- item
        s["items"] += 1
        d = p.data
        code = _clean(d.get("item_code"))
        base_key = code or f"R{p.source_row}"
        key = base_key
        issues = list(p.issues)
        if base_key in seen_codes:
            seen_codes[base_key] += 1
            key = f"{base_key}#{seen_codes[base_key]}"
            issues.append(_issue("DUPLICATE_CODE", f"Item code '{base_key}' appears more than once in this file "
                                 f"(first at an earlier row); stored as '{key}'.", "error"))
            s["duplicates"] += 1
        else:
            seen_codes[base_key] = 1
        keys_in_file.add(key)
        res = d["_unit_res"]
        qty: Decimal = d["_qty"]
        needs_review = any(i["level"] == "error" for i in issues)
        cur = db.one("SELECT * FROM boq_items WHERE project_id=? AND item_key=?", (pid, key))
        if cur is None:
            db.insert("boq_items", dict(
                project_id=pid, import_id=iid, item_key=key, item_code=code, item_type="item", section=section,
                description=_clean(d.get("description")), trade=_clean(d.get("trade")), unit_original=_clean(d.get("unit")),
                unit=res.code, unit_status=res.status, quantity_original=str(d.get("quantity")).strip(),
                quantity=qty, client_rate=to_text(D_opt(d.get("client_rate"))), client_amount=to_text(D_opt(d.get("client_amount"))),
                drawing_ref=_clean(d.get("drawing_ref")), spec_ref=_clean(d.get("spec_ref")),
                cost_code=_clean(d.get("cost_code")), revision=_clean(d.get("revision")) or revision,
                source_file=fname, source_sheet=sheet, source_row=p.source_row, issues_json=issues,
                validation_status="Needs Review" if needs_review else "OK", original_json=p.raw,
                created_at=now_iso()))
            s["items_new"] += 1
            if res.status in ("ambiguous", "unknown"):
                db.insert("change_requests", dict(project_id=pid, entity_type="boq_unit", entity_id=key, field="unit",
                                                  old_value=_clean(d.get("unit")), new_value=None,
                                                  reason=res.message + (f" Candidates: {', '.join(res.candidates)}" if res.candidates else ""),
                                                  status="Pending Review", requested_by="system:importer",
                                                  requested_at=now_iso()))
        else:
            # re-import: compare, never overwrite
            changed = False
            if (cur["item_type"] == "item") and D_opt(cur["quantity"]) != qty:
                _queue_change(db, pid, key, "quantity", cur["quantity"], to_text(qty),
                              f"Quantity differs in {fname} (revision {revision or '-'}).", entity="boq_quantity")
                s["change_requests"] += 1
                changed = True
            if (cur["description"] or "") != (_clean(d.get("description")) or ""):
                _queue_change(db, pid, key, "description", cur["description"], _clean(d.get("description")),
                              f"Description differs in {fname}.", entity="boq_quantity")
                s["change_requests"] += 1
                changed = True
            if res.code and cur["unit"] and res.code != cur["unit"]:
                _queue_change(db, pid, key, "unit", cur["unit"], res.code, f"Unit differs in {fname}.", entity="boq_unit")
                s["change_requests"] += 1
                changed = True
            if cur["status_in_revision"] != "Current":
                db.update("boq_items", {"status_in_revision": "Current"}, "id=?", (cur["id"],))
            if not changed:
                s["items_unchanged"] += 1
        if needs_review:
            s["needs_review"] += 1
        ca = D_opt(d.get("client_amount"))
        if ca is not None:
            total_amt += ca
        tr = _clean(d.get("trade")) or "(none)"
        s["by_trade"][tr] = s["by_trade"].get(tr, 0) + 1
    # items that existed before but are absent from this file
    if db.scalar("SELECT COUNT(*) FROM boq_imports WHERE project_id=?", (pid,)) > 1:
        for r in db.all("SELECT id, item_key FROM boq_items WHERE project_id=? AND item_type='item' AND import_id<>? "
                        "AND status_in_revision='Current'", (pid, iid)):
            if r["item_key"] not in keys_in_file:
                db.update("boq_items", {"status_in_revision": "Missing in latest revision"}, "id=?", (r["id"],))
                s["missing_in_revision"] += 1
    s["total_client_amount"] = to_text(total_amt)
    return s


def _queue_change(db: Database, pid: str, key: str, field_: str, old, new, reason: str, entity: str) -> None:
    exists = db.one("SELECT 1 FROM change_requests WHERE project_id=? AND entity_id=? AND field=? AND new_value IS ? "
                    "AND status='Pending Review'", (pid, key, field_, new))
    if exists:
        return
    db.insert("change_requests", dict(project_id=pid, entity_type=entity, entity_id=key, field=field_, old_value=old,
                                      new_value=new, reason=reason, status="Pending Review",
                                      requested_by="system:importer", requested_at=now_iso()))


# ----------------------------------------------------------------------------- takeoff resources
TAKEOFF_SYNONYMS = {
    "item_code": HEADER_SYNONYMS["item_code"], "resource_id": ["resource", "resource id", "resource_id", "res id"],
    "description": HEADER_SYNONYMS["description"], "quantity": HEADER_SYNONYMS["quantity"],
    "unit": HEADER_SYNONYMS["unit"],
}


def import_takeoff_resources(db: Database, actor: Actor, project_id: str, path: Path, sheet: str | None = None) -> dict:
    """Pre-calculated resource quantities per BOQ item (item_code, resource_id, quantity, unit)."""
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    reg = registry(db)
    rs = read_sheet(Path(path), sheet)
    hidx = None
    cmap: dict[str, int] = {}
    for idx, (rn, cells) in enumerate(rs.rows[:40]):
        m = {}
        for f, syns in TAKEOFF_SYNONYMS.items():
            for ci, c in enumerate(cells):
                if _norm_header(c) in syns and ci not in m.values():
                    m[f] = ci
                    break
        if {"item_code", "resource_id", "quantity"} <= set(m):
            hidx, cmap = idx, m
            break
    if hidx is None:
        raise ValidationFailed("Takeoff-resource file needs columns: item code, resource id, quantity (unit optional).",
                               code="MAPPING_INCOMPLETE")
    added, rejected = 0, []
    touched: set[str] = set()
    with db.tx():
        for rn, cells in rs.rows[hidx + 1:]:
            if all(c in (None, "") for c in cells):
                continue
            code = _clean(_cell(cells, cmap.get("item_code")))
            rid = _clean(_cell(cells, cmap.get("resource_id")))
            q = D_opt(_cell(cells, cmap.get("quantity")))
            ures = reg.resolve(_clean(_cell(cells, cmap.get("unit")))) if "unit" in cmap else None
            item = db.one("SELECT * FROM boq_items WHERE project_id=? AND (item_key=? OR item_code=?) AND item_type='item'",
                          (project_id, code, code))
            reason = None
            if not item:
                reason = f"BOQ item '{code}' not found in project."
            elif q is None or q < 0:
                reason = "Quantity missing/invalid."
            elif not rid or not db.one("SELECT 1 FROM resources WHERE id=?", (rid,)):
                reason = f"Resource '{rid}' not found."
            elif ures and ures.status != "ok":
                reason = ures.message
            if reason:
                rejected.append({"row": rn, "reason": reason})
                continue
            res = db.one("SELECT unit FROM resources WHERE id=?", (rid,))
            unit = ures.code if ures and ures.code else res["unit"]
            db.insert("takeoff_resource_lines", dict(project_id=project_id, item_key=item["item_key"], resource_id=rid,
                                                     description=_clean(_cell(cells, cmap.get("description"))),
                                                     quantity=q, unit=unit, source_file=Path(path).name,
                                                     source_sheet=rs.name, source_row=rn))
            touched.add(item["item_key"])
            added += 1
        for k in touched:
            db.update("boq_items", {"pricing_method": "takeoff_resources", "pricing_status": "Approved"},
                      "project_id=? AND item_key=?", (project_id, k))
        audit.log(db, actor, "takeoff_import", Path(path).name, "import",
                  after={"lines": added, "rejected": len(rejected), "items": len(touched)}, project_id=project_id)
    return {"lines_added": added, "items_priced_from_takeoff": len(touched), "rejected": rejected}
