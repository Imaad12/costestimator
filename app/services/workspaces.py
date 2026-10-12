"""Numbered per-project workspaces (docs/PROJECT_WORKSPACES.md).

A workspace is the *file* side of a project: tender documents, extracts, BOQ uploads, quotations, exports.  The database stays the
source of truth for every number and every approval; the workspace holds source files and generated deliverables only.

Guarantees
* `ensure_workspace` is idempotent: it creates what is missing and NEVER overwrites or deletes existing files.
* The folder is `<workspaces_dir>/<PROJECT-ID>-<slug>`; the project id (unique in the DB) is the identity, the slug is cosmetic.
* `project.json` is a generated manifest; `CLAUDE.md` keeps a generated block between markers and preserves the human notes below it.
* Nothing here approves anything.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from ..config import get_settings
from ..core.errors import ValidationFailed
from ..core.timeutil import now_iso
from ..database import Database, jload

# Product requirement: these names and numbers are fixed.
AREAS: dict[str, str] = {
    "tender": "1. Tender Documents",
    "ai_context": "2. AI Context",
    "boq": "3. BOQ & Takeoff",
    "clarifications": "4. Clarifications & Assumptions",
    "estimate": "5. Estimate & Cost Build-Up",
    "procurement": "6. Procurement & Quotations",
    "programme": "7. Programme & Indirects",
    "commercial": "8. Commercial Submission",
    "reconciliation": "9. Reconciliation & Approvals",
    "exports": "10. Exports & Archive",
}
AREA_NAMES = list(AREAS.values())
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,40}$")
GEN_BEGIN = "<!-- BEGIN GENERATED (ksa-estimator) - regenerated from the database; edit the human notes section below instead -->"
GEN_END = "<!-- END GENERATED -->"
HUMAN_HEADER = "## Human notes (preserved on refresh)"
MANIFEST = "project.json"


def slugify(text: str, max_len: int = 40) -> str:
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    t = t[:max_len].strip("-")
    return t or "project"


def check_project_id(project_id: str) -> str:
    if not _ID_RE.match(project_id or ""):
        raise ValidationFailed(f"Invalid project id '{project_id}': use 2-41 letters, digits, '-' or '_'.", code="BAD_PROJECT_ID")
    return project_id


def workspace_name(project_id: str, name: str) -> str:
    return f"{check_project_id(project_id)}-{slugify(name)}"


def _manifest_id(d: Path) -> str | None:
    m = d / MANIFEST
    if m.is_file():
        try:
            return json.loads(m.read_text(encoding="utf-8")).get("project_id")
        except (OSError, ValueError):
            return None
    return None


def find_existing(project_id: str, base: Path | None = None) -> Path | None:
    """Locate this project's workspace on disk. Matching is by the manifest's project_id (not by name prefix)."""
    base = base or get_settings().workspaces_dir
    if not base.is_dir():
        return None
    exact = [p for p in base.iterdir() if p.is_dir() and (p.name == project_id or p.name.startswith(project_id + "-"))]
    owned = [p for p in exact if _manifest_id(p) == project_id]
    if owned:
        return sorted(owned)[0]
    # a folder named exactly after the id but without a manifest (hand-made / restored) is adopted; prefix matches are not
    bare = [p for p in exact if p.name == project_id and _manifest_id(p) is None]
    return bare[0] if bare else None


def resolve_dir(project_id: str, db: Database | None = None, create: bool = True) -> Path:
    """Workspace directory for a project (created on demand when `create`)."""
    found = find_existing(project_id)
    if found:
        return found
    if not create:
        raise ValidationFailed(f"No workspace exists for {project_id}.", code="NO_WORKSPACE")
    if db is None:
        from ..database import get_db
        db = get_db()
    return ensure_workspace(db, project_id)


def area_dir(project_id: str, area: str, db: Database | None = None) -> Path:
    """Directory for a logical area key (`boq`, `procurement`, ...). Created if missing."""
    if area not in AREAS:
        raise ValidationFailed(f"Unknown workspace area '{area}'. Known: {sorted(AREAS)}")
    p = resolve_dir(project_id, db) / AREAS[area]
    p.mkdir(parents=True, exist_ok=True)
    return p


# ------------------------------------------------------------------------------------------------ generation
def ensure_workspace(db: Database, project_id: str, *, refresh_claude_md: bool = True) -> Path:
    """Create (or complete) the numbered folder tree + project.json + CLAUDE.md. Safe to call repeatedly."""
    row = db.one("SELECT * FROM projects WHERE id=?", (project_id,))
    if not row:
        raise ValidationFailed(f"Project {project_id} not found.", code="NOT_FOUND")
    proj = dict(row)
    s = get_settings()
    s.workspaces_dir.mkdir(parents=True, exist_ok=True)
    root = find_existing(project_id)
    if root is None and proj.get("workspace_path"):
        cand = s.workspaces_dir / proj["workspace_path"]
        if cand.exists() and _manifest_id(cand) not in (None, project_id):
            raise ValidationFailed(f"Workspace folder {cand.name} belongs to another project.", code="WORKSPACE_CONFLICT")
        root = cand
    if root is None:
        root = s.workspaces_dir / workspace_name(project_id, proj["name"])
        if root.exists() and _manifest_id(root) not in (None, project_id):
            raise ValidationFailed(f"Workspace folder {root.name} belongs to another project.", code="WORKSPACE_CONFLICT")
    root.mkdir(parents=True, exist_ok=True)
    for name in AREA_NAMES:
        (root / name).mkdir(exist_ok=True)
    (root / AREAS["ai_context"] / "extracts").mkdir(exist_ok=True)
    rel = root.name
    slug = rel[len(project_id) + 1:] if rel.startswith(project_id + "-") else slugify(proj["name"])
    if proj.get("workspace_path") != rel or proj.get("workspace_slug") != slug:
        db.update("projects", {"workspace_path": rel, "workspace_slug": slug}, "id=?", (project_id,))
        proj.update(workspace_path=rel, workspace_slug=slug)
    write_manifest(db, proj, root)
    if refresh_claude_md:
        write_project_claude_md(db, proj, root)
    return root


def write_manifest(db: Database, proj: dict, root: Path) -> Path:
    m = root / MANIFEST
    created = None
    if m.exists():
        try:
            created = json.loads(m.read_text(encoding="utf-8")).get("workspace_created_at")
        except (OSError, ValueError):
            created = None
    data = {
        "schema": "ksa-estimator/project-workspace/1",
        "managed_by": "app.services.workspaces (generated - do not hand-edit; the database is the source of truth)",
        "project_id": proj["id"], "name": proj["name"], "slug": proj.get("workspace_slug"), "workspace_dir": root.name,
        "client": proj.get("client"), "tender_ref": proj.get("tender_ref"), "location": proj.get("location"),
        "region": proj.get("region"), "currency": proj.get("currency"), "project_type": proj.get("project_type"),
        "trades": jload(proj.get("trades"), []), "design_stage": proj.get("design_stage"), "status": proj.get("status"),
        "is_demo": bool(proj.get("is_demo")), "drawing_revision": proj.get("drawing_revision"), "spec_revision": proj.get("spec_revision"),
        "areas": AREAS, "workspace_created_at": created or now_iso(), "manifest_updated_at": now_iso(),
    }
    m.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return m


def library_versions(db: Database) -> dict:
    """Identifiers of the global libraries a project is working against (counts + the highest record ids - not a quality claim)."""
    def one(sql):
        return db.scalar(sql)
    last_mig = one("SELECT MAX(version) FROM schema_migrations")
    return {
        "schema_migration": last_mig,
        "resources": one("SELECT COUNT(*) FROM resources"),
        "rates_total": one("SELECT COUNT(*) FROM resource_rates"),
        "rates_approved_real": one("SELECT COUNT(*) FROM resource_rates WHERE status='Approved' AND is_synthetic=0 AND unit_price IS NOT NULL"),
        "rates_approved_synthetic": one("SELECT COUNT(*) FROM resource_rates WHERE status='Approved' AND is_synthetic=1"),
        "highest_rate_id": one("SELECT COALESCE(MAX(id),0) FROM resource_rates"),
        "assemblies_approved": one("SELECT COUNT(*) FROM assemblies WHERE status='Approved'"),
        "assumptions": one("SELECT COUNT(*) FROM assumptions"),
        "tax_categories_approved": one("SELECT COUNT(*) FROM tax_categories WHERE status='Approved'"),
    }


def outstanding_issues(db: Database, project_id: str) -> list[str]:
    out: list[str] = []
    n_items = db.scalar("SELECT COUNT(*) FROM boq_items WHERE project_id=? AND item_type='item'", (project_id,)) or 0
    if not n_items:
        out.append("No BOQ imported yet (import into '3. BOQ & Takeoff').")
        return out
    unmapped = db.scalar("SELECT COUNT(*) FROM boq_items WHERE project_id=? AND item_type='item' AND assembly_code IS NULL "
                         "AND pricing_resource_id IS NULL AND COALESCE(pricing_method,'')<>'excluded'", (project_id,)) or 0
    if unmapped:
        out.append(f"{unmapped} BOQ item(s) have no assembly / pricing resource mapping.")
    try:
        from ..estimators.estimate import compute_estimate
        est = compute_estimate(db, project_id)
        out.append(f"Estimate state: {est.state}.")
        out.extend(est.blockers[:8])
    except Exception as e:  # never let the instructions file break project creation
        out.append(f"Estimate could not be computed yet ({type(e).__name__}).")
    return out


def render_generated_block(db: Database, proj: dict) -> str:
    pid = proj["id"]
    lv = library_versions(db)
    pol = db.one("SELECT code, version, name, status FROM commercial_policies WHERE id=?", (proj.get("commercial_policy_id"),)) \
        if proj.get("commercial_policy_id") else None
    pa = db.all("SELECT status, COUNT(*) n FROM project_assumptions WHERE project_id=? GROUP BY status", (pid,))
    pa_txt = ", ".join(f"{r['n']} {r['status']}" for r in pa) or "none adopted yet"
    trades = jload(proj.get("trades"), [])
    issues = outstanding_issues(db, pid)
    est_v = db.all("SELECT version_no, status FROM estimate_versions WHERE project_id=? ORDER BY version_no", (pid,))
    demo = "**SYNTHETIC / DEMO / NOT A MARKET QUOTE - every figure in this project is illustrative.**\n\n" if proj.get("is_demo") else ""
    L = [GEN_BEGIN, "", f"# Project {pid} - {proj['name']}", "", demo.rstrip()] if demo else [GEN_BEGIN, "", f"# Project {pid} - {proj['name']}", ""]
    L += [
        "", "## Project facts", "",
        f"- Project ID: `{pid}` (workspace folder `{proj.get('workspace_path') or '(pending)'}`)",
        f"- Client: {proj.get('client') or '(not recorded)'}",
        f"- Tender reference: {proj.get('tender_ref') or '(not recorded)'}",
        f"- Location / region: {proj.get('location') or '(not recorded)'} / {proj.get('region')}",
        f"- Project type: {proj.get('project_type') or '(not recorded)'}",
        f"- Applicable trades: {', '.join(trades) if trades else '(not recorded - set in project settings)'}",
        f"- Estimate currency: {proj.get('currency')}",
        f"- Design / tender stage: {proj.get('design_stage') or '(not recorded)'}",
        f"- Approved drawing revision(s): {proj.get('drawing_revision') or '(none recorded - a human must record them)'}",
        f"- Approved specification revision(s): {proj.get('spec_revision') or '(none recorded - a human must record them)'}",
        f"- Rate as-of date: {proj.get('rate_as_of_date') or '(today)'}",
        f"- Status: {proj.get('status')}",
        "", "## Library and policy versions this project works against", "",
        f"- Global resource library: {lv['resources']} resources, {lv['rates_total']} rate records "
        f"({lv['rates_approved_real']} approved real rates, {lv['rates_approved_synthetic']} approved synthetic), highest rate id {lv['highest_rate_id']}; "
        f"DB schema `{lv['schema_migration']}`. Rates are versioned; an approved estimate version records the exact rate ids it used "
        f"(`estimate_snapshots`).",
        f"- Approved assemblies: {lv['assemblies_approved']}; global assumptions: {lv['assumptions']}; project assumptions: {pa_txt}.",
        f"- Commercial policy: {(pol['code'] + ' v' + str(pol['version']) + ' - ' + pol['name'] + ' [' + pol['status'] + ']') if pol else '(none assigned)'}.",
        f"- Estimate versions: {', '.join('v%s %s' % (v['version_no'], v['status']) for v in est_v) or 'none frozen yet'}.",
        "", "## Workspace map", "",
        "| Folder | Contents |", "|---|---|",
        "| `1. Tender Documents/` | Original tender drawings, specifications, addenda. **Read-only: never edit or overwrite originals.** |",
        "| `2. AI Context/` | Generated: document index, text extracts (versioned), summaries. Not authoritative over originals. |",
        "| `3. BOQ & Takeoff/` | Uploaded BOQ / takeoff files (originals kept; imports copy, never modify). Quantities are human-measured. |",
        "| `4. Clarifications & Assumptions/` | Clarification, exclusion and assumption working files. |",
        "| `5. Estimate & Cost Build-Up/` | Master workbook exports, estimate version snapshots. |",
        "| `6. Procurement & Quotations/` | RFQs issued, supplier quotations received (originals). |",
        "| `7. Programme & Indirects/` | Programme / Gantt inputs, indirect-cost working files. |",
        "| `8. Commercial Submission/` | Pricing schedule, offer letter, estimate report (PRELIMINARY until released). |",
        "| `9. Reconciliation & Approvals/` | Reconciliation reports and approval evidence. |",
        "| `10. Exports & Archive/` | Submission-ready exports (after human release), archived snapshots, project packages. |",
        "", "## Source-file conventions", "",
        "- Keep originals exactly as received; add new revisions as new files (e.g. `A-101_RevB.pdf`), never overwrite.",
        "- Name files so the revision is visible (`..._RevA`, `..._R2`); the indexer records revision only when the name shows it.",
        "- Supplier quotations stay in this project's folder `6. Procurement & Quotations/` and in the DB against this project.",
        "- No credentials, API keys or personal data in any project file.",
        "", "## Human-approval rules (apply to this project)", "",
        "- Quantities are human-measured. Nothing here may be generated, inferred or 'completed' by AI.",
        "- AI output is a *suggestion* (`ai_suggestions`, Pending Review) until an authorised human accepts it in the application.",
        "- Rates, assumptions, assemblies, supplier selections, the estimate, the offer and the tender export each need their own recorded human approval "
        "(roles in `app/approvals/policy.py`). Do not bypass `app/approvals` or write approval rows directly.",
        "- A project may mix approved rates with approved *provisional* allowances; unresolved mandatory items block final approval.",
        "- Submission-ready export exists only after the Commercial Approver releases the tender export.",
        "", "## Outstanding issues (from the database at last refresh)", "",
    ]
    L += [f"- {i}" for i in issues] or ["- none recorded"]
    L += ["", "## Updating this context safely", "",
          "- Run `python -m app.cli project refresh " + pid + "` (or re-open the project in the UI) to regenerate this block and `project.json`.",
          "- Only the block between the GENERATED markers is rewritten. Add your own notes below the 'Human notes' heading; they are preserved.",
          "- Project facts live in the database: change them in the application (project settings), not by editing this file.",
          "- After adding documents run `python -m app.cli project index " + pid + "` to refresh `2. AI Context/`.",
          "", GEN_END]
    return "\n".join(L) + "\n"


def write_project_claude_md(db: Database, proj: dict, root: Path) -> Path:
    f = root / "CLAUDE.md"
    block = render_generated_block(db, proj)
    if f.exists():
        text = f.read_text(encoding="utf-8")
        if GEN_BEGIN.split(" (")[0] in text and GEN_END in text:
            head = text[:text.index(GEN_BEGIN.split(" (")[0])]
            tail = text[text.index(GEN_END) + len(GEN_END):].lstrip("\n")
            new = head + block.rstrip("\n") + "\n\n" + tail
        else:                                     # human-authored file without markers: keep it intact, append the block
            new = text.rstrip("\n") + "\n\n" + block
    else:
        new = block + "\n" + HUMAN_HEADER + "\n\n_Add project-specific notes for future sessions here._\n"
    if not f.exists() or f.read_text(encoding="utf-8") != new:
        f.write_text(new, encoding="utf-8")
    return f
