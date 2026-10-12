"""Mini end-to-end: estimate -> reconciliation -> final approval -> offer -> gated submission export. All figures SYNTHETIC."""
from decimal import Decimal

import pytest

from app.core.errors import ApprovalBlocked, PermissionDenied
from app.estimators.estimate import compute_estimate
from app.imports import boq as boq_import
from app.reconciliation import engine as recon
from app.services import boq, estimates, indirects, offers, projects, registers
from app.services.rates import create_resource

from tests.conftest import ADMIN, COMMERCIAL, ESTIMATOR, PROCUREMENT
from tests.helpers import approve_vat, approved_assembly, approved_rate, std_policy, write_boq


@pytest.fixture()
def project(seeded, tmp_path):
    db = seeded
    create_resource(db, ESTIMATOR, resource_type="material", description="DEMO Ready-mix C30", unit="m3", cost_code="C.01",
                    id="DEMO-MAT-001", is_synthetic=True)
    create_resource(db, ESTIMATOR, resource_type="labour", description="DEMO Labourer", unit="hr", cost_code="C", id="DEMO-LAB-001", is_synthetic=True)
    approved_rate(db, "DEMO-MAT-001", "100")
    approved_rate(db, "DEMO-LAB-001", "10")
    approved_assembly(db, "DEMO-CONC", "m3", [
        dict(line_type="material", resource_id="DEMO-MAT-001", factor="1.05", factor_includes_waste=1),
        dict(line_type="labour", resource_id="DEMO-LAB-001", factor="2", productivity_basis="paid_hours_per_unit")])
    pid = projects.create_project(db, ESTIMATOR, name="Mini (SYNTHETIC)", is_demo=True, tax_category="VAT-STD")
    f = write_boq(tmp_path / "b.csv", [("1.1", "Concrete", "m3", "10", "", ""), ("1.2", "Concrete B", "cum", "5", "", "")])
    boq_import.import_boq(db, ESTIMATOR, pid, f)
    for k in ("1.1", "1.2"):
        boq.map_to_assembly(db, ESTIMATOR, pid, k, "DEMO-CONC")
    std_policy(db, pid)
    approve_vat(db)
    indirects.add_indirect(db, ESTIMATOR, pid, code="IND-1", category="Project management", description="PM lump (SYNTHETIC)",
                           method="fixed", amount="500", is_synthetic=True)
    indirects.submit_indirect(db, ESTIMATOR, pid, "IND-1")
    indirects.approve_indirect(db, COMMERCIAL, pid, "IND-1")
    return db, pid


def test_estimate_numbers(project):
    db, pid = project
    r = compute_estimate(db, pid)
    # direct 1875 + indirect 500 = 2375 ; contingency 5% of (D+I) = 118.75 ; T = 2493.75 ; markup 10% => 2743.125 -> 2743.13
    assert r.direct.direct_cost_total == Decimal("1875.00") and r.indirect.total == Decimal("500.00")
    c = r.commercial
    assert c.contingency == Decimal("118.75") and c.total_cost == Decimal("2493.75")
    assert c.selling_price_pre_discount == Decimal("2743.13")
    assert c.net_price == Decimal("2743.13")
    assert r.schedule.total_pre_tax - c.net_price in (Decimal("0"), r.schedule.rounding_variance)
    assert abs(r.schedule.rounding_variance) <= r.schedule.max_rounding_variance
    # VAT 15% on the tendered schedule total
    assert c.tax_total == (r.schedule.total_pre_tax * Decimal("0.15")).quantize(Decimal("0.01"))


def test_final_flow_and_gates(project):
    db, pid = project
    est = compute_estimate(db, pid)
    assert est.blockers == [], est.blockers
    run = recon.run_reconciliation(db, ESTIMATOR, pid)
    opens = recon.get_run(db, run["run_id"])["findings"]
    codes = {f["rule_code"] for f in opens}
    assert "OFFER_MISSING" in codes and "SYNTHETIC_DEMO" in codes
    vid = estimates.freeze_version(db, ESTIMATOR, pid, "v1")
    estimates.submit_version(db, ESTIMATOR, vid)
    # no one but a Commercial Approver / Admin may approve
    with pytest.raises(PermissionDenied):
        estimates.approve_version(db, ESTIMATOR, vid)
    estimates.approve_version(db, COMMERCIAL, vid)
    # tender export requires an approved offer
    with pytest.raises(ApprovalBlocked) as e:
        estimates.approve_tender_export(db, COMMERCIAL, pid, vid)
    assert e.value.code == "OFFER_NOT_APPROVED"
    o = offers.generate_offer(db, ESTIMATOR, pid, payment_terms="SYNTHETIC terms")
    offers.approve_offer(db, COMMERCIAL, pid, o["version_no"])
    ap = estimates.approve_tender_export(db, COMMERCIAL, pid, vid, "ok")
    files = estimates.export_submission(db, ESTIMATOR, pid, vid, ap)
    assert set(files) >= {"pricing_schedule", "letter_of_offer", "reconciliation_report"}
    from pathlib import Path
    assert all(Path(f).exists() for f in files.values())


def test_critical_blocks_final(project):
    db, pid = project
    # make an item unpriced -> Critical
    db.execute("UPDATE boq_items SET assembly_code=NULL, mapping_status='Unmapped', pricing_method='unpriced' WHERE project_id=? AND item_key='1.2'", (pid,))
    est = compute_estimate(db, pid)
    assert est.state.startswith("Preliminary")
    vid = estimates.freeze_version(db, ESTIMATOR, pid)
    estimates.submit_version(db, ESTIMATOR, vid)
    with pytest.raises(ApprovalBlocked):
        estimates.approve_version(db, COMMERCIAL, vid)
    g = recon.final_gate(db, COMMERCIAL, pid)
    assert g["blocked"] and any(b["rule_code"] == "UNPRICED_ITEM" for b in g["blockers"])
    # a Critical finding cannot be excepted
    f = next(b for b in g["blockers"] if b["rule_code"] == "UNPRICED_ITEM")
    with pytest.raises(PermissionDenied):
        recon.accept_exception(db, COMMERCIAL, f["id"], "trying to waive a critical finding")
