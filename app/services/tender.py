"""Tender intake and registers: customer enquiry, received-document register, technical/commercial query registers (draft-only detection), and the generic
tender registers (bid/no-bid, compliance matrix, ITP, method statements, HSE risks, permits, submittals, testing & commissioning, NCR structure ...).

Principles: nothing here interprets a drawing or specification (a document is 'registered_only' until a person marks it parsed/reviewed); every detected query is a DRAFT that a
person must approve before it can be issued; no customer response is ever invented; skeleton register rows carry explicit 'TO BE COMPLETED BY A COMPETENT PERSON' markers.
"""
from __future__ import annotations

import json
import re

from ..approvals import engine as approvals
from ..core.errors import Conflict, NotFound, ValidationFailed
from ..core.timeutil import now_iso
from ..database import Database, rows_to_dicts
from ..models.actor import Actor
from ..models.enums import Entity
from . import audit, projects

TODO = "TO BE COMPLETED BY A COMPETENT PERSON"
QUERY_REGISTERS = ("technical", "commercial", "boq_discrepancy", "scope_exclusion", "design_interface", "missing_input", "assumption_confirmation", "supplier")
OPEN_QUERY = ("Draft", "Approved to Issue", "Issued")
DOC_TYPES = ("drawing", "specification", "boq", "addendum", "site_information", "geotechnical", "survey", "existing_asset", "client_form", "contract", "standard", "clarification_response", "other")
# Heuristic markers (detection only - they raise a DRAFT question, never a conclusion): wording that leaves scope, quantity or responsibility open.
AMBIGUITY_MARKERS = ("as required", "to be confirmed", "tbc", "tbd", "by others", "or similar", "or equal", "approx", "allow for", "as directed", "if required", "as necessary", "provisional")

REGISTER_FIELDS = {
    "bid_no_bid": ("criterion", "assessment", "evidence"),
    "required_input": ("input", "needed_for", "status_note"),
    "responsibility": ("role", "responsibility", "assigned_to"),
    "compliance": ("requirement_ref", "requirement", "response", "evidence"),
    "deviation": ("requirement_ref", "deviation", "justification"),
    "itp": ("activity", "inspection_point", "acceptance_criteria", "hold_point"),
    "method_statement": ("activity", "scope", "status_note"),
    "hse_risk": ("hazard", "activity", "control_measures", "residual_risk"),
    "permit": ("permit", "authority", "needed_before"),
    "submittal_material": ("item", "specification_ref", "required_by"),
    "submittal_shop": ("item", "drawing_ref", "required_by"),
    "test_commissioning": ("system", "test", "acceptance", "when"),
    "ncr_structure": ("field", "description"),
    "procurement_strategy": ("package", "approach", "rationale"),
    "supplier_qualification": ("supplier", "status", "basis"),
    "execution_review": ("topic", "content"),
    "customer_requirement": ("requirement", "stated", "source"),
    "tender_context": ("contract_type", "delivery_model"),
    "quality_plan": ("topic", "content"),
    "interface": ("interface", "parties", "responsibility"),
    "handover_obligation": ("obligation", "source", "owner"),
}
CONTEXT_KEYS = ("contract_type", "delivery_model", "customer_requires")


def _j(x) -> str:
    return json.dumps(x, sort_keys=True, ensure_ascii=False)


# ================================================================================================ enquiry
def create_enquiry(db: Database, actor: Actor, *, customer_name: str, title: str, received_date: str, tender_deadline: str | None = None,
                   submission_instructions: str | None = None, brief: str | None = None, scope_summary: str | None = None,
                   customer_is_synthetic: bool = False, project_id: str | None = None) -> str:
    approvals.require_author(actor)
    if not customer_name.strip() or not title.strip():
        raise ValidationFailed("customer_name and title are required.", code="FIELD_REQUIRED")
    n = (db.scalar("SELECT COUNT(*) FROM tender_enquiries") or 0) + 1
    eid = f"ENQ-{n:04d}"
    db.insert("tender_enquiries", dict(id=eid, project_id=project_id, customer_name=customer_name, customer_is_synthetic=int(customer_is_synthetic), title=title,
                                       received_date=received_date, tender_deadline=tender_deadline, submission_instructions=submission_instructions, brief=brief,
                                       scope_summary=scope_summary, created_by=actor.username, created_at=now_iso()))
    audit.log(db, actor, "tender_enquiry", eid, "create", after={"customer": customer_name}, project_id=project_id)
    return eid


def link_enquiry(db: Database, actor: Actor, eid: str, project_id: str) -> None:
    approvals.require_author(actor)
    if not db.update("tender_enquiries", {"project_id": project_id, "status": "Project created"}, "id=?", (eid,)):
        raise NotFound(f"Enquiry {eid} not found.")
    audit.log(db, actor, "tender_enquiry", eid, "link_project", after=project_id, project_id=project_id)


def get_enquiry(db: Database, project_id: str) -> dict | None:
    r = db.one("SELECT * FROM tender_enquiries WHERE project_id=? ORDER BY id LIMIT 1", (project_id,))
    return dict(r) if r else None


# ================================================================================================ received documents
def register_document(db: Database, actor: Actor, project_id: str, *, doc_ref: str, doc_type: str, title: str, revision: str, source: str | None = None,
                      received_date: str | None = None, applicability: str | None = None, status: str = "Current", is_synthetic: bool = False) -> int:
    """Register a received document. A new revision of the same doc_ref supersedes the earlier one (kept, marked Superseded). Registering is NOT interpreting."""
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    if doc_type not in DOC_TYPES:
        raise ValidationFailed(f"doc_type must be one of {list(DOC_TYPES)}", code="DOC_TYPE")
    if status not in ("Current", "Missing"):
        raise ValidationFailed("status must be Current or Missing at registration.", code="DOC_STATUS")
    if db.one("SELECT 1 FROM tender_documents WHERE project_id=? AND doc_ref=? AND revision=?", (project_id, doc_ref, revision)):
        raise Conflict(f"{doc_ref} revision {revision} is already registered.", code="DOC_REVISION_EXISTS")
    prev = db.one("SELECT pk FROM tender_documents WHERE project_id=? AND doc_ref=? AND status IN ('Current','Missing') ORDER BY pk DESC LIMIT 1", (project_id, doc_ref))
    with db.tx():
        pk = db.insert("tender_documents", dict(project_id=project_id, doc_ref=doc_ref, doc_type=doc_type, title=title, revision=revision, source=source, received_date=received_date,
                                                applicability=applicability, status=status, supersedes_pk=prev["pk"] if prev else None, is_synthetic=int(is_synthetic),
                                                created_by=actor.username, created_at=now_iso()))
        if prev and status == "Current":
            db.update("tender_documents", {"status": "Superseded"}, "pk=?", (prev["pk"],))
    audit.log(db, actor, "tender_document", f"{project_id}/{doc_ref}", "register", after={"revision": revision, "status": status}, project_id=project_id)
    return pk


def set_content_status(db: Database, actor: Actor, project_id: str, doc_ref: str, revision: str, content_status: str, note: str) -> None:
    """Only a person who actually read/parsed the document may raise its content status; the note records what was done."""
    approvals.require_author(actor)
    if content_status not in ("registered_only", "parsed", "reviewed"):
        raise ValidationFailed("content_status must be registered_only, parsed or reviewed.")
    if content_status != "registered_only" and not note.strip():
        raise ValidationFailed("A note describing what was parsed / reviewed is required.", code="NOTE_REQUIRED")
    if not db.update("tender_documents", {"content_status": content_status}, "project_id=? AND doc_ref=? AND revision=?", (project_id, doc_ref, revision)):
        raise NotFound("Document revision not found.")
    audit.log(db, actor, "tender_document", f"{project_id}/{doc_ref}", f"content_status:{content_status}", comment=note, project_id=project_id)


def list_documents(db: Database, project_id: str, include_superseded: bool = True) -> list[dict]:
    sql = "SELECT * FROM tender_documents WHERE project_id=?" + ("" if include_superseded else " AND status<>'Superseded'") + " ORDER BY doc_type, doc_ref, pk"
    return rows_to_dicts(db.all(sql, (project_id,)))


def documents_report(db: Database, project_id: str) -> dict:
    docs = list_documents(db, project_id)
    cur = {d["doc_ref"]: d for d in docs if d["status"] in ("Current", "Missing")}
    conflicts = []
    for b in db.all("SELECT item_key, drawing_ref, spec_ref, revision FROM boq_items WHERE project_id=? AND item_type='item'", (project_id,)):
        for ref in filter(None, (b["drawing_ref"], b["spec_ref"])):
            d = cur.get(ref.strip())
            if d and d["status"] == "Current" and b["revision"] and str(b["revision"]).strip() != d["revision"]:
                conflicts.append(dict(item_key=b["item_key"], doc_ref=ref, boq_revision=b["revision"], register_revision=d["revision"]))
    return dict(project_id=project_id, current=[d for d in docs if d["status"] == "Current"], superseded=[d for d in docs if d["status"] == "Superseded"],
                missing=[d for d in docs if d["status"] == "Missing"], revision_conflicts=conflicts,
                not_interpreted=[d["doc_ref"] for d in docs if d["status"] == "Current" and d["content_status"] == "registered_only"],
                note="A document is registered, not interpreted, unless its content status says parsed/reviewed.")


# ================================================================================================ queries
def _next_qid(db: Database, project_id: str) -> str:
    n = (db.scalar("SELECT COUNT(*) FROM tender_queries WHERE project_id=?", (project_id,)) or 0) + 1
    return f"TQ-{project_id}-{n:03d}"


def add_query(db: Database, actor: Actor | str, project_id: str, *, register: str, question: str, why: str = "", discipline: str | None = None,
              responsible_party: str | None = None, related: dict | None = None, impact: dict | None = None, response_due: str | None = None,
              options: str | None = None, recommendation: str | None = None, detector_key: str | None = None, generated_by: str = "user",
              blocks_submission: bool = True) -> str:
    uname = actor if isinstance(actor, str) else actor.username
    if not isinstance(actor, str):
        approvals.require_author(actor)
    if register not in QUERY_REGISTERS:
        raise ValidationFailed(f"register must be one of {list(QUERY_REGISTERS)}", code="QUERY_REGISTER")
    if not question.strip():
        raise ValidationFailed("The exact question is required.", code="FIELD_REQUIRED")
    if detector_key and db.one("SELECT id FROM tender_queries WHERE project_id=? AND detector_key=?", (project_id, detector_key)):
        return db.one("SELECT id FROM tender_queries WHERE project_id=? AND detector_key=?", (project_id, detector_key))["id"]
    qid = _next_qid(db, project_id)
    db.insert("tender_queries", dict(id=qid, project_id=project_id, register=register, discipline=discipline, responsible_party=responsible_party, related_json=_j(related or {}),
                                     question=question, why=why, impact_json=_j(impact or {"assessed": False}), response_due=response_due, options=options, recommendation=recommendation,
                                     detector_key=detector_key, generated_by=generated_by, blocks_submission=int(blocks_submission), created_by=uname, created_at=now_iso()))
    audit.log(db, actor if not isinstance(actor, str) else Actor(uname, "Administrator", uname), "tender_query", qid, "create", after={"register": register, "generated_by": generated_by}, project_id=project_id)
    return qid


def get_query(db: Database, qid: str) -> dict:
    r = db.one("SELECT * FROM tender_queries WHERE id=?", (qid,))
    if not r:
        raise NotFound(f"Query {qid} not found.")
    return dict(r)


def list_queries(db: Database, project_id: str, register: str | None = None, status: str | None = None) -> list[dict]:
    sql, par = "SELECT * FROM tender_queries WHERE project_id=?", [project_id]
    if register:
        sql, par = sql + " AND register=?", par + [register]
    if status:
        sql, par = sql + " AND status=?", par + [status]
    return rows_to_dicts(db.all(sql + " ORDER BY id", par))


def edit_query(db: Database, actor: Actor, qid: str, **changes) -> None:
    approvals.require_author(actor)
    q = get_query(db, qid)
    if q["status"] != "Draft":
        raise Conflict("Only a Draft query can be edited; withdraw and re-raise instead.", code="QUERY_NOT_DRAFT")
    ok = {"question", "why", "discipline", "responsible_party", "response_due", "options", "recommendation", "blocks_submission"}
    if set(changes) - ok - {"related", "impact"}:
        raise ValidationFailed(f"Not editable: {sorted(set(changes) - ok - {'related', 'impact'})}")
    c = {k: v for k, v in changes.items() if k in ok}
    if "related" in changes:
        c["related_json"] = _j(changes["related"])
    if "impact" in changes:
        c["impact_json"] = _j(changes["impact"])
    db.update("tender_queries", c, "id=?", (qid,))
    audit.log(db, actor, "tender_query", qid, "edit", after=changes, project_id=q["project_id"])


def approve_to_issue(db: Database, actor: Actor, qid: str, comments: str | None = None) -> None:
    """A person releases a draft query for issue to the customer. Nothing is sent by the application."""
    q = get_query(db, qid)
    approvals.authorize(actor, Entity.TENDER_QUERY.value, "approve", created_by=q["created_by"])
    if q["status"] != "Draft":
        raise Conflict(f"Query must be a Draft (is {q['status']}).", code="NOT_DRAFT")
    if not q["response_due"]:
        raise ValidationFailed("A required response date is needed before a query can be released.", code="RESPONSE_DUE_REQUIRED")
    with db.tx():
        db.update("tender_queries", {"status": "Approved to Issue", "approved_by": actor.username, "approved_at": now_iso()}, "id=?", (qid,))
        approvals.record(db, actor, Entity.TENDER_QUERY.value, qid, "approve", project_id=q["project_id"], comments=comments)


def mark_issued(db: Database, actor: Actor, qid: str, note: str = "Issued manually by a user outside the application") -> None:
    approvals.require_author(actor)
    q = get_query(db, qid)
    if q["status"] != "Approved to Issue":
        raise Conflict("Only a released query can be marked issued.", code="NOT_RELEASED")
    db.update("tender_queries", {"status": "Issued"}, "id=?", (qid,))
    audit.log(db, actor, "tender_query", qid, "issued", comment=note, project_id=q["project_id"])


def record_response(db: Database, actor: Actor, qid: str, *, response_text: str, response_by: str, response_date: str, cost_impact: str | None = None,
                    time_impact_days: str | None = None, is_synthetic: bool = False) -> None:
    """Enter the customer's answer as received. Never generated; a synthetic answer is labelled and can never read as a real customer response."""
    approvals.require_author(actor)
    q = get_query(db, qid)
    if q["status"] != "Issued":
        raise Conflict("A response can only be recorded for an issued query.", code="NOT_ISSUED")
    if not response_text.strip() or not response_by.strip():
        raise ValidationFailed("response_text and response_by are required.", code="FIELD_REQUIRED")
    db.update("tender_queries", {"status": "Answered", "response_text": response_text, "response_by": response_by, "response_date": response_date, "cost_impact": cost_impact,
                                 "time_impact_days": time_impact_days, "response_is_synthetic": int(is_synthetic)}, "id=?", (qid,))
    audit.log(db, actor, "tender_query", qid, "response", comment=response_text[:200], project_id=q["project_id"])


def set_impact(db: Database, actor: Actor, qid: str, *, cost_impact: str | None = None, time_impact_days: str | None = None, basis: str) -> None:
    """Record the assessed cost / time impact of an answered query (from a recalculation by a person); the basis is mandatory."""
    approvals.require_author(actor)
    q = get_query(db, qid)
    if q["status"] not in ("Answered", "Closed"):
        raise Conflict("Impact is recorded after the response.", code="NOT_ANSWERED")
    if not basis.strip():
        raise ValidationFailed("A basis for the assessed impact is required.", code="FIELD_REQUIRED")
    db.update("tender_queries", {"cost_impact": cost_impact, "time_impact_days": time_impact_days}, "id=?", (qid,))
    audit.log(db, actor, "tender_query", qid, "impact", after={"cost": cost_impact, "days": time_impact_days}, comment=basis, project_id=q["project_id"])


def close_query(db: Database, actor: Actor, qid: str, note: str, *, withdraw: bool = False) -> None:
    approvals.require_author(actor)
    q = get_query(db, qid)
    if q["status"] in ("Closed", "Withdrawn"):
        raise Conflict("Already closed.")
    if not withdraw and q["status"] != "Answered":
        raise Conflict("Only an answered query can be closed; withdraw it instead.", code="NOT_ANSWERED")
    db.update("tender_queries", {"status": "Withdrawn" if withdraw else "Closed"}, "id=?", (qid,))
    audit.log(db, actor, "tender_query", qid, "withdraw" if withdraw else "close", comment=note, project_id=q["project_id"])


def open_material_queries(db: Database, project_id: str) -> list[dict]:
    return rows_to_dicts(db.all("SELECT id, register, question, status FROM tender_queries WHERE project_id=? AND blocks_submission=1 AND status IN ('Draft','Approved to Issue','Issued') ORDER BY id", (project_id,)))


def queries_report(db: Database, project_id: str) -> dict:
    qs = list_queries(db, project_id)
    for q in qs:
        q["related"] = json.loads(q.pop("related_json"))
        q["impact"] = json.loads(q.pop("impact_json"))
    return dict(project_id=project_id, queries=qs, by_register={r: sum(1 for q in qs if q["register"] == r) for r in QUERY_REGISTERS},
                by_status={s: sum(1 for q in qs if q["status"] == s) for s in ("Draft", "Approved to Issue", "Issued", "Answered", "Closed", "Withdrawn")},
                open_material=open_material_queries(db, project_id),
                note="Generated queries are drafts for human review; no response is ever generated and nothing is sent by the application.")


# ------------------------------------------------------------------------------------------------ detectors
def generate_draft_queries(db: Database, actor: Actor | str, project_id: str, *, response_due: str | None = None, est=None) -> dict:
    """Detect ambiguities, omissions, conflicts and missing data from the project's own records and raise DRAFT queries (de-duplicated by detector key)."""
    from ..estimators.estimate import compute_estimate
    from . import assumptions as asm, workforce
    projects.require_active(db, project_id)
    created: list[str] = []

    def q(key, register, question, why, **kw):
        before = db.one("SELECT 1 FROM tender_queries WHERE project_id=? AND detector_key=?", (project_id, key))
        qid = add_query(db, actor, project_id, register=register, question=question, why=why, detector_key=key, generated_by="system:detector", response_due=response_due, **kw)
        if not before:
            created.append(qid)

    items = rows_to_dicts(db.all("SELECT * FROM boq_items WHERE project_id=? AND item_type='item' ORDER BY id", (project_id,)))
    for b in items:
        desc = (b["description"] or "")
        low = desc.lower()
        hit = [m for m in AMBIGUITY_MARKERS if re.search(r"\b" + re.escape(m) + r"\b", low)]
        if hit:
            q(f"AMBIG:{b['item_key']}", "technical", f"BOQ item {b['item_key']} ('{desc[:120]}') uses open wording ({', '.join(hit)}). Please state the exact scope, extent and responsibility priced under this item.",
              "Open wording leaves scope or quantity undefined; the estimate cannot price it without an assumption.", discipline=b["trade"], responsible_party="Customer / design team",
              related=dict(boq_items=[b["item_key"]], drawing_ref=b["drawing_ref"], spec_ref=b["spec_ref"], revision=b["revision"]),
              impact={"assessed": False, "note": "detected by wording heuristic; impact to be assessed by an estimator"})
        if b["unit_status"] in ("ambiguous", "unknown", "missing"):
            q(f"UNIT:{b['item_key']}", "boq_discrepancy", f"BOQ item {b['item_key']} has an unclear unit ('{b['unit_original']}'). Please confirm the unit of measurement.",
              f"unit status is '{b['unit_status']}'; quantity cannot be priced reliably.", discipline=b["trade"], responsible_party="Customer (BOQ owner)", related=dict(boq_items=[b["item_key"]]))
        if b["validation_status"] == "Needs Review" and b["issues_json"]:
            try:
                iss = json.loads(b["issues_json"])
            except ValueError:
                iss = [str(b["issues_json"])]
            if iss and b["unit_status"] == "ok":
                q(f"ISSUE:{b['item_key']}", "boq_discrepancy", f"BOQ item {b['item_key']} was flagged during import: {'; '.join(str(i.get('message', i)) if isinstance(i, dict) else str(i) for i in iss)[:300]} Please confirm the intended item / quantity.",
                  "Import validation found a discrepancy.", discipline=b["trade"], responsible_party="Customer (BOQ owner)", related=dict(boq_items=[b["item_key"]]))
    drep = documents_report(db, project_id)
    groups: dict[tuple, list] = {}
    for c in drep["revision_conflicts"]:                       # one query per document / revision pair, listing every BOQ item that cites the superseded revision
        groups.setdefault((c["doc_ref"], c["boq_revision"], c["register_revision"]), []).append(c["item_key"])
    for (doc_ref, brev, rrev), keys in sorted(groups.items()):
        q(f"REV:{doc_ref}:{brev}>{rrev}", "technical", f"{len(keys)} BOQ item(s) ({', '.join(keys[:12])}{'...' if len(keys) > 12 else ''}) cite {doc_ref} at revision {brev} but the document register holds revision {rrev}. Which revision governs the quantities and scope?",
          "Conflicting revisions between the BOQ and the received document register.", related=dict(boq_items=keys, documents=[doc_ref]))
    for d in drep["missing"]:
        q(f"MISSDOC:{d['doc_ref']}", "missing_input", f"Document {d['doc_ref']} ({d['title']}) is required for the tender but has not been received. Please issue it.",
          "A required tender document is missing; dependent scope cannot be assessed.", related=dict(documents=[d["doc_ref"]]), responsible_party="Customer")
    est = est or compute_estimate(db, project_id)
    seen_res: set[str] = set()
    for e in est.direct.exceptions:
        if e.code in ("MISSING_RATE", "INDEX_ONLY_NO_PRICE", "UNAPPROVED_RATE", "EXPIRED_RATE", "RATE_REGION_MISMATCH", "RATE_NOT_YET_EFFECTIVE"):
            if e.resource_id and e.resource_id not in seen_res:
                seen_res.add(e.resource_id)
                q(f"RATE:{e.resource_id}", "supplier", f"No approved rate exists for resource {e.resource_id}. Request a quotation (RFQ) from suitable suppliers / subcontractors.",
                  e.message, responsible_party="Procurement", related=dict(boq_items=[e.item_key] if e.item_key else [], resource=e.resource_id), blocks_submission=True,
                  impact={"assessed": True, "cost": f"{e.code}: the priced lines depending on {e.resource_id} remain unpriced (never zero)"})
    ev = asm.evidence_report(db, project_id)
    bycat: dict[str, list] = {}
    for r in ev["rows"]:
        if r["mandatory"] and r["data_class"] in ("Missing data", "Pending human review", "Imported but unverified"):
            bycat.setdefault(r["category"], []).append(r)
    for cat, rows in sorted(bycat.items()):                    # grouped by category: one question per area, not one per library row
        q(f"ASMP-CAT:{cat}", "assumption_confirmation", f"{len(rows)} mandatory assumption(s) in '{cat}' need confirmation of the project basis: " + "; ".join(f"{r['id']} {r['name']} ({r['data_class']})" for r in rows[:15]) + ("; ..." if len(rows) > 15 else "") + ".",
          "; ".join(sorted({r.get('consequence_if_missing') or "A mandatory assumption has no approved value." for r in rows}))[:400], responsible_party="Estimator / Customer", related=dict(assumptions=[r["id"] for r in rows], category=cat))
    byreq: dict[str, dict] = {}
    for it in list_items(db, project_id, "customer_requirement"):
        byreq.setdefault(str(it["data"].get("requirement", "")).strip().lower(), {})[it["item_key"]] = (str(it["data"].get("stated")), it["data"].get("source"))
    for rq, srcs in sorted(byreq.items()):
        if len({v[0] for v in srcs.values()}) > 1:
            q(f"CONFLICT:{rq[:40]}", "technical", f"The customer documents state the requirement '{rq}' inconsistently ({'; '.join(f'{k}: {v[0]} per {v[1]}' for k, v in sorted(srcs.items()))}). Which statement governs?",
              "Conflicting customer requirements cannot both be priced or complied with.", responsible_party="Customer", related=dict(requirement=rq, sources=sorted(srcs)))
    for s in db.all("SELECT id, kind, description FROM scope_register WHERE project_id=? AND status IN ('Draft','Pending Review')", (project_id,)):
        q(f"SCOPE:{s['id']}", "scope_exclusion", f"Please confirm the scope boundary: '{s['description'][:200]}' ({s['kind']}).", "A scope entry is awaiting confirmation.", related=dict(scope=s["id"]))
    for ll in db.all("SELECT id, description, lead_time_weeks, required_on_site FROM long_lead_items WHERE project_id=?", (project_id,)):
        q(f"LL:{ll['id']}", "supplier", f"Confirm delivery for long-lead item {ll['id']} ({ll['description'][:100]}): lead time {ll['lead_time_weeks']} weeks against required-on-site {ll['required_on_site']}.",
          "Long-lead item drives the programme and must be ordered by a date that supports required-on-site.", responsible_party="Procurement", related=dict(long_lead=ll["id"]))
    from . import programme as _p  # noqa: F401
    try:
        acts = workforce.list_activities(db, project_id)
    except Exception:
        acts = []
    for a in acts:
        if not a["norm_id"] or not workforce.norm_for_run(db, a["norm_id"], False):
            q(f"NORM:{a['code']}", "assumption_confirmation", f"Activity {a['code']} ({a['name']}) has no approved productivity norm. Provide or approve a sourced norm before the duration is relied on.",
              "The programme duration of this activity cannot be calculated from an approved norm.", responsible_party="Estimator", related=dict(activity=a["code"], norm=a["norm_id"]), blocks_submission=False)
    audit.log(db, actor if not isinstance(actor, str) else Actor(actor, "Administrator", actor), "tender_query", project_id, "generate_drafts", after={"created": len(created)}, project_id=project_id)
    return dict(created=created, total=len(list_queries(db, project_id)), note="all are Draft: a person must edit and approve before issue")


# ================================================================================================ generic registers
def upsert_item(db: Database, actor: Actor, project_id: str, register: str, item_key: str, data: dict, *, source_ref: str | None = None, is_synthetic: bool = False) -> int:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    if register not in REGISTER_FIELDS:
        raise ValidationFailed(f"register must be one of {sorted(REGISTER_FIELDS)}", code="REGISTER")
    missing = [f for f in REGISTER_FIELDS[register] if f not in data]
    if missing:
        raise ValidationFailed(f"{register}: missing field(s) {missing}.", code="REGISTER_FIELD")
    if register == "tender_context" and "customer_requires" in data and not isinstance(data["customer_requires"], dict):
        raise ValidationFailed("customer_requires must be a {requirement: 'yes'|'no'} map.", code="REGISTER_FIELD")
    cur = db.one("SELECT * FROM tender_register_items WHERE project_id=? AND register=? AND item_key=?", (project_id, register, item_key))
    if cur:
        if cur["status"] == "Approved":
            raise Conflict("An approved register item cannot be edited; withdraw it by adding a new item key.", code="IMMUTABLE")
        db.update("tender_register_items", {"data_json": _j(data), "source_ref": source_ref, "status": "Draft"}, "pk=?", (cur["pk"],))
        pk = cur["pk"]
    else:
        pk = db.insert("tender_register_items", dict(project_id=project_id, register=register, item_key=item_key, data_json=_j(data), source_ref=source_ref,
                                                    is_synthetic=int(is_synthetic), created_by=actor.username, created_at=now_iso()))
    audit.log(db, actor, "tender_register_item", f"{project_id}/{register}/{item_key}", "upsert", project_id=project_id)
    return pk


def _item(db, project_id, register, item_key):
    r = db.one("SELECT * FROM tender_register_items WHERE project_id=? AND register=? AND item_key=?", (project_id, register, item_key))
    if not r:
        raise NotFound(f"{register}/{item_key} not found.")
    return dict(r)


def submit_item(db: Database, actor: Actor, project_id: str, register: str, item_key: str) -> None:
    approvals.require_author(actor)
    it = _item(db, project_id, register, item_key)
    if it["status"] not in ("Draft", "Rejected"):
        raise Conflict(f"Cannot submit an item in status {it['status']}.")
    if TODO in it["data_json"]:
        raise ValidationFailed("The item still contains 'TO BE COMPLETED' placeholders; complete it before submitting.", code="PLACEHOLDER")
    db.update("tender_register_items", {"status": "Pending Review"}, "pk=?", (it["pk"],))


def approve_item(db: Database, actor: Actor, project_id: str, register: str, item_key: str, comments: str | None = None) -> None:
    it = _item(db, project_id, register, item_key)
    approvals.authorize(actor, Entity.TENDER_REGISTER_ITEM.value, "approve", created_by=it["created_by"])
    if it["status"] != "Pending Review":
        raise Conflict(f"Item must be Pending Review (is {it['status']}).", code="NOT_PENDING")
    with db.tx():
        db.update("tender_register_items", {"status": "Approved", "approved_by": actor.username, "approved_at": now_iso()}, "pk=?", (it["pk"],))
        approvals.record(db, actor, Entity.TENDER_REGISTER_ITEM.value, f"{project_id}/{register}/{item_key}", "approve", project_id=project_id, comments=comments)


def reject_item(db: Database, actor: Actor, project_id: str, register: str, item_key: str, reason: str) -> None:
    it = _item(db, project_id, register, item_key)
    approvals.authorize(actor, Entity.TENDER_REGISTER_ITEM.value, "reject")
    if it["status"] == "Approved":
        raise Conflict("Approved items cannot be rejected.")
    db.update("tender_register_items", {"status": "Rejected", "review_note": reason}, "pk=?", (it["pk"],))
    approvals.record(db, actor, Entity.TENDER_REGISTER_ITEM.value, f"{project_id}/{register}/{item_key}", "reject", project_id=project_id, comments=reason)


def list_items(db: Database, project_id: str, register: str | None = None) -> list[dict]:
    sql, par = "SELECT * FROM tender_register_items WHERE project_id=?", [project_id]
    if register:
        sql, par = sql + " AND register=?", par + [register]
    out = rows_to_dicts(db.all(sql + " ORDER BY register, pk", par))
    for r in out:
        r["data"] = json.loads(r.pop("data_json"))
    return out


def context(db: Database, project_id: str) -> dict:
    r = db.one("SELECT data_json FROM tender_register_items WHERE project_id=? AND register='tender_context' AND item_key='context'", (project_id,))
    return json.loads(r["data_json"]) if r else {}


# ------------------------------------------------------------------------------------------------ skeletons (never fabricated content)
def skeleton_registers(db: Database, actor: Actor, project_id: str) -> dict:
    """Create DRAFT skeleton rows from what the project actually contains (activities, BOQ trades, reference documents). Content fields are explicit placeholders."""
    from . import workforce
    approvals.require_author(actor)
    n = {"itp": 0, "method_statement": 0, "submittal_material": 0, "test_commissioning": 0, "hse_risk": 0, "compliance": 0, "ncr_structure": 0}
    for a in workforce.list_activities(db, project_id):
        upsert_item(db, actor, project_id, "itp", a["code"], dict(activity=a["name"], inspection_point=TODO, acceptance_criteria=TODO, hold_point=TODO), source_ref=f"activity {a['code']}")
        upsert_item(db, actor, project_id, "method_statement", a["code"], dict(activity=a["name"], scope=TODO, status_note="not yet drafted"), source_ref=f"activity {a['code']}")
        upsert_item(db, actor, project_id, "hse_risk", a["code"], dict(hazard=TODO, activity=a["name"], control_measures=TODO, residual_risk=TODO), source_ref=f"activity {a['code']}")
        n["itp"] += 1; n["method_statement"] += 1; n["hse_risk"] += 1
    for t in rows_to_dicts(db.all("SELECT DISTINCT trade FROM boq_items WHERE project_id=? AND item_type='item' AND trade IS NOT NULL AND trade<>'' ORDER BY trade", (project_id,))):
        upsert_item(db, actor, project_id, "submittal_material", f"MAT-{t['trade']}", dict(item=f"Materials for trade {t['trade']}", specification_ref=TODO, required_by=TODO), source_ref=f"BOQ trade {t['trade']}")
        upsert_item(db, actor, project_id, "test_commissioning", f"TC-{t['trade']}", dict(system=f"Trade {t['trade']}", test=TODO, acceptance=TODO, when=TODO), source_ref=f"BOQ trade {t['trade']}")
        n["submittal_material"] += 1; n["test_commissioning"] += 1
    for d in list_documents(db, project_id, include_superseded=False):
        if d["doc_type"] in ("specification", "standard", "client_form", "contract") and d["status"] == "Current":
            upsert_item(db, actor, project_id, "compliance", d["doc_ref"], dict(requirement_ref=d["doc_ref"], requirement=f"Requirements of {d['title']} (rev {d['revision']}) - clauses not extracted",
                                                                               response=TODO, evidence=TODO), source_ref=d["doc_ref"])
            n["compliance"] += 1
    for f_, desc in (("NCR number", "unique reference"), ("Date raised / raised by", "who found the nonconformance"), ("Description / location / reference", "what, where, which requirement"),
                     ("Cause and classification", "root cause and severity"), ("Corrective and preventive action", "action, owner, due date"), ("Verification / closure", "who verified and when")):
        upsert_item(db, actor, project_id, "ncr_structure", f_, dict(field=f_, description=desc))
        n["ncr_structure"] += 1
    return n


# ================================================================================================ follow-up actions (owners are people, never invented)
def add_action(db: Database, actor: Actor, project_id: str, description: str, *, owner: str | None = None, due: str | None = None, source_ref: str | None = None) -> str:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    if not description.strip():
        raise ValidationFailed("description is required.", code="FIELD_REQUIRED")
    n = (db.scalar("SELECT COUNT(*) FROM open_actions WHERE project_id=?", (project_id,)) or 0) + 1
    aid = f"ACT-{project_id}-{n:03d}"
    db.insert("open_actions", dict(id=aid, project_id=project_id, description=description, owner=owner, due=due, source_ref=source_ref, created_by=actor.username, created_at=now_iso()))
    audit.log(db, actor, "open_action", aid, "create", after={"owner": owner, "due": due}, project_id=project_id)
    return aid


def close_action(db: Database, actor: Actor, aid: str, note: str) -> None:
    approvals.require_author(actor)
    if not db.update("open_actions", {"status": "Done"}, "id=? AND status='Open'", (aid,)):
        raise NotFound(f"Open action {aid} not found.")
    audit.log(db, actor, "open_action", aid, "close", comment=note)
