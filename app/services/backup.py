"""Local backup / restore / validation and project-level export packages."""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from ..config import Settings, get_settings
from ..core.errors import Conflict, ValidationFailed
from ..core.timeutil import now_iso
from ..database import Database, rows_to_dicts
from . import audit

APP_VERSION = "0.1.0"
KEY_TABLES = ["projects", "resources", "resource_rates", "assumptions", "assemblies", "boq_items", "quotations", "approvals", "audit_log",
              # end-to-end closure records (migration 0015)
              "productivity_norms", "workforce_profiles", "work_activities", "programme_baselines", "tender_enquiries", "tender_documents", "tender_queries", "tender_register_items",
              "tender_packs", "generated_documents", "open_actions", "standards_register"]


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def _snapshot_db(src: Path, dst: Path) -> None:
    """Consistent copy via SQLite's online backup API (safe while the app is running)."""
    s = sqlite3.connect(str(src))
    d = sqlite3.connect(str(dst))
    with d:
        s.backup(d)
    s.close()
    d.close()


def create_backup(settings: Settings | None = None, dest: Path | None = None, label: str = "") -> Path:
    s = settings or get_settings()
    s.ensure_dirs()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = Path(dest) if dest else s.backups_dir / f"ksa-backup-{ts}{('-' + label) if label else ''}.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise Conflict(f"Backup file {dest} already exists; refusing to overwrite.")
    tmp = Path(tempfile.mkdtemp(prefix="ksa_bk_"))
    try:
        dbcopy = tmp / "ksa_estimator.db"
        _snapshot_db(s.db_path, dbcopy)
        counts = {}
        c = sqlite3.connect(str(dbcopy))
        for t in KEY_TABLES:
            try:
                counts[t] = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except sqlite3.Error:
                counts[t] = None
        migrations = [r[0] for r in c.execute("SELECT version FROM schema_migrations ORDER BY version")]
        c.close()
        files: dict[str, str] = {}
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(dbcopy, "ksa_estimator.db")
            files["ksa_estimator.db"] = _sha_file(dbcopy)
            for base, prefix in ((s.projects_dir, "projects"), (s.outputs_dir, "outputs"), (s.workspaces_dir, "workspaces"), (s.imports_dir, "imports")):
                if base.exists():
                    for p in sorted(base.rglob("*")):
                        if p.is_file() and not p.name.startswith("."):
                            arc = f"{prefix}/{p.relative_to(base).as_posix()}"
                            z.write(p, arc)
                            files[arc] = _sha_file(p)
            manifest = {"app_version": APP_VERSION, "created": now_iso(), "label": label, "schema_migrations": migrations,
                        "row_counts": counts, "files": files}
            z.writestr("manifest.json", json.dumps(manifest, indent=1))
        return dest
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def validate_backup(path: Path) -> dict:
    """Checks zip integrity, manifest hashes, SQLite integrity_check, and the audit hash chain. Returns a report; never modifies anything."""
    path = Path(path)
    rep = {"ok": False, "problems": [], "manifest": None}
    if not path.exists():
        rep["problems"].append("Backup file not found.")
        return rep
    try:
        with zipfile.ZipFile(path) as z:
            bad = z.testzip()
            if bad:
                rep["problems"].append(f"Corrupt zip member: {bad}")
                return rep
            names = set(z.namelist())
            if "manifest.json" not in names or "ksa_estimator.db" not in names:
                rep["problems"].append("manifest.json or ksa_estimator.db missing.")
                return rep
            manifest = json.loads(z.read("manifest.json"))
            rep["manifest"] = manifest
            for name, digest in manifest["files"].items():
                if name not in names:
                    rep["problems"].append(f"Missing file: {name}")
                elif _sha(z.read(name)) != digest:
                    rep["problems"].append(f"Hash mismatch: {name}")
            tmp = Path(tempfile.mkdtemp(prefix="ksa_val_"))
            try:
                dbp = tmp / "db.sqlite"
                dbp.write_bytes(z.read("ksa_estimator.db"))
                c = sqlite3.connect(str(dbp))
                ic = c.execute("PRAGMA integrity_check").fetchone()[0]
                if ic != "ok":
                    rep["problems"].append(f"SQLite integrity_check: {ic}")
                c.close()
                d = Database(dbp)
                chain = audit.verify_chain(d)
                if not chain["ok"]:
                    rep["problems"].append(f"Audit chain broken at id {chain['first_bad_id']}")
                rep["audit_entries"] = chain["checked"]
                d.close()
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
    except zipfile.BadZipFile:
        rep["problems"].append("Not a valid zip file.")
        return rep
    rep["ok"] = not rep["problems"]
    return rep


def restore_backup(path: Path, *, confirm: bool, settings: Settings | None = None, overwrite_files: bool = False) -> dict:
    """DESTRUCTIVE for the current database. Requires confirm=True. A safety backup of the current state is taken first,
    the backup is validated before anything is touched, and existing project files are never silently overwritten."""
    from .. import database as dbmod

    s = settings or get_settings()
    if not confirm:
        raise ValidationFailed("Restore replaces the current database. Re-run with explicit confirmation (--yes).", code="CONFIRM_REQUIRED")
    rep = validate_backup(path)
    if not rep["ok"]:
        raise ValidationFailed("Backup failed validation: " + "; ".join(rep["problems"]), code="BACKUP_INVALID")
    safety = None
    if s.db_path.exists():
        dbmod.set_db(None)
        safety = create_backup(s, label="pre-restore")
    out = {"safety_backup": str(safety) if safety else None, "files_restored": 0, "files_conflicting": []}
    with zipfile.ZipFile(path) as z:
        s.db_path.parent.mkdir(parents=True, exist_ok=True)
        for ext in ("", "-wal", "-shm"):
            p = Path(str(s.db_path) + ext)
            if p.exists():
                p.unlink()
        s.db_path.write_bytes(z.read("ksa_estimator.db"))
        for name in z.namelist():
            if name in ("manifest.json", "ksa_estimator.db") or name.endswith("/"):
                continue
            base = {"projects": s.projects_dir, "workspaces": s.workspaces_dir, "imports": s.imports_dir}.get(name.split("/", 1)[0], s.outputs_dir)
            target = base / name.split("/", 1)[1]
            data = z.read(name)
            if target.exists() and _sha_file(target) != _sha(data):
                if not overwrite_files:
                    alt = target.with_name(target.name + ".restored")
                    alt.parent.mkdir(parents=True, exist_ok=True)
                    alt.write_bytes(data)
                    out["files_conflicting"].append(str(target))
                    continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            out["files_restored"] += 1
    return out


def export_project_package(db: Database, project_id: str, dest: Path | None = None, settings: Settings | None = None) -> Path:
    """Self-contained project export (JSON data + uploads + outputs) for hand-over or archive."""
    s = settings or get_settings()
    proj = db.one("SELECT * FROM projects WHERE id=?", (project_id,))
    if not proj:
        raise ValidationFailed(f"Project {project_id} not found.")
    dest = Path(dest) if dest else s.backups_dir / f"project-{project_id}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise Conflict(f"{dest} exists; refusing to overwrite.")
    tables = {
        "project": "SELECT * FROM projects WHERE id=?", "boq_imports": "SELECT * FROM boq_imports WHERE project_id=?",
        "boq_items": "SELECT * FROM boq_items WHERE project_id=?", "boq_rejected_rows": "SELECT * FROM boq_rejected_rows WHERE project_id=?",
        "change_requests": "SELECT * FROM change_requests WHERE project_id=?", "project_assumptions": "SELECT * FROM project_assumptions WHERE project_id=?",
        "indirect_items": "SELECT * FROM indirect_items WHERE project_id=?", "project_durations": "SELECT * FROM project_durations WHERE project_id=?",
        "estimate_versions": "SELECT * FROM estimate_versions WHERE project_id=?", "offers": "SELECT * FROM offers WHERE project_id=?",
        "clarifications": "SELECT * FROM clarifications WHERE project_id=?", "scope_register": "SELECT * FROM scope_register WHERE project_id=?",
        "risks": "SELECT * FROM risks WHERE project_id=?", "procurement_items": "SELECT * FROM procurement_items WHERE project_id=?",
        "quotations": "SELECT * FROM quotations WHERE project_id=?", "recon_findings": "SELECT * FROM recon_findings WHERE project_id=?",
        "approvals": "SELECT * FROM approvals WHERE project_id=?", "audit_log": "SELECT * FROM audit_log WHERE project_id=?",
        "actual_costs": "SELECT * FROM actual_costs WHERE project_id=?",
        # structure, programme, parameters, analyses and controls (iteration 4) and the rows earlier exports omitted
        "takeoff_resource_lines": "SELECT * FROM takeoff_resource_lines WHERE project_id=?", "schedule_tasks": "SELECT * FROM schedule_tasks WHERE project_id=?",
        "estimate_snapshots": "SELECT * FROM estimate_snapshots WHERE project_id=?", "procurement_packages": "SELECT * FROM procurement_packages WHERE project_id=?",
        "wbs_nodes": "SELECT * FROM wbs_nodes WHERE project_id=?", "boq_wbs": "SELECT * FROM boq_wbs WHERE project_id=?", "code_crosswalk": "SELECT * FROM code_crosswalk WHERE project_id=?",
        "governed_params": "SELECT * FROM governed_params WHERE project_id=?", "analysis_runs": "SELECT * FROM analysis_runs WHERE project_id=?",
        "mto_applications": "SELECT * FROM mto_applications WHERE project_id=?", "project_profiles": "SELECT * FROM project_profiles WHERE project_id=?",
        "profile_assessments": "SELECT * FROM profile_assessments WHERE project_id=?", "bid_scores": "SELECT * FROM bid_scores WHERE project_id=?",
        "long_lead_items": "SELECT * FROM long_lead_items WHERE project_id=?", "package_scope": "SELECT * FROM package_scope WHERE project_id=?",
        "variations": "SELECT * FROM variations WHERE project_id=?", "task_progress": "SELECT * FROM task_progress WHERE project_id=?",
        "variation_lines": "SELECT l.* FROM variation_lines l JOIN variations v ON v.id=l.variation_id WHERE v.project_id=?",
        # end-to-end closure records
        "work_activities": "SELECT * FROM work_activities WHERE project_id=?", "programme_baselines": "SELECT * FROM programme_baselines WHERE project_id=?",
        "tender_enquiries": "SELECT * FROM tender_enquiries WHERE project_id=?", "tender_documents": "SELECT * FROM tender_documents WHERE project_id=?",
        "tender_queries": "SELECT * FROM tender_queries WHERE project_id=?", "tender_register_items": "SELECT * FROM tender_register_items WHERE project_id=?",
        "tender_packs": "SELECT * FROM tender_packs WHERE project_id=?", "open_actions": "SELECT * FROM open_actions WHERE project_id=?",
        "generated_documents": "SELECT g.* FROM generated_documents g JOIN tender_packs p ON p.pk=g.pack_pk WHERE p.project_id=?",
    }
    data = {k: rows_to_dicts(db.all(q, (project_id,))) for k, q in tables.items()}
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("project_data.json", json.dumps(data, indent=1, default=str))
        files = {}
        from . import workspaces as _ws
        ws = _ws.find_existing(project_id, s.workspaces_dir)
        for base, prefix in ((s.projects_dir / project_id, "uploads"), (s.outputs_dir / project_id, "outputs"), *(((ws, "workspace"),) if ws else ())):
            if base.exists():
                for p in sorted(base.rglob("*")):
                    if p.is_file():
                        arc = f"{prefix}/{p.relative_to(base).as_posix()}"
                        z.write(p, arc)
                        files[arc] = _sha_file(p)
        z.writestr("manifest.json", json.dumps({"project": project_id, "created": now_iso(), "app_version": APP_VERSION, "files": files}, indent=1))
    audit.log(db, "system", "project", project_id, "export_package", after={"file": dest.name}, project_id=project_id)
    return dest
