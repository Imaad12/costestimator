import json
import zipfile
from pathlib import Path

import openpyxl
import pytest

from app.core.errors import Conflict, ValidationFailed
from app.database import Database, get_db, set_db
from app.imports import datasets
from app.services import audit, backup, projects, rates
from app.services.rates import create_resource

from tests.conftest import COMMERCIAL, ESTIMATOR, PROCUREMENT
from tests.helpers import build_mini


# --------------------------------------------------------------------------- backup / restore
@pytest.fixture()
def filedb(tmp_path, settings):
    settings.db_path = tmp_path / "var" / "real.db"
    set_db(None)
    db = get_db()
    from app.services import refdata
    refdata.seed_reference(db)
    return db, settings, tmp_path


def test_backup_validate_restore_cycle(filedb):
    db, s, tmp = filedb
    pid = build_mini(db, tmp)
    up = projects.project_dir(pid, "uploads") / "keep.txt"
    up.write_text("original upload")
    b = backup.create_backup(s, label="t1")
    rep = backup.validate_backup(b)
    assert rep["ok"] and rep["manifest"]["row_counts"]["projects"] == 1 and rep["audit_entries"] > 10
    assert "projects/%s/uploads/keep.txt" % pid in rep["manifest"]["files"]
    with pytest.raises(Conflict):
        backup.create_backup(s, dest=b)                                    # never overwrite a backup
    # destroy data, then restore
    db.execute("DELETE FROM boq_items")
    up.write_text("MODIFIED after backup")
    with pytest.raises(ValidationFailed) as e:
        backup.restore_backup(b, confirm=False, settings=s)               # destructive action needs explicit confirmation
    assert e.value.code == "CONFIRM_REQUIRED"
    out = backup.restore_backup(b, confirm=True, settings=s)
    assert out["safety_backup"] and Path(out["safety_backup"]).exists()   # current state is saved first
    db2 = get_db()
    assert db2.scalar("SELECT COUNT(*) FROM boq_items") == 2 and audit.verify_chain(db2)["ok"]
    assert up.read_text() == "MODIFIED after backup"                       # existing project file NOT silently overwritten
    assert str(up) in out["files_conflicting"] and Path(str(up) + ".restored").read_text() == "original upload"


def test_corrupt_backup_is_rejected_and_nothing_changes(filedb):
    db, s, tmp = filedb
    build_mini(db, tmp)
    b = backup.create_backup(s)
    bad = tmp / "bad.zip"
    with zipfile.ZipFile(b) as z, zipfile.ZipFile(bad, "w") as o:
        for n in z.namelist():
            data = z.read(n)
            if n == "ksa_estimator.db":
                data = data[:-200] + b"\x00" * 200
            o.writestr(n, data)
    rep = backup.validate_backup(bad)
    assert not rep["ok"] and any("Hash mismatch" in p or "integrity" in p for p in rep["problems"])
    with pytest.raises(ValidationFailed) as e:
        backup.restore_backup(bad, confirm=True, settings=s)
    assert e.value.code == "BACKUP_INVALID"
    assert get_db().scalar("SELECT COUNT(*) FROM projects") == 1
    notzip = tmp / "x.zip"
    notzip.write_text("nope")
    assert not backup.validate_backup(notzip)["ok"] and not backup.validate_backup(tmp / "missing.zip")["ok"]


def test_backup_with_tampered_audit_chain_flagged(filedb):
    db, s, tmp = filedb
    build_mini(db, tmp)
    db.execute("UPDATE audit_log SET comment='edited' WHERE id=(SELECT MIN(id) FROM audit_log)")
    rep = backup.validate_backup(backup.create_backup(s))
    assert not rep["ok"] and any("Audit chain" in p for p in rep["problems"])


def test_project_package_and_archive(filedb):
    db, s, tmp = filedb
    pid = build_mini(db, tmp)
    z = backup.export_project_package(db, pid, settings=s)
    with zipfile.ZipFile(z) as zf:
        data = json.loads(zf.read("project_data.json"))
        assert len(data["boq_items"]) == 2 and data["project"][0]["id"] == pid and "manifest.json" in zf.namelist()
    with pytest.raises(Exception):
        projects.archive_project(db, ESTIMATOR, pid, "done")                 # archiving needs a Commercial Approver / Administrator
    projects.archive_project(db, COMMERCIAL, pid, "tender closed")
    assert projects.get_project(db, pid)["status"] == "Archived"
    from app.imports import boq as bi
    from tests.helpers import write_boq
    with pytest.raises(Conflict):
        bi.import_boq(db, ESTIMATOR, pid, write_boq(tmp / "n.csv", [("9", "x", "m", "1", "", "")]))


# --------------------------------------------------------------------------- dataset ingestion
def make_dataset(path, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Rate Dataset"
    ws.append(["Resource ID", "Description", "Unit", "Unit price", "Currency", "Rate type", "Region", "Price date", "Valid until", "Source ID", "Supplier ID", "Tax basis", "Delivery basis", "Evidence"])
    for r in rows:
        ws.append(r)
    wb.save(path)
    return path


def test_dataset_staging_validation_and_publication(seeded, tmp_path):
    db = seeded
    approved_before = db.scalar("SELECT COUNT(*) FROM resource_rates WHERE status='Approved'")
    create_resource(db, ESTIMATOR, resource_type="material", description="Cable", unit="m", id="DS-1", is_synthetic=True)
    from tests.helpers import approved_rate
    approved_rate(db, "DS-1", "10")
    rows = [
        ["DS-1", None, "m", 10.5, "SAR", "Published Market Price", "KSA-ALL", "2026-10-01", None, "SRC-001", None, "excl VAT", "ex-works", "catalogue"],     # ok
        ["DS-1", None, "m", 99, "SAR", "Published Market Price", "KSA-ALL", "2026-10-01", None, "SRC-001", None, None, None, None],                           # conflict with row 1
        ["NOPE", None, "m", 5, "SAR", "Published Market Price", "KSA-ALL", "2026-10-01", None, "SRC-001", None, None, None, None],                            # unknown resource
        ["DS-1", None, "kg", 5, "SAR", "Published Market Price", "KSA-ALL", "2026-10-02", None, "SRC-001", None, None, None, None],                           # incompatible unit
        ["DS-1", None, "m", "abc", "SAR", "Published Market Price", "KSA-ALL", "2026-10-03", None, "SRC-001", None, None, None, None],                         # bad price
        ["DS-1", None, "m", 5, "XYZ", "Published Market Price", "KSA-ALL", "2026-10-04", None, "SRC-001", None, None, None, None],                             # currency
        ["DS-1", None, "m", 5, "SAR", "Published Market Price", "KSA-ALL", "2026-10-05", None, None, None, None, None, None],                                  # missing source
        ["DS-1", None, "m", 5, "SAR", "Made-Up Type", "KSA-ALL", "2026-10-06", None, None, None, None, None, None],                                            # invalid status/type
        ["DS-1", None, "m", 5, "SAR", "Published Market Price", "KSA-ALL", "2020-01-01", None, "SRC-001", None, None, None, None],                             # stale
        ["DS-1", None, "m", 40, "SAR", "Published Market Price", "KSA-ALL", "2026-10-07", None, "SRC-001", None, None, None, None],                            # unusual change (+300%)
        ["DS-1", None, "", 5, "SAR", "Published Market Price", "KSA-ALL", "2026-10-08", None, "SRC-001", None, None, None, None],                              # missing unit
        ["DS-1", None, "m", 5, "SAR", "Published Market Price", "MARS", "2026-10-09", None, "SRC-001", None, None, None, None],                                # bad region
    ]
    res = datasets.stage_rate_dataset(db, ESTIMATOR, make_dataset(tmp_path / "d.xlsx", rows))
    assert res["rows"] == 12
    ic = res["issue_counts"]
    for code in ("CONFLICT", "UNKNOWN_RESOURCE", "UNIT_INCOMPATIBLE", "INVALID_PRICE", "CURRENCY_UNSUPPORTED", "SOURCE_MISSING", "RATE_TYPE_INVALID", "STALE", "UNUSUAL_CHANGE", "UNIT_MISSING", "REGION_INVALID"):
        assert ic.get(code, 0) >= 1, code
    staged = datasets.staged_rows(db, res["dataset_id"])
    assert db.scalar("SELECT COUNT(*) FROM resource_rates WHERE unit_price='10.5'") == 0          # nothing written to the rate table yet
    assert staged[1]["blocking"] and "CONFLICT" in [i["code"] for i in staged[1]["issues"]]
    with pytest.raises(ValidationFailed):
        datasets.decide_rows(db, ESTIMATOR, res["dataset_id"], [staged[2]["id"]], "Accept")          # blocking rows cannot be accepted
    ok_row = staged[0]
    assert not ok_row["blocking"]
    datasets.decide_rows(db, ESTIMATOR, res["dataset_id"], [ok_row["id"]], "Accept")
    from app.core.errors import PermissionDenied
    with pytest.raises(PermissionDenied):
        datasets.publish_dataset(db, ESTIMATOR, res["dataset_id"])
    out = datasets.publish_dataset(db, PROCUREMENT, res["dataset_id"])
    assert out["published"] == 1 and out["changes"][0]["old"] == "10" and out["changes"][0]["new"] == "10.5"
    r = rates.get_rate(db, out["changes"][0]["rate_id"])
    assert r["status"] == "Pending Review" and r["source_id"] == "SRC-001" and "Dataset" in r["evidence"]       # never auto-approved
    assert db.scalar("SELECT COUNT(*) FROM resource_rates WHERE status='Approved'") == approved_before + 1      # only the pre-existing DS-1 rate
    assert list((tmp_path / "projects" / "_datasets").glob("*d.xlsx"))                                             # original dataset file retained
    with pytest.raises(ValidationFailed):
        datasets.publish_dataset(db, PROCUREMENT, res["dataset_id"])                                               # not twice


def test_dataset_csv_and_json_and_foreign_benchmark(seeded, tmp_path):
    db = seeded
    create_resource(db, ESTIMATOR, resource_type="material", description="Steel", unit="t", id="DS-2", is_synthetic=True)
    c = tmp_path / "d.csv"
    c.write_text("resource_id,unit,unit_price,currency,rate_type,price_date,source_id\nDS-2,t,650,USD,Official Index or Benchmark,2026-09-01,SRC-002\nDS-2,t,800,USD,Published Market Price,2026-09-01,SRC-002\n")
    r = datasets.stage_rate_dataset(db, ESTIMATOR, c)
    codes = {i["code"] for row in datasets.staged_rows(db, r["dataset_id"]) for i in row["issues"]}
    assert {"INDEX_NOT_PRICE", "FOREIGN_CURRENCY"} <= codes                      # original currency and benchmark status preserved, never converted
    assert db.one("SELECT currency FROM rate_staging WHERE dataset_id=? AND row_no=2", (r["dataset_id"],))["currency"] == "USD"
    j = tmp_path / "d.json"
    j.write_text(json.dumps([{"resource_id": "DS-2", "unit": "t", "unit_price": 3100, "currency": "SAR", "rate_type": "Published Market Price", "price_date": "2026-09-02", "source_id": "SRC-002"}]))
    assert datasets.stage_rate_dataset(db, ESTIMATOR, j)["rows"] == 1


# --------------------------------------------------------------------------- historical analytics
def test_actuals_need_a_source_and_variance_uses_only_entered_data(seeded, tmp_path):
    from app.reporting import history
    db = seeded
    pid = build_mini(db, tmp_path)
    with pytest.raises(ValidationFailed) as e:
        history.record_actual(db, ESTIMATOR, pid, source="", cost_code="C.01", actual_amount="100")
    assert e.value.code == "SOURCE_REQUIRED"
    with pytest.raises(ValidationFailed):
        history.record_actual(db, ESTIMATOR, pid, source="ledger", cost_code="C.01")             # nothing to record
    df = history.estimate_vs_actual(db, pid)
    assert list(df["cost_code"]) == ["(unassigned)"] and df["actual"].isna().all()                # no actuals => no invented variance
    db.execute("UPDATE boq_items SET cost_code='C.01' WHERE project_id=?", (pid,))
    history.record_actual(db, ESTIMATOR, pid, source="GL-001", cost_code="C.01", actual_amount="2000")
    df = history.estimate_vs_actual(db, pid)
    row = df[df.cost_code == "C.01"].iloc[0]
    assert row.estimated == 1875.0 and row.actual == 2000.0 and row.variance == 125.0 and round(row.variance_pct, 2) == 6.67
    history.record_actual(db, ESTIMATOR, pid, source="timesheet", resource_id="DEMO-LAB-001", actual_hours="35")
    pv = history.productivity_variance(db, pid)
    assert float(pv.estimated_hours.iloc[0]) == 30.0 and float(pv.variance_hours.iloc[0]) == 5.0
    ch = history.rate_changes(db, "DEMO-MAT-001")
    assert len(ch) == 1 and ch.change_pct.isna().all()


# --------------------------------------------------------------------------- CLI
def test_cli_init_demo_templates_backup(tmp_path, monkeypatch, capsys):
    import app.config as cfg
    from app import cli
    s = cfg.load_settings(env={})
    s.db_path = tmp_path / "var" / "cli.db"
    s.data_dir = cfg.BASE_DIR / "data"
    s.__class__.projects_dir = property(lambda self: tmp_path / "projects")
    s.__class__.outputs_dir = property(lambda self: tmp_path / "outputs")
    s.__class__.backups_dir = property(lambda self: tmp_path / "backups")
    s.secret_key = "k"
    cfg.set_settings(s)
    set_db(None)
    assert cli.main(["init", "--admin-password", "pw12345", "--demo-users"]) == 0
    assert cli.main(["demo"]) == 0
    assert cli.main(["demo"]) == 0                                                        # idempotent
    assert cli.main(["templates", "--out", str(tmp_path / "tpl")]) == 0
    assert (tmp_path / "tpl" / "estimate_master.xlsx").exists()
    assert cli.main(["backup", "--label", "cli"]) == 0
    assert cli.main(["audit-verify"]) == 0
    assert cli.main(["export-workbook", "PRJ-0001", "--out", str(tmp_path / "wb.xlsx")]) == 0
    assert cli.main(["verify-workbook", str(tmp_path / "wb.xlsx"), "--project", "PRJ-0001", "--no-recalc"]) == 0
    assert cli.main(["restore", str(next((tmp_path / "backups").glob("*.zip")))]) == 2   # refuses without --yes
    out = capsys.readouterr().out
    assert "Created user 'admin'" in out and "SYNTHETIC" in out and "WARNING" in out
    db = get_db()
    assert db.one("SELECT is_ai, password_hash FROM users WHERE username='ai-assistant'")["password_hash"] is None
    set_db(None)
    cfg.set_settings(None)
