"""Cash flow, retention, bonds and financing: monthly engine checked against a hand-worked schedule (SYNTHETIC terms)."""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.core.errors import PermissionDenied, ValidationFailed
from app.estimators import cashflow as cf
from app.estimators.estimate import compute_estimate
from app.services import cashflow, governed, indirects
from tests.conftest import COMMERCIAL, ESTIMATOR, VIEWER
from tests.helpers import build_mini

TERMS = dict(advance_pct="10", retention_pct="5", retention_release_at_completion_pct="50", defects_months="12", certification_lag_months="1", payment_lag_months="0",
             supplier_payment_lag_months="0", financing_rate_annual_pct="12", performance_bond_pct="10", performance_bond_fee_annual_pct="2")


def test_cashflow_hand_worked_schedule():
    r = cf.build({0: D(100), 1: D(200), 2: D(100)}, D(500), TERMS)
    # valuations 125/250/125 ; advance 50 ; recovery 12.5/25/12.5 ; retention 6.25/12.5/6.25 (=25) ; received at months 1,2,3 ; retention 12.5 at m3, 12.5 at m14
    bal = {x["month"]: x["balance"] for x in r["rows"]}
    assert [v["value"] for v in r["valuations"]] == [D(125), D(250), D(125)] and r["retention_total"] == D(25) and r["advance"] == D(50)
    assert bal[0] == D(-50) and bal[1] == D("-144.25") and bal[2] == D("-33.1925") and bal[3] == D("85.225575")                # 1% monthly on negative opening balances
    assert r["interest_total"] == D("2.274425") and r["peak_funding"] == D("144.25") and r["peak_funding_month"] == 1
    assert bal[14] == D("97.725575") == r["final_balance"] == D(500) - D(400) - r["interest_total"]                              # price - cost - interest
    assert r["performance_bond_cost"] == D("1.25") and r["bond_months"] == 15                                                    # 500 x 10% x 2% x 15/12
    assert len(r["rows"]) == 15 and all(len(x) == 6 for x in r["rows"]) and len(r["assumptions"]) == 4


def test_supplier_credit_and_zero_financing_cases():
    t = dict(TERMS, advance_pct="0", retention_pct="0", supplier_payment_lag_months="2", financing_rate_annual_pct="0", performance_bond_pct="0",
             certification_lag_months="0", defects_months="0", retention_release_at_completion_pct="100")
    r = cf.build({0: D(100), 1: D(100)}, D(240), t)
    assert r["interest_total"] == 0 and r["performance_bond_cost"] == 0 and r["final_balance"] == D(40)                           # no financing cost: price 240 - cost 200
    assert [x["balance"] for x in r["rows"]] == [D(120), D(240), D(140), D(40)] and r["peak_funding"] == 0                     # valuations arrive before suppliers are paid


def test_invalid_inputs():
    with pytest.raises(ValidationFailed):
        cf.build({}, D(100), TERMS)
    with pytest.raises(ValidationFailed):
        cf.build({0: D(10)}, None, TERMS)
    with pytest.raises(KeyError):
        cf.build({0: D(10)}, D(20), {k: v for k, v in TERMS.items() if k != "advance_pct"})                                     # nothing defaulted


def test_terms_validation(seeded):
    with pytest.raises(ValidationFailed):
        governed.propose(seeded, ESTIMATOR, "payment_terms", "T", {"name": "x", **{k: v for k, v in TERMS.items() if k != "retention_pct"}}, source="s")
    with pytest.raises(ValidationFailed):
        governed.propose(seeded, ESTIMATOR, "payment_terms", "T", {"name": "x", **TERMS, "defects_months": "1.5"}, source="s")
    with pytest.raises(ValidationFailed):
        governed.propose(seeded, ESTIMATOR, "payment_terms", "T", {"name": "x", **TERMS, "retention_pct": "150"}, source="s")


@pytest.fixture()
def proj(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    c = governed.propose(seeded, ESTIMATOR, "calendar", "PROJECT", {"start_date": "2026-03-01", "work_weekdays": [6, 0, 1, 2, 3], "holidays": []}, project_id=pid, source="contract (test)", submit=True)
    governed.approve(seeded, COMMERCIAL, c)
    indirects.set_tasks(seeded, ESTIMATOR, pid, [{"task_code": "A", "name": "Phase 1", "duration_days": "20", "cost_code": "C"}])
    return pid


def test_service_report_proposals_and_estimate_unchanged(seeded, proj):
    with pytest.raises(ValidationFailed) as e:
        cashflow.cashflow_report(seeded, proj)
    assert e.value.code == "TERMS_NONE"
    t = governed.propose(seeded, ESTIMATOR, "payment_terms", "CONTRACT", {"name": "Contract terms (SYNTHETIC)", **TERMS}, project_id=proj, source="Contract clause 14 (test)", submit=True)
    governed.approve(seeded, COMMERCIAL, t)
    est = compute_estimate(seeded, proj)
    r = cashflow.cashflow_report(seeded, proj, est=est)
    assert r["price"] == est.commercial.net_price and r["total_cost"] == est.direct.direct_cost_total and r["terms"]["code"] == "CONTRACT"
    # money conserved under the documented convention: indirects (500) are paid with the direct cost; contingency/margin are not cash-out
    rc = r["reconciliation"]
    assert r["complete"] and abs(rc["cash_out_total"] - (est.direct.direct_cost_total + est.indirect.total)) < D("0.0001") and all(c["ok"] for c in rc["checks"])
    assert abs(r["final_balance"] - (r["price"] - rc["cash_out_total"] - r["interest_total"])) < D("0.0001")
    before = compute_estimate(seeded, proj)
    out = cashflow.propose_financing_indirects(seeded, ESTIMATOR, proj)
    rows = {i["code"]: i for i in indirects.list_indirects(seeded, proj)}
    assert set(out["indirect_codes"]) == {"FIN-BOND", "FIN-INTEREST"} and rows["FIN-BOND"]["status"] == "Draft" and rows["FIN-BOND"]["source"] == "cash-flow analysis"
    after = compute_estimate(seeded, proj)
    assert after.indirect.total == before.indirect.total and after.commercial.net_price == before.commercial.net_price         # drafts add no cost to the price
    assert any("FIN-BOND" in e["message"] and "Draft" in e["message"] for e in after.exceptions)                              # flagged as unapproved, not silently priced
    with pytest.raises(PermissionDenied):
        cashflow.propose_financing_indirects(seeded, VIEWER, proj)
