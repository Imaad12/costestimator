"""Command line: `python -m app.cli <command>`  (or the `ksa` script after `pip install -e .`)."""
from __future__ import annotations

import argparse
import getpass
import json
import logging
import os
import secrets
import sys
from pathlib import Path

from .config import get_settings
from .core.errors import AppError
from .database import Database, get_db, set_db
from .models.actor import Actor
from .services import audit, auth, backup, refdata

log = logging.getLogger("ksa.cli")
DEMO_USERS = [("estimator", "Demo Estimator", "Estimator"), ("procurement", "Demo Procurement Reviewer", "Procurement Reviewer"),
              ("commercial", "Demo Commercial Approver", "Commercial Approver")]


def cmd_init(a) -> int:
    s = get_settings()
    s.ensure_dirs()
    db = get_db()
    out = refdata.seed_reference(db)
    print("Reference data loaded:", json.dumps(out))
    if not db.one("SELECT 1 FROM users WHERE username='admin'"):
        pw = a.admin_password or os.environ.get("KSA_ADMIN_PASSWORD") or secrets.token_urlsafe(10)
        auth.create_user(db, "admin", "Administrator", "Administrator", pw)
        print(f"Created user 'admin'. Password: {pw}   (shown once - store it; change via `create-user --reset`)")
    if not db.one("SELECT 1 FROM users WHERE username='ai-assistant'"):
        auth.create_user(db, "ai-assistant", "AI Assistant (proposals only)", "AI Assistant", None, is_ai=True)
    if a.demo_users:
        for u, n, r in DEMO_USERS:
            if not db.one("SELECT 1 FROM users WHERE username=?", (u,)):
                auth.create_user(db, u, n, r, a.demo_password)
        print(f"Demo users created ({', '.join(u for u, _, _ in DEMO_USERS)}) with password '{a.demo_password}'. "
              "LOCAL DEMO ONLY - change or remove for any real use.")
    return 0


def cmd_create_user(a) -> int:
    db = get_db()
    pw = a.password or getpass.getpass("Password: ")
    if a.reset and db.one("SELECT 1 FROM users WHERE username=?", (a.username,)):
        db.update("users", {"password_hash": auth.hash_password(pw)}, "username=?", (a.username,))
        print("Password reset.")
    else:
        auth.create_user(db, a.username, a.display_name or a.username, a.role, pw)
        print("User created.")
    return 0


def cmd_run(a) -> int:
    import uvicorn
    s = get_settings()
    get_db()
    uvicorn.run("app.main:app", host=a.host or s.host, port=a.port or s.port, log_level=s.log_level.lower())
    return 0


def cmd_demo(a) -> int:
    from .demo.build import seed_demo
    db = get_db()
    refdata.seed_reference(db)
    res = seed_demo(db)
    print(json.dumps(res, indent=1, default=str))
    return 0


def cmd_backup(a) -> int:
    p = backup.create_backup(label=a.label or "")
    rep = backup.validate_backup(p)
    print(f"Backup written: {p}\nValidation: {'OK' if rep['ok'] else rep['problems']}")
    return 0 if rep["ok"] else 1


def cmd_validate_backup(a) -> int:
    rep = backup.validate_backup(Path(a.file))
    print(json.dumps({k: rep[k] for k in ("ok", "problems")}, indent=1))
    return 0 if rep["ok"] else 1


def cmd_restore(a) -> int:
    if not a.yes:
        print("WARNING: restore REPLACES the current database with the backup (a safety backup of the current state is taken first).\n"
              "Re-run with --yes to proceed.")
        return 2
    set_db(None)
    out = backup.restore_backup(Path(a.file), confirm=True, overwrite_files=a.overwrite_files)
    print(json.dumps(out, indent=1))
    return 0


def cmd_templates(a) -> int:
    from .excel.templates import generate_all
    out = generate_all(Path(a.out or get_settings().templates_dir), get_db())
    print("\n".join(str(p) for p in out))
    return 0


def cmd_export_workbook(a) -> int:
    from .excel.master import build_master
    p = build_master(Path(a.out), get_db(), a.project)
    print(p)
    return 0


def cmd_verify_workbook(a) -> int:
    from .excel.roundtrip import validate_workbook
    st, vr = validate_workbook(Path(a.file), get_db() if a.project else None, a.project, recalc=not a.no_recalc)
    print(json.dumps({"structure_ok": st.ok, "missing_sheets": st.missing_sheets, "header_problems": st.header_problems,
                      "overwritten_formulas": st.overwritten_formulas[:20], "stale": st.stale,
                      "recalculated": vr.recalculated if vr else None, "formula_errors": vr.errors[:20] if vr else None,
                      "mismatches": vr.mismatches[:20] if vr else None, "formulas": vr.formula_count if vr else None,
                      "notes": vr.notes if vr else None}, indent=1))
    return 0 if st.ok and (vr is None or vr.ok) else 1


def cmd_audit_verify(a) -> int:
    r = audit.verify_chain(get_db())
    print(json.dumps(r))
    return 0 if r["ok"] else 1


def cmd_export_project(a) -> int:
    print(backup.export_project_package(get_db(), a.project))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ksa", description="KSA Construction Estimating Suite")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init", help="create database, load reference data and users")
    s.add_argument("--admin-password")
    s.add_argument("--demo-users", action="store_true", help="also create estimator/procurement/commercial demo logins")
    s.add_argument("--demo-password", default="demo-only-change-me")
    s.set_defaults(fn=cmd_init)
    s = sub.add_parser("create-user")
    s.add_argument("username"); s.add_argument("role"); s.add_argument("--display-name"); s.add_argument("--password"); s.add_argument("--reset", action="store_true")
    s.set_defaults(fn=cmd_create_user)
    s = sub.add_parser("run", help="start the local web application")
    s.add_argument("--host"); s.add_argument("--port", type=int)
    s.set_defaults(fn=cmd_run)
    sub.add_parser("demo", help="create the SYNTHETIC demonstration project").set_defaults(fn=cmd_demo)
    s = sub.add_parser("backup"); s.add_argument("--label"); s.set_defaults(fn=cmd_backup)
    s = sub.add_parser("validate-backup"); s.add_argument("file"); s.set_defaults(fn=cmd_validate_backup)
    s = sub.add_parser("restore"); s.add_argument("file"); s.add_argument("--yes", action="store_true"); s.add_argument("--overwrite-files", action="store_true")
    s.set_defaults(fn=cmd_restore)
    s = sub.add_parser("templates", help="(re)generate templates/*.xlsx and *.docx"); s.add_argument("--out"); s.set_defaults(fn=cmd_templates)
    s = sub.add_parser("export-workbook"); s.add_argument("project"); s.add_argument("--out", required=True); s.set_defaults(fn=cmd_export_workbook)
    s = sub.add_parser("verify-workbook"); s.add_argument("file"); s.add_argument("--project"); s.add_argument("--no-recalc", action="store_true")
    s.set_defaults(fn=cmd_verify_workbook)
    sub.add_parser("audit-verify", help="verify the audit hash chain").set_defaults(fn=cmd_audit_verify)
    s = sub.add_parser("export-project"); s.add_argument("project"); s.set_defaults(fn=cmd_export_project)
    a = p.parse_args(argv)
    logging.basicConfig(level=get_settings().log_level, format="%(levelname)s %(name)s: %(message)s")
    try:
        return a.fn(a)
    except AppError as e:
        print(f"ERROR [{e.code}]: {e.message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
