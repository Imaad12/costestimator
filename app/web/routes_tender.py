"""Web pages for the tender workflow: control tower, tender desk, queries / RFIs, registers, workforce & programme, tender pack, readiness, standards, audit trail and help.

Pages are server-rendered and read from the same services as the REST API and CLI. Every write goes through `/ui/do/<action>` (the shared action registry), so authorisation stays
inside the services; nothing on these pages approves or changes data by itself.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, HTMLResponse

from ..api.deps import current_actor
from ..api.serializers import ser
from ..core.errors import AppError, NotFound
from ..database import get_db, rows_to_dicts
from ..models.actor import Actor
from ..reporting import registry, tower
from ..services import assumptions, audit, estimates, projects, readiness, standards, tender, workforce
from ..tender import catalogue
from .routes import page

router = APIRouter()
ROOT = Path(__file__).resolve().parents[2]
REGISTERS = tuple(tender.REGISTER_FIELDS)


def _proj(pid: str) -> dict:
    return projects.get_project(get_db(), pid)


# ------------------------------------------------------------------ control tower
@router.get("/projects/{pid}/tower", response_class=HTMLResponse)
def project_tower(pid: str, request: Request, actor: Actor = Depends(current_actor)):
    return page(request, "tower.html", actor, project=_proj(pid), t=tower.project_tower(get_db(), pid), title="Control tower", tab="tower")


# ------------------------------------------------------------------ tender desk
@router.get("/projects/{pid}/tender", response_class=HTMLResponse)
def tender_desk(pid: str, request: Request, actor: Actor = Depends(current_actor)):
    db = get_db()
    return page(request, "tender_desk.html", actor, project=_proj(pid), enq=tender.get_enquiry(db, pid), rep=tender.documents_report(db, pid), dm=tender.discipline_matrix(db, pid),
                docs=tender.list_documents(db, pid), doc_types=tender.DOC_TYPES, disciplines=tender.DISCIPLINES, title="Tender desk", tab="tender")


# ------------------------------------------------------------------ queries / RFIs
@router.get("/projects/{pid}/queries", response_class=HTMLResponse)
def queries(pid: str, request: Request, register: str = "", status: str = "", actor: Actor = Depends(current_actor)):
    db = get_db()
    allq = tender.list_queries(db, pid)
    rows = [q for q in allq if (not register or q["register"] == register) and (not status or q["status"] == status)]
    for q in rows:
        q["related"] = json.loads(q.get("related_json") or "{}")
        q["impact"] = json.loads(q.get("impact_json") or "{}")
    counts = {s: sum(1 for q in allq if q["status"] == s) for s in sorted({q["status"] for q in allq})}
    return page(request, "queries.html", actor, project=_proj(pid), qs=rows, total=len(allq), counts=counts, registers=tender.QUERY_REGISTERS, f_register=register, f_status=status,
                material=len(tender.open_material_queries(db, pid)), title="Queries & RFIs", tab="queries")


# ------------------------------------------------------------------ registers and open actions
@router.get("/projects/{pid}/tender-registers", response_class=HTMLResponse)
def tender_registers(pid: str, request: Request, actor: Actor = Depends(current_actor)):
    db = get_db()
    items = tender.list_items(db, pid)
    grouped: dict[str, list] = {}
    for it in items:
        grouped.setdefault(it["register"], []).append(it)
    actions = rows_to_dicts(db.all("SELECT * FROM open_actions WHERE project_id=? ORDER BY id", (pid,)))
    return page(request, "tender_registers.html", actor, project=_proj(pid), grouped=grouped, actions=actions, registers=REGISTERS, title="Registers & actions", tab="tender-registers")


# ------------------------------------------------------------------ workforce and programme
@router.get("/projects/{pid}/workforce", response_class=HTMLResponse)
def workforce_page(pid: str, request: Request, profiles: list[str] = Query(default=[]), actor: Actor = Depends(current_actor)):
    db = get_db()
    baselines = rows_to_dicts(db.all("SELECT version_no, profile_id, profile_version, status, provisional, created_by, created_at, approved_by, result_json FROM programme_baselines WHERE project_id=? ORDER BY version_no DESC", (pid,)))
    for b in baselines:
        r = json.loads(b.pop("result_json") or "{}")
        b["working_days"], b["calendar_days"], b["finish"], b["synthetic"], b["claims"] = r.get("working_days"), r.get("calendar_days"), r.get("finish_date"), r.get("synthetic"), r.get("claims")
    scen, err = None, None
    sel = [y for x in profiles for y in x.split(",") if y]
    if sel:
        try:
            scen = ser(workforce.crew_scenarios(db, pid, sel, allow_provisional=True, allow_unconfirmed_calendar=True))
        except AppError as e:
            err = f"{e.code}: {e.message}"
    acts = workforce.list_activities(db, pid)
    for a in acts:
        a["fx"] = json.loads(a.get("fixed_days_json") or "{}")
    boq_keys = [r["item_key"] for r in db.all("SELECT item_key FROM boq_items WHERE project_id=? AND item_type='item' ORDER BY id", (pid,))]
    long_leads = [r["id"] for r in db.all("SELECT id FROM long_lead_items WHERE project_id=? ORDER BY id", (pid,))]
    return page(request, "workforce.html", actor, project=_proj(pid), boq_keys=boq_keys, long_leads=long_leads, bands=workforce.ARCHETYPE_BANDS, norms=workforce.list_norms(db), profile_rows=workforce.list_profiles(db), acts=acts, baselines=baselines,
                scen=scen, scen_err=err, sel=sel, title="Workforce & programme", tab="workforce")


# ------------------------------------------------------------------ tender pack
@router.get("/projects/{pid}/pack", response_class=HTMLResponse)
def pack_page(pid: str, request: Request, pack: int | None = None, validate: int = 0, actor: Actor = Depends(current_actor)):
    db = get_db()
    packs = rows_to_dicts(db.all("SELECT * FROM tender_packs WHERE project_id=? ORDER BY CASE kind WHEN 'tender' THEN 0 ELSE 1 END, revision DESC", (pid,)))
    cur = next((p for p in packs if p["pk"] == pack), packs[0] if packs else None)
    docs, val = [], None
    if cur:
        docs = rows_to_dicts(db.all("SELECT * FROM generated_documents WHERE pack_pk=? ORDER BY doc_code", (cur["pk"],)))
        for d in docs:
            d["formats"] = [f for f in (d.get("format") or "").split(",") if f]
        if validate:                                       # read-only: re-reads the files and checks checksums, formats, placeholders, arithmetic and cross-document facts
            from ..tender import packs as _packs
            val = _packs.validate_pack(db, cur["pk"])
    versions = list(reversed(estimates.list_versions(db, pid)))
    try:
        mx = catalogue.matrix(db, pid)
    except AppError:
        mx = None
    return page(request, "pack.html", actor, project=_proj(pid), packs=packs, cur=cur, docs=docs, val=val, versions=versions, mx=mx, title="Tender pack", tab="pack")


@router.get("/projects/{pid}/pack/{pk}/file/{doc_id}/{fmt}")
def pack_file(pid: str, pk: int, doc_id: str, fmt: str, actor: Actor = Depends(current_actor)):
    """Serve one generated document. The path is rebuilt from the database row and must stay inside the pack's own output directory."""
    db = get_db()
    pack = db.one("SELECT * FROM tender_packs WHERE pk=? AND project_id=?", (pk, pid))
    row = db.one("SELECT * FROM generated_documents WHERE pack_pk=? AND doc_id=?", (pk, doc_id))
    if not pack or not row or not row["path"] or fmt not in ("docx", "pdf", "xlsx"):
        raise NotFound("Document not found.")
    p = Path(row["path"]).with_suffix("." + fmt).resolve()
    if Path(pack["out_dir"]).resolve() not in p.parents or not p.is_file():
        raise NotFound("Document file not found on disk (regenerate the pack).")
    return FileResponse(p, filename=p.name)


@router.get("/projects/{pid}/pack/{pk}/manifest")
def pack_manifest(pid: str, pk: int, actor: Actor = Depends(current_actor)):
    pack = get_db().one("SELECT * FROM tender_packs WHERE pk=? AND project_id=?", (pk, pid))
    if not pack:
        raise NotFound("Pack not found.")
    p = (Path(pack["out_dir"]) / "manifest.json").resolve()
    if not p.is_file():
        raise NotFound("Manifest not found on disk.")
    return FileResponse(p, media_type="application/json", filename=f"{pid}_pack_r{pack['revision']}_manifest.json")


# ------------------------------------------------------------------ readiness
@router.get("/projects/{pid}/readiness", response_class=HTMLResponse)
def readiness_page(pid: str, request: Request, version: int | None = None, actor: Actor = Depends(current_actor)):
    db = get_db()
    versions = list(reversed(estimates.list_versions(db, pid)))
    v = next((x for x in versions if x["id"] == version), versions[0] if versions else None)
    r = None
    if v:
        exp = db.one("SELECT id FROM approvals WHERE entity_type='tender_export' AND entity_id=? AND action='approve' ORDER BY id DESC LIMIT 1", (f"{pid}/v{v['version_no']}",))
        r = readiness.evaluate(db, pid, v["id"], exp["id"] if exp else None)
    ev = assumptions.evidence_report(db, pid)
    return page(request, "readiness.html", actor, project=_proj(pid), versions=versions, v=v, r=r, ev=ev, title="Readiness", tab="readiness")


# ------------------------------------------------------------------ global pages
@router.get("/favicon.ico")
def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)


@router.get("/standards", response_class=HTMLResponse)
def standards_page(request: Request, actor: Actor = Depends(current_actor)):
    db = get_db()
    rows = standards.list_standards(db)
    return page(request, "standards.html", actor, rows=rows, acq=standards.acquisition_list(db), title="Standards & evidence")


@router.get("/audit", response_class=HTMLResponse)
def audit_page(request: Request, project: str = "", entity: str = "", verify: int = 0, actor: Actor = Depends(current_actor)):
    db = get_db()
    sql, par = "SELECT id, ts, actor, actor_role, project_id, entity_type, entity_id, action, comment FROM audit_log WHERE 1=1", []
    if project:
        sql, par = sql + " AND project_id=?", par + [project]
    if entity:
        sql, par = sql + " AND entity_type=?", par + [entity]
    rows = rows_to_dicts(db.all(sql + " ORDER BY id DESC LIMIT 300", par))
    etypes = [r["entity_type"] for r in db.all("SELECT DISTINCT entity_type FROM audit_log ORDER BY entity_type")]
    return page(request, "audit.html", actor, rows=rows, chain=audit.verify_chain(db) if verify else None, etypes=etypes, f_project=project, f_entity=entity, title="Audit trail")


# ------------------------------------------------------------------ help / documentation viewer
_DOC_GROUPS = (("Start here", ("SYSTEM_MAP_BUILT_VS_MISSING", "PROJECT_HISTORY_AND_NEXT_STEPS", "USER_GUIDE", "KNOWN_LIMITATIONS")),
               ("How it works", ("ARCHITECTURE", "ESTIMATING_METHODOLOGY", "APPROVAL_WORKFLOW", "WORKFORCE_PRODUCTIVITY_AND_PROGRAMME_METHOD", "TENDER_DOCUMENT_APPLICABILITY_MATRIX", "PROCUREMENT_GUIDE", "ASSUMPTIONS_POLICY")),
               ("Evidence & audits", ("SYNTHETIC_END_TO_END_CLOSURE_REPORT", "ASSUMPTIONS_GOVERNANCE_AND_SECURITY_AUDIT", "STANDARDS_AND_EVIDENCE_REGISTER", "PILOT_READINESS", "SECURITY", "TESTING")))


def _inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\[([^\]]+)\]\(((?:https?://|/|#)[^)\s]*)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\[([^\]]+)\]\(([A-Za-z0-9_./-]+)\.md(#[^)]*)?\)", lambda m: f'<a href="/help/{Path(m.group(2)).name}">{m.group(1)}</a>', s)
    return s


def render_markdown(text: str) -> str:
    """Small, safe Markdown subset (headings, tables, lists, code/diagram blocks, bold, inline code, links). Everything is HTML-escaped first."""
    out, lines, i = [], text.splitlines(), 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            lang, i, buf = ln[3:].strip(), i + 1, []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            out.append(f'<pre class="diagram" data-lang="{html.escape(lang)}">{html.escape(chr(10).join(buf))}</pre>')
        elif re.match(r"^#{1,4} ", ln):
            n = len(ln) - len(ln.lstrip("#"))
            out.append(f"<h{n + 1}>{_inline(ln[n + 1:])}</h{n + 1}>")
        elif ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|?$", lines[i + 1]):
            head = [c.strip() for c in ln.strip().strip("|").split("|")]
            i += 2
            body = []
            while i < len(lines) and lines[i].startswith("|"):
                body.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            out.append("<table><thead><tr>" + "".join(f"<th>{_inline(h)}</th>" for h in head) + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in body) + "</tbody></table>")
            continue
        elif re.match(r"^\s*([-*]|\d+\.) ", ln):
            items = []
            while i < len(lines) and re.match(r"^\s*([-*]|\d+\.) ", lines[i]):
                items.append(re.sub(r"^\s*([-*]|\d+\.) ", "", lines[i]))
                i += 1
            out.append("<ul>" + "".join(f"<li>{_inline(x)}</li>" for x in items) + "</ul>")
            continue
        elif ln.strip():
            para = [ln]
            while i + 1 < len(lines) and lines[i + 1].strip() and not re.match(r"^(#|```|\||\s*([-*]|\d+\.) )", lines[i + 1]):
                i += 1
                para.append(lines[i])
            out.append(f"<p>{_inline(' '.join(para))}</p>")
        i += 1
    return "\n".join(out)


@router.get("/help", response_class=HTMLResponse)
def help_index(request: Request, actor: Actor = Depends(current_actor)):
    have = {p.stem for p in (ROOT / "docs").glob("*.md")}
    rest = sorted(have - {n for _, names in _DOC_GROUPS for n in names})
    groups = [(g, [n for n in names if n in have]) for g, names in _DOC_GROUPS] + [("All other documents", rest)]
    return page(request, "help_index.html", actor, groups=groups, title="Help & documentation")


@router.get("/help/{name}", response_class=HTMLResponse)
def help_doc(name: str, request: Request, actor: Actor = Depends(current_actor)):
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise NotFound("Document not found.")
    p = ROOT / "docs" / f"{name}.md"
    if not p.is_file():
        raise NotFound("Document not found.")
    return page(request, "help_doc.html", actor, docname=name, body=render_markdown(p.read_text(encoding="utf-8")), title=name.replace("_", " ").title())
