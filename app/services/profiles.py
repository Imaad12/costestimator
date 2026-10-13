"""Client / owner compliance profiles and estimate classification.

A profile is a list of requirements that a PERSON loads from the owner's own controlled documents (each with a source reference), then a Commercial Approver
approves. The software evaluates measurable requirements against project facts and records human attestations for the rest. With no requirements loaded
no compliance statement can be made. Nothing here asserts compliance with any owner's standards on its own authority."""
from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path

from ..approvals import engine as approvals
from ..core.errors import Conflict, NotFound, ValidationFailed
from ..core.money import D, D_opt
from ..core.timeutil import now_iso
from ..database import Database, rows_to_dicts
from ..estimators import profile_checks
from ..models.actor import Actor
from ..models.enums import Status
from . import audit, governed, projects

CATEGORIES = ("form", "template", "code_list", "rule", "procedure", "deliverable", "other")
ENTITY = "client_profile"


def create_profile(db: Database, actor: Actor, code: str, name: str, *, client: str | None = None, source_documents: list[dict] | None = None,
                   requirements: list[dict] | None = None, notes: str | None = None) -> int:
    """New Draft profile version. `requirements`: [{req_id, category, title, source_ref, mandatory?, check?{fact,op,value}}]."""
    approvals.require_author(actor)
    code = (code or "").strip()
    if not code or not (name or "").strip():
        raise ValidationFailed("Profile code and name are required.")
    docs = source_documents or []
    reqs = requirements or []
    seen = set()
    clean = []
    for r in reqs:
        rid = str(r.get("req_id", "")).strip()
        if not rid or rid in seen:
            raise ValidationFailed(f"Requirement id missing or duplicated: '{rid}'.", code="PROFILE_REQ")
        seen.add(rid)
        if r.get("category") not in CATEGORIES:
            raise ValidationFailed(f"{rid}: category must be one of {CATEGORIES}.", code="PROFILE_REQ")
        if not (r.get("title") or "").strip() or not (r.get("source_ref") or "").strip():
            raise ValidationFailed(f"{rid}: title and source_ref (controlled document, revision, clause) are required.", code="PROFILE_REQ")
        clean.append(dict(req_id=rid, category=r["category"], title=r["title"].strip(), source_ref=r["source_ref"].strip(),
                          mandatory=int(r.get("mandatory", 1) in (1, "1", True, "true", "yes", "Y", "y")),
                          check=profile_checks.validate_check(r.get("check"))))
    with db.tx():
        v = (db.scalar("SELECT MAX(version) FROM client_profiles WHERE code=?", (code,)) or 0) + 1
        pid = db.insert("client_profiles", dict(code=code, version=v, name=name.strip(), client=client, status=Status.DRAFT.value,
                                                source_documents_json=json.dumps(docs), notes=notes, created_by=actor.username, created_at=now_iso()))
        for r in clean:
            db.insert("profile_requirements", dict(profile_id=pid, req_id=r["req_id"], category=r["category"], title=r["title"], source_ref=r["source_ref"],
                                                   mandatory=r["mandatory"], check_json=json.dumps(r["check"]) if r["check"] else None))
        audit.log(db, actor, ENTITY, f"{code}/v{v}", "create", after={"requirements": len(clean), "documents": len(docs)})
    return pid


def import_requirements_csv(path: Path) -> list[dict]:
    """CSV columns: req_id,category,title,source_ref[,mandatory][,fact,op,value]."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        chk = {"fact": r["fact"], "op": r["op"], "value": r.get("value")} if r.get("fact") else None
        out.append(dict(req_id=r["req_id"], category=r["category"], title=r["title"], source_ref=r["source_ref"], mandatory=r.get("mandatory") or 1, check=chk))
    return out


def _profile(db: Database, pid: int) -> dict:
    r = db.one("SELECT * FROM client_profiles WHERE id=?", (pid,))
    if not r:
        raise NotFound(f"Profile {pid} not found.")
    return dict(r)


def submit_profile(db: Database, actor: Actor, pid: int) -> None:
    approvals.require_author(actor)
    p = _profile(db, pid)
    if p["status"] != Status.DRAFT.value:
        raise Conflict("Only a Draft profile can be submitted.")
    if not db.one("SELECT 1 FROM profile_requirements WHERE profile_id=?", (pid,)):
        raise ValidationFailed("A profile without requirements cannot be submitted: load the owner's requirements first.", code="PROFILE_EMPTY")
    db.update("client_profiles", {"status": Status.PENDING.value}, "id=?", (pid,))


def approve_profile(db: Database, actor: Actor, pid: int, comments: str | None = None) -> None:
    p = _profile(db, pid)
    approvals.authorize(actor, ENTITY, "approve", created_by=p["created_by"])
    if p["status"] != Status.PENDING.value:
        raise Conflict("Only a Pending Review profile can be approved.")
    with db.tx():
        for old in db.all("SELECT id FROM client_profiles WHERE code=? AND status='Approved'", (p["code"],)):
            db.update("client_profiles", {"status": Status.SUPERSEDED.value}, "id=?", (old["id"],))
        db.update("client_profiles", {"status": Status.APPROVED.value, "approved_by": actor.username, "approved_at": now_iso()}, "id=?", (pid,))
        approvals.record(db, actor, ENTITY, f"{p['code']}/v{p['version']}", "approve", version=p["version"], comments=comments,
                         approved_value={"requirements": db.scalar("SELECT COUNT(*) FROM profile_requirements WHERE profile_id=?", (pid,))})


def link_project(db: Database, actor: Actor, project_id: str, code: str, version: int | None = None) -> None:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    q = "SELECT * FROM client_profiles WHERE code=? AND status='Approved'" + (" AND version=?" if version else "") + " ORDER BY version DESC"
    p = db.one(q, (code, version) if version else (code,))
    if not p:
        raise NotFound(f"No approved profile '{code}'" + (f" v{version}" if version else "") + ".")
    db.execute("INSERT INTO project_profiles(project_id,profile_code,profile_version,linked_by,linked_at) VALUES (?,?,?,?,?) "
               "ON CONFLICT(project_id) DO UPDATE SET profile_code=excluded.profile_code, profile_version=excluded.profile_version, "
               "linked_by=excluded.linked_by, linked_at=excluded.linked_at", (project_id, p["code"], p["version"], actor.username, now_iso()))
    audit.log(db, actor, ENTITY, f"{project_id}->{p['code']}/v{p['version']}", "link", project_id=project_id)


def attest(db: Database, actor: Actor, project_id: str, req_id: str, status: str, evidence: str) -> int:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    link = db.one("SELECT * FROM project_profiles WHERE project_id=?", (project_id,))
    if not link:
        raise NotFound("The project is not linked to a client profile.")
    prof = db.one("SELECT * FROM client_profiles WHERE code=? AND version=?", (link["profile_code"], link["profile_version"]))
    req = db.one("SELECT * FROM profile_requirements WHERE profile_id=? AND req_id=?", (prof["id"], req_id))
    if not req:
        raise NotFound(f"Requirement {req_id} not in profile {prof['code']} v{prof['version']}.")
    if req["check_json"]:
        raise ValidationFailed("This requirement is evaluated automatically from measured facts; it cannot be attested by hand.", code="PROFILE_AUTO")
    if status not in ("Met", "Not met", "Not applicable"):
        raise ValidationFailed("status must be Met, Not met or Not applicable.")
    if not (evidence or "").strip():
        raise ValidationFailed("Evidence (document / record reference) is required for an attestation.", code="EVIDENCE_REQUIRED")
    aid = db.insert("profile_assessments", dict(project_id=project_id, profile_id=prof["id"], req_id=req_id, status=status, evidence=evidence.strip(),
                                                assessed_by=actor.username, assessed_at=now_iso()))
    audit.log(db, actor, "profile_assessment", f"{project_id}/{req_id}", "attest", after={"status": status}, comment=evidence, project_id=project_id)
    return aid


# ------------------------------------------------------------------------------------------------ facts + report
def project_facts(db: Database, project_id: str, est=None) -> dict:
    from ..estimators.estimate import compute_estimate
    from . import mto
    est = est or compute_estimate(db, project_id)
    items = [i for i in est.direct.items.values() if i.pricing_method != "excluded"]
    n = len(items)
    unpriced = sum(1 for i in items if not i.complete)
    boq_items = db.scalar("SELECT COUNT(*) FROM boq_items WHERE project_id=? AND item_type='item'", (project_id,)) or 0
    wbs_assigned = db.scalar("SELECT COUNT(*) FROM boq_wbs WHERE project_id=?", (project_id,)) or 0
    tot_direct = est.direct.direct_cost_total
    nocc = sum((l.amount for l in est.direct.lines if l.amount is not None and not l.cost_code), Decimal(0))
    run = db.one("SELECT id FROM recon_runs WHERE project_id=? ORDER BY id DESC LIMIT 1", (project_id,))
    rec_clean = None
    if run:
        rec_clean = not db.one("SELECT 1 FROM recon_findings WHERE run_id=? AND status='Open' AND severity IN ('Critical','High')", (run["id"],))
    cont = (est.policy or {}).get("contingency") or {}
    cats = [r["code"] for r in db.all("SELECT DISTINCT tax_category code FROM boq_items WHERE project_id=? AND tax_category IS NOT NULL", (project_id,))]
    if est.project.get("tax_category"):
        cats.append(est.project["tax_category"])
    tax_ok = all(v.get("status") == "Approved" for v in est.tax_status.values()) if est.tax_status else None
    return dict(
        estimate_state=est.state, blockers=len(est.blockers), items_total=n, items_unpriced_pct=(None if not n else float(Decimal(unpriced) * 100 / n)),
        synthetic_used=bool(est.direct.synthetic_used), provisional_used=bool(est.direct.provisional_used),
        contingency_pct=(D_opt(cont.get("pct")) if cont else None),
        has_approved_duration=bool(db.one("SELECT 1 FROM project_durations WHERE project_id=? AND status='Approved'", (project_id,))),
        schedule_tasks=db.scalar("SELECT COUNT(*) FROM schedule_tasks WHERE project_id=?", (project_id,)) or 0,
        wbs_assigned_pct=(None if not boq_items else float(Decimal(wbs_assigned) * 100 / boq_items)),
        crosswalk_systems=[r["system"] for r in db.all("SELECT DISTINCT system FROM code_crosswalk WHERE project_id=?", (project_id,))],
        risks_quantified=db.scalar("SELECT COUNT(*) FROM risks WHERE project_id=? AND prob_pct IS NOT NULL AND cost_likely IS NOT NULL", (project_id,)) or 0,
        classification_present=bool(db.one("SELECT 1 FROM analysis_runs WHERE project_id=? AND kind='classification'", (project_id,))),
        boe_generated=bool(db.one("SELECT 1 FROM analysis_runs WHERE project_id=? AND kind='boe'", (project_id,))),
        reconciliation_clean=rec_clean, tax_approved=tax_ok,
        open_clarifications=db.scalar("SELECT COUNT(*) FROM clarifications WHERE project_id=? AND status='Open'", (project_id,)) or 0,
        scope_register_approved=db.scalar("SELECT COUNT(*) FROM scope_register WHERE project_id=? AND status='Approved'", (project_id,)) or 0,
        mto_stale=len(mto.status_report(db, project_id)["stale"]),
        cost_codes_unassigned_pct=(None if tot_direct == 0 else float(nocc * 100 / tot_direct)))


def compliance_report(db: Database, project_id: str, est=None) -> dict:
    link = db.one("SELECT * FROM project_profiles WHERE project_id=?", (project_id,))
    if not link:
        return dict(project_id=project_id, linked=False, statement="No client profile is linked to this project: no compliance statement can be made.", requirements=[])
    prof = dict(db.one("SELECT * FROM client_profiles WHERE code=? AND version=?", (link["profile_code"], link["profile_version"])))
    reqs = rows_to_dicts(db.all("SELECT * FROM profile_requirements WHERE profile_id=? ORDER BY id", (prof["id"],)))
    facts = project_facts(db, project_id, est)
    rows = []
    for r in reqs:
        if r["check_json"]:
            st, detail = profile_checks.evaluate(json.loads(r["check_json"]), facts)
            by, ev, kind = "automatic check", detail, "auto"
        else:
            a = db.one("SELECT * FROM profile_assessments WHERE project_id=? AND profile_id=? AND req_id=? ORDER BY id DESC LIMIT 1", (project_id, prof["id"], r["req_id"]))
            st, by, ev, kind = ((a["status"], f"{a['assessed_by']} {a['assessed_at'][:10]}", a["evidence"], "manual") if a else ("Not assessed", "", "", "manual"))
        rows.append(dict(req_id=r["req_id"], category=r["category"], title=r["title"], source_ref=r["source_ref"], mandatory=bool(r["mandatory"]), kind=kind,
                         status=st, assessed_by=by, evidence=ev))
    mand = [r for r in rows if r["mandatory"]]
    unmet = [r for r in mand if r["status"] not in ("Met", "Not applicable")]
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    if not rows:
        stmt = "The linked profile has no requirements: no compliance statement can be made."
    elif unmet:
        stmt = f"NOT COMPLIANT / INCOMPLETE: {len(unmet)} of {len(mand)} mandatory requirement(s) are not met or not yet assessed."
    else:
        stmt = (f"All {len(mand)} mandatory requirement(s) loaded in profile {prof['code']} v{prof['version']} are met. This covers ONLY the requirements loaded from "
                f"the listed source documents; it is not a statement of compliance with the owner's standards generally.")
    return dict(project_id=project_id, linked=True, profile=dict(code=prof["code"], version=prof["version"], name=prof["name"], client=prof["client"], status=prof["status"],
                                                               source_documents=json.loads(prof["source_documents_json"] or "[]")),
                requirements=rows, counts=counts, mandatory_unmet=[r["req_id"] for r in unmet], statement=stmt, facts=facts)


# ------------------------------------------------------------------------------------------------ classification
def classification_report(db: Database, project_id: str, *, est=None, save_actor: Actor | None = None) -> dict:
    """Classify with the APPROVED scheme and the estimator's approved maturity input; shows the measured maturity facts next to it. No scheme -> no class."""
    from ..estimators.estimate import compute_estimate
    schemes = governed.effective(db, project_id, "classification_scheme")
    mats = governed.effective(db, project_id, "maturity_input")
    est = est or compute_estimate(db, project_id)
    facts = project_facts(db, project_id, est)
    out = dict(project_id=project_id, estimate_state=est.state, measured_maturity={k: facts[k] for k in ("items_total", "items_unpriced_pct", "wbs_assigned_pct", "open_clarifications",
                                                                                                         "mto_stale", "synthetic_used", "provisional_used")},
               scheme=None, definition_pct=None, class_id=None, range=None, notes=[])
    if not schemes:
        out["notes"].append("No approved classification scheme: enter the scheme the company/client works to (governed parameter 'classification_scheme') and have it approved.")
        return out
    sch = schemes[0]["data"]
    out["scheme"] = dict(name=sch["name"], source_document=sch["source_document"], code=schemes[0]["code"], version=schemes[0]["version"])
    if not mats:
        out["notes"].append("No approved maturity input: the estimator must state the definition maturity (%) with its basis ('maturity_input').")
        return out
    m = mats[0]["data"]
    dp = D(m["definition_pct"])
    out["definition_pct"] = dp
    out["definition_basis"] = m["basis"]
    hit = next((c for c in sch["classes"] if D(c["min_definition_pct"]) <= dp < D(c["max_definition_pct"])
                or (dp == 100 and D(c["max_definition_pct"]) == 100)), None)
    if hit is None:
        out["notes"].append(f"Definition maturity {dp}% falls outside every band of the scheme.")
        return out
    out["class_id"] = hit["class_id"]
    out["class_name"] = hit.get("name")
    total = est.commercial.net_price if est.commercial else None
    out["range"] = dict(low_pct=D(hit["low_pct"]), high_pct=D(hit["high_pct"]))
    base = est.commercial.total_cost if est.commercial else None
    if base is not None:
        out["range"].update(base=base, low=base * (1 + D(hit["low_pct"]) / 100), high=base * (1 + D(hit["high_pct"]) / 100), basis="total cost before margin and tax")
    out["notes"].append("Class and range follow the approved scheme and the estimator's stated maturity; they are not derived by the software.")
    if est.state != "Complete":
        out["notes"].append(f"The estimate itself is '{est.state}': the range is indicative only.")
    return out
