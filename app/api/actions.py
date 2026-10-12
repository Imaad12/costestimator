"""Single registry of state-changing actions used by BOTH the REST API (/api/actions/{name}) and the web UI.
Every action calls a service that enforces permissions and approval rules on the server."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..ai import service as ai_service
from ..core.errors import ValidationFailed
from ..database import Database
from ..imports import datasets
from ..models.actor import Actor
from ..procurement import leveling, needs, quotes, rfq, selection
from ..reconciliation import engine as recon
from ..services import (assemblies, assumptions, backup, boq, commercial, estimates, indirects, offers, projects, rates, registers,
                        refdata, suggestions, suppliers)
from ..services import audit

ACTIONS: dict[str, Callable[[Database, Actor, dict], Any]] = {}


def action(name: str):
    def deco(fn):
        ACTIONS[name] = fn
        return fn
    return deco


def req(p: dict, *keys: str) -> list:
    out = []
    for k in keys:
        v = p.get(k)
        if v is None or (isinstance(v, str) and not v.strip()):
            raise ValidationFailed(f"'{k}' is required.", code="FIELD_REQUIRED")
        out.append(v.strip() if isinstance(v, str) else v)
    return out


def opt(p: dict, k: str):
    v = p.get(k)
    return None if v is None or (isinstance(v, str) and not v.strip()) else (v.strip() if isinstance(v, str) else v)


def run(db: Database, actor: Actor, name: str, params: dict) -> Any:
    if name not in ACTIONS:
        raise ValidationFailed(f"Unknown action '{name}'.", code="UNKNOWN_ACTION")
    return ACTIONS[name](db, actor, params)


# ---------------------------------------------------------------- projects
@action("create_project")
def _(db, a, p):
    return projects.create_project(db, a, name=req(p, "name")[0], client=opt(p, "client") or "", location=opt(p, "location") or "",
                                   region=opt(p, "region") or "KSA-ALL", design_stage=opt(p, "design_stage") or "",
                                   tax_category=opt(p, "tax_category") or "VAT-STD", tender_ref=opt(p, "tender_ref") or "",
                                   project_type=opt(p, "project_type") or "",
                                   trades=[t.strip() for t in (opt(p, "trades") or "").replace(";", ",").split(",") if t.strip()],
                                   drawing_revision=opt(p, "drawing_revision") or "", spec_revision=opt(p, "spec_revision") or "")


@action("archive_project")
def _(db, a, p):
    projects.archive_project(db, a, req(p, "project_id")[0], req(p, "reason")[0])


# ---------------------------------------------------------------- BOQ
@action("decide_change")
def _(db, a, p):
    boq.decide_change(db, a, int(req(p, "change_id")[0]), p.get("decision") == "approve", comment=opt(p, "comment"), unit_code=opt(p, "unit_code"))


@action("request_quantity_change")
def _(db, a, p):
    return boq.request_quantity_change(db, a, *req(p, "project_id", "item_key", "new_quantity", "reason"))


@action("map_item")
def _(db, a, p):
    pid, key, code = req(p, "project_id", "item_key", "assembly_code")
    boq.map_to_assembly(db, a, pid, key, code, source="manual", comment=opt(p, "comment"))


@action("approve_mapping")
def _(db, a, p):
    boq.approve_mapping(db, a, *req(p, "project_id", "item_key"), comment=opt(p, "comment"))


@action("set_cost_code")
def _(db, a, p):
    boq.set_cost_code(db, a, *req(p, "project_id", "item_key", "cost_code"))


@action("set_pricing")
def _(db, a, p):
    pid, key, method = req(p, "project_id", "item_key", "method")
    boq.set_pricing(db, a, pid, key, method, resource_id=opt(p, "resource_id"), amount=opt(p, "amount"), note=opt(p, "note"))


@action("decide_pricing")
def _(db, a, p):
    boq.decide_pricing(db, a, *req(p, "project_id", "item_key", "decision"), comment=req(p, "comment")[0])


@action("acknowledge_issues")
def _(db, a, p):
    boq.acknowledge_issues(db, a, *req(p, "project_id", "item_key", "comment"))


# ---------------------------------------------------------------- libraries
@action("create_resource")
def _(db, a, p):
    return rates.create_resource(db, a, resource_type=req(p, "resource_type")[0], description=req(p, "description")[0], unit=req(p, "unit")[0],
                                 cost_code=opt(p, "cost_code"), category=opt(p, "category"), specification=opt(p, "specification"))


@action("propose_rate")
def _(db, a, p):
    import json
    comps = None
    if opt(p, "components"):
        try:
            comps = json.loads(opt(p, "components"))
        except ValueError as e:
            raise ValidationFailed(f"Build-up components must be valid JSON: {e}")
        if not isinstance(comps, dict):
            raise ValidationFailed("Build-up components must be a JSON object.")
    if comps and not opt(p, "unit_price"):
        p = {**p, "unit_price": "0"}          # price is derived from the build-up below
    return rates.propose_rate(db, a, req(p, "resource_id")[0], unit_price=None if comps else req(p, "unit_price")[0], components=comps, rate_type=req(p, "rate_type")[0],
                              currency=opt(p, "currency") or "SAR", price_date=opt(p, "price_date"), valid_until=opt(p, "valid_until"),
                              region=opt(p, "region") or "KSA-ALL", evidence=opt(p, "evidence"), source_id=opt(p, "source_id"),
                              supplier_id=opt(p, "supplier_id"), confidence=opt(p, "confidence") or "Unverified", submit=bool(p.get("submit")))


@action("submit_rate")
def _(db, a, p):
    rates.submit_rate(db, a, int(req(p, "rate_id")[0]))


@action("approve_rate")
def _(db, a, p):
    rates.approve_rate(db, a, int(req(p, "rate_id")[0]), comments=opt(p, "comments"), evidence=opt(p, "evidence"))


@action("approve_rate_provisional")
def _(db, a, p):
    rates.approve_rate_provisional(db, a, int(req(p, "rate_id")[0]), req(p, "project_id")[0], comments=req(p, "comments")[0])


@action("reject_rate")
def _(db, a, p):
    rates.reject_rate(db, a, int(req(p, "rate_id")[0]), req(p, "reason")[0])


# ---------------------------------------------------------------- assumptions
@action("revise_assumption")
def _(db, a, p):
    return assumptions.revise_assumption(db, a, req(p, "id")[0], default_value=req(p, "value")[0])


@action("submit_assumption")
def _(db, a, p):
    assumptions.submit_assumption(db, a, req(p, "id")[0])


@action("approve_assumption")
def _(db, a, p):
    assumptions.approve_assumption(db, a, req(p, "id")[0], comments=opt(p, "comments"), evidence=opt(p, "evidence"))


@action("reject_assumption")
def _(db, a, p):
    assumptions.reject_assumption(db, a, req(p, "id")[0], req(p, "reason")[0])


@action("adopt_assumption")
def _(db, a, p):
    assumptions.adopt(db, a, *req(p, "project_id", "id"))


@action("set_override")
def _(db, a, p):
    assumptions.set_override(db, a, *req(p, "project_id", "id", "value", "reason"))


@action("approve_override")
def _(db, a, p):
    assumptions.approve_override(db, a, *req(p, "project_id", "id"), comments=opt(p, "comments"))


@action("reject_override")
def _(db, a, p):
    assumptions.reject_override(db, a, *req(p, "project_id", "id", "reason"))


# ---------------------------------------------------------------- assemblies
@action("submit_assembly")
def _(db, a, p):
    assemblies.submit_assembly(db, a, req(p, "code")[0])


@action("approve_assembly")
def _(db, a, p):
    assemblies.approve_assembly(db, a, req(p, "code")[0], comments=opt(p, "comments"))


@action("reject_assembly")
def _(db, a, p):
    assemblies.reject_assembly(db, a, *req(p, "code", "reason"))


@action("new_assembly_version")
def _(db, a, p):
    return assemblies.new_version(db, a, req(p, "code")[0], revision_note=opt(p, "note"))


@action("clone_assembly")
def _(db, a, p):
    return assemblies.clone(db, a, *req(p, "code", "new_code"), project_id=opt(p, "project_id"))


@action("create_assembly")
def _(db, a, p):
    return assemblies.create_assembly(db, a, code=req(p, "code")[0], description=req(p, "description")[0], unit=req(p, "unit")[0], cost_code=opt(p, "cost_code"),
                                      specification=opt(p, "specification"), source=opt(p, "source"), project_id=opt(p, "project_id"))


def _line_params(p: dict) -> dict:
    out = {k: opt(p, k) for k in ("line_type", "resource_id", "child_assembly_code", "factor", "factor_unit", "waste_basis", "waste_value", "waste_ref",
                                  "productivity_basis", "utilisation_basis", "utilisation_value", "utilisation_ref", "overtime_share_pct", "notes")
           if opt(p, k) is not None}
    for k in ("factor_includes_waste", "includes_labour", "includes_material", "includes_plant", "explicitly_separate"):
        if p.get(k) not in (None, "", "0", 0, False):
            out[k] = 1
    crew = opt(p, "crew")
    if crew:
        members = []
        for part in str(crew).split(";"):
            if ":" in part:
                rid, cnt = part.split(":", 1)
                members.append({"resource_id": rid.strip(), "count": float(cnt)})
        if members:
            out["crew"] = members
    return out


@action("add_assembly_line")
def _(db, a, p):
    asm = assemblies.get(db, req(p, "code")[0])
    return assemblies.add_line(db, a, asm["pk"], **_line_params(p))


@action("update_assembly_line")
def _(db, a, p):
    asm = assemblies.get(db, req(p, "code")[0])
    ch = _line_params(p)
    ch.pop("line_type", None)
    assemblies.update_line(db, a, asm["pk"], int(req(p, "line_no")[0]), **ch)


@action("remove_assembly_line")
def _(db, a, p):
    asm = assemblies.get(db, req(p, "code")[0])
    assemblies.remove_line(db, a, asm["pk"], int(req(p, "line_no")[0]))


# ---------------------------------------------------------------- indirects / commercial
@action("create_policy")
def _(db, a, p):
    import json
    try:
        cfg = json.loads(req(p, "config")[0])
    except ValueError as e:
        raise ValidationFailed(f"Policy configuration is not valid JSON: {e}")
    return commercial.create_policy(db, a, code=req(p, "code")[0], name=req(p, "name")[0], config=cfg)


@action("edit_policy")
def _(db, a, p):
    import json
    try:
        cfg = json.loads(req(p, "config")[0])
    except ValueError as e:
        raise ValidationFailed(f"Policy configuration is not valid JSON: {e}")
    return commercial.edit_policy(db, a, int(req(p, "policy_id")[0]), cfg)
@action("add_indirect")
def _(db, a, p):
    return indirects.add_indirect(db, a, req(p, "project_id")[0], code=req(p, "code")[0], category=req(p, "category")[0], description=req(p, "description")[0],
                                  method=req(p, "method")[0], amount=opt(p, "amount"), quantity=opt(p, "quantity") or "1",
                                  allocation_method=opt(p, "allocation_method") or "pro_rata_direct", allocation_target=opt(p, "allocation_target"),
                                  included_in_subcontract=bool(p.get("included_in_subcontract")))


@action("submit_indirect")
def _(db, a, p):
    indirects.submit_indirect(db, a, *req(p, "project_id", "code"))


@action("approve_indirect")
def _(db, a, p):
    indirects.approve_indirect(db, a, *req(p, "project_id", "code"), comments=opt(p, "comments"))


@action("propose_duration")
def _(db, a, p):
    return indirects.propose_duration(db, a, req(p, "project_id")[0], req(p, "months")[0], opt(p, "source_type") or "estimator_input", req(p, "basis_note")[0])


@action("approve_duration")
def _(db, a, p):
    indirects.approve_duration(db, a, int(req(p, "duration_id")[0]), comments=opt(p, "comments"))


@action("submit_policy")
def _(db, a, p):
    commercial.submit_policy(db, a, int(req(p, "policy_id")[0]))


@action("approve_policy")
def _(db, a, p):
    commercial.approve_policy(db, a, int(req(p, "policy_id")[0]), comments=opt(p, "comments"))


@action("assign_policy")
def _(db, a, p):
    commercial.assign_policy(db, a, req(p, "project_id")[0], int(req(p, "policy_id")[0]))


@action("approve_tax_category")
def _(db, a, p):
    commercial.approve_tax_category(db, a, int(req(p, "tax_id")[0]), evidence=req(p, "evidence")[0], comments=opt(p, "comments"))


@action("propose_fx")
def _(db, a, p):
    return commercial.propose_fx(db, a, *req(p, "from_ccy", "to_ccy", "rate", "rate_date", "source"), valid_until=opt(p, "valid_until"))


@action("approve_fx")
def _(db, a, p):
    commercial.approve_fx(db, a, int(req(p, "fx_id")[0]), comments=opt(p, "comments"))


# ---------------------------------------------------------------- procurement
@action("detect_needs")
def _(db, a, p):
    return needs.detect_needs(db, a, req(p, "project_id")[0])


@action("create_rfq")
def _(db, a, p):
    pid, pkg = req(p, "project_id", "package_id")
    return rfq.create_rfq(db, a, pid, pkg, supplier_id=opt(p, "supplier_id"), language=opt(p, "language") or "en", response_deadline=opt(p, "response_deadline"))


@action("mark_rfq_issued")
def _(db, a, p):
    rfq.mark_issued(db, a, req(p, "rfq_id")[0])


@action("create_supplier")
def _(db, a, p):
    return suppliers.create_supplier(db, a, name=req(p, "name")[0], supplier_type=opt(p, "supplier_type") or "supplier", trades=opt(p, "trades") or "",
                                     contact_name=opt(p, "contact_name"), contact_email=opt(p, "contact_email"), contact_phone=opt(p, "contact_phone"),
                                     contact_source=opt(p, "contact_source"))


@action("qualify_supplier")
def _(db, a, p):
    suppliers.qualify_supplier(db, a, req(p, "supplier_id")[0], opt(p, "comments"))


@action("create_quotation")
def _(db, a, p):
    return quotes.create_quotation(db, a, supplier_id=req(p, "supplier_id")[0], project_id=opt(p, "project_id"), package_id=opt(p, "package_id"),
                                   reference=opt(p, "reference"), quote_date=opt(p, "quote_date"), valid_until=opt(p, "valid_until"),
                                   currency=opt(p, "currency") or "SAR", payment_terms=opt(p, "payment_terms"), tax_treatment=opt(p, "tax_treatment"),
                                   tax_rate_pct=opt(p, "tax_rate_pct"), exclusions=opt(p, "exclusions"), deviations=opt(p, "deviations"))


@action("add_quote_line")
def _(db, a, p):
    qid = req(p, "quotation_id")[0]
    line = {k: opt(p, k) for k in ("procurement_item_id", "description", "specification", "quantity", "unit", "unit_rate", "discount_pct",
                                   "delivery_included", "unloading_included", "lead_time_days", "compliance", "comments") if opt(p, k) is not None}
    return quotes.add_line(db, a, qid, **line)


@action("submit_quotation")
def _(db, a, p):
    quotes.submit_quotation(db, a, req(p, "quotation_id")[0])


@action("approve_quotation")
def _(db, a, p):
    quotes.approve_quotation(db, a, req(p, "quotation_id")[0], comments=opt(p, "comments"), evidence=opt(p, "evidence"))


@action("reject_quotation")
def _(db, a, p):
    quotes.reject_quotation(db, a, *req(p, "quotation_id", "reason"))


@action("add_adjustment")
def _(db, a, p):
    return leveling.add_adjustment(db, a, req(p, "quotation_id")[0], req(p, "adj_type")[0], req(p, "amount")[0], req(p, "basis")[0], opt(p, "description") or "")


@action("approve_adjustment")
def _(db, a, p):
    leveling.approve_adjustment(db, a, int(req(p, "adjustment_id")[0]), opt(p, "comments"))


@action("propose_selection")
def _(db, a, p):
    return selection.propose_selection(db, a, *req(p, "package_id", "quotation_id", "justification"), not_lowest_reason=opt(p, "not_lowest_reason"))


@action("decide_selection")
def _(db, a, p):
    selection.decide_selection(db, a, int(req(p, "selection_id")[0]), p.get("decision") == "approve", comments=opt(p, "comments"))


@action("publish_rates")
def _(db, a, p):
    return selection.publish_rates(db, a, int(req(p, "selection_id")[0]))


# ---------------------------------------------------------------- registers
@action("add_clarification")
def _(db, a, p):
    return registers.add_clarification(db, a, req(p, "project_id")[0], req(p, "question")[0], trade=opt(p, "trade"), boq_item_key=opt(p, "boq_item_key"),
                                       doc_ref=opt(p, "doc_ref"), reason=opt(p, "reason"), commercial_impact=opt(p, "commercial_impact"),
                                       cost_exposure=opt(p, "cost_exposure"), proposed_wording=opt(p, "proposed_wording"), owner=opt(p, "owner"))


@action("resolve_clarification")
def _(db, a, p):
    registers.resolve_clarification(db, a, *req(p, "id", "client_response", "evidence"))


@action("clarification_status")
def _(db, a, p):
    registers.set_clarification_status(db, a, *req(p, "id", "status"))


@action("add_scope_entry")
def _(db, a, p):
    return registers.add_scope_entry(db, a, req(p, "project_id")[0], req(p, "kind")[0], req(p, "description")[0], trade=opt(p, "trade"),
                                     boq_item_key=opt(p, "boq_item_key"), cost_code=opt(p, "cost_code"), rationale=opt(p, "rationale"))


@action("approve_scope_entry")
def _(db, a, p):
    registers.approve_scope_entry(db, a, req(p, "id")[0], opt(p, "comments"))


@action("add_risk")
def _(db, a, p):
    return registers.add_risk(db, a, req(p, "project_id")[0], req(p, "title")[0], description=opt(p, "description") or "", trade=opt(p, "trade"),
                              probability=opt(p, "probability"), impact=opt(p, "impact"), cost_exposure=opt(p, "cost_exposure"), mitigation=opt(p, "mitigation"))


# ---------------------------------------------------------------- estimate / reconciliation / export
@action("run_reconciliation")
def _(db, a, p):
    return recon.run_reconciliation(db, a, req(p, "project_id")[0])


@action("accept_exception")
def _(db, a, p):
    recon.accept_exception(db, a, int(req(p, "finding_id")[0]), req(p, "reason")[0])


@action("freeze_version")
def _(db, a, p):
    return estimates.freeze_version(db, a, req(p, "project_id")[0], opt(p, "label") or "", opt(p, "notes") or "")


@action("submit_version")
def _(db, a, p):
    estimates.submit_version(db, a, int(req(p, "version_id")[0]))


@action("approve_version")
def _(db, a, p):
    return estimates.approve_version(db, a, int(req(p, "version_id")[0]), opt(p, "comments"))


@action("generate_offer")
def _(db, a, p):
    return offers.generate_offer(db, a, req(p, "project_id")[0], validity_days=int(opt(p, "validity_days") or 30), payment_terms=opt(p, "payment_terms") or "",
                                 signatory=opt(p, "signatory") or "[Authorised signatory]")


@action("approve_offer")
def _(db, a, p):
    offers.approve_offer(db, a, req(p, "project_id")[0], int(req(p, "version_no")[0]), opt(p, "comments"))


@action("preliminary_export")
def _(db, a, p):
    return estimates.preliminary_export(db, a, req(p, "project_id")[0])


@action("approve_tender_export")
def _(db, a, p):
    return estimates.approve_tender_export(db, a, req(p, "project_id")[0], int(req(p, "version_id")[0]), opt(p, "comments"))


@action("export_submission")
def _(db, a, p):
    return estimates.export_submission(db, a, req(p, "project_id")[0], int(req(p, "version_id")[0]), int(req(p, "approval_id")[0]))


# ---------------------------------------------------------------- AI / suggestions
@action("heuristic_mapping")
def _(db, a, p):
    from ..approvals import engine as ap
    ap.require_author(a)
    return ai_service.heuristic_mapping(db, req(p, "project_id")[0])


@action("scope_checks")
def _(db, a, p):
    from ..approvals import engine as ap
    ap.require_author(a)
    return ai_service.deterministic_scope_checks(db, req(p, "project_id")[0])


@action("ai_suggest_mappings")
def _(db, a, p):
    from ..approvals import engine as ap
    ap.require_author(a)
    return ai_service.ai_suggest_mappings(db, req(p, "project_id")[0])


@action("accept_suggestion")
def _(db, a, p):
    return suggestions.accept(db, a, int(req(p, "suggestion_id")[0]), comment=req(p, "comment")[0], supplier_id=opt(p, "supplier_id"))


@action("reject_suggestion")
def _(db, a, p):
    suggestions.reject(db, a, int(req(p, "suggestion_id")[0]), req(p, "comment")[0])


# ---------------------------------------------------------------- datasets / admin
@action("decide_dataset_rows")
def _(db, a, p):
    ids = [int(x) for x in str(req(p, "row_ids")[0]).split(",") if x.strip()]
    datasets.decide_rows(db, a, int(req(p, "dataset_id")[0]), ids, req(p, "decision")[0])


@action("publish_dataset")
def _(db, a, p):
    return datasets.publish_dataset(db, a, int(req(p, "dataset_id")[0]))


@action("record_actual")
def _(db, a, p):
    from ..reporting import history
    return history.record_actual(db, a, req(p, "project_id")[0], source=req(p, "source")[0], cost_code=opt(p, "cost_code"), resource_id=opt(p, "resource_id"),
                                 actual_amount=opt(p, "actual_amount"), actual_quantity=opt(p, "actual_quantity"), actual_hours=opt(p, "actual_hours"),
                                 description=opt(p, "description"), cost_date=opt(p, "cost_date"))


@action("add_cost_code")
def _(db, a, p):
    from ..approvals import engine as ap
    ap.require_admin(a, "taxonomy changes")
    code, name, parent = req(p, "code", "name", "parent_code")
    par = db.one("SELECT * FROM cost_codes WHERE code=?", (parent,))
    if not par:
        raise ValidationFailed(f"Parent code {parent} not found.")
    if db.one("SELECT 1 FROM cost_codes WHERE code=?", (code,)):
        raise ValidationFailed(f"Cost code {code} exists.")
    db.insert("cost_codes", dict(code=code, parent_code=parent, level=par["level"] + 1, kind="subtrade" if par["level"] >= 1 else "trade", name=name,
                                 default_unit=opt(p, "default_unit"), active=1, is_system=0))
    audit.log(db, a, "cost_code", code, "create", after={"name": name, "parent": parent})
    return code


@action("create_backup")
def _(db, a, p):
    from ..approvals import engine as ap
    ap.require_admin(a, "backup")
    return str(backup.create_backup())


@action("save_company_settings")
def _(db, a, p):
    import json
    from ..approvals import engine as ap
    from ..config import get_settings
    from ..core.timeutil import now_iso
    ap.require_admin(a, "company settings")
    co = get_settings().company
    for k in ("name", "address", "cr_number", "vat_number", "contact_name", "contact_email", "contact_phone"):
        if opt(p, k) is not None:
            co[k] = opt(p, k)
    val = json.dumps(co, ensure_ascii=False)
    if db.one("SELECT 1 FROM settings WHERE key='company'"):
        db.update("settings", {"value": val, "updated_at": now_iso(), "updated_by": a.username}, "key='company'")
    else:
        db.insert("settings", dict(key="company", value=val, updated_at=now_iso(), updated_by=a.username))
    audit.log(db, a, "settings", "company", "update", after={k: co.get(k) for k in co})


@action("create_user")
def _(db, a, p):
    from ..approvals import engine as ap
    ap.require_admin(a, "user administration")
    username, role, pw = req(p, "username", "role", "password")
    if len(pw) < 8:
        raise ValidationFailed("Password must be at least 8 characters.")
    from ..services import auth
    auth.create_user(db, username, opt(p, "display_name") or username, role, pw, creator=a)
    return username


@action("export_project_package")
def _(db, a, p):
    from ..approvals import engine as ap
    ap.require_author(a)
    return str(backup.export_project_package(db, req(p, "project_id")[0]))


@action("add_standard_indirects")
def _(db, a, p):
    """Create Draft indirect items (no amounts) for every standard category so nothing is forgotten; amounts must be entered, never defaulted."""
    import csv as _csv
    from ..config import get_settings
    pid = req(p, "project_id")[0]
    n = 0
    path = get_settings().data_dir / "indirects" / "indirect_categories.csv"
    for r in _csv.DictReader(open(path, encoding="utf-8-sig")):
        if db.one("SELECT 1 FROM indirect_items WHERE project_id=? AND code=?", (pid, r["code"])):
            continue
        method = r["typical_methods"].split("|")[0]
        indirects.add_indirect(db, a, pid, code=r["code"], category=r["category"], description=r["description"], method=method, amount=None, notes=r["notes"],
                               source="data/indirects/indirect_categories.csv (no amount supplied)")
        n += 1
    return n


# ---------------------------------------------------------------- workspaces / documents / public-source rate updates
@action("update_project")
def _(db, a, p):
    pid = req(p, "project_id")[0]
    changes = {k: opt(p, k) or "" for k in ("project_type", "drawing_revision", "spec_revision", "design_stage", "tender_ref", "location", "client") if k in p}
    if "trades" in p:
        changes["trades"] = [t.strip() for t in (opt(p, "trades") or "").replace(";", ",").split(",") if t.strip()]
    projects.update_project(db, a, pid, **changes)


@action("refresh_workspace")
def _(db, a, p):
    from ..services import workspaces
    from ..approvals import engine as _ap
    _ap.require_author(a)
    return str(workspaces.ensure_workspace(db, req(p, "project_id")[0]))


@action("index_project_documents")
def _(db, a, p):
    from ..services import project_index
    r = project_index.index_project(db, a, req(p, "project_id")[0])
    return f"{r['new']} new, {r['changed']} changed, {r['unchanged']} unchanged, {r['missing']} missing; {r['extracted']} extracted, {r['not_extracted']} not text-extracted"


@action("mark_document_reviewed")
def _(db, a, p):
    from ..services import project_index
    project_index.mark_reviewed(db, a, req(p, "project_id")[0], int(req(p, "doc_id")[0]), opt(p, "comment") or "")


@action("review_rate_candidate")
def _(db, a, p):
    from ..rate_updates import candidates
    return candidates.review(db, a, req(p, "candidate")[0], req(p, "decision")[0], opt(p, "comment") or "")["status"]


@action("edit_rate_candidate")
def _(db, a, p):
    from ..rate_updates import candidates
    ch = {k: opt(p, k) for k in ("resource_id", "unit", "tax_basis", "delivery_basis", "installation_included", "geography", "specification",
                                 "valid_until", "effective_date", "confidence", "price_kind") if opt(p, k)}
    return candidates.edit(db, a, req(p, "candidate")[0], **ch)["queue"]


@action("publish_rate_candidate")
def _(db, a, p):
    from ..rate_updates import candidates
    return candidates.publish(db, a, req(p, "candidate")[0])


@action("refresh_sources")
def _(db, a, p):
    """Dry-run by default. A live refresh contacts only providers whose policy permits automated access and only creates proposals."""
    from ..rate_updates import refresh
    live = str(p.get("live", "")).lower() in ("1", "true", "yes", "on")
    rep = refresh.refresh_sources(db, a, provider_ids=[x for x in [opt(p, "provider")] if x] or None, dry_run=not live)
    s = rep["summary"]
    return (f"{'LIVE' if live else 'DRY RUN'}: {s['successful']} ok, {s['blocked']} blocked, {s['skipped_or_dry_run']} skipped/dry, {s['errors']} errors; "
            f"{s['new_candidates']} new candidate(s), {s['new_or_revised_index_rows']} index row(s)")
