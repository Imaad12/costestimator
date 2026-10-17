"""Approvals inbox: every record waiting for a human decision, with the approve / reject form that belongs to it.

Read-only assembly of what the services already hold. The forms post to `/ui/do/<action>` (the shared action registry), so authorisation, four-eyes and
audit stay in the services; this module only decides which buttons to *show* (mirroring `approvals.policy`) and never approves anything itself.
"""
from __future__ import annotations

import json
from typing import Callable

from ..approvals.policy import allowed_roles
from ..database import Database, rows_to_dicts
from ..models.actor import Actor

COMMENT = ("comments", "Comment (optional)", False)
REASON = ("reason", "Reason (required)", True)


def op(action: str, fields: dict, inputs: list[tuple] | None = None, label: str = "Approve") -> dict:
    return dict(action=action, fields={k: v for k, v in fields.items() if v is not None}, inputs=inputs if inputs is not None else [COMMENT], label=label)


def _item(title: str, detail: str, *, project_id: str | None = None, raised_by: str | None = None, entity: str, approve: dict | None = None, reject: dict | None = None,
          approve_policy: str = "approve", link: str | None = None, synthetic: bool = False, extra: dict | None = None) -> dict:
    return dict(title=title, detail=detail, project_id=project_id, raised_by=raised_by, entity=entity, approve=approve, reject=reject, approve_policy=approve_policy,
                link=link, synthetic=synthetic, extra=extra or {})


def _s(v) -> str:
    return "" if v is None else str(v)


def _rates(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM resource_rates WHERE status='Pending Review' ORDER BY id LIMIT 200")):
        title = f"{r['resource_id']} - {r['unit_price']} {r['currency']}/{_s(r['unit'])}"
        detail = f"{r['rate_type']} - v{r['version']}" + (f" - project {r['project_id']} (project-only)" if r["project_id"] else " - global library")
        a = op("approve_rate", {"rate_id": r["id"]})
        policy = "approve"
        if r["project_id"]:
            a = op("approve_rate", {"rate_id": r["id"]})
        yield _item(title, detail, project_id=r["project_id"], raised_by=r["created_by"], entity="rate", approve=a, reject=op("reject_rate", {"rate_id": r["id"]}, [REASON], "Reject"),
                    approve_policy=policy, link=f"/libraries/resource/{r['resource_id']}", synthetic=bool(r["is_synthetic"]),
                    extra=dict(provisional=op("approve_rate_provisional", {"rate_id": r["id"], "project_id": r["project_id"]}, [("comments", "Basis for provisional use (required)", True)],
                                              "Approve as provisional") if r["project_id"] else None))


def _assumptions(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM assumptions WHERE status='Pending Review' ORDER BY id")):
        yield _item(f"{r['id']} v{r['version']} - {r['name']}", f"Value {_s(r['default_value'])} {_s(r['unit'])} - family {_s(r['family'])}", raised_by=r["created_by"], entity="assumption",
                    approve=op("approve_assumption", {"id": r["id"]}), reject=op("reject_assumption", {"id": r["id"]}, [REASON], "Reject"), link="/assumptions", synthetic=bool(r["is_synthetic"]))


def _overrides(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM project_assumptions WHERE status='Pending Review' ORDER BY project_id")):
        f = {"project_id": r["project_id"], "id": r["assumption_id"]}
        yield _item(f"{r['project_id']} / {r['assumption_id']} override", f"Proposed value {_s(r['override_value'])} - {_s(r['reason'])}", project_id=r["project_id"], raised_by=r["created_by"],
                    entity="project_assumption", approve=op("approve_override", f), reject=op("reject_override", f, [REASON], "Reject"), link=f"/projects/{r['project_id']}/assumptions")


def _assemblies(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM assemblies WHERE status='Pending Review' ORDER BY code")):
        yield _item(f"{r['code']} v{r['version']} - {_s(r['description'])}", f"Unit {_s(r['unit'])}", raised_by=r["created_by"], entity="assembly",
                    approve=op("approve_assembly", {"code": r["code"]}), reject=op("reject_assembly", {"code": r["code"]}, [REASON], "Reject"), link="/assemblies", synthetic=bool(r["is_synthetic"]))


def _quotations(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM quotations WHERE status='Pending Review' ORDER BY id")):
        yield _item(f"{r['id']} - {_s(r['reference'])}", f"Supplier {_s(r['supplier_id'])} - {'AI-extracted - ' if r['extracted_by_ai'] else ''}{_s(r['currency'])}", project_id=r["project_id"], raised_by=r["entered_by"],
                    entity="quotation", approve=op("approve_quotation", {"quotation_id": r["id"]}), reject=op("reject_quotation", {"quotation_id": r["id"]}, [REASON], "Reject"),
                    link=f"/projects/{r['project_id']}/quotes" if r["project_id"] else None, synthetic=bool(r["is_synthetic"]))


def _selections(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM quote_selections WHERE status='Pending Review' ORDER BY id")):
        f = {"selection_id": r["id"]}
        yield _item(f"Selection {r['id']} - quotation {r['quotation_id']}", f"Package {_s(r['package_id'])} - SAR {_s(r['value_sar'])}" + (f" - not lowest: {r['not_lowest_reason']}" if r["not_lowest_reason"] else ""),
                    project_id=r["project_id"], raised_by=r["proposed_by"], entity="supplier_selection", approve=op("decide_selection", {**f, "decision": "approve"}),
                    reject=op("decide_selection", {**f, "decision": "reject"}, [("comments", "Reason (required)", True)], "Reject"))


def _changes(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM change_requests WHERE status='Pending Review' ORDER BY id")):
        f = {"change_id": r["id"]}
        yield _item(f"BOQ {r['entity_id']} - {r['field']}", f"{_s(r['old_value'])} -> {_s(r['new_value'])} - {_s(r['reason'])}", project_id=r["project_id"], raised_by=r["requested_by"],
                    entity="boq_quantity", approve=op("decide_change", {**f, "decision": "approve"}, [("comment", "Comment (optional)", False)]),
                    reject=op("decide_change", {**f, "decision": "reject"}, [("comment", "Reason (required)", True)], "Reject"), link=f"/projects/{r['project_id']}/boq")


def _indirects(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM indirect_items WHERE status='Pending Review' ORDER BY project_id, code")):
        yield _item(f"{r['code']} - {_s(r['description'])}", f"{_s(r['method'])} - amount {_s(r['amount'])} {_s(r['currency'])}", project_id=r["project_id"], raised_by=r["created_by"], entity="indirect",
                    approve=op("approve_indirect", {"project_id": r["project_id"], "code": r["code"]}), link=f"/projects/{r['project_id']}/commercial", synthetic=bool(r["is_synthetic"]))


def _durations(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM project_durations WHERE status='Pending Review'")):
        yield _item(f"Duration {_s(r['months'])} months", f"{_s(r['source_type'])} - {_s(r['basis_note'])}", project_id=r["project_id"], raised_by=r["proposed_by"], entity="project_duration",
                    approve=op("approve_duration", {"duration_id": r["id"]}))


def _policies(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM commercial_policies WHERE status='Pending Review'")):
        yield _item(f"{r['code']} v{r['version']} - {_s(r['name'])}", "Commercial policy", raised_by=r["created_by"], entity="commercial_policy", approve=op("approve_policy", {"policy_id": r["id"]}),
                    synthetic=bool(r["is_synthetic"]))


def _tax(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM tax_categories WHERE status='Pending Review'")):
        yield _item(f"{r['code']} - {_s(r['rate_pct'])}%", f"Valid from {_s(r['valid_from'])} - {_s(r['verification_note'])}", raised_by=r["created_by"], entity="tax_category",
                    approve=op("approve_tax_category", {"tax_id": r["id"]}, [("evidence", "Evidence (source of the rate) - required", True), COMMENT]), synthetic=bool(r["is_synthetic"]))


def _fx(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM fx_rates WHERE status='Pending Review'")):
        yield _item(f"{r['from_ccy']} -> {r['to_ccy']} = {r['rate']}", f"Date {_s(r['rate_date'])} - source {_s(r['source'])}", raised_by=r["created_by"], entity="fx_rate",
                    approve=op("approve_fx", {"fx_id": r["id"]}), synthetic=bool(r["is_synthetic"]))


def _adjustments(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM quote_adjustments WHERE status='Pending Review'")):
        yield _item(f"Adjustment {r['id']} - {_s(r['adj_type'])}", f"{_s(r['description'])} - {_s(r['amount'])}", raised_by=r["created_by"], entity="quotation",
                    approve=op("approve_adjustment", {"adjustment_id": r["id"]}))


def _scope(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM scope_register WHERE status='Draft' ORDER BY project_id, id")):
        yield _item(f"{r['id']} - {_s(r['kind'])}", _s(r["description"]), project_id=r["project_id"], raised_by=r["created_by"], entity="exclusion", approve=op("approve_scope_entry", {"id": r["id"]}))


def _pricing(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM boq_items WHERE pricing_status='Pending Review'")):
        f = {"project_id": r["project_id"], "item_key": r["item_key"]}
        c = ("comment", "Comment (required)", True)
        yield _item(f"{r['item_key']} - {_s(r['description'])[:70]}", f"{_s(r['pricing_method'])} - {_s(r['pricing_amount'])} {_s(r['pricing_currency'])} - {_s(r['pricing_note'])}", project_id=r["project_id"],
                    entity="pricing_decision", approve=op("decide_pricing", {**f, "decision": "approve"}, [c]), reject=op("decide_pricing", {**f, "decision": "reject"}, [c], "Reject"),
                    link=f"/projects/{r['project_id']}/mapping")


def _mappings(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM boq_items WHERE mapping_status IN ('Suggested','Pending Review') AND assembly_code IS NOT NULL ORDER BY project_id, item_key LIMIT 300")):
        yield _item(f"{r['item_key']} -> {r['assembly_code']}", f"{_s(r['description'])[:80]} - mapping is {r['mapping_status']}", project_id=r["project_id"], entity="boq_mapping",
                    approve=op("approve_mapping", {"project_id": r["project_id"], "item_key": r["item_key"]}, [("comment", "Comment (optional)", False)]), link=f"/projects/{r['project_id']}/mapping")


def _versions(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM estimate_versions WHERE status='Pending Review'")):
        yield _item(f"Estimate version {r['version_no']} - {_s(r['state'])}", f"Fingerprint {_s(r['inputs_hash'])[:12]}", project_id=r["project_id"], raised_by=r["created_by"], entity="estimate",
                    approve=op("approve_version", {"version_id": r["id"]}), link=f"/projects/{r['project_id']}/reconciliation")


def _candidates(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM rate_candidates WHERE status IN ('Pending Review','Needs Verification','Approved for Publication') ORDER BY id LIMIT 200")):
        title = f"{r['candidate_ref']} - {_s(r['description'])[:60]}"
        detail = f"{_s(r['original_price'])} {_s(r['original_currency'])}/{_s(r['original_unit'])} - {_s(r['source_name'])} - {r['status']}"
        link = f"/rates/updates/{r['candidate_ref']}"
        if r["status"] == "Approved for Publication":
            yield _item(title, detail + " - ready to publish as a Pending Review rate", raised_by=r["created_by"], entity="rate_candidate", approve=op("publish_rate_candidate", {"candidate": r["candidate_ref"]}, [], "Publish as rate"),
                        link=link)
        else:
            yield _item(title, detail, raised_by=r["created_by"], entity="rate_candidate", approve=op("review_rate_candidate", {"candidate": r["candidate_ref"], "decision": "approve"}, [("comment", "Comment (optional)", False)], "Approve for publication"),
                        reject=op("review_rate_candidate", {"candidate": r["candidate_ref"], "decision": "reject"}, [("comment", "Reason (required)", True)], "Reject"), link=link,
                        extra=dict(more=op("review_rate_candidate", {"candidate": r["candidate_ref"], "decision": "needs_verification"}, [("comment", "What must be verified (required)", True)], "Needs verification")))


def _suggestions(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM ai_suggestions WHERE status='Pending Review' ORDER BY id DESC LIMIT 100")):
        f = {"suggestion_id": r["id"]}
        c = ("comment", "Comment (required)", True)
        yield _item(f"Suggestion {r['id']} - {_s(r['kind'])}", f"{_s(r['subject_type'])} {_s(r['subject_id'])} - produced by {_s(r['produced_by'])} - confidence {_s(r['confidence'])}", project_id=r["project_id"],
                    raised_by=r["produced_by"], entity="ai_suggestion", approve=op("accept_suggestion", f, [c], "Accept"), reject=op("reject_suggestion", f, [c], "Reject"))


def _params(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM governed_params WHERE status='Pending Review' ORDER BY id")):
        try:
            data = json.dumps(json.loads(r["data_json"]), sort_keys=True)[:140]
        except ValueError:
            data = _s(r["data_json"])[:140]
        yield _item(f"{r['kind']} / {r['code']} v{r['version']}", f"{data} - source: {_s(r['source'])}", project_id=r["project_id"], raised_by=r["created_by"], entity=f"param:{r['kind']}",
                    approve=op("approve_param", {"param_id": r["id"]}), reject=op("reject_param", {"param_id": r["id"]}, [("comments", "Reason (required)", True)], "Reject"),
                    link=f"/projects/{r['project_id']}/inputs" if r["project_id"] else None, synthetic=bool(r["is_synthetic"]))


def _norms(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM productivity_norms WHERE status='Pending Review' ORDER BY id")):
        yield _item(f"{r['id']} v{r['version']} - {_s(r['trade'])} / {_s(r['activity'])}", f"{_s(r['value'])} per {_s(r['basis'])} ({_s(r['output_unit'])}) - source {_s(r['source'])}", raised_by=r["created_by"],
                    entity="productivity_norm", approve=op("approve_norm", {"id": r["id"]}), reject=op("reject_norm", {"id": r["id"]}, [REASON], "Reject"), synthetic=bool(r["is_synthetic"]))


def _profiles(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM workforce_profiles WHERE status='Pending Review' ORDER BY id")):
        yield _item(f"{r['id']} v{r['version']} - {_s(r['name'])}", f"Workforce profile ({_s(r['archetype'])}), {_s(r['min_workers'])}-{_s(r['max_workers'])} workers", raised_by=r["created_by"],
                    entity="workforce_profile", approve=op("approve_profile", {"id": r["id"]}), synthetic=bool(r["is_synthetic"]))


def _baselines(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM programme_baselines WHERE status='Pending Review' ORDER BY project_id, version_no")):
        yield _item(f"Programme baseline v{r['version_no']}", f"Profile {_s(r['profile_id'])} - start {_s(r['start_date'])}" + (" - PROVISIONAL" if r["provisional"] else ""), project_id=r["project_id"],
                    raised_by=r["created_by"], entity="programme_baseline", approve=op("approve_baseline", {"project_id": r["project_id"], "version_no": r["version_no"]}),
                    link=f"/projects/{r['project_id']}/workforce")


def _queries(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM tender_queries WHERE status='Draft' ORDER BY project_id, id")):
        yield _item(f"{r['id']} - {_s(r['discipline'])}", _s(r["question"])[:200], project_id=r["project_id"], raised_by=r["created_by"], entity="tender_query",
                    approve=op("release_query", {"query_id": r["id"]}, [COMMENT], "Approve to issue"), link=f"/projects/{r['project_id']}/queries")


def _register_items(db: Database):
    for r in rows_to_dicts(db.all("SELECT * FROM tender_register_items WHERE status='Pending Review' ORDER BY project_id, register, item_key")):
        yield _item(f"{r['register']} / {r['item_key']}", _s(r["review_note"]) or _s(r["data_json"])[:140], project_id=r["project_id"], raised_by=r["created_by"], entity="tender_register_item",
                    approve=op("approve_register_item", {"project_id": r["project_id"], "register": r["register"], "item_key": r["item_key"]}), link=f"/projects/{r['project_id']}/tender-registers")


GROUPS: list[tuple[str, str, Callable]] = [
    ("Rates", "rates", _rates), ("Public-source rate candidates", "candidates", _candidates), ("Assumptions", "assumptions", _assumptions), ("Project assumption overrides", "overrides", _overrides),
    ("Assemblies", "assemblies", _assemblies), ("Quotations", "quotations", _quotations), ("Quotation adjustments", "adjustments", _adjustments), ("Supplier selections", "selections", _selections),
    ("BOQ change requests", "changes", _changes), ("BOQ mappings", "mappings", _mappings), ("Allowances and sums", "pricing", _pricing), ("Indirect items", "indirects", _indirects),
    ("Durations", "durations", _durations), ("Commercial policies", "policies", _policies), ("Tax categories", "tax", _tax), ("FX rates", "fx", _fx), ("Scope entries", "scope", _scope),
    ("Governed parameters", "params", _params), ("Productivity norms", "norms", _norms), ("Workforce profiles", "profiles", _profiles), ("Programme baselines", "baselines", _baselines),
    ("Tender queries (release for issue)", "queries", _queries), ("Tender register items", "register", _register_items), ("Estimate versions", "versions", _versions),
    ("AI and heuristic suggestions", "suggestions", _suggestions),
]


def _can(actor: Actor, entity: str, policy_action: str) -> bool:
    return actor.role in allowed_roles(entity, policy_action)


def build(db: Database, actor: Actor, only: str = "") -> list[dict]:
    """Groups of pending items; each item carries `can_approve` / `can_reject` for this user and `own` when this user raised it (four-eyes: the server refuses these)."""
    out = []
    for name, key, fn in GROUPS:
        if only and key != only:
            continue
        items = []
        for it in fn(db):
            it["can_approve"] = bool(it["approve"]) and (_can(actor, it["entity"], it["approve_policy"]) or bool(it["extra"].get("provisional") and _can(actor, it["entity"], "approve_provisional")))
            it["can_reject"] = bool(it["reject"]) and _can(actor, it["entity"], "reject")
            it["own"] = bool(it["raised_by"]) and it["raised_by"] == actor.username
            it["roles"] = sorted(allowed_roles(it["entity"], it["approve_policy"]) | (allowed_roles(it["entity"], "approve_provisional") if it["extra"].get("provisional") else set()))
            items.append(it)
        if items or only:
            out.append(dict(name=name, key=key, items=items))
    return out


def counts(db: Database) -> dict[str, int]:
    return {key: sum(1 for _ in fn(db)) for _, key, fn in GROUPS}
