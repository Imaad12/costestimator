"""Letter of offer: draft generation from the strict estimate + scope registers; approval by Commercial Approver."""
from __future__ import annotations

from pathlib import Path

from ..approvals import engine as approvals
from ..config import get_settings
from ..core.errors import Conflict, NotFound, ValidationFailed
from ..core.money import ZERO, fmt, to_text
from ..core.timeutil import now_iso, today_iso
from ..database import Database, jload, rows_to_dicts
from ..estimators.estimate import compute_estimate
from ..exports.docx_util import fill_template, insert_list_after
from ..models.actor import Actor
from ..models.enums import Entity, Status
from ..reconciliation.engine import schedule_hash
from . import audit, projects


def generate_offer(db: Database, actor: Actor, project_id: str, *, validity_days: int = 30, payment_terms: str = "",
                   signatory: str = "[Authorised signatory]") -> dict:
    approvals.require_author(actor)
    p = projects.require_active(db, project_id)
    est = compute_estimate(db, project_id)
    sch, c = est.schedule, est.commercial
    scope = rows_to_dicts(db.all("SELECT * FROM scope_register WHERE project_id=? AND status='Approved' ORDER BY id", (project_id,)))
    inc = [s for s in scope if s["kind"] == "inclusion"]
    exc = [s for s in scope if s["kind"] == "exclusion"]
    qua = [s for s in scope if s["kind"] == "qualification"]
    clar = rows_to_dicts(db.all("SELECT * FROM clarifications WHERE project_id=? ORDER BY id", (project_id,)))
    total = sch.total_pre_tax if (sch and sch.complete) else None
    tax_total = c.tax_total if (c and total is not None) else None
    incl = (total + tax_total) if (total is not None and tax_total is not None) else None
    v = (db.scalar("SELECT MAX(version_no) FROM offers WHERE project_id=?", (project_id,)) or 0) + 1
    offer_ref = f"OFR-{project_id}-{v:02d}"
    banner = ("DRAFT - PRELIMINARY - NOT FOR SUBMISSION" if (est.blockers or total is None) else "DRAFT FOR COMMERCIAL REVIEW")
    if p["is_demo"]:
        banner += " - DEMONSTRATION PROJECT / SYNTHETIC DATA / NOT A MARKET QUOTE"
    co = get_settings().company
    tax_lines = "; ".join(f"{k or 'tax'}: {fmt(v['tax'])} SAR @ {v['rate_pct']}%" if v["tax"] is not None else f"{k}: rate unresolved"
                          for k, v in (c.tax_by_category.items() if c else []))
    mapping = dict(status_banner=banner, date=today_iso(), offer_ref=offer_ref, tender_ref=p.get("tender_ref") or "-",
                   client=p.get("client") or "[Client]", project_name=p["name"], location=p.get("location") or "",
                   company_name=co.get("name", ""), company_address=co.get("address", ""), cr_number=co.get("cr_number", ""),
                   vat_number=co.get("vat_number", ""), total_pre_tax=fmt(total) if total is not None else "[unresolved - estimate incomplete]",
                   tax_lines=tax_lines or "Tax: [unresolved]", total_incl_tax=fmt(incl) if incl is not None else "[unresolved]",
                   validity_days=str(validity_days), payment_terms=payment_terms or "[to be confirmed]", signatory=signatory,
                   pricing_basis=(c.method_label if c else "[commercial policy unresolved]"))
    tmpl = get_settings().templates_dir / "letter_of_offer_template.docx"
    if not tmpl.exists():
        from ..exports.docx_templates import generate_docx_templates
        generate_docx_templates(get_settings().templates_dir)
    doc = fill_template(tmpl, mapping)
    insert_list_after(doc, "INCLUSIONS", [f"{s['id']}: {s['description']}" for s in inc], empty_text="As per the pricing schedule.")
    insert_list_after(doc, "EXCLUSIONS", [f"{s['id']}: {s['description']}" for s in exc], empty_text="None stated.")
    insert_list_after(doc, "QUALIFICATIONS", [f"{s['id']}: {s['description']}" for s in qua], empty_text="None stated.")
    insert_list_after(doc, "CLARIFICATIONS", [f"{x['id']} [{x['status']}]: {x['question']}" + (f" - Response: {x['client_response']}" if x["client_response"] else "")
                                              for x in clar], empty_text="None.")
    out = projects.output_dir(project_id) / f"{offer_ref}.docx"
    doc.save(str(out))
    oid = db.insert("offers", dict(project_id=project_id, version_no=v, total_pre_tax=to_text(total), tax_total=to_text(tax_total),
                                   total_incl_tax=to_text(incl), validity_days=str(validity_days), payment_terms=payment_terms,
                                   inclusions_json=[{"id": s["id"], "description": s["description"], "boq_item_key": s["boq_item_key"],
                                                     "cost_code": s["cost_code"]} for s in inc],
                                   exclusions_json=[{"id": s["id"], "description": s["description"]} for s in exc + qua],
                                   clarifications_json=[{"id": x["id"], "status": x["status"]} for x in clar],
                                   schedule_hash=schedule_hash(sch) if sch else None, file_path=str(out), status=Status.DRAFT.value,
                                   created_by=actor.username, created_at=now_iso(), estimate_version_id=None))
    audit.log(db, actor, "offer", offer_ref, "generate", after={"total_pre_tax": to_text(total), "file": out.name}, project_id=project_id)
    return {"offer_id": oid, "offer_ref": offer_ref, "version_no": v, "file": str(out), "total_pre_tax": total, "banner": banner}


def approve_offer(db: Database, actor: Actor, project_id: str, version_no: int, comments: str | None = None) -> None:
    o = db.one("SELECT * FROM offers WHERE project_id=? AND version_no=?", (project_id, version_no))
    if not o:
        raise NotFound("Offer not found.")
    approvals.authorize(actor, Entity.OFFER.value, "approve", created_by=o["created_by"])
    if o["total_pre_tax"] is None:
        raise ValidationFailed("An offer generated from an incomplete estimate cannot be approved.", code="OFFER_INCOMPLETE")
    est = compute_estimate(db, project_id)
    if not est.schedule or o["schedule_hash"] != schedule_hash(est.schedule):
        raise Conflict("The offer no longer matches the current pricing schedule; regenerate it.", code="OFFER_STALE")
    db.update("offers", {"status": Status.APPROVED.value}, "id=?", (o["id"],))
    approvals.record(db, actor, Entity.OFFER.value, f"{project_id}/v{version_no}", "approve", project_id=project_id,
                     approved_value={"total_pre_tax": o["total_pre_tax"]}, comments=comments)


def latest_offer(db: Database, project_id: str) -> dict | None:
    r = db.one("SELECT * FROM offers WHERE project_id=? ORDER BY version_no DESC LIMIT 1", (project_id,))
    return dict(r) if r else None
