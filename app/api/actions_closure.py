"""Actions added by the end-to-end closure: assumptions register, productivity norms, workforce profiles, programme baselines, tender registers and packs.
Registered into the same registry as actions.py (REST, UI and `python -m app.cli action NAME JSON` all call these); every action calls a service that enforces roles and approvals."""
from __future__ import annotations

from pathlib import Path

from ..core.errors import ValidationFailed
from .actions import action, opt, req
from .actions_ext import jdict


def _b(p, k):
    return str(p.get(k, "")).lower() in ("1", "true", "on", "yes")


# ---------------------------------------------------------------- assumptions register
@action("create_assumption")
def _(db, a, p):
    from ..services import assumptions
    return assumptions.create_assumption(db, a, id=req(p, "id")[0], family=req(p, "family")[0], name=req(p, "name")[0], description=opt(p, "description") or "",
                                         value_type=opt(p, "value_type") or "number", default_value=opt(p, "default_value"), unit=opt(p, "unit"), source=opt(p, "source"),
                                         evidence=opt(p, "evidence"), confidence=opt(p, "confidence") or "Low", mandatory_for_projects=_b(p, "mandatory"),
                                         is_synthetic=_b(p, "is_synthetic"), category=opt(p, "category"), origin=opt(p, "origin") or "manual", reason=opt(p, "reason"),
                                         business_impact=opt(p, "business_impact"), uncertainty=opt(p, "uncertainty"), consequence_if_missing=opt(p, "consequence_if_missing"), affects=opt(p, "affects"))


# ---------------------------------------------------------------- productivity norms
@action("create_norm")
def _(db, a, p):
    from ..services import workforce
    return workforce.create_norm(db, a, id=req(p, "id")[0], trade=req(p, "trade")[0], activity=req(p, "activity")[0], output_unit=req(p, "output_unit")[0], basis=req(p, "basis")[0],
                                 value=req(p, "value")[0], crew=jdict(p, "crew"), cost_prefix=opt(p, "cost_prefix"), includes_productivity_factors=_b(p, "includes_productivity_factors"),
                                 applicability=jdict(p, "applicability", False), exclusions=opt(p, "exclusions"), source=opt(p, "source"), evidence=opt(p, "evidence"),
                                 confidence=opt(p, "confidence") or "Low", evidence_status=opt(p, "evidence_status") or "unverified", origin=opt(p, "origin") or "user",
                                 effective_from=opt(p, "effective_from"), review_by=opt(p, "review_by"), is_synthetic=_b(p, "is_synthetic"), notes=opt(p, "notes"))


for _n, _fn in (("propose_norm", "propose_norm"), ("submit_norm", "submit_norm")):
    def _mk(fn):
        def f(db, a, p):
            from ..services import workforce
            getattr(workforce, fn)(db, a, req(p, "id")[0])
        return f
    action(_n)(_mk(_fn))


@action("approve_norm")
def _(db, a, p):
    from ..services import workforce
    workforce.approve_norm(db, a, req(p, "id")[0], comments=opt(p, "comments"), evidence_verified=_b(p, "evidence_verified"))


@action("reject_norm")
def _(db, a, p):
    from ..services import workforce
    workforce.reject_norm(db, a, req(p, "id")[0], req(p, "reason")[0])


@action("revise_norm")
def _(db, a, p):
    from ..services import workforce
    ch = jdict(p, "changes")
    return workforce.revise_norm(db, a, req(p, "id")[0], **ch)


# ---------------------------------------------------------------- workforce profiles / activities / baselines
@action("create_profile")
def _(db, a, p):
    from ..services import workforce
    return workforce.create_profile(db, a, id=req(p, "id")[0], archetype=req(p, "archetype")[0], name=req(p, "name")[0], roles=jdict(p, "roles"), indirect=jdict(p, "indirect", False),
                                    shifts=int(opt(p, "shifts") or 1), night_shift_efficiency_pct=opt(p, "night_shift_efficiency_pct"), attendance_pct=req(p, "attendance_pct")[0],
                                    availability_pct=req(p, "availability_pct")[0], productive_hours_per_shift=req(p, "productive_hours_per_shift")[0],
                                    overtime_hours_per_day=opt(p, "overtime_hours_per_day") or "0", overtime_efficiency_pct=opt(p, "overtime_efficiency_pct") or "0",
                                    work_fronts=int(opt(p, "work_fronts")) if opt(p, "work_fronts") else None, mobilisation_wd=int(opt(p, "mobilisation_wd") or 0),
                                    subcontract_capacity=jdict(p, "subcontract_capacity", False), role_day_cost=jdict(p, "role_day_cost", False), source=opt(p, "source"),
                                    is_synthetic=_b(p, "is_synthetic"), notes=opt(p, "notes"))


@action("submit_profile")
def _(db, a, p):
    from ..services import workforce
    workforce.submit_profile(db, a, req(p, "id")[0])


@action("approve_profile")
def _(db, a, p):
    from ..services import workforce
    workforce.approve_profile(db, a, req(p, "id")[0], comments=opt(p, "comments"))


@action("set_activities")
def _(db, a, p):
    from ..services import workforce
    return workforce.set_activities(db, a, req(p, "project_id")[0], jdict(p, "activities"))


@action("save_baseline")
def _(db, a, p):
    from ..services import workforce
    return workforce.save_baseline(db, a, req(p, "project_id")[0], req(p, "profile_id")[0], allow_provisional=_b(p, "allow_provisional"), allow_unconfirmed_calendar=_b(p, "allow_unconfirmed_calendar"))


@action("approve_baseline")
def _(db, a, p):
    from ..services import workforce
    workforce.approve_baseline(db, a, req(p, "project_id")[0], int(req(p, "version_no")[0]), comments=opt(p, "comments"))


@action("baseline_to_schedule")
def _(db, a, p):
    from ..services import workforce
    return workforce.baseline_to_schedule_tasks(db, a, req(p, "project_id")[0], int(req(p, "version_no")[0]))


# ---------------------------------------------------------------- tender intake / registers
@action("create_enquiry")
def _(db, a, p):
    from ..services import tender
    return tender.create_enquiry(db, a, customer_name=req(p, "customer_name")[0], title=req(p, "title")[0], received_date=req(p, "received_date")[0], tender_deadline=opt(p, "tender_deadline"),
                                 submission_instructions=opt(p, "submission_instructions"), brief=opt(p, "brief"), scope_summary=opt(p, "scope_summary"),
                                 customer_is_synthetic=_b(p, "customer_is_synthetic"), project_id=opt(p, "project_id"))


@action("register_document")
def _(db, a, p):
    from ..services import tender
    return tender.register_document(db, a, req(p, "project_id")[0], doc_ref=req(p, "doc_ref")[0], doc_type=req(p, "doc_type")[0], title=req(p, "title")[0], revision=req(p, "revision")[0],
                                    source=opt(p, "source"), received_date=opt(p, "received_date"), applicability=opt(p, "applicability"), status=opt(p, "status") or "Current", is_synthetic=_b(p, "is_synthetic"))


@action("generate_queries")
def _(db, a, p):
    from ..services import tender
    return tender.generate_draft_queries(db, a, req(p, "project_id")[0], response_due=opt(p, "response_due"))


@action("add_query")
def _(db, a, p):
    from ..services import tender
    return tender.add_query(db, a, req(p, "project_id")[0], register=req(p, "register")[0], question=req(p, "question")[0], why=opt(p, "why") or "", discipline=opt(p, "discipline"),
                            responsible_party=opt(p, "responsible_party"), related=jdict(p, "related", False), impact=jdict(p, "impact", False), response_due=opt(p, "response_due"),
                            options=opt(p, "options"), recommendation=opt(p, "recommendation"))


@action("release_query")
def _(db, a, p):
    from ..services import tender
    tender.approve_to_issue(db, a, req(p, "query_id")[0], comments=opt(p, "comments"))


@action("mark_query_issued")
def _(db, a, p):
    from ..services import tender
    tender.mark_issued(db, a, req(p, "query_id")[0])


@action("record_query_response")
def _(db, a, p):
    from ..services import tender
    tender.record_response(db, a, req(p, "query_id")[0], response_text=req(p, "response_text")[0], response_by=req(p, "response_by")[0], response_date=req(p, "response_date")[0],
                           cost_impact=opt(p, "cost_impact"), time_impact_days=opt(p, "time_impact_days"), is_synthetic=_b(p, "is_synthetic"))


@action("set_query_impact")
def _(db, a, p):
    from ..services import tender
    tender.set_impact(db, a, req(p, "query_id")[0], cost_impact=opt(p, "cost_impact"), time_impact_days=opt(p, "time_impact_days"), basis=req(p, "basis")[0])


@action("close_query")
def _(db, a, p):
    from ..services import tender
    tender.close_query(db, a, req(p, "query_id")[0], req(p, "note")[0], withdraw=_b(p, "withdraw"))


@action("upsert_register_item")
def _(db, a, p):
    from ..services import tender
    return tender.upsert_item(db, a, req(p, "project_id")[0], req(p, "register")[0], req(p, "item_key")[0], jdict(p, "data"), source_ref=opt(p, "source_ref"), is_synthetic=_b(p, "is_synthetic"))


@action("submit_register_item")
def _(db, a, p):
    from ..services import tender
    tender.submit_item(db, a, *req(p, "project_id", "register", "item_key"))


@action("approve_register_item")
def _(db, a, p):
    from ..services import tender
    tender.approve_item(db, a, *req(p, "project_id", "register", "item_key"), comments=opt(p, "comments"))


@action("skeleton_registers")
def _(db, a, p):
    from ..services import tender
    return tender.skeleton_registers(db, a, req(p, "project_id")[0])


# ---------------------------------------------------------------- packs
def _out(p, pid):
    from ..services import projects
    return Path(opt(p, "out_dir")) if opt(p, "out_dir") else projects.output_dir(pid, "exports")


@action("generate_tender_pack")
def _(db, a, p):
    from ..tender import packs
    pid = req(p, "project_id")[0]
    r = packs.generate_pack(db, a, pid, out_root=_out(p, pid), issue_date=req(p, "issue_date")[0], version_id=int(opt(p, "version_id")) if opt(p, "version_id") else None)
    return {k: v for k, v in r.items() if k != "documents"} | {"documents": [{k: d[k] for k in ("code", "doc_id", "status", "applicability")} for d in r["documents"]]}


@action("generate_handover_pack")
def _(db, a, p):
    from ..tender import packs
    pid = req(p, "project_id")[0]
    r = packs.generate_handover_pack(db, a, pid, out_root=_out(p, pid), issue_date=req(p, "issue_date")[0])
    return {k: v for k, v in r.items() if k != "documents"} | {"documents": [{k: d[k] for k in ("code", "doc_id", "status")} for d in r["documents"]]}


@action("approve_document")
def _(db, a, p):
    from ..tender import packs
    return packs.approve_document(db, a, req(p, "project_id")[0], req(p, "doc_id")[0], comments=opt(p, "comments"))


@action("validate_pack")
def _(db, a, p):
    from ..tender import packs
    return packs.validate_pack(db, int(req(p, "pack_pk")[0]))


@action("add_action")
def _(db, a, p):
    from ..services import tender
    return tender.add_action(db, a, req(p, "project_id")[0], req(p, "description")[0], owner=opt(p, "owner"), due=opt(p, "due"), source_ref=opt(p, "source_ref"))


@action("close_action")
def _(db, a, p):
    from ..services import tender
    tender.close_action(db, a, req(p, "action_id")[0], req(p, "note")[0])
