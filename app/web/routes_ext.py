"""Web pages for the iteration-4 modules: generic analysis viewer, governed inputs, structure (WBS / cross-walk / programme)."""
from __future__ import annotations

import json
import re
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from ..api.deps import current_actor
from ..api.serializers import ser
from ..core.errors import AppError
from ..database import get_db
from ..models.actor import Actor
from ..reporting import registry
from ..services import analysis, governed, projects, wbs
from .routes import page

router = APIRouter()
_LONG = re.compile(r"^-?\d+\.\d{7,}$")


def display_round(o, dp: int = 4):
    """Display-only: long decimal strings (division results) are shown to `dp` places. The API and stored runs keep the exact values."""
    if isinstance(o, str) and _LONG.match(o):
        return str(Decimal(o).quantize(Decimal(1).scaleb(-dp), ROUND_HALF_UP))
    if isinstance(o, dict):
        return {k: display_round(v, dp) for k, v in o.items()}
    if isinstance(o, list):
        return [display_round(v, dp) for v in o]
    return o


def _proj(pid: str) -> dict:
    return projects.get_project(get_db(), pid)


@router.get("/projects/{pid}/analysis", response_class=HTMLResponse)
def analysis_index(pid: str, request: Request, actor: Actor = Depends(current_actor)):
    groups: dict[str, list] = {}
    for r in registry.listing():
        groups.setdefault(r["group"], []).append(r)
    return page(request, "analysis.html", actor, project=_proj(pid), groups=groups, runs=analysis.list_runs(get_db(), pid), title="Analysis", tab="analysis")


@router.get("/projects/{pid}/analysis/{name}", response_class=HTMLResponse)
def analysis_run(pid: str, name: str, request: Request, actor: Actor = Depends(current_actor)):
    params = {k: v for k, v in request.query_params.items()}
    rep = registry.REPORTS.get(name)
    ctx = dict(project=_proj(pid), rname=name, label=rep.label if rep else name, params_json=json.dumps(params), qs=urlencode(params), saved=None, result=None, error=None,
               title="Analysis", tab="analysis")
    try:
        ctx["result"] = display_round(ser(registry.run_report(get_db(), name, pid, params)))
    except AppError as e:
        ctx["error"] = e
    return page(request, "analysis_result.html", actor, **ctx)


@router.get("/projects/{pid}/analysis-run/{rid}", response_class=HTMLResponse)
def analysis_saved(pid: str, rid: int, request: Request, actor: Actor = Depends(current_actor)):
    r = analysis.get_run(get_db(), rid)
    rep = registry.REPORTS.get(r["kind"])
    return page(request, "analysis_result.html", actor, project=_proj(pid), rname=r["kind"], label=(rep.label if rep else r["kind"]) + f" (saved run #{rid})", params_json="{}", qs="",
                saved=r, result=display_round(r["result"]), error=None, title="Analysis", tab="analysis")


@router.get("/projects/{pid}/inputs", response_class=HTMLResponse)
def inputs_page(pid: str, request: Request, actor: Actor = Depends(current_actor)):
    kinds = governed.kinds()
    for k in kinds:
        k["fields_json"] = json.dumps(k["fields"], ensure_ascii=False)
    params = governed.list_params(get_db(), None, pid)
    for p in params:
        p["data_text"] = json.dumps(p["data"], ensure_ascii=False)
    return page(request, "inputs.html", actor, project=_proj(pid), kinds=kinds, params=params, title="Inputs", tab="inputs")


@router.get("/projects/{pid}/structure", response_class=HTMLResponse)
def structure_page(pid: str, request: Request, actor: Actor = Depends(current_actor)):
    from ..database import rows_to_dicts
    from ..services import mto, registers
    db = get_db()
    st = mto.status_report(db, pid)
    return page(request, "structure.html", actor, project=_proj(pid), wbs=wbs.list_nodes(db, pid),
                crosswalk=rows_to_dicts(db.all("SELECT * FROM code_crosswalk WHERE project_id=? ORDER BY system, client_code", (pid,))),
                tasks=rows_to_dicts(db.all("SELECT * FROM schedule_tasks WHERE project_id=? ORDER BY id", (pid,))),
                mto_apps=[dict(a, flags=", ".join(a["flags"])) for a in st["applications"]], templates=sorted(mto.templates().values(), key=lambda t: t["code"]),
                risks=registers.list_risks(db, pid), link=db.one("SELECT * FROM project_profiles WHERE project_id=?", (pid,)), title="Structure", tab="structure")
