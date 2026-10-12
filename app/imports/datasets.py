"""Rate/dataset ingestion with provenance: stage -> validate -> human decision -> publish as Pending Review.

No conflicting records are merged automatically; nothing is published as Approved."""
from __future__ import annotations

import json
import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from ..approvals import engine as approvals
from ..core.errors import ValidationFailed
from ..core.money import D, D_opt, to_text
from ..core.timeutil import now_iso, parse_date, today
from ..core.units import registry
from ..database import Database, jload, rows_to_dicts
from ..models.actor import Actor
from ..models.enums import RATE_TYPE_VALUES, RateType, Status
from ..services import audit, projects, rates
from .readers import read_sheet, sha256_file

SUPPORTED_CURRENCIES = {"SAR", "USD", "EUR", "GBP", "AED", "KWD", "QAR", "BHD", "OMR", "EGP", "JOD", "INR", "PKR", "CNY", "TRY"}
UNUSUAL_CHANGE_PCT = Decimal("30")
STALE_DAYS = 365
BLOCKING = {"UNKNOWN_RESOURCE", "INVALID_PRICE", "UNIT_MISSING", "UNIT_INVALID", "UNIT_INCOMPATIBLE", "CURRENCY_UNSUPPORTED", "RATE_TYPE_INVALID",
            "DATE_INVALID", "SOURCE_MISSING", "SOURCE_UNKNOWN", "CONFLICT", "MISSING_TYPE_WITH_PRICE", "REGION_INVALID", "NEGATIVE_PRICE"}

SYN = {
    "resource_id": ["resource id", "resource_id", "resource", "id", "res id"], "description": ["description", "desc", "item"],
    "unit": ["unit", "uom"], "unit_price": ["unit price", "unit_price", "rate", "price", "unit rate"],
    "currency": ["currency", "ccy"], "rate_type": ["rate type", "rate_type", "type"], "region": ["region"],
    "price_date": ["price date", "price_date", "date"], "valid_until": ["valid until", "valid_until", "validity", "expiry"],
    "source_id": ["source id", "source_id", "source", "source id (source register)"], "supplier_id": ["supplier id", "supplier_id", "supplier"],
    "tax_basis": ["tax basis", "tax_basis", "tax"], "delivery_basis": ["delivery basis", "delivery_basis", "delivery"],
    "evidence": ["evidence", "evidence / reference", "reference", "notes"],
}


def _rows_from_file(path: Path, sheet: str | None):
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("rates") or data.get("data") or []
        return [(i + 1, d) for i, d in enumerate(data)]
    rs = read_sheet(path, sheet or ("Rate Dataset" if path.suffix.lower() == ".xlsx" and "Rate Dataset" in _sheets(path) else None))
    hidx, cmap = None, {}
    for idx, (rn, cells) in enumerate(rs.rows[:40]):
        m = {}
        for f, syns in SYN.items():
            for ci, c in enumerate(cells):
                if str(c or "").strip().lower() in syns and ci not in m.values():
                    m[f] = ci
                    break
        # prefer the human header row (row 5 of generated templates) over the hidden key row
        if "unit_price" in m and ("resource_id" in m or "description" in m) and (hidx is None or len(m) > len(cmap)):
            hidx, cmap = idx, m
    if hidx is None:
        raise ValidationFailed("No header row with a unit-price column and resource id/description found.", code="NO_HEADER")
    out = []
    for rn, cells in rs.rows[hidx + 1:]:
        if all(c in (None, "") for c in cells):
            continue
        out.append((rn, {f: (cells[i] if i < len(cells) else None) for f, i in cmap.items()}))
    return out


def _sheets(path: Path) -> list[str]:
    from .readers import list_sheets
    return list_sheets(path)


def _d(v):
    if hasattr(v, "date"):
        return v.date().isoformat()
    return None if v in (None, "") else str(v).strip()


def stage_rate_dataset(db: Database, actor: Actor, path: Path, *, source_id: str | None = None, sheet: str | None = None) -> dict:
    approvals.require_author(actor)
    path = Path(path)
    reg = registry(db)
    rows = _rows_from_file(path, sheet)
    sha = sha256_file(path)
    store = get_dataset_store()
    store.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, store / f"{sha[:10]}_{path.name}")        # original kept untouched
    sources = {r["source_id"] for r in db.all("SELECT source_id FROM sources")}
    seen: dict[tuple, tuple[int, Decimal]] = {}
    with db.tx():
        did = db.insert("dataset_imports", dict(source_id=source_id, file_name=path.name, sha256=sha, kind="rates", status="Staged",
                                                imported_by=actor.username, imported_at=now_iso(), summary_json={}))
        counts: dict[str, int] = {}
        for rn, r in rows:
            issues: list[dict] = []

            def issue(code, msg, level="error"):
                issues.append({"code": code, "message": msg, "level": level})
                counts[code] = counts.get(code, 0) + 1

            rid = _d(r.get("resource_id"))
            res = db.one("SELECT * FROM resources WHERE id=?", (rid,)) if rid else None
            if not res:
                issue("UNKNOWN_RESOURCE", f"Resource '{rid}' not found; create it first (no resources are auto-created).")
            price = D_opt(r.get("unit_price"))
            rtype = _d(r.get("rate_type")) or ""
            if rtype not in RATE_TYPE_VALUES:
                issue("RATE_TYPE_INVALID", f"Rate type '{rtype}' invalid.")
            if price is None and rtype != RateType.MISSING.value:
                issue("INVALID_PRICE", f"Unit price '{r.get('unit_price')}' is not numeric.")
            elif price is not None and price < 0:
                issue("NEGATIVE_PRICE", "Negative price.")
            if price is not None and rtype == RateType.MISSING.value:
                issue("MISSING_TYPE_WITH_PRICE", "Rate type 'Missing Rate' cannot carry a price.")
            ures = reg.resolve(_d(r.get("unit")))
            if ures.status == "missing":
                issue("UNIT_MISSING", "Unit missing.")
            elif ures.status != "ok":
                issue("UNIT_INVALID", ures.message)
            elif res and not reg.can_convert(ures.code, res["unit"]):
                issue("UNIT_INCOMPATIBLE", f"Unit {ures.code} not convertible to resource unit {res['unit']}.")
            ccy = (_d(r.get("currency")) or "SAR").upper()
            if ccy not in SUPPORTED_CURRENCIES:
                issue("CURRENCY_UNSUPPORTED", f"Currency {ccy} unsupported.")
            region = _d(r.get("region")) or "KSA-ALL"
            if not db.one("SELECT 1 FROM regions WHERE code=?", (region,)):
                issue("REGION_INVALID", f"Region {region} unknown.")
            pd_, vu = _d(r.get("price_date")), _d(r.get("valid_until"))
            if (pd_ and not parse_date(pd_)) or (vu and not parse_date(vu)):
                issue("DATE_INVALID", "Invalid price/valid-until date.")
            elif not pd_:
                issue("DATE_INVALID", "price_date is required.")
            elif (today() - parse_date(pd_)).days > STALE_DAYS:
                issue("STALE", f"Price date {pd_} is older than {STALE_DAYS} days.", "warning")
            src = _d(r.get("source_id")) or source_id
            if rtype in (RateType.PUBLISHED_MARKET_PRICE.value, RateType.OFFICIAL_INDEX.value, RateType.HISTORICAL_ACTUAL.value,
                         RateType.APPROVED_INTERNAL_BENCHMARK.value) and not (src or _d(r.get("evidence"))):
                issue("SOURCE_MISSING", "Source reference required for this rate type.")
            if src and src not in sources:
                issue("SOURCE_UNKNOWN", f"Source {src} not in the Source Register.")
            if rtype == RateType.OFFICIAL_INDEX.value:
                issue("INDEX_NOT_PRICE", "Official index/benchmark stored for reference; never usable as a unit price.", "warning")
            if ccy != "SAR" and rtype != RateType.OFFICIAL_INDEX.value:
                issue("FOREIGN_CURRENCY", f"Price in {ccy}: original currency preserved; needs an approved FX rate to use.", "warning")
            key = (rid, region, pd_, rtype, _d(r.get("supplier_id")))
            if price is not None and key in seen:
                if seen[key][1] == price:
                    issue("DUPLICATE", f"Duplicate of row {seen[key][0]}.", "warning")
                else:
                    issue("CONFLICT", f"Conflicts with row {seen[key][0]}: same resource/date/type, different price. Not auto-merged.")
            elif price is not None:
                seen[key] = (rn, price)
            if res and price is not None and ccy == "SAR":
                cur = db.one("SELECT unit_price FROM resource_rates WHERE resource_id=? AND status='Approved' AND region=? ORDER BY version DESC LIMIT 1",
                             (rid, region))
                if cur and D_opt(cur["unit_price"]):
                    chg = abs(price - D(cur["unit_price"])) / D(cur["unit_price"]) * 100
                    if chg > UNUSUAL_CHANGE_PCT:
                        issue("UNUSUAL_CHANGE", f"{chg:.0f}% change vs current approved rate {cur['unit_price']}.", "warning")
                    elif price == D(cur["unit_price"]):
                        issue("NO_CHANGE", "Same as current approved rate.", "warning")
            db.insert("rate_staging", dict(dataset_id=did, row_no=rn, resource_id=rid, description=_d(r.get("description")), unit=ures.code,
                                           unit_price=to_text(price), currency=ccy, rate_type=rtype, region=region, price_date=pd_,
                                           valid_until=vu, source_id=src, supplier_id=_d(r.get("supplier_id")), tax_basis=_d(r.get("tax_basis")),
                                           delivery_basis=_d(r.get("delivery_basis")), raw_json={k: (str(v) if v is not None else None) for k, v in r.items()},
                                           issues_json=issues, decision="Pending"))
        summary = {"rows": len(rows), "issue_counts": counts}
        db.update("dataset_imports", {"summary_json": summary}, "id=?", (did,))
    audit.log(db, actor, "dataset", did, "stage", after=summary)
    return {"dataset_id": did, **summary}


def get_dataset_store() -> Path:
    from ..config import get_settings
    return get_settings().projects_dir / "_datasets"


def staged_rows(db: Database, dataset_id: int) -> list[dict]:
    rs = rows_to_dicts(db.all("SELECT * FROM rate_staging WHERE dataset_id=? ORDER BY row_no", (dataset_id,)))
    for r in rs:
        r["issues"] = jload(r["issues_json"], [])
        r["blocking"] = [i for i in r["issues"] if i["code"] in BLOCKING]
    return rs


def decide_rows(db: Database, actor: Actor, dataset_id: int, row_ids: list[int], decision: str) -> None:
    approvals.require_author(actor)
    if decision not in ("Accept", "Reject", "Pending"):
        raise ValidationFailed("decision must be Accept, Reject or Pending.")
    for rid in row_ids:
        r = db.one("SELECT * FROM rate_staging WHERE id=? AND dataset_id=?", (rid, dataset_id))
        if r and decision == "Accept" and any(i["code"] in BLOCKING for i in jload(r["issues_json"], [])):
            raise ValidationFailed(f"Row {r['row_no']} has blocking issues and cannot be accepted.", code="BLOCKING_ISSUES")
        db.update("rate_staging", {"decision": decision}, "id=?", (rid,))
    audit.log(db, actor, "dataset", dataset_id, f"decide:{decision}", after={"rows": len(row_ids)})


def publish_dataset(db: Database, actor: Actor, dataset_id: int) -> dict:
    """Publish ACCEPTED rows as Pending Review rates (never Approved). Returns a change report."""
    approvals.authorize(actor, "publication", "approve")
    ds = db.one("SELECT * FROM dataset_imports WHERE id=?", (dataset_id,))
    if not ds or ds["status"] != "Staged":
        raise ValidationFailed("Dataset not staged.")
    changes = []
    with db.tx():
        for r in staged_rows(db, dataset_id):
            if r["decision"] != "Accept":
                continue
            old = db.one("SELECT unit_price FROM resource_rates WHERE resource_id=? AND status='Approved' AND region=? ORDER BY version DESC LIMIT 1",
                         (r["resource_id"], r["region"]))
            new_id = rates.propose_rate(db, actor, r["resource_id"], unit_price=r["unit_price"], rate_type=r["rate_type"], currency=r["currency"],
                                        unit=r["unit"], region=r["region"], supplier_id=r["supplier_id"], source_id=r["source_id"],
                                        evidence=f"Dataset #{dataset_id} ({ds['file_name']}) row {r['row_no']}", price_date=r["price_date"],
                                        valid_until=r["valid_until"], tax_basis=r["tax_basis"], delivery_basis=r["delivery_basis"],
                                        confidence="Medium", submit=True, is_synthetic=(r["rate_type"] == RateType.SYNTHETIC.value))
            db.update("rate_staging", {"published_rate_id": new_id}, "id=?", (r["id"],))
            changes.append({"resource_id": r["resource_id"], "old": old["unit_price"] if old else None, "new": r["unit_price"], "currency": r["currency"],
                            "rate_id": new_id})
        db.update("dataset_imports", {"status": "Published", "published_by": actor.username, "published_at": now_iso()}, "id=?", (dataset_id,))
    audit.log(db, actor, "dataset", dataset_id, "publish", after={"rates": len(changes)})
    return {"published": len(changes), "changes": changes}
