"""Governed parameters (productivity factors, plant hire terms): lifecycle, approval rules, and hand-calculated engine effects (SYNTHETIC figures)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.errors import ApprovalBlocked, Conflict, PermissionDenied, ValidationFailed
from app.estimators.direct_cost import compute_direct_cost
from app.estimators.param_kinds import KINDS
from app.estimators.types import EstimateInputs
from app.services import governed
from tests.conftest import ADMIN, AI, COMMERCIAL, ESTIMATOR, PROCUREMENT, VIEWER
from tests.unit.test_direct_cost import build, item, line


def P(code, data, status="Approved", version=1, unapproved=False, **kw):
    return dict(code=code, version=version, status=status, unapproved=unapproved, scope="project", is_synthetic=True, data=data, **kw)


def PF(code, factor, status="Approved", unapproved=False, **scope):
    return P(code, {"category": "height", "factor": str(factor), "applies_to": "labour", **scope}, status=status, unapproved=unapproved)


LAB = [line(1, "labour", "LAB1", 2, productivity_basis="paid_hours_per_unit")]          # 2 h per m3 @ SAR 12/h


def run(inp: EstimateInputs, **params):
    inp.params = params
    return compute_direct_cost(inp)


# ------------------------------------------------------------------ engine (pure)
def test_no_factor_is_baseline():
    r = compute_direct_cost(build(LAB, [item("50")]))
    assert r.direct_cost_total == Decimal("1200.00")                                 # 50 m3 x 2 h x 12


def test_combined_productivity_factors_are_multiplicative_and_hand_checked():
    inp = build(LAB, [item("50")])
    r = run(inp, productivity_factor=[PF("HT", "1.20"), PF("CG", "1.10")])
    # hours 100 x 1.20 x 1.10 = 132 ; amount 132 x 12 = 1584
    assert r.direct_cost_total == Decimal("1584.00")
    l = r.lines[0]
    assert l.hours == Decimal("132.00") and "PRODUCTIVITY_ADJUSTED" in l.flags and "x 1.320" in l.basis.replace("1.32", "1.320")


def test_factor_scope_cost_prefix_and_wbs():
    inp = build(LAB, [item("50")])                                                    # item cost code C.01
    assert run(inp, productivity_factor=[PF("A", "2", scope_cost_prefix="C.")]).direct_cost_total == Decimal("2400.00")
    assert run(build(LAB, [item("50")]), productivity_factor=[PF("A", "2", scope_cost_prefix="D.")]).direct_cost_total == Decimal("1200.00")
    inp = build(LAB, [item("50")])
    inp.item_wbs, inp.wbs_parent = {"1.1": "A1.2"}, {"A1.2": "A1", "A1": None, "B1": None}
    assert run(inp, productivity_factor=[PF("W", "1.5", scope_wbs="A1")]).direct_cost_total == Decimal("1800.00")      # ancestor scope applies
    inp2 = build(LAB, [item("50")]); inp2.item_wbs, inp2.wbs_parent = {"1.1": "A1.2"}, {"A1.2": "A1", "A1": None, "B1": None}
    assert run(inp2, productivity_factor=[PF("W", "1.5", scope_wbs="B1")]).direct_cost_total == Decimal("1200.00")     # other area does not


def test_unapproved_factor_is_flagged_loudly():
    inp = build(LAB, [item("50")], include_unapproved=True)
    r = run(inp, productivity_factor=[PF("HT", "1.2", status="Draft", unapproved=True)])
    assert "UNAPPROVED_PRODUCTIVITY_FACTOR" in r.lines[0].flags and any(e.code == "UNAPPROVED_PRODUCTIVITY_FACTOR" for e in r.exceptions)


PLANT = [line(1, "plant", "PUMP", 0.1)]          # 0.1 h per m3 x 50 m3 = 5 h @ 400/h = 2000 (no utilisation)


def test_plant_min_hire_and_standby_hand_calculated():
    base = compute_direct_cost(build(PLANT, [item("50")]))
    assert base.direct_cost_total == Decimal("2000.00")
    t = P("PUMP-T", {"resource_id": "PUMP", "min_hire_qty": "8", "standby_qty": "2", "standby_pct_of_rate": "25"})
    r = run(build(PLANT, [item("50")]), plant_hire_terms=[t])
    # top-up (8-5)=3 h x 400 = 1200 ; standby 2 h x 400 x 25% = 200 ; total 3400
    assert r.direct_cost_total == Decimal("3400.00")
    kinds = {l.kind: l.amount for l in r.lines}
    assert kinds["plant_min_hire_top_up"] == Decimal("1200.00") and kinds["plant_standby"] == Decimal("200.00")
    assert r.items["1.1"].direct_cost == Decimal("3400.00")
    # when use already exceeds the minimum there is no top-up
    r2 = run(build(PLANT, [item("50")]), plant_hire_terms=[P("T2", {"resource_id": "PUMP", "min_hire_qty": "4"})])
    assert r2.direct_cost_total == Decimal("2000.00")
    # terms for plant that is not used add nothing
    r3 = run(build(PLANT, [item("50")]), plant_hire_terms=[P("T3", {"resource_id": "OTHER", "min_hire_qty": "100"})])
    assert r3.direct_cost_total == Decimal("2000.00")


# ------------------------------------------------------------------ validation
def test_validators_reject_bad_values_and_ship_no_defaults():
    k = KINDS["productivity_factor"]
    for bad in ({"category": "height", "factor": "0"}, {"category": "height", "factor": "-1"}, {"category": "height", "factor": "abc"},
                {"category": "nonsense", "factor": "1.1"}, {"category": "height"}, {"category": "height", "factor": "1.1", "surprise": 1}):
        with pytest.raises(ValidationFailed):
            k.validate(bad)
    assert k.validate({"category": "height", "factor": "1.2500"})["factor"] == "1.25"
    with pytest.raises(ValidationFailed):
        KINDS["plant_hire_terms"].validate({"resource_id": "X", "standby_qty": "3"})               # standby needs its percentage
    with pytest.raises(ValidationFailed):
        KINDS["calendar"].validate({"start_date": "2026-02-30", "work_weekdays": "0,1"})
    with pytest.raises(ValidationFailed):
        KINDS["calendar"].validate({"start_date": "2026-03-01", "work_weekdays": ""})


# ------------------------------------------------------------------ lifecycle, authority
def test_lifecycle_versioning_and_effective_resolution(seeded):
    data = {"category": "climate_heat", "factor": "1.15"}
    pid = governed.propose(seeded, ESTIMATOR, "productivity_factor", "HEAT", data, source="Company site records 2025 (test)")
    assert governed.effective(seeded, "none", "productivity_factor") == []                          # Draft is not in force
    with pytest.raises(Conflict):
        governed.approve(seeded, COMMERCIAL, pid)                                                    # must be submitted first
    governed.submit(seeded, ESTIMATOR, pid)
    governed.approve(seeded, COMMERCIAL, pid, comments="ok")
    eff = governed.effective(seeded, "none", "productivity_factor")
    assert [(e["code"], e["version"], e["data"]["factor"]) for e in eff] == [("HEAT", 1, "1.15")]
    # revision: approved version stays in force until the new one is approved; preliminary view shows the draft, flagged
    p2 = governed.propose(seeded, ESTIMATOR, "productivity_factor", "HEAT", {"category": "climate_heat", "factor": "1.25"}, source="revised record", submit=True)
    assert governed.effective(seeded, "none", "productivity_factor")[0]["data"]["factor"] == "1.15"
    pre = governed.effective(seeded, "none", "productivity_factor", include_unapproved=True)[0]
    assert pre["data"]["factor"] == "1.25" and pre["unapproved"] is True
    governed.approve(seeded, COMMERCIAL, p2)
    assert governed.effective(seeded, "none", "productivity_factor")[0]["data"]["factor"] == "1.25"
    assert seeded.one("SELECT status FROM governed_params WHERE id=?", (pid,))["status"] == "Superseded"       # old kept, never edited
    assert seeded.one("SELECT COUNT(*) n FROM approvals WHERE entity_type='param:productivity_factor'")["n"] == 2
    with pytest.raises(Conflict):
        governed.approve(seeded, COMMERCIAL, p2)                                                       # already approved: immutable


def test_authority_source_and_ai_rules(seeded, settings):
    with pytest.raises(ValidationFailed):                                                           # source/basis required
        governed.propose(seeded, ESTIMATOR, "productivity_factor", "X", {"category": "height", "factor": "1.1"})
    with pytest.raises(PermissionDenied):
        governed.propose(seeded, AI, "productivity_factor", "X", {"category": "height", "factor": "1.1"}, source="s")
    with pytest.raises(PermissionDenied):
        governed.propose(seeded, VIEWER, "productivity_factor", "X", {"category": "height", "factor": "1.1"}, source="s")
    pid = governed.propose(seeded, ESTIMATOR, "productivity_factor", "X", {"category": "height", "factor": "1.1"}, source="s", submit=True)
    with pytest.raises(PermissionDenied):
        governed.approve(seeded, AI, pid)
    with pytest.raises(PermissionDenied):
        governed.approve(seeded, PROCUREMENT, pid)                                                  # productivity is not a procurement decision
    settings.allow_self_approval = False
    with pytest.raises(ApprovalBlocked):
        governed.approve(seeded, ESTIMATOR, pid)
    governed.approve(seeded, COMMERCIAL, pid)
    # plant terms need procurement / commercial, not the author-estimator
    res = seeded.one("SELECT id FROM resources WHERE resource_type='plant' LIMIT 1")["id"]
    t = governed.propose(seeded, ESTIMATOR, "plant_hire_terms", "T", {"resource_id": res, "min_hire_qty": "10"}, source="hire quotation Q-1 (test)", submit=True)
    settings.allow_self_approval = True
    with pytest.raises(PermissionDenied):
        governed.approve(seeded, ESTIMATOR, t)
    governed.approve(seeded, PROCUREMENT, t)
    with pytest.raises(ValidationFailed):                                                           # must reference a plant/equipment resource
        governed.propose(seeded, ESTIMATOR, "plant_hire_terms", "T9", {"resource_id": "NOPE", "min_hire_qty": "1"}, source="s")


def test_project_scope_overrides_company_and_estimate_reads_it(seeded, tmp_path):
    from app.estimators.estimate import compute_estimate
    from tests.helpers import build_mini
    pid = build_mini(seeded, tmp_path)
    base = compute_estimate(seeded, pid)
    base_direct = base.direct.direct_cost_total                                                       # 15 m3 x 2 h x SAR 10 + materials
    g = governed.propose(seeded, ESTIMATOR, "productivity_factor", "F", {"category": "height", "factor": "1.5"}, source="company record (test)", submit=True)
    governed.approve(seeded, COMMERCIAL, g)
    after = compute_estimate(seeded, pid)
    labour_before = sum(l.amount for l in base.direct.lines if l.kind == "labour")
    labour_after = sum(l.amount for l in after.direct.lines if l.kind == "labour")
    assert labour_after == labour_before * Decimal("1.5") and after.direct.direct_cost_total == base_direct + labour_before / 2
    p = governed.propose(seeded, ESTIMATOR, "productivity_factor", "F", {"category": "height", "factor": "2"}, project_id=pid, source="project study (test)", submit=True)
    governed.approve(seeded, COMMERCIAL, p)
    again = compute_estimate(seeded, pid)
    assert sum(l.amount for l in again.direct.lines if l.kind == "labour") == labour_before * 2                  # project value replaces company value of same code
    assert again.fingerprint != after.fingerprint != base.fingerprint
