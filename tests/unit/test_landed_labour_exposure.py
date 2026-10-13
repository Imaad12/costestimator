"""Landed-cost proposals, labour statutory on-costs, workforce mix and currency exposure. Expected values worked out by hand (SYNTHETIC figures)."""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.core.errors import PermissionDenied, ValidationFailed
from app.estimators import labour_costs, landed_cost
from app.estimators.estimate import compute_estimate
from app.imports import boq as bi
from app.services import commercial, governed, labour, landed, rates
from app.services.rates import create_resource
from tests.conftest import AI, COMMERCIAL, ESTIMATOR, PROCUREMENT
from tests.helpers import approved_rate, build_mini, write_boq


# ------------------------------------------------------------------ pure landed cost
COMPS = [dict(name="freight", kind="pct", value="10", applies_to="base"),
         dict(name="insurance", kind="pct", value="0.5", applies_to=["base", "freight"]),
         dict(name="duty", kind="pct", value="5", applies_to=["base", "freight", "insurance"]),
         dict(name="clearance", kind="per_unit", value="15", currency="SAR"),
         dict(name="port", kind="per_shipment", value="2000", currency="SAR"),
         dict(name="handling", kind="pct", value="3", applies_to="cumulative")]


def test_landed_cost_hand_calculated_with_exposure():
    r = landed_cost.landed(D(1000), "USD", landed_cost.validate_components(COMPS), "SAR", lambda c: D("3.75") if c == "USD" else None, D(400))
    # base 3750 ; freight 375 ; insurance (3750+375)x0.5% = 20.625 ; duty (4145.625)x5% = 207.28125 ; clearance 15 ; port 2000/400 = 5
    # handling 3% x (3750+375+20.625+207.28125+15+5 = 4372.90625) = 131.1871875 ; landed 4504.0934375
    amt = {l["name"]: l["amount"] for l in r["lines"]}
    assert r["base_out"] == D(3750) and amt["freight"] == D(375) and amt["insurance"] == D("20.625") and amt["duty"] == D("207.28125")
    assert amt["clearance"] == D(15) and amt["port"] == D(5) and amt["handling"] == D("131.1871875") and r["landed"] == D("4504.0934375")
    assert r["exposure"]["USD"] == D("4483.4934375") and r["exposure"]["SAR"] == D("20.6") and sum(r["exposure"].values()) == r["landed"]


def test_landed_validation_and_missing_fx():
    for bad in ([], [dict(name="x", kind="pct", value="1", applies_to="later")], [dict(name="x", kind="weird", value="1")], [dict(name="x", kind="pct", value="-1")],
                [dict(name="base", kind="pct", value="1")], [dict(name="a", kind="pct", value="1"), dict(name="a", kind="pct", value="2")]):
        with pytest.raises(ValidationFailed):
            landed_cost.validate_components(bad)
    with pytest.raises(ValidationFailed) as e:
        landed_cost.landed(D(10), "EUR", landed_cost.validate_components([dict(name="f", kind="pct", value="1")]), "SAR", lambda c: None)
    assert e.value.code == "FX_MISSING"
    with pytest.raises(ValidationFailed) as e:
        landed_cost.landed(D(10), "SAR", landed_cost.validate_components([dict(name="p", kind="per_shipment", value="5")]), "SAR", lambda c: None)
    assert e.value.code == "LANDED_SHIPMENT_UNITS"


# ------------------------------------------------------------------ pure labour
def test_statutory_monthly_and_workforce_blend_hand_calculated():
    rules = [dict(code="R-SOC", name="social", basis="pct_of_base_wage", value="10", applies_to="all"), dict(code="R-LEVY", name="levy", basis="per_head_month", value="800", applies_to="expat"),
             dict(code="R-VISA", name="visa", basis="per_head_once", value="1200", applies_to="expat"), dict(code="R-EOSB", name="eosb", basis="pct_of_base_wage", value="5", applies_to="all"),
             dict(code="R-INS", name="insurance", basis="per_head_year", value="2400", applies_to="all")]
    ex = labour_costs.statutory_monthly(D(2000), rules, "expat", D(12))
    assert ex["monthly_total"] == D(200 + 800 + 100 + 100 + 200)                       # 10% + levy + 1200/12 + 5% + 2400/12
    sa = labour_costs.statutory_monthly(D(2000), rules, "saudi", None)
    assert sa["monthly_total"] == D(200 + 100 + 200) and [r["code"] for r in sa["rows"]] == ["R-SOC", "R-EOSB", "R-INS"]
    with pytest.raises(ValidationFailed) as e:
        labour_costs.statutory_monthly(D(2000), rules, "expat", None)                    # one-off cost cannot be amortised without a contract length
    assert e.value.code == "LABOUR_CONTRACT_MONTHS"
    b = labour_costs.blend([dict(name="e", headcount=80, hourly_cost="18", saudi=False), dict(name="s", headcount=20, hourly_cost="13.5", saudi=True)])
    assert b["blended_hourly_cost"] == D("17.1") and b["saudi_pct"] == D(20)
    assert labour_costs.national_target_check(D(20), D(25)) == {"required_pct": D(25), "actual_pct": D(20), "meets": False, "shortfall_pct_points": D(5)}
    with pytest.raises(ValidationFailed):
        labour_costs.blend([])


# ------------------------------------------------------------------ services
def _approve(db, kind, code, data, project_id=None, who=COMMERCIAL):
    i = governed.propose(db, ESTIMATOR, kind, code, data, project_id=project_id, source="Test source (SYNTHETIC)", submit=True)
    governed.approve(db, who, i)
    return i


def _fx(db):
    f = commercial.propose_fx(db, ESTIMATOR, "USD", "SAR", "3.75", "2026-01-01", "TEST FX (SYNTHETIC)", is_synthetic=True)
    commercial.approve_fx(db, PROCUREMENT, f)


@pytest.fixture()
def world(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    _fx(seeded)
    create_resource(seeded, ESTIMATOR, resource_type="material", description="DEMO imported valve", unit="nr", cost_code="C.01", id="DEMO-MAT-USD", is_synthetic=True)
    base = approved_rate(seeded, "DEMO-MAT-USD", "10", currency="USD")
    bi.import_boq(seeded, ESTIMATOR, pid, write_boq(tmp_path / "t.csv", [("3.1", "Imported valves", "nr", "100", "", "")]))
    t = tmp_path / "take.csv"
    t.write_text("item_code,resource_id,quantity,unit\n3.1,DEMO-MAT-USD,100,nr\n", encoding="utf-8")
    bi.import_takeoff_resources(seeded, ESTIMATOR, pid, t)
    return pid, base


def test_exposure_report_split_hedge_and_sensitivity(seeded, world):
    pid, _ = world
    _approve(seeded, "hedge_cover", "USD", {"currency": "USD", "cover_pct": "60", "instrument": "Forward contract FC-1 (test)"}, project_id=pid)
    r = landed.exposure_report(seeded, pid, shocks="10")
    by = {x["currency"]: x for x in r["by_currency"]}
    assert by["USD"]["amount_home"] == D("3750.00") and by["USD"]["hedge_cover_pct"] == 60 and by["USD"]["unhedged_home"] == D("1500.0000")       # 100 x USD10 x 3.75 ; 40% open
    assert by["SAR"]["home"] and by["SAR"]["unhedged_home"] == 0
    assert r["sensitivity"] == [{"shock_pct": D(10), "delta_unhedged_home": D("150.00000")}]
    assert sum(x["share_pct"] for x in r["by_currency"]) == D(100)


def test_landed_rate_is_a_proposal_that_needs_normal_approval_and_changes_exposure(seeded, world):
    pid, base = world
    _approve(seeded, "landed_cost_terms", "VALVE-IMPORT", {"name": "Valve import to site", "incoterm": "FOB", "output_currency": "SAR",
                                                          "components": [dict(name="freight", kind="pct", value="10"), dict(name="haulage", kind="per_unit", value="20", currency="SAR")]},
             who=PROCUREMENT)
    res = landed.compute(seeded, "10", "USD", "VALVE-IMPORT")
    assert res["landed"] == D("61.25") and res["exposure"] == {"USD": D("41.25"), "SAR": D(20)}                  # 37.5 + 3.75 + 20
    pr = landed.propose_landed_rate(seeded, ESTIMATOR, base, "VALVE-IMPORT")
    row = rates.get_rate(seeded, pr["rate_id"])
    assert row["status"] == "Draft" and row["currency"] == "SAR" and D(row["unit_price"]) == D("61.25") and row["delivery_basis"].startswith("Delivered")
    assert compute_estimate(seeded, pid).direct.items["3.1"].direct_cost == D("3750.00")                          # unchanged until approved
    rates.submit_rate(seeded, ESTIMATOR, pr["rate_id"])
    rates.approve_rate(seeded, PROCUREMENT, pr["rate_id"])
    est = compute_estimate(seeded, pid)
    assert est.direct.items["3.1"].direct_cost == D("6125.00")                                                    # 100 x 61.25
    by = {x["currency"]: x["amount_home"] for x in landed.exposure_report(seeded, pid)["by_currency"]}
    assert by["USD"] == D("4125.00")                                                                              # 100 x 41.25 stays USD-exposed
    with pytest.raises(PermissionDenied):
        landed.propose_landed_rate(seeded, AI, base, "VALVE-IMPORT")
    draft = rates.propose_rate(seeded, ESTIMATOR, "DEMO-MAT-USD", unit_price="11", rate_type="Synthetic Demonstration Rate", currency="USD", is_synthetic=True)
    with pytest.raises(ValidationFailed) as e:                                                                    # derived from an unapproved base is refused
        landed.propose_landed_rate(seeded, ESTIMATOR, draft, "VALVE-IMPORT")
    assert e.value.code == "LANDED_BASE_NOT_APPROVED"


def test_labour_buildup_with_user_rules_and_workforce_check(seeded, tmp_path):
    create_resource(seeded, ESTIMATOR, resource_type="labour", description="DEMO welder expat", unit="hr", cost_code="C", id="DEMO-LAB-EX", is_synthetic=True)
    for code, basis, val, app in (("R-SOC", "pct_of_base_wage", "10", "all"), ("R-LEVY", "per_head_month", "800", "expat"), ("R-VISA", "per_head_once", "1200", "expat"),
                                  ("R-EOSB", "pct_of_base_wage", "5", "all")):
        _approve(seeded, "labour_statutory", code, {"name": code, "basis": basis, "value": val, "applies_to": app, "authority_ref": "Test regulation extract"})
    out = labour.propose_labour_rate(seeded, ESTIMATOR, "DEMO-LAB-EX", monthly_base_wage="2000", group="expat", normal_hours_per_month="200", contract_months="12",
                                     allowances_monthly="400", evidence="Test wage sheet (SYNTHETIC)", price_date="2026-09-01")
    assert out["statutory_monthly"] == D(1200) and out["hourly_cost"] == D(18) and sorted(out["rules_applied"]) == ["R-EOSB", "R-LEVY", "R-SOC", "R-VISA"]   # (2000+400+1200)/200
    row = rates.get_rate(seeded, out["rate_id"])
    assert D(row["unit_price"]) == 18 and row["status"] == "Draft" and "statutory_breakdown" in row["components_json"]
    sa = labour.build(seeded, monthly_base_wage="2000", group="saudi", normal_hours_per_month="200", allowances_monthly="400")
    assert sa["hourly_cost"] == D("13.5")                                                                       # (2000+400+300)/200
    with pytest.raises(ValidationFailed):
        labour.propose_labour_rate(seeded, ESTIMATOR, "DEMO-LAB-EX", monthly_base_wage="2000", group="expat", normal_hours_per_month="200", contract_months="12", evidence="")
    r0 = labour.workforce_report(seeded, [dict(name="e", headcount=80, hourly_cost="18", saudi=False), dict(name="s", headcount=20, hourly_cost="13.5", saudi=True)])
    assert r0["target"] is None and "no compliance check" in r0["note"]
    _approve(seeded, "national_workforce_target", "TGT", {"name": "Test target", "required_pct": "25", "authority_ref": "Test programme rule"})
    r1 = labour.workforce_report(seeded, [dict(name="e", headcount=80, hourly_cost="18", saudi=False), dict(name="s", headcount=20, hourly_cost="13.5", saudi=True)])
    assert r1["target"]["meets"] is False and r1["target"]["shortfall_pct_points"] == 5 and r1["blended_hourly_cost"] == D("17.1")
