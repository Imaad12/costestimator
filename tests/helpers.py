"""Shared builders for tests (all figures SYNTHETIC)."""
from __future__ import annotations

import csv
from pathlib import Path

from app.services import assemblies, assumptions, boq, commercial, indirects, projects, rates
from app.imports import boq as boq_import

from tests.conftest import ADMIN, COMMERCIAL, ESTIMATOR, PROCUREMENT


def approved_rate(db, rid, price, unit=None, rate_type="Synthetic Demonstration Rate", components=None, **kw):
    res = db.one("SELECT unit FROM resources WHERE id=?", (rid,))
    r = rates.propose_rate(db, ESTIMATOR, rid, unit_price=price, rate_type=rate_type, unit=unit or res["unit"],
                           price_date="2026-09-01", confidence="Medium", is_synthetic=True, components=components,
                           evidence="SYNTHETIC / DEMO / NOT A MARKET QUOTE", submit=True, **kw)
    rates.approve_rate(db, PROCUREMENT, r)
    return r


def approve_assumption(db, aid, value=None):
    if value is not None:
        assumptions.revise_assumption(db, ESTIMATOR, aid, default_value=str(value))
    assumptions.submit_assumption(db, ESTIMATOR, aid)
    assumptions.approve_assumption(db, COMMERCIAL, aid)


def write_boq(path: Path, rows, header=("Item", "Description", "Unit", "Qty", "Rate", "Amount")):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return path


def approved_assembly(db, code, unit, lines, cost_code="C.01", description=None):
    assemblies.create_assembly(db, ESTIMATOR, code=code, description=description or code, unit=unit, cost_code=cost_code,
                               is_synthetic=True, source="SYNTHETIC test assembly", lines_=lines)
    assemblies.submit_assembly(db, ESTIMATOR, code)
    assemblies.approve_assembly(db, COMMERCIAL, code)


def std_policy(db, project_id, method="markup", markup="10", **extra):
    cfg = {"method": method, "markup_pct": markup, "margin_pct": markup, "default_tax_category": "VAT-STD",
           "contingency": {"pct": "5", "base": "direct_indirect"}, "risk_items": [], "rounding": {"dp": 2}}
    cfg.update(extra)
    pid = commercial.create_policy(db, ESTIMATOR, code="POL-TEST", name="Test policy (SYNTHETIC)", config=cfg, is_synthetic=True)
    commercial.submit_policy(db, ESTIMATOR, pid)
    commercial.approve_policy(db, COMMERCIAL, pid)
    commercial.assign_policy(db, ESTIMATOR, project_id, pid)
    return pid


def approve_vat(db):
    tid = db.scalar("SELECT id FROM tax_categories WHERE code='VAT-STD'")
    commercial.approve_tax_category(db, COMMERCIAL, tid, evidence="TEST: verified against test fixture (not an official check)")


def build_mini(db, tmp_path, *, with_indirect=True):
    """Complete, resolvable SYNTHETIC mini project (all rates/assembly/policy/tax approved). Returns project id."""
    from app.imports import boq as bi
    from app.services import boq, commercial, indirects, projects
    from app.services.rates import create_resource
    create_resource(db, ESTIMATOR, resource_type="material", description="DEMO Ready-mix C30", unit="m3", cost_code="C.01", id="DEMO-MAT-001", is_synthetic=True)
    create_resource(db, ESTIMATOR, resource_type="labour", description="DEMO Labourer", unit="hr", cost_code="C", id="DEMO-LAB-001", is_synthetic=True)
    approved_rate(db, "DEMO-MAT-001", "100")
    approved_rate(db, "DEMO-LAB-001", "10")
    approved_assembly(db, "DEMO-CONC", "m3", [
        dict(line_type="material", resource_id="DEMO-MAT-001", factor="1.05", factor_includes_waste=1),
        dict(line_type="labour", resource_id="DEMO-LAB-001", factor="2", productivity_basis="paid_hours_per_unit")],
        description="Reinforced concrete C30 foundations per m3")
    pid = projects.create_project(db, ESTIMATOR, name="Mini (SYNTHETIC)", is_demo=True, tax_category="VAT-STD")
    f = write_boq(tmp_path / "mini.csv", [("1.1", "Concrete", "m3", "10", "", ""), ("1.2", "Concrete B", "cum", "5", "", "")])
    bi.import_boq(db, ESTIMATOR, pid, f)
    for k in ("1.1", "1.2"):
        boq.map_to_assembly(db, ESTIMATOR, pid, k, "DEMO-CONC")
    std_policy(db, pid)
    approve_vat(db)
    if with_indirect:
        indirects.add_indirect(db, ESTIMATOR, pid, code="IND-1", category="Project management", description="PM lump (SYNTHETIC)", method="fixed", amount="500",
                               is_synthetic=True)
        indirects.submit_indirect(db, ESTIMATOR, pid, "IND-1")
        indirects.approve_indirect(db, COMMERCIAL, pid, "IND-1")
    return pid
