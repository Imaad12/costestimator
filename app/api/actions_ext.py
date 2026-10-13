"""Actions added in iteration 4 (governed parameters, WBS/CBS, programme, analyses, controls ...). Registered into the same registry as actions.py;
every action calls a service that enforces roles and approval rules on the server."""
from __future__ import annotations

import json
from typing import Any

from ..core.errors import ValidationFailed
from .actions import action, opt, req


def jdict(p: dict, key: str, required: bool = True) -> Any:
    """A dict/list given as a real object (REST) or JSON text (HTML form)."""
    raw = p.get(key)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        if required:
            raise ValidationFailed(f"'{key}' is required.", code="FIELD_REQUIRED")
        return None
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValidationFailed(f"'{key}' is not valid JSON: {e}", code="BAD_JSON")
    return raw


# ---------------------------------------------------------------- governed parameters
@action("propose_param")
def _(db, a, p):
    from ..services import governed
    return governed.propose(db, a, req(p, "kind")[0], req(p, "code")[0], jdict(p, "data"), project_id=opt(p, "project_id"), source=opt(p, "source"),
                            basis_note=opt(p, "basis_note"), is_synthetic=str(p.get("is_synthetic", "")).lower() in ("1", "true", "on", "yes"),
                            submit=str(p.get("submit", "")).lower() in ("1", "true", "on", "yes"))


@action("submit_param")
def _(db, a, p):
    from ..services import governed
    governed.submit(db, a, int(req(p, "param_id")[0]))


@action("approve_param")
def _(db, a, p):
    from ..services import governed
    governed.approve(db, a, int(req(p, "param_id")[0]), comments=opt(p, "comments"))


@action("reject_param")
def _(db, a, p):
    from ..services import governed
    governed.reject(db, a, int(req(p, "param_id")[0]), comments=req(p, "comments")[0])


# ---------------------------------------------------------------- WBS / cross-walk
@action("add_wbs_node")
def _(db, a, p):
    from ..services import wbs
    return wbs.add_node(db, a, req(p, "project_id")[0], req(p, "code")[0], req(p, "name")[0], opt(p, "parent_code"), opt(p, "kind") or "area")


@action("delete_wbs_node")
def _(db, a, p):
    from ..services import wbs
    wbs.delete_node(db, a, req(p, "project_id")[0], req(p, "code")[0])


@action("assign_wbs")
def _(db, a, p):
    """`mapping`: {item_key: wbs_code} (JSON), or single `item_key` + `wbs_code`."""
    from ..services import wbs
    pid = req(p, "project_id")[0]
    mapping = jdict(p, "mapping", required=False) or {req(p, "item_key")[0]: req(p, "wbs_code")[0]}
    return wbs.assign_items(db, a, pid, mapping)


@action("add_crosswalk")
def _(db, a, p):
    from ..services import wbs
    return wbs.add_crosswalk(db, a, req(p, "project_id")[0], req(p, "system")[0], req(p, "client_code")[0], req(p, "cost_code")[0], opt(p, "client_name"))


# ---------------------------------------------------------------- analysis runs
@action("save_analysis")
def _(db, a, p):
    """Run a registered report and store its result as an immutable analysis run (not an approved record)."""
    from ..reporting.registry import run_report
    from ..services import analysis
    pid, name = req(p, "project_id", "report")
    params = jdict(p, "params", required=False) or {}
    res = run_report(db, name, pid, params)
    return analysis.save_run(db, a, pid, name, params, res, inputs_hash=analysis.digest(res), notes=opt(p, "notes"))


# ---------------------------------------------------------------- take-off derivation
@action("mto_apply")
def _(db, a, p):
    from ..services import mto
    skip = jdict(p, "skip_slots", required=False)
    if isinstance(skip, str):
        skip = [x.strip() for x in skip.split(",") if x.strip()]
    r = mto.apply(db, a, req(p, "project_id")[0], req(p, "item_key")[0], req(p, "template")[0], opt(p, "driver_qty"), opt(p, "driver_source"), skip)
    return {"application_id": r["application_id"], "lines": len(r["lines"]), "skipped": r["skipped"]}


# ---------------------------------------------------------------- client profiles / classification / BoE
@action("create_profile")
def _(db, a, p):
    from ..services import profiles
    return profiles.create_profile(db, a, req(p, "code")[0], req(p, "name")[0], client=opt(p, "client"), source_documents=jdict(p, "source_documents", False),
                                   requirements=jdict(p, "requirements", False), notes=opt(p, "notes"))


@action("submit_profile")
def _(db, a, p):
    from ..services import profiles
    profiles.submit_profile(db, a, int(req(p, "profile_id")[0]))


@action("approve_profile")
def _(db, a, p):
    from ..services import profiles
    profiles.approve_profile(db, a, int(req(p, "profile_id")[0]), opt(p, "comments"))


@action("link_profile")
def _(db, a, p):
    from ..services import profiles
    profiles.link_project(db, a, req(p, "project_id")[0], req(p, "code")[0], int(p["version"]) if opt(p, "version") else None)


@action("attest_requirement")
def _(db, a, p):
    from ..services import profiles
    return profiles.attest(db, a, *req(p, "project_id", "req_id", "status", "evidence"))


@action("generate_boe")
def _(db, a, p):
    from ..services import boe
    return boe.generate_boe(db, a, req(p, "project_id")[0])


# ---------------------------------------------------------------- landed cost / labour
@action("propose_landed_rate")
def _(db, a, p):
    from ..services import landed
    r = landed.propose_landed_rate(db, a, int(req(p, "base_rate_id")[0]), req(p, "terms_code")[0], project_id=opt(p, "project_id"),
                                   submit=str(p.get("submit", "")).lower() in ("1", "true", "on", "yes"))
    return {"rate_id": r["rate_id"], "landed": str(r["landed"]), "currency": r["currency"]}


@action("propose_labour_rate")
def _(db, a, p):
    from ..services import labour
    extra = {k: p[k] for k in ("allowances_monthly", "accommodation_monthly", "transport_monthly", "other_monthly", "overtime_multiplier") if opt(p, k) is not None}
    r = labour.propose_labour_rate(db, a, req(p, "resource_id")[0], monthly_base_wage=req(p, "monthly_base_wage")[0], group=req(p, "group")[0],
                                   normal_hours_per_month=req(p, "normal_hours_per_month")[0], contract_months=opt(p, "contract_months"),
                                   project_id=opt(p, "project_id"), evidence=req(p, "evidence")[0], price_date=opt(p, "price_date"), source_id=opt(p, "source_id"),
                                   submit=str(p.get("submit", "")).lower() in ("1", "true", "on", "yes"), **extra)
    return {"rate_id": r["rate_id"], "hourly_cost": str(r["hourly_cost"])}


# ---------------------------------------------------------------- risk / cash flow
@action("quantify_risk")
def _(db, a, p):
    from ..services import registers
    registers.quantify_risk(db, a, req(p, "risk_id")[0], prob_pct=req(p, "prob_pct")[0], cost_low=req(p, "cost_low")[0], cost_likely=req(p, "cost_likely")[0],
                            cost_high=req(p, "cost_high")[0], schedule_days=opt(p, "schedule_days"), category=opt(p, "category"), response=opt(p, "response"),
                            basis=req(p, "basis")[0])


@action("propose_financing_indirects")
def _(db, a, p):
    from ..services import cashflow
    r = cashflow.propose_financing_indirects(db, a, req(p, "project_id")[0], terms_code=opt(p, "terms_code"))
    return {"indirect_codes": r["indirect_codes"], "interest": str(r["interest"]), "bond": str(r["bond"])}


# ---------------------------------------------------------------- procurement controls
@action("record_bid_score")
def _(db, a, p):
    from ..services import bids
    return bids.record_score(db, a, *req(p, "package_id", "quotation_id", "criteria_code", "criterion_id", "score", "evidence"))


@action("add_long_lead")
def _(db, a, p):
    from ..services import bids
    return bids.add_long_lead(db, a, req(p, "project_id")[0], req(p, "description")[0], req(p, "lead_time_weeks")[0], req(p, "required_on_site")[0],
                              package_id=opt(p, "package_id"), supplier_id=opt(p, "supplier_id"), planned_order_date=opt(p, "planned_order_date"),
                              vendor_data_due=opt(p, "vendor_data_due"), notes=opt(p, "notes"))


@action("update_long_lead")
def _(db, a, p):
    from ..services import bids
    changes = {k: opt(p, k) for k in ("planned_order_date", "actual_order_date", "vendor_data_due", "vendor_data_received", "notes", "lead_time_weeks", "required_on_site") if k in p}
    bids.update_long_lead(db, a, req(p, "long_lead_id")[0], **changes)


@action("set_package_scope")
def _(db, a, p):
    from ..services import bids
    return bids.set_scope(db, a, req(p, "project_id")[0], req(p, "package_id")[0], req(p, "ref_type")[0], req(p, "ref")[0], req(p, "responsibility")[0],
                          opt(p, "counterpart_package"), opt(p, "note"))


# ---------------------------------------------------------------- post-award control
@action("create_variation")
def _(db, a, p):
    from ..services import controls
    return controls.create_variation(db, a, req(p, "project_id")[0], req(p, "title")[0], description=opt(p, "description") or "", instructed_by=opt(p, "instructed_by"),
                                     instruction_ref=opt(p, "instruction_ref"), time_days=opt(p, "time_days"))


@action("add_variation_line")
def _(db, a, p):
    from ..services import controls
    return controls.add_line(db, a, req(p, "variation_id")[0], req(p, "resource_id")[0], req(p, "quantity")[0], unit=opt(p, "unit"), direction=opt(p, "direction") or "add",
                             description=opt(p, "description"))


@action("submit_variation")
def _(db, a, p):
    from ..services import controls
    r = controls.submit_variation(db, a, req(p, "variation_id")[0])
    return {"amount": str(r["amount"])}


@action("decide_variation")
def _(db, a, p):
    from ..services import controls
    controls.decide_variation(db, a, req(p, "variation_id")[0], str(p.get("decision", "")).lower() in ("approve", "approved", "1", "true"), req(p, "comments")[0])


@action("record_progress")
def _(db, a, p):
    from ..services import controls
    return controls.record_progress(db, a, *req(p, "project_id", "task_code", "as_of", "pct", "basis"))


# ---------------------------------------------------------------- provisions (all produce Draft indirect items)
@action("propose_reserves")
def _(db, a, p):
    from ..services import provisions
    return [{k: str(v) for k, v in o.items()} for o in provisions.reserve_proposals(db, a, req(p, "project_id")[0])]


@action("propose_engineering_indirects")
def _(db, a, p):
    from ..services import provisions
    return [{k: str(v) for k, v in o.items()} for o in provisions.propose_engineering_indirects(db, a, req(p, "project_id")[0])]


@action("propose_overhead_indirects")
def _(db, a, p):
    from ..services import provisions
    return [{k: str(v) for k, v in o.items()} for o in provisions.propose_overhead_indirects(db, a, req(p, "project_id")[0])]
