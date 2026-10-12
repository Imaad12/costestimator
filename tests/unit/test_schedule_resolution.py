from datetime import date
from decimal import Decimal

from app.estimators.direct_cost import compute_direct_cost
from app.estimators.indirect import IndirectLine, IndirectResult
from app.estimators.pricing_schedule import build_schedule
from app.estimators.rate_resolution import resolve_rate
from app.estimators.types import DirectCostResult, ItemCost

D = Decimal


def rate(**kw):
    r = dict(id=1, resource_id="R", version=1, rate_type="Verified Supplier Quote", unit_price="10", currency="SAR", unit="m", region="KSA-ALL",
             status="Approved", price_date="2026-01-01", valid_until=None, confidence="High", project_id=None, is_synthetic=0)
    r.update(kw)
    return r


AS_OF = date(2026, 6, 1)
PARENTS = {"KSA-CENTRAL": "KSA-ALL", "KSA-ALL": None, "KSA-EASTERN": "KSA-ALL"}


def res(rates, region="KSA-CENTRAL", project="P1"):
    return resolve_rate(rates, project_id=project, project_region=region, as_of=AS_OF, region_parents=PARENTS, age_warning_days=180)


def test_resolution_outcomes():
    assert res([rate()]).eligibility == "ELIGIBLE"
    assert res([]).eligibility == "MISSING"
    assert res([rate(rate_type="Missing Rate", unit_price=None, status="Draft")]).eligibility == "MISSING"
    assert res([rate(status="Pending Review")]).eligibility == "UNAPPROVED" and res([rate(status="Draft")]).indicative_rate
    assert res([rate(valid_until="2026-05-31")]).eligibility == "EXPIRED"
    assert res([rate(status="Expired")]).eligibility == "EXPIRED"
    assert res([rate(price_date="2026-07-01")]).eligibility == "FUTURE"
    assert res([rate(rate_type="Official Index or Benchmark")]).eligibility == "NON_PRICE"      # an index is never a unit price
    assert res([rate(region="KSA-EASTERN")]).eligibility == "REGION"
    assert res([rate(region="KSA-CENTRAL")]).eligibility == "ELIGIBLE"
    assert res([rate(status="Superseded")]).eligibility == "MISSING"


def test_provisional_is_project_scoped():
    prov = rate(status="Provisional — Approved for This Estimate", project_id="P1")
    assert res([prov]).eligibility == "PROVISIONAL"
    assert res([prov], project="P2").eligibility == "MISSING"                       # other project's provisional is invisible
    assert res([rate(status="Provisional — Approved for This Estimate", project_id=None)]).eligibility == "UNAPPROVED"


def test_selection_prefers_project_then_latest():
    a, b = rate(id=1, unit_price="10"), rate(id=2, version=2, unit_price="11", price_date="2026-03-01")
    assert res([a, b]).rate["id"] == 2
    p = rate(id=3, version=3, unit_price="9", project_id="P1", status="Provisional — Approved for This Estimate", price_date="2025-12-01")
    assert res([a, b, p]).rate["id"] == 3


def test_age_and_confidence_warnings_and_synthetic():
    r = res([rate(price_date="2025-01-01", confidence="Low", is_synthetic=1)])
    assert r.eligibility == "ELIGIBLE" and len(r.warnings) == 3 and any("SYNTHETIC" in w for w in r.warnings)


def _direct(item_costs):
    items = {k: ItemCost(k, k, k, "m2", D(1), "C.01", "assembly", direct_cost=v, complete=True) for k, v in item_costs.items()}
    return DirectCostResult([], items, [], sum(item_costs.values(), D(0)), set(), set(), False, False, 2, 3, "SAR")


def _ind(lines):
    return IndirectResult([IndirectLine(c, "cat", c, "fixed", a, "", alloc, None, "Approved") for c, a, alloc in lines], sum(a for _, a, _ in lines), [], None, None)


def test_schedule_spread_reconciles_exactly_to_net_price():
    direct = _direct({"1": D("1000.00"), "2": D("2000.00"), "3": D("3333.33")})
    ind = _ind([("I1", D("1000.00"), "pro_rata_direct"), ("I2", D("700.00"), "separate_line")])
    # arbitrary commercial adders: they must be fully distributed with no lost/created cents
    net = D("9876.55")
    ratio = {"adders": D("400.00"), "margin": net - direct.direct_cost_total - ind.total - D("400.00"), "discount": D(0), "net": net}
    sch = build_schedule(direct, ind, {}, ratio, {}, money_dp=2, rate_dp=6, default_tax="VAT-STD")
    unrounded = sum((l.net_unrounded for l in sch.lines), D(0)) + sum((s["net"] for s in sch.separate_lines), D(0))
    assert unrounded == net
    assert sum((l.allocated_indirect for l in sch.lines), D(0)) == D("1000.00")          # pro-rata portion allocated exactly
    assert len(sch.separate_lines) == 1 and sch.separate_lines[0]["amount"] == D("700.00")
    assert abs(sch.rounding_variance) <= sch.max_rounding_variance and sch.complete


def test_schedule_excludes_unpriced_and_flags_incomplete():
    direct = _direct({"1": D("100.00")})
    direct.items["2"] = ItemCost("2", "2", "x", "m2", D(5), "C.01", "unpriced", complete=False)
    direct.items["3"] = ItemCost("3", "3", "x", "m2", D(5), "C.01", "excluded", complete=True)
    sch = build_schedule(direct, _ind([]), {}, {"adders": D(0), "margin": D(10), "discount": D(0), "net": D(110)}, {})
    st = {l.item_key: l.status for l in sch.lines}
    assert st == {"1": "Priced", "2": "Unpriced", "3": "Excluded"} and not sch.complete
    assert sch.lines[1].amount is None                                                  # unpriced is never shown as zero
