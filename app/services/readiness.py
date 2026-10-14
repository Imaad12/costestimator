"""Submission readiness: is an exported estimate backed by a PRODUCTION approval chain?

An export is *submission-ready* only when ALL of these hold, each checked server-side from durable records (never from display names):
  * the project is not a demonstration project and no synthetic data is in use;
  * the estimate, the offer and the tender export carry approvals that (a) exist for exactly this project/version, (b) were recorded for a REGISTERED, active user whose
    registered role matched and whose `actor_type` was 'human', (c) were recorded in a 'production' environment, (d) were by a role the policy allows, and (e) have a matching entry
    in the hash-chained audit log (a copied or hand-inserted approval row has none) - and the audit chain itself verifies;
  * the approvals behind the inputs that price the estimate (rates, commercial policy, tax, approved indirects) satisfy the same tests;
  * every accepted reconciliation exception was accepted by a registered human Commercial Approver/Administrator in production;
  * the reconciliation gate is clear and the estimate state is Complete;
  * if a client profile is linked, every mandatory requirement is Met / Not applicable.
Anything else is either a 'demonstration' export (demo projects only, never described as submission-ready) or refused.
"""
from __future__ import annotations

import json
from typing import Any

from ..approvals.policy import allowed_roles
from ..config import get_settings
from ..database import Database
from ..models.enums import Entity
from . import audit


def _audit_has(db: Database, row: dict) -> bool:
    return bool(db.one("SELECT 1 FROM audit_log WHERE entity_type=? AND entity_id=? AND action=? AND actor=?",
                       (row["entity_type"], row["entity_id"], f"approval:{row['action']}", row["reviewer"])))


def check_approval(db: Database, row: dict | None, label: str, *, entity_type: str, entity_id: str, project_id: str | None = None,
                   actions: tuple[str, ...] = ("approve",)) -> tuple[list[str], dict]:
    """Problems that stop `row` counting as a production approval of (entity_type, entity_id)."""
    if row is None:
        return [f"{label}: no approval record"], {}
    row = dict(row)
    info = dict(label=label, approval_id=row["id"], entity=f"{row['entity_type']}:{row['entity_id']}", by=row["reviewer"], role=row["reviewer_role"],
                actor_type=row["actor_type"], environment=row["environment"])
    p: list[str] = []
    if row["entity_type"] != entity_type or str(row["entity_id"]) != str(entity_id) or row["action"] not in actions:
        p.append(f"{label}: approval is for {row['entity_type']}:{row['entity_id']} ({row['action']}), not {entity_type}:{entity_id}")
    if project_id is not None and row["project_id"] not in (project_id, None) and entity_type in (Entity.ESTIMATE.value, Entity.OFFER.value, Entity.TENDER_EXPORT.value):
        p.append(f"{label}: approval belongs to project {row['project_id']}")
    if row["actor_type"] != "human":
        p.append(f"{label}: approved by a '{row['actor_type']}' principal ({row['reviewer']}); only registered human users count")
    if (row["environment"] or "") != "production":
        p.append(f"{label}: recorded in environment '{row['environment']}', not 'production'")
    if row["reviewer_role"] not in allowed_roles(entity_type, "approve") | allowed_roles(entity_type, "approve_provisional"):
        p.append(f"{label}: role '{row['reviewer_role']}' is not permitted to approve {entity_type}")
    u = db.one("SELECT role, actor_type, is_active FROM users WHERE username=?", (row["reviewer"],))
    if not u or not u["is_active"] or u["actor_type"] != "human" or u["role"] != row["reviewer_role"]:
        p.append(f"{label}: {row['reviewer']} is not (or is no longer) an active registered human user holding role '{row['reviewer_role']}'")
    if not _audit_has(db, row):
        p.append(f"{label}: no matching audit-log entry (copied or hand-written approval row?)")
    return p, info


def _latest(db: Database, entity_type: str, entity_id: str, actions=("approve",)):
    q = ",".join("?" * len(actions))
    return db.one(f"SELECT * FROM approvals WHERE entity_type=? AND entity_id=? AND action IN ({q}) ORDER BY id DESC LIMIT 1", (entity_type, str(entity_id), *actions))


def _closure_gate(db: Database, project_id: str, est) -> list[str]:
    """Stage J: tender-delivery controls. Each applies only where the project uses the corresponding register, so legacy projects are unaffected; none can be waived here."""
    from . import assumptions as asm, tender, workforce
    out: list[str] = []
    openq = tender.open_material_queries(db, project_id)
    if openq:
        out.append(f"{len(openq)} unresolved material technical/commercial quer{'y' if len(openq) == 1 else 'ies'}: " + ", ".join(q["id"] for q in openq[:6]))
    missing_docs = [d["doc_ref"] for d in tender.list_documents(db, project_id) if d["status"] == "Missing"]
    if missing_docs:
        out.append("required tender document(s) not received: " + ", ".join(missing_docs))
    used = sorted(set(getattr(est.direct, "used_assumptions", set()) or set()))
    syn = [r["id"] for r in db.all(f"SELECT DISTINCT id FROM assumptions WHERE is_synthetic=1 AND id IN ({','.join('?' * len(used)) or 'NULL'})", tuple(used))] if used else []
    if syn:
        out.append("synthetic assumption(s) feed the estimate: " + ", ".join(syn[:6]))
    # Unapproved material assumptions are reconciliation findings (High); they can only be accepted as exceptions by a registered human Commercial Approver, never silently.
    # The APPROVALS behind the assumption values the estimate used must themselves be registered-human production approvals (a test or copied approval does not count).
    for aid in used:
        ra = asm.resolve(db, project_id, aid)
        if not ra.approved:
            out.append(f"assumption {aid} feeds the estimate but is not approved (status '{ra.status}')")
            continue
        if ra.origin == "project_override":
            row = db.one("SELECT * FROM approvals WHERE entity_type=? AND entity_id=? AND action='approve' AND version=? ORDER BY id DESC LIMIT 1",
                         (Entity.PROJECT_ASSUMPTION.value, f"{project_id}/{aid}", str(ra.version)))
            et, eid = Entity.PROJECT_ASSUMPTION.value, f"{project_id}/{aid}"
        else:
            row = db.one("SELECT * FROM approvals WHERE entity_type=? AND entity_id=? AND action='approve' AND version=? ORDER BY id DESC LIMIT 1", (Entity.ASSUMPTION.value, aid, str(ra.version)))
            et, eid = Entity.ASSUMPTION.value, aid
        out.extend(check_approval(db, row, f"assumption {aid}", entity_type=et, entity_id=eid)[0])
    if workforce.list_activities(db, project_id):
        b = workforce.latest_baseline(db, project_id, approved_only=True)
        if not b:
            out.append("programme baseline: none approved")
        elif b["result"].get("synthetic") or b["provisional"]:
            out.append("programme baseline rests on synthetic or provisional norms / profile / calendar")
        pend = [n for n in db.all("SELECT n.id, n.status FROM productivity_norms n JOIN work_activities a ON a.norm_id=n.id WHERE a.project_id=? AND n.version=(SELECT MAX(version) FROM productivity_norms WHERE id=n.id) GROUP BY n.id", (project_id,)) if n["status"] != "Approved"]
        if pend:
            out.append("productivity norms not approved: " + ", ".join(n["id"] for n in pend))
        # approvals behind the norms, the workforce profile and the baseline must be registered-human production approvals too
        for n in db.all("SELECT DISTINCT n.id, n.version FROM productivity_norms n JOIN work_activities a ON a.norm_id=n.id WHERE a.project_id=? AND n.status='Approved'", (project_id,)):
            row = db.one("SELECT * FROM approvals WHERE entity_type=? AND entity_id=? AND action='approve' AND version=? ORDER BY id DESC LIMIT 1", (Entity.PRODUCTIVITY_NORM.value, n["id"], str(n["version"])))
            out.extend(check_approval(db, row, f"productivity norm {n['id']}", entity_type=Entity.PRODUCTIVITY_NORM.value, entity_id=n["id"])[0])
        if b:
            row = db.one("SELECT * FROM approvals WHERE entity_type=? AND entity_id=? AND action='approve' ORDER BY id DESC LIMIT 1", (Entity.PROGRAMME_BASELINE.value, f"{project_id}/v{b['version_no']}"))
            out.extend(check_approval(db, row, f"programme baseline v{b['version_no']}", entity_type=Entity.PROGRAMME_BASELINE.value, entity_id=f"{project_id}/v{b['version_no']}")[0])
            row = db.one("SELECT * FROM approvals WHERE entity_type=? AND entity_id=? AND action='approve' AND version=? ORDER BY id DESC LIMIT 1", (Entity.WORKFORCE_PROFILE.value, b["profile_id"], str(b["profile_version"])))
            out.extend(check_approval(db, row, f"workforce profile {b['profile_id']}", entity_type=Entity.WORKFORCE_PROFILE.value, entity_id=b["profile_id"])[0])
    pk = db.one("SELECT pk FROM tender_packs WHERE project_id=? AND kind='tender' ORDER BY revision DESC LIMIT 1", (project_id,))
    if pk:
        for code in ("D16", "D06"):
            g = db.one("SELECT doc_id FROM generated_documents WHERE pack_pk=? AND doc_code=? AND status<>'Not Applicable'", (pk["pk"], code))
            if g:
                row = db.one("SELECT * FROM approvals WHERE entity_type=? AND entity_id=? AND action='approve' ORDER BY id DESC LIMIT 1", (Entity.TENDER_DOCUMENT.value, f"{project_id}/{g['doc_id']}"))
                probs, _ = check_approval(db, row, f"document {g['doc_id']} approval", entity_type=Entity.TENDER_DOCUMENT.value, entity_id=f"{project_id}/{g['doc_id']}")
                out.extend(probs)
    return out


def evaluate(db: Database, project_id: str, version_id: int, export_approval_id: int, *, gate: dict | None = None) -> dict:
    """Structured readiness verdict: {'classification': 'production'|'demonstration'|'not_ready', 'production_ready': bool, 'reasons': [...], 'chain': [...]}."""
    from ..reconciliation import engine as recon
    from . import estimates, offers, profiles, projects
    v = estimates.get_version(db, version_id)
    proj = projects.get_project(db, project_id)
    gate = gate or recon.final_gate(db, "system:readiness", project_id)
    est = gate["estimate"]
    reasons: list[str] = []
    chain: list[dict] = []
    structural: list[str] = []          # reasons that make the project a demonstration / synthetic one (as opposed to approval-chain defects)
    if proj.get("is_demo"):
        structural.append("the project is flagged as a demonstration project")
    if est.flags.get("synthetic"):
        structural.append("synthetic data is used in the estimate")
    if get_settings().environment != "production":
        structural.append(f"the environment is '{get_settings().environment}', not 'production'")

    if proj.get("basis_defaulted"):
        reasons.append(f"project region/currency ({proj.get('region')} / {proj.get('currency')}) are system defaults, not confirmed by a person")

    for imp in db.all("SELECT id, summary_json FROM boq_imports WHERE project_id=?", (project_id,)):
        sm = json.loads(imp["summary_json"] or "{}")
        if sm.get("unverified_transcription"):
            reasons.append(f"BOQ import #{imp['id']} is a transcription from '{(sm.get('derived_from') or {}).get('source_file')}' that no second person has checked")

    def need(problems_info):
        problems, info = problems_info
        reasons.extend(problems)
        if info:
            chain.append(info)

    need(check_approval(db, _latest(db, Entity.ESTIMATE.value, f"{project_id}/v{v['version_no']}"), "estimate approval", entity_type=Entity.ESTIMATE.value,
                        entity_id=f"{project_id}/v{v['version_no']}", project_id=project_id))
    o = offers.latest_offer(db, project_id)
    if not o:
        reasons.append("letter of offer: none generated")
    else:
        need(check_approval(db, _latest(db, Entity.OFFER.value, f"{project_id}/v{o['version_no']}"), "offer approval", entity_type=Entity.OFFER.value,
                            entity_id=f"{project_id}/v{o['version_no']}", project_id=project_id))
    ex = db.one("SELECT * FROM approvals WHERE id=?", (export_approval_id,))
    need(check_approval(db, ex, "tender-export approval", entity_type=Entity.TENDER_EXPORT.value, entity_id=f"{project_id}/v{v['version_no']}", project_id=project_id))
    # approvals behind the pricing inputs
    inp = est.inputs
    for rid in sorted(est.direct.used_rates):
        rr = db.one("SELECT status, is_synthetic FROM resource_rates WHERE id=?", (rid,))
        row = db.one("SELECT * FROM approvals WHERE entity_type=? AND entity_id=? AND action IN ('approve','approve_provisional') ORDER BY id DESC LIMIT 1", (Entity.RATE.value, str(rid)))
        probs, _ = check_approval(db, row, f"rate {rid}", entity_type=Entity.RATE.value, entity_id=str(rid), actions=("approve",))
        reasons.extend(probs)
    pol = est.commercial.policy_name if est.commercial else None
    prow = db.one("SELECT code, version FROM commercial_policies WHERE id=(SELECT commercial_policy_id FROM projects WHERE id=?)", (project_id,))
    if prow:
        need(check_approval(db, _latest(db, Entity.COMMERCIAL_POLICY.value, f"{prow['code']}@{prow['version']}"), "commercial policy approval", entity_type=Entity.COMMERCIAL_POLICY.value,
                            entity_id=f"{prow['code']}@{prow['version']}"))
    for code in sorted((est.commercial.tax_by_category or {}) if est.commercial else []):
        trow = db.one("SELECT code, valid_from FROM tax_categories WHERE code=? AND status='Approved' ORDER BY valid_from DESC LIMIT 1", (code,))
        if trow:
            need(check_approval(db, _latest(db, Entity.TAX_CATEGORY.value, f"{trow['code']}@{trow['valid_from']}"), f"tax category {code} approval", entity_type=Entity.TAX_CATEGORY.value,
                                entity_id=f"{trow['code']}@{trow['valid_from']}"))
        else:
            reasons.append(f"tax category {code}: no approved record")
    for it in db.all("SELECT code FROM indirect_items WHERE project_id=? AND status='Approved'", (project_id,)):
        reasons.extend(check_approval(db, _latest(db, Entity.INDIRECT.value, f"{project_id}/{it['code']}"), f"indirect {it['code']}", entity_type=Entity.INDIRECT.value,
                                      entity_id=f"{project_id}/{it['code']}")[0])
    # accepted reconciliation exceptions
    for e in db.all("SELECT * FROM recon_exceptions WHERE project_id=? AND revoked=0", (project_id,)):
        bad = []
        if e["accepted_actor_type"] != "human":
            bad.append(f"accepted by a '{e['accepted_actor_type']}' principal")
        if e["accepted_role"] not in ("Commercial Approver", "Administrator"):
            bad.append(f"accepted by role '{e['accepted_role']}'")
        if (e["environment"] or "") != "production":
            bad.append(f"recorded in environment '{e['environment']}'")
        if bad:
            reasons.append(f"reconciliation exception {e['rule_code']} ({e['entity_id']}): " + "; ".join(bad))
    if gate["blocked"]:
        reasons.append(f"reconciliation gate blocked by {len(gate['blockers'])} finding(s)")
    if est.state != "Complete":
        reasons.append(f"estimate state is '{est.state}'")
    if gate["fingerprint"] != v["inputs_hash"]:
        reasons.append("estimate inputs changed since the version was frozen")
    comp = profiles.compliance_report(db, project_id, est=est)
    if comp.get("linked") and comp.get("mandatory_unmet"):
        reasons.append(f"client profile: {len(comp['mandatory_unmet'])} mandatory requirement(s) unmet or unassessed")
    reasons.extend(_closure_gate(db, project_id, est))
    ar = audit.verify_chain(db)
    if not ar["ok"]:
        reasons.append(f"audit chain does not verify (first bad row {ar.get('first_bad_id')})")
    all_reasons = structural + reasons
    ready = not all_reasons
    cls = "production" if ready else ("demonstration" if proj.get("is_demo") else "not_ready")
    return dict(classification=cls, production_ready=ready, reasons=all_reasons, structural=structural, chain=chain, project_is_demo=bool(proj.get("is_demo")),
                synthetic_data=bool(est.flags.get("synthetic")), environment=get_settings().environment, version=v["version_no"])


def banner(r: dict | None, est_state: str = "") -> str:
    """The export banner. States exactly what the approval chain is; never 'approved by an authorised human reviewer' unless it verifiably is."""
    if r is None:
        return ""
    if r["production_ready"]:
        who = "; ".join(f"{c['label']}: {c['by']} ({c['role']}, {c['actor_type']})" for c in r["chain"][:3])
        return f"SUBMISSION READY - production approval chain verified ({who})"
    if r["classification"] == "demonstration":
        kinds = sorted({c["actor_type"] for c in r["chain"]}) or ["none"]
        return ("DEMONSTRATION EXPORT - NOT SUBMISSION READY - NOT APPROVED FOR ANY REAL TENDER | approvals by: " + ", ".join(kinds) + " principals in environment '" + r["environment"] + "'")
    return "NOT SUBMISSION READY - " + "; ".join(r["reasons"][:3])
