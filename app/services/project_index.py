"""Project document indexer (repeatable, read-only over originals).

Scans a project's workspace, records every file in `project_documents` and writes searchable, VERSIONED text extracts plus a
machine-readable index and a plain summary under `2. AI Context/`.

Rules
* Original documents are only ever read.  Files inside `2. AI Context/` are generated and are not indexed themselves.
* When a document's hash changes the old extract is kept (`<id>_v<n>.txt`), a new version is written and the record is flagged
  `Source changed - review` until a human marks it reviewed.  Extracts are never silently replaced.
* No parser available / unsupported type / unreadable file -> recorded as indexed but NOT text-extracted (with the reason).
  Nothing is invented; summaries are counts and lists only and carry a "not authoritative" notice.
* Revision / trade / category are taken from the FILE NAME only and only when the pattern is unambiguous.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from ..approvals import engine as approvals
from ..core.errors import NotFound
from ..core.timeutil import now_iso
from ..database import Database, rows_to_dicts
from ..models.actor import Actor
from . import audit, workspaces

AI_AREA = workspaces.AREAS["ai_context"]
MAX_EXTRACT_CHARS = 2_000_000
MAX_FILE_BYTES = 150 * 1024 * 1024
SKIP_NAMES = {"CLAUDE.md", workspaces.MANIFEST}
TEXT_TYPES = {"txt", "md", "csv", "json", "tsv", "log", "xml", "html", "htm"}

_CATEGORY = [
    ("boq", r"boq|bill[ _-]?of[ _-]?quantit|schedule[ _-]?of[ _-]?(rates|prices)|takeoff|take-off|pricing[ _-]?schedule"),
    ("specification", r"spec(ification)?s?\b|spec[_-]|\bsection[ _-]?\d"),
    ("drawing", r"drawing|dwg|\bplan\b|elevation|section[ _-]drawing|layout|detail|\b[ASMEPCL]-?\d{3}\b"),
    ("addendum", r"addend|addenda|bulletin|\brfi\b|clarif"),
    ("quotation", r"quot|offer|proposal|rfq"),
    ("contract", r"contract|conditions|\bgcc\b|\bscc\b|terms"),
    ("programme", r"programme|program|schedule|gantt|\bp6\b|baseline"),
    ("report", r"report|study|survey|soil|geotech"),
]
_TRADE = [
    ("Architectural", r"archit|finish|ceiling|partition|door|window|joinery|\bA-?\d{3}\b"),
    ("Structural", r"struct|rebar|reinforc|concrete|foundation|steel|\bS-?\d{3}\b"),
    ("Civil / Infrastructure", r"civil|road|drain|sewer|earthwork|infrastructure|\bC-?\d{3}\b"),
    ("HVAC", r"hvac|air[ _-]?cond|chiller|duct|ventilat|\bM-?\d{3}\b"),
    ("Plumbing", r"plumb|sanitary|water[ _-]?supply|\bP-?\d{3}\b"),
    ("Fire protection", r"fire|sprinkler|hydrant|\bFP-?\d{2,3}\b"),
    ("Electrical", r"electric|lighting|power|switchgear|\bE-?\d{3}\b|\bLV\b"),
    ("ELV", r"\belv\b|extra[ _-]?low|cctv|access[ _-]?control|data|fire[ _-]?alarm|\bEL-?\d{2,3}\b"),
    ("External works", r"external|landscape|paving|fenc|\bL-?\d{3}\b"),
]
_REV_PATTERNS = [r"[_\-\s]rev(?:ision)?[_\-\s]?([A-Za-z]?\d{0,2}|[A-Za-z])(?=[_\-\s.]|$)", r"[_\-\s]r(\d{1,2})(?=[_\-\s.]|$)"]


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def classify_name(name: str) -> dict:
    """Category / trade / revision guesses from the file name only."""
    stem = Path(name).stem
    low = stem.lower()
    cat = next((c for c, pat in _CATEGORY if re.search(pat, stem, re.I)), None)
    trades = [t for t, pat in _TRADE if re.search(pat, stem, re.I)]
    rev = None
    for pat in _REV_PATTERNS:
        m = re.search(pat, stem, re.I)
        if m and m.group(1):
            rev = m.group(1).upper()
            break
    return {"category": cat, "trade_hint": ", ".join(trades) if len(trades) <= 2 else None, "revision": rev}


# ---------------------------------------------------------------------------------------------------- extraction
def extract_text(path: Path) -> tuple[str | None, str | None]:
    """(text, reason_not_extracted). Never raises; text None means not extracted."""
    ext = path.suffix.lower().lstrip(".")
    try:
        if ext in TEXT_TYPES:
            raw = path.read_bytes()
            for enc in ("utf-8-sig", "utf-16", "cp1256", "latin-1"):
                try:
                    txt = raw.decode(enc)
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
            if ext in ("html", "htm"):
                txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", txt, flags=re.S | re.I)
                txt = re.sub(r"<[^>]+>", " ", txt)
            return txt, None
        if ext == "pdf":
            try:
                from pypdf import PdfReader
            except ImportError:
                return None, "PDF parser (pypdf) not installed"
            r = PdfReader(str(path))
            if r.is_encrypted:
                return None, "PDF is encrypted/password-protected"
            parts = [f"=== page {i + 1} ===\n{(pg.extract_text() or '').strip()}" for i, pg in enumerate(r.pages)]
            txt = "\n\n".join(parts)
            if not re.sub(r"=== page \d+ ===|\s", "", txt):
                return None, "PDF contains no extractable text (scanned image?) - OCR not available"
            return txt, None
        if ext == "docx":
            try:
                import docx
            except ImportError:
                return None, "DOCX parser (python-docx) not installed"
            d = docx.Document(str(path))
            lines = [p.text for p in d.paragraphs if p.text.strip()]
            for ti, t in enumerate(d.tables, 1):
                lines.append(f"--- table {ti} ---")
                lines += [" | ".join(c.text.strip() for c in row.cells) for row in t.rows]
            return "\n".join(lines), None
        if ext in ("xlsx", "xlsm"):
            import openpyxl
            wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
            out = []
            for ws in wb.worksheets:
                out.append(f"=== sheet {ws.title} ===")
                for n, row in enumerate(ws.iter_rows(values_only=True), 1):
                    if n > 5000:
                        out.append("... (truncated at 5000 rows)")
                        break
                    if any(c not in (None, "") for c in row):
                        out.append(" | ".join("" if c is None else str(c) for c in row))
            wb.close()
            return "\n".join(out), None
    except Exception as e:  # corrupt file, parser failure...
        return None, f"{type(e).__name__}: {str(e)[:200]}"
    if ext in ("dwg", "dxf", "rvt", "ifc", "nwd"):
        return None, f"CAD/BIM format '.{ext}' is not text-extracted (no parser; use a PDF plot of the drawing)"
    return None, f"No text extractor for '.{ext or '(none)'}' files"


# ---------------------------------------------------------------------------------------------------- indexing
def _iter_files(root: Path):
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if rel.parts[0] == AI_AREA or p.name.startswith(".") or (len(rel.parts) == 1 and p.name in SKIP_NAMES):
            continue
        if any(part.startswith("~$") for part in rel.parts):
            continue
        yield p, rel


def index_project(db: Database, actor: Actor | str, project_id: str, *, extract: bool = True) -> dict:
    """Index (or re-index) a workspace. Idempotent. Returns counts and the list of changes."""
    if isinstance(actor, Actor):
        approvals.require_author(actor)
    root = workspaces.ensure_workspace(db, project_id)
    ai = root / AI_AREA
    (ai / "extracts").mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    changes: list[dict] = []
    stats = dict(new=0, changed=0, unchanged=0, missing=0, extracted=0, not_extracted=0, errors=0)
    ts = now_iso()
    for p, rel in _iter_files(root):
        rel_s = rel.as_posix()
        seen.add(rel_s)
        st = p.stat()
        area = rel.parts[0] if len(rel.parts) > 1 else ""
        existing = db.one("SELECT * FROM project_documents WHERE project_id=? AND rel_path=?", (project_id, rel_s))
        too_big = st.st_size > MAX_FILE_BYTES
        sha = None if too_big else _sha256(p)
        meta = classify_name(p.name)
        base = dict(file_name=p.name, file_type=p.suffix.lower().lstrip(".") or None, size_bytes=st.st_size,
                    modified_at=datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds"),
                    sha256=sha, area=area, last_indexed_at=ts, **meta)
        if existing and existing["sha256"] == sha and existing["extraction_status"] != "Missing":
            db.update("project_documents", {**base, "extraction_status": existing["extraction_status"]}, "id=?", (existing["id"],))
            stats["unchanged"] += 1
            continue
        changed = existing is not None
        text, reason = (None, "File larger than the indexing limit") if too_big else (extract_text(p) if extract else (None, "Extraction skipped"))
        version = (existing["extract_version"] if existing else 0)
        status, err, xpath, chars = "Not text-extracted", reason, existing["extract_path"] if existing else None, None
        if text is not None:
            version += 1
            chars = len(text)
            clipped = text[:MAX_EXTRACT_CHARS]
            doc_key = existing["id"] if existing else None
            status, err = "Extracted", None
        else:
            doc_key = existing["id"] if existing else None
            if reason and ("Extraction skipped" not in reason) and not reason.startswith("No text extractor") \
                    and not reason.startswith("CAD/BIM") and "larger than" not in reason:
                status = "Extraction error"
                stats["errors"] += 1
        review = "Source changed - review" if changed else "New"
        if existing:
            db.update("project_documents", {**base, "extraction_status": status, "extraction_error": err, "extract_version": version,
                                            "text_chars": chars, "review_status": review}, "id=?", (existing["id"],))
            did = existing["id"]
            stats["changed"] += 1
        else:
            did = db.insert("project_documents", dict(project_id=project_id, rel_path=rel_s, extraction_status=status, extraction_error=err,
                                                      extract_version=version, text_chars=chars, review_status=review,
                                                      first_indexed_at=ts, **base))
            stats["new"] += 1
        if text is not None:
            ext_path = ai / "extracts" / f"doc{did:05d}_v{version}.txt"
            header = (f"# EXTRACT (machine-generated, not authoritative)\n# source: {rel_s}\n# sha256: {sha}\n# extract version: {version}\n"
                      f"# extracted: {ts}\n\n")
            ext_path.write_text(header + clipped, encoding="utf-8")        # new file per version; older versions are kept
            db.update("project_documents", {"extract_path": ext_path.relative_to(root).as_posix()}, "id=?", (did,))
            stats["extracted"] += 1
        else:
            stats["not_extracted"] += 1
        changes.append({"file": rel_s, "event": "changed" if changed else "new", "status": status, "reason": err})
    # files that disappeared
    for r in db.all("SELECT id, rel_path, extraction_status FROM project_documents WHERE project_id=?", (project_id,)):
        if r["rel_path"] not in seen and r["extraction_status"] != "Missing":
            db.update("project_documents", {"extraction_status": "Missing", "review_status": "Missing", "last_indexed_at": ts}, "id=?", (r["id"],))
            stats["missing"] += 1
            changes.append({"file": r["rel_path"], "event": "missing"})
    docs = rows_to_dicts(db.all("SELECT * FROM project_documents WHERE project_id=? ORDER BY rel_path", (project_id,)))
    write_index_files(db, project_id, root, docs, stats)
    audit.log(db, actor, "project", project_id, "index_documents", after=stats, project_id=project_id)
    return {**stats, "documents": len(docs), "changes": changes, "index_file": str(ai / "project_index.json")}


def write_index_files(db: Database, project_id: str, root: Path, docs: list[dict], stats: dict) -> None:
    ai = root / AI_AREA
    idx = {"schema": "ksa-estimator/project-index/1", "project_id": project_id, "generated_at": now_iso(),
           "notice": "Generated index. Original documents are authoritative; extracts and this index are aids only.",
           "documents": [{k: d[k] for k in ("id", "rel_path", "file_name", "file_type", "size_bytes", "modified_at", "sha256", "area", "category",
                                            "trade_hint", "revision", "extraction_status", "extraction_error", "extract_version",
                                            "extract_path", "text_chars", "review_status")} for d in docs]}
    (ai / "project_index.json").write_text(json.dumps(idx, indent=1, ensure_ascii=False), encoding="utf-8")
    by_status: dict[str, int] = {}
    by_cat: dict[str, int] = {}
    for d in docs:
        by_status[d["extraction_status"]] = by_status.get(d["extraction_status"], 0) + 1
        by_cat[d["category"] or "unclassified"] = by_cat.get(d["category"] or "unclassified", 0) + 1
    L = [f"# Document index summary - {project_id}", "",
         "> Generated listing. **Not authoritative**: the original drawings and specifications always prevail. No content is summarised or inferred here;",
         "> categories, trades and revisions come from file names only.", "",
         f"Generated {now_iso()} - {len(docs)} file(s).", "", "## By extraction status", ""]
    L += [f"- {k}: {v}" for k, v in sorted(by_status.items())] or ["- (no files)"]
    L += ["", "## By category (file-name based)", ""] + ([f"- {k}: {v}" for k, v in sorted(by_cat.items())] or ["- (no files)"])
    flagged = [d for d in docs if d["review_status"] in ("Source changed - review", "Missing")]
    L += ["", "## Needs human attention", ""]
    L += [f"- `{d['rel_path']}` - {d['review_status']}" for d in flagged] or ["- nothing flagged"]
    errs = [d for d in docs if d["extraction_status"] in ("Extraction error", "Not text-extracted")]
    L += ["", "## Not text-extracted / errors", ""]
    L += [f"- `{d['rel_path']}` - {d['extraction_status']}: {d['extraction_error']}" for d in errs] or ["- none"]
    L += ["", "## Files", "", "| File | Area | Category | Trade hint | Rev | Status | Review |", "|---|---|---|---|---|---|---|"]
    for d in docs:
        L.append(f"| {d['rel_path']} | {d['area']} | {d['category'] or ''} | {d['trade_hint'] or ''} | {d['revision'] or ''} | "
                 f"{d['extraction_status']} | {d['review_status']} |")
    (ai / "project_summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def list_documents(db: Database, project_id: str) -> list[dict]:
    return rows_to_dicts(db.all("SELECT * FROM project_documents WHERE project_id=? ORDER BY rel_path", (project_id,)))


def mark_reviewed(db: Database, actor: Actor, project_id: str, doc_id: int, comment: str = "") -> None:
    """A human confirms they have looked at a new/changed document and its extract."""
    approvals.require_author(actor)
    r = db.one("SELECT * FROM project_documents WHERE id=? AND project_id=?", (doc_id, project_id))
    if not r:
        raise NotFound("Document not found in this project.")
    db.update("project_documents", {"review_status": "Reviewed"}, "id=?", (doc_id,))
    audit.log(db, actor, "project_document", doc_id, "reviewed", comment=comment, project_id=project_id)


def search(db: Database, project_id: str, query: str, limit: int = 20, context: int = 80) -> list[dict]:
    """Case-insensitive text search over the CURRENT extract of each document (snippets only)."""
    root = workspaces.resolve_dir(project_id, db)
    out: list[dict] = []
    q = query.strip().lower()
    if not q:
        return out
    for d in list_documents(db, project_id):
        if d["extraction_status"] != "Extracted" or not d["extract_path"]:
            continue
        f = root / d["extract_path"]
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        low = text.lower()
        pos, n = low.find(q), 0
        while pos != -1 and n < 3 and len(out) < limit:
            out.append({"doc_id": d["id"], "file": d["rel_path"], "extract_version": d["extract_version"],
                        "snippet": text[max(0, pos - context):pos + len(q) + context].replace("\n", " ")})
            n += 1
            pos = low.find(q, pos + len(q))
        if len(out) >= limit:
            break
    return out
