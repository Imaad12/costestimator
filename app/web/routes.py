"""Server-rendered local web UI. Authentication here; authorisation is enforced by the services (never only in the UI)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..api.actions import ACTIONS, run
from ..api.deps import COOKIE, current_actor
from ..api.routes import save_upload
from ..config import get_settings
from ..core.errors import AppError, AuthRequired
from ..database import Database, get_db, jload, rows_to_dicts
from ..estimators.estimate import compute_estimate
from ..excel.master import build_master
from ..imports import boq as boq_import
from ..imports import datasets
from ..models.actor import Actor
from ..models.enums import RATE_TYPE_VALUES, ROLE_VALUES
from ..procurement import leveling, needs, quotes, rfq
from ..reconciliation import engine as recon
from ..reporting import dashboard, history
from ..rate_updates import candidates as rate_candidates
from ..rate_updates import importer as rate_importer
from ..rate_updates import index_import, refresh as source_refresh
from ..reporting import completeness
from ..services import (assemblies, assumptions, audit, auth, backup, boq, commercial, estimates, indirects, offers, project_index, projects, rates, registers,
                        snapshots, suggestions, suppliers, workspaces)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def page(request: Request, name: str, actor: Actor | None, **ctx):
    ctx.setdefault("ok", request.query_params.get("ok"))
    ctx.setdefault("err", request.query_params.get("err"))
    if actor is not None:
        try:
            ctx.setdefault("lib", workspaces.library_versions(get_db()))
        except Exception:
            ctx.setdefault("lib", None)
    return templates.TemplateResponse(request, name, {"actor": actor, "request": request, **ctx})


def back(next_url: str, ok: str | None = None, err: str | None = None) -> RedirectResponse:
    sep = "&" if "?" in next_url else "?"
    q = urlencode({"ok": ok} if ok else {"err": err})
    return RedirectResponse(f"{next_url}{sep}{q}", status_code=303)


def db_() -> Database:
    return get_db()


# ------------------------------------------------------------------ auth
@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return page(request, "login.html", None)


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    try:
        a = auth.authenticate(get_db(), username, password)
    except AppError as e:
        return page(request, "login.html", None, err=e.message)
    r = RedirectResponse("/", status_code=303)
    r.set_cookie(COOKIE, auth.make_token(a.username), httponly=True, samesite="strict")
    return r


@router.get("/logout")
def logout():
    r = RedirectResponse("/login", status_code=303)
    r.delete_cookie(COOKIE)
    return r


# ------------------------------------------------------------------ generic action endpoint
@router.post("/ui/do/{name}")
async def do(name: str, request: Request, actor: Actor = Depends(current_actor)):
    form = dict((await request.form()).items())
    nxt = form.pop("_next", "/")
    try:
        result = run(get_db(), actor, name, form)
    except AppError as e:
        return back(nxt, err=f"{e.code}: {e.message}")
    except ValueError as e:
        return back(nxt, err=str(e))
    if isinstance(result, str) and "{result}" in nxt:
        nxt = nxt.replace("{result}", quote(result))
    msg = f"Done: {name.replace('_', ' ')}" + (f" → {result}" if isinstance(result, (str, int)) else "")
    if name == "run_reconciliation" and isinstance(result, dict):
        msg += f" (open: {result.get('open_by_severity')})"
    return back(nxt, ok=msg)


# ------------------------------------------------------------------ dashboard / projects
@router.get("/", response_class=HTMLResponse)
def home(request: Request, actor: Actor = Depends(current_actor)):
    return page(request, "dashboard.html", actor, d=dashboard.dashboard(get_db()), title="Dashboard")


@router.get("/projects", response_class=HTMLResponse)
def projects_list(request: Request, actor: Actor = Depends(current_actor)):
    db = get_db()
    return page(request, "projects.html", actor, projects=projects.list_projects(db, include_archived=True),
                regions=rows_to_dicts(db.all("SELECT code, name FROM regions")), title="Projects")


def _proj(pid: str) -> dict:
    return projects.get_project(get_db(), pid)


@router.get("/projects/{pid}/", response_class=HTMLResponse)
def project_home(pid: str, request: Request, actor: Actor = Depends(current_actor)):
    db = get_db()
    est = compute_estimate(db, pid)
    return page(request, "project.html", actor, project=_proj(pid), est=est, versions=estimates.list_versions(db, pid),
                changes=boq.pending_changes(db, pid), title=_proj(pid)["name"], tab="")


@router.get("/projects/{pid}", response_class=HTMLResponse)
def project_home2(pid: str, request: Request, actor: Actor = Depends(current_actor)):
    return project_home(pid, request, actor)


# ---- BOQ
@router.get("/projects/{pid}/boq", response_class=HTMLResponse)
def project_boq(pid: str, request: Request, q: str | None = None, actor: Actor = Depends(current_actor)):
    db = get_db()
    imports = rows_to_dicts(db.all("SELECT * FROM boq_imports WHERE project_id=? ORDER BY id DESC", (pid,)))
    for i in imports:
        i["summary"] = jload(i["summary_json"], {})
    rej = rows_to_dicts(db.all("SELECT * FROM boq_rejected_rows WHERE project_id=? ORDER BY id", (pid,)))
    return page(request, "boq.html", actor, project=_proj(pid), items=boq.list_items(db, pid, q=q, only_items=False), imports=imports, rejected=rej,
                changes=boq.pending_changes(db, pid), q=q or "", preview=None, title="BOQ import", tab="boq")


@router.post("/projects/{pid}/boq/preview", response_class=HTMLResponse)
async def boq_preview(pid: str, request: Request, file: UploadFile = File(...), actor: Actor = Depends(current_actor)):
    path = save_upload(pid, file)
    try:
        pv = boq_import.preview(path)
    except AppError as e:
        return back(f"/projects/{pid}/boq", err=e.message)
    db = get_db()
    return page(request, "boq.html", actor, project=_proj(pid), items=boq.list_items(db, pid, only_items=False), imports=[], rejected=[],
                changes=boq.pending_changes(db, pid), q="", preview=pv, preview_file=path.name, title="BOQ import", tab="boq",
                fields=boq_import.FIELDS)


@router.post("/projects/{pid}/boq/import")
async def boq_do_import(pid: str, request: Request, actor: Actor = Depends(current_actor)):
    form = await request.form()
    name = form["stored_name"]
    path = projects.project_dir(pid, "uploads") / Path(name).name
    mapping = {f: (int(form[f"map_{f}"]) if form.get(f"map_{f}", "") != "" else None) for f in boq_import.FIELDS}
    try:
        s = boq_import.import_boq(get_db(), actor, pid, path, mapping=mapping, sheet=form.get("sheet") or None,
                                  header_row=int(form["header_row"]) if form.get("header_row") else None, revision=form.get("revision") or None)
    except AppError as e:
        return back(f"/projects/{pid}/boq", err=f"{e.code}: {e.message}")
    return back(f"/projects/{pid}/boq", ok=f"Imported: {s['items_new']} new, {s['items_unchanged']} unchanged, {s['change_requests']} change request(s), "
                f"{s['rejected']} rejected, {s['needs_review']} need review.")


@router.post("/projects/{pid}/takeoff/import")
async def takeoff(pid: str, file: UploadFile = File(...), actor: Actor = Depends(current_actor)):
    try:
        r = boq_import.import_takeoff_resources(get_db(), actor, pid, save_upload(pid, file, "estimate"))
    except AppError as e:
        return back(f"/projects/{pid}/boq", err=e.message)
    return back(f"/projects/{pid}/boq", ok=f"Takeoff resources: {r['lines_added']} lines, {len(r['rejected'])} rejected.")


# ---- mapping
@router.get("/projects/{pid}/mapping", response_class=HTMLResponse)
def project_mapping(pid: str, request: Request, q: str = "", actor: Actor = Depends(current_actor)):
    db = get_db()
    from ..ai import service as ai_service
    similar = ai_service.find_historical(db, q, exclude_project=pid) if q else []
    return page(request, "mapping.html", actor, similar=similar, q=q, project=_proj(pid), items=boq.list_items(db, pid), assemblies=assemblies.list_assemblies(db, project_id=pid),
                suggestions=suggestions.list_suggestions(db, pid, kind="mapping"), cost_codes=rows_to_dicts(db.all("SELECT code, name FROM cost_codes ORDER BY code")),
                resources=rows_to_dicts(db.all("SELECT id, description FROM resources WHERE resource_type='subcontract' ORDER BY id LIMIT 300")),
                title="Mapping", tab="mapping")


# ---- estimate
@router.get("/projects/{pid}/estimate", response_class=HTMLResponse)
def project_estimate(pid: str, request: Request, preliminary: int = 0, view: str = "summary", item: str | None = None, actor: Actor = Depends(current_actor)):
    db = get_db()
    est = compute_estimate(db, pid, include_unapproved=bool(preliminary))
    lines = [l for l in est.direct.lines if not item or l.item_key == item]
    return page(request, "estimate.html", actor, project=_proj(pid), est=est, lines=lines[:1500], total_lines=len(lines), prelim=preliminary, item=item or "",
                title="Estimate build-up", tab="estimate")


# ---- assumptions
@router.get("/projects/{pid}/assumptions", response_class=HTMLResponse)
def project_assumptions(pid: str, request: Request, actor: Actor = Depends(current_actor)):
    db = get_db()
    rows = assumptions.project_assumption_status(db, pid)
    pending = rows_to_dicts(db.all("SELECT * FROM project_assumptions WHERE project_id=? AND status='Pending Review'", (pid,)))
    est = compute_estimate(db, pid)
    return page(request, "project_assumptions.html", actor, project=_proj(pid), rows=rows, pending=pending, used=sorted(est.direct.used_assumptions),
                all_assumptions=assumptions.list_assumptions(db), title="Assumptions", tab="assumptions")


@router.get("/projects/{pid}/assumptions/impact", response_class=HTMLResponse)
def assumption_impact(pid: str, request: Request, aid: str, value: str, actor: Actor = Depends(current_actor)):
    db = get_db()
    base = compute_estimate(db, pid, include_unapproved=True)
    alt = compute_estimate(db, pid, include_unapproved=True, assumption_overrides={aid: value})
    b, a = base.direct.direct_cost_total, alt.direct.direct_cost_total
    return page(request, "impact.html", actor, project=_proj(pid), aid=aid, value=value, base=base, alt=alt, delta=a - b, title="Assumption impact", tab="assumptions")


# ---- procurement
@router.get("/projects/{pid}/procurement", response_class=HTMLResponse)
def project_procurement(pid: str, request: Request, actor: Actor = Depends(current_actor)):
    db = get_db()
    pk = rows_to_dicts(db.all("SELECT * FROM procurement_packages WHERE project_id=? ORDER BY id", (pid,)))
    rfqs = rows_to_dicts(db.all("SELECT * FROM rfqs WHERE project_id=? ORDER BY id", (pid,)))
    return page(request, "procurement.html", actor, project=_proj(pid), register=needs.register(db, pid), packages=pk, rfqs=rfqs,
                suppliers=suppliers.list_suppliers(db), title="Procurement", tab="procurement")


@router.get("/rfq/{rfq_id}", response_class=HTMLResponse)
def rfq_view(rfq_id: str, request: Request, actor: Actor = Depends(current_actor)):
    r = rfq.get_rfq(get_db(), rfq_id)
    return page(request, "rfq.html", actor, rfq=r, project=_proj(r["project_id"]), title=rfq_id, tab="procurement")


@router.get("/rfq/{rfq_id}/download/{fmt}")
def rfq_dl(rfq_id: str, fmt: str, actor: Actor = Depends(current_actor)):
    db = get_db()
    return FileResponse(rfq.export_xlsx(db, rfq_id) if fmt == "xlsx" else rfq.export_docx(db, rfq_id))


# ---- quotations & levelling
@router.get("/projects/{pid}/quotes", response_class=HTMLResponse)
def project_quotes(pid: str, request: Request, package: str | None = None, actor: Actor = Depends(current_actor)):
    db = get_db()
    qs = quotes.list_quotations(db, pid)
    for q in qs:
        q["validity"] = quotes.validity(q)
        q["lines"] = rows_to_dicts(db.all("SELECT * FROM quotation_lines WHERE quotation_id=? ORDER BY line_no", (q["id"],)))
    pk = rows_to_dicts(db.all("SELECT * FROM procurement_packages WHERE project_id=?", (pid,)))
    lv = leveling.level_package(db, package) if package else None
    sel = rows_to_dicts(db.all("SELECT * FROM quote_selections WHERE project_id=? ORDER BY id DESC", (pid,)))
    adjs = rows_to_dicts(db.all("SELECT * FROM quote_adjustments WHERE quotation_id IN (SELECT id FROM quotations WHERE project_id=?)", (pid,)))
    return page(request, "quotes.html", actor, project=_proj(pid), quotes=qs, packages=pk, lv=lv, package=package, selections=sel, adjustments=adjs,
                suppliers=suppliers.list_suppliers(db), items=rows_to_dicts(db.all("SELECT id, description, package_id FROM procurement_items WHERE project_id=? AND closed=0", (pid,))),
                title="Quotations & levelling", tab="quotes")


@router.post("/quotations/{qid}/import")
async def quote_import(qid: str, file: UploadFile = File(...), actor: Actor = Depends(current_actor)):
    db = get_db()
    q = quotes.get_quotation(db, qid)
    try:
        r = quotes.import_quotation_lines(db, actor, qid, save_upload(q["project_id"], file, "procurement"))
    except AppError as e:
        return back(f"/projects/{q['project_id']}/quotes", err=e.message)
    return back(f"/projects/{q['project_id']}/quotes", ok=f"Imported {r['added']} line(s); {len(r['skipped'])} skipped.")


# ---- commercial
@router.get("/projects/{pid}/commercial", response_class=HTMLResponse)
def project_commercial(pid: str, request: Request, actor: Actor = Depends(current_actor)):
    db = get_db()
    est = compute_estimate(db, pid)
    pols = rows_to_dicts(db.all("SELECT id, code, version, name, status FROM commercial_policies ORDER BY id DESC"))
    return page(request, "commercial.html", actor, project=_proj(pid), est=est, indirects=indirects.list_indirects(db, pid), durations=indirects.list_durations(db, pid),
                policies=pols, policy_json=json.dumps(est.policy, indent=1) if est.policy else "", tax=commercial.list_tax_categories(db),
                title="Indirects & commercials", tab="commercial")


# ---- registers
@router.get("/projects/{pid}/registers", response_class=HTMLResponse)
def project_registers(pid: str, request: Request, actor: Actor = Depends(current_actor)):
    db = get_db()
    return page(request, "registers.html", actor, project=_proj(pid), clar=registers.list_clarifications(db, pid), scope=registers.list_scope(db, pid),
                risks=registers.list_risks(db, pid), sug=[s for s in suggestions.list_suggestions(db, pid) if s["kind"] in ("clarifications", "scope_gap")],
                title="Clarifications & risk", tab="registers")


# ---- reconciliation
@router.get("/projects/{pid}/reconciliation", response_class=HTMLResponse)
def project_recon(pid: str, request: Request, actor: Actor = Depends(current_actor)):
    db = get_db()
    try:
        run_ = recon.get_run(db, project_id=pid)
    except AppError:
        run_ = None
    return page(request, "reconciliation.html", actor, project=_proj(pid), run=run_, versions=estimates.list_versions(db, pid), offer=offers.latest_offer(db, pid),
                title="Reconciliation", tab="reconciliation")


# ---- reports
@router.get("/projects/{pid}/reports", response_class=HTMLResponse)
def project_reports(pid: str, request: Request, actor: Actor = Depends(current_actor)):
    db = get_db()
    ex = rows_to_dicts(db.all("SELECT * FROM exports WHERE project_id=? ORDER BY id DESC LIMIT 50", (pid,)))
    ap = rows_to_dicts(db.all("SELECT * FROM approvals WHERE project_id=? AND entity_type='tender_export' AND action='approve' ORDER BY id DESC", (pid,)))
    try:
        eva = history.estimate_vs_actual(db, pid)
        eva_rows = eva.fillna("").to_dict("records")
    except Exception:
        eva_rows = []
    return page(request, "reports.html", actor, project=_proj(pid), exports=ex, versions=estimates.list_versions(db, pid), offers=rows_to_dicts(db.all("SELECT * FROM offers WHERE project_id=? ORDER BY version_no DESC", (pid,))),
                tender_approvals=ap, eva=eva_rows, actuals=rows_to_dicts(db.all("SELECT * FROM actual_costs WHERE project_id=?", (pid,))), title="Reports & exports", tab="reports")


@router.get("/projects/{pid}/workbook")
def workbook(pid: str, actor: Actor = Depends(current_actor)):
    out = projects.output_dir(pid, "estimate") / f"estimate_master_{pid}.xlsx"
    build_master(out, get_db(), pid)
    return FileResponse(out, filename=out.name)


@router.post("/projects/{pid}/workbook/import")
async def workbook_import(pid: str, file: UploadFile = File(...), actor: Actor = Depends(current_actor)):
    from ..excel import roundtrip
    try:
        rep = roundtrip.import_master(get_db(), actor, pid, save_upload(pid, file, "estimate"))
    except AppError as e:
        return back(f"/projects/{pid}/reports", err=e.message)
    msg = f"Workbook import created {rep.created}; ignored {rep.ignored}; errors: {len(rep.errors)}. " + " ".join(rep.notes + rep.errors[:5])
    return back(f"/projects/{pid}/reports", ok=msg)


@router.get("/exports/{eid}")
def export_dl(eid: int, actor: Actor = Depends(current_actor)):
    r = get_db().one("SELECT * FROM exports WHERE id=?", (eid,))
    return FileResponse(r["file_path"], filename=Path(r["file_path"]).name)


# ------------------------------------------------------------------ libraries
@router.get("/libraries", response_class=HTMLResponse)
def libraries(request: Request, q: str = "", type: str = "", cc: str = "", missing: int = 0, page_no: int = 1, actor: Actor = Depends(current_actor)):
    db = get_db()
    sql, p = "SELECT r.*, (SELECT unit_price||' '||currency||' ['||status||']' FROM resource_rates x WHERE x.resource_id=r.id AND x.unit_price IS NOT NULL ORDER BY (x.status='Approved') DESC, x.version DESC LIMIT 1) AS best_rate FROM resources r WHERE r.is_active=1", []
    if q:
        sql += " AND (r.description LIKE ? OR r.aliases LIKE ? OR r.id LIKE ?)"; p += [f"%{q}%"] * 3
    if type:
        sql += " AND r.resource_type=?"; p.append(type)
    if cc:
        sql += " AND r.cost_code LIKE ?"; p.append(cc + "%")
    if missing:
        sql += " AND NOT EXISTS (SELECT 1 FROM resource_rates x WHERE x.resource_id=r.id AND x.status='Approved' AND x.unit_price IS NOT NULL)"
    total = db.scalar(f"SELECT COUNT(*) FROM ({sql})", p)
    rows = rows_to_dicts(db.all(sql + " ORDER BY r.id LIMIT 100 OFFSET ?", p + [(page_no - 1) * 100]))
    stats = {"resources": db.scalar("SELECT COUNT(*) FROM resources"),
             "with_approved_rate": db.scalar("SELECT COUNT(DISTINCT resource_id) FROM resource_rates WHERE status='Approved' AND unit_price IS NOT NULL"),
             "synthetic_rates": db.scalar("SELECT COUNT(*) FROM resource_rates WHERE is_synthetic=1 AND status='Approved'")}
    return page(request, "libraries.html", actor, rows=rows, total=total, q=q, type=type, cc=cc, missing=missing, page_no=page_no, stats=stats,
                cost_codes=rows_to_dicts(db.all("SELECT code, name FROM cost_codes WHERE level<=2 ORDER BY code")), title="Resource libraries")


@router.get("/libraries/{rid}", response_class=HTMLResponse)
def resource_view(rid: str, request: Request, project: str | None = None, actor: Actor = Depends(current_actor)):
    db = get_db()
    return page(request, "resource.html", actor, r=dict(rates.get_resource(db, rid)), rates=rates.rates_for(db, rid), rate_types=RATE_TYPE_VALUES,
                history=audit.history(db, "resource", rid), projects=projects.list_projects(db), suppliers=suppliers.list_suppliers(db), title=rid)


@router.get("/assumptions", response_class=HTMLResponse)
def global_assumptions(request: Request, family: str = "", status: str = "", q: str = "", actor: Actor = Depends(current_actor)):
    db = get_db()
    return page(request, "assumptions.html", actor, rows=assumptions.list_assumptions(db, family or None, status or None, q or None), families=assumptions.FAMILIES,
                family=family, status=status, q=q, title="Assumption register")


@router.get("/assemblies", response_class=HTMLResponse)
def assembly_list(request: Request, q: str = "", code: str | None = None, actor: Actor = Depends(current_actor)):
    db = get_db()
    detail = None
    if code:
        a = assemblies.get(db, code)
        detail = {"a": a, "lines": assemblies.lines(db, a["pk"]), "problems": assemblies.validate(db, a["pk"]),
                  "versions": rows_to_dicts(db.all("SELECT version, status, approved_by, approved_at, revision_note FROM assemblies WHERE code=? ORDER BY version", (code,)))}
    return page(request, "assemblies.html", actor, rows=assemblies.list_assemblies(db, q=q or None), q=q, detail=detail, title="Assemblies")


# ------------------------------------------------------------------ approvals & settings
@router.get("/approvals", response_class=HTMLResponse)
def approvals_page(request: Request, entity: str = "", actor: Actor = Depends(current_actor)):
    db = get_db()
    log = rows_to_dicts(db.all("SELECT * FROM approvals " + ("WHERE entity_type=? " if entity else "") + "ORDER BY id DESC LIMIT 300", (entity,) if entity else ()))
    return page(request, "approvals.html", actor, queue=dashboard.pending_queue(db), log=log, entity=entity, title="Approvals")


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, actor: Actor = Depends(current_actor)):
    db = get_db()
    s = get_settings()
    return page(request, "settings.html", actor, sources=rows_to_dicts(db.all("SELECT * FROM sources ORDER BY source_id")), tax=commercial.list_tax_categories(db),
                fx=rows_to_dicts(db.all("SELECT * FROM fx_rates ORDER BY id DESC")), company=s.company, users=rows_to_dicts(db.all("SELECT username, display_name, role, is_active FROM users")),
                backups=sorted(p.name for p in s.backups_dir.glob("*.zip")) if s.backups_dir.exists() else [], datasets=rows_to_dicts(db.all("SELECT * FROM dataset_imports ORDER BY id DESC LIMIT 20")),
                cost_codes=rows_to_dicts(db.all("SELECT * FROM cost_codes ORDER BY code")), audit=audit.verify_chain(db), ai_enabled=s.ai_enabled, title="Settings & data sources")


@router.post("/datasets/stage")
async def dataset_stage(file: UploadFile = File(...), source_id: str = Form(""), actor: Actor = Depends(current_actor)):
    try:
        r = datasets.stage_rate_dataset(get_db(), actor, save_upload("", file), source_id=source_id or None)
    except AppError as e:
        return back("/settings", err=e.message)
    return back(f"/datasets/{r['dataset_id']}", ok=f"Staged {r['rows']} rows; issues: {r['issue_counts']}")


@router.get("/datasets/{did}", response_class=HTMLResponse)
def dataset_view(did: int, request: Request, actor: Actor = Depends(current_actor)):
    db = get_db()
    return page(request, "dataset.html", actor, ds=dict(db.one("SELECT * FROM dataset_imports WHERE id=?", (did,))), rows=datasets.staged_rows(db, did), title=f"Dataset {did}")


# ------------------------------------------------------------------ project workspace / documents / completeness
@router.get("/projects/{pid}/workspace", response_class=HTMLResponse)
def project_workspace(pid: str, request: Request, actor: Actor = Depends(current_actor)):
    db = get_db()
    root = workspaces.ensure_workspace(db, pid)
    counts = {}
    for key, name in workspaces.AREAS.items():
        d = root / name
        counts[key] = sum(1 for f in d.rglob("*") if f.is_file()) if d.is_dir() else 0
    claude_md = (root / "CLAUDE.md").read_text(encoding="utf-8") if (root / "CLAUDE.md").exists() else ""
    snaps = rows_to_dicts(db.all("SELECT s.estimate_version_id, v.version_no, s.sha256, s.created_at, s.file_path FROM estimate_snapshots s JOIN estimate_versions v "
                                 "ON v.id=s.estimate_version_id WHERE s.project_id=? ORDER BY v.version_no", (pid,)))
    return page(request, "workspace.html", actor, project=_proj(pid), root=str(root), areas=workspaces.AREAS, counts=counts,
                docs=project_index.list_documents(db, pid), claude_md=claude_md, snaps=snaps,
                trades=jload(_proj(pid).get("trades"), []), title="Workspace", tab="workspace")


@router.post("/projects/{pid}/workspace/upload")
async def workspace_upload(pid: str, area: str = Form("tender"), file: UploadFile = File(...), actor: Actor = Depends(current_actor)):
    from ..approvals import engine as _ap
    try:
        _ap.require_author(actor)
        projects.require_active(get_db(), pid)
        if area not in workspaces.AREAS or area == "ai_context":
            return back(f"/projects/{pid}/workspace", err="Choose a valid workspace folder (generated 'AI Context' cannot receive uploads).")
        path = save_upload(pid, file, area)
    except AppError as e:
        return back(f"/projects/{pid}/workspace", err=e.message)
    return back(f"/projects/{pid}/workspace", ok=f"Saved {path.name} to '{workspaces.AREAS[area]}' (original kept as uploaded; never overwritten).")


@router.get("/projects/{pid}/completeness", response_class=HTMLResponse)
def project_completeness(pid: str, request: Request, actor: Actor = Depends(current_actor)):
    return page(request, "completeness.html", actor, project=_proj(pid), rep=completeness.project_completeness(get_db(), pid), title="Completeness", tab="completeness")


# ------------------------------------------------------------------ public-source rate updates (proposals only)
@router.get("/rates/updates", response_class=HTMLResponse)
def rate_updates(request: Request, queue: str = "", status: str = "", actor: Actor = Depends(current_actor)):
    db = get_db()
    from ..services import workspaces as _w
    return page(request, "rate_updates.html", actor, rows=rate_candidates.list_queue(db, queue=queue or None, status=status or None, open_only=not status),
                counts=rate_candidates.queue_counts(db), srcs=source_refresh.status_report(db), queue=queue, status=status, lib=_w.library_versions(db),
                register=rows_to_dicts(db.all("SELECT source_id, name FROM sources ORDER BY source_id")), title="Rate updates")


@router.get("/rates/updates/{ref}", response_class=HTMLResponse)
def rate_update_detail(ref: str, request: Request, actor: Actor = Depends(current_actor)):
    db = get_db()
    c = rate_candidates.get(db, ref)
    price, how, reasons = rate_candidates.publishable_price(db, c)
    man = db.one("SELECT id, source_name, source_url, sha256, imported_at FROM import_manifests WHERE id=?", (c["manifest_id"],)) if c["manifest_id"] else None
    return page(request, "rate_candidate.html", actor, c=c, publish_price=price, publish_how=how, reasons=reasons, manifest=dict(man) if man else None,
                resources=rows_to_dicts(db.all("SELECT id, description, unit FROM resources WHERE is_active=1 ORDER BY id LIMIT 3000")),
                suggestions=rate_candidates.suggest_resource(db, f"{c['description'] or ''} {c['specification'] or ''}"), title=c["candidate_ref"])


@router.post("/rates/updates/import")
async def rate_updates_import(file: UploadFile = File(...), source_id: str = Form(""), source_name: str = Form(""), source_url: str = Form(""),
                              source_type: str = Form("Manual dataset"), description: str = Form(""), dry_run: str = Form(""),
                              actor: Actor = Depends(current_actor)):
    try:
        path = save_upload("", file)
        r = rate_importer.import_rates_file(get_db(), actor, path, source_id=source_id or None, source_name=source_name or None, source_url=source_url or None,
                                            source_type=source_type, description=description, dry_run=bool(dry_run),
                                            extra_flags=["AWARD_NOT_MARKET_QUOTE"] if source_type == "Public tender award" else None)
    except AppError as e:
        return back("/rates/updates", err=f"{e.code}: {e.message}")
    msg = (f"{'DRY RUN - nothing stored. ' if r['dry_run'] else ''}{r['accepted']} row(s) accepted, {r['rejected']} rejected (manifest #{r['manifest_id']})."
           + ("".join(f" Row {e['row']}: {'; '.join(e['errors'])}." for e in r['errors'][:5])))
    return back("/rates/updates", ok=msg)


@router.post("/rates/updates/index")
async def index_upload(file: UploadFile = File(...), dataset: str = Form("gastat-cci"), source_id: str = Form(""), source_name: str = Form(""),
                       dry_run: str = Form(""), actor: Actor = Depends(current_actor)):
    try:
        r = index_import.import_index_file(get_db(), actor, save_upload("", file), dataset=dataset, source_id=source_id or None, source_name=source_name or dataset,
                                           dry_run=bool(dry_run))
    except AppError as e:
        return back("/rates/updates", err=f"{e.code}: {e.message}")
    return back("/rates/updates", ok=f"Index data: {r}")
