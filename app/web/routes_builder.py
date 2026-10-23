"""BOQ builder: pick items from the catalogue, type the quantities, get a BOQ document (and optionally add the lines to a project's BOQ) in a few clicks."""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, Request
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
