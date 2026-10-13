"""REST API (JSON). All authorisation is enforced in the services; the API adds authentication only."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from ..approvals import engine as approvals
from ..core.errors import AppError, ValidationFailed
from ..database import Database, jload, rows_to_dicts
from ..estimators.estimate import compute_estimate
from ..excel import roundtrip
from ..excel.master import build_master
from ..imports import boq as boq_import
from ..imports import datasets
from ..models.actor import Actor
from ..procurement import leveling, needs, quotes
from ..reconciliation import engine as recon
from ..reporting import dashboard
from ..services import assemblies, assumptions, audit, auth, boq, estimates, indirects, projects, rates, registers, suppliers
from ..config import get_settings
from .actions import run as run_action
from .deps import COOKIE, current_actor, database
from .serializers import estimate_summary, ser

router = APIRouter(prefix="/api")


def save_upload(project_id: str, f: UploadFile, sub: str = "uploads") -> Path:
    """Store an upload under the project's uploads folder without ever overwriting an existing file."""
    d = projects.project_dir(project_id, sub) if project_id else (get_settings().projects_dir / "_uploads")
    d.mkdir(parents=True, exist_ok=True)
    name = Path(f.filename or "upload").name
    dest = d / name
    i = 1
    while dest.exists():
        dest = d / f"{dest.stem.split('__')[0]}__{i}{Path(name).suffix}"
        i += 1
    with open(dest, "wb") as out:
        shutil.copyfileobj(f.file, out)
    return dest


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/auth/login")
def login(body: dict, db: Database = Depends(database)):
    a = auth.authenticate(db, body.get("username", ""), body.get("password", ""))
    token = auth.make_token(a.username)
    r = JSONResponse({"token": token, "user": {"username": a.username, "role": a.role}})
    r.set_cookie(COOKIE, token, httponly=True, samesite="strict")
    return r


@router.get("/me")
def me(actor: Actor = Depends(current_actor)):
    return {"username": actor.username, "role": actor.role, "name": actor.display_name}


@router.post("/actions/{name}")
def do_action(name: str, params: dict, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    return ser({"result": run_action(db, actor, name, params)})


# ------------------------------------------------------------------ reads
@router.get("/dashboard")
def get_dashboard(actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    return ser(dashboard.dashboard(db))


@router.get("/projects")
def list_projects(actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    return projects.list_projects(db, include_archived=True)


@router.get("/projects/{pid}")
def get_project(pid: str, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    return projects.get_project(db, pid)


@router.get("/projects/{pid}/estimate")
def get_estimate(pid: str, preliminary: bool = False, lines: bool = False, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    return estimate_summary(compute_estimate(db, pid, include_unapproved=preliminary), include_lines=lines)


@router.get("/projects/{pid}/boq")
def get_boq(pid: str, q: str | None = None, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    return boq.list_items(db, pid, q=q, only_items=False)


@router.get("/reports")
def list_reports(actor: Actor = Depends(current_actor)):
    from ..reporting import registry
    return registry.listing()


@router.get("/projects/{pid}/report/{name}")
def get_report(pid: str, name: str, request: Request, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    from ..reporting import registry
    return ser(registry.run_report(db, name, pid, dict(request.query_params)))


@router.get("/projects/{pid}/analysis-runs")
def get_analysis_runs(pid: str, kind: str | None = None, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    from ..services import analysis
    return analysis.list_runs(db, pid, kind)


@router.get("/analysis-runs/{rid}")
def get_analysis_run(rid: int, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    from ..services import analysis
    return analysis.get_run(db, rid)


@router.get("/projects/{pid}/params")
def get_params(pid: str, kind: str | None = None, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    from ..services import governed
    return ser(governed.list_params(db, kind, pid))


@router.get("/param-kinds")
def get_param_kinds(actor: Actor = Depends(current_actor)):
    from ..services import governed
    return governed.kinds()


@router.get("/projects/{pid}/changes")
def get_changes(pid: str, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    return boq.pending_changes(db, pid)


@router.get("/projects/{pid}/procurement")
def get_procurement(pid: str, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    return needs.register(db, pid)


@router.get("/projects/{pid}/reconciliation")
def get_recon(pid: str, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    return ser(recon.get_run(db, project_id=pid))


@router.get("/projects/{pid}/versions")
def get_versions(pid: str, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    return estimates.list_versions(db, pid)


@router.get("/projects/{pid}/approvals")
def get_approvals(pid: str, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    return rows_to_dicts(db.all("SELECT * FROM approvals WHERE project_id=? ORDER BY id DESC LIMIT 1000", (pid,)))


@router.get("/projects/{pid}/leveling/{package_id}")
def get_leveling(pid: str, package_id: str, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    return ser(leveling.level_package(db, package_id))


@router.get("/resources")
def list_resources(q: str | None = None, type: str | None = None, cost_code: str | None = None, limit: int = 200, offset: int = 0,
                   actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    sql, p = "SELECT * FROM resources WHERE is_active=1", []
    if q:
        sql += " AND (description LIKE ? OR aliases LIKE ? OR id LIKE ?)"; p += [f"%{q}%"] * 3
    if type:
        sql += " AND resource_type=?"; p.append(type)
    if cost_code:
        sql += " AND cost_code LIKE ?"; p.append(cost_code + "%")
    return rows_to_dicts(db.all(sql + " ORDER BY id LIMIT ? OFFSET ?", p + [min(limit, 1000), offset]))


@router.get("/resources/{rid}")
def get_resource(rid: str, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    return {"resource": dict(rates.get_resource(db, rid)), "rates": rates.rates_for(db, rid)}


@router.get("/assumptions")
def list_assumptions(family: str | None = None, status: str | None = None, q: str | None = None, actor: Actor = Depends(current_actor),
                     db: Database = Depends(database)):
    return assumptions.list_assumptions(db, family, status, q)


@router.get("/assemblies")
def list_assemblies(cost_code: str | None = None, q: str | None = None, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    return assemblies.list_assemblies(db, cost_code, q)


@router.get("/assemblies/{code}")
def get_assembly(code: str, version: int | None = None, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    a = assemblies.get(db, code, version)
    return {"assembly": a, "lines": assemblies.lines(db, a["pk"]), "problems": assemblies.validate(db, a["pk"])}


@router.get("/cost-codes")
def cost_codes(actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    return rows_to_dicts(db.all("SELECT * FROM cost_codes ORDER BY code"))


@router.get("/sources")
def sources(actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    return rows_to_dicts(db.all("SELECT * FROM sources ORDER BY source_id"))


@router.get("/suppliers")
def list_suppliers(q: str | None = None, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    return suppliers.list_suppliers(db, q)


@router.get("/audit/verify")
def audit_verify(actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    return audit.verify_chain(db)


@router.get("/audit/{etype}/{eid:path}")
def audit_history(etype: str, eid: str, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    return audit.history(db, etype, eid)


# ------------------------------------------------------------------ uploads
@router.post("/projects/{pid}/boq/preview")
def boq_preview(pid: str, file: UploadFile = File(...), sheet: str | None = Form(None), actor: Actor = Depends(current_actor)):
    tmp = Path(tempfile.mkdtemp()) / Path(file.filename or "upload").name
    with open(tmp, "wb") as out:
        shutil.copyfileobj(file.file, out)
    try:
        pv = boq_import.preview(tmp, sheet)
        return ser(pv)
    finally:
        shutil.rmtree(tmp.parent, ignore_errors=True)


@router.post("/projects/{pid}/boq/import")
def boq_do_import(pid: str, file: UploadFile = File(...), sheet: str | None = Form(None), mapping: str | None = Form(None),
                  header_row: int | None = Form(None), revision: str | None = Form(None), actor: Actor = Depends(current_actor),
                  db: Database = Depends(database)):
    import json
    approvals.require_author(actor)
    path = save_upload(pid, file)
    m = json.loads(mapping) if mapping else None
    return ser(boq_import.import_boq(db, actor, pid, path, mapping=m, sheet=sheet, header_row=header_row, revision=revision))


@router.post("/projects/{pid}/takeoff/import")
def takeoff_import(pid: str, file: UploadFile = File(...), sheet: str | None = Form(None), actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    approvals.require_author(actor)
    return ser(boq_import.import_takeoff_resources(db, actor, pid, save_upload(pid, file), sheet))


@router.post("/quotations/{qid}/import")
def quote_import(qid: str, file: UploadFile = File(...), actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    approvals.require_author(actor)
    q = quotes.get_quotation(db, qid)
    return ser(quotes.import_quotation_lines(db, actor, qid, save_upload(q["project_id"] or "", file, "procurement")))


@router.post("/datasets/stage")
def dataset_stage(file: UploadFile = File(...), source_id: str | None = Form(None), actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    approvals.require_author(actor)
    return ser(datasets.stage_rate_dataset(db, actor, save_upload("", file), source_id=source_id))


@router.get("/datasets/{did}")
def dataset_rows(did: int, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    return ser(datasets.staged_rows(db, did))


@router.post("/projects/{pid}/workbook/import")
def workbook_import(pid: str, file: UploadFile = File(...), actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    approvals.require_author(actor)
    rep = roundtrip.import_master(db, actor, pid, save_upload(pid, file, "estimate"))
    return ser({"created": rep.created, "ignored": rep.ignored, "errors": rep.errors, "notes": rep.notes})


# ------------------------------------------------------------------ downloads
@router.get("/projects/{pid}/workbook")
def workbook_download(pid: str, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    out = projects.output_dir(pid, "estimate") / f"estimate_master_{pid}.xlsx"
    build_master(out, db, pid)
    return FileResponse(out, filename=out.name, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.get("/exports/{export_id}")
def export_download(export_id: int, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    r = db.one("SELECT * FROM exports WHERE id=?", (export_id,))
    if not r or not Path(r["file_path"]).exists():
        raise ValidationFailed("Export not found.")
    return FileResponse(r["file_path"], filename=Path(r["file_path"]).name)


@router.get("/rfq/{rfq_id}/{fmt}")
def rfq_download(rfq_id: str, fmt: str, actor: Actor = Depends(current_actor), db: Database = Depends(database)):
    from ..procurement import rfq
    if fmt == "xlsx":
        return FileResponse(rfq.export_xlsx(db, rfq_id))
    if fmt == "docx":
        return FileResponse(rfq.export_docx(db, rfq_id))
    if fmt == "txt":
        return JSONResponse({"email": rfq.email_text(db, rfq_id)})
    raise ValidationFailed("fmt must be xlsx, docx or txt.")
