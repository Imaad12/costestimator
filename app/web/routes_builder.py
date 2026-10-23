"""BOQ builder: pick items from the catalogue, type the quantities, get a BOQ document (and optionally add the lines to a project's BOQ) in a few clicks."""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, Response

from ..api.deps import current_actor
from ..core.errors import AppError
from ..database import get_db, rows_to_dicts
from ..imports import boq as boq_import
from ..models.actor import Actor
from ..services import projects
from . import boq_builder
from .routes import back, page

router = APIRouter()


@router.get("/boq-builder", response_class=HTMLResponse)
def builder(request: Request, project: str = "", actor: Actor = Depends(current_actor)):
    db = get_db()
    projs = rows_to_dicts(db.all("SELECT id, name FROM projects WHERE archived_at IS NULL ORDER BY id"))
    cat = boq_builder.catalogue(db)
    return page(request, "boq_builder.html", actor, divisions=cat, projects=projs, project=project, kinds=boq_builder.TYPE_LABELS, total=sum(len(d["items"]) for d in cat), title="BOQ builder")


@router.post("/boq-builder/build")
async def build(request: Request, actor: Actor = Depends(current_actor)):
    form = await request.form(max_fields=5000)   # one quantity box per catalogue item (about 1,000+)
    db = get_db()
    title, pid, mode = (form.get("title") or "").strip(), (form.get("project") or "").strip(), form.get("mode") or "download"
    try:
        lines = boq_builder.parse_selection(form, db)
        if mode == "project":
            if not pid:
                raise AppError("Choose the project to add these lines to.", code="NO_PROJECT")
            slug = re.sub(r"[^A-Za-z0-9]+", "_", title or "builder_boq").strip("_")[:40] or "builder_boq"
            d = projects.project_dir(pid, "uploads")
            d.mkdir(parents=True, exist_ok=True)
            path, i = d / f"{slug}.xlsx", 1
            while path.exists():
                i += 1
                path = d / f"{slug}_{i}.xlsx"
            boq_builder.write_import_file(path, lines)
            s = boq_import.import_boq(db, actor, pid, path)
            return back(f"/projects/{pid}/boq", ok=f"Added from the BOQ builder: {s['items_new']} new line(s), {s['items_unchanged']} unchanged, {s['rejected']} rejected, {s['needs_review']} need review. Map them to assemblies next.")
        with tempfile.TemporaryDirectory() as t:
            p = boq_builder.write_submission(Path(t) / "boq.xlsx", lines, title=title, project=pid or None, prepared_by=actor.display_name or actor.username)
            data = p.read_bytes()
    except AppError as e:
        return back("/boq-builder" + (f"?project={pid}" if pid else ""), err=f"{e.message}")
    fn = (re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_") or "BOQ") + ".xlsx"
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{fn}"'})


# ------------------------------------------------------------------ BOQ upload: a whole workbook (one sheet per trade) in one go
from fastapi import File, UploadFile  # noqa: E402

from ..api.routes import save_upload  # noqa: E402
from ..config import get_settings  # noqa: E402


def _upload_path(pid: str, name: str) -> Path:
    return (projects.project_dir(pid, "uploads") if pid else get_settings().projects_dir / "_uploads") / Path(name).name


def _projects(db):
    return rows_to_dicts(db.all("SELECT id, name FROM projects WHERE archived_at IS NULL ORDER BY id"))


@router.get("/boq-upload", response_class=HTMLResponse)
def boq_upload_page(request: Request, project: str = "", actor: Actor = Depends(current_actor)):
    return page(request, "boq_upload.html", actor, projects=_projects(get_db()), project=project, analysis=None, title="BOQ upload")


@router.post("/boq-upload/analyse", response_class=HTMLResponse)
async def boq_upload_analyse(request: Request, file: UploadFile = File(...), project: str = Form(""), actor: Actor = Depends(current_actor)):
    db = get_db()
    try:
        path = save_upload(project, file)
        if path.suffix.lower() not in (".xlsx", ".xlsm", ".csv"):
            raise AppError("Upload an Excel (.xlsx) or CSV file. PDFs and images are not read - export the table to Excel first.", code="UNSUPPORTED_FILE")
        analysis = boq_import.analyse_workbook(path)
    except AppError as e:
        return back("/boq-upload" + (f"?project={project}" if project else ""), err=e.message)
    return page(request, "boq_upload.html", actor, projects=_projects(db), project=project, analysis=analysis, stored=path.name, title="BOQ upload")


@router.post("/boq-upload/import")
async def boq_upload_import(request: Request, actor: Actor = Depends(current_actor)):
    form = await request.form(max_fields=500)
    pid, stored = (form.get("project") or "").strip(), form.get("stored") or ""
    sheets = form.getlist("sheet")
    db = get_db()
    try:
        if not sheets:
            raise AppError("Tick at least one sheet to import.", code="NOTHING_SELECTED")
        src = _upload_path(pid, stored)
        if not src.exists():
            raise AppError("The uploaded file is no longer available; please upload it again.", code="FILE_GONE")
        if not pid:
            name = (form.get("new_name") or "").strip()
            if not name:
                raise AppError("Give the new project a name (or choose an existing project).", code="FIELD_REQUIRED")
            pid = projects.create_project(db, actor, name=name, client=(form.get("new_client") or "").strip(), location=(form.get("new_location") or "").strip())
        res = boq_import.import_workbook(db, actor, pid, src, sheets=sheets, revision=(form.get("revision") or "").strip() or None)
    except AppError as e:
        return back("/boq-upload" + (f"?project={pid}" if pid else ""), err=e.message)
    parts = ", ".join(f'{s["name"]} {s["items_new"] + s["items_unchanged"]}' for s in res["sheets"])
    msg = f'Imported {res["items_new"]} new line(s) ({res["items_unchanged"]} unchanged, {res["rejected"]} rejected, {res["needs_review"]} need review) from {len(res["sheets"])} sheet(s): {parts}.'
    if res["errors"]:
        msg += " Not imported: " + "; ".join(res["errors"])
    return back(f"/projects/{pid}/boq", ok=msg)
