"""Control tower: where a project stands in the enquiry-to-handover workflow (stages A-K), and what blocks a submission-ready status.

Read-only. Every figure is read from the database or from the estimate engine; nothing here approves, changes or invents anything. A stage is
`done` (nothing open), `partial` (work exists, items open), `blocked` (a gate or missing input stops the next step) or `todo` (not started).
"""
from __future__ import annotations

import json

from ..database import Database
from ..estimators.estimate import compute_estimate_cached
from ..services import caveats, tender, workforce

DONE, PART, BLOCK, TODO = "done", "partial", "blocked", "todo"


def _n(db: Database, sql: str, *par) -> int:
    return db.scalar(sql, par) or 0


def _stage(key, label, status, headline, facts, tab, hint=""):
    return dict(key=key, label=label, status=status, headline=headline, facts=facts, tab=tab, hint=hint)


def project_tower(db: Database, pid: str) -> dict:
    p = dict(db.one("SELECT * FROM projects WHERE id=?", (pid,)))
    est = compute_estimate_cached(db, pid)
    c = est.completeness
    stages = []
    # A enquiry
    enq = tender.get_enquiry(db, pid)
    stages.append(_stage("A", "Enquiry", DONE if enq else TODO, (enq or {}).get("customer_name") or "no enquiry recorded",
                         [f"deadline {enq['tender_deadline']}" if enq and enq.get("tender_deadline") else "no deadline recorded"], "tender", "Record the customer, deadline and submission instructions."))
    # B documents
    rep = tender.documents_report(db, pid)
    dm = tender.discipline_matrix(db, pid)
    gaps = sum(1 for r in dm["rows"] if r["gaps"]) + (1 if dm["documents_without_discipline"] else 0)
    st = TODO if not (rep["current"] or rep["missing"]) else BLOCK if rep["missing"] else PART if gaps else DONE
    stages.append(_stage("B", "Documents", st, f"{len(rep['current'])} received · {len(rep['missing'])} missing · {len(rep['superseded'])} superseded",
                         [f"{gaps} discipline(s) with gaps", f"{len(rep['revision_conflicts'])} revision conflict(s)", f"{len(rep['not_interpreted'])} registered-only (not interpreted)"], "tender"))
    # C BOQ
    items = _n(db, "SELECT COUNT(*) FROM boq_items WHERE project_id=? AND item_type='item'", pid)
    pend = _n(db, "SELECT COUNT(*) FROM change_requests WHERE project_id=? AND status='Pending Review'", pid)
    unchecked = [i["id"] for i in db.all("SELECT id, summary_json FROM boq_imports WHERE project_id=?", (pid,)) if json.loads(i["summary_json"] or "{}").get("unverified_transcription")]
    rej = _n(db, "SELECT COUNT(*) FROM boq_rejected_rows WHERE project_id=?", pid)
    stages.append(_stage("C", "BOQ", TODO if not items else PART if (pend or unchecked or rej) else DONE, f"{items} item(s) imported",
                         [f"{rej} rejected row(s)", f"{pend} pending change request(s)", f"{len(unchecked)} unchecked transcription(s)"], "boq", "Quantities are human-measured; the application never measures drawings."))
    # D mapping and rates
    mapped = _n(db, "SELECT COUNT(*) FROM boq_items WHERE project_id=? AND item_type='item' AND (assembly_code IS NOT NULL OR pricing_resource_id IS NOT NULL)", pid)
    stages.append(_stage("D", "Mapping & rates", TODO if not mapped else DONE if c["items_total"] and c["items_unpriced"] == 0 else PART, f"{mapped}/{items} mapped · {c['items_complete']}/{c['items_total']} fully priced",
                         [f"{c['missing_rate_lines']} priced line(s) lack an eligible rate", f"exposure from unapproved/expired rates SAR {c['indicative_exposure']}"], "mapping"))
    # E queries
    qs = tender.list_queries(db, pid)
    openq = tender.open_material_queries(db, pid)
    drafts = sum(1 for q in qs if q["status"] == "Draft")
    stages.append(_stage("E", "Queries / RFIs", TODO if not qs else BLOCK if openq else DONE, f"{len(qs)} quer{'y' if len(qs) == 1 else 'ies'} · {len(openq)} unresolved material",
                         [f"{drafts} draft (not issued)", f"{sum(1 for q in qs if q['status'] == 'Closed')} closed"], "queries", "Queries are drafted by detectors; a person releases and issues them outside the application."))
    # F programme
    acts = workforce.list_activities(db, pid)
    base = workforce.latest_baseline(db, pid)
    appr = workforce.latest_baseline(db, pid, approved_only=True)
    if not acts:
        st, head = TODO, "no activities defined"
    elif appr:
        st, head = (PART if appr["result"].get("synthetic") or appr.get("provisional") else DONE), f"baseline v{appr['version_no']} approved · {appr['result'].get('working_days')} working days"
    else:
        st, head = PART, f"{len(acts)} activities · {'draft baseline v' + str(base['version_no']) if base else 'no baseline'}"
    stages.append(_stage("F", "Method & programme", st, head, [f"{_n(db, 'SELECT COUNT(*) FROM productivity_norms WHERE status=?', 'Approved')} approved norm(s)", f"{len(workforce.list_profiles(db))} workforce profile(s)"], "programme",
                         "Every norm, calendar and profile is a person-entered, approved record."))
    # G registers
    reg = db.all("SELECT register, status, COUNT(*) n FROM tender_register_items WHERE project_id=? GROUP BY register, status", (pid,))
    total_reg = sum(r["n"] for r in reg)
    appr_reg = sum(r["n"] for r in reg if r["status"] == "Approved")
    stages.append(_stage("G", "Quality · HSE · compliance", TODO if not total_reg else PART if appr_reg < total_reg else DONE, f"{total_reg} register item(s) · {appr_reg} approved",
                         [f"{_n(db, 'SELECT COUNT(*) FROM open_actions WHERE project_id=? AND status=?', pid, 'Open')} open action(s)"], "registers", "Skeleton rows are marked TO BE COMPLETED BY A COMPETENT PERSON."))
    # H procurement
    needs = _n(db, "SELECT COUNT(*) FROM procurement_items WHERE project_id=? AND closed=0", pid)
    rfqs = _n(db, "SELECT COUNT(*) FROM rfqs WHERE project_id=?", pid)
    qpend = _n(db, "SELECT COUNT(*) FROM quotations WHERE project_id=? AND status IN ('Draft','Pending Review')", pid)
    stages.append(_stage("H", "Procurement", TODO if not (needs or rfqs) else PART if (needs or qpend) else DONE, f"{needs} open need(s) · {rfqs} RFQ(s) · {qpend} quotation(s) awaiting review",
                         [], "procurement"))
    # I cost / risk / commercial
    run = db.one("SELECT id FROM recon_runs WHERE project_id=? ORDER BY id DESC LIMIT 1", (pid,))
    crit = _n(db, "SELECT COUNT(*) FROM recon_findings WHERE run_id=? AND status='Open' AND severity='Critical'", run["id"]) if run else None
    high = _n(db, "SELECT COUNT(*) FROM recon_findings WHERE run_id=? AND status='Open' AND severity='High'", run["id"]) if run else None
    pol = db.one("SELECT status FROM commercial_policies WHERE id=?", (p.get("commercial_policy_id"),)) if p.get("commercial_policy_id") else None
    complete = est.state.startswith("Complete")
    stages.append(_stage("I", "Cost · risk · commercial", BLOCK if (crit or not complete) and items else TODO if not items else PART if (high or not (pol and pol["status"] == "Approved")) else DONE,
                         est.state, [f"reconciliation: {'not run' if run is None else f'{crit} Critical / {high} High open'}", f"commercial policy: {pol['status'] if pol else 'none'}"], "reconciliation"))
    # J pack and gates
    pack = db.one("SELECT * FROM tender_packs WHERE project_id=? AND kind='tender' ORDER BY revision DESC LIMIT 1", (pid,))
    if pack:
        docs = db.all("SELECT status FROM generated_documents WHERE pack_pk=?", (pack["pk"],))
        nb = sum(1 for d in docs if d["status"] == "BLOCKED")
        stages.append(_stage("J", "Tender pack & gates", DONE if pack["classification"] == "production" and not nb else BLOCK if nb else PART, f"pack r{pack['revision']} · {pack['classification']} · {len(docs)} documents",
                             [f"{nb} BLOCKED document(s)", pack["status_label"][:80]], "pack"))
    else:
        stages.append(_stage("J", "Tender pack & gates", TODO, "no pack generated", ["freeze an estimate version, then generate the pack"], "pack"))
    hp = db.one("SELECT revision FROM tender_packs WHERE project_id=? AND kind='handover' ORDER BY revision DESC LIMIT 1", (pid,))
    stages.append(_stage("K", "Handover (hypothetical)", DONE if hp else TODO, f"handover pack r{hp['revision']}" if hp else "not generated", ["only for an explicit award scenario; never a real award"], "pack"))
    # what blocks a submission-ready status
    blockers = list(est.blockers) + caveats.estimate_caveats(db, pid, est)
    if openq:
        blockers.append(f"{len(openq)} unresolved material quer{'y' if len(openq) == 1 else 'ies'}")
    if rep["missing"]:
        blockers.append("required document(s) not received: " + ", ".join(d["doc_ref"] for d in rep["missing"][:8]))
    if gaps:
        blockers.append(f"{gaps} discipline(s) without a complete document set")
    if crit:
        blockers.append(f"{crit} Critical reconciliation finding(s) (cannot be waived)")
    if high:
        blockers.append(f"{high} High reconciliation finding(s) (need a Commercial Approver's recorded exception)")
    if p["is_demo"]:
        blockers.append("project is a demonstration project - never submission-ready")
    return dict(project=p, state=est.state, stages=stages, blockers=list(dict.fromkeys(blockers)),
                done=sum(1 for s in stages if s["status"] == DONE), total=len(stages), readiness_version=_latest_version(db, pid))


def _latest_version(db: Database, pid: str):
    r = db.one("SELECT id, version_no, status FROM estimate_versions WHERE project_id=? ORDER BY version_no DESC LIMIT 1", (pid,))
    return dict(r) if r else None
