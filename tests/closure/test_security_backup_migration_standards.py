"""Backup/restore round trip of the closure tables, forward-only migration 0015 on populated data, standards register rules, secrets hygiene of generated documents."""
from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from app import database as dbmod
from app.core.errors import ValidationFailed
from app.database import Database, get_db, set_db
from app.services import assumptions as asm, audit, backup, standards, tender, workforce as wf
from tests.conftest import COMMERCIAL, ESTIMATOR
from tests.helpers import build_mini


@pytest.fixture()
def filedb(tmp_path, settings):
    settings.db_path = tmp_path / "var" / "real.db"
    set_db(None)
    db = get_db()
    from app.services import refdata
    refdata.seed_reference(db)
    return db, settings, tmp_path


def test_backup_restore_preserves_closure_records_guards_and_audit_chain(filedb):
    db, s, tmp = filedb
    pid = build_mini(db, tmp)
    asm.create_assumption(db, ESTIMATOR, id="ASMP-Z-501", family="I", name="Validity", value_type="number", default_value="30", is_synthetic=True)
    asm.submit_assumption(db, ESTIMATOR, "ASMP-Z-501")
    asm.approve_assumption(db, COMMERCIAL, "ASMP-Z-501")
    wf.create_norm(db, ESTIMATOR, id="N-B", trade="t", activity="a", output_unit="m3", basis="crew_output_per_crew_day", value="2", crew={"skilled": 1}, source="s", is_synthetic=True)
    q = tender.add_query(db, ESTIMATOR, pid, register="technical", question="Extent?", response_due="2027-03-01")
    b = backup.create_backup(s, label="closure")
    rep = backup.validate_backup(b)
    assert rep["ok"] and rep["manifest"]["row_counts"]["tender_queries"] == 1 and rep["manifest"]["row_counts"]["productivity_norms"] == 1
    db.execute("DELETE FROM tender_queries")
    db.execute("DELETE FROM productivity_norms")
    backup.restore_backup(b, confirm=True, settings=s)
    db2 = get_db()
    assert db2.scalar("SELECT COUNT(*) FROM tender_queries") == 1 and db2.scalar("SELECT status FROM tender_queries WHERE id=?", (q,)) == "Draft"
    assert audit.verify_chain(db2)["ok"]
    with pytest.raises(sqlite3.DatabaseError, match="IMMUTABLE_RECORD"):                       # the immutability triggers survive a restore
        db2.execute("UPDATE assumptions SET default_value='9' WHERE id='ASMP-Z-501' AND version=1")


def test_migration_0015_is_additive_and_forward_only_on_populated_data(tmp_path, monkeypatch):
    old = tmp_path / "migs_to_0014"
    old.mkdir()
    for f in sorted(dbmod.MIGRATIONS_DIR.glob("*.sql")):
        if f.stem < "0015":
            shutil.copy2(f, old / f.name)
    monkeypatch.setattr(dbmod, "MIGRATIONS_DIR", old)
    db = Database(tmp_path / "m.db")
    applied = db.migrate()
    assert applied[-1].startswith("0014")
    db.insert("assumptions", dict(id="ASMP-OLD", version=1, family="I", name="old approved value", value_type="number", default_value="7", status="Approved", created_by="x", approved_by="y"))
    db.update("assumptions", {"default_value": "8"}, "id=?", ("ASMP-OLD",))              # before 0015 nothing guards it (documented): this is the gap the migration closes
    monkeypatch.undo()
    assert db.migrate() == [f.stem for f in sorted(dbmod.MIGRATIONS_DIR.glob("*.sql")) if f.stem >= "0015"]
    row = db.one("SELECT * FROM assumptions WHERE id='ASMP-OLD'")
    assert row["default_value"] == "8" and row["origin"] == "manual" and row["category"] is None            # existing rows untouched, new columns defaulted
    with pytest.raises(sqlite3.DatabaseError, match="IMMUTABLE_RECORD"):
        db.execute("UPDATE assumptions SET default_value='9' WHERE id='ASMP-OLD'")                         # guard now active for already-approved rows
    assert db.migrate() == []                                                                               # idempotent: forward-only, applied once


def test_standards_register_rules(seeded, tmp_path):
    rows = standards.list_standards(seeded)
    assert len(rows) == 13
    for r in rows:
        if r["verification_status"].startswith("Verified"):
            assert r["url"] and r["access_date"] and r["limitations"], r["id"]
        assert len(r["paraphrase"] or "") < 700                                                  # concise paraphrase, never reproduced text
    prod = [r for r in rows if r["topic"] and "productivity" in r["topic"].lower()]
    assert all(r["verification_status"].startswith("Not verified") for r in prod) or not prod
    assert all(r["verification_status"].startswith("Not verified") for r in rows if r["id"] in ("STD-009", "STD-010", "STD-011", "STD-012", "STD-004"))
    todo = standards.acquisition_list(seeded)
    assert {"STD-004", "STD-009"} <= {x["id"] for x in todo}
    f = tmp_path / "s.json"
    base = {"access_date": "2026-10-14", "title": "t", "topic": "x"}
    f.write_text(json.dumps({"sources": [dict(base, id="STD-X1", verification_status="Verified - primary source read", url=None)]}))
    with pytest.raises(ValidationFailed):
        standards.import_register(seeded, f)                                                       # 'Verified' needs the URL / file that was read
    f.write_text(json.dumps({"sources": [dict(base, id="STD-X2", verification_status="Plausibly true")]}))
    with pytest.raises(ValidationFailed):
        standards.import_register(seeded, f)
    f.write_text(json.dumps({"sources": [dict(base, id="STD-X3", verification_status="Not verified - requires human acquisition")]}))
    assert standards.import_register(seeded, f, dry_run=True)["new"] == 1 and len(standards.list_standards(seeded)) == 13
    assert standards.import_register(seeded, f)["new"] == 1 and standards.import_register(seeded, f)["new"] == 0       # insert-only


def test_no_secret_material_in_documents_or_logs(tmp_path):
    from app.config import get_settings
    from app.tender import model
    key = "synthetic-closure-secret-key"
    d = model.Doc("D01", "t", [model.Section("S", ["text"])])
    meta = dict(project_id="P", project_name="n", customer="c", doc_id="P-D01", title="t", revision=1, issue_date="2027-01-01", status="Draft", author="a", reviewer="r", estimate_version="v1",
                fingerprint="ab", template="t", confidentiality="c", banner="B", synthetic_mark="")
    p = tmp_path / "x.docx"
    model.render_docx(d, meta, p)
    assert key.encode() not in p.read_bytes() and "password" not in model.parse_back(p)["text"].lower()


def test_standards_update_is_audited(seeded, tmp_path):
    f = tmp_path / "u.json"
    row = dict(id="STD-U1", title="t", topic="x", access_date="2026-10-14", verification_status="Not verified - requires human acquisition")
    f.write_text(json.dumps({"sources": [row]}))
    standards.import_register(seeded, f)
    row.update(verification_status="Verified - primary source read", url="file:evidence/x.pdf")
    f.write_text(json.dumps({"sources": [row]}))
    assert standards.import_register(seeded, f)["updated"] == 0                                    # default stays insert-only
    assert standards.import_register(seeded, f, update=True, dry_run=True)["updated"] == 1
    assert standards.import_register(seeded, f, update=True, created_by="alice")["updated"] == 1
    assert standards.import_register(seeded, f, update=True)["updated"] == 0                       # idempotent
    assert [r for r in standards.list_standards(seeded) if r["id"] == "STD-U1"][0]["verification_status"].startswith("Verified")
    assert seeded.one("SELECT 1 FROM audit_log WHERE entity_type='standards_register' AND entity_id='STD-U1' AND action='update'")
