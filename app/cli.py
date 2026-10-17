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
                auth.create_user(db, u, n, r, a.demo_password, actor_type="test")        # published demo credentials: never a production approver
        print(f"Demo users created ({', '.join(u for u, _, _ in DEMO_USERS)}) with password '{a.demo_password}'. "
              "LOCAL DEMO ONLY - change or remove for any real use.")
    return 0


def cmd_superuser(a) -> int:
    """Development convenience: ONE Administrator login for tuning the application. It is a 'test' principal, so nothing it approves can make an export submission-ready.
    The password is generated (or given with --password / KSA_SUPERUSER_PASSWORD) and shown once. Whether it may approve its own work is NOT decided here: that stays off
    unless whoever starts the server sets KSA_ALLOW_SELF_APPROVAL=true."""
    db = get_db()
    pw = a.password or os.environ.get("KSA_SUPERUSER_PASSWORD") or secrets.token_urlsafe(10)
    who = f"cli:{getpass.getuser()}"
    if db.one("SELECT 1 FROM users WHERE username='superuser'"):
        if not (a.password or os.environ.get("KSA_SUPERUSER_PASSWORD") or a.reset):
            print("User 'superuser' already exists (use --reset to set a new password).")
            return 0
        db.update("users", {"password_hash": auth.hash_password(pw), "role": "Administrator", "is_active": 1, "actor_type": "test"}, "username='superuser'")
        audit.log(db, who, "user", "superuser", "password_reset")
        print("Superuser password reset.")
    else:
        auth.create_user(db, "superuser", "Super User (development)", "Administrator", pw, creator=who, actor_type="test")
        print("Created user 'superuser'.")
    print(f"Sign in as  superuser  /  {pw}      (shown once; development only - replace with real users before any real use)")
    return 0


def cmd_create_user(a) -> int:
    db = get_db()
    pw = a.password or getpass.getpass("Password: ")
    who = f"cli:{getpass.getuser()}"                    # the CLI is a shell-access tool, not an authenticated session: record which operating-system user ran it
    if a.reset and db.one("SELECT 1 FROM users WHERE username=?", (a.username,)):
        db.update("users", {"password_hash": auth.hash_password(pw)}, "username=?", (a.username,))
        audit.log(db, who, "user", a.username, "password_reset")
        print("Password reset.")
    else:
        auth.create_user(db, a.username, a.display_name or a.username, a.role, pw, creator=who, actor_type=a.actor_type)
        print("User created.")
    return 0


def cmd_run(a) -> int:
    import uvicorn
    s = get_settings()
    get_db()
    host = a.host or s.host
    tls = bool(a.ssl_certfile and a.ssl_keyfile)
    if bool(a.ssl_certfile) != bool(a.ssl_keyfile):
        print("ERROR: --ssl-certfile and --ssl-keyfile must be given together.", file=sys.stderr)
        return 2
    if host not in ("127.0.0.1", "localhost", "::1") and not tls and not a.allow_insecure_network:
        print(f"ERROR: refusing to listen on {host} without TLS. Use --ssl-certfile/--ssl-keyfile (or terminate TLS at a reverse proxy and pass --allow-insecure-network "
              "to confirm). See docs/SECURITY.md.", file=sys.stderr)
        return 2
    if tls:
        s.tls = True
        os.environ["KSA_TLS"] = "1"
    uvicorn.run("app.main:app", host=host, port=a.port or s.port, log_level=s.log_level.lower(),
                ssl_certfile=a.ssl_certfile if tls else None, ssl_keyfile=a.ssl_keyfile if tls else None)
    return 0


def cmd_report(a) -> int:
    from .api.serializers import ser
    from .reporting import registry
    db = get_db()
    if a.project == "list":
        for r in registry.listing():
            print(f"{r['name']:18} {r['group']:22} {r['label']}  params: {', '.join(p['name'] for p in r['params']) or '-'}")
        return 0
    params = dict(kv.split("=", 1) for kv in (a.param or []))
    res = registry.run_report(db, a.name, a.project, params)
    if a.save:
        from .services import analysis
        rid = analysis.save_run(db, _actor(a), a.project, a.name, params, res, inputs_hash=analysis.digest(res))
        print(f"Saved analysis run #{rid}", file=sys.stderr)
    _print(ser(res))
    return 0


def cmd_action(a) -> int:
    """Run any registered action as a real user (same registry and server-side checks as the REST API and the UI)."""
    from .api import actions
    from .api.serializers import ser
    params = json.loads(Path(a.params[1:]).read_text(encoding="utf-8")) if a.params.startswith("@") else json.loads(a.params)
    _print(ser(actions.run(get_db(), _actor(a), a.name, params)))
    return 0


def cmd_standards(a) -> int:
    from .services import standards
    db = get_db()
    if a.stcmd == "list":
        _print(standards.list_standards(db, a.status))
    elif a.stcmd == "acquire":
        _print(standards.acquisition_list(db))
    elif a.stcmd == "import":
        _print(standards.import_register(db, Path(a.file), created_by=_actor(a).username, dry_run=a.dry_run, update=a.update))
    return 0


def cmd_param(a) -> int:
    from .services import governed
    db = get_db()
    if a.pcmd3 == "kinds":
        _print(governed.kinds())
    elif a.pcmd3 == "list":
        _print(governed.list_params(db, a.kind, a.project))
    elif a.pcmd3 == "propose":
        data = json.loads(Path(a.data[1:]).read_text(encoding="utf-8")) if a.data.startswith("@") else json.loads(a.data)
        print(governed.propose(db, _actor(a), a.kind, a.code, data, project_id=a.project, source=a.source, basis_note=a.basis, submit=a.submit))
    elif a.pcmd3 == "import":
        _print(governed.import_csv(db, _actor(a), a.file, project_id=a.project, dry_run=a.dry_run))
    elif a.pcmd3 == "submit":
        governed.submit(db, _actor(a), a.param_id)
    elif a.pcmd3 == "approve":
        governed.approve(db, _actor(a), a.param_id, comments=a.comment)
    elif a.pcmd3 == "reject":
        governed.reject(db, _actor(a), a.param_id, comments=a.comment or "")
    return 0


def cmd_wbs(a) -> int:
    from .services import wbs
    _print(wbs.import_csv(get_db(), _actor(a), a.project, Path(a.file)))
    return 0


def cmd_profile(a) -> int:
    from .services import profiles
    db = get_db()
    if a.prcmd == "create":
        reqs = profiles.import_requirements_csv(Path(a.requirements)) if a.requirements else []
        docs = json.loads(Path(a.documents[1:]).read_text(encoding="utf-8")) if a.documents and a.documents.startswith("@") else (json.loads(a.documents) if a.documents else [])
        print(profiles.create_profile(db, _actor(a), a.code, a.name, client=a.client, source_documents=docs, requirements=reqs))
    elif a.prcmd == "submit":
        profiles.submit_profile(db, _actor(a), a.profile_id)
    elif a.prcmd == "approve":
        profiles.approve_profile(db, _actor(a), a.profile_id, a.comment)
    elif a.prcmd == "link":
        profiles.link_project(db, _actor(a), a.project, a.code)
    elif a.prcmd == "attest":
        print(profiles.attest(db, _actor(a), a.project, a.req_id, a.status, a.evidence))
    return 0


def cmd_mto(a) -> int:
    from .api.serializers import ser
    from .services import mto
    db = get_db()
    if a.mcmd == "templates":
        for t in sorted(mto.templates().values(), key=lambda t: t["code"]):
            print(f"{t['code']:30} driver={t['driver_unit']:9} slots={len(t['slots']):2}  {t['name']}")
    elif a.mcmd == "preview":
        _print(ser(mto.preview(db, a.project, a.item, a.template, a.driver_qty, a.driver_source, a.skip)))
    elif a.mcmd == "apply":
        _print(ser(mto.apply(db, _actor(a), a.project, a.item, a.template, a.driver_qty, a.driver_source, a.skip)))
    return 0


def cmd_unlock(a) -> int:
    n = auth.unlock_user(get_db(), _actor(a), a.username)
    print(f"Cleared {n} failed attempt(s) for {a.username}.")
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


def cmd_coverage(a) -> int:
    from .reporting.coverage import library_coverage
    cov = library_coverage(get_db())
    print(json.dumps(cov, indent=1, default=str))
    if not cov["totals"]["resources"]:
        print("NOTE: the library is empty - this database has not been initialised. Run `python -m app.cli init`.", file=sys.stderr)
    return 0


def cmd_export_project(a) -> int:
    print(backup.export_project_package(get_db(), a.project))
    return 0


# ------------------------------------------------------------------------------------------------ authenticated actor
def _actor(a) -> Actor:
    """State-changing CLI commands act as a real, authenticated human user (same roles and server-side checks as the web app)."""
    user = getattr(a, "user", None) or os.environ.get("KSA_CLI_USER")
    if not user:
        raise AppError("State-changing commands need --user (or KSA_CLI_USER); the password is read from KSA_CLI_PASSWORD or prompted.")
    pw = os.environ.get("KSA_CLI_PASSWORD") or getpass.getpass(f"Password for {user}: ")
    return auth.authenticate(get_db(), user, pw)


def _print(obj) -> None:
    print(json.dumps(obj, indent=1, default=str, ensure_ascii=False))


# ------------------------------------------------------------------------------------------------ projects / workspaces
def cmd_project(a) -> int:
    from .services import project_index, projects, snapshots, workspaces
    db = get_db()
    act = a.pcmd
    if act == "list":
        for p in projects.list_projects(db, include_archived=True):
            print(f"{p['id']}  {p['status']:9} {p['name']}  -> projects/{p.get('workspace_path') or '(no workspace yet)'}")
        return 0
    if act == "create":
        pid = projects.create_project(db, _actor(a), name=a.name, client=a.client or "", location=a.location or "", tender_ref=a.tender_ref or "",
                                      project_type=a.project_type or "", trades=[t.strip() for t in (a.trades or "").split(",") if t.strip()],
                                      design_stage=a.design_stage or "", is_demo=a.demo, id=a.id)
        root = workspaces.resolve_dir(pid, db)
        print(f"Created {pid}\nWorkspace: {root}\nNext: copy tender documents into '1. Tender Documents/', run `python -m app.cli project index {pid}`, "
              f"then import the BOQ (web app > project > BOQ, or `POST /api/projects/{pid}/boq/import`).")
        return 0
    if act == "refresh":
        print(workspaces.ensure_workspace(db, a.project))
        return 0
    if act == "import-boq":
        from .imports import boq as boq_import
        r = boq_import.import_boq(db, _actor(a), a.project, Path(a.file), revision=a.revision)       # auto-detected column mapping; rejects if ambiguous
        _print(r)
        return 0
    if act == "index":
        r = project_index.index_project(db, _actor(a), a.project)
        _print({k: v for k, v in r.items() if k != "changes"} | {"changes": r["changes"][:50]})
        return 0
    if act == "search":
        _print(project_index.search(db, a.project, a.query))
        return 0
    if act == "verify-snapshot":
        _print({"verify": snapshots.verify_snapshot(db, a.version_id), "replay_direct_cost": snapshots.replay_direct_cost(db, a.version_id),
                "replay_estimate": snapshots.replay_estimate(db, a.version_id)})
        return 0
    return 2


def cmd_migrate_workspaces(a) -> int:
    from .services import workspace_migration
    rep = workspace_migration.migrate(get_db(), dry_run=a.dry_run)
    _print(rep)
    return 0 if not rep.get("errors") else 1


# ------------------------------------------------------------------------------------------------ sources / rates / index
def cmd_sources(a) -> int:
    from .rate_updates import refresh
    db = get_db()
    if a.scmd == "list":
        for s in refresh.list_sources(db):
            print(f"{s['id']:22} {s['status']:12} auto={'yes' if s['automated_access'] else 'no ':3} {s['produces']:28} {s['name']}")
        return 0
    if a.scmd == "status":
        _print(refresh.status_report(db))
        return 0
    if a.scmd == "refresh":
        actor = Actor("system:refresh", "Estimator", "Scheduled source refresh (proposals only)") if a.dry_run else _actor(a)
        rep = refresh.refresh_sources(db, actor, provider_ids=a.provider or None, dry_run=a.dry_run)
        _print(rep)
        return 0
    return 2


def cmd_rates(a) -> int:
    from .rate_updates import candidates, importer
    db = get_db()
    if a.rcmd in ("import", "validate"):
        dry = a.dry_run or a.rcmd == "validate"
        actor = _actor(a)
        rep = importer.import_rates_file(db, actor, Path(a.file), source_id=a.source, source_name=a.source_name, source_url=a.url,
                                         source_type=a.source_type, description=a.description or "", dry_run=dry, retrieved_at=a.retrieved,
                                         extra_flags=(["AWARD_NOT_MARKET_QUOTE"] if a.source_type == "Public tender award" else []) + (["SYNTHETIC_DATA"] if a.synthetic else []) or None)
        _print(rep)
        return 0 if not rep["errors"] or rep["accepted"] else 1
    if a.rcmd == "pending":
        rows = candidates.list_queue(db, queue=a.queue)
        for r in rows:
            print(f"{r['candidate_ref']}  {r['queue']:22} {r['status']:24} {str(r['resource_id'] or r['suggested_resource_id'] or '?'):14} "
                  f"{r['original_price'] or '-':>10} {r['original_currency'] or '':3}/{r['original_unit'] or '?':4} {r['source_name'] or ''} [{','.join(r['flags'])}]")
        print(f"{len(rows)} open candidate(s)."); _print(candidates.queue_counts(db))
        return 0
    if a.rcmd == "review":
        actor = _actor(a)
        _print(candidates.review(db, actor, a.candidate, a.decision, a.comment or ""))
        return 0
    if a.rcmd == "publish":
        rid = candidates.publish(db, _actor(a), a.candidate)
        print(f"Published as global rate version id {rid} (status Pending Review). It is NOT usable in a final estimate until a human approves the rate.")
        return 0
    return 2


def cmd_pack(a) -> int:
    from .services import refdata
    db = get_db()
    if a.pcmd2 == "list":
        for p_ in refdata.list_packs(db):
            print(f"{p_['name']:14} loaded={p_['loaded']!s:5} codes={p_['cost_codes']} resources={p_['resources']}  {p_['description']}")
        return 0
    _print(refdata.load_pack(db, _actor(a), a.name))
    return 0


def cmd_index(a) -> int:
    from .rate_updates import index_import
    db = get_db()
    if a.icmd == "import":
        _print(index_import.import_index_file(db, _actor(a), Path(a.file), dataset=a.dataset, source_id=a.source, source_name=a.source_name or a.dataset,
                                             source_url=a.url, description=a.description or "", dry_run=a.dry_run))
        return 0
    if a.icmd == "list":
        for o in index_import.latest_observations(db, a.dataset)[-60:]:
            print(f"{o['dataset']:12} {o['period']} {o['series']:60} {o['value']}")
        return 0
    return 2


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
    s.add_argument("--actor-type", choices=["human", "test"], default="human", help="'test' principals can never satisfy a production approval")
    s.set_defaults(fn=cmd_create_user)
    s = sub.add_parser("superuser", help="create (or --reset) the single development 'superuser' Administrator (a test principal; password shown once)")
    s.add_argument("--password"); s.add_argument("--reset", action="store_true"); s.set_defaults(fn=cmd_superuser)
    s = sub.add_parser("run", help="start the local web application")
    s.add_argument("--host"); s.add_argument("--port", type=int)
    s.add_argument("--ssl-certfile", help="serve over TLS (with --ssl-keyfile)"); s.add_argument("--ssl-keyfile")
    s.add_argument("--allow-insecure-network", action="store_true", help="confirm that TLS is terminated elsewhere when binding a non-loopback address")
    s.set_defaults(fn=cmd_run)
    s = sub.add_parser("report", help="run a registered project report / analysis (use 'report list x y' to list)")
    s.add_argument("project"); s.add_argument("name"); s.add_argument("--param", action="append", help="name=value"); s.add_argument("--save", action="store_true"); s.add_argument("--user")
    s.set_defaults(fn=cmd_report)
    s = sub.add_parser("action", help="run a registered action as a real user: action NAME 'JSON' | @file.json  (see /api/actions)")
    s.add_argument("name"); s.add_argument("params"); s.add_argument("--user"); s.set_defaults(fn=cmd_action)
    s = sub.add_parser("standards", help="standards / source register: list | acquire (what a person must still obtain) | import FILE")
    st_ = s.add_subparsers(dest="stcmd", required=True)
    q = st_.add_parser("list"); q.add_argument("--status"); q.set_defaults(fn=cmd_standards)
    st_.add_parser("acquire").set_defaults(fn=cmd_standards)
    q = st_.add_parser("import"); q.add_argument("file"); q.add_argument("--dry-run", action="store_true"); q.add_argument("--update", action="store_true", help="update existing rows whose content changed (audited)"); q.add_argument("--user"); q.set_defaults(fn=cmd_standards)
    s = sub.add_parser("param", help="governed parameters: kinds / list / propose / submit / approve / reject")
    ps_ = s.add_subparsers(dest="pcmd3", required=True)
    ps_.add_parser("kinds").set_defaults(fn=cmd_param)
    q = ps_.add_parser("list"); q.add_argument("--kind"); q.add_argument("--project"); q.set_defaults(fn=cmd_param)
    q = ps_.add_parser("propose"); q.add_argument("kind"); q.add_argument("code"); q.add_argument("data", help="JSON text or @file.json"); q.add_argument("--project")
    q.add_argument("--source", required=True); q.add_argument("--basis"); q.add_argument("--submit", action="store_true"); q.add_argument("--user"); q.set_defaults(fn=cmd_param)
    q = ps_.add_parser("import", help="load proposals from CSV as Drafts (never approves)"); q.add_argument("file"); q.add_argument("--project"); q.add_argument("--dry-run", action="store_true"); q.add_argument("--user"); q.set_defaults(fn=cmd_param)
    for n in ("submit", "approve", "reject"):
        q = ps_.add_parser(n); q.add_argument("param_id", type=int); q.add_argument("--comment"); q.add_argument("--user"); q.set_defaults(fn=cmd_param)
    s = sub.add_parser("wbs", help="import WBS nodes or item->WBS assignments from CSV"); s.add_argument("project"); s.add_argument("file"); s.add_argument("--user"); s.set_defaults(fn=cmd_wbs)
    s = sub.add_parser("profile", help="client/owner profile: create / submit / approve / link / attest")
    pr_ = s.add_subparsers(dest="prcmd", required=True)
    q = pr_.add_parser("create"); q.add_argument("code"); q.add_argument("name"); q.add_argument("--client"); q.add_argument("--requirements", help="CSV: req_id,category,title,source_ref[,mandatory][,fact,op,value]")
    q.add_argument("--documents", help="JSON list or @file.json of source documents"); q.add_argument("--user"); q.set_defaults(fn=cmd_profile)
    for n in ("submit", "approve"):
        q = pr_.add_parser(n); q.add_argument("profile_id", type=int); q.add_argument("--comment"); q.add_argument("--user"); q.set_defaults(fn=cmd_profile)
    q = pr_.add_parser("link"); q.add_argument("project"); q.add_argument("code"); q.add_argument("--user"); q.set_defaults(fn=cmd_profile)
    q = pr_.add_parser("attest"); q.add_argument("project"); q.add_argument("req_id"); q.add_argument("status"); q.add_argument("evidence"); q.add_argument("--user"); q.set_defaults(fn=cmd_profile)
    s = sub.add_parser("mto", help="take-off derivation templates: templates / preview / apply")
    mt_ = s.add_subparsers(dest="mcmd", required=True)
    mt_.add_parser("templates").set_defaults(fn=cmd_mto)
    for n in ("preview", "apply"):
        q = mt_.add_parser(n); q.add_argument("project"); q.add_argument("item"); q.add_argument("template"); q.add_argument("--driver-qty"); q.add_argument("--driver-source")
        q.add_argument("--skip", action="append"); q.add_argument("--user"); q.set_defaults(fn=cmd_mto)
    s = sub.add_parser("unlock-user", help="clear the failed-sign-in lock of a user (administrator)"); s.add_argument("username"); s.add_argument("--user")
    s.set_defaults(fn=cmd_unlock)
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
    sub.add_parser("coverage", help="measured rate-library coverage (counts only)").set_defaults(fn=cmd_coverage)
    s = sub.add_parser("export-project"); s.add_argument("project"); s.set_defaults(fn=cmd_export_project)
    s = sub.add_parser("project", help="numbered project workspaces: list/create/refresh/index/search/verify-snapshot")
    ps = s.add_subparsers(dest="pcmd", required=True)
    ps.add_parser("list").set_defaults(fn=cmd_project)
    q = ps.add_parser("create"); q.add_argument("--name", required=True); q.add_argument("--client"); q.add_argument("--location"); q.add_argument("--tender-ref")
    q.add_argument("--project-type"); q.add_argument("--trades", help="comma-separated"); q.add_argument("--design-stage"); q.add_argument("--id"); q.add_argument("--demo", action="store_true")
    q.add_argument("--user"); q.set_defaults(fn=cmd_project)
    q = ps.add_parser("import-boq", help="import a human-measured BOQ file (copied into '3. BOQ & Takeoff')"); q.add_argument("project"); q.add_argument("file")
    q.add_argument("--revision"); q.add_argument("--user"); q.set_defaults(fn=cmd_project)
    for n in ("refresh", "index"):
        q = ps.add_parser(n); q.add_argument("project"); q.add_argument("--user"); q.set_defaults(fn=cmd_project)
    q = ps.add_parser("search"); q.add_argument("project"); q.add_argument("query"); q.set_defaults(fn=cmd_project)
    q = ps.add_parser("verify-snapshot"); q.add_argument("version_id", type=int); q.set_defaults(fn=cmd_project)
    s = sub.add_parser("migrate-workspaces", help="copy legacy data/projects + data/outputs files into numbered workspaces (non-destructive)")
    s.add_argument("--dry-run", action="store_true"); s.set_defaults(fn=cmd_migrate_workspaces)
    s = sub.add_parser("sources", help="public-source providers: list / status / refresh")
    ss = s.add_subparsers(dest="scmd", required=True)
    ss.add_parser("list").set_defaults(fn=cmd_sources)
    ss.add_parser("status").set_defaults(fn=cmd_sources)
    q = ss.add_parser("refresh"); q.add_argument("--dry-run", action="store_true"); q.add_argument("--provider", action="append"); q.add_argument("--user")
    q.set_defaults(fn=cmd_sources)
    s = sub.add_parser("rates", help="rate candidates: import / validate / pending / review / publish")
    rs = s.add_subparsers(dest="rcmd", required=True)
    for n in ("import", "validate"):
        q = rs.add_parser(n); q.add_argument("file"); q.add_argument("--source", help="Source Register id, e.g. SRC-006"); q.add_argument("--source-name")
        q.add_argument("--url"); q.add_argument("--source-type", default="Manual dataset"); q.add_argument("--description"); q.add_argument("--retrieved")
        q.add_argument("--dry-run", action="store_true"); q.add_argument("--user"); q.add_argument("--synthetic", action="store_true", help="label every candidate SYNTHETIC; published as a Synthetic Demonstration Rate")
        q.set_defaults(fn=cmd_rates)
    q = rs.add_parser("pending"); q.add_argument("--queue"); q.set_defaults(fn=cmd_rates)
    q = rs.add_parser("review"); q.add_argument("candidate"); q.add_argument("decision", choices=["approve", "reject", "needs_verification"])
    q.add_argument("--comment"); q.add_argument("--user"); q.set_defaults(fn=cmd_rates)
    q = rs.add_parser("publish"); q.add_argument("candidate"); q.add_argument("--user"); q.set_defaults(fn=cmd_rates)
    s = sub.add_parser("pack", help="optional definitions-only packs (no prices): list / load")
    pks = s.add_subparsers(dest="pcmd2", required=True)
    pks.add_parser("list").set_defaults(fn=cmd_pack)
    q = pks.add_parser("load"); q.add_argument("name"); q.add_argument("--user"); q.set_defaults(fn=cmd_pack)
    s = sub.add_parser("index", help="official index series (e.g. GASTAT CCI): import / list")
    isub = s.add_subparsers(dest="icmd", required=True)
    q = isub.add_parser("import"); q.add_argument("file"); q.add_argument("--dataset", required=True); q.add_argument("--source"); q.add_argument("--source-name")
    q.add_argument("--url"); q.add_argument("--description"); q.add_argument("--dry-run", action="store_true"); q.add_argument("--user"); q.set_defaults(fn=cmd_index)
    q = isub.add_parser("list"); q.add_argument("--dataset"); q.set_defaults(fn=cmd_index)
    a = p.parse_args(argv)
    logging.basicConfig(level=get_settings().log_level, format="%(levelname)s %(name)s: %(message)s")
    try:
        return a.fn(a)
    except AppError as e:
        print(f"ERROR [{e.code}]: {e.message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
