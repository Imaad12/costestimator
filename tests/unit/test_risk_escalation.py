"""Quantified risk (expected value, seeded Monte Carlo) and time-phased escalation. Analyses only: they propose, never change a policy or estimate."""
from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest

from app.core.errors import PermissionDenied, ValidationFailed
from app.estimators import escalation as esc
from app.estimators import montecarlo as mc
from app.estimators.estimate import compute_estimate
from app.services import analysis, governed, indirects, registers, risk
from tests.conftest import COMMERCIAL, ESTIMATOR, VIEWER
from tests.helpers import build_mini


# ------------------------------------------------------------------ pure
RISKS = [mc.RiskIn("R1", "Ground conditions", D("0.5"), D(100), D(200), D(300), D(10)), mc.RiskIn("R2", "Fixed event", D(1), D(10), D(10), D(10))]
RANGES = [mc.RangeIn("rebar", D(-20), D(0), D(50))]               # deviation from the value in the estimate: mean (−20+0+50)/3 = 10


def test_expected_value_hand_calculated():
    ev = mc.expected_value(RISKS, RANGES)
    assert ev["per_risk"] == {"R1": D(100), "R2": D(10)} and ev["per_range"] == {"rebar": D(10)} and ev["total"] == D(120)


def test_simulation_is_reproducible_ordered_and_close_to_expected_value():
    a = mc.simulate(RISKS, RANGES, 20000, 7)
    b = mc.simulate(RISKS, RANGES, 20000, 7)
    c = mc.simulate(RISKS, RANGES, 20000, 8)
    assert a == b and a["mean"] != c["mean"]                                       # same seed -> identical ; other seed -> different
    assert abs(a["mean"] - 120) < 5                                                # sampling error ~0.8 at this size
    p = a["percentiles"]
    assert p["P10"] <= p["P50"] <= p["P80"] <= p["P90"] and a["min"] <= p["P10"] and p["P90"] <= a["max"]
    assert abs(a["per_risk"][0]["occurred_pct"] - 50) < 2 and a["per_risk"][1]["occurred_pct"] == 100
    assert sum(h["count"] for h in a["histogram"]) == 20000
    assert a["schedule_days"]["P90"] >= a["schedule_days"]["P50"]


def test_degenerate_cases_are_exact():
    r = mc.simulate([mc.RiskIn("X", "sure thing", D(1), D(100), D(100), D(100))], [], 1000, 1)
    assert set(r["percentiles"].values()) == {D(100)} and r["mean"] == 100 and r["std_dev"] == 0
    r0 = mc.simulate([mc.RiskIn("X", "never", D(0), D(100), D(200), D(300))], [], 1000, 1)
    assert r0["mean"] == 0 and r0["max"] == 0


def test_invalid_inputs_refused():
    for bad in (mc.RiskIn("B", "x", D("1.1"), D(1), D(2), D(3)), mc.RiskIn("B", "x", D("0.5"), D(5), D(2), D(3)), mc.RiskIn("B", "x", D("0.5"), D(-1), D(2), D(3))):
        with pytest.raises(ValidationFailed):
            mc.simulate([bad], [], 1000, 1)
    with pytest.raises(ValidationFailed):
        mc.simulate(RISKS, [], 10, 1)                                              # too few trials


def test_escalation_factor_and_phasing_hand_calculated():
    assert abs(esc.factor(D(10), D(12)) - D("1.1")) < D("1e-20")
    assert abs(esc.factor(D(10), D(6)) - D("1.0488088481701515469914535")) < D("1e-20")                  # sqrt(1.1)
    assert esc.factor(D(10), D(0)) == 1 and esc.factor(D(10), D(-3)) == 1                                  # no de-escalation before the base date
    r = esc.phase({"2026-03": D(1000), "2026-09": D(1000)}, {"2026-03": date(2026, 3, 15), "2026-09": date(2026, 9, 15)}, date(2026, 3, 15), D(10))
    assert r["rows"][0]["factor"] == 1 and abs(r["rows"][1]["escalated"] - D("1048.8088481701515469914535")) < D("1e-18")
    assert abs(r["escalation_total"] - D("48.8088481701515469914535")) < D("1e-18")
    with pytest.raises(ValidationFailed):
        esc.factor(D(-100), D(6))


# ------------------------------------------------------------------ services
@pytest.fixture()
def proj(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    r1 = registers.add_risk(seeded, ESTIMATOR, pid, "Ground conditions")
    registers.add_risk(seeded, ESTIMATOR, pid, "Unquantified supply risk")
    registers.quantify_risk(seeded, ESTIMATOR, r1, prob_pct="50", cost_low="100", cost_likely="200", cost_high="300", basis="Analogue project P-12 (test)")
    return pid


def test_quantify_risk_validation(seeded, proj):
    rid = registers.list_risks(seeded, proj)[0]["id"]
    with pytest.raises(ValidationFailed) as e:
        registers.quantify_risk(seeded, ESTIMATOR, rid, prob_pct="50", cost_low="1", cost_likely="2", cost_high="3", basis="")
    assert e.value.code == "RISK_BASIS"
    for kw in (dict(prob_pct="120", cost_low="1", cost_likely="2", cost_high="3"), dict(prob_pct="50", cost_low="3", cost_likely="2", cost_high="1"),
               dict(prob_pct="x", cost_low="1", cost_likely="2", cost_high="3")):
        with pytest.raises(ValidationFailed):
            registers.quantify_risk(seeded, ESTIMATOR, rid, basis="b", **kw)
    with pytest.raises(PermissionDenied):
        registers.quantify_risk(seeded, VIEWER, rid, prob_pct="50", cost_low="1", cost_likely="2", cost_high="3", basis="b")


def test_risk_report_proposes_provision_and_compares_with_policy(seeded, proj):
    i = governed.propose(seeded, ESTIMATOR, "range_item", "rebar", {"name": "Rebar price movement", "low": "80", "likely": "100", "high": "150", "basis": "Supplier range (test)"},
                         project_id=proj, source="Quotations Q1-Q3 (test)", submit=True)
    governed.approve(seeded, COMMERCIAL, i)
    rep = risk.risk_report(seeded, proj, trials=5000, seed=3, target_pct=80)
    est = compute_estimate(seeded, proj)
    assert rep["expected_value"]["per_risk"] == {"RSK-" + proj + "-001": D(100)} and rep["expected_value"]["per_range"]["Rebar price movement"] == D(10)
    assert rep["expected_value"]["total"] == D(110)                                                        # 50% x 200 + range deviation mean (-20+0+50)/3
    assert rep["target"] == "P80" and rep["proposed_provision"] == rep["simulation"]["percentiles"]["P80"]
    assert rep["policy_provision"] == est.commercial.contingency + est.commercial.risk
    assert rep["difference_vs_policy"] == rep["proposed_provision"] - rep["policy_provision"]
    assert "PROPOSAL ONLY" in rep["note"] and any("NOT in the simulation" in n for n in rep["notes"])
    assert compute_estimate(seeded, proj).fingerprint == est.fingerprint                                   # the analysis changed nothing
    rid = analysis.save_run(seeded, ESTIMATOR, proj, "monte_carlo", {"trials": 5000, "seed": 3}, rep, inputs_hash=analysis.digest(rep["inputs"]))
    assert analysis.get_run(seeded, rid)["params"]["seed"] == 3
    assert risk.risk_report(seeded, proj, trials=5000, seed=3)["simulation"]["mean"] == rep["simulation"]["mean"]


def test_risk_report_needs_quantified_inputs(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    with pytest.raises(ValidationFailed) as e:
        risk.risk_report(seeded, pid)
    assert e.value.code == "RISK_NONE"


def _calendar_and_tasks(db, pid):
    c = governed.propose(db, ESTIMATOR, "calendar", "PROJECT", {"start_date": "2026-03-01", "work_weekdays": [6, 0, 1, 2, 3], "holidays": []}, project_id=pid, source="contract (test)", submit=True)
    governed.approve(db, COMMERCIAL, c)
    indirects.set_tasks(db, ESTIMATOR, pid, [{"task_code": "T1", "name": "All works", "duration_days": "10", "cost_code": "C"}])


def _profile(db, pid, code, **data):
    base = {"name": code, "annual_pct": "10", "base_date": "2026-03-15", "scope_kind": "all", "basis": "Company view (test)"}
    base.update(data)
    i = governed.propose(db, ESTIMATOR, "escalation_profile", code, base, project_id=pid, source="test", submit=True)
    governed.approve(db, COMMERCIAL, i)


def test_escalation_report_hand_calculated_and_scoped(seeded, proj):
    with pytest.raises(ValidationFailed) as e:
        risk.escalation_report(seeded, proj)
    assert e.value.code == "ESC_NONE"
    _profile(seeded, proj, "ALL", base_date="2026-01-15")
    with pytest.raises(ValidationFailed) as e:
        risk.escalation_report(seeded, proj)
    assert e.value.code == "CALENDAR_REQUIRED"
    _calendar_and_tasks(seeded, proj)
    est = compute_estimate(seeded, proj)
    rep = risk.escalation_report(seeded, proj, est=est)
    total = est.direct.direct_cost_total                                                                   # all cost lands in March 2026 (10 Sun-Thu working days from 1 Mar = 1-26 Mar)
    f = D(str(1.1 ** (2 / 12)))                                                                           # Jan 15 -> Mar 15 = 2 months
    pr = rep["profiles"][0]
    assert [p["period"] for p in pr["periods"]] == ["2026-03"] and pr["base_total"] == total                # 10 Sun-Thu working days from 1 Mar end on 12 Mar
    assert abs(pr["escalated_total"] - total * f) < D("0.000001") and abs(rep["escalation_total"] - total * (f - 1)) < D("0.000001")
    assert rep["not_covered_by_any_profile"] == 0 and rep["policy_escalation"] is not None


def test_escalation_scope_by_kind_and_overlap_protection(seeded, proj):
    _calendar_and_tasks(seeded, proj)
    _profile(seeded, proj, "LAB", scope_kind="labour", base_date="2026-03-15", annual_pct="12")
    est = compute_estimate(seeded, proj)
    rep = risk.escalation_report(seeded, proj, est=est)
    lab = sum(l.amount for l in est.direct.lines if l.kind == "labour")
    mat = sum(l.amount for l in est.direct.lines if l.kind == "material")
    assert lab > 0 and mat > 0 and rep["scheduled_base_total"] == lab and rep["not_covered_by_any_profile"] == est.direct.direct_cost_total - lab       # materials untouched
    _profile(seeded, proj, "EVERYTHING", scope_kind="all")
    with pytest.raises(ValidationFailed) as e:
        risk.escalation_report(seeded, proj)
    assert e.value.code == "ESC_OVERLAP"                                                                   # would escalate labour twice
