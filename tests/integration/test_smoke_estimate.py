from decimal import Decimal

from app.estimators.estimate import compute_estimate
from app.imports import boq as boq_import
from app.services import boq, indirects, projects, rates

from tests.conftest import COMMERCIAL, ESTIMATOR
from tests.helpers import (approve_assumption, approve_vat, approved_assembly, approved_rate, std_policy, write_boq)


def test_mini_project_end_to_end(seeded, tmp_path):
    db = seeded
    rid_c = rates.create_resource if False else None
    # resources & rates
    from app.services.rates import create_resource
    create_resource(db, ESTIMATOR, resource_type="material", description="DEMO Ready-mix C30", unit="m3", cost_code="C.01",
                    id="DEMO-MAT-001", is_synthetic=True)
    create_resource(db, ESTIMATOR, resource_type="labour", description="DEMO Labourer", unit="hr", cost_code="C", id="DEMO-LAB-001",
                    is_synthetic=True)
    approved_rate(db, "DEMO-MAT-001", "100")
    approved_rate(db, "DEMO-LAB-001", "10")
    approved_assembly(db, "DEMO-CONC", "m3", [
        dict(line_type="material", resource_id="DEMO-MAT-001", factor="1.05", factor_includes_waste=1),
        dict(line_type="labour", resource_id="DEMO-LAB-001", factor="2", productivity_basis="paid_hours_per_unit")])
    pid = projects.create_project(db, ESTIMATOR, name="Mini (SYNTHETIC)", is_demo=True, tax_category="VAT-STD")
    f = write_boq(tmp_path / "b.csv", [("1.1", "Concrete", "m3", "10", "", ""), ("1.2", "Concrete B", "cum", "5", "", "")])
    s = boq_import.import_boq(db, ESTIMATOR, pid, f)
    assert s["items_new"] == 2 and s["rejected"] == 0
    for k in ("1.1", "1.2"):
        boq.map_to_assembly(db, ESTIMATOR, pid, k, "DEMO-CONC")
    # per m3: 1.05*100 + 2*10 = 125 ; 15 m3 => 1875
    for aid, v in (("ASMP-B-001", None),):
        pass
    std_policy(db, pid)
    r = compute_estimate(db, pid)
    assert r.direct.direct_cost_total == Decimal("1875.00")
    assert r.commercial is not None
    # contingency 5% of direct => 93.75 ; total cost 1968.75 ; markup 10% => 2165.625 -> 2165.63
    assert r.commercial.contingency == Decimal("93.75")
    assert r.commercial.selling_price_pre_discount == Decimal("2165.63")
    assert r.state.startswith("Preliminary")           # VAT unverified, durations etc.
    assert any("Tax" in b or "tax" in b for b in r.blockers)
    approve_vat(db)
    r2 = compute_estimate(db, pid)
    assert r2.commercial.tax_total > 0
