"""Construction-method alternatives: what-if comparison only; hand-calculated (SYNTHETIC)."""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.core.errors import ValidationFailed
from app.estimators.estimate import compute_estimate
from app.services import governed, indirects, methods
from tests.conftest import COMMERCIAL, ESTIMATOR
from tests.helpers import approved_assembly, build_mini


def _alt(db, pid, code, data):
    i = governed.propose(db, ESTIMATOR, "method_alternative", code, data, project_id=pid, source="Method statement MS-4 (test)", submit=True)
    governed.approve(db, COMMERCIAL, i)


def test_alternative_is_compared_what_if_and_changes_nothing(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    # base per m3: material 1.05 x 100 + labour 2 h x 10 = 125 -> 15 m3 = 1875 ; alternative B: material 100 + labour 1 h x 10 = 110 -> 1650
    approved_assembly(seeded, "DEMO-CONC-B", "m3", [dict(line_type="material", resource_id="DEMO-MAT-001", factor="1"),
                                                    dict(line_type="labour", resource_id="DEMO-LAB-001", factor="1", productivity_basis="paid_hours_per_unit")])
    indirects.add_indirect(seeded, ESTIMATOR, pid, code="IND-2", category="Site staff", description="Site staff (SYNTHETIC)", method="per_duration_month", amount="100", is_synthetic=True)
    indirects.submit_indirect(seeded, ESTIMATOR, pid, "IND-2"); indirects.approve_indirect(seeded, COMMERCIAL, pid, "IND-2")
    d = indirects.propose_duration(seeded, ESTIMATOR, pid, "3", "estimator_input", "Programme rev A (test)")
    indirects.approve_duration(seeded, COMMERCIAL, d)
    before = compute_estimate(seeded, pid)
    assert before.direct.direct_cost_total == D(1875) and before.indirect.total == D(800)                        # 500 fixed + 100 x 3 months
    _alt(seeded, pid, "ALT-B", {"name": "Lean crew method", "item_assemblies": {"1.1": "DEMO-CONC-B", "1.2": "DEMO-CONC-B"}, "duration_months": "2", "basis": "Method statement MS-4"})
    rep = methods.comparison_report(seeded, pid)
    a = rep["alternatives"][0]
    assert rep["base"]["direct_cost"] == D(1875) and rep["base"]["labour_hours"] == D(30) and rep["base"]["duration_months"] == 3
    assert a["summary"]["direct_cost"] == D(1650) and a["summary"]["labour_hours"] == D(15) and a["summary"]["duration_months"] == 2
    assert a["delta_vs_base"]["direct_cost"] == D(-225) and a["delta_vs_base"]["labour_hours"] == D(-15) and a["delta_vs_base"]["indirect_cost"] == D(-100)       # one month less staff
    assert "WHAT-IF" in rep["note"]
    after = compute_estimate(seeded, pid)
    assert after.fingerprint == before.fingerprint                                                                 # nothing was stored or changed
    assert seeded.one("SELECT assembly_code FROM boq_items WHERE project_id=? AND item_key='1.1'", (pid,))["assembly_code"] == "DEMO-CONC"


def test_alternative_validation_and_unknown_items(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    with pytest.raises(ValidationFailed) as e:
        governed.propose(seeded, ESTIMATOR, "method_alternative", "X", {"name": "n", "item_assemblies": {"1.1": "NO-SUCH-ASM"}, "basis": "b"}, project_id=pid, source="s")
    assert e.value.code == "METHOD_ASSEMBLY"
    for bad in ({"name": "n", "item_assemblies": {}, "basis": "b"}, {"name": "n", "item_assemblies": {"1.1": ""}, "basis": "b"}, {"name": "n", "basis": "b"}):
        with pytest.raises(ValidationFailed):
            governed.propose(seeded, ESTIMATOR, "method_alternative", "X", bad, project_id=pid, source="s")
    _alt(seeded, pid, "ALT-ZZ", {"name": "Ghost", "item_assemblies": {"9.9": "DEMO-CONC"}, "basis": "b"})
    assert "unknown BOQ item" in methods.comparison_report(seeded, pid)["alternatives"][0]["error"]
