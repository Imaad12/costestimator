"""Norm / profile / activity / programme service: governance lifecycle, DB-level immutability, scenarios and baseline gate (SYNTHETIC)."""
from __future__ import annotations

import sqlite3

import pytest

from app.core.errors import ApprovalBlocked, Conflict, ImmutableRecord, PermissionDenied, ValidationFailed
from app.models.actor import Actor
from app.services import governed, workforce as wf
from tests.conftest import ADMIN, COMMERCIAL, ESTIMATOR, PROCUREMENT, VIEWER
from tests.helpers import build_mini

CREW = {"fitter": 2, "helper": 1}


def norm(db, nid="NRM-1", **kw):
    base = dict(id=nid, trade="Concrete", activity="Place C30", output_unit="m3", basis="crew_output_per_crew_day", value="2", crew=CREW,
                source="SYNTHETIC test source", evidence="SYNTHETIC", effective_from="2026-01-01", is_synthetic=True)
    base.update(kw)
    return wf.create_norm(db, ESTIMATOR, **base)


def approve_norm(db, nid):
    wf.submit_norm(db, ESTIMATOR, nid)
    wf.approve_norm(db, COMMERCIAL, nid)


def profile(db, pid="WP-1", archetype="sme", roles=None, **kw):
    base = dict(id=pid, archetype=archetype, name="SYNTHETIC crew", roles=roles or {"fitter": 6, "helper": 3}, attendance_pct="100", availability_pct="100",
                productive_hours_per_shift="6", is_synthetic=True)
    base.update(kw)
    return wf.create_profile(db, ESTIMATOR, **base)


@pytest.fixture()
def proj(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    c = governed.propose(seeded, ESTIMATOR, "calendar", "PROJECT", {"start_date": "2027-01-03", "work_weekdays": [6, 0, 1, 2, 3], "holidays": [], "hours_per_day": "8"},
                         project_id=pid, source="contract (test)", submit=True)
    governed.approve(seeded, COMMERCIAL, c)
    return pid


def test_norm_lifecycle_states_and_immutability(seeded):
    n = norm(seeded)
    assert wf.get_norm(seeded, n)["status"] == "Draft"
    # imported / system proposals land in their own states, and a synthetic norm can never be 'verified'
    assert wf.get_norm(seeded, norm(seeded, "NRM-I", origin="import", is_synthetic=False))["status"] == "Imported - Unverified"
    with pytest.raises(ValidationFailed):
        wf.create_norm(seeded, ESTIMATOR, id="X", trade="t", activity="a", output_unit="m", basis="labour_hours_per_unit", value="1", crew=CREW, origin="system")
    wf.propose_norm(seeded, ESTIMATOR, n)
    wf.submit_norm(seeded, ESTIMATOR, n)
    with pytest.raises(PermissionDenied):
        wf.approve_norm(seeded, VIEWER, n)
    with pytest.raises(PermissionDenied):
        wf.approve_norm(seeded, Actor("bot", "AI Assistant", "bot", is_ai=True), n)
    wf.approve_norm(seeded, COMMERCIAL, n)
    assert wf.get_norm(seeded, n)["status"] == "Approved" and wf.get_norm(seeded, n)["evidence_status"] == "synthetic"
    with pytest.raises(Conflict):
        wf.approve_norm(seeded, COMMERCIAL, "NRM-I")                       # an imported-unverified norm must be submitted for review first
    # a change creates version 2; v1 stays untouched until v2 is approved
    assert wf.revise_norm(seeded, ESTIMATOR, n, value="3") == 2
    assert wf.get_norm(seeded, n, 1)["value"] == "2" and wf.get_norm(seeded, n, 1)["status"] == "Approved"
    # direct SQL against an approved row is refused by the database guard
    with pytest.raises(sqlite3.DatabaseError):
        seeded.execute("UPDATE productivity_norms SET value='99' WHERE id=? AND version=1", (n,))
    with pytest.raises(sqlite3.DatabaseError):
        seeded.execute("DELETE FROM productivity_norms WHERE id=? AND version=1", (n,))
    wf.submit_norm(seeded, ESTIMATOR, n)
    wf.approve_norm(seeded, COMMERCIAL, n)
    assert wf.get_norm(seeded, n, 1)["status"] == "Superseded"
    with pytest.raises(ImmutableRecord):
        wf.reject_norm(seeded, COMMERCIAL, n, "no")


def test_norm_needs_source_and_cannot_be_self_approved(seeded):
    n = wf.create_norm(seeded, ESTIMATOR, id="NRM-S", trade="t", activity="a", output_unit="m", basis="labour_hours_per_unit", value="1", crew=CREW)
    with pytest.raises(ValidationFailed) as e:
        wf.submit_norm(seeded, ESTIMATOR, n)
    assert e.value.code == "NORM_SOURCE_REQUIRED"
    wf.revise_norm(seeded, ESTIMATOR, n, source="s", effective_from="2026-01-01")
    wf.submit_norm(seeded, ESTIMATOR, n)
    seeded_settings = __import__("app.config", fromlist=["x"]).get_settings()
    seeded_settings.allow_self_approval = False
    with pytest.raises(ApprovalBlocked) as e:
        wf.approve_norm(seeded, Actor("est", "Administrator", "x"), n)       # same username as author, Administrator role: still blocked for governed norms
    assert e.value.code == "SELF_APPROVAL_BLOCKED"


def test_profile_band_and_approval(seeded):
    with pytest.raises(ValidationFailed) as e:
        profile(seeded, "WP-X", "sme", roles={"fitter": 40})                  # 40 is outside the configured SME band 4-15
    assert e.value.code == "ARCHETYPE_BAND"
    with pytest.raises(ValidationFailed):
        profile(seeded, "WP-N", "sme", shifts=2)                              # night efficiency must be entered
    p = profile(seeded)
    assert wf.get_profile(seeded, p)["label"].startswith("Configurable company planning assumption")
    wf.submit_profile(seeded, ESTIMATOR, p)
    wf.approve_profile(seeded, COMMERCIAL, p)
    with pytest.raises(sqlite3.DatabaseError):
        seeded.execute("UPDATE workforce_profiles SET roles_json='{}' WHERE id=?", (p,))


def activities(proj_, norm_id="NRM-1"):
    return [dict(code="A1", name="Concrete A", boq_item_key="1.1", norm_id=norm_id, crews=2, work_fronts=2, fixed_days={"curing": 2}),
            dict(code="A2", name="Concrete B", boq_item_key="1.2", norm_id=norm_id, predecessors="A1")]


def test_programme_gaps_provisional_and_baseline_gate(seeded, proj):
    n = norm(seeded)
    p = profile(seeded)
    wf.set_activities(seeded, ESTIMATOR, proj, activities(proj))
    with pytest.raises(ValidationFailed) as e:                                # unapproved profile
        wf.build_programme(seeded, proj, p)
    assert e.value.code == "PROFILE_NOT_APPROVED"
    r = wf.build_programme(seeded, proj, p, allow_provisional=True)
    assert r["provisional"] and not r["complete"] and r["claims"].startswith("PROVISIONAL - NOT FOR RELIANCE")
    # quantity comes from the BOQ: 10 m3 / 2 per crew-day = 5 crew-days, 2 crews -> 3 d (+2 curing); A2: 5 m3 -> 3 crew-days on 2 fronts? crews default 1 -> 3 d
    by = {a["code"]: a for a in r["activities"]}
    assert by["A1"]["crew_days"] == "5.00" and by["A1"]["unconstrained_wd"] == 5 and by["A2"]["crew_days"] == "2.50"
    # without provisional approval the norm is a reported gap, never a silent zero
    approve_norm(seeded, n)
    wf.submit_profile(seeded, ESTIMATOR, p)
    wf.approve_profile(seeded, COMMERCIAL, p)
    r2 = wf.build_programme(seeded, proj, p)
    assert r2["synthetic"] and r2["claims"].startswith("PROVISIONAL")            # synthetic inputs can never read as 'based on approved norms'
    assert r2["working_days"] == 5 + 3 and not r2["gaps"] == []                  # A1: ceil(5/2)=3 +2 curing = 5; A2: ceil(2.5)=3
    # a baseline built on a provisional (here: unapproved-profile) scenario cannot be approved
    q = profile(seeded, "WP-Q")
    v = wf.save_baseline(seeded, ESTIMATOR, proj, q, allow_provisional=True)
    with pytest.raises(ValidationFailed) as e:
        wf.approve_baseline(seeded, COMMERCIAL, proj, v)
    assert e.value.code == "BASELINE_PROVISIONAL"
    v2 = wf.save_baseline(seeded, ESTIMATOR, proj, p)
    wf.approve_baseline(seeded, COMMERCIAL, proj, v2)
    assert wf.latest_baseline(seeded, proj, approved_only=True)["version_no"] == v2


def test_scenarios_and_forecast(seeded, proj):
    n = norm(seeded)
    approve_norm(seeded, n)
    small = profile(seeded, "WP-S", "custom", roles={"fitter": 2, "helper": 1})
    big = profile(seeded, "WP-B", "mid", roles={"fitter": 10, "helper": 6}, indirect={"foreman": 3})
    for x in (small, big):
        wf.submit_profile(seeded, ESTIMATOR, x)
        wf.approve_profile(seeded, COMMERCIAL, x)
    wf.set_activities(seeded, ESTIMATOR, proj, activities(proj))
    s = wf.crew_scenarios(seeded, proj, [small, big])
    a, b = s["scenarios"]
    # small: 1 crew only: A1 5 + 2 curing, A2 3 -> 10 ; big: A1 on 2 crews 3 +2, A2 3 -> 8
    assert a["working_days"] == 10 and b["working_days"] == 8 and a["peak_workers"] == 3 and b["peak_workers"] == 6
    assert b["working_days"] > a["working_days"] / 2                                   # doubling-plus the crews does not halve the programme
    assert a["resource_limited"] == ["A1"] and a["cost"]["computed"] is False       # no role cost entered -> cost impact not invented
    wf.save_baseline(seeded, ESTIMATOR, proj, big)
    fc = wf.forecast_vs_baseline(seeded, proj, {"A1": 100}, status_wd=6)
    assert fc["baseline_wd"] == 8 and fc["forecast_wd"] == 9 and fc["variance_wd"] == 1


def test_missing_calendar_blocks(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    p = profile(seeded)
    wf.set_activities(seeded, ESTIMATOR, pid, activities(pid))
    with pytest.raises(ValidationFailed) as e:
        wf.build_programme(seeded, pid, p, allow_provisional=True)
    assert e.value.code == "CALENDAR_REQUIRED"


def test_baseline_bridge_to_schedule(seeded, proj):
    n = norm(seeded, is_synthetic=False, evidence_status="unverified", origin="user")
    approve_norm(seeded, n)
    p = profile(seeded, is_synthetic=False)
    wf.submit_profile(seeded, ESTIMATOR, p)
    wf.approve_profile(seeded, COMMERCIAL, p)
    wf.set_activities(seeded, ESTIMATOR, proj, activities(proj))
    v = wf.save_baseline(seeded, ESTIMATOR, proj, p, allow_unconfirmed_calendar=True)
    assert wf.baseline_to_schedule_tasks(seeded, ESTIMATOR, proj, v) == 2
    from app.services import programme
    rep = programme.schedule_report(seeded, proj, include_unapproved=True)
    assert rep["project_working_days"] == wf.latest_baseline(seeded, proj)["result"]["working_days"]
