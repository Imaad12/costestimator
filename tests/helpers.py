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
                           price_date="2026-09-01", confidence="Low", is_synthetic=True, components=components,
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
