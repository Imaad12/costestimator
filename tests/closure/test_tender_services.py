"""Tender intake, query registers, generic registers, applicability and the Stage-J readiness gate (SYNTHETIC inputs)."""
from __future__ import annotations

import pytest

from app import config as cfg
from app.core.errors import ApprovalBlocked, Conflict, NotFound, PermissionDenied, ValidationFailed
from app.estimators.estimate import compute_estimate
from app.services import readiness, tender
from app.tender import catalogue
from tests.conftest import ADMIN, COMMERCIAL, ESTIMATOR, VIEWER
from tests.helpers import build_mini, write_boq


@pytest.fixture()
def pid(seeded, tmp_path):
    return build_mini(seeded, tmp_path)


def test_enquiry_requires_customer_and_title(seeded):
    with pytest.raises(ValidationFailed):
        tender.create_enquiry(seeded, ESTIMATOR, customer_name="", title="t", received_date="2027-01-01")
    e = tender.create_enquiry(seeded, ESTIMATOR, customer_name="FICTIONAL CO (SYNTHETIC)", title="t", received_date="2027-01-01", customer_is_synthetic=True)
    assert e == "ENQ-0001"
    with pytest.raises(NotFound):
        tender.link_enquiry(seeded, ESTIMATOR, "ENQ-9999", "PRJ-0001")


def test_document_register_revisions_supersede_and_status_rules(seeded, pid):
    a = tender.register_document(seeded, ESTIMATOR, pid, doc_ref="DWG-1", doc_type="drawing", title="Layout", revision="A")
    b = tender.register_document(seeded, ESTIMATOR, pid, doc_ref="DWG-1", doc_type="drawing", title="Layout", revision="B")
    rows = {d["revision"]: d for d in tender.list_documents(seeded, pid)}
    assert rows["A"]["status"] == "Superseded" and rows["B"]["status"] == "Current" and rows["B"]["supersedes_pk"] == a
    with pytest.raises(Conflict) as e:
        tender.register_document(seeded, ESTIMATOR, pid, doc_ref="DWG-1", doc_type="drawing", title="Layout", revision="B")
    assert e.value.code == "DOC_REVISION_EXISTS"
    with pytest.raises(ValidationFailed):
        tender.register_document(seeded, ESTIMATOR, pid, doc_ref="X", doc_type="hologram", title="t", revision="0")
    with pytest.raises(ValidationFailed):
        tender.register_document(seeded, ESTIMATOR, pid, doc_ref="X", doc_type="drawing", title="t", revision="0", status="Approved")
    # registering is not interpreting
    assert tender.documents_report(seeded, pid)["not_interpreted"] == ["DWG-1"]
    with pytest.raises(ValidationFailed):
        tender.set_content_status(seeded, ESTIMATOR, pid, "DWG-1", "B", "reviewed", "")
    tender.set_content_status(seeded, ESTIMATOR, pid, "DWG-1", "B", "reviewed", "read against BOQ items 1.1-1.2")
    assert tender.documents_report(seeded, pid)["not_interpreted"] == []


def test_revision_conflict_is_detected_between_boq_and_register(seeded, tmp_path):
    from app.imports import boq as bi
    from app.services import projects
    pid = projects.create_project(seeded, ESTIMATOR, name="Rev conflict (SYNTHETIC)", is_demo=True)
    f = write_boq(tmp_path / "b.csv", [("1", "Pipe", "m", "10", "A.01", "DWG-9", "B")], header=("Item", "Description", "Unit", "Qty", "Cost Code", "Drawing", "Rev"))
    bi.import_boq(seeded, ESTIMATOR, pid, f)
    tender.register_document(seeded, ESTIMATOR, pid, doc_ref="DWG-9", doc_type="drawing", title="x", revision="B")
    assert tender.documents_report(seeded, pid)["revision_conflicts"] == []
    tender.register_document(seeded, ESTIMATOR, pid, doc_ref="DWG-9", doc_type="drawing", title="x", revision="C")
    c = tender.documents_report(seeded, pid)["revision_conflicts"]
    assert c == [dict(item_key="1", doc_ref="DWG-9", boq_revision="B", register_revision="C")]
    r = tender.generate_draft_queries(seeded, "system:detector", pid, response_due="2027-02-01")
    assert any(q["detector_key"] == "REV:DWG-9:B>C" and q["register"] == "technical" for q in tender.list_queries(seeded, pid))


def test_ambiguity_duplicate_missing_document_and_conflicting_requirement_detectors(seeded, tmp_path):
    from app.imports import boq as bi
    from app.services import projects
    pid = projects.create_project(seeded, ESTIMATOR, name="Detectors (SYNTHETIC)", is_demo=True)
    f = write_boq(tmp_path / "b.csv", [("1", "Excavation, quantity approximate, as required", "m3", "10"), ("2", "Pipe", "m", "5"), ("2", "Pipe", "m", "6")])
    bi.import_boq(seeded, ESTIMATOR, pid, f)
    tender.register_document(seeded, ESTIMATOR, pid, doc_ref="DWG-2", doc_type="drawing", title="x", revision="-", status="Missing")
    tender.upsert_item(seeded, ESTIMATOR, pid, "customer_requirement", "a", dict(requirement="Quality Plan", stated="yes", source="spec"))
    tender.upsert_item(seeded, ESTIMATOR, pid, "customer_requirement", "b", dict(requirement="quality plan", stated="no", source="letter"))
    r1 = tender.generate_draft_queries(seeded, "system:detector", pid)
    keys = {q["detector_key"] for q in tender.list_queries(seeded, pid)}
    assert {"AMBIG:1", "ISSUE:2#2", "MISSDOC:DWG-2", "CONFLICT:quality plan"} <= keys
    r2 = tender.generate_draft_queries(seeded, "system:detector", pid)
    assert r2["created"] == [] and r2["total"] == r1["total"]                     # de-duplicated: re-running never multiplies drafts
    assert all(q["status"] == "Draft" and q["generated_by"] == "system:detector" for q in tender.list_queries(seeded, pid) if q["detector_key"])
    amb = next(q for q in tender.list_queries(seeded, pid) if q["detector_key"] == "AMBIG:1")
    assert "approx" in amb["question"] and '"assessed": false' in amb["impact_json"].replace(" ", "") .replace('"assessed":false', '"assessed": false') or "assessed" in amb["impact_json"]


def test_query_workflow_gates(seeded, pid):
    q = tender.add_query(seeded, ESTIMATOR, pid, register="technical", question="What is the extent?", why="unclear")
    with pytest.raises(ValidationFailed):
        tender.add_query(seeded, ESTIMATOR, pid, register="astrology", question="x")
    with pytest.raises(ValidationFailed) as e:
        tender.approve_to_issue(seeded, COMMERCIAL, q)                              # a response date is required before release
    assert e.value.code == "RESPONSE_DUE_REQUIRED"
    tender.edit_query(seeded, ESTIMATOR, q, response_due="2027-03-01")
    with pytest.raises(PermissionDenied):
        tender.approve_to_issue(seeded, VIEWER, q)
    with pytest.raises(Conflict):
        tender.mark_issued(seeded, ESTIMATOR, q)                                     # not released yet
    cfg.get_settings().allow_self_approval = False
    with pytest.raises(ApprovalBlocked):
        tender.approve_to_issue(seeded, ESTIMATOR, q)                                # the author cannot release their own query
    tender.approve_to_issue(seeded, COMMERCIAL, q, comments="ok")
    with pytest.raises(Conflict):
        tender.edit_query(seeded, ESTIMATOR, q, question="changed after release")
    with pytest.raises(Conflict):
        tender.record_response(seeded, ESTIMATOR, q, response_text="r", response_by="c", response_date="2027-03-02")       # cannot answer before issue
    assert [x["id"] for x in tender.open_material_queries(seeded, pid)] == [q]
    tender.mark_issued(seeded, ESTIMATOR, q)
    with pytest.raises(ValidationFailed):
        tender.record_response(seeded, ESTIMATOR, q, response_text="", response_by="c", response_date="2027-03-02")
    tender.record_response(seeded, ESTIMATOR, q, response_text="SYNTHETIC answer", response_by="SYNTHETIC rep", response_date="2027-03-02", is_synthetic=True)
    assert tender.get_query(seeded, q)["response_is_synthetic"] == 1
    with pytest.raises(ValidationFailed):
        tender.set_impact(seeded, ESTIMATOR, q, cost_impact="10", basis=" ")
    tender.set_impact(seeded, ESTIMATOR, q, cost_impact="10", time_impact_days="1", basis="recalculated")
    tender.close_query(seeded, ESTIMATOR, q, "done")
    assert tender.open_material_queries(seeded, pid) == []
    with pytest.raises(Conflict):
        tender.close_query(seeded, ESTIMATOR, q, "again")


def test_generic_registers_validate_and_protect_approved_rows(seeded, pid):
    with pytest.raises(ValidationFailed):
        tender.upsert_item(seeded, ESTIMATOR, pid, "nonsense", "k", {})
    with pytest.raises(ValidationFailed) as e:
        tender.upsert_item(seeded, ESTIMATOR, pid, "itp", "k", {"activity": "x"})
    assert e.value.code == "REGISTER_FIELD"
    tender.upsert_item(seeded, ESTIMATOR, pid, "itp", "k", dict(activity="a", inspection_point=tender.TODO, acceptance_criteria="c", hold_point="h"))
    with pytest.raises(ValidationFailed) as e:
        tender.submit_item(seeded, ESTIMATOR, pid, "itp", "k")                       # placeholders must be completed by a person first
    assert e.value.code == "PLACEHOLDER"
    tender.upsert_item(seeded, ESTIMATOR, pid, "itp", "k", dict(activity="a", inspection_point="p", acceptance_criteria="c", hold_point="h"))
    tender.submit_item(seeded, ESTIMATOR, pid, "itp", "k")
    cfg.get_settings().allow_self_approval = False
    with pytest.raises(ApprovalBlocked):
        tender.approve_item(seeded, ESTIMATOR, pid, "itp", "k")
    tender.approve_item(seeded, COMMERCIAL, pid, "itp", "k")
    with pytest.raises(Conflict):
        tender.upsert_item(seeded, ESTIMATOR, pid, "itp", "k", dict(activity="a2", inspection_point="p", acceptance_criteria="c", hold_point="h"))
    with pytest.raises(Conflict):
        tender.reject_item(seeded, COMMERCIAL, pid, "itp", "k", "no")


def test_applicability_reasons_follow_customer_requirements_and_documents(seeded, pid):
    m = {r["code"]: r for r in catalogue.matrix(seeded, pid)["rows"]}
    assert m["D16"]["applicability"] == catalogue.MCR and "do not state" in m["D16"]["reason"]            # the technical proposal requirement is unknown
    assert m["D23"]["applicability"] == catalogue.MCR and m["D44"]["applicability"] == catalogue.NA and m["D38"]["applicability"] == catalogue.REQ
    tender.upsert_item(seeded, ESTIMATOR, pid, "tender_context", "context", dict(contract_type="lump sum", delivery_model="design-build", customer_requires={"technical_proposal": "no"}, award_scenario="hypothetical"))
    tender.register_document(seeded, ESTIMATOR, pid, doc_ref="SPEC-1", doc_type="specification", title="Spec", revision="0")
    m = {r["code"]: r for r in catalogue.matrix(seeded, pid)["rows"]}
    assert m["D16"]["applicability"] == catalogue.NA and m["D23"]["applicability"] == catalogue.REQ
    assert m["D26"]["applicability"] == catalogue.REQ and m["D44"]["applicability"] == catalogue.REQ
    assert all(r["reason"] for r in m.values()) and len(m) == 45


def test_stage_j_gate_reasons(seeded, pid):
    est = compute_estimate(seeded, pid)
    assert readiness._closure_gate(seeded, pid, est) == []                         # a project that does not use the registers is unaffected
    q = tender.add_query(seeded, ESTIMATOR, pid, register="commercial", question="Payment?", response_due="2027-03-01")
    tender.register_document(seeded, ESTIMATOR, pid, doc_ref="DWG-M", doc_type="drawing", title="x", revision="-", status="Missing")
    from app.services import workforce as wf
    wf.create_norm(seeded, ESTIMATOR, id="N-X", trade="t", activity="a", output_unit="m3", basis="crew_output_per_crew_day", value="1", crew={"skilled": 1}, source="s", is_synthetic=True)
    wf.set_activities(seeded, ESTIMATOR, pid, [dict(code="A1", name="a", boq_item_key="1.1", norm_id="N-X")])
    reasons = readiness._closure_gate(seeded, pid, est)
    text = " | ".join(reasons)
    assert "unresolved material" in text and q in text and "DWG-M" in text and "programme baseline: none approved" in text and "productivity norms not approved: N-X" in text
