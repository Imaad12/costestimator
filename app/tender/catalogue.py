"""The tender-document catalogue (45 items) and the applicability matrix.

Not every tender needs every document: each item is classified Required / Conditional / Not Applicable / Missing Customer Requirement with a stated reason, from the project's
trade, delivery model, contract type, the customer's stated requirements, the documents received and the project stage. Templates are versioned: a change to a builder's output
shape bumps TEMPLATE_VERSION so every output records which template produced it.
"""
from __future__ import annotations

import json

from ..database import Database
from ..services import governed, tender, workforce

TEMPLATE_VERSION = "1.0.0"
REQ, COND, NA, MCR = "Required", "Conditional", "Not Applicable", "Missing Customer Requirement"

# (n, group, title, xlsx_also, template_id)
CATALOGUE = [
    (1, "Executive and commercial", "Tender cover letter", False, "T-COVER"),
    (2, "Executive and commercial", "Executive summary", False, "T-EXEC"),
    (3, "Executive and commercial", "Bid/no-bid record", False, "T-BIDNOBID"),
    (4, "Executive and commercial", "Scope of work and scope boundary", False, "T-SCOPE"),
    (5, "Executive and commercial", "Priced BOQ / pricing schedule", True, "T-PRICED-BOQ"),
    (6, "Executive and commercial", "Commercial offer summary", False, "T-OFFER"),
    (7, "Executive and commercial", "Pricing basis and basis of estimate (BOE)", False, "T-BOE"),
    (8, "Executive and commercial", "Assumptions register", True, "T-ASSUMPTIONS"),
    (9, "Executive and commercial", "Exclusions and qualifications", False, "T-EXCLUSIONS"),
    (10, "Executive and commercial", "Commercial clarifications", True, "T-COMM-CLARIF"),
    (11, "Executive and commercial", "Risk and opportunity register", True, "T-RISK"),
    (12, "Executive and commercial", "Tax and commercial terms summary", False, "T-TAX"),
    (13, "Executive and commercial", "Payment milestones and cash-flow basis", True, "T-CASHFLOW"),
    (14, "Executive and commercial", "Validity, delivery and programme qualifications", False, "T-VALIDITY"),
    (15, "Executive and commercial", "Bid approval and submission-readiness record", False, "T-READINESS"),
    (16, "Technical", "Technical proposal", False, "T-TECH-PROPOSAL"),
    (17, "Technical", "Understanding of the project and scope", False, "T-UNDERSTANDING"),
    (18, "Technical", "Execution methodology", False, "T-METHODOLOGY"),
    (19, "Technical", "Construction programme and milestones", True, "T-PROGRAMME"),
    (20, "Technical", "Workforce and resource-loading plan", True, "T-WORKFORCE"),
    (21, "Technical", "Plant and equipment plan", True, "T-PLANT"),
    (22, "Technical", "Procurement and long-lead schedule", True, "T-PROCUREMENT"),
    (23, "Technical", "Technical compliance matrix", True, "T-COMPLIANCE"),
    (24, "Technical", "Technical deviations and exceptions", True, "T-DEVIATIONS"),
    (25, "Technical", "Technical query / RFI register", True, "T-RFI"),
    (26, "Technical", "Design and interface matrix", True, "T-INTERFACE"),
    (27, "Technical", "Quality plan summary", False, "T-QUALITY"),
    (28, "Technical", "ITP and inspection register", True, "T-ITP"),
    (29, "Technical", "HSE execution summary and risk register", True, "T-HSE"),
    (30, "Technical", "Material and technical submittal schedule", True, "T-SUBMITTALS"),
    (31, "Technical", "Testing and commissioning plan", True, "T-TESTING"),
    (32, "Technical", "Handover and closeout plan", False, "T-CLOSEOUT"),
    (33, "Supporting records", "Tender document register and revision log", True, "T-DOCREG"),
    (34, "Supporting records", "BOQ mapping and quantity validation report", True, "T-BOQ-VALIDATION"),
    (35, "Supporting records", "Estimate audit and reconciliation report", True, "T-RECON"),
    (36, "Supporting records", "Missing-rate and procurement report", True, "T-MISSING-RATES"),
    (37, "Supporting records", "Productivity and programme assumptions report", True, "T-PRODUCTIVITY"),
    (38, "Supporting records", "Indirect-cost eligibility report", True, "T-INDIRECT-ELIG"),
    (39, "Supporting records", "Plant-hire and equipment exposure report", True, "T-PLANT-EXPOSURE"),
    (40, "Supporting records", "Estimate risk / sensitivity report", True, "T-SENSITIVITY"),
    (41, "Supporting records", "Approval and decision log", True, "T-APPROVALS"),
    (42, "Supporting records", "Open actions and outstanding information register", True, "T-OPEN-ACTIONS"),
    (43, "Supporting records", "Tender handover checklist", False, "T-HANDOVER-CHECK"),
    (44, "Supporting records", "Post-award project setup checklist", False, "T-POSTAWARD"),
    (45, "Supporting records", "Final document manifest", True, "T-MANIFEST"),
]
BY_N = {c[0]: c for c in CATALOGUE}

HANDOVER_DOCS = [
    ("H01", "Awarded scope and scope boundaries", "H-SCOPE"), ("H02", "Final tender BOQ and cost baseline", "H-BASELINE"), ("H03", "Approved assumptions and exclusions", "H-ASSUMPTIONS"),
    ("H04", "Customer clarifications and responses", "H-CLARIF"), ("H05", "Programme baseline and constraints", "H-PROGRAMME"), ("H06", "Procurement and long-lead commitments", "H-PROCUREMENT"),
    ("H07", "Subcontract interfaces", "H-INTERFACES"), ("H08", "Technical submittal obligations", "H-SUBMITTALS"), ("H09", "Quality, inspection and test obligations", "H-QUALITY"),
    ("H10", "HSE and access requirements", "H-HSE"), ("H11", "Commissioning and handover obligations", "H-COMMISSIONING"), ("H12", "Commercial terms, payment milestones and retention", "H-COMMERCIAL"),
    ("H13", "Risk register and mitigation owners", "H-RISK"), ("H14", "Outstanding decisions and actions", "H-OPEN"), ("H15", "Document register and revisions", "H-DOCREG"),
    ("H16", "Estimate snapshot and replay fingerprint", "H-SNAPSHOT"), ("H17", "Follow-up action owners", "H-OWNERS"),
]

TRADES_COMMISSIONED = ("mechanical", "hvac", "electrical", "elv", "fire", "piping", "plumbing", "industrial", "instrument")


def facts_for_rules(db: Database, project_id: str) -> dict:
    p = dict(db.one("SELECT * FROM projects WHERE id=?", (project_id,)))
    ctx = tender.context(db, project_id)
    docs = tender.list_documents(db, project_id, include_superseded=False)
    trades = {(r["trade"] or "").lower() for r in db.all("SELECT DISTINCT trade FROM boq_items WHERE project_id=? AND item_type='item'", (project_id,))}
    try:
        trades |= {str(t).strip().lower() for t in json.loads(p.get("trades") or "[]")}
    except ValueError:
        pass
    return dict(project=p, ctx=ctx, requires=(ctx.get("customer_requires") or {}), docs=docs, doc_types={d["doc_type"] for d in docs if d["status"] == "Current"}, trades=trades,
                has_spec=any(d["doc_type"] == "specification" and d["status"] == "Current" for d in docs),
                has_activities=bool(workforce.list_activities(db, project_id)),
                has_payment=bool(governed.effective(db, project_id, "payment_terms")),
                has_long_lead=bool(db.scalar("SELECT COUNT(*) FROM long_lead_items WHERE project_id=?", (project_id,))),
                has_indirects=bool(db.scalar("SELECT COUNT(*) FROM indirect_items WHERE project_id=? AND status<>'Superseded'", (project_id,))),
                has_plant=bool(db.scalar("SELECT COUNT(*) FROM governed_params WHERE kind='plant_hire_terms'")),
                n_comm_queries=len(tender.list_queries(db, project_id, "commercial")),
                award=bool(ctx.get("award_scenario")), delivery=(ctx.get("delivery_model") or "").lower(), contract=(ctx.get("contract_type") or ""),
                has_commissioned_trade=any(any(k in t for k in TRADES_COMMISSIONED) for t in trades))


def _customer(f, key, label):
    v = (f["requires"] or {}).get(key)
    if v in ("yes", True):
        return REQ, f"the customer requires {label} (tender_context.customer_requires.{key} = yes)"
    if v in ("no", False):
        return NA, f"the customer states {label} is not required (customer_requires.{key} = no)"
    return MCR, f"the tender documents do not state whether {label} is required (customer_requires.{key} not recorded) - confirm with the customer"


def classify(f: dict, n: int) -> tuple[str, str]:
    always = {1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15, 25, 29, 33, 34, 35, 36, 40, 41, 42, 43, 45}
    if n in always:
        return REQ, "core tender record produced for every tender"
    if n == 10:
        return (REQ, f"{f['n_comm_queries']} commercial clarification(s) are registered") if f["n_comm_queries"] else (COND, "no commercial clarification raised yet; becomes required when one is")
    if n == 13:
        return (REQ, "approved payment terms are on record") if f["has_payment"] else (MCR, "no approved payment terms (contract payment / retention / bond terms) have been supplied")
    if n in (16, 17, 18):
        return _customer(f, "technical_proposal", "a technical proposal")
    if n in (19, 20):
        return (REQ, "work activities with norms are defined for the programme") if f["has_activities"] else (MCR, "no work activities are defined, so a programme / workforce plan cannot be produced")
    if n == 21:
        return (REQ, "plant hire terms / plant resources are in the estimate") if f["has_plant"] else (COND, "no plant hire terms recorded; required if plant is priced")
    if n == 22:
        return (REQ, "long-lead items are registered") if f["has_long_lead"] else (COND, "no long-lead items registered; becomes required when one is")
    if n in (23, 24):
        return (REQ, "a specification / standard has been received that requires a compliance response") if f["has_spec"] else (MCR, "no specification received: compliance requirements are unknown")
    if n == 26:
        if "design" in f["delivery"] or "epc" in f["delivery"]:
            return REQ, f"delivery model '{f['ctx'].get('delivery_model')}' carries design responsibility"
        return COND, "construct-only delivery; interfaces still need recording where the BOQ names other parties"
    if n in (27, 28, 30):
        r = _customer(f, "quality_plan", "a quality plan / ITP / submittal schedule")
        return (REQ, "a specification is received and quality requirements follow from it") if f["has_spec"] and r[0] == MCR else r
    if n == 31:
        return (REQ, "the scope includes systems that need testing and commissioning") if f["has_commissioned_trade"] else (COND, "no commissioned system identified in the BOQ trades")
    if n == 32:
        return COND, "required by most contracts; confirm customer handover requirements"
    if n == 37:
        return (REQ, "productivity norms drive the programme") if f["has_activities"] else (COND, "no activities defined")
    if n == 38:
        return (REQ, "indirect items exist") if f["has_indirects"] else (NA, "no indirect items in the estimate")
    if n == 39:
        return (REQ, "day-priced plant exists") if f["has_plant"] else (NA, "no plant hire terms recorded")
    if n == 44:
        return (REQ, "an award scenario is selected") if f["award"] else (NA, "tender stage: applicable only after an award (no award scenario selected)")
    return COND, "unclassified"


def matrix(db: Database, project_id: str) -> dict:
    f = facts_for_rules(db, project_id)
    rows = []
    for n, group, title, xl, tid in CATALOGUE:
        a, why = classify(f, n)
        rows.append(dict(n=n, code=f"D{n:02d}", group=group, title=title, applicability=a, reason=why, template_id=tid, template_version=TEMPLATE_VERSION, xlsx=xl))
    return dict(project_id=project_id, template_version=TEMPLATE_VERSION, rows=rows, counts={k: sum(1 for r in rows if r["applicability"] == k) for k in (REQ, COND, NA, MCR)},
                inputs=dict(contract_type=f["contract"], delivery_model=f["delivery"], customer_requires=f["requires"], documents=len(f["docs"]), award_scenario=f["award"]))
