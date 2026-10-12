"""Import manifests: provenance for every file or retrieved payload that enters the system."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from ..config import get_settings
from ..core.errors import Conflict
from ..core.timeutil import now_iso
from ..database import Database, jload
from ..imports.readers import sha256_file
from ..services import audit


def store_original(src: Path, name: str | None = None) -> tuple[Path, str]:
    """Copy the file into data/public_data/imports as `<sha10>_<name>` (never overwritten; identical content is reused)."""
    src = Path(src)
    sha = sha256_file(src)
    d = get_settings().imports_dir
    d.mkdir(parents=True, exist_ok=True)
    dest = d / f"{sha[:10]}_{name or src.name}"
    if not dest.exists():
        shutil.copy2(src, dest)
    return dest, sha


def store_payload(body: bytes, name: str) -> tuple[Path, str]:
    import hashlib
    sha = hashlib.sha256(body).hexdigest()
    d = get_settings().imports_dir
    d.mkdir(parents=True, exist_ok=True)
    dest = d / f"{sha[:10]}_{name}"
    if not dest.exists():
        dest.write_bytes(body)
    return dest, sha


def existing_import(db: Database, sha: str, kind: str) -> dict | None:
    r = db.one("SELECT * FROM import_manifests WHERE sha256=? AND kind=? AND dry_run=0 AND status='Imported'", (sha, kind))
    return dict(r) if r else None


def refuse_duplicate(db: Database, sha: str, kind: str) -> None:
    ex = existing_import(db, sha, kind)
    if ex:
        raise Conflict(f"This exact file was already imported (manifest #{ex['id']} on {ex['imported_at']}). Datasets are never silently replaced; "
                       f"if the source published a corrected file it will have a different hash.", code="ALREADY_IMPORTED")


def write_manifest(db: Database, actor, *, kind: str, adapter: str, source_id: str | None, source_name: str | None, source_url: str | None,
                   original_path: str | None, stored_path: Path | None, sha: str | None, description: str, dry_run: bool, parsing: dict,
                   accepted: int, rejected: int, errors: list[dict], candidate_ids: list[int], status: str | None = None) -> int:
    status = status or ("Dry run" if dry_run else "Imported")
    mid = db.insert("import_manifests", dict(
        kind=kind, adapter=adapter, source_id=source_id, source_name=source_name, source_url=source_url, original_path=original_path,
        stored_path=str(stored_path) if stored_path else None, sha256=sha, description=description, imported_at=now_iso(),
        imported_by=getattr(actor, "username", str(actor)), dry_run=int(dry_run), status=status, parsing_json=parsing,
        accepted_rows=accepted, rejected_rows=rejected, errors_json=errors[:500], candidate_ids_json=candidate_ids))
    if not dry_run and stored_path:
        mf = Path(str(stored_path) + f".manifest-{mid}.json")
        doc = {"manifest_id": mid, "kind": kind, "adapter": adapter, "source_id": source_id, "source_name": source_name, "source_url": source_url,
               "original_path": original_path, "stored_path": str(stored_path), "sha256": sha, "description": description,
               "imported_at": now_iso(), "imported_by": getattr(actor, "username", str(actor)), "parsing": parsing,
               "accepted_rows": accepted, "rejected_rows": rejected, "errors": errors[:500], "candidate_ids": candidate_ids}
        mf.write_text(json.dumps(doc, indent=1, default=str, ensure_ascii=False), encoding="utf-8")
        db.update("import_manifests", {"manifest_path": str(mf)}, "id=?", (mid,))
        audit.log(db, actor, "import_manifest", mid, "import", after={"kind": kind, "sha": (sha or "")[:12], "accepted": accepted, "rejected": rejected})
    return mid


def get_manifest(db: Database, mid: int) -> dict | None:
    r = db.one("SELECT * FROM import_manifests WHERE id=?", (mid,))
    if not r:
        return None
    d = dict(r)
    for k in ("parsing_json", "errors_json", "candidate_ids_json"):
        d[k.replace("_json", "")] = jload(d.get(k), None)
    return d
