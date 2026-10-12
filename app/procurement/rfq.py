"""RFQ drafting and export (XLSX / DOCX / copyable email body). Never sends anything; never invents contacts."""
from __future__ import annotations

import re
from pathlib import Path

from ..approvals import engine as approvals
from ..config import get_settings
from ..core.errors import NotFound, ValidationFailed
from ..core.timeutil import now_iso
from ..database import Database, rows_to_dicts
from ..models.actor import Actor
from ..services import audit, projects
from ..services.suppliers import get_supplier

TEMPLATES: dict[str, dict[str, str]] = {
    "en": {
        "subject": "Request for Quotation - {project} - {package}",
        "greeting": "Dear {contact},",
        "intro": ("We invite your quotation for the items listed below for the project \"{project}\" ({location}). "
                  "Reference: {rfq_id}."),
        "table": "Items required",
        "requirements": "Quotation requirements",
        "reqs": [
            "Unit prices (and extended amounts) in {currency}, stating the unit-price basis for each line.",
            "State clearly whether prices include delivery to site, unloading, installation, and applicable taxes (and the rate).",
            "Quotation validity period (days or date) and lead time per item.",
            "Payment terms and any warranty terms.",
            "Compliance with the stated specification, with datasheets/technical submittals attached; list ALL deviations and exclusions.",
            "Required delivery date: {required_date}. Delivery location: {location}.",
        ],
        "deadline": "Please respond by {deadline}.",
        "disclaimer": ("This is a request for quotation only and not an order or commitment. Quantities are as measured by "
                       "the estimator and may change."),
        "regards": "Kind regards,",
        "contact_ph": "[Supplier contact - enter only from a legitimate, traceable source]",
        "cols": ["Item", "Description", "Specification", "Qty", "Unit", "Your unit rate", "Lead time", "Remarks / deviations"],
    },
    "ar": {
        "subject": "طلب عرض سعر - {project} - {package}",
        "greeting": "السادة {contact} المحترمين،",
        "intro": "نرجو تزويدنا بعرض سعركم للبنود المبينة أدناه لمشروع \"{project}\" ({location}). المرجع: {rfq_id}.",
        "table": "البنود المطلوبة",
        "requirements": "متطلبات عرض السعر",
        "reqs": [
            "أسعار الوحدات والمبالغ الإجمالية بعملة {currency} مع بيان أساس السعر لكل بند.",
            "يرجى توضيح ما إذا كانت الأسعار تشمل التوريد إلى الموقع والتفريغ والتركيب والضرائب المطبقة (ونسبتها).",
            "مدة سريان العرض ومدة التوريد لكل بند.",
            "شروط الدفع وأي شروط ضمان.",
            "المطابقة للمواصفات المطلوبة مع إرفاق الكتالوجات الفنية، وبيان جميع الاستثناءات والانحرافات.",
            "تاريخ التسليم المطلوب: {required_date}. موقع التسليم: {location}.",
        ],
        "deadline": "نرجو الرد قبل {deadline}.",
        "disclaimer": "هذا طلب عرض سعر فقط وليس أمر شراء أو التزاماً. الكميات حسب قياس المقدّر وقد تتغير. (مسودة ترجمة - تتطلب مراجعة بشرية)",
        "regards": "وتفضلوا بقبول فائق الاحترام،",
        "contact_ph": "[بيانات المورد - تُدخل فقط من مصدر مشروع وقابل للتتبع]",
        "cols": ["البند", "الوصف", "المواصفات", "الكمية", "الوحدة", "سعر الوحدة", "مدة التوريد", "ملاحظات / استثناءات"],
    },
}


def create_rfq(db: Database, actor: Actor, project_id: str, package_id: str, *, supplier_id: str | None = None,
               language: str = "en", response_deadline: str | None = None, item_ids: list[str] | None = None) -> str:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    if language not in TEMPLATES:
        raise ValidationFailed(f"Unsupported RFQ language '{language}'. Available: {sorted(TEMPLATES)}")
    pkg = db.one("SELECT * FROM procurement_packages WHERE id=? AND project_id=?", (package_id, project_id))
    if not pkg:
        raise NotFound(f"Package {package_id} not found.")
    sql = "SELECT * FROM procurement_items WHERE package_id=? AND closed=0"
    params: list = [package_id]
    if item_ids:
        sql += f" AND id IN ({','.join('?' * len(item_ids))})"
        params += item_ids
    items = rows_to_dicts(db.all(sql + " ORDER BY id", params))
    if not items:
        raise ValidationFailed("No open procurement items in this package.")
    n = (db.scalar("SELECT COUNT(*) FROM rfqs WHERE project_id=?", (project_id,)) or 0) + 1
    rid = f"RFQ-{project_id}-{n:03d}"
    sup = get_supplier(db, supplier_id) if supplier_id else None
    project = projects.get_project(db, project_id)
    subject, body = render(db, rid, project, pkg, items, sup, language, response_deadline)
    with db.tx():
        db.insert("rfqs", dict(id=rid, project_id=project_id, package_id=package_id, supplier_id=supplier_id, language=language,
                               subject=subject, body=body, status="Draft", response_deadline=response_deadline,
                               created_by=actor.username, created_at=now_iso()))
        for it in items:
            db.insert("rfq_items", dict(rfq_id=rid, procurement_item_id=it["id"]))
            db.update("procurement_items", {"rfq_status": "Draft RFQ", "response_deadline": response_deadline}, "id=?", (it["id"],))
    audit.log(db, actor, "rfq", rid, "create", after={"items": len(items), "supplier": supplier_id}, project_id=project_id)
    return rid


def render(db: Database, rfq_id: str, project: dict, pkg: dict, items: list[dict], supplier: dict | None, language: str,
           deadline: str | None) -> tuple[str, str]:
    t = TEMPLATES[language]
    s = get_settings().company
    req_date = next((i["required_date"] for i in items if i.get("required_date")), "[to be confirmed]")
    ctx = dict(project=project["name"], package=pkg["name"], location=project.get("location") or "[site location]",
               rfq_id=rfq_id, currency=project["currency"], required_date=req_date, deadline=deadline or "[response deadline]",
               contact=(supplier or {}).get("contact_name") or (supplier or {}).get("name") or t["contact_ph"])
    lines = [t["greeting"].format(**ctx), "", t["intro"].format(**ctx), "", t["table"] + ":", ""]
    for n, it in enumerate(items, 1):
        lines.append(f"{n}. {it['description']} | {it['quantity']} {it['unit']}")
        if it.get("specification"):
            lines.append(f"   Spec: {it['specification']}")
    lines += ["", t["requirements"] + ":"] + [f"- {r.format(**ctx)}" for r in t["reqs"]] + ["", t["deadline"].format(**ctx), "",
                                                                                             t["disclaimer"], "", t["regards"],
                                                                                             s.get("contact_name") or "[Your name]",
                                                                                             s.get("name") or "[Company]",
                                                                                             s.get("contact_email") or "", s.get("contact_phone") or ""]
    return t["subject"].format(**ctx), "\n".join(lines)


def get_rfq(db: Database, rfq_id: str) -> dict:
    r = db.one("SELECT * FROM rfqs WHERE id=?", (rfq_id,))
    if not r:
        raise NotFound(f"RFQ {rfq_id} not found.")
    d = dict(r)
    d["items"] = rows_to_dicts(db.all("SELECT p.* FROM rfq_items ri JOIN procurement_items p ON p.id=ri.procurement_item_id "
                                      "WHERE ri.rfq_id=? ORDER BY p.id", (rfq_id,)))
    return d


def mark_issued(db: Database, actor: Actor, rfq_id: str, note: str = "Issued manually by user outside the application") -> None:
    """Record that the human sent the RFQ (the application never sends email)."""
    approvals.require_author(actor)
    r = get_rfq(db, rfq_id)
    db.update("rfqs", {"status": "Issued (manually)", "issued_at": now_iso()}, "id=?", (rfq_id,))
    for it in r["items"]:
        db.update("procurement_items", {"rfq_status": "Issued"}, "id=?", (it["id"],))
    audit.log(db, actor, "rfq", rfq_id, "mark_issued", comment=note, project_id=r["project_id"])


def email_text(db: Database, rfq_id: str) -> str:
    r = get_rfq(db, rfq_id)
    return f"Subject: {r['subject']}\n\n{r['body']}"


def export_xlsx(db: Database, rfq_id: str, path: Path | None = None) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    r = get_rfq(db, rfq_id)
    t = TEMPLATES[r["language"]]
    wb = Workbook()
    ws = wb.active
    ws.title = "RFQ"
    ws["A1"], ws["A2"], ws["A3"] = r["subject"], f"RFQ ref: {rfq_id}", "Prices in SAR unless stated. Complete the yellow columns."
    ws["A1"].font = Font(bold=True, size=13)
    hdr = 5
    for c, name in enumerate(t["cols"], 1):
        cell = ws.cell(hdr, c, name)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F3864")
    for n, it in enumerate(r["items"], 1):
        row = hdr + n
        for c, v in enumerate([it["id"], it["description"], it.get("specification") or "", it["quantity"], it["unit"], None, None, None], 1):
            ws.cell(row, c, v)
        for c in (6, 7, 8):
            ws.cell(row, c).fill = PatternFill("solid", fgColor="FFF2CC")
        ws.cell(row, 2).alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(row, 3).alignment = Alignment(wrap_text=True, vertical="top")
    for col, w in zip("ABCDEFGH", (16, 48, 48, 10, 8, 16, 14, 40)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = ws.cell(hdr + 1, 1)
    ws.auto_filter.ref = f"A{hdr}:H{hdr + len(r['items'])}"
    ws2 = wb.create_sheet("Terms")
    ws2["A1"] = "Quotation terms (to be completed by supplier)"
    for i, k in enumerate(["Quotation reference", "Quotation date", "Validity (days/date)", "Currency", "Delivery & unloading included?",
                           "Tax included? (rate)", "Payment terms", "Lead time", "Exclusions", "Deviations"], 3):
        ws2.cell(i, 1, k).font = Font(bold=True)
        ws2.cell(i, 2).fill = PatternFill("solid", fgColor="FFF2CC")
    ws2.column_dimensions["A"].width = 36
    ws2.column_dimensions["B"].width = 60
    out = path or (projects.output_dir(r["project_id"]) / f"{rfq_id}.xlsx")
    wb.save(out)
    return out


def export_docx(db: Database, rfq_id: str, path: Path | None = None) -> Path:
    from docx import Document
    r = get_rfq(db, rfq_id)
    doc = Document()
    doc.add_heading(r["subject"], level=1)
    for line in r["body"].split("\n"):
        doc.add_paragraph(line)
    out = path or (projects.output_dir(r["project_id"]) / f"{rfq_id}.docx")
    doc.save(out)
    return out
