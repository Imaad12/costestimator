"""Variations (priced from approved rates, approved by a Commercial Approver) and earned-value reporting: hand-calculated (SYNTHETIC figures)."""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.core.errors import ApprovalBlocked, Conflict, NotFound, PermissionDenied, ValidationFailed
from app.estimators import evm
from app.reporting import history
from app.services import controls, governed, indirects, wbs
from app.services.rates import create_resource
from tests.conftest import AI, COMMERCIAL, ESTIMATOR, PROCUREMENT, VIEWER
from tests.helpers import build_mini


def test_evm_arithmetic_and_undefined_ratios():
    m = evm.metrics(D(1875), D("937.5"), D(750), D(800))
    assert m["CV"] == D(-50) and m["SV"] == D("-187.5") and m["CPI"] == D("0.9375") and m["SPI"] == D("0.8")
    assert m["EAC_cpi"] == D(2000) and m["ETC_cpi"] == D(1200) and m["VAC_cpi"] == D(-125) and m["EAC_remaining_at_budget"] == D(1925)
    assert m["TCPI"] == D(1125) / D(1075) and m["percent_complete"] == D(40)
    z = evm.metrics(D(100), D(0), D(0), D(0))
    assert z["CPI"] is None and z["SPI"] is None and z["EAC_cpi"] is None                       # undefined, never zero / infinity
    assert evm.planned_pct(D(3), D(0), D(4)) == D("0.75") and evm.planned_pct(D(3), D(4), D(9)) == 0 and evm.planned_pct(D(20), D(4), D(9)) == 1
    assert evm.planned_pct(D(2), D(2), D(2)) == 1 and evm.planned_pct(D(1), D(2), D(2)) == 0   # milestone


@pytest.fixture()
def proj(seeded, tmp_path):
    return build_mini(seeded, tmp_path)


def _markup(db, pid):
    i = governed.propose(db, ESTIMATOR, "variation_markup", "VO", {"overhead_pct": "10", "profit_pct": "5", "contract_clause": "Cl. 13.3 (test)"}, project_id=pid, source="contract (test)", submit=True)
    governed.approve(db, COMMERCIAL, i)


def test_variation_pricing_lifecycle_and_authority(seeded, proj, settings):
    vid = controls.create_variation(seeded, ESTIMATOR, proj, "Additional foundations", instructed_by="Client rep", instruction_ref="VI-014", time_days="3")
    controls.add_line(seeded, ESTIMATOR, vid, "DEMO-MAT-001", 10)                           # 10 m3 x 100 = 1000
    controls.add_line(seeded, ESTIMATOR, vid, "DEMO-LAB-001", 20)                           # 20 h x 10 = 200
    controls.add_line(seeded, ESTIMATOR, vid, "DEMO-MAT-001", 2, direction="omit")          # omission -200
    pr = controls.price_variation(seeded, vid)
    assert pr["direct_total"] == D(1000) and pr["complete"] is False and "no approved variation_markup" in pr["blockers"]
    with pytest.raises(ValidationFailed) as e:
        controls.submit_variation(seeded, ESTIMATOR, vid)
    assert e.value.code == "VARIATION_INCOMPLETE"
    _markup(seeded, proj)
    pr = controls.price_variation(seeded, vid)
    assert pr["markup"]["overhead"] == D(100) and pr["markup"]["profit"] == D(55) and pr["amount"] == D(1155)           # 10% of 1000 ; 5% of 1100
    controls.submit_variation(seeded, ESTIMATOR, vid)
    with pytest.raises(Conflict):
        controls.add_line(seeded, ESTIMATOR, vid, "DEMO-MAT-001", 1)                        # locked once submitted
    for who in (AI, VIEWER, PROCUREMENT, ESTIMATOR):
        with pytest.raises(PermissionDenied):
            controls.decide_variation(seeded, who, vid, True, "ok")
    settings.allow_self_approval = False
    mine = controls.create_variation(seeded, COMMERCIAL, proj, "Raised by the approver")
    controls.add_line(seeded, COMMERCIAL, mine, "DEMO-MAT-001", 1)
    controls.submit_variation(seeded, COMMERCIAL, mine)
    with pytest.raises(ApprovalBlocked):
        controls.decide_variation(seeded, COMMERCIAL, mine, True, "ok")                     # nobody approves their own variation when self-approval is off
    with pytest.raises(ValidationFailed):
        controls.decide_variation(seeded, COMMERCIAL, vid, True, "")
    controls.decide_variation(seeded, COMMERCIAL, vid, True, "Valid instruction VI-014")
    assert seeded.one("SELECT status, amount FROM variations WHERE id=?", (vid,))["amount"] == "1155"
    assert seeded.one("SELECT COUNT(*) n FROM approvals WHERE entity_type='variation'")["n"] == 1
    with pytest.raises(Conflict):
        controls.decide_variation(seeded, COMMERCIAL, vid, False, "again")


def test_unpriced_resource_blocks_submission_never_priced_at_zero(seeded, proj):
    _markup(seeded, proj)
    create_resource(seeded, ESTIMATOR, resource_type="material", description="DEMO no-rate item", unit="nr", id="DEMO-NORATE", cost_code="C.01", is_synthetic=True)
    seeded_rate = seeded.one("SELECT 1 FROM resource_rates WHERE resource_id='DEMO-NORATE'")
    vid = controls.create_variation(seeded, ESTIMATOR, proj, "Extra item")
    controls.add_line(seeded, ESTIMATOR, vid, "DEMO-NORATE", 5)
    pr = controls.price_variation(seeded, vid)
    assert pr["unpriced_lines"] == 1 and pr["lines"][0]["amount"] is None and pr["amount"] is None and not pr["complete"]
    with pytest.raises(ValidationFailed):
        controls.submit_variation(seeded, ESTIMATOR, vid)
    for bad in (dict(resource_id="NOPE", quantity=1), dict(resource_id="DEMO-NORATE", quantity=0), dict(resource_id="DEMO-NORATE", quantity="x"), dict(resource_id="DEMO-NORATE", quantity=1, unit="kg")):
        with pytest.raises((ValidationFailed, NotFound)):
            controls.add_line(seeded, ESTIMATOR, vid, **bad)


def test_contract_status_original_plus_approved_variations(seeded, proj):
    with pytest.raises(ValidationFailed) as e:
        controls.contract_status(seeded, proj)
    assert e.value.code == "BASELINE_NONE"
    b = governed.propose(seeded, ESTIMATOR, "contract_baseline", "CONTRACT", {"contract_sum": "100000", "currency": "SAR", "award_date": "2026-09-01", "reference": "Contract C-1 (test)"},
                         project_id=proj, source="Signed contract (test)", submit=True)
    governed.approve(seeded, COMMERCIAL, b)
    _markup(seeded, proj)
    v1 = controls.create_variation(seeded, ESTIMATOR, proj, "VO 1", time_days="3")
    controls.add_line(seeded, ESTIMATOR, v1, "DEMO-MAT-001", 10); controls.add_line(seeded, ESTIMATOR, v1, "DEMO-LAB-001", 20); controls.add_line(seeded, ESTIMATOR, v1, "DEMO-MAT-001", 2, direction="omit")
    v2 = controls.create_variation(seeded, ESTIMATOR, proj, "VO 2", time_days="2")
    controls.add_line(seeded, ESTIMATOR, v2, "DEMO-MAT-001", 1)                         # 100 -> +10 oh -> +5.5 profit = 115.5
    controls.submit_variation(seeded, ESTIMATOR, v1); controls.submit_variation(seeded, ESTIMATOR, v2)
    controls.decide_variation(seeded, COMMERCIAL, v1, True, "approved")
    s = controls.contract_status(seeded, proj)
    assert s["original_contract_sum"] == 100000 and s["approved_variations"] == D(1155) and s["revised_contract_sum"] == D(101155) and s["pending_variations"] == D("115.5")
    assert s["exposure_if_pending_approved"] == D("101270.5") and s["approved_time_days"] == 3 and s["pending_time_days"] == 2
    assert s["cumulative_effect_pct"] == D(1155) / D(1000) and s["count"]["approved"] == 1 and s["count"]["pending"] == 1


def _programme(db, pid):
    wbs.add_node(db, ESTIMATOR, pid, "A1", "Area 1"); wbs.add_node(db, ESTIMATOR, pid, "A2", "Area 2")
    wbs.assign_items(db, ESTIMATOR, pid, {"1.1": "A1", "1.2": "A2"})
    c = governed.propose(db, ESTIMATOR, "calendar", "PROJECT", {"start_date": "2026-03-01", "work_weekdays": [6, 0, 1, 2, 3], "holidays": []}, project_id=pid, source="contract (test)", submit=True)
    governed.approve(db, COMMERCIAL, c)
    indirects.set_tasks(db, ESTIMATOR, pid, [{"task_code": "T1", "name": "Area 1", "duration_days": "4", "wbs_code": "A1", "cost_code": "C"},
                                              {"task_code": "T2", "name": "Area 2", "duration_days": "5", "predecessors": "T1", "wbs_code": "A2", "cost_code": "C"}])


def test_evm_report_hand_calculated(seeded, proj):
    _programme(seeded, proj)
    controls.record_progress(seeded, ESTIMATOR, proj, "T1", "2026-03-04", "60", "Quantities installed per site measure SM-3")
    history.record_actual(seeded, ESTIMATOR, proj, source="Ledger extract L-1 (test)", actual_amount="800", cost_date="2026-03-03")
    history.record_actual(seeded, ESTIMATOR, proj, source="Ledger extract L-2 (test)", actual_amount="9999", cost_date="2026-04-01")      # after the data date: excluded
    r = controls.evm_report(seeded, proj, "2026-03-04")
    m = r["metrics"]
    # items: 1.1 = 10 x (105 + 20) = 1250 -> T1 ; 1.2 = 5 x 125 = 625 -> T2 ; BAC 1875 ; 3 working days elapsed => T1 planned 75% => PV 937.5 ; EV 60% x 1250 = 750 ; AC 800
    assert m["BAC"] == D(1875) and m["PV"] == D("937.5") and m["EV"] == D(750) and m["AC"] == D(800)
    assert m["CPI"] == D("0.9375") and m["SPI"] == D("0.8") and m["EAC_cpi"] == D(2000) and m["VAC_cpi"] == D(-125) and m["EAC_remaining_at_budget"] == D(1925)
    assert r["no_progress_recorded"] == ["T2"] and r["unscheduled_budget"] == 0
    later = controls.evm_report(seeded, proj, "2026-04-05")                           # whole programme elapsed: PV = BAC ; AC now includes the later actual
    assert later["metrics"]["PV"] == D(1875) and later["metrics"]["AC"] == D(10799) and later["metrics"]["EV"] == D(750)


def test_progress_validation_and_frozen_version_baseline(seeded, proj):
    _programme(seeded, proj)
    for bad in (dict(task_code="T9", as_of="2026-03-04", pct="10", basis="b"), dict(task_code="T1", as_of="2026-03-04", pct="120", basis="b"),
                dict(task_code="T1", as_of="2026-03-04", pct="10", basis=""), dict(task_code="T1", as_of="nonsense", pct="10", basis="b")):
        with pytest.raises((ValidationFailed, NotFound)):
            controls.record_progress(seeded, ESTIMATOR, proj, **bad)
    from app.services import estimates
    vid = estimates.freeze_version(seeded, ESTIMATOR, proj, "baseline")
    from tests.helpers import approved_rate
    approved_rate(seeded, "DEMO-MAT-001", "500")                                          # live library moves on: the baseline must not
    base = controls.evm_report(seeded, proj, "2026-03-04", version_id=vid)
    live = controls.evm_report(seeded, proj, "2026-03-04")
    assert base["metrics"]["BAC"] == D(1875) and live["metrics"]["BAC"] != D(1875)
