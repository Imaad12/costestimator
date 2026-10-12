"""Project completeness report: what is done, what is open, what blocks final approval.  No scores, no percentages of "confidence" -
only facts counted from the database, each with the place to resolve it.  Information rows never block; Blocked rows do."""
from __future__ import annotations

from ..core.timeutil import today_iso
from ..database import Database, jload
from ..estimators.estimate import compute_estimate
from ..services import workspaces

OK, OPEN, BLOCKED, INFO = "OK", "Open", "Blocked", "Info"


def _row(area, check, status, detail, where=""):
    return {"area": area, "check": check, "status": status, "detail": detail, "where": where}


def project_completeness(db: Database, project_id: str) -> dict:
    p = dict(db.one("SELECT * FROM projects WHERE id=?", (project_id,)))
    rows: list[dict] = []
    base = f"/projects/{project_id}"
    # --- global library state (shared, not project-specific)
    lv = workspaces.library_versions(db)
    if lv["rates_approved_real"] == 0:
        rows.append(_row("Global library", "Approved real (non-synthetic) rates", BLOCKED if not p["is_demo"] else INFO,
                         f"The global library has {lv['resources']} catalogue resources but 0 approved real rates"
                         + (" (this demonstration project uses SYNTHETIC rates)." if p["is_demo"] else
                            ". Every priced line must come from rates you import, quote and approve - see Rate updates."), "/rates/updates"))
    else:
        rows.append(_row("Global library", "Approved real rates", INFO, f"{lv['rates_approved_real']} approved real rate record(s) in the global library.", "/libraries"))
    # --- workspace
    try:
        root = workspaces.resolve_dir(project_id, db, create=False)
        docs = db.all("SELECT extraction_status, review_status FROM project_documents WHERE project_id=?", (project_id,))
        tender = len(list((root / workspaces.AREAS["tender"]).glob("*"))) if (root / workspaces.AREAS["tender"]).is_dir() else 0
        rows.append(_row("Workspace", "Numbered folders present", OK, f"{root.name}", f"{base}/workspace"))
        rows.append(_row("Workspace", "Tender documents received", OK if tender else OPEN, f"{tender} item(s) in '1. Tender Documents'" if tender else "No tender documents in the workspace yet.", f"{base}/workspace"))
        changed = sum(1 for d in docs if d["review_status"] in ("Source changed - review", "Missing"))
        unextracted = sum(1 for d in docs if d["extraction_status"] in ("Extraction error", "Not text-extracted"))
        rows.append(_row("Workspace", "Document index", OK if docs and not changed else OPEN if docs else INFO,
                         f"{len(docs)} indexed; {changed} new/changed/missing awaiting human review; {unextracted} not text-extracted." if docs else "Not indexed yet.", f"{base}/workspace"))
    except Exception:
        rows.append(_row("Workspace", "Numbered folders present", OPEN, "No workspace folder yet - open the Workspace tab to create it.", f"{base}/workspace"))
    # --- project context recorded by a human
    trades = jload(p.get("trades"), [])
    rows.append(_row("Project context", "Applicable trades recorded", OK if trades else OPEN, ", ".join(trades) or "Not recorded.", f"{base}/workspace"))
    rows.append(_row("Project context", "Approved drawing / specification revisions recorded", OK if p.get("drawing_revision") and p.get("spec_revision") else OPEN,
                     f"drawings: {p.get('drawing_revision') or 'not recorded'}; specification: {p.get('spec_revision') or 'not recorded'}", f"{base}/workspace"))
    # --- BOQ
    n_items = db.scalar("SELECT COUNT(*) FROM boq_items WHERE project_id=? AND item_type='item'", (project_id,)) or 0
    if not n_items:
        rows.append(_row("BOQ", "BOQ imported", BLOCKED, "No BOQ items. Import a BOQ (template: Reports & exports > templates).", f"{base}/boq"))
    else:
        unmapped = db.scalar("SELECT COUNT(*) FROM boq_items WHERE project_id=? AND item_type='item' AND assembly_code IS NULL AND pricing_resource_id IS NULL "
                             "AND COALESCE(pricing_method,'')<>'excluded'", (project_id,)) or 0
        pend = db.scalar("SELECT COUNT(*) FROM change_requests WHERE project_id=? AND status='Pending Review'", (project_id,)) or 0
        rows.append(_row("BOQ", "BOQ items", INFO, f"{n_items} item(s) imported (human-measured quantities as supplied).", f"{base}/boq"))
        rows.append(_row("BOQ", "Items mapped to an assembly or priced resource", OK if not unmapped else BLOCKED, f"{unmapped} unmapped item(s)." if unmapped else "All items mapped.", f"{base}/mapping"))
        rows.append(_row("BOQ", "Pending BOQ change requests", OK if not pend else OPEN, f"{pend} awaiting human decision.", f"{base}/boq"))
        est = compute_estimate(db, project_id)
        c = est.completeness
        rows.append(_row("Rates", "Lines priced from eligible rates", OK if not c["missing_rate_lines"] else BLOCKED,
                         f"{c['items_complete']}/{c['items_total']} items fully priced; {c['missing_rate_lines']} unpriced line(s); indicative exposure from unapproved/expired rates SAR {c['indicative_exposure']} "
                         f"(not in totals); {c['unknown_exposure_lines']} line(s) with unknown exposure.", f"{base}/procurement"))
        if est.flags["provisional"]:
            rows.append(_row("Rates", "Provisional (project-scoped) inputs in use", INFO, "Approved provisional rates/allowances are used and disclosed in the estimate state.", f"{base}/estimate"))
        if est.flags["synthetic"]:
            rows.append(_row("Rates", "Synthetic data in use", INFO, "SYNTHETIC / DEMO / NOT A MARKET QUOTE values are present.", f"{base}/estimate"))
        for b in est.blockers:
            rows.append(_row("Estimate", "Blocking condition", BLOCKED, b, f"{base}/estimate"))
        rows.append(_row("Estimate", "Estimate state", INFO if est.state.startswith("Complete") else OPEN, est.state, f"{base}/estimate"))
    # --- procurement
    open_needs = db.scalar("SELECT COUNT(*) FROM procurement_items WHERE project_id=? AND closed=0", (project_id,)) or 0
    rfq_n = db.scalar("SELECT COUNT(*) FROM rfqs WHERE project_id=?", (project_id,)) or 0
    q_pend = db.scalar("SELECT COUNT(*) FROM quotations WHERE project_id=? AND status IN ('Draft','Pending Review')", (project_id,)) or 0
    sel_pend = db.scalar("SELECT COUNT(*) FROM quote_selections s JOIN procurement_packages k ON k.id=s.package_id WHERE k.project_id=? AND s.status='Pending Review'", (project_id,)) or 0
    rows.append(_row("Procurement", "Open procurement needs", OK if not open_needs else OPEN, f"{open_needs} open need(s); {rfq_n} RFQ(s); {q_pend} quotation(s) awaiting review; {sel_pend} selection(s) awaiting approval.", f"{base}/procurement"))
    # --- indirects, duration, commercial
    ind_unappr = db.scalar("SELECT COUNT(*) FROM indirect_items WHERE project_id=? AND status NOT IN ('Approved','Superseded')", (project_id,)) or 0
    rows.append(_row("Programme & indirects", "Indirect cost items approved", OK if db.scalar("SELECT COUNT(*) FROM indirect_items WHERE project_id=? AND status='Approved'", (project_id,)) and not ind_unappr else OPEN,
                     f"{ind_unappr} indirect item(s) not yet approved." if ind_unappr else "Approved items present." , f"{base}/commercial"))
    dur = db.one("SELECT months, status FROM project_durations WHERE project_id=? ORDER BY id DESC LIMIT 1", (project_id,))
    rows.append(_row("Programme & indirects", "Project duration", OK if dur and dur["status"] == "Approved" else OPEN, f"{dur['months']} months ({dur['status']})" if dur else "Not recorded.", f"{base}/commercial"))
    pol = db.one("SELECT name, status FROM commercial_policies WHERE id=?", (p.get("commercial_policy_id"),)) if p.get("commercial_policy_id") else None
    rows.append(_row("Commercial", "Commercial policy approved", OK if pol and pol["status"] == "Approved" else BLOCKED, f"{pol['name']} ({pol['status']})" if pol else "No policy assigned.", f"{base}/commercial"))
    # --- clarifications / reconciliation / approvals
    oc = db.scalar("SELECT COUNT(*) FROM clarifications WHERE project_id=? AND status IN ('Open','Submitted')", (project_id,)) or 0
    rows.append(_row("Clarifications", "Outstanding clarifications", OK if not oc else OPEN, f"{oc} outstanding.", f"{base}/registers"))
    run = db.one("SELECT id, ts FROM recon_runs WHERE project_id=? ORDER BY id DESC LIMIT 1", (project_id,))
    if not run:
        rows.append(_row("Reconciliation", "Reconciliation run", OPEN, "Not run yet.", f"{base}/reconciliation"))
    else:
        blk = db.scalar("SELECT COUNT(*) FROM recon_findings WHERE run_id=? AND status='Open' AND severity IN ('Critical','High')", (run["id"],)) or 0
        rows.append(_row("Reconciliation", "Blocking findings (Critical/High, open)", OK if not blk else BLOCKED, f"{blk} open at run #{run['id']} ({run['ts']})", f"{base}/reconciliation"))
    v = db.one("SELECT version_no, status FROM estimate_versions WHERE project_id=? ORDER BY version_no DESC LIMIT 1", (project_id,))
    rows.append(_row("Approvals", "Estimate version", OK if v and v["status"] == "Approved" else OPEN, f"v{v['version_no']}: {v['status']}" if v else "No version frozen.", f"{base}/reconciliation"))
    exp = db.scalar("SELECT COUNT(*) FROM approvals WHERE project_id=? AND entity_type='tender_export' AND action='approve'", (project_id,)) or 0
    rows.append(_row("Approvals", "Tender export released by a Commercial Approver", OK if exp else OPEN, "Released." if exp else "Not released - only PRELIMINARY outputs exist.", f"{base}/reports"))
    blocked = [r for r in rows if r["status"] == BLOCKED]
    return {"project_id": project_id, "generated": today_iso(), "rows": rows, "blocked": len(blocked), "open": sum(1 for r in rows if r["status"] == OPEN),
            "final_approval_possible": not blocked and not any(r["status"] == OPEN and r["area"] in ("Approvals", "Reconciliation") and r["check"] == "Reconciliation run" for r in rows),
            "note": "Final approval additionally re-runs every server-side gate; this report is a guide, not the gate."}
