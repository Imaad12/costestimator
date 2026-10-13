"""Benchmarks, reserves, engineering effort and overhead pools: user-supplied ranges/percentages, Draft proposals only, hand-calculated (SYNTHETIC)."""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.core.errors import PermissionDenied, ValidationFailed
from app.estimators.estimate import compute_estimate
from app.services import governed, indirects, provisions
from app.services.rates import create_resource
from tests.conftest import AI, COMMERCIAL, ESTIMATOR, VIEWER
from tests.helpers import approved_rate, build_mini


@pytest.fixture()
def proj(seeded, tmp_path):
    return build_mini(seeded, tmp_path)


def _ok(db, kind, code, data, pid=None, who=COMMERCIAL):
    i = governed.propose(db, ESTIMATOR, kind, code, data, project_id=pid, source="Company records (test)", submit=True)
    governed.approve(db, who, i)
    return i


# ------------------------------------------------------------------ benchmarks
def test_benchmark_validation(seeded):
    bad = [dict(name="x", metric="item_unit_cost", cost_prefix="C", unit="m3", low="1", high="2", source_note="s"),                              # needs currency
           dict(name="x", metric="item_unit_cost", cost_prefix="C", unit="m3", low="5", high="2", currency="SAR", source_note="s"),            # low > high
           dict(name="x", metric="share_of_direct", low="1", high="2", source_note="s"),                                                      # needs kind
           dict(name="x", metric="share_of_direct", kind="labour", low="1", high="150", source_note="s"),
           dict(name="x", metric="weird", low="1", high="2", source_note="s")]
    for b in bad:
        with pytest.raises(ValidationFailed):
            governed.propose(seeded, ESTIMATOR, "benchmark_range", "B", b, source="s")


def test_benchmark_report_flags_outliers_and_says_nothing_without_ranges(seeded, proj):
    assert provisions.benchmark_report(seeded, proj)["rows"] == [] and "no reasonableness check" in provisions.benchmark_report(seeded, proj)["note"]
    # item 1.1: 10 m3 -> cost 1250 -> SAR 125 per m3 ; labour total 300 of 1875 = 16 % ; hours per m3 = 2
    _ok(seeded, "benchmark_range", "UC-OK", dict(name="Concrete SAR/m3 (test)", metric="item_unit_cost", cost_prefix="C", unit="m3", low="100", high="150", currency="SAR", source_note="Closed jobs 2025 (test)"), proj)
    _ok(seeded, "benchmark_range", "UC-HI", dict(name="Concrete SAR/m3 low band (test)", metric="item_unit_cost", cost_prefix="C", unit="m3", low="10", high="100", currency="SAR", source_note="Old job (test)"), proj)
    _ok(seeded, "benchmark_range", "SH", dict(name="Labour share (test)", metric="share_of_direct", kind="labour", low="20", high="40", source_note="Company average (test)"), proj)
    _ok(seeded, "benchmark_range", "HR", dict(name="Hours per m3 (test)", metric="hours_per_unit", cost_prefix="C", unit="m3", low="1", high="3", source_note="Time sheets (test)"), proj)
    _ok(seeded, "benchmark_range", "USD", dict(name="Concrete USD/m3 (test)", metric="item_unit_cost", cost_prefix="C", unit="m3", low="1", high="2", currency="USD", source_note="Foreign job (test)"), proj)
    r = provisions.benchmark_report(seeded, proj)
    st = {(x["benchmark"], x["subject"]): (x["status"], x["value"]) for x in r["rows"]}
    assert st[("UC-OK", "1.1")] == ("Within range", D(125)) and st[("UC-HI", "1.1")] == ("Above range", D(125)) and st[("UC-OK", "1.2")][0] == "Within range"
    sh = next(x for x in r["rows"] if x["benchmark"] == "SH")
    assert sh["status"] == "Below range" and abs(sh["value"] - D(300) * 100 / D(1875)) < D("0.0001")                    # labour 20 + 10 = 30 per... total labour 15 m3 x 20 = 300
    assert st[("HR", "1.1")] == ("Within range", D(2)) and all(x["status"] == "Not comparable" for x in r["rows"] if x["benchmark"] == "USD")
    assert {(x["benchmark"], x["subject"]) for x in r["outside"]} == {("UC-HI", "1.1"), ("UC-HI", "1.2"), ("SH", "labour share of direct %")}


# ------------------------------------------------------------------ reserves
def test_reserve_proposals_are_draft_indirects_with_hand_calculated_amounts(seeded, proj):
    with pytest.raises(ValidationFailed) as e:
        provisions.reserve_proposals(seeded, ESTIMATOR, proj)
    assert e.value.code == "RESERVE_NONE"
    _ok(seeded, "reserve_rule", "WARR", dict(name="Defects liability reserve", base="direct", pct="1.5", category="Warranty", basis="Contract cl. 20 (test)"), proj)
    _ok(seeded, "reserve_rule", "COMM", dict(name="Commissioning reserve", base="selling_price", pct="0.5", category="Commissioning", basis="Company policy (test)"), proj)
    est = compute_estimate(seeded, proj)
    out = {o["code"]: o for o in provisions.reserve_proposals(seeded, ESTIMATOR, proj)}
    assert out["RSV-WARR"]["amount"] == D("28.13") and out["RSV-COMM"]["amount"] == (est.commercial.net_price * D("0.005")).quantize(D("0.01"), "ROUND_HALF_UP")   # 1.5% of 1875 = 28.125
    rows = {i["code"]: i for i in indirects.list_indirects(seeded, proj)}
    assert rows["RSV-WARR"]["status"] == "Draft" and rows["RSV-WARR"]["source"] == "reserve rule"
    again = provisions.reserve_proposals(seeded, ESTIMATOR, proj)                                                               # idempotent: revises the draft
    assert {o["action"] for o in again} == {"revised"} and sum(1 for i in indirects.list_indirects(seeded, proj) if i["code"] == "RSV-WARR") == 1
    with pytest.raises(PermissionDenied):
        provisions.reserve_proposals(seeded, VIEWER, proj)


# ------------------------------------------------------------------ engineering
def test_engineering_effort_costing_hand_calculated_and_unpriced_blocks(seeded, proj):
    create_resource(seeded, ESTIMATOR, resource_type="labour", description="DEMO design engineer", unit="hr", cost_code="C", id="DEMO-ENG", is_synthetic=True)
    create_resource(seeded, ESTIMATOR, resource_type="labour", description="DEMO drafter (no rate)", unit="hr", cost_code="C", id="DEMO-DRAFT", is_synthetic=True)
    approved_rate(seeded, "DEMO-ENG", "80")
    _ok(seeded, "engineering_basis", "CIV-DWG", dict(discipline="Civil", deliverable="General arrangement drawings", count="12", hours_each="30", resource_id="DEMO-ENG", basis="Last similar job (test)"), proj, who=COMMERCIAL)
    _ok(seeded, "engineering_basis", "CIV-CALC", dict(discipline="Civil", deliverable="Design calculations", count="4", hours_each="50", resource_id="DEMO-ENG", basis="Last similar job (test)"), proj)
    _ok(seeded, "engineering_basis", "ELE-DWG", dict(discipline="Electrical", deliverable="Single line diagrams", count="5", hours_each="20", resource_id="DEMO-ENG", basis="Last similar job (test)"), proj)
    r = provisions.engineering_report(seeded, proj)
    assert r["by_discipline"]["Civil"]["hours"] == D(560) and r["by_discipline"]["Civil"]["cost"] == D(44800) and r["by_discipline"]["Electrical"]["cost"] == D(8000)    # 12x30+4x50 ; x80
    assert r["total_hours"] == D(660) and r["total_cost"] == D(52800) and r["unpriced_lines"] == 0
    out = {o["code"]: o for o in provisions.propose_engineering_indirects(seeded, ESTIMATOR, proj)}
    assert out["ENG-CIVIL"]["amount"] == D(44800) and {i["code"]: i["status"] for i in indirects.list_indirects(seeded, proj)}["ENG-ELECTRICAL"] == "Draft"
    _ok(seeded, "engineering_basis", "DRAFT", dict(discipline="Architecture", deliverable="Detail drawings", count="10", hours_each="10", resource_id="DEMO-DRAFT", basis="b"), proj)
    r2 = provisions.engineering_report(seeded, proj)
    assert r2["unpriced_lines"] == 1 and r2["by_discipline"]["Architecture"]["unpriced_hours"] == D(100)
    with pytest.raises(ValidationFailed) as e:
        provisions.propose_engineering_indirects(seeded, ESTIMATOR, proj)
    assert e.value.code == "ENG_UNPRICED"


# ------------------------------------------------------------------ overhead pool
def test_overhead_pool_share_hand_calculated(seeded, proj):
    est = compute_estimate(seeded, proj)
    _ok(seeded, "overhead_pool", "HO", dict(name="Head office", annual_cost="2400000", annual_base="48000000", base_kind="direct_cost", basis="FY25 accounts (test)"))          # 5 % of direct
    _ok(seeded, "overhead_pool", "HRS", dict(name="Engineering office", annual_cost="1000000", annual_base="200000", base_kind="labour_hours", basis="FY25 accounts (test)"))      # SAR 5 per labour hour
    r = {x["pool"]: x for x in provisions.overhead_report(seeded, proj, est=est)["rows"]}
    assert r["HO"]["recovery_rate_pct"] == D(5) and r["HO"]["share"] == D("93.75")                          # 5% x 1875
    assert r["HRS"]["share"] == D(150)                                                                      # 30 labour hours x ... 15 m3 x 2 h = 30 h x 5 = 150
    out = provisions.propose_overhead_indirects(seeded, ESTIMATOR, proj)
    assert {o["code"]: o["amount"] for o in out} == {"OH-HO": D("93.75"), "OH-HRS": D(150)}
    with pytest.raises(ValidationFailed):
        provisions.overhead_report(seeded, proj, pool_code="NOPE")
