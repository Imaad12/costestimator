"""Supplier quotation capture (manual or XLSX/CSV import) with validity tracking and human approval."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from ..approvals import engine as approvals
from ..core.errors import Conflict, NotFound, ValidationFailed
from ..core.money import D, D_opt, to_text
from ..core.timeutil import now_iso, parse_date, today
from ..core.units import registry
from ..database import Database, rows_to_dicts
from ..imports.readers import read_sheet
from ..models.actor import Actor
from ..models.enums import Entity, Status
from ..services import audit

LINE_FIELDS = {"procurement_item_id", "description", "specification", "quantity", "unit", "unit_rate", "discount_pct",
               "delivery_included", "unloading_included", "installation_included", "tax_included", "lead_time_days",
               "compliance", "comments"}
TRI = ("Yes", "No", "Unknown")
COMPLIANCE = ("Compliant", "Non-compliant", "Deviation", "Unassessed")


def create_quotation(db: Database, actor: Actor, *, supplier_id: str, project_id: str | None = None, package_id: str | None = None,
                     reference: str | None = None, quote_date: str | None = None, valid_until: str | None = None,
                     currency: str = "SAR", payment_terms: str | None = None, delivery_terms: str | None = None,
                     tax_treatment: str | None = None, tax_rate_pct=None, lead_time_days=None, exclusions: str | None = None,
                     deviations: str | None = None, supporting_documents: str | None = None, source_file: str | None = None,
                     extracted_by_ai: bool = False, is_synthetic: bool = False, lines: list[dict] | None = None) -> str:
    approvals.require_author(actor)
    if not db.one("SELECT 1 FROM suppliers WHERE id=?", (supplier_id,)):
        raise NotFound(f"Supplier {supplier_id} not found.")
    if tax_treatment not in (None, "excl", "incl", "exempt"):
        raise ValidationFailed("tax_treatment must be 'excl', 'incl' or 'exempt'.")
    if quote_date and not parse_date(quote_date):
        raise ValidationFailed("quote_date is not a valid date.")
    if valid_until and not parse_date(valid_until):
        raise ValidationFailed("valid_until is not a valid date.")
    n = (db.scalar("SELECT COUNT(*) FROM quotations") or 0) + 1
    qid = f"QT-{n:04d}"
    with db.tx():
        db.insert("quotations", dict(id=qid, project_id=project_id, package_id=package_id, supplier_id=supplier_id,
                                     reference=reference, quote_date=quote_date, valid_until=valid_until, currency=currency.upper(),
                                     payment_terms=payment_terms, delivery_terms=delivery_terms, tax_treatment=tax_treatment,
                                     tax_rate_pct=to_text(D_opt(tax_rate_pct)), lead_time_days=to_text(D_opt(lead_time_days)),
                                     exclusions=exclusions, deviations=deviations, supporting_documents=supporting_documents,
                                     source_file=source_file, extracted_by_ai=int(extracted_by_ai), status=Status.DRAFT.value,
                                     is_synthetic=int(is_synthetic), entered_by=actor.username, entered_at=now_iso()))
        for ln in lines or []:
            add_line(db, actor, qid, **ln)
    audit.log(db, actor, "quotation", qid, "create", after={"supplier": supplier_id, "ref": reference}, project_id=project_id)
    return qid


def get_quotation(db: Database, qid: str) -> dict:
    r = db.one("SELECT * FROM quotations WHERE id=?", (qid,))
    if not r:
        raise NotFound(f"Quotation {qid} not found.")
    d = dict(r)
    d["lines"] = rows_to_dicts(db.all("SELECT * FROM quotation_lines WHERE quotation_id=? ORDER BY line_no", (qid,)))
    return d


def _editable(q: dict) -> None:
    if q["status"] in (Status.APPROVED.value, Status.SUPERSEDED.value, Status.EXPIRED.value):
        raise Conflict(f"Quotation {q['id']} is {q['status']} and immutable; enter a revised quotation instead.", code="IMMUTABLE_RECORD")


def add_line(db: Database, actor: Actor, qid: str, **line) -> int:
    approvals.require_author(actor)
    q = get_quotation(db, qid)
    _editable(q)
    bad = set(line) - LINE_FIELDS
    if bad:
        raise ValidationFailed(f"Unknown quotation line fields: {sorted(bad)}")
    for k in ("quantity", "unit_rate", "discount_pct", "lead_time_days"):
        if line.get(k) not in (None, "") and D_opt(line[k]) is None:
            raise ValidationFailed(f"{k} must be numeric.")
        if line.get(k) not in (None, ""):
            line[k] = to_text(D(line[k]))
    if line.get("unit") and registry(db).resolve(line["unit"]).status == "ok":
        line["unit"] = registry(db).resolve(line["unit"]).code
    elif line.get("unit"):
        raise ValidationFailed(f"Quotation unit '{line['unit']}' is ambiguous/unknown; enter a canonical unit.", code="UNIT_INVALID")
    for k in ("delivery_included", "unloading_included", "installation_included", "tax_included"):
        if line.get(k) not in (None, *TRI):
            raise ValidationFailed(f"{k} must be one of {TRI}")
    if line.get("compliance") not in (None, *COMPLIANCE):
        raise ValidationFailed(f"compliance must be one of {COMPLIANCE}")
    n = (db.scalar("SELECT MAX(line_no) FROM quotation_lines WHERE quotation_id=?", (qid,)) or 0) + 1
    if q["status"] in (Status.PENDING.value, Status.REJECTED.value):
        db.update("quotations", {"status": Status.DRAFT.value}, "id=?", (qid,))
    return db.insert("quotation_lines", {**line, "quotation_id": qid, "line_no": n})


def validity(q: dict, as_of: date | None = None) -> str:
    as_of = as_of or today()
    vu = parse_date(q.get("valid_until"))
    if vu is None:
        return "No validity stated"
    return "Expired" if vu < as_of else "Valid"


_QSYN = {
    "procurement_item_id": ["item", "item id", "item no", "ref", "procurement item", "المرجع", "البند"],
    "description": ["description", "desc", "particulars", "الوصف"],
    "specification": ["specification", "spec", "المواصفات"],
    "quantity": ["qty", "quantity", "الكمية"],
    "unit": ["unit", "uom", "الوحدة"],
    "unit_rate": ["your unit rate", "unit rate", "rate", "unit price", "price", "سعر الوحدة"],
    "discount_pct": ["discount", "discount %", "discount%"],
    "lead_time_days": ["lead time", "lead time (days)", "delivery (days)", "مدة التوريد"],
    "comments": ["remarks / deviations", "remarks", "comments", "deviations", "ملاحظات / استثناءات"],
}


def import_quotation_lines(db: Database, actor: Actor, qid: str, path: Path, sheet: str | None = None) -> dict:
    """Import supplier-returned XLSX/CSV (e.g. the exported RFQ sheet with the yellow columns completed)."""
    approvals.require_author(actor)
    q = get_quotation(db, qid)
    _editable(q)
    rs = read_sheet(Path(path), sheet)
    hidx, cmap = None, {}
    for idx, (rn, cells) in enumerate(rs.rows[:40]):
        m = {}
        for f, syns in _QSYN.items():
            for ci, c in enumerate(cells):
                if str(c or "").strip().lower() in syns and ci not in m.values():
                    m[f] = ci
                    break
        if "unit_rate" in m and ("procurement_item_id" in m or "description" in m):
            hidx, cmap = idx, m
            break
    if hidx is None:
        raise ValidationFailed("Could not find a header row with a unit-rate column plus item/description.", code="NO_HEADER")
    added, skipped = 0, []
    items = {r["id"]: r for r in db.all("SELECT * FROM procurement_items WHERE project_id=?", (q["project_id"],))} if q["project_id"] else {}
    by_desc = {r["description"].strip().lower(): r["id"] for r in items.values()}
    for rn, cells in rs.rows[hidx + 1:]:
        if all(c in (None, "") for c in cells):
            continue
        g = lambda f: (None if f not in cmap or cmap[f] >= len(cells) or cells[cmap[f]] in (None, "") else cells[cmap[f]])  # noqa: E731
        rate = g("unit_rate")
        if rate is None:
            skipped.append({"row": rn, "reason": "no rate quoted (treated as not quoted)"})
            continue
        if D_opt(rate) is None:
            skipped.append({"row": rn, "reason": f"rate '{rate}' not numeric"})
            continue
        pid = g("procurement_item_id")
        pid = str(pid).strip() if pid is not None else None
        if pid not in items:
            pid = by_desc.get(str(g("description") or "").strip().lower())
        try:
            add_line(db, actor, qid, procurement_item_id=pid, description=str(g("description") or ""), specification=g("specification"),
                     quantity=g("quantity"), unit=g("unit"), unit_rate=rate, discount_pct=g("discount_pct"),
                     lead_time_days=g("lead_time_days"), comments=g("comments"))
            added += 1
        except ValidationFailed as e:
            skipped.append({"row": rn, "reason": e.message})
    audit.log(db, actor, "quotation", qid, "import_lines", after={"added": added, "skipped": len(skipped), "file": Path(path).name},
              project_id=q["project_id"])
    return {"added": added, "skipped": skipped}


def submit_quotation(db: Database, actor: Actor, qid: str) -> None:
    approvals.require_author(actor)
    n = db.update("quotations", {"status": Status.PENDING.value}, "id=? AND status IN ('Draft','Rejected')", (qid,))
    if not n:
        raise Conflict("Only Draft/Rejected quotations can be submitted.")
    audit.log(db, actor, "quotation", qid, "submit")


def approve_quotation(db: Database, actor: Actor, qid: str, *, comments: str | None = None, evidence: str | None = None) -> None:
    """Procurement review confirms the captured data matches the supplier's document."""
    q = get_quotation(db, qid)
    approvals.authorize(actor, Entity.QUOTATION.value, "approve", created_by=q["entered_by"])
    if q["status"] != Status.PENDING.value:
        raise Conflict(f"Quotation must be Pending Review (is {q['status']}).", code="NOT_PENDING")
    if q["extracted_by_ai"] and not (evidence or comments):
        raise ValidationFailed("AI-extracted quotation data must be checked against the source document: "
                               "state the verification in evidence/comments.", code="AI_EXTRACTION_UNVERIFIED")
    if not q["lines"]:
        raise ValidationFailed("Quotation has no lines.")
    if not q["quote_date"]:
        raise ValidationFailed("Quote date is required for approval.")
    db.update("quotations", {"status": Status.APPROVED.value, "approved_by": actor.username, "approved_at": now_iso()}, "id=?", (qid,))
    approvals.record(db, actor, Entity.QUOTATION.value, qid, "approve", project_id=q["project_id"],
                     approved_value={"ref": q["reference"], "lines": len(q["lines"]), "valid_until": q["valid_until"]},
                     evidence=evidence, comments=comments)


def reject_quotation(db: Database, actor: Actor, qid: str, reason: str) -> None:
    q = get_quotation(db, qid)
    approvals.authorize(actor, Entity.QUOTATION.value, "reject")
    if q["status"] == Status.APPROVED.value:
        raise Conflict("Approved quotations are immutable.", code="IMMUTABLE_RECORD")
    db.update("quotations", {"status": Status.REJECTED.value}, "id=?", (qid,))
    approvals.record(db, actor, Entity.QUOTATION.value, qid, "reject", comments=reason, project_id=q["project_id"])


def mark_expired(db: Database, actor: Actor | str = "system", as_of: date | None = None) -> int:
    """Flag approved quotations past validity as Expired (kept, never deleted)."""
    as_of = as_of or today()
    n = 0
    for r in db.all("SELECT id, valid_until FROM quotations WHERE status='Approved' AND valid_until IS NOT NULL"):
        if parse_date(r["valid_until"]) < as_of:
            db.update("quotations", {"status": Status.EXPIRED.value}, "id=?", (r["id"],))
            audit.log(db, actor, "quotation", r["id"], "expired", after={"as_of": as_of.isoformat()})
            n += 1
    return n


def list_quotations(db: Database, project_id: str | None = None) -> list[dict]:
    if project_id:
        return rows_to_dicts(db.all("SELECT * FROM quotations WHERE project_id=? ORDER BY id", (project_id,)))
    return rows_to_dicts(db.all("SELECT * FROM quotations ORDER BY id"))
