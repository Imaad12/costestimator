"""Material-take-off derivation: human-measured driver x approved factor, gated by approvals; expected values hand-calculated (SYNTHETIC figures)."""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.core.errors import Conflict, PermissionDenied, ValidationFailed
from app.estimators import mto as engine
from app.estimators.estimate import compute_estimate
from app.imports import boq as bi
from app.services import boq, governed, mto, projects
from app.services.rates import create_resource
from tests.conftest import AI, COMMERCIAL, ESTIMATOR
from tests.helpers import approved_rate, build_mini, write_boq

T = "piping.valve_install"


def test_templates_are_structure_only_and_cover_the_industrial_gaps():
    ts = mto.templates()
    assert len(ts) >= 20 and T in ts
    for t in ts.values():
        assert set(t) >= {"code", "driver_unit", "slots"} and t["slots"]
        assert not any(k in s for t in ts.values() for s in t["slots"] for k in ("factor", "price", "rate", "value"))
    cov = {c for t in ts.values() for c in t["capability"].split()}
    assert {"PRC-01", "PRC-03", "PRC-06", "PRC-12", "CLO-01"} <= cov


def test_engine_derive_hand_calculated_missing_and_skipped():
    t = {"code": "x", "driver_unit": "nr", "slots": [{"slot": "a", "description": "A"}, {"slot": "b", "description": "B"}, {"slot": "c", "description": "C"}]}
    f = {"a": {"resource_id": "R1", "factor": "3.5"}, "b": {"resource_id": "R2", "factor": "1", "waste_pct": "10"}}
    r = engine.derive(t, D(12), f, skip={"c"})
    assert [(l["slot"], l["qty"]) for l in r["lines"]] == [("a", D("42.000000")), ("b", D("13.200000"))] and r["skipped"] == ["c"] and r["missing"] == []
    r2 = engine.derive(t, D(12), f)
    assert r2["missing"] == ["c"]                                                 # nothing invented for a slot without a factor
    with pytest.raises(ValidationFailed):
        engine.derive(t, D(-1), f)
    with pytest.raises(ValidationFailed):
        engine.derive(t, D(1), f, skip={"zzz"})


@pytest.fixture()
def world(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)                                            # includes DEMO-LAB-001 (hr, SAR 10)
    create_resource(seeded, ESTIMATOR, resource_type="material", description="DEMO gasket+bolt set", unit="nr", cost_code="C.01", id="DEMO-MAT-NR", is_synthetic=True)
    approved_rate(seeded, "DEMO-MAT-NR", "25")
    bi.import_boq(seeded, ESTIMATOR, pid, write_boq(tmp_path / "valves.csv", [("2.1", "Install valves", "nr", "12", "", "")]))
    return pid


def _factor(db, pid, slot, rid, factor, waste=None, approve=True, template=T):
    data = {"template": template, "slot": slot, "resource_id": rid, "factor": factor}
    if waste:
        data["waste_pct"] = waste
    i = governed.propose(db, ESTIMATOR, "mto_factor", f"{template}/{slot}", data, source="Company productivity record PR-7 (test)", submit=True)
    if approve:
        governed.approve(db, COMMERCIAL, i)
    return i


def test_factor_validation_against_template_slot_resource_and_unit(seeded, world):
    ok = {"template": T, "slot": "install_labour", "resource_id": "DEMO-LAB-001", "factor": "3.5"}
    with pytest.raises(ValidationFailed) as e:                                     # code must be template/slot
        governed.propose(seeded, ESTIMATOR, "mto_factor", "wrong", ok, source="s")
    assert e.value.code == "MTO_CODE"
    with pytest.raises(ValidationFailed) as e:                                     # labour slot with a material resource
        governed.propose(seeded, ESTIMATOR, "mto_factor", f"{T}/install_labour", {**ok, "resource_id": "DEMO-MAT-NR"}, source="s")
    assert e.value.code == "MTO_RESOURCE"
    with pytest.raises(ValidationFailed) as e:                                     # material slot expects a count unit
        governed.propose(seeded, ESTIMATOR, "mto_factor", f"{T}/gaskets_bolting", {"template": T, "slot": "gaskets_bolting", "resource_id": "DEMO-MAT-001", "factor": "1"}, source="s")
    assert e.value.code == "MTO_UNIT"
    with pytest.raises(ValidationFailed):
        governed.propose(seeded, ESTIMATOR, "mto_factor", f"{T}/nope", {**ok, "slot": "nope"}, source="s")


def test_apply_pricing_gate_and_hand_calculated_cost(seeded, world):
    pid = world
    _factor(seeded, pid, "install_labour", "DEMO-LAB-001", "3.5")
    pv = mto.preview(seeded, pid, "2.1", T)
    assert pv["missing"] == ["gaskets_bolting", "test_labour"] and pv["driver_qty"] == 12 and pv["driver_source"].startswith("BOQ item 2.1")
    with pytest.raises(ValidationFailed) as e:
        mto.apply(seeded, ESTIMATOR, pid, "2.1", T)                                # factors missing -> refused, nothing written
    assert e.value.code == "MTO_FACTORS_MISSING"
    assert seeded.one("SELECT COUNT(*) n FROM takeoff_resource_lines WHERE project_id=?", (pid,))["n"] == 0
    _factor(seeded, pid, "gaskets_bolting", "DEMO-MAT-NR", "1", waste="10")
    _factor(seeded, pid, "test_labour", "DEMO-LAB-001", "0.5")
    r = mto.apply(seeded, ESTIMATOR, pid, "2.1", T)
    assert [l["qty"] for l in r["lines"]] == [D("42.000000"), D("13.200000"), D("6.000000")]
    item = seeded.one("SELECT pricing_method, pricing_status FROM boq_items WHERE project_id=? AND item_key='2.1'", (pid,))
    assert (item["pricing_method"], item["pricing_status"]) == ("takeoff_resources", "Pending Review")
    # not usable until a person approves the pricing decision
    est = compute_estimate(seeded, pid)
    assert not est.direct.items["2.1"].complete and any(e["code"] == "TAKEOFF_NOT_APPROVED" for e in est.exceptions)
    pre = compute_estimate(seeded, pid, include_unapproved=True)
    assert pre.direct.items["2.1"].direct_cost == D("810.00")                      # (42+6) h x 10 + 13.2 x 25 = 480 + 330
    boq.decide_pricing(seeded, COMMERCIAL, pid, "2.1", "approve", comment="Factors and driver checked against the valve list")
    est = compute_estimate(seeded, pid)
    assert est.direct.items["2.1"].complete and est.direct.items["2.1"].direct_cost == D("810.00")
    assert seeded.one("SELECT COUNT(*) n FROM approvals WHERE entity_type='pricing_decision'")["n"] == 1
    mh = [l for l in est.direct.lines if l.item_key == "2.1" and l.kind == "labour"]
    assert sum(l.hours for l in mh) == D(48)                                       # derived labour carries hours into the man-hour reports


def test_productivity_factor_applies_to_derived_labour_only(seeded, world):
    pid = world
    for slot, rid, f, w in (("install_labour", "DEMO-LAB-001", "3.5", None), ("gaskets_bolting", "DEMO-MAT-NR", "1", "10"), ("test_labour", "DEMO-LAB-001", "0.5", None)):
        _factor(seeded, pid, slot, rid, f, w)
    mto.apply(seeded, ESTIMATOR, pid, "2.1", T)
    boq.decide_pricing(seeded, COMMERCIAL, pid, "2.1", "approve", comment="ok")
    p = governed.propose(seeded, ESTIMATOR, "productivity_factor", "HT", {"category": "height", "factor": "1.2"}, source="site study (test)", submit=True)
    governed.approve(seeded, COMMERCIAL, p)
    est = compute_estimate(seeded, pid)
    assert est.direct.items["2.1"].direct_cost == D("906.00")                      # 48 h x 1.2 = 57.6 h x 10 = 576 + 330


def test_skip_slot_is_explicit_and_recorded(seeded, world):
    pid = world
    _factor(seeded, pid, "install_labour", "DEMO-LAB-001", "3.5")
    r = mto.apply(seeded, ESTIMATOR, pid, "2.1", T, skip_slots=["gaskets_bolting", "test_labour"])
    assert r["skipped"] == ["gaskets_bolting", "test_labour"] and len(r["lines"]) == 1
    st = mto.status_report(seeded, pid)
    assert st["applications"][0]["skipped"] == ["gaskets_bolting", "test_labour"] and st["pending_review"]


def test_stale_detection_after_factor_or_driver_change(seeded, world):
    pid = world
    for slot, rid, f in (("install_labour", "DEMO-LAB-001", "3.5"), ("gaskets_bolting", "DEMO-MAT-NR", "1"), ("test_labour", "DEMO-LAB-001", "0.5")):
        _factor(seeded, pid, slot, rid, f)
    mto.apply(seeded, ESTIMATOR, pid, "2.1", T)
    assert mto.status_report(seeded, pid)["stale"] == []
    _factor(seeded, pid, "install_labour", "DEMO-LAB-001", "4")                    # new approved version
    st = mto.status_report(seeded, pid)
    assert st["stale"][0]["flags"] == ["FACTORS_CHANGED"] and st["stale"][0]["changed_slots"] == ["install_labour"]
    mto.apply(seeded, ESTIMATOR, pid, "2.1", T)                                    # re-apply replaces the derived lines (not appends)
    assert seeded.one("SELECT COUNT(*) n FROM takeoff_resource_lines WHERE project_id=? AND item_key='2.1'", (pid,))["n"] == 3
    assert mto.status_report(seeded, pid)["stale"] == []


def test_guards_double_pricing_driver_source_and_authority(seeded, world):
    pid = world
    for slot, rid, f in (("install_labour", "DEMO-LAB-001", "3.5"), ("gaskets_bolting", "DEMO-MAT-NR", "1"), ("test_labour", "DEMO-LAB-001", "0.5")):
        _factor(seeded, pid, slot, rid, f)
    with pytest.raises(Conflict):                                                  # 1.1 is priced by an approved assembly
        mto.apply(seeded, ESTIMATOR, pid, "1.1", T, driver_qty="5", driver_source="MTO-1")
    with pytest.raises(ValidationFailed) as e:                                     # explicit driver needs its source
        mto.apply(seeded, ESTIMATOR, pid, "2.1", T, driver_qty="10")
    assert e.value.code == "MTO_DRIVER_SOURCE"
    with pytest.raises(PermissionDenied):
        mto.apply(seeded, AI, pid, "2.1", T)
    r = mto.apply(seeded, ESTIMATOR, pid, "2.1", T, driver_qty="10", driver_source="Valve list rev C (estimator count)")
    assert r["driver_qty"] == 10 and r["lines"][0]["qty"] == D("35.000000")        # explicit measured driver wins over the BOQ quantity
    # a template whose driver unit differs from the item unit and no explicit driver -> refused (never guessed)
    with pytest.raises(ValidationFailed) as e:
        mto.preview(seeded, pid, "1.1", "coating.surface")
    assert e.value.code == "MTO_DRIVER_UNIT"
