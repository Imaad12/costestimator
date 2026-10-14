"""Negative controls the closure brief names that are not covered by the scenario's own stages: invalid units and tax inputs, incomplete programmes, synthetic data on a 'real' project,
missing required documents in a pack, API self-approval and viewer writes for the closure actions. All data are SYNTHETIC / FIXTURE values."""
from __future__ import annotations

import pytest

from app import config as cfg
from app.core.errors import ValidationFailed
from app.estimators.estimate import compute_estimate
from app.reconciliation import engine as recon
from app.services import assumptions as asm, auth, commercial, governed, readiness, workforce as wf
from tests.approvals.test_actor_isolation import finish, mk_users
from tests.conftest import COMMERCIAL, ESTIMATOR
from tests.helpers import build_mini

CREW = {"skilled": 1}


def _cal(db, pid, **kw):
    data = {"start_date": "2027-01-03", "work_weekdays": [6, 0, 1, 2, 3], "holidays": [], "hours_per_day": "8"} | kw
    i = governed.propose(db, ESTIMATOR, "calendar", "PROJECT", data, project_id=pid, source="SYNTHETIC", is_synthetic=True, submit=True)
    governed.approve(db, COMMERCIAL, i)


def test_invalid_unit_between_norm_and_boq_excludes_the_activity_with_a_gap(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    _cal(seeded, pid)
    wf.create_norm(seeded, ESTIMATOR, id="N-U", trade="t", activity="a", output_unit="kg", basis="crew_output_per_crew_day", value="1", crew=CREW, source="s", effective_from="2026-01-01", is_synthetic=True)
    wf.submit_norm(seeded, ESTIMATOR, "N-U")
    wf.approve_norm(seeded, COMMERCIAL, "N-U")
    wf.create_profile(seeded, ESTIMATOR, id="WP-U", archetype="custom", name="p", roles={"skilled": 4}, attendance_pct="100", availability_pct="100", productive_hours_per_shift="6", is_synthetic=True)
    wf.set_activities(seeded, ESTIMATOR, pid, [dict(code="A1", name="a", boq_item_key="1.1", norm_id="N-U")])                 # BOQ item 1.1 is in m3, the norm is per kg
    r = wf.build_programme(seeded, pid, "WP-U", allow_provisional=True, allow_unconfirmed_calendar=True)
    assert any(g["kind"] == "UNIT_MISMATCH" and g["code"] == "A1" for g in r["gaps"]) and r["activities"][0]["status"] == "MISSING_NORM" and not r["complete"]
    assert r["working_days"] == 0                                                                     # never a silent duration for an activity that could not be calculated


def test_invalid_calendar_and_activity_inputs_are_refused(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    for bad in ({"hours_per_day": "8", "reduced_hours": [{"from": "2027-04-01", "to": "2027-04-10", "hours": "9", "reason": "x"}]},        # reduced day longer than the standard day
                {"hours_per_day": "8", "reduced_hours": [{"from": "2027-04-01", "to": "2027-04-10", "hours": "6"}]},                         # no reason / approval reference
                {"reduced_hours": [{"from": "2027-04-01", "to": "2027-04-10", "hours": "6", "reason": "x"}]},                               # standard day not stated
                {"hours_per_day": "8", "shutdowns": [{"from": "2027-05-10", "to": "2027-05-01"}]}):                                          # reversed window
        with pytest.raises(ValidationFailed):
            governed.propose(seeded, ESTIMATOR, "calendar", "PROJECT", {"start_date": "2027-01-03", "work_weekdays": [6], "holidays": []} | bad, project_id=pid, source="s")
    with pytest.raises(ValidationFailed) as e:
        wf.set_activities(seeded, ESTIMATOR, pid, [dict(code="A1", name="a", predecessors="NOPE")])
    assert e.value.code == "PROGRAMME_UNKNOWN_PRED"
    with pytest.raises(ValidationFailed):
        wf.set_activities(seeded, ESTIMATOR, pid, [dict(code="A1", name="a"), dict(code="A1", name="b")])
    with pytest.raises(ValidationFailed):
        wf.set_activities(seeded, ESTIMATOR, pid, [dict(code="A1", name="a", boq_item_key="NO-SUCH-ITEM")])


def test_programme_without_confirmed_calendar_or_profile_is_flagged_never_approved(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    _cal(seeded, pid, requires_confirmation=True)
    wf.create_profile(seeded, ESTIMATOR, id="WP-C", archetype="custom", name="p", roles={"skilled": 4}, attendance_pct="100", availability_pct="100", productive_hours_per_shift="6", is_synthetic=True)
    wf.set_activities(seeded, ESTIMATOR, pid, [dict(code="M", name="fixed", fixed_days={"fixed_only": True, "setup": 2})])
    with pytest.raises(ValidationFailed) as e:
        wf.build_programme(seeded, pid, "WP-C")                                                          # profile not approved: no provisional scenario requested
    assert e.value.code == "PROFILE_NOT_APPROVED"
    r = wf.build_programme(seeded, pid, "WP-C", allow_provisional=True)
    assert r["provisional"] and any(g["kind"] == "CALENDAR_UNCONFIRMED" for g in r["gaps"]) and r["claims"].startswith("PROVISIONAL")
    v = wf.save_baseline(seeded, ESTIMATOR, pid, "WP-C", allow_provisional=True)
    with pytest.raises(ValidationFailed) as e:
        wf.approve_baseline(seeded, COMMERCIAL, pid, v)
    assert e.value.code == "BASELINE_PROVISIONAL"


def test_invalid_tax_and_commercial_inputs_are_refused_or_block(seeded, tmp_path):
    for bad in ({"method": "markup"}, {"method": "magic", "markup_pct": "5"}, {"method": "markup", "markup_pct": "5", "contingency": {"pct": "5", "base": "direct", "eligibility": {"default": "maybe"}}}):
        with pytest.raises(ValidationFailed):
            commercial.create_policy(seeded, ESTIMATOR, code="BAD", name="bad", config=bad)
    pid = build_mini(seeded, tmp_path)
    seeded.execute("UPDATE tax_categories SET status='Draft' WHERE code='VAT-STD'")                       # an unapproved tax category must not silently be treated as approved
    est = compute_estimate(seeded, pid)
    assert est.state != "Complete" or est.tax_status.get("approved") is False or any("tax" in b.lower() for b in est.blockers)


def test_unapproved_adopted_assumptions_surface_as_findings_not_silence(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    asm.create_assumption(seeded, ESTIMATOR, id="ASMP-Z-601", family="I", name="Pending probe", value_type="number", default_value="3", is_synthetic=True, mandatory_for_projects=True)
    asm.adopt_mandatory(seeded, ESTIMATOR, pid)
    run = recon.run_reconciliation(seeded, ESTIMATOR, pid)
    codes = {f["rule_code"] for f in recon.get_run(seeded, run["run_id"])["findings"]}
    assert "UNAPPROVED_ADOPTED_ASSUMPTION" in codes
    assert any(r["id"] == "ASMP-Z-601" and r["data_class"] == "Explicitly synthetic test data" for r in asm.evidence_report(seeded, pid)["rows"])


def test_synthetic_data_on_a_real_project_is_never_production_ready_even_with_humans(seeded, tmp_path):
    """The approval chain is entirely registered humans in a production environment; the only defect is that the priced rate is synthetic."""
    from app.imports import boq as boq_import
    from app.services import assemblies, boq, indirects, projects, rates
    from tests.helpers import write_boq
    U = mk_users(seeded)
    est, proc, com = U["h-est"], U["h-proc"], U["h-com"]
    rid = rates.create_resource(seeded, est, resource_type="material", description="FIXTURE synthetic material", unit="m3", cost_code="C.01", id="FX-SYN-1", is_synthetic=True)
    r = rates.propose_rate(seeded, est, rid, unit_price="100", rate_type="Synthetic Demonstration Rate", currency="SAR", unit="m3", evidence="SYNTHETIC", price_date="2026-09-01", confidence="Medium",
                           is_synthetic=True, submit=True)
    rates.approve_rate(seeded, proc, r)
    assemblies.create_assembly(seeded, est, code="FX-SYN-ASM", description="f", unit="m3", cost_code="C.01", source="SYNTHETIC", is_synthetic=True,
                               lines_=[dict(line_type="material", resource_id=rid, factor="1", factor_includes_waste=1)])
    assemblies.submit_assembly(seeded, est, "FX-SYN-ASM")
    assemblies.approve_assembly(seeded, com, "FX-SYN-ASM")
    pid = projects.create_project(seeded, est, name="Real project with a synthetic rate", is_demo=False, tax_category="VAT-STD")
    boq_import.import_boq(seeded, est, pid, write_boq(tmp_path / "b.csv", [("1", "Item", "m3", "10", "", "")]))
    boq.map_to_assembly(seeded, est, pid, "1", "FX-SYN-ASM")
    pol = commercial.create_policy(seeded, est, code="FX-POL2", name="f", config={"method": "markup", "markup_pct": "10", "default_tax_category": "VAT-STD", "contingency": {"pct": "5", "base": "direct_indirect"},
                                                                                  "risk_items": [], "rounding": {"dp": 2}})
    commercial.submit_policy(seeded, est, pol)
    commercial.approve_policy(seeded, com, pol)
    commercial.assign_policy(seeded, est, pid, pol)
    commercial.approve_tax_category(seeded, com, seeded.scalar("SELECT id FROM tax_categories WHERE code='VAT-STD'"), evidence="TEST FIXTURE")
    indirects.add_indirect(seeded, est, pid, code="IND-1", category="PM", description="f", method="fixed", amount="500", source="f")
    indirects.submit_indirect(seeded, est, pid, "IND-1")
    indirects.approve_indirect(seeded, com, pid, "IND-1")
    from app.core.errors import AppError
    from app.services import estimates
    vid = estimates.freeze_version(seeded, est, pid, "v1")
    estimates.submit_version(seeded, est, vid)
    with pytest.raises(AppError) as e:                                   # the existing Critical rule SYNTHETIC_IN_REAL_PROJECT stops final approval first, and it cannot be waived
        estimates.approve_version(seeded, com, vid, "attempt")
    assert e.value.code == "RECON_BLOCKED" and "SYNTHETIC_IN_REAL_PROJECT" in str(e.value)
    res = readiness.evaluate(seeded, pid, vid, None)                      # ... and the readiness gate independently refuses to call it production-ready
    assert not res["production_ready"] and "synthetic data is used in the estimate" in res["reasons"] and res["classification"] == "not_ready"
    with pytest.raises(AppError) as e:
        estimates.export_submission(seeded, est, pid, vid, 1)
    assert e.value.code in ("EXPORT_NOT_APPROVED", "NOT_PRODUCTION_READY")


def test_validator_flags_a_missing_required_document(seeded, tmp_path):
    from app.tender import packs
    U = mk_users(seeded)
    from tests.approvals.test_actor_isolation import real_project
    pid = real_project(seeded, tmp_path, U)
    vid, ap = finish(seeded, tmp_path, U, pid)
    r = packs.generate_pack(seeded, U["h-est"], pid, out_root=tmp_path / "out", issue_date="2027-01-01", version_id=vid)
    seeded.execute("DELETE FROM generated_documents WHERE pack_pk=? AND doc_code='D09'", (r["pack_pk"],))
    assert any("D09" in e and "not in the applicability matrix / pack" in e for e in packs.validate_pack(seeded, r["pack_pk"])["errors"])


def test_closure_api_actions_enforce_roles_and_four_eyes(tmp_path):
    from fastapi.testclient import TestClient
    from app.database import get_db, set_db
    from app.main import app
    from app.services import refdata
    s = cfg.load_settings(env={})
    s.db_path = tmp_path / "var" / "api.db"
    s.data_dir = cfg.BASE_DIR / "data"
    s.secret_key = "k"
    s.workspaces_override = tmp_path / "workspaces"
    s.__class__.projects_dir = property(lambda self: tmp_path / "projects")
    s.__class__.outputs_dir = property(lambda self: tmp_path / "outputs")
    s.__class__.backups_dir = property(lambda self: tmp_path / "backups")
    s.allow_self_approval = False
    cfg.set_settings(s)
    set_db(None)
    db = get_db()
    refdata.seed_reference(db)
    for u, role in (("est", "Estimator"), ("com", "Commercial Approver"), ("view", "Viewer")):
        auth.create_user(db, u, u, role, "pw-" + u)
    try:
        with TestClient(app, headers={"Origin": "http://testserver"}) as c:
            def h(u):
                t = c.post("/api/auth/login", json={"username": u, "password": "pw-" + u}).json()["token"]
                c.cookies.clear()
                return {"Authorization": "Bearer " + t}
            body = dict(id="N-API", trade="t", activity="a", output_unit="m3", basis="crew_output_per_crew_day", value="2", crew={"skilled": 1}, source="SYNTHETIC", effective_from="2027-01-01", is_synthetic=True)
            assert c.post("/api/actions/create_norm", json=body, headers=h("view")).status_code == 403
            assert c.post("/api/actions/create_norm", json=body, headers=h("est")).status_code == 200
            assert c.post("/api/actions/submit_norm", json={"id": "N-API"}, headers=h("est")).status_code == 200
            r = c.post("/api/actions/approve_norm", json={"id": "N-API", "approved_by": "com", "reviewer": "com"}, headers=h("est"))
            assert r.status_code == 409 and r.json()["error"] == "SELF_APPROVAL_BLOCKED"                          # identity comes from the token, not the body
            assert c.post("/api/actions/approve_norm", json={"id": "N-API"}, headers=h("view")).status_code == 403
            assert c.post("/api/actions/approve_norm", json={"id": "N-API"}, headers=h("com")).status_code == 200
            assert db.scalar("SELECT approved_by FROM productivity_norms WHERE id='N-API'") == "com"
            assert c.post("/api/actions/approve_norm", json={"id": "N-API"}).status_code == 401
    finally:
        set_db(None)
        cfg.set_settings(None)


def test_closure_gate_rejects_test_principal_approvals_of_norms_profile_and_baseline(seeded, tmp_path):
    """The approvals behind the programme inputs must be registered-human production approvals: a test principal's approval makes the records Approved but never counts for readiness."""
    U = mk_users(seeded)
    auth.create_user(seeded, "t-com", "Test Commercial", "Commercial Approver", "pw", actor_type="test")
    T = auth.get_actor(seeded, "t-com")
    pid = build_mini(seeded, tmp_path)
    cal = governed.propose(seeded, U["h-est"], "calendar", "PROJECT", {"start_date": "2027-01-03", "work_weekdays": [6, 0, 1, 2, 3], "holidays": [], "hours_per_day": "8"}, project_id=pid, source="s", submit=True)
    governed.approve(seeded, U["h-com"], cal)
    wf.create_norm(seeded, U["h-est"], id="N-G", trade="t", activity="a", output_unit="m3", basis="crew_output_per_crew_day", value="2", crew=CREW, source="s", effective_from="2026-01-01")
    wf.submit_norm(seeded, U["h-est"], "N-G")
    wf.approve_norm(seeded, T, "N-G")
    wf.create_profile(seeded, U["h-est"], id="WP-G", archetype="custom", name="p", roles={"skilled": 4}, attendance_pct="100", availability_pct="100", productive_hours_per_shift="6")
    wf.submit_profile(seeded, U["h-est"], "WP-G")
    wf.approve_profile(seeded, T, "WP-G")
    wf.set_activities(seeded, U["h-est"], pid, [dict(code="A1", name="a", boq_item_key="1.1", norm_id="N-G")])
    v = wf.save_baseline(seeded, U["h-est"], pid, "WP-G", allow_unconfirmed_calendar=False)
    wf.approve_baseline(seeded, T, pid, v)
    text = " | ".join(readiness._closure_gate(seeded, pid, compute_estimate(seeded, pid)))
    assert "productivity norm N-G: approved by a 'test' principal" in text
    assert f"programme baseline v{v}: approved by a 'test' principal" in text
    assert "workforce profile WP-G: approved by a 'test' principal" in text
    # the same records approved by registered humans (new versions) satisfy the check
    wf.revise_norm(seeded, U["h-est"], "N-G", value="3")
    wf.submit_norm(seeded, U["h-est"], "N-G")
    wf.approve_norm(seeded, U["h-com"], "N-G")
    text2 = " | ".join(readiness._closure_gate(seeded, pid, compute_estimate(seeded, pid)))
    assert "productivity norm N-G" not in text2
