"""Row providers: turn database state + the strict estimate into rows for each workbook sheet."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from ..core.money import ZERO
from ..database import Database, jload, rows_to_dicts
from ..estimators.estimate import EstimateResult
from ..estimators.rate_resolution import resolve_rate
from ..procurement.leveling import level_package
from ..reconciliation.engine import get_run
from ..services import assemblies as asm_service
from ..services import assumptions as assumption_service


def trade_mapping(est: EstimateResult) -> list[dict]:
    return [dict(item_key=i["item_key"], item_code=i["item_code"], description=i["description"], trade=i["trade"], cost_code=i["cost_code"],
                 assembly_code=i["assembly_code"], mapping_status=i["mapping_status"], mapping_source=i["mapping_source"],
                 pricing_method=i["pricing_method"]) for i in est.inputs.items if i["item_type"] == "item"]


def pricing_schedule(est: EstimateResult) -> list[dict]:
    if not est.schedule:
        return []
    rows = [dict(item_code=l.item_code or l.item_key, description=l.description, unit=l.unit, quantity=l.quantity, unit_rate=l.unit_rate,
                 engine_amount=l.amount, status=l.status, flags=", ".join(l.flags)) for l in est.schedule.lines]
    for s in est.schedule.separate_lines:
        rows.append(dict(item_code=s["code"], description=s["description"], unit="ls", quantity=1, unit_rate=s["price"], engine_amount=s["price"],
                         status="Priced", flags="indirect shown as separate line"))
    return rows


def boq_import(est: EstimateResult) -> list[dict]:
    out = []
    for i in est.inputs.items:
        if i["item_type"] != "item":
            continue
        issues = "; ".join(x["message"] for x in jload(i.get("issues_json"), []))
        out.append(dict(item_code=i["item_code"], description=i["description"], trade=i["trade"], unit=i["unit"] or i["unit_original"],
                        quantity=i["quantity"], client_rate=i["client_rate"], client_amount=i["client_amount"], drawing_ref=i["drawing_ref"],
                        spec_ref=i["spec_ref"], cost_code=i["cost_code"], revision=i["revision"], source_file=i["source_file"],
                        source_sheet=i["source_sheet"], source_row=i["source_row"], quantity_original=i["quantity_original"],
                        unit_status=i["unit_status"], validation_status=i["validation_status"], issues=issues))
    return out


def direct_cost(est: EstimateResult) -> list[dict]:
    rows = []
    for l in est.direct.lines:
        rate = l.rate
        if l.kind == "plant" and l.amount is not None and l.quantity:
            rate = l.amount / l.quantity
        rows.append(dict(item_key=l.item_key, assembly=l.assembly_code, line_ref=l.line_ref, kind=l.kind, resource_id=l.resource_id,
                         description=l.description, quantity=l.quantity, unit=l.unit, rate=rate if l.amount is not None else None,
                         engine_amount=l.amount, rate_type=l.rate_type, rate_status=l.rate_status, eligibility=l.eligibility,
                         basis=l.basis, flags=", ".join(l.flags)))
    return rows


def library(db: Database, est: EstimateResult, types: tuple[str, ...], all_resources: bool = False) -> list[dict]:
    inp = est.inputs
    if all_resources:
        res = {r["id"]: dict(r) for r in db.all(f"SELECT * FROM resources WHERE resource_type IN ({','.join('?' * len(types))}) ORDER BY id", types)}
        rates_ = {rid: rows_to_dicts(db.all("SELECT * FROM resource_rates WHERE resource_id=?", (rid,))) for rid in res}
    else:
        res = {k: v for k, v in inp.resources.items() if v["resource_type"] in types}
        rates_ = inp.rates
    out = []
    for rid, r in sorted(res.items()):
        rr = resolve_rate(rates_.get(rid, []), project_id=est.project["id"], project_region=est.project.get("region") or "KSA-ALL", as_of=est.as_of,
                          region_parents=inp.region_parents)
        rate = rr.rate if rr.usable else None
        sup = None
        if rate and rate.get("supplier_id"):
            row = db.one("SELECT name FROM suppliers WHERE id=?", (rate["supplier_id"],))
            sup = row["name"] if row else rate["supplier_id"]
        out.append(dict(id=rid, cost_code=r["cost_code"], category=r["category"], description=r["description"], specification=r["specification"],
                        unit=r["unit"], rate=rate["unit_price"] if rate else None, currency=rate["currency"] if rate else None,
                        rate_type=rate["rate_type"] if rate else ("MISSING (" + rr.eligibility + ")"),
                        rate_status=rate["status"] if rate else rr.eligibility, price_date=rate["price_date"] if rate else None,
                        valid_until=rate["valid_until"] if rate else None, supplier=sup, evidence=rate["evidence"] if rate else None,
                        confidence=rate["confidence"] if rate else None, region=rate["region"] if rate else None))
    return out


def assemblies(db: Database, est: EstimateResult) -> list[dict]:
    out = []
    for code, a in sorted(est.inputs.assemblies.items()):
        row = db.one("SELECT confidence, source FROM assemblies WHERE code=? AND version=?", (code, a.version))
        for l in a.lines:
            crew = ";".join(f"{c['resource_id']}:{c.get('count', 1)}" for c in (l.get("crew") or []))
            out.append(dict(assembly_code=code, version=a.version, status=a.status, description=a.description, unit=a.unit, cost_code=a.cost_code,
                            line_no=l["line_no"], line_type=l["line_type"], resource_id=l["resource_id"], child_assembly_code=l["child_assembly_code"],
                            factor=l["factor"], factor_unit=l["factor_unit"], factor_includes_waste=l["factor_includes_waste"],
                            waste_basis=l["waste_basis"], waste_value=l["waste_value"], waste_ref=l["waste_ref"],
                            productivity_basis=l["productivity_basis"], crew=crew, includes_labour=l["includes_labour"],
                            includes_material=l["includes_material"], includes_plant=l["includes_plant"],
                            utilisation_basis=l["utilisation_basis"], utilisation_value=l["utilisation_value"], utilisation_ref=l["utilisation_ref"],
                            confidence=row["confidence"] if row else None, source=row["source"] if row else None))
    return out


def assumptions(db: Database, project_id: str, only_adopted: bool = True) -> list[dict]:
    out = []
    ids = [r["assumption_id"] for r in db.all("SELECT DISTINCT assumption_id FROM project_assumptions WHERE project_id=?", (project_id,))]
    for a in assumption_service.list_assumptions(db):
        if only_adopted and a["id"] not in ids:
            continue
        ra = assumption_service.resolve(db, project_id, a["id"])
        out.append(dict(id=a["id"], family=a["family"], name=a["name"], description=a["description"], applies_to=a["applies_to"], value=ra.value,
                        unit=ra.unit, status=ra.status, origin=ra.origin, engine_key=a["engine_key"], confidence=a["confidence"]))
    return out


def indirects(db: Database, est: EstimateResult) -> list[dict]:
    items = {r["code"]: r for r in db.all("SELECT * FROM indirect_items WHERE project_id=? AND status<>'Superseded'", (est.project["id"],))}
    out = []
    for l in est.indirect.lines:
        r = items.get(l.code, {})
        out.append(dict(code=l.code, category=l.category, description=l.description, method=l.method, amount=r["amount"] if r else None,
                        quantity=r["quantity"] if r else None, allocation_method=l.allocation_method, allocation_target=l.allocation_target,
                        included_in_subcontract=r["included_in_subcontract"] if r else 0, status=l.status, engine_amount=l.amount, basis=l.basis))
    return out


def procurement(db: Database, project_id: str) -> list[dict]:
    return rows_to_dicts(db.all("SELECT * FROM procurement_items WHERE project_id=? AND closed=0 ORDER BY id", (project_id,)))


def vendors(db: Database) -> list[dict]:
    return rows_to_dicts(db.all("SELECT * FROM suppliers ORDER BY id"))


def vendor_quotes(db: Database, project_id: str) -> list[dict]:
    out = []
    for q in db.all("SELECT * FROM quotations WHERE project_id=? ORDER BY id", (project_id,)):
        for l in db.all("SELECT * FROM quotation_lines WHERE quotation_id=? ORDER BY line_no", (q["id"],)):
            out.append(dict(quotation_id=q["id"], supplier_id=q["supplier_id"], reference=q["reference"], quote_date=q["quote_date"],
                            valid_until=q["valid_until"], currency=q["currency"], tax_treatment=q["tax_treatment"], tax_rate_pct=q["tax_rate_pct"],
                            payment_terms=q["payment_terms"], status=q["status"], line_no=l["line_no"], procurement_item_id=l["procurement_item_id"],
                            description=l["description"], quantity=l["quantity"], unit=l["unit"], unit_rate=l["unit_rate"], discount_pct=l["discount_pct"],
                            delivery_included=l["delivery_included"], unloading_included=l["unloading_included"], lead_time_days=l["lead_time_days"],
                            compliance=l["compliance"], comments=l["comments"]))
    return out


def quote_comparison(db: Database, project_id: str) -> list[dict]:
    out = []
    for p in db.all("SELECT id FROM procurement_packages WHERE project_id=?", (project_id,)):
        if not db.one("SELECT 1 FROM quotations WHERE package_id=?", (p["id"],)):
            continue
        lv = level_package(db, p["id"])
        for q in lv["quotations"]:
            sup = db.one("SELECT name FROM suppliers WHERE id=?", (q["supplier_id"],))
            out.append(dict(package_id=p["id"], quotation_id=q["quotation_id"], supplier=sup["name"] if sup else q["supplier_id"], validity=q["validity"],
                            coverage=q["coverage"], quoted_total=q["quoted_total"], currency=q["currency"], approved_adjustments=q["approved_adjustments"],
                            normalised_total=q["normalised_total"], like_for_like="Yes" if q["like_for_like"] else "No",
                            lead_time_days=q["lead_time_days"], payment_terms=q["payment_terms"], exclusions=q["exclusions"],
                            missing_items=", ".join(q["missing_items"]), notes="; ".join(q["notes"])))
    return out


def reconciliation(db: Database, project_id: str) -> list[dict]:
    try:
        run = get_run(db, project_id=project_id)
    except Exception:
        return []
    return [dict(severity=f["severity"], rule_code=f["rule_code"], title=f["title"], detail=f["detail"], entity=f"{f['entity_type'] or ''}:{f['entity_id'] or ''}",
                 financial_impact=f["financial_impact"], owner=f["owner"], status=f["status"], exception_reason=f.get("exception_reason"))
            for f in run["findings"]]


def approval_log(db: Database, project_id: str) -> list[dict]:
    return rows_to_dicts(db.all("SELECT * FROM approvals WHERE project_id=? OR project_id IS NULL ORDER BY id DESC LIMIT 5000", (project_id,)))


def sources(db: Database) -> list[dict]:
    return rows_to_dicts(db.all("SELECT * FROM sources ORDER BY source_id"))


def clarifications(db: Database, project_id: str) -> list[dict]:
    return rows_to_dicts(db.all("SELECT * FROM clarifications WHERE project_id=? ORDER BY id", (project_id,)))


def scope(db: Database, project_id: str) -> list[dict]:
    return rows_to_dicts(db.all("SELECT * FROM scope_register WHERE project_id=? ORDER BY id", (project_id,)))


def risks(db: Database, project_id: str) -> list[dict]:
    return rows_to_dicts(db.all("SELECT * FROM risks WHERE project_id=? ORDER BY id", (project_id,)))
