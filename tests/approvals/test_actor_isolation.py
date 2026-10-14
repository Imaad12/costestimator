"""Production readiness needs a verifiable chain of REGISTERED HUMAN approvals in a production environment; test, unregistered, forged, copied or role-mismatched approvals
never make an export submission-ready, and synthetic/demo projects can never be described as approved for a real tender.

The rates/assemblies below are ordinary (non-synthetic) TEST FIXTURE records created inside the test database only - they are not market data and are labelled as fixtures."""
from __future__ import annotations

import json
from pathlib import Path

import openpyxl
import pytest

from app.core.errors import ApprovalBlocked, PermissionDenied
from app.imports import boq as boq_import
from app.models.actor import Actor
from app.reconciliation import engine as recon
from app.services import assemblies, auth, boq, commercial, estimates, indirects, offers, projects, rates, readiness
from tests.conftest import ESTIMATOR
from tests.helpers import write_boq


def mk_users(db, **types):
    for u, role in (("h-est", "Estimator"), ("h-proc", "Procurement Reviewer"), ("h-com", "Commercial Approver")):
        auth.create_user(db, u, "Display " + u, role, "pw", actor_type=types.get(u, "human"))
    return {u: auth.get_actor(db, u) for u in ("h-est", "h-proc", "h-com")}


def real_project(db, tmp_path, U, *, demo=False):
    """A complete, non-synthetic fixture project whose every approval is made by the given registered users."""
    est, proc, com = U["h-est"], U["h-proc"], U["h-com"]
    rid = rates.create_resource(db, est, resource_type="material", description="FIXTURE material (not market data)", unit="m3", cost_code="C.01", id="FX-MAT-1")
    r = rates.propose_rate(db, est, rid, unit_price="100", rate_type="Published Market Price", currency="SAR", unit="m3", evidence="TEST FIXTURE evidence (not a market price)",
                           price_date="2026-09-01", valid_until="2027-09-01", confidence="Medium", tax_basis="Excluded", submit=True)
    rates.approve_rate(db, proc, r, comments="fixture")
    assemblies.create_assembly(db, est, code="FX-ASM", description="fixture", unit="m3", cost_code="C.01", source="TEST FIXTURE",
                               lines_=[dict(line_type="material", resource_id=rid, factor="1", factor_includes_waste=1)])
    assemblies.submit_assembly(db, est, "FX-ASM")
    assemblies.approve_assembly(db, com, "FX-ASM")
    pid = projects.create_project(db, est, name="Fixture project", is_demo=demo, tax_category="VAT-STD")
    boq_import.import_boq(db, est, pid, write_boq(tmp_path / "b.csv", [("1", "Item", "m3", "10", "", "")]))
    boq.map_to_assembly(db, est, pid, "1", "FX-ASM")
    pol = commercial.create_policy(db, est, code="FX-POL", name="fixture", config={"method": "markup", "markup_pct": "10", "default_tax_category": "VAT-STD",
                                   "contingency": {"pct": "5", "base": "direct_indirect"}, "risk_items": [], "rounding": {"dp": 2}})
    commercial.submit_policy(db, est, pol)
    commercial.approve_policy(db, com, pol)
    commercial.assign_policy(db, est, pid, pol)
    tid = db.scalar("SELECT id FROM tax_categories WHERE code='VAT-STD'")
    commercial.approve_tax_category(db, com, tid, evidence="TEST FIXTURE evidence (not a tax determination)")
    indirects.add_indirect(db, est, pid, code="IND-1", category="Project management", description="fixture lump", method="fixed", amount="500", source="TEST FIXTURE")
    indirects.submit_indirect(db, est, pid, "IND-1")
    indirects.approve_indirect(db, com, pid, "IND-1")
    return pid


def finish(db, tmp_path, U, pid, *, exec_actor=None):
    est, com = U["h-est"], exec_actor or U["h-com"]
    recon.run_reconciliation(db, est, pid)
    for f in recon.get_run(db, recon.run_reconciliation(db, est, pid)["run_id"])["findings"]:
        if f["status"] == "Open" and f["severity"] in ("High", "Critical") and f["severity"] != "Critical":
            recon.accept_exception(db, com, f["id"], "fixture exception for the isolation test")
    vid = estimates.freeze_version(db, est, pid, "v1")
    estimates.submit_version(db, est, vid)
    estimates.approve_version(db, com, vid, "fixture")
    o = offers.generate_offer(db, est, pid, payment_terms="fixture terms")
    offers.approve_offer(db, com, pid, o["version_no"])
    ap = estimates.approve_tender_export(db, com, pid, vid, "fixture")
    return vid, ap


def test_registered_human_chain_in_production_is_submission_ready(seeded, tmp_path):
    U = mk_users(seeded)
    pid = real_project(seeded, tmp_path, U)
    vid, ap = finish(seeded, tmp_path, U, pid)
    r = readiness.evaluate(seeded, pid, vid, ap)
    assert r["production_ready"], r["reasons"]
    files = estimates.export_submission(seeded, U["h-est"], pid, vid, ap)
    a2 = openpyxl.load_workbook(files["pricing_schedule"]).active["A2"].value
    assert a2.startswith("SUBMISSION READY - production approval chain verified") and "h-com (Commercial Approver, human)" in a2
    assert seeded.scalar("SELECT COUNT(*) FROM exports WHERE submission_ready=1") == 4


def test_test_actor_approvals_never_satisfy_production(seeded, tmp_path):
    U = mk_users(seeded)
    pid = real_project(seeded, tmp_path, U)
    auth.create_user(seeded, "t-com", "Looks Like A Real Commercial Approver", "Commercial Approver", "pw", actor_type="test")
    t = auth.get_actor(seeded, "t-com")
    with pytest.raises(ApprovalBlocked) as e:
        finish(seeded, tmp_path, U, pid, exec_actor=t)                       # a registered TEST principal cannot approve the estimate of a real project in production
    assert e.value.code == "NON_HUMAN_ACTOR"


def test_forged_display_name_and_unregistered_principal_do_not_count(seeded, tmp_path):
    U = mk_users(seeded)
    pid = real_project(seeded, tmp_path, U)
    forged = Actor("someone-else", "Commercial Approver", "h-com (Commercial Approver) - real human")        # nobody registered under this username
    assert seeded.scalar("SELECT COUNT(*) FROM users WHERE username='someone-else'") == 0
    with pytest.raises(ApprovalBlocked) as e:
        finish(seeded, tmp_path, U, pid, exec_actor=forged)
    assert e.value.code == "NON_HUMAN_ACTOR"
    # a registered user whose claimed role differs from the registered one is 'role_mismatch', not human
    liar = Actor("h-est", "Commercial Approver", "claims to be a commercial approver")
    from app.approvals import engine as ap
    assert ap.resolve_actor_type(seeded, liar) == "role_mismatch" and ap.resolve_actor_type(seeded, Actor("nobody", "Estimator")) == "unregistered"


def test_environment_must_be_production(seeded, tmp_path, settings):
    settings.environment = "test"
    U = mk_users(seeded)
    pid = real_project(seeded, tmp_path, U)
    vid, ap = finish(seeded, tmp_path, U, pid)                               # allowed to act in a test environment ...
    settings.environment = "production"
    r = readiness.evaluate(seeded, pid, vid, ap)
    assert not r["production_ready"] and any("environment 'test'" in x for x in r["reasons"])           # ... but those approvals never count in production
    with pytest.raises(ApprovalBlocked) as e:
        estimates.export_submission(seeded, U["h-est"], pid, vid, ap)
    assert e.value.code == "NOT_PRODUCTION_READY"


def test_copied_or_handwritten_approval_rows_are_detected(seeded, tmp_path):
    U = mk_users(seeded)
    pid = real_project(seeded, tmp_path, U)
    vid, ap = finish(seeded, tmp_path, U, pid)
    row = dict(seeded.one("SELECT * FROM approvals WHERE id=?", (ap,)))
    row.pop("id")
    # a genuine approval copied to another project/version is refused: it names a different entity
    other = seeded.insert("approvals", {**row, "entity_id": "PRJ-9999/v1", "project_id": "PRJ-9999"})
    probs, _ = readiness.check_approval(seeded, seeded.one("SELECT * FROM approvals WHERE id=?", (other,)), "x", entity_type="tender_export", entity_id=f"{pid}/v1", project_id=pid)
    assert any("approval is for tender_export:PRJ-9999/v1" in p for p in probs) and any("no matching audit-log entry" in p for p in probs)
    # a hand-written row for a real version with a made-up reviewer has no audit entry and no registered user
    hand = seeded.insert("approvals", {**row, "reviewer": "ghost", "reviewer_role": "Commercial Approver", "actor_type": "human", "environment": "production"})
    probs, _ = readiness.check_approval(seeded, seeded.one("SELECT * FROM approvals WHERE id=?", (hand,)), "x", entity_type="tender_export", entity_id=f"{pid}/v1", project_id=pid)
    assert any("no matching audit-log entry" in p for p in probs) and any("not (or is no longer) an active registered human" in p for p in probs)
    r = readiness.evaluate(seeded, pid, vid, hand)
    assert not r["production_ready"]


def test_demo_project_gets_a_demonstration_export_never_submission_ready(seeded, tmp_path):
    U = mk_users(seeded)
    pid = real_project(seeded, tmp_path, U, demo=True)
    vid, ap = finish(seeded, tmp_path, U, pid)
    r = readiness.evaluate(seeded, pid, vid, ap)
    assert r["classification"] == "demonstration" and not r["production_ready"] and any("demonstration project" in x for x in r["reasons"])
    files = estimates.export_submission(seeded, U["h-est"], pid, vid, ap)
    a2 = openpyxl.load_workbook(files["pricing_schedule"]).active["A2"].value
    assert a2.startswith("DEMONSTRATION EXPORT - NOT SUBMISSION READY - NOT APPROVED FOR ANY REAL TENDER") and "SUBMISSION READY -" not in a2.replace("NOT SUBMISSION READY -", "")
    assert Path(files["pricing_schedule"]).name.endswith("_DEMONSTRATION.xlsx") and seeded.scalar("SELECT COUNT(*) FROM exports WHERE submission_ready=1") == 0


def test_exception_by_a_test_principal_blocks_production_readiness(seeded, tmp_path):
    U = mk_users(seeded)
    pid = real_project(seeded, tmp_path, U)
    vid, ap = finish(seeded, tmp_path, U, pid)
    seeded.execute("INSERT INTO recon_exceptions(project_id, rule_code, entity_type, entity_id, fingerprint, reason, accepted_by, accepted_role, accepted_at, accepted_actor_type, environment) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?,?)", (pid, "X", "t", "1", "fp", "forged waiver", "h-com", "Commercial Approver", "2026-01-01", "test", "production"))
    r = readiness.evaluate(seeded, pid, vid, ap)
    assert not r["production_ready"] and any("accepted by a 'test' principal" in x for x in r["reasons"])


def test_ai_and_viewer_cannot_approve_and_role_matrix_unchanged(seeded, tmp_path):
    U = mk_users(seeded)
    pid = real_project(seeded, tmp_path, U)
    vid = estimates.freeze_version(seeded, U["h-est"], pid, "v1")
    estimates.submit_version(seeded, U["h-est"], vid)
    with pytest.raises(PermissionDenied):
        estimates.approve_version(seeded, Actor("ai-bot", "AI Assistant", "AI", is_ai=True), vid)
    with pytest.raises(PermissionDenied):
        estimates.approve_version(seeded, U["h-est"], vid)
