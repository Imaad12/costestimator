"""Standards / source register: where a requirement, a rule or a productivity basis comes from, what was actually read, and what still needs a person to acquire.

The register holds concise references and traceable paraphrases only - never copyrighted text, prices or productivity values. A row marked 'Verified' means a person or a research session read
the primary page; it is NOT a statement that a project complies with the standard. Rows without a URL or file reference can never be 'Verified'.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..core.errors import ValidationFailed
from ..core.timeutil import now_iso
from ..database import Database, rows_to_dicts

STATUSES = ("Verified - primary source read", "Partially verified - secondary source", "Not verified - requires human acquisition")


def import_register(db: Database, path: Path, *, created_by: str = "system:seed", dry_run: bool = False) -> dict:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    new, skipped, problems = 0, 0, []
    for s in doc["sources"]:
        sid = s.get("id")
        if s.get("verification_status") not in STATUSES:
            problems.append(f"{sid}: unknown verification_status {s.get('verification_status')!r}")
            continue
        if s["verification_status"].startswith("Verified") and not s.get("url"):
            problems.append(f"{sid}: a 'Verified' row needs the URL or file that was read")
            continue
        if not s.get("title") or not s.get("access_date"):
            problems.append(f"{sid}: title and access_date are required")
            continue
        if db.one("SELECT 1 FROM standards_register WHERE id=?", (sid,)):
            skipped += 1
            continue
        new += 1
        if not dry_run:
            db.insert("standards_register", dict(id=sid, topic=s.get("topic") or "", title=s["title"], publisher=s.get("publisher"), url=s.get("url"), edition=s.get("edition_or_publication_date"),
                                                 access_date=s["access_date"], clause_or_page=s.get("clause_or_page"), scope=s.get("scope"), limitations=s.get("limitations"),
                                                 verification_status=s["verification_status"], paraphrase=s.get("paraphrase"), notes=s.get("notes"), created_by=created_by, created_at=now_iso()))
    if problems:
        raise ValidationFailed("standards register import refused: " + "; ".join(problems), code="STANDARDS_IMPORT")
    return dict(new=new, skipped=skipped, dry_run=dry_run)


def list_standards(db: Database, status: str | None = None) -> list[dict]:
    sql, par = "SELECT * FROM standards_register", []
    if status:
        sql, par = sql + " WHERE verification_status=?", [status]
    return rows_to_dicts(db.all(sql + " ORDER BY id", par))


def acquisition_list(db: Database) -> list[dict]:
    """Sources a person must obtain before the product may rely on them (manual evidence-import process)."""
    return [dict(id=r["id"], topic=r["topic"], title=r["title"], why=r["limitations"], next_step="Obtain the document, record edition / clause / page, then import the row with verification_status 'Verified' and the file or URL")
            for r in list_standards(db) if not r["verification_status"].startswith("Verified")]
