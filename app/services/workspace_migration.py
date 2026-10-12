"""Non-destructive migration of legacy per-project files into numbered workspaces.

Legacy layout (pre-0007):  data/projects/<PRJ>/uploads/*  and  data/outputs/<PRJ>/*
New layout:                projects/<PRJ>-<slug>/<numbered areas>/

* Files are COPIED, never moved or deleted; legacy originals stay where they were (DB rows that store legacy absolute paths keep working).
* Existing target files are never overwritten: identical content is skipped, different content is written beside it as `<name>.legacy-<sha8>`.
* `dry_run=True` computes and reports the plan without creating anything (not even folders).
* A real run first takes a verified database backup, then writes a JSON migration report to var/migration_reports/.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from ..config import get_settings
from ..database import Database
from . import backup, workspaces

_OUT_RULES = [(r"^estimate_master_", "estimate"), (r"^(pricing_schedule|estimate_report|OFR|offer|letter_of_offer)", "commercial"),
              (r"^reconciliation_report", "reconciliation"), (r"^RFQ", "procurement")]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _area_for_output(name: str) -> str:
    for pat, area in _OUT_RULES:
        if re.match(pat, name, re.I):
            return area
    return "exports"


def plan(db: Database) -> list[dict]:
    s = get_settings()
    items: list[dict] = []
    for p in db.all("SELECT id, name, workspace_path FROM projects ORDER BY id"):
        pid = p["id"]
        existing = workspaces.find_existing(pid)
        root = existing or (s.workspaces_dir / workspaces.workspace_name(pid, p["name"]))
        moves: list[dict] = []
        for base, kind in ((s.projects_dir / pid / "uploads", "uploads"), (s.outputs_dir / pid, "outputs")):
            if not base.is_dir():
                continue
            for f in sorted(base.rglob("*")):
                if not f.is_file() or f.name.startswith("."):
                    continue
                area = "boq" if kind == "uploads" else _area_for_output(f.name)
                rel = f.relative_to(base)
                target = root / workspaces.AREAS[area] / rel
                if target.exists():
                    action = "skip-identical" if _sha(target) == _sha(f) else "copy-as-legacy-variant"
                else:
                    action = "copy"
                moves.append({"from": str(f), "to": str(target), "area": workspaces.AREAS[area], "action": action})
        items.append({"project": pid, "workspace": str(root), "workspace_exists": existing is not None, "files": moves})
    return items


def migrate(db: Database, *, dry_run: bool = True) -> dict:
    s = get_settings()
    pl = plan(db)
    report = {"dry_run": dry_run, "started": datetime.now(timezone.utc).isoformat(timespec="seconds"), "projects": [], "errors": [], "backup": None,
              "totals": {"projects": len(pl), "files_planned": sum(len(p["files"]) for p in pl)}}
    if dry_run:
        report["projects"] = pl
        report["note"] = "Dry run: nothing was created, copied or changed."
        return report
    b = backup.create_backup(s, label="pre-workspace-migration",
                             dest=s.backups_dir / f"ksa-backup-pre-workspace-migration-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')}.zip")
    ok = backup.validate_backup(b)
    report["backup"] = {"file": str(b), "valid": ok["ok"]}
    if not ok["ok"]:
        report["errors"].append("pre-migration backup failed validation; migration aborted")
        return report
    copied = skipped = variants = 0
    for item in pl:
        pid = item["project"]
        try:
            workspaces.ensure_workspace(db, pid)
        except Exception as e:
            report["errors"].append(f"{pid}: {type(e).__name__}: {e}")
            continue
        done = []
        for m in item["files"]:
            src, dst = Path(m["from"]), Path(m["to"])
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                if _sha(dst) == _sha(src):
                    skipped += 1
                    done.append({**m, "result": "skipped (identical)"})
                    continue
                dst = dst.with_name(f"{dst.name}.legacy-{_sha(src)[:8]}")
                variants += not dst.exists()
            if not dst.exists():
                shutil.copy2(src, dst)
                copied += 1
            done.append({**m, "to": str(dst), "result": "copied"})
        report["projects"].append({"project": pid, "workspace": item["workspace"], "files": done})
    report["totals"].update(copied=copied, skipped_identical=skipped, legacy_variants=variants)
    out = s.var_dir / "migration_reports"
    out.mkdir(parents=True, exist_ok=True)
    f = out / f"workspaces-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
    f.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    report["report_file"] = str(f)
    return report
