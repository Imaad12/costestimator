"""Estimate versions (frozen results), final approval, and the human-gated submission export."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..approvals import engine as approvals
from ..core.errors import ApprovalBlocked, Conflict, NotFound, ValidationFailed
from ..core.money import to_text
from ..core.timeutil import now_iso
from ..database import Database, jload, rows_to_dicts
from ..estimators.estimate import EstimateResult, compute_estimate
from ..exports import documents
from ..models.actor import Actor
from ..models.enums import Entity, Status
from ..reconciliation.engine import final_gate, get_run
from . import assumptions as assumption_service
from . import audit, offers, projects, readiness, snapshots


def _totals_json(est: EstimateResult) -> dict:
    return {k: to_text(v) for k, v in est.totals().items()}


def _result_json(est: EstimateResult) -> dict:
    return {
        "state": est.state, "blockers": est.blockers, "completeness": {k: (to_text(v) if hasattr(v, "quantize") else v) for k, v in est.completeness.items()},
        "flags": est.flags, "exceptions": [{**e, "exposure": to_text(e.get("exposure"))} for e in est.exceptions],
        "items": [{"item_key": k, "direct_cost": to_text(i.direct_cost), "complete": i.complete, "method": i.pricing_method}
                  for k, i in est.direct.items.items()],
        "schedule": None if not est.schedule else [{"item": l.item_key, "qty": to_text(l.quantity), "rate": to_text(l.unit_rate),
                                                    "amount": to_text(l.amount), "status": l.status} for l in est.schedule.lines],
        "trace": [] if not est.commercial else [{"step": t.name, "amount": to_text(t.amount), "formula": t.formula} for t in est.commercial.trace],
    }


def freeze_version(db: Database, actor: Actor, project_id: str, label: str = "", notes: str = "") -> int:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    est = compute_estimate(db, project_id)
    v = (db.scalar("SELECT MAX(version_no) FROM estimate_versions WHERE project_id=?", (project_id,)) or 0) + 1
    vid = db.insert("estimate_versions", dict(project_id=project_id, version_no=v, label=label or f"v{v}", state=est.state,
                                              status=Status.DRAFT.value, inputs_hash=est.fingerprint, totals_json=_totals_json(est),
                                              result_json=_result_json(est), created_by=actor.username, created_at=now_iso(), notes=notes))
    snapshots.store_snapshot(db, actor, vid, est)          # reproducible record of every input used (docs/DATA_MODEL.md)
    audit.log(db, actor, "estimate_version", f"{project_id}/v{v}", "freeze", after={"state": est.state, "hash": est.fingerprint[:12]}, project_id=project_id)
    return vid


def get_version(db: Database, version_id: int) -> dict:
    r = db.one("SELECT * FROM estimate_versions WHERE id=?", (version_id,))
    if not r:
        raise NotFound("Estimate version not found.")
    d = dict(r)
    d["totals"] = jload(d["totals_json"], {})
    d["result"] = jload(d["result_json"], {})
    return d


def list_versions(db: Database, project_id: str) -> list[dict]:
    return rows_to_dicts(db.all("SELECT id, project_id, version_no, label, state, status, created_by, created_at, approved_by, approved_at, "
                                "totals_json FROM estimate_versions WHERE project_id=? ORDER BY version_no", (project_id,)))


def submit_version(db: Database, actor: Actor, version_id: int) -> None:
    approvals.require_author(actor)
    n = db.update("estimate_versions", {"status": Status.PENDING.value}, "id=? AND status='Draft'", (version_id,))
    if not n:
        raise Conflict("Only Draft versions can be submitted for review.")
    audit.log(db, actor, "estimate_version", version_id, "submit")


def approve_version(db: Database, actor: Actor, version_id: int, comments: str | None = None) -> dict:
    """Final estimate approval. Blocked by: open blocking reconciliation findings, preliminary state, or changed inputs."""
    v = get_version(db, version_id)
    approvals.authorize(actor, Entity.ESTIMATE.value, "approve", created_by=v["created_by"])
    approvals.require_production_actor(db, actor, v["project_id"], "approve an estimate")
    if v["status"] != Status.PENDING.value:
        raise Conflict(f"Version must be Pending Review (is {v['status']}).", code="NOT_PENDING")
    gate = final_gate(db, actor, v["project_id"])
    if gate["fingerprint"] != v["inputs_hash"]:
        raise ApprovalBlocked("Estimate inputs changed since this version was frozen. Freeze and review a new version.", code="STALE_VERSION")
    if gate["state"].startswith("Preliminary"):
        raise ApprovalBlocked("The estimate is Preliminary/Incomplete; it cannot receive final approval.", code="ESTIMATE_PRELIMINARY")
    if gate["blocked"]:
        titles = "; ".join(f"[{b['severity']}] {b['rule_code']}" for b in gate["blockers"][:8])
        raise ApprovalBlocked(f"Final approval blocked by {len(gate['blockers'])} unresolved reconciliation finding(s): {titles}",
                              code="RECON_BLOCKED", details=[b["id"] for b in gate["blockers"]])
    with db.tx():
        for old in db.all("SELECT id FROM estimate_versions WHERE project_id=? AND status='Approved'", (v["project_id"],)):
            db.update("estimate_versions", {"status": Status.SUPERSEDED.value}, "id=?", (old["id"],))
        db.update("estimate_versions", {"status": Status.APPROVED.value, "approved_by": actor.username, "approved_at": now_iso()},
                  "id=?", (version_id,))
        approvals.record(db, actor, Entity.ESTIMATE.value, f"{v['project_id']}/v{v['version_no']}", "approve", project_id=v["project_id"],
                         version=v["version_no"], approved_value=v["totals"], evidence=f"reconciliation run {gate['run_id']}", comments=comments)
    return {"approved": True, "recon_run": gate["run_id"]}


def preliminary_export(db: Database, actor: Actor, project_id: str) -> dict[str, str]:
    """Watermarked, always-available outputs with visible exceptions. Never submission-ready."""
    approvals.require_author(actor)
    est = compute_estimate(db, project_id)
    assum = assumption_service.project_assumption_status(db, project_id)
    files = {
        "pricing_schedule": str(documents.client_pricing_schedule(est, submission_ready=False)),
        "estimate_report": str(documents.estimate_report_docx(est, submission_ready=False, assumptions=assum)),
    }
    for kind, f in files.items():
        db.insert("exports", dict(project_id=project_id, kind=kind, submission_ready=0, file_path=f, created_by=actor.username,
                                  created_at=now_iso(), sha256=_sha(f)))
    audit.log(db, actor, "export", project_id, "preliminary_export", after=files, project_id=project_id)
    return files


def _sha(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def approve_tender_export(db: Database, actor: Actor, project_id: str, version_id: int, comments: str | None = None) -> int:
    """Explicit human approval to release a submission-ready export. Re-validates every gate at approval time."""
    v = get_version(db, version_id)
    approvals.authorize(actor, Entity.TENDER_EXPORT.value, "approve")
    approvals.require_production_actor(db, actor, project_id, "approve a tender export")
    if v["project_id"] != project_id or v["status"] != Status.APPROVED.value:
        raise ApprovalBlocked("The estimate version must be Approved before a tender export can be approved.", code="ESTIMATE_NOT_APPROVED")
    gate = final_gate(db, actor, project_id)
    if gate["fingerprint"] != v["inputs_hash"]:
        raise ApprovalBlocked("Estimate changed since final approval; re-approve a new version.", code="STALE_VERSION")
    if gate["blocked"]:
        raise ApprovalBlocked("Reconciliation has unresolved blocking findings.", code="RECON_BLOCKED", details=[b["id"] for b in gate["blockers"]])
    o = offers.latest_offer(db, project_id)
    if not o or o["status"] != Status.APPROVED.value:
        raise ApprovalBlocked("An approved letter of offer matching the pricing schedule is required.", code="OFFER_NOT_APPROVED")
    return approvals.record(db, actor, Entity.TENDER_EXPORT.value, f"{project_id}/v{v['version_no']}", "approve", project_id=project_id,
                            version=v["version_no"], approved_value={"recon_run": gate["run_id"], "offer_version": o["version_no"]}, comments=comments)


def require_export_gate(db: Database, actor: Actor, project_id: str, version_id: int, approval_id: int):
    """Shared by every submission-ready export: a valid, still-current tender-export approval, a clean reconciliation gate and an approved, unchanged estimate."""
    approvals.require_author(actor)
    ap = db.one("SELECT * FROM approvals WHERE id=? AND entity_type='tender_export' AND action='approve'", (approval_id,))
    v = get_version(db, version_id)
    if not ap or ap["project_id"] != project_id or ap["entity_id"] != f"{project_id}/v{v['version_no']}":
        raise ApprovalBlocked("No valid tender-export approval for this estimate version.", code="EXPORT_NOT_APPROVED")
    # re-check at export time: nothing may have changed since approval
    gate = final_gate(db, actor, project_id)
    if gate["fingerprint"] != v["inputs_hash"] or gate["blocked"] or v["status"] != Status.APPROVED.value:
        raise ApprovalBlocked("Project state changed after approval or blocking findings exist; submission export refused.", code="EXPORT_BLOCKED")
    return v, gate


def export_submission(db: Database, actor: Actor, project_id: str, version_id: int, approval_id: int) -> dict[str, str]:
    """Produce the export package. It is SUBMISSION READY only when `readiness.evaluate` verifies a production approval chain (registered human approvers, production
    environment, no synthetic/demo data, clear gate). A demonstration project gets a clearly labelled DEMONSTRATION export instead; any other project that fails is refused."""
    approvals.require_production_actor(db, actor, project_id, "export a submission package")
    v, gate = require_export_gate(db, actor, project_id, version_id, approval_id)
    r = readiness.evaluate(db, project_id, version_id, approval_id, gate=gate)
    if r["classification"] == "not_ready":
        raise ApprovalBlocked("Submission export refused: the production approval chain is not satisfied - " + "; ".join(r["reasons"][:6]), code="NOT_PRODUCTION_READY", details=r["reasons"])
    ready = r["production_ready"]
    est = gate["estimate"]
    assum = assumption_service.project_assumption_status(db, project_id)
    o = offers.latest_offer(db, project_id)
    files = {
        "pricing_schedule": str(documents.client_pricing_schedule(est, submission_ready=ready, readiness=r)),
        "estimate_report": str(documents.estimate_report_docx(est, submission_ready=ready, version_label=f"v{v['version_no']}", assumptions=assum, readiness=r)),
        "letter_of_offer": o["file_path"],
    }
    run = get_run(db, gate["run_id"])
    files["reconciliation_report"] = str(documents.reconciliation_report_xlsx(run, est.project))
    for kind, f in files.items():
        db.insert("exports", dict(project_id=project_id, kind=kind, submission_ready=int(ready), estimate_version_id=version_id, file_path=f,
                                  sha256=_sha(f), created_by=actor.username, created_at=now_iso(), approval_ref=str(approval_id),
                                  readiness=r["classification"], readiness_json=json.dumps(r, default=str)))
    if ready:
        db.update("estimate_versions", {"submitted_at": now_iso()}, "id=?", (version_id,))
    audit.log(db, actor, "export", project_id, "submission_export" if ready else "demonstration_export", after={**files, "readiness": r["classification"], "reasons": r["reasons"][:10]}, project_id=project_id)
    return files


def export_client_form(db: Database, actor: Actor, project_id: str, template_path, mapping: dict, *, version_id: int | None = None, approval_id: int | None = None) -> dict:
    """Fill a client-supplied form workbook. With a version and a valid, current tender-export approval the file is submission-ready (same gate as export_submission);
    without them it is a PRELIMINARY copy with a banner, never presented as final."""
    from pathlib import Path

    from ..exports import client_form
    from . import workspaces
    approvals.require_author(actor)
    template_path = Path(template_path)
    if not template_path.is_absolute():
        template_path = workspaces.resolve_dir(project_id, db) / template_path
    root = workspaces.resolve_dir(project_id, db).resolve()
    if root not in template_path.resolve().parents:
        raise ValidationFailed("The form template must be a file inside the project's workspace (copy it into '8. Commercial Submission' or '1. Tender Documents').", code="FORM_PATH")
    if not template_path.exists():
        raise ValidationFailed(f"Template not found: {template_path}", code="FILE_NOT_FOUND")
    if (version_id is None) != (approval_id is None):
        raise ValidationFailed("Give both version_id and approval_id for a submission-ready form, or neither for a preliminary copy.", code="FORM_ARGS")
    if version_id is not None:
        approvals.require_production_actor(db, actor, project_id, "export a client form")
        v, gate = require_export_gate(db, actor, project_id, version_id, approval_id)
        r = readiness.evaluate(db, project_id, version_id, approval_id, gate=gate)
        if r["classification"] == "not_ready":
            raise ApprovalBlocked("Client-form export refused: the production approval chain is not satisfied - " + "; ".join(r["reasons"][:6]), code="NOT_PRODUCTION_READY", details=r["reasons"])
        est, ready, banner = gate["estimate"], r["production_ready"], (None if r["production_ready"] else readiness.banner(r))
    else:
        est, ready = compute_estimate(db, project_id), False
        banner = "PRELIMINARY - NOT FOR SUBMISSION" + ((" - DEMONSTRATION" + (" / SYNTHETIC DATA" if est.flags.get("synthetic") else "")) if est.project.get("is_demo") else "")
    d = workspaces.area_dir(project_id, "commercial", db)
    n = 1
    while (d / f"ClientForm_{project_id}_{n:02d}{'' if ready else '_PRELIMINARY'}.xlsx").exists():
        n += 1
    out = d / f"ClientForm_{project_id}_{n:02d}{'' if ready else '_PRELIMINARY'}.xlsx"
    rep = client_form.fill(est, template_path, mapping, out, banner=banner)
    db.insert("exports", dict(project_id=project_id, kind="client_form", submission_ready=int(ready), estimate_version_id=version_id, file_path=str(out), sha256=_sha(str(out)),
                              created_by=actor.username, created_at=now_iso(), approval_ref=str(approval_id) if approval_id else None))
    audit.log(db, actor, "export", project_id, "client_form", after={"file": out.name, "submission_ready": ready, "rows": rep["rows_filled"]}, project_id=project_id)
    rep["submission_ready"] = ready
    return rep
