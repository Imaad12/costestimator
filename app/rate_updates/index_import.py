"""Official index series (e.g. GASTAT Construction Cost Index) -> `index_observations`.

An index is NOT a price.  Observations are stored for escalation reference only; they never become rate candidates and no code path
turns them into a unit rate (rate type 'Official Index or Benchmark' is non-priceable by design).

Accepted inputs (all lead to identical stored rows):
  * Opendatasoft/KAPSARC API response   {"total_count": n, "results": [{"time_period": "2026-04", "measure": "Index",
                                          "section_and_group": "Labor Costs", "index": 104.89}, ...]}
  * the same records as a bare JSON list
  * CSV / XLSX in long format with columns like period | series | measure | value (header synonyms below)
Values are kept as the exact text published; periods are normalised to YYYY-MM; unparseable rows are rejected with a reason.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from ..core.errors import ValidationFailed
from ..core.money import D_opt
from ..core.timeutil import now_iso
from ..database import Database
from ..imports.readers import read_sheet
from . import manifest as mf

SYN = {
    "period": ["time_period", "period", "date", "month", "reference period", "الفترة"],
    "series": ["section_and_group", "series", "section", "group", "indicator", "category", "item"],
    "measure": ["measure", "type", "statistic", "metric"],
    "value": ["index", "value", "obs_value", "amount", "قيمة"],
}
MEASURES = {"index", "m-o-m", "y-o-y", "q-o-q"}


def _period(v: Any) -> str | None:
    if v is None or v == "":
        return None
    if hasattr(v, "year") and hasattr(v, "month"):
        return f"{v.year:04d}-{v.month:02d}"
    s = str(v).strip()
    m = re.match(r"^(\d{4})[-/](\d{1,2})(?:[-/]\d{1,2})?(?:[T ].*)?$", s)
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}"
    m = re.match(r"^(\d{4})(\d{2})$", s)
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{m.group(1)}-{m.group(2)}"
    return None


def parse_records(path: Path) -> tuple[list[dict], dict]:
    """-> (records [{period, series, measure, value, row}], parsing-info). Raises ValidationFailed when the layout is unrecognised."""
    path = Path(path)
    ext = path.suffix.lower()
    info: dict = {"format": ext.lstrip("."), "file": path.name}
    raw: list[tuple[int, dict]] = []
    if ext == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as e:
            raise ValidationFailed(f"Malformed JSON: {e}", code="MALFORMED_FILE")
        if isinstance(data, dict):
            if "error_code" in data or "error" in data and "results" not in data:
                raise ValidationFailed(f"The file is an API error response, not data: {str(data)[:200]}", code="API_ERROR_RESPONSE")
            info["total_count_declared"] = data.get("total_count")
            data = data.get("results") or data.get("records") or data.get("data") or []
        if not isinstance(data, list) or not data:
            raise ValidationFailed("No records found in the JSON file.", code="NO_RECORDS")
        for i, rec in enumerate(data, 1):
            rec = rec.get("record", {}).get("fields", rec) if isinstance(rec, dict) and "record" in rec else rec
            raw.append((i, {"period": rec.get("time_period", rec.get("period")), "series": rec.get("section_and_group", rec.get("series")),
                            "measure": rec.get("measure"), "value": rec.get("index", rec.get("value"))}))
    else:
        rs = read_sheet(path)
        hdr, cmap = None, {}
        for idx, (rn, cells) in enumerate(rs.rows[:40]):
            m: dict[str, int] = {}
            for f, syns in SYN.items():
                for ci, c in enumerate(cells):
                    if str(c or "").strip().lower() in syns and ci not in m.values():
                        m[f] = ci
                        break
            if {"period", "series", "value"} <= set(m):
                hdr, cmap = idx, m
                break
        if hdr is None:
            raise ValidationFailed("Unrecognised index table: need columns for period, series and value (e.g. time_period, section_and_group, index).",
                                   code="NO_HEADER")
        for rn, cells in rs.rows[hdr + 1:]:
            if all(c in (None, "") for c in cells):
                continue
            raw.append((rn, {f: (cells[i] if i < len(cells) else None) for f, i in cmap.items()}))
    out, rejected = [], []
    for rn, r in raw:
        per = _period(r.get("period"))
        series = str(r.get("series") or "").strip()
        measure = str(r.get("measure") or "Index").strip()
        val = D_opt(r.get("value"))
        why = None
        if per is None:
            why = f"unparseable period '{r.get('period')}'"
        elif not series:
            why = "series missing"
        elif val is None:
            why = f"value '{r.get('value')}' is not numeric"
        elif measure.lower() not in MEASURES:
            why = f"unknown measure '{measure}' (expected one of {sorted(MEASURES)})"
        if why:
            rejected.append({"row": rn, "reason": why})
        else:
            out.append({"period": per, "series": series, "measure": measure, "value": str(r.get("value")).strip(), "row": rn})
    info["rejected"] = rejected
    return out, info


def import_index_file(db: Database, actor, path: Path, *, dataset: str, source_id: str | None, source_name: str, source_url: str | None = None,
                      description: str = "", dry_run: bool = False, adapter: str = "manual-file", unit: str = "index points / %") -> dict:
    """Parse + (unless dry_run) store a manifest and observations. Re-importing an identical file is refused."""
    path = Path(path)
    recs, info = parse_records(path)
    sha_dry = None
    if dry_run:
        from ..imports.readers import sha256_file
        sha_dry = sha256_file(path)
        existing = mf.existing_import(db, sha_dry, "index")
        mid = mf.write_manifest(db, actor, kind="index", adapter=adapter, source_id=source_id, source_name=source_name, source_url=source_url,
                                original_path=str(path), stored_path=None, sha=sha_dry, description=description, dry_run=True, parsing=info,
                                accepted=len(recs), rejected=len(info["rejected"]), errors=info["rejected"], candidate_ids=[])
        return {"manifest_id": mid, "dry_run": True, "records": len(recs), "rejected": len(info["rejected"]), "would_be_duplicate": bool(existing),
                "periods": sorted({r["period"] for r in recs})[-3:]}
    stored, sha = mf.store_original(path)
    mf.refuse_duplicate(db, sha, "index")
    new = changed = unchanged = 0
    with db.tx():
        mid = mf.write_manifest(db, actor, kind="index", adapter=adapter, source_id=source_id, source_name=source_name, source_url=source_url,
                                original_path=str(path), stored_path=stored, sha=sha, description=description, dry_run=False, parsing=info,
                                accepted=len(recs), rejected=len(info["rejected"]), errors=info["rejected"], candidate_ids=[])
        for r in recs:
            prev = db.one("SELECT value FROM index_observations WHERE dataset=? AND series=? AND measure=? AND period=? ORDER BY id DESC LIMIT 1",
                          (dataset, r["series"], r["measure"], r["period"]))
            if prev and str(D_opt(prev["value"])) == str(D_opt(r["value"])):
                unchanged += 1
                continue
            db.insert("index_observations", dict(source_id=source_id, dataset=dataset, series=r["series"], measure=r["measure"], period=r["period"],
                                                 value=r["value"], unit=("%" if r["measure"].lower() != "index" else "index points"),
                                                 manifest_id=mid, retrieved_at=now_iso()))
            changed += bool(prev)
            new += not prev
    return {"manifest_id": mid, "dry_run": False, "records": len(recs), "new": new, "revised": changed, "unchanged": unchanged,
            "rejected": len(info["rejected"])}


def latest_observations(db: Database, dataset: str | None = None, measure: str = "Index") -> list[dict]:
    sql = ("SELECT o.* FROM index_observations o WHERE o.measure=? "
           "AND o.id=(SELECT MAX(id) FROM index_observations x WHERE x.dataset=o.dataset AND x.series=o.series AND x.measure=o.measure AND x.period=o.period)")
    params: list = [measure]
    if dataset:
        sql += " AND o.dataset=?"
        params.append(dataset)
    rows = db.all(sql + " ORDER BY o.series, o.period", params)
    return [dict(r) for r in rows]
