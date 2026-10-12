"""CLI workflows for workspaces / sources / rates / index, and the non-destructive workspace migration."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import app.config as cfg
from app import cli
from app.database import get_db, set_db
from app.services import projects, workspace_migration, workspaces
from tests.conftest import ESTIMATOR


@pytest.fixture()
def clienv(tmp_path, monkeypatch):
    s = cfg.load_settings(env={})
    s.db_path = tmp_path / "var" / "cli.db"
    s.data_dir = tmp_path / "data"
    s.workspaces_override = tmp_path / "workspaces"
    s.secret_key = "k"
    (tmp_path / "data").mkdir()
    import shutil
    for d in ("taxonomy", "units", "regions", "materials", "labour", "plant", "equipment", "subcontractors", "assumptions", "sources", "assemblies",
              "indirects", "commercial_rules", "suppliers", "productivity", "demo", "public_data"):
        if (cfg.BASE_DIR / "data" / d).exists():
            shutil.copytree(cfg.BASE_DIR / "data" / d, tmp_path / "data" / d)
    cfg.set_settings(s)
    set_db(None)
    monkeypatch.setenv("KSA_CLI_USER", "est")
    monkeypatch.setenv("KSA_CLI_PASSWORD", "pw-est")
    assert cli.main(["init", "--admin-password", "pw12345"]) == 0
    from app.services import auth
    db = get_db()
    auth.create_user(db, "est", "Est", "Estimator", "pw-est")
    auth.create_user(db, "proc", "Proc", "Procurement Reviewer", "pw-proc")
    yield tmp_path
    set_db(None)
    cfg.set_settings(None)


def test_cli_project_create_index_search_refresh(clienv, capsys):
    assert cli.main(["project", "create", "--name", "CLI Office (SYNTHETIC)", "--client", "ACME", "--trades", "HVAC,Electrical", "--demo"]) == 0
    out = capsys.readouterr().out
    assert "Created PRJ-0001" in out and "1. Tender Documents" in out
    root = workspaces.resolve_dir("PRJ-0001", get_db())
    (root / "1. Tender Documents" / "spec_hvac_RevA.txt").write_text("Chilled water pipework shall be insulated.")
    assert cli.main(["project", "index", "PRJ-0001"]) == 0
    capsys.readouterr()
    assert cli.main(["project", "search", "PRJ-0001", "chilled water"]) == 0
    assert "spec_hvac_RevA.txt" in capsys.readouterr().out
    assert cli.main(["project", "refresh", "PRJ-0001"]) == 0
    assert cli.main(["project", "list"]) == 0
    assert "cli-office-synthetic" in capsys.readouterr().out


def test_cli_requires_authenticated_user_for_state_changes(clienv, monkeypatch, capsys):
    monkeypatch.delenv("KSA_CLI_USER")
    assert cli.main(["project", "create", "--name", "x"]) == 1
    assert "--user" in capsys.readouterr().err
    monkeypatch.setenv("KSA_CLI_USER", "est")
    monkeypatch.setenv("KSA_CLI_PASSWORD", "wrong")
    assert cli.main(["project", "create", "--name", "x"]) == 1
    assert get_db().scalar("SELECT COUNT(*) FROM projects") == 0


def test_cli_sources_rates_index_flow(clienv, capsys, monkeypatch):
    db = get_db()
    from app.services.rates import create_resource
    create_resource(db, ESTIMATOR, resource_type="material", description="Ready-mix concrete C30", unit="m3", cost_code="C.01", id="T-MAT-001")
    assert cli.main(["sources", "list"]) == 0
    assert "kapsarc-gastat-cci" in capsys.readouterr().out
    # dry-run refresh must not need credentials, network or write data
    monkeypatch.delenv("KSA_CLI_USER")
    assert cli.main(["sources", "refresh", "--dry-run"]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["dry_run"] and rep["summary"]["new_candidates"] == 0
    monkeypatch.setenv("KSA_CLI_USER", "est")
    assert cli.main(["sources", "status"]) == 0
    capsys.readouterr()
    f = clienv / "rates.csv"
    f.write_text("Resource ID,Description,Unit,Unit Price,Currency,Price Date,VAT,Delivery,Source URL\n"
                 "T-MAT-001,Ready-mix,m3,310.50,SAR,2026-09-15,Excluded,Delivered,https://example.invalid/list\n"
                 "T-MAT-001,Bad,m3,xx,SAR,2026-09-15,Excluded,Delivered,https://example.invalid/list\n")
    assert cli.main(["rates", "validate", str(f), "--source-name", "Test list"]) == 0
    v = json.loads(capsys.readouterr().out)
    assert v["dry_run"] and v["accepted"] == 1 and v["rejected"] == 1 and db.scalar("SELECT COUNT(*) FROM rate_candidates") == 0
    assert cli.main(["rates", "import", str(f), "--source-name", "Test list"]) == 0
    capsys.readouterr()
    assert db.scalar("SELECT COUNT(*) FROM rate_candidates") == 1
    assert cli.main(["rates", "pending"]) == 0
    assert "RC-000001" in capsys.readouterr().out
    monkeypatch.setenv("KSA_CLI_USER", "proc")
    monkeypatch.setenv("KSA_CLI_PASSWORD", "pw-proc")
    assert cli.main(["rates", "review", "RC-000001", "approve", "--comment", "ok"]) == 0
    capsys.readouterr()
    monkeypatch.setenv("KSA_CLI_USER", "est")
    monkeypatch.setenv("KSA_CLI_PASSWORD", "pw-est")
    assert cli.main(["rates", "publish", "RC-000001"]) == 0
    assert "Pending Review" in capsys.readouterr().out
    assert db.scalar("SELECT status FROM resource_rates WHERE resource_id='T-MAT-001'") == "Pending Review"
    cci = Path(cfg.BASE_DIR / "data/public_data/gastat_cci/kapsarc_cci_2026-04.records.json")
    assert cli.main(["index", "import", str(cci), "--dataset", "gastat-cci", "--source", "SRC-002", "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["records"] == 39
    assert cli.main(["index", "import", str(cci), "--dataset", "gastat-cci", "--source", "SRC-002"]) == 0
    capsys.readouterr()
    assert cli.main(["index", "import", str(cci), "--dataset", "gastat-cci", "--source", "SRC-002"]) == 1       # duplicate refused
    assert "ALREADY_IMPORTED" in capsys.readouterr().err


def test_workspace_migration_dry_run_then_copy_without_destroying_legacy_files(clienv, capsys):
    db = get_db()
    s = cfg.get_settings()
    from app.services import auth
    pid = projects.create_project(db, ESTIMATOR, name="Legacy One", id="PRJ-0007")
    # simulate the pre-0007 layout
    (s.projects_dir / pid / "uploads").mkdir(parents=True)
    (s.projects_dir / pid / "uploads" / "boq.csv").write_text("legacy boq")
    (s.outputs_dir / pid).mkdir(parents=True)
    (s.outputs_dir / pid / "estimate_master_PRJ-0007.xlsx").write_bytes(b"xlsx")
    (s.outputs_dir / pid / "pricing_schedule_PRJ-0007_PRELIMINARY.xlsx").write_bytes(b"ps")
    (s.outputs_dir / pid / "RFQ-0001.docx").write_bytes(b"rfq")
    (s.outputs_dir / pid / "misc.txt").write_text("misc")
    root = workspaces.resolve_dir(pid, db)
    before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
    dry = workspace_migration.migrate(db, dry_run=True)
    assert dry["dry_run"] and dry["totals"]["files_planned"] == 5 and sorted(p.relative_to(root).as_posix() for p in root.rglob("*")) == before
    areas = {Path(m["from"]).name: m["area"] for m in dry["projects"][0]["files"]}
    assert areas == {"boq.csv": "3. BOQ & Takeoff", "estimate_master_PRJ-0007.xlsx": "5. Estimate & Cost Build-Up",
                     "pricing_schedule_PRJ-0007_PRELIMINARY.xlsx": "8. Commercial Submission", "RFQ-0001.docx": "6. Procurement & Quotations",
                     "misc.txt": "10. Exports & Archive"}
    (root / "3. BOQ & Takeoff" / "boq.csv").write_text("DIFFERENT existing target")             # must never be overwritten
    rep = workspace_migration.migrate(db, dry_run=False)
    assert not rep["errors"] and rep["backup"]["valid"] and Path(rep["report_file"]).exists()
    assert (root / "3. BOQ & Takeoff" / "boq.csv").read_text() == "DIFFERENT existing target"
    assert any(p.name.startswith("boq.csv.legacy-") for p in (root / "3. BOQ & Takeoff").iterdir())
    assert (root / "5. Estimate & Cost Build-Up" / "estimate_master_PRJ-0007.xlsx").read_bytes() == b"xlsx"
    assert (s.projects_dir / pid / "uploads" / "boq.csv").read_text() == "legacy boq"                # legacy originals untouched
    assert (s.outputs_dir / pid / "misc.txt").exists()
    again = workspace_migration.migrate(db, dry_run=False)
    assert again["totals"]["copied"] == 0                                                           # idempotent
