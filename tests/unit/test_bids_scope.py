"""Bid evaluation, long-lead tracking and package interface matrix: hand-calculated, evidence-bearing, advisory only (SYNTHETIC)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest

from app.core.errors import NotFound, PermissionDenied, ValidationFailed
from app.estimators import bid_eval
from app.estimators.param_kinds import KINDS
from app.services import bids, boq, governed
from tests.conftest import AI, COMMERCIAL, ESTIMATOR, PROCUREMENT, VIEWER
from tests.helpers import build_mini

CRIT = {"name": "Package evaluation plan (SYNTHETIC)", "stage": "bid", "scale_max": "10", "price_weight": "50", "criteria": [
    {"id": "T1", "name": "Method statement", "weight": "30"}, {"id": "T2", "name": "Experience", "weight": "20", "min_score": "3"},
    {"id": "HSE", "name": "HSE accreditation", "pass_fail": True}]}


def test_weights_must_total_100_and_passfail_has_no_weight():
    ok = KINDS["evaluation_criteria"].validate(CRIT)
    assert ok["price_weight"] == "50" and [c["id"] for c in ok["criteria"]] == ["T1", "T2", "HSE"]
    for bad in ({**CRIT, "price_weight": "40"}, {**CRIT, "criteria": [{"id": "A", "name": "a", "weight": "50"}, {"id": "A", "name": "dup", "weight": "50"}]},
                {**CRIT, "criteria": [{"id": "PRICE", "name": "x", "weight": "50"}]}, {**CRIT, "criteria": [{"id": "H", "name": "h", "pass_fail": True, "weight": "10"}]},
                {**CRIT, "criteria": []}, {**CRIT, "stage": "nonsense"}):
        with pytest.raises(ValidationFailed):
            KINDS["evaluation_criteria"].validate(bad)


def test_evaluation_hand_calculated_with_gate_minimum_and_incomplete():
    cs = bid_eval.validate_criteria(CRIT)
    scores = {"Q1": {"T1": D(8), "T2": D(6), "HSE": D(1)}, "Q2": {"T1": D(5), "T2": D(7), "HSE": D(1)}, "Q3": {"T1": D(9), "T2": D(9), "HSE": D(0)},
              "Q4": {"T1": D(10), "T2": D(2), "HSE": D(1)}, "Q5": {"T1": D(7)}}
    prices = {"Q1": D(1000), "Q2": D(800), "Q3": D(500), "Q4": D(600), "Q5": D(700)}
    r = bid_eval.evaluate(cs, D(10), scores, prices)
    b = r["bids"]
    assert b["Q3"]["status"] == "Disqualified" and "HSE" in b["Q3"]["disqualified"][0]                 # fails the gate despite top scores and the lowest price
    assert b["Q4"]["status"] == "Disqualified" and "below minimum" in b["Q4"]["disqualified"][0]        # T2 minimum 3
    assert b["Q5"]["status"] == "Incomplete" and set(b["Q5"]["missing"]) == {"T2", "HSE"}
    assert r["lowest_qualifying_price"] == D(800)                                                      # the 500 and 600 bids do not set the price benchmark
    # Q1: 8/10x30 = 24 + 6/10x20 = 12 + price 50x800/1000 = 40 => 76 ; Q2: 15 + 14 + 50 = 79
    assert b["Q1"]["total"] == D(76) and b["Q2"]["total"] == D(79) and r["ranking"] == ["Q2", "Q1"] and b["Q2"]["rank"] == 1
    assert b["Q3"]["total"] is None and b["Q5"]["total"] is None


# ------------------------------------------------------------------ services
@pytest.fixture()
def world(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    for p in ("PKG-A", "PKG-B"):
        seeded.insert("procurement_packages", dict(id=p, project_id=pid, name=p, status="Open", created_by="t", created_at="2026-01-01"))
    for q in ("Q1", "Q2"):
        seeded.insert("suppliers", dict(id=f"S-{q}", name=f"Supplier {q} [SYNTHETIC]", qualification_status="Approved", is_synthetic=1, created_by="t", created_at="2026-01-01"))
        seeded.insert("quotations", dict(id=q, project_id=pid, package_id="PKG-A", supplier_id=f"S-{q}", status="Approved", currency="SAR", is_synthetic=1))
    i = governed.propose(seeded, ESTIMATOR, "evaluation_criteria", "EVAL-A", CRIT, project_id=pid, source="Tender evaluation plan rev 1 (test)", submit=True)
    governed.approve(seeded, PROCUREMENT, i)
    return pid


def test_scores_need_evidence_valid_ranges_and_authority(seeded, world):
    ok = lambda **kw: bids.record_score(seeded, ESTIMATOR, "PKG-A", kw.pop("q", "Q1"), "EVAL-A", kw.pop("c", "T1"), kw.pop("s", 7), kw.pop("e", "Bid section 3.2"))
    ok()
    for kw in (dict(e=""), dict(s=11), dict(s=-1), dict(s="x"), dict(c="NOPE"), dict(q="Q9"), dict(c="HSE", s=0.5)):
        with pytest.raises((ValidationFailed, NotFound, ValidationFailed)):
            ok(**kw)
    with pytest.raises(PermissionDenied):
        bids.record_score(seeded, AI, "PKG-A", "Q1", "EVAL-A", "T1", 5, "ev")
    with pytest.raises(PermissionDenied):
        bids.record_score(seeded, VIEWER, "PKG-A", "Q1", "EVAL-A", "T1", 5, "ev")
    with pytest.raises(NotFound):
        bids.record_score(seeded, ESTIMATOR, "PKG-A", "Q1", "NO-SUCH-CRITERIA", "T1", 5, "ev")


def test_report_uses_levelled_prices_and_latest_score(seeded, world):
    sc = lambda q, c, s: bids.record_score(seeded, ESTIMATOR, "PKG-A", q, "EVAL-A", c, s, f"evidence {q}/{c}")
    sc("Q1", "T1", 8); sc("Q1", "T2", 6); sc("Q1", "HSE", 1); sc("Q2", "T1", 4); sc("Q2", "T2", 7); sc("Q2", "HSE", 1)
    sc("Q2", "T1", 5)                                                                                   # re-score: latest wins, history kept
    assert seeded.one("SELECT COUNT(*) n FROM bid_scores WHERE quotation_id='Q2' AND criterion_id='T1'")["n"] == 2
    level = {"advisory": "lvl", "quotations": [dict(quotation_id="Q1", normalised_total=D(1000), like_for_like=True), dict(quotation_id="Q2", normalised_total=D(800), like_for_like=True)]}
    r = bids.evaluation_report(seeded, "PKG-A", "EVAL-A", level=level)
    assert r["ranking"] == ["Q2", "Q1"] and r["bids"]["Q2"]["total"] == D(79) and r["bids"]["Q1"]["total"] == D(76)
    assert "evidence Q2/T1" in r["bids"]["Q2"]["evidence"]["T1"] and "Advisory" in r["advisory"]
    assert seeded.one("SELECT COUNT(*) n FROM quote_selections")["n"] == 0                           # evaluation never selects or awards


def test_long_lead_dates_hand_calculated(seeded, world):
    pid = world
    a = bids.add_long_lead(seeded, ESTIMATOR, pid, "Transformer 33/11 kV", 20, "2026-12-01", planned_order_date="2026-07-01", vendor_data_due="2026-06-10")
    b = bids.add_long_lead(seeded, ESTIMATOR, pid, "Switchgear", 20, "2026-12-01", planned_order_date="2026-08-01")
    c = bids.add_long_lead(seeded, ESTIMATOR, pid, "Chiller", 20, "2026-12-01")
    # latest order date = 2026-12-01 - 140 days = 2026-07-14
    r = {x["id"]: x for x in bids.long_lead_report(seeded, pid, on=date(2026, 6, 15))["items"]}
    assert r[a]["latest_order_date"] == "2026-07-14" and r[a]["status"] == "On plan" and r[a]["float_days"] == 13 and r[a]["vendor_data"] == "Overdue"
    assert r[b]["status"].startswith("At risk") and r[b]["float_days"] == -18 and r[c]["status"] == "No order plan" and r[c]["float_days"] == 29
    late = {x["id"]: x for x in bids.long_lead_report(seeded, pid, on=date(2026, 8, 1))["items"]}
    assert late[c]["status"].startswith("Late: no order") and late[a]["status"].startswith("Late")
    bids.update_long_lead(seeded, ESTIMATOR, a, actual_order_date="2026-07-20", vendor_data_received="2026-06-20")
    done = {x["id"]: x for x in bids.long_lead_report(seeded, pid, on=date(2026, 8, 1))["items"]}
    assert done[a]["status"] == "Ordered late" and done[a]["float_days"] == -6 and done[a]["vendor_data"] == "Received"
    assert {x["id"] for x in bids.long_lead_report(seeded, pid, on=date(2026, 8, 1))["attention"]} == {a, b, c}
    for bad in (dict(lead_time_weeks="-1", required_on_site="2026-12-01"), dict(lead_time_weeks="4", required_on_site="not-a-date")):
        with pytest.raises(ValidationFailed):
            bids.add_long_lead(seeded, ESTIMATOR, pid, "x", **bad)


def test_interface_matrix_detects_double_count_gap_and_open_interface(seeded, world):
    pid = world
    boq.set_cost_code(seeded, ESTIMATOR, pid, "1.2", "C.01")
    seeded.execute("UPDATE boq_items SET pricing_method='subcontract_lump' WHERE project_id=? AND item_key='1.2'", (pid,))
    r0 = bids.interface_report(seeded, pid)
    assert r0["findings"] == [] and "not in use" in r0["note"]                                          # no matrix recorded -> no checks, no noise
    bids.set_scope(seeded, ESTIMATOR, pid, "PKG-B", "boq_item", "1.1", "included")
    assert [f["code"] for f in bids.interface_report(seeded, pid)["findings"]] == ["PACKAGE_GAP"]       # matrix in use and subcontract item 1.2 sits in no package
    bids.set_scope(seeded, ESTIMATOR, pid, "PKG-A", "cost_prefix", "C", "included")
    r = bids.interface_report(seeded, pid)
    assert r["clean"] is True and r["findings"] == [] and r["matrix"][1]["packages"] == {"PKG-A": "included", "PKG-B": ""}
    bids.set_scope(seeded, ESTIMATOR, pid, "PKG-B", "boq_item", "1.2", "included")                      # also included by B => double count of 1.2 (A covers it via prefix C)
    r = bids.interface_report(seeded, pid)
    assert r["double_counted"] == ["1.2"] and any(f["severity"] == "Critical" for f in r["findings"])
    bids.set_scope(seeded, ESTIMATOR, pid, "PKG-A", "boq_item", "1.2", "by_others", "PKG-B")           # A hands it to B, B includes it: consistent
    r = bids.interface_report(seeded, pid)
    assert r["double_counted"] == [] and not [f for f in r["findings"] if f["code"] == "INTERFACE_OPEN"]
    bids.set_scope(seeded, ESTIMATOR, pid, "PKG-B", "boq_item", "1.2", "excluded")                     # B now excludes it => falls between packages
    r = bids.interface_report(seeded, pid)
    assert any(f["code"] == "INTERFACE_OPEN" and f["item_key"] == "1.2" for f in r["findings"])
    for bad in (("PKG-A", "boq_item", "9.9", "included", None), ("PKG-A", "boq_item", "1.2", "by_others", None), ("PKG-A", "boq_item", "1.2", "by_others", "PKG-A"),
                ("PKG-A", "cost_prefix", "ZZ", "included", None), ("PKG-X", "boq_item", "1.2", "included", None), ("PKG-A", "boq_item", "1.2", "weird", None)):
        with pytest.raises((ValidationFailed, NotFound)):
            bids.set_scope(seeded, ESTIMATOR, pid, *bad[:4], bad[4])
