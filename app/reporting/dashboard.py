"""Dashboard metrics. Percentages are only reported when the denominator is defined; otherwise None ('n/a')."""
from __future__ import annotations

from decimal import Decimal

from ..core.money import ZERO, quantize
from ..core.timeutil import today
from ..database import Database
from ..estimators.estimate import compute_estimate
from ..procurement.quotes import validity


def dashboard(db: Database, project_id: str | None = None) -> dict:
    pids = [project_id] if project_id else [r["id"] for r in db.all("SELECT id FROM projects WHERE status='Active' ORDER BY id")]
    rows = []
    tot_value = tot_exposure = ZERO
    for pid in pids:
        est = compute_estimate(db, pid)
        crit = db.scalar("SELECT COUNT(*) FROM recon_findings f JOIN recon_runs r ON r.id=f.run_id WHERE f.project_id=? AND f.severity='Critical' AND f.status='Open' "
                         "AND r.id=(SELECT MAX(id) FROM recon_runs WHERE project_id=?)", (pid, pid))
        last_ver = db.one("SELECT version_no, status FROM estimate_versions WHERE project_id=? ORDER BY version_no DESC LIMIT 1", (pid,))
        unapproved = sum(1 for aid in est.direct.used_assumptions if _unapproved(db, pid, aid))
        c = est.completeness
        rows.append({
            "project_id": pid, "name": est.project["name"], "state": est.state, "demo": bool(est.project["is_demo"]),
            "estimate_value": est.schedule.total_pre_tax if est.schedule and est.schedule.complete else None,
            "priced_direct_cost": est.direct.direct_cost_total,
            "missing_rate_lines": c["missing_rate_lines"], "indicative_exposure": c["indicative_exposure"], "unknown_exposure_lines": c["unknown_exposure_lines"],
            "unapproved_assumptions_in_use": unapproved,
            "pending_quotations": db.scalar("SELECT COUNT(*) FROM quotations WHERE project_id=? AND status IN ('Draft','Pending Review')", (pid,)),
            "expired_quotations": sum(1 for q in db.all("SELECT * FROM quotations WHERE project_id=?", (pid,)) if q["status"] == "Expired" or validity(dict(q)) == "Expired"),
            "open_clarifications": db.scalar("SELECT COUNT(*) FROM clarifications WHERE project_id=? AND status IN ('Open','Submitted')", (pid,)),
            "critical_findings": crit if db.scalar("SELECT COUNT(*) FROM recon_runs WHERE project_id=?", (pid,)) else None,
            "approval_status": f"v{last_ver['version_no']}: {last_ver['status']}" if last_ver else "No version frozen",
            "completeness_pct": c["pct_items_complete"], "items": f"{c['items_complete']}/{c['items_total']}" if c["items_total"] else "n/a",
            "synthetic": est.flags["synthetic"], "provisional": est.flags["provisional"],
        })
        if rows[-1]["estimate_value"]:
            tot_value += rows[-1]["estimate_value"]
        tot_exposure += c["indicative_exposure"]
    return {"projects": rows, "totals": {"active_estimates": len(rows), "estimate_value": tot_value if any(r["estimate_value"] for r in rows) else None,
                                          "indicative_exposure": tot_exposure,
                                          "pending_approvals": pending_approvals_count(db)}}


def _unapproved(db: Database, pid: str, aid: str) -> bool:
    from ..services import assumptions
    ra = assumptions.resolve(db, pid, aid)
    return ra.status != "Approved" or not ra.has_value


def pending_approvals_count(db: Database) -> int:
    q = {"rates": "SELECT COUNT(*) FROM resource_rates WHERE status='Pending Review'", "assumptions": "SELECT COUNT(*) FROM assumptions WHERE status='Pending Review'",
         "assemblies": "SELECT COUNT(*) FROM assemblies WHERE status='Pending Review'", "quotations": "SELECT COUNT(*) FROM quotations WHERE status='Pending Review'",
         "changes": "SELECT COUNT(*) FROM change_requests WHERE status='Pending Review'", "selections": "SELECT COUNT(*) FROM quote_selections WHERE status='Pending Review'",
         "versions": "SELECT COUNT(*) FROM estimate_versions WHERE status='Pending Review'", "suggestions": "SELECT COUNT(*) FROM ai_suggestions WHERE status='Pending Review'"}
    return sum(db.scalar(s) or 0 for s in q.values())


def pending_queue(db: Database) -> dict[str, list[dict]]:
    from ..database import rows_to_dicts
    return {
        "Rates": rows_to_dicts(db.all("SELECT id, resource_id, rate_type, unit_price, currency, unit, project_id, created_by FROM resource_rates WHERE status='Pending Review' ORDER BY id LIMIT 200")),
        "Assumptions": rows_to_dicts(db.all("SELECT id, version, name, default_value, unit FROM assumptions WHERE status='Pending Review' ORDER BY id LIMIT 200")),
        "Project assumption overrides": rows_to_dicts(db.all("SELECT project_id, assumption_id, override_value, reason FROM project_assumptions WHERE status='Pending Review' LIMIT 200")),
        "Assemblies": rows_to_dicts(db.all("SELECT code, version, description, unit FROM assemblies WHERE status='Pending Review' ORDER BY code LIMIT 200")),
        "Quotations": rows_to_dicts(db.all("SELECT id, supplier_id, reference, project_id, extracted_by_ai FROM quotations WHERE status='Pending Review' ORDER BY id LIMIT 200")),
        "Supplier selections": rows_to_dicts(db.all("SELECT id, package_id, quotation_id, value_sar, not_lowest_reason FROM quote_selections WHERE status='Pending Review' ORDER BY id")),
        "BOQ change requests": rows_to_dicts(db.all("SELECT id, project_id, entity_id, field, old_value, new_value, reason FROM change_requests WHERE status='Pending Review' ORDER BY id LIMIT 200")),
        "Indirect items": rows_to_dicts(db.all("SELECT project_id, code, description, amount, method FROM indirect_items WHERE status='Pending Review' ORDER BY project_id, code LIMIT 200")),
        "Durations": rows_to_dicts(db.all("SELECT id, project_id, months, source_type, basis_note FROM project_durations WHERE status='Pending Review'")),
        "Commercial policies": rows_to_dicts(db.all("SELECT id, code, version, name FROM commercial_policies WHERE status='Pending Review'")),
        "Tax categories": rows_to_dicts(db.all("SELECT id, code, rate_pct, valid_from, verification_note FROM tax_categories WHERE status='Pending Review'")),
        "Scope entries": rows_to_dicts(db.all("SELECT id, project_id, kind, description FROM scope_register WHERE status='Draft' ORDER BY project_id, id LIMIT 200")),
        "Allowances / sums": rows_to_dicts(db.all("SELECT project_id, item_key, pricing_method, pricing_amount, pricing_note FROM boq_items WHERE pricing_status='Pending Review'")),
        "Estimate versions": rows_to_dicts(db.all("SELECT id, project_id, version_no, state FROM estimate_versions WHERE status='Pending Review'")),
        "AI / heuristic suggestions": rows_to_dicts(db.all("SELECT id, project_id, kind, produced_by, confidence FROM ai_suggestions WHERE status='Pending Review' ORDER BY id DESC LIMIT 100")),
    }
