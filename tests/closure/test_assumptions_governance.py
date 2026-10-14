"""Assumptions register: categories, origins, data classes, immutability (service and database guard), four-eyes defaults (SYNTHETIC values)."""
from __future__ import annotations

import sqlite3

import pytest

from app import config as cfg
from app.core.errors import ApprovalBlocked, Conflict, ImmutableRecord, PermissionDenied, ValidationFailed
from app.models.actor import Actor
from app.services import assumptions as asm
from tests.conftest import ADMIN, COMMERCIAL, ESTIMATOR, VIEWER
from tests.helpers import build_mini

AI = Actor("ai-bot", "AI Assistant", "AI", is_ai=True)


def mk(db, aid="ASMP-T-001", **kw):
    base = dict(id=aid, family="I", name="Offer validity", value_type="number", default_value="30", unit="day", source="SYNTHETIC", category="Commercial terms and payment", reason="test", is_synthetic=True)
    base.update(kw)
    return asm.create_assumption(db, ESTIMATOR, **base)


def test_seventeen_categories_and_validation(seeded):
    assert len(asm.CATEGORIES) == 17 and len(set(asm.CATEGORIES)) == 17
    with pytest.raises(ValidationFailed):
        mk(seeded, category="Not a category")
    with pytest.raises(ValidationFailed):
        mk(seeded, origin="telepathy")
    mk(seeded, "ASMP-T-002", category=None)                                   # defaults from the family mapping
    assert asm.get_latest(seeded, "ASMP-T-002")["category"] == asm.FAMILY_DEFAULT_CATEGORY["I"]


def test_ai_cannot_enter_or_approve_register_rows(seeded):
    with pytest.raises(PermissionDenied):
        asm.create_assumption(seeded, AI, id="ASMP-T-009", family="I", name="x")
    mk(seeded)
    asm.submit_assumption(seeded, ESTIMATOR, "ASMP-T-001")
    with pytest.raises(PermissionDenied) as e:
        asm.approve_assumption(seeded, AI, "ASMP-T-001")
    assert e.value.code == "AI_CANNOT_APPROVE"
    with pytest.raises(ValidationFailed):
        mk(seeded, "ASMP-T-010", origin="ai")                                 # AI-proposed values enter only through ai_suggestions


def test_manual_entry_is_not_approval_and_values_stay_pending(seeded):
    mk(seeded)
    assert asm.get_latest(seeded, "ASMP-T-001")["status"] == "Draft"
    with pytest.raises(Conflict):
        asm.approve_assumption(seeded, COMMERCIAL, "ASMP-T-001")              # not even submitted
    asm.submit_assumption(seeded, ESTIMATOR, "ASMP-T-001")
    assert asm.get_latest(seeded, "ASMP-T-001")["status"] == "Pending Review"


def test_data_class_matrix():
    assert asm.data_class(dict(is_synthetic=1, default_value="1", status="Approved")) == "Explicitly synthetic test data"
    assert asm.data_class(dict(default_value=None, status="Approved", origin="manual")) == "Missing data"
    assert asm.data_class(dict(default_value="1", status="Pending Review", origin="manual")) == "Pending human review"
    assert asm.data_class(dict(default_value="1", status="Draft", origin="import")) == "Imported but unverified"
    assert asm.data_class(dict(default_value="1", status="Draft", origin="ai")) == "AI-proposed data"
    assert asm.data_class(dict(default_value="1", status="Approved", origin="manual", evidence="e", confidence="High")) == "Verified source data"
    assert asm.data_class(dict(default_value="1", status="Approved", origin="manual", evidence=None, confidence="Low")) == "Company-approved internal data"
    assert asm.data_class(dict(override_value="2", status="Approved", origin="manual"), project_override=True) == "Project-approved data"
    assert asm.data_class(dict(default_value="1", status="Rejected", origin="manual")) == "Missing data"


def test_approved_versions_are_immutable_in_service_and_database(seeded):
    mk(seeded, is_synthetic=False, evidence="e", confidence="High")
    asm.submit_assumption(seeded, ESTIMATOR, "ASMP-T-001")
    asm.approve_assumption(seeded, COMMERCIAL, "ASMP-T-001")
    v = asm.revise_assumption(seeded, ESTIMATOR, "ASMP-T-001", default_value="45", reason="customer changed the validity")
    assert v == 2 and asm.get_latest(seeded, "ASMP-T-001")["supersedes_version"] == 1
    assert [asm.get_latest(seeded, "ASMP-T-001")["default_value"], asm.get_current_approved(seeded, "ASMP-T-001")["default_value"]] == ["45", "30"]
    for sql in ("UPDATE assumptions SET default_value='99' WHERE id='ASMP-T-001' AND version=1", "DELETE FROM assumptions WHERE id='ASMP-T-001' AND version=1",
                "UPDATE assumptions SET approved_by='x' WHERE id='ASMP-T-001' AND version=1", "UPDATE assumptions SET source='forged' WHERE id='ASMP-T-001' AND version=1",
                "UPDATE assumptions SET is_synthetic=1 WHERE id='ASMP-T-001' AND version=1", "UPDATE assumptions SET status='Draft' WHERE id='ASMP-T-001' AND version=1"):
        with pytest.raises(sqlite3.DatabaseError, match="IMMUTABLE_RECORD"):
            seeded.execute(sql)
    asm.submit_assumption(seeded, ESTIMATOR, "ASMP-T-001")
    asm.approve_assumption(seeded, COMMERCIAL, "ASMP-T-001")
    old = seeded.one("SELECT status FROM assumptions WHERE id='ASMP-T-001' AND version=1")
    assert old["status"] == "Superseded"                                       # the legal status transition is still allowed
    with pytest.raises(sqlite3.DatabaseError, match="IMMUTABLE_RECORD"):
        seeded.execute("UPDATE assumptions SET status='Approved' WHERE id='ASMP-T-001' AND version=1")            # a superseded version cannot be resurrected
    with pytest.raises(ImmutableRecord):
        asm.reject_assumption(seeded, COMMERCIAL, "ASMP-T-001", "no")


def test_history_links_versions_approvals_and_audit(seeded):
    mk(seeded)
    asm.submit_assumption(seeded, ESTIMATOR, "ASMP-T-001")
    asm.approve_assumption(seeded, COMMERCIAL, "ASMP-T-001", comments="ok")
    h = asm.assumption_history(seeded, "ASMP-T-001")[0]
    assert h["versions"][0]["approvals"][0]["reviewer"] == "com" and [a["action"] for a in h["audit"]][:3] == ["create", "submit", "approval:approve"]


def test_project_override_is_separate_and_immutable_when_approved(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    mk(seeded)
    asm.submit_assumption(seeded, ESTIMATOR, "ASMP-T-001")
    asm.approve_assumption(seeded, COMMERCIAL, "ASMP-T-001")
    asm.adopt(seeded, ESTIMATOR, pid, "ASMP-T-001")
    asm.set_override(seeded, ESTIMATOR, pid, "ASMP-T-001", "60", "project needs a longer validity")
    r = asm.resolve(seeded, pid, "ASMP-T-001")
    assert r.value == "60" and r.status == "Pending Review" and not r.approved                  # a proposed override is flagged, never silently approved
    asm.approve_override(seeded, COMMERCIAL, pid, "ASMP-T-001")
    assert asm.resolve(seeded, pid, "ASMP-T-001").approved and asm.get_current_approved(seeded, "ASMP-T-001")["default_value"] == "30"      # the global library is untouched
    with pytest.raises(sqlite3.DatabaseError, match="IMMUTABLE_RECORD"):
        seeded.execute("UPDATE project_assumptions SET override_value='1' WHERE assumption_id='ASMP-T-001' AND status='Approved'")
    with pytest.raises(sqlite3.DatabaseError, match="IMMUTABLE_RECORD"):
        seeded.execute("DELETE FROM project_assumptions WHERE assumption_id='ASMP-T-001' AND status='Approved'")
    rep = asm.evidence_report(seeded, pid)
    row = next(x for x in rep["rows"] if x["id"] == "ASMP-T-001")
    assert row["data_class"] == "Explicitly synthetic test data" and not rep["fully_verified"]          # synthetic never reads as verified, even when approved


def test_four_eyes_is_the_default_and_the_administrator_is_not_exempt_for_material_records(seeded):
    assert cfg.load_settings(env={}).allow_self_approval is False
    cfg.get_settings().allow_self_approval = False
    adm = Actor("admin", "Administrator", "Admin")
    asm.create_assumption(seeded, adm, id="ASMP-T-050", family="I", name="x", value_type="number", default_value="1", is_synthetic=True)
    asm.submit_assumption(seeded, adm, "ASMP-T-050")
    with pytest.raises(ApprovalBlocked) as e:
        asm.approve_assumption(seeded, adm, "ASMP-T-050")
    assert e.value.code == "SELF_APPROVAL_BLOCKED"
    mk(seeded)
    asm.submit_assumption(seeded, ESTIMATOR, "ASMP-T-001")
    with pytest.raises(ApprovalBlocked):
        asm.approve_assumption(seeded, ESTIMATOR, "ASMP-T-001")
    with pytest.raises(PermissionDenied):
        asm.approve_assumption(seeded, VIEWER, "ASMP-T-001")
    asm.approve_assumption(seeded, COMMERCIAL, "ASMP-T-001")


def test_seeded_library_ships_unapproved_and_without_values(seeded):
    rows = asm.list_assumptions(seeded)
    assert rows and all(r["origin"] == "seed" and r["status"] == "Pending Review" and r["category"] for r in rows)
    assert {asm.data_class(r) for r in rows} <= {"Missing data", "Pending human review"}
