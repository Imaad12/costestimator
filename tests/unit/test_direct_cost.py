"""Direct-cost engine tests with fixed, independently hand-calculated expected values (SYNTHETIC test figures)."""
from datetime import date
from decimal import Decimal

import pytest

from app.core.units import UnitRegistry
from app.estimators.direct_cost import compute_direct_cost
from app.estimators.types import AssemblyDef, AssumptionValue, EstimateInputs
from app.services import refdata  # noqa: F401

UNITS = UnitRegistry([
    dict(code="m3", name="m3", dimension="volume", to_base="1", synonyms="", ambiguous_synonyms=""),
    dict(code="l", name="l", dimension="volume", to_base="0.001"),
    dict(code="kg", name="kg", dimension="mass", to_base="1"),
    dict(code="t", name="t", dimension="mass", to_base="1000"),
    dict(code="m2", name="m2", dimension="area", to_base="1"),
    dict(code="hr", name="hr", dimension="time_hr", to_base="1"),
    dict(code="nr", name="nr", dimension="count", to_base="1"),
    dict(code="ls", name="ls", dimension="lump", to_base="1"),
])


def rate(rid, resource_id, price, unit, **kw):
    r = dict(id=rid, resource_id=resource_id, version=1, rate_type="Synthetic Demonstration Rate", unit_price=str(price),
             currency="SAR", unit=unit, region="KSA-ALL", status="Approved", price_date="2026-01-01", valid_until=None,
             confidence="Low", project_id=None, is_synthetic=1, components_json=None)
    r.update(kw)
    return r


def res(rid, rtype, unit, desc=None):
    return dict(id=rid, resource_type=rtype, unit=unit, description=desc or rid)


def akv(id, value, status="Approved", key=None):
    return AssumptionValue(id, value, status, "global_default", id, None, key)


def line(no, lt, rid=None, factor=None, **kw):
    base = dict(line_no=no, line_type=lt, resource_id=rid, factor=None if factor is None else str(factor),
                factor_unit=None, factor_includes_waste=0, waste_basis="none", waste_value=None, waste_ref=None,
                productivity_basis=None, crew_json=None, shift_hours_ref=None, productive_hours_ref=None,
                overtime_share_pct=None, utilisation_basis="none", utilisation_value=None, utilisation_ref=None,
                includes_labour=0, includes_material=0, includes_plant=0, explicitly_separate=0, child_assembly_code=None)
    base.update(kw)
    return base


def build(lines, items, extra_rates=(), keys=None, include_unapproved=False, assemblies=None):
    resources = {r["id"]: r for r in [
        res("MC", "material", "m3"), res("RB", "material", "kg"), res("LAB1", "labour", "hr"), res("FOR", "labour", "hr"),
        res("PUMP", "plant", "hr"), res("SUBX", "subcontract", "m2")]}
    rates = {"MC": [rate(1, "MC", 100, "m3")], "RB": [rate(2, "RB", 3.2, "kg")], "LAB1": [rate(3, "LAB1", 12, "hr")],
             "FOR": [rate(4, "FOR", 20, "hr")], "PUMP": [rate(5, "PUMP", 400, "hr")], "SUBX": [rate(6, "SUBX", 55, "m2")]}
    for r in extra_rates:
        rates[r["resource_id"]] = [r]
    asm = assemblies or {"CONC": AssemblyDef("CONC", 1, "m3", "Concrete per m3", "Approved", True, lines)}
    k = keys if keys is not None else {
        "labour.shift_hours": akv("A-SH", "8", key="labour.shift_hours"),
        "labour.productive_hours_per_shift": akv("A-PH", "6", key="labour.productive_hours_per_shift"),
        "plant.utilisation_pct": akv("A-UT", "50", key="plant.utilisation_pct"),
        "money.rounding_dp": akv("A-M", "2", key="money.rounding_dp"),
    }
    return EstimateInputs(project={"id": "P1", "region": "KSA-ALL", "currency": "SAR"}, as_of=date(2026, 6, 1), items=items,
                          assemblies=asm, resources=resources, rates=rates, assumptions={"A-W": akv("A-W", "5")},
                          engine_keys=k, takeoff={}, fx=[], units=UNITS, include_unapproved=include_unapproved)


def item(qty="50", unit="m3", code="CONC", key="1.1", **kw):
    d = dict(item_key=key, item_code=key, item_type="item", description="Concrete", quantity=qty, unit=unit,
             cost_code="C.01", pricing_method="assembly", assembly_code=code, mapping_status="Approved",
             status_in_revision="Current")
    d.update(kw)
    return d


def test_full_assembly_hand_calculated():
    lines = [
        line(1, "material", "MC", 1, waste_basis="fixed_pct", waste_value="5"),                  # 1.05 m3 x 100 = 105
        line(2, "material", "RB", 100),                                                          # 100 kg x 3.2 = 320
        line(3, "labour", "LAB1", 10, productivity_basis="output_per_crew_shift",
             crew_json='[{"resource_id":"LAB1","count":2},{"resource_id":"FOR","count":1}]'),    # 35.2
        line(4, "plant", "PUMP", 0.1, utilisation_basis="assumption"),                           # 0.2h x 400 = 80
    ]
    res_ = compute_direct_cost(build(lines, [item()]))
    assert res_.exceptions == [] or all(e.severity == "Low" for e in res_.exceptions)
    # per m3 = 105 + 320 + 35.2 + 80 = 540.2 ; x 50 m3
    assert res_.direct_cost_total == Decimal("27010.00")
    ic = res_.items["1.1"]
    assert ic.complete and ic.direct_cost == Decimal("27010.00")
    by = res_.by_kind()
    assert by["material"] == Decimal("21250.00")      # (105+320)*50
    assert by["labour"] == Decimal("1760.00")         # 35.2*50
    assert by["plant"] == Decimal("4000.00")          # 80*50
    lab = [l for l in res_.lines if l.kind == "labour"]
    assert sum(l.hours for l in lab) == Decimal("120")  # 2.4 h/m3 * 50


def test_waste_not_applied_twice_by_validation():
    from app.core.errors import ValidationFailed
    from app.services import assemblies as svc
    with pytest.raises(ValidationFailed) as e:
        svc._check_line_rules({"factor_includes_waste": 1, "waste_basis": "fixed_pct", "waste_value": "5"})
    assert e.value.code == "DOUBLE_WASTE"


def test_missing_rate_never_zero():
    lines = [line(1, "material", "MC", 1)]
    inp = build(lines, [item("10")])
    inp.rates["MC"] = []
    r = compute_direct_cost(inp)
    assert r.direct_cost_total == Decimal("0")
    assert not r.items["1.1"].complete
    assert r.lines[0].amount is None
    assert any(e.code == "MISSING_RATE" for e in r.exceptions)


def test_unapproved_rate_excluded_but_exposure_reported():
    lines = [line(1, "material", "MC", 2)]
    inp = build(lines, [item("10")])
    inp.rates["MC"] = [rate(1, "MC", 100, "m3", status="Pending Review")]
    r = compute_direct_cost(inp)
    assert r.lines[0].amount is None and r.lines[0].indicative_amount == Decimal("2000.00")
    assert r.items["1.1"].indicative_exposure == Decimal("2000.00") and r.direct_cost_total == 0
    # preliminary mode prices it but flags it
    inp2 = build(lines, [item("10")], include_unapproved=True)
    inp2.rates["MC"] = [rate(1, "MC", 100, "m3", status="Pending Review")]
    r2 = compute_direct_cost(inp2)
    assert r2.direct_cost_total == Decimal("2000.00")
    assert "UNAPPROVED_RATE_USED_PRELIMINARY" in r2.lines[0].flags


def test_expired_rate_flagged_not_used():
    lines = [line(1, "material", "MC", 1)]
    inp = build(lines, [item("1")])
    inp.rates["MC"] = [rate(1, "MC", 100, "m3", valid_until="2026-03-01")]
    r = compute_direct_cost(inp)
    assert r.lines[0].amount is None and any(e.code == "EXPIRED_RATE" for e in r.exceptions)


def test_unit_conversion_t_to_kg():
    # steel rate quoted per tonne (3200/t), consumed in kg
    lines = [line(1, "material", "RB", 100)]
    inp = build(lines, [item("1")])
    inp.rates["RB"] = [rate(2, "RB", 3200, "t")]
    r = compute_direct_cost(inp)
    assert r.direct_cost_total == Decimal("320.00")


def test_item_unit_conversion_to_assembly_unit():
    # BOQ in litres against an m3 assembly: 1000 l = 1 m3
    lines = [line(1, "material", "MC", 1)]
    inp = build(lines, [item("1000", unit="l")])
    assert compute_direct_cost(inp).direct_cost_total == Decimal("100.00")


def test_incompatible_units_rejected():
    inp = build([line(1, "material", "MC", 1)], [item("5", unit="m2")])
    r = compute_direct_cost(inp)
    assert r.direct_cost_total == 0 and any(e.code == "ITEM_UNIT_INCOMPATIBLE" for e in r.exceptions)


def test_subcontract_double_count_blocked():
    lines = [line(1, "subcontract", "SUBX", 1, includes_labour=1, includes_material=1),
             line(2, "labour", "LAB1", 1, productivity_basis="paid_hours_per_unit"),
             line(3, "material", "MC", 1)]
    r = compute_direct_cost(build(lines, [item("2", unit="m3")]))
    codes = [e.code for e in r.exceptions]
    assert codes.count("DOUBLE_COUNT_SUBCONTRACT") == 2
    assert r.direct_cost_total == Decimal("0.00") or r.direct_cost_total == Decimal("110.00")  # only subcontract priced: 2 x 55
    assert r.direct_cost_total == Decimal("110.00")


def test_productive_hours_conversion():
    # 0.75 productive h/unit, shift 8, productive 6 => 1.0 paid h/unit ; x12 = 12 h x 12/h = 144 per 1 qty
    lines = [line(1, "labour", "LAB1", 0.75, productivity_basis="productive_hours_per_unit")]
    r = compute_direct_cost(build(lines, [item("1")]))
    assert r.direct_cost_total == Decimal("12.00")


def test_missing_shift_assumption_blocks_crew_pricing():
    lines = [line(1, "labour", "LAB1", 10, productivity_basis="output_per_crew_shift",
                  crew_json='[{"resource_id":"LAB1","count":2}]')]
    inp = build(lines, [item("5")], keys={"money.rounding_dp": akv("A-M", "2", key="money.rounding_dp")})
    r = compute_direct_cost(inp)
    assert r.direct_cost_total == 0 and any(e.code == "ASSUMPTION_MISSING" for e in r.exceptions)


def test_unapproved_assumption_blocks_unless_preliminary():
    lines = [line(1, "material", "MC", 1, waste_basis="assumption", waste_ref="A-W")]
    inp = build(lines, [item("1")])
    inp.assumptions["A-W"] = akv("A-W", "10", status="Pending Review")
    r = compute_direct_cost(inp)
    assert r.lines[0].amount is None and any(e.code == "ASSUMPTION_NOT_APPROVED" for e in r.exceptions)
    inp2 = build(lines, [item("1")], include_unapproved=True)
    inp2.assumptions["A-W"] = akv("A-W", "10", status="Pending Review")
    assert compute_direct_cost(inp2).direct_cost_total == Decimal("110.00")


def test_nested_assembly_and_cycle_guard():
    child = AssemblyDef("CH", 1, "m3", "child", "Approved", True, [line(1, "material", "MC", 1)])
    parent = AssemblyDef("CONC", 1, "m3", "parent", "Approved", True,
                         [line(1, "assembly", None, 2, child_assembly_code="CH")])
    r = compute_direct_cost(build([], [item("3")], assemblies={"CONC": parent, "CH": child}))
    assert r.direct_cost_total == Decimal("600.00")      # 3 x 2 x 100
    loop_a = AssemblyDef("CONC", 1, "m3", "a", "Approved", True, [line(1, "assembly", None, 1, child_assembly_code="CH")])
    loop_b = AssemblyDef("CH", 1, "m3", "b", "Approved", True, [line(1, "assembly", None, 1, child_assembly_code="CONC")])
    r2 = compute_direct_cost(build([], [item("1")], assemblies={"CONC": loop_a, "CH": loop_b}))
    assert any(e.code == "CIRCULAR_ASSEMBLY" for e in r2.exceptions)


def test_foreign_currency_requires_approved_fx():
    lines = [line(1, "material", "MC", 1)]
    inp = build(lines, [item("1")])
    inp.rates["MC"] = [rate(1, "MC", 25, "m3", currency="USD")]
    r = compute_direct_cost(inp)
    assert r.lines[0].amount is None and any(e.code == "FX_MISSING" for e in r.exceptions)
    inp.fx = [dict(from_ccy="USD", to_ccy="SAR", rate="3.75", rate_date="2026-01-01", valid_until=None, status="Approved")]
    assert compute_direct_cost(inp).direct_cost_total == Decimal("93.75")
    inp.fx[0]["status"] = "Pending Review"
    assert compute_direct_cost(inp).direct_cost_total == Decimal("0")


def test_provisional_rate_flagged():
    inp = build([line(1, "material", "MC", 1)], [item("2")])
    inp.rates["MC"] = [rate(1, "MC", 90, "m3", status="Provisional — Approved for This Estimate", project_id="P1")]
    r = compute_direct_cost(inp)
    assert r.direct_cost_total == Decimal("180.00") and r.provisional_used and r.items["1.1"].provisional


def test_rounding_dp_assumption():
    inp = build([line(1, "material", "RB", 1)], [item("1")])
    inp.rates["RB"] = [rate(2, "RB", "3.33333", "kg")]
    inp.engine_keys["money.rounding_dp"] = akv("A-M", "4", key="money.rounding_dp")
    assert compute_direct_cost(inp).direct_cost_total == Decimal("3.3333")
