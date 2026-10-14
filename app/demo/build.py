"""Builds the clearly-labelled SYNTHETIC demonstration project. Library items are approved by the 'demo-seed' principal ONLY because
they are synthetic; the project is deliberately left with realistic open issues for the human walkthrough (docs/USER_GUIDE.md)."""
from __future__ import annotations

import csv
from pathlib import Path

from ..config import get_settings
from ..core.errors import AppError
from ..core.timeutil import today_iso
from ..database import Database
from ..imports import boq as boq_import
from ..models.actor import Actor
from ..services import assemblies, assumptions, boq, commercial, indirects, projects, rates, registers, suppliers
from . import data as D

SEED = Actor("demo-seed", "Administrator", "Demo data seeder (synthetic data only)")
NOTE = "SYNTHETIC DEMO DATA approved by the demo seeder - not a human review and not market data"


def write_demo_boq(path: Path) -> Path:
    """Client BOQ as it might arrive: headings, blank row, ambiguous unit, duplicate code, invalid quantity."""
    path.parent.mkdir(parents=True, exist_ok=True)
    header = ["Item", "Description", "Unit", "Qty", "Trade", "Drawing Ref", "Spec Ref"]
    rows = []
    for code, desc, unit, qty, trade, kind in D.BOQ:
        if kind == "BLANK":
            rows.append([None] * 7)
        elif kind == D.HEAD:
            rows.append([code, desc, None, None, trade, None, None])
        else:
            rows.append([code, desc, unit, qty, trade, "DWG-SYN-" + (code or "").split(".")[0].zfill(2) if code else None,
                         None if code in ("9.1", "9.4") else "SPEC-SYN-" + (code or "").split(".")[0].zfill(2)])
    if path.suffix == ".csv":
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
    else:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "BOQ"
        ws.append(["SYNTHETIC DEMO BOQ - NOT A REAL TENDER"])
        ws.append([])
        ws.append(header)
        for r in rows:
            ws.append(r)
        wb.save(path)
    return path


def _approve_rate(db, rid: str, price, unit: str, **kw) -> int:
    r = rates.propose_rate(db, SEED, rid, unit_price=price, rate_type="Synthetic Demonstration Rate", unit=unit, price_date="2026-09-01",
                           confidence="Medium", is_synthetic=True, evidence=D.TAG, submit=True, **kw)
    rates.approve_rate(db, SEED, r, comments=NOTE)
    return r


def seed_demo(db: Database, project_name: str = "DEMO - Synthetic Mixed-Use Building (SYNTHETIC)") -> dict:
    s = get_settings()
    existing = db.one("SELECT id FROM projects WHERE name=?", (project_name,))
    if existing:
        return {"project_id": existing["id"], "note": "Demo project already exists."}
    # The loader authors AND approves as the single 'demo-seed' principal (synthetic data only; recorded as an unregistered, non-human principal on a demonstration project).
    # Four-eyes is the default everywhere else, so it is relaxed only for the duration of this seeding and always restored.
    prior = s.allow_self_approval
    s.allow_self_approval = True
    try:
        return _seed_demo(db, project_name, s)
    finally:
        s.allow_self_approval = prior


def _seed_demo(db: Database, project_name: str, s) -> dict:
    with db.tx():
        for rid, rtype, desc, unit, cc, price, rate_unit, state in D.RESOURCES:
            rates.create_resource(db, SEED, resource_type=rtype, description=desc, unit=unit, cost_code=cc, id=rid, is_synthetic=True,
                                  notes=D.TAG)
            if state is None:
                rates.create_missing_placeholder(db, rid, unit=unit, created_by="demo-seed")
            elif state == "approved":
                _approve_rate(db, rid, price, rate_unit or unit)
            elif state == "pending":
                rates.propose_rate(db, SEED, rid, unit_price=price, rate_type="Synthetic Demonstration Rate", unit=unit, price_date="2026-09-01",
                                   confidence="Medium", is_synthetic=True, evidence=D.TAG, submit=True)
            elif state == "expired":
                r = rates.propose_rate(db, SEED, rid, unit_price=price, rate_type="Synthetic Demonstration Rate", unit=unit, price_date="2026-01-15",
                                       valid_until="2099-01-01", confidence="Medium", is_synthetic=True, evidence=D.TAG, submit=True)
                rates.approve_rate(db, SEED, r, comments=NOTE)
                db.update("resource_rates", {"valid_until": "2026-03-31"}, "id=?", (r,))      # simulate time passing: validity lapsed
                rates.expire_stale_rates(db, actor=SEED)
        for rid, d in D.LABOUR_BUILDUP.items():
            rates.create_resource(db, SEED, resource_type="labour", description=d["desc"], unit="hr", cost_code=d["cc"], id=rid, is_synthetic=True, notes=D.TAG)
            _approve_rate(db, rid, None, "hr", components=d["comps"])
        for rid, d in D.PLANT_BUILDUP.items():
            rates.create_resource(db, SEED, resource_type="plant", description=d["desc"], unit="hr", cost_code=d["cc"], id=rid, is_synthetic=True, notes=D.TAG)
            _approve_rate(db, rid, None, "hr", components=d["comps"])
        for code, desc, unit, cc, lines in D.ASSEMBLIES:
            assemblies.create_assembly(db, SEED, code=code, description=desc, unit=unit, cost_code=cc, is_synthetic=True, source=D.TAG,
                                       confidence="Low", lines_=[dict(l) for l in lines])
            assemblies.submit_assembly(db, SEED, code)
            assemblies.approve_assembly(db, SEED, code, comments=NOTE)
        for name, typ, trades in D.SUPPLIERS:
            suppliers.create_supplier(db, SEED, name=name, supplier_type=typ, trades=trades, is_synthetic=True, notes=D.TAG)
        pid = projects.create_project(db, SEED, name=project_name, client="SYNTHETIC CLIENT (DEMO)", location="SYNTHETIC SITE, Riyadh (demo)",
                                      region="KSA-CENTRAL", design_stage="Tender (synthetic)", tax_category="VAT-STD", is_demo=True,
                                      tender_ref="DEMO-TENDER-001", notes=D.TAG)
        for aid, (val, why) in D.OVERRIDES.items():
            assumptions.adopt(db, SEED, pid, aid)
            assumptions.set_override(db, SEED, pid, aid, val, why)
            assumptions.approve_override(db, SEED, pid, aid, comments=NOTE)
        pol = commercial.create_policy(db, SEED, code="DEMO-POL", name="Demo commercial policy (SYNTHETIC)", config=D.POLICY, is_synthetic=True, notes=D.TAG)
        commercial.submit_policy(db, SEED, pol)
        commercial.approve_policy(db, SEED, pol, comments=NOTE)
        commercial.assign_policy(db, SEED, pid, pol)
        for code, cat, desc, method, amt, qty, alloc, target, insub in D.INDIRECTS:
            indirects.add_indirect(db, SEED, pid, code=code, category=cat, description=desc, method=method, amount=amt, quantity=qty,
                                   allocation_method=alloc, allocation_target=target, included_in_subcontract=bool(insub), source=D.TAG, is_synthetic=True)
            indirects.submit_indirect(db, SEED, pid, code)
            indirects.approve_indirect(db, SEED, pid, code, comments=NOTE)
        did = indirects.propose_duration(db, SEED, pid, D.DURATION_MONTHS, "estimator_input", "SYNTHETIC DEMO duration")
        indirects.approve_duration(db, SEED, did, comments=NOTE)
    # BOQ import (outside the seeding transaction: importer opens its own)
    path = s.data_dir / "demo" / "demo_boq.xlsx"
    if not path.exists():
        write_demo_boq(path)
    summary = boq_import.import_boq(db, SEED, pid, path, sheet="BOQ", revision="A")
    with db.tx():
        for code, desc, unit, qty, trade, kind in D.BOQ:
            if kind in (D.HEAD, "BLANK", "REJECT"):
                continue
            key = code if kind != "DUP" else f"{code}#2"
            if kind.startswith("DEMO-A-"):
                boq.map_to_assembly(db, SEED, pid, key, kind, comment=NOTE)
                boq.set_cost_code(db, SEED, pid, key, db.scalar("SELECT cost_code FROM assemblies WHERE code=?", (kind,)))
            elif kind.startswith("SUBCON:"):
                boq.set_pricing(db, SEED, pid, key, "subcontract_lump", resource_id=kind.split(":")[1], note=D.TAG)
                boq.set_cost_code(db, SEED, pid, key, "J.01")
            elif kind.startswith("PSUM:"):
                boq.set_pricing(db, SEED, pid, key, "provisional_sum", amount=kind.split(":")[1], note="Client-stated provisional sum (SYNTHETIC)")
                boq.set_cost_code(db, SEED, pid, key, "L.10")
            elif kind.startswith("PCSUM:"):
                boq.set_pricing(db, SEED, pid, key, "prime_cost_sum", amount=kind.split(":")[1], note="Client-stated prime cost sum (SYNTHETIC)")
                boq.set_cost_code(db, SEED, pid, key, "L.11")
            elif kind == "EXCLUDED":
                boq.set_pricing(db, SEED, pid, key, "excluded", note="Landscaping by others per client BOQ")
                boq.set_cost_code(db, SEED, pid, key, "B.15")
            elif kind == "UNPRICED":
                boq.set_cost_code(db, SEED, pid, key, "A.05")
            elif kind == "DUP":
                boq.map_to_assembly(db, SEED, pid, key, "DEMO-A-CABLE", comment=NOTE)
                boq.set_cost_code(db, SEED, pid, key, "H.06")
        registers.add_clarification(db, SEED, pid, "Item 9.1: please confirm lift speed, capacity and the number of landings; drawing reference is missing.",
                                    trade="Specialist", boq_item_key="9.1", doc_ref="(none)", reason="Missing drawing/spec reference on a high-value item",
                                    commercial_impact="Lift package price varies with speed/capacity", cost_exposure="400000", owner="Estimator")
        registers.add_clarification(db, SEED, pid, "Item 9.5: who provides the temporary power connection and who pays authority fees?", trade="General",
                                    boq_item_key="9.5", reason="Responsibility unclear", owner="Estimator")
        registers.add_scope_entry(db, SEED, pid, "inclusion", "Testing and commissioning of all installed MEP systems as per specification (SYNTHETIC)",
                                  trade="General", cost_code="E")
        registers.add_scope_entry(db, SEED, pid, "exclusion", "Landscaping and irrigation (by others per client BOQ item 9.4)", trade="Civil",
                                  boq_item_key="9.4", cost_code="B.15", rationale="Client BOQ marks landscaping as by others")
        registers.add_scope_entry(db, SEED, pid, "qualification", "Prices are valid for 30 days and exclude VAT; VAT is added at the prevailing approved rate (SYNTHETIC)")
        registers.add_risk(db, SEED, pid, "Lift package lead time", description="Imported lifts may have long lead times; programme impact (SYNTHETIC)",
                           trade="Specialist", probability="Medium", impact="High", cost_exposure="50000", mitigation="Early RFQ and lead-time confirmation")
    return {"project_id": pid, "boq_import": {k: summary[k] for k in ("items_new", "headings", "blank", "rejected", "needs_review", "duplicates")},
            "label": D.TAG,
            "open_issues": ["VAT-STD tax category awaits Commercial Approver verification", "Ambiguous unit 'ton' on item 2.2", "Rates missing: sprinkler heads, AHU, CCTV, lift",
                            "Tile rate pending, cable tray rate expired", "Provisional/PC sums and exclusion awaiting approval", "Item 9.5 unpriced",
                            "Duplicate item code 6.1 and one rejected BOQ row"]}
