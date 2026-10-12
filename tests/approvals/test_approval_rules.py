"""The human-approval system: nothing becomes verified, approved or exportable without explicit, authorised human action."""
import ast
import json
from pathlib import Path

import pytest

from app.approvals import engine as ap
from app.approvals.policy import POLICY
from app.core.errors import ApprovalBlocked, Conflict, ImmutableRecord, PermissionDenied, ValidationFailed
from app.estimators.estimate import compute_estimate
from app.models.enums import Entity
from app.reconciliation import engine as recon
from app.services import assemblies, assumptions, audit, estimates, projects, rates
from app.services.rates import create_resource

from tests.conftest import ADMIN, AI, COMMERCIAL, ESTIMATOR, PROCUREMENT, VIEWER
from tests.helpers import approve_vat, approved_assembly, approved_rate, std_policy


@pytest.fixture()
def res(seeded):
    create_resource(seeded, ESTIMATOR, resource_type="material", description="Test material", unit="m", id="T-1", cost_code="C.01", is_synthetic=True)
    return seeded


def propose(db, price="10", **kw):
    return rates.propose_rate(db, ESTIMATOR, "T-1", unit_price=price, rate_type="Synthetic Demonstration Rate", price_date="2026-09-01",
                              is_synthetic=True, evidence="SYNTHETIC", submit=True, **kw)


def test_unapproved_rate_never_becomes_verified(res):
    rid = propose(res)
    assert rates.get_rate(res, rid)["status"] == "Pending Review"
    with pytest.raises(PermissionDenied):
        rates.approve_rate(res, ESTIMATOR, rid)                       # estimators cannot approve rates (only provisionally)
    with pytest.raises(PermissionDenied):
        rates.approve_rate(res, VIEWER, rid)
    with pytest.raises(PermissionDenied):
        rates.approve_rate(res, AI, rid)
    assert rates.get_rate(res, rid)["status"] == "Pending Review"
    rates.approve_rate(res, PROCUREMENT, rid, comments="checked")
    r = rates.get_rate(res, rid)
    assert r["status"] == "Approved" and r["approved_by"] == "proc"
    log = ap.approval_history(res, "rate", rid)
    assert len(log) == 1 and log[0]["reviewer"] == "proc" and log[0]["reviewer_role"] == "Procurement Reviewer" and log[0]["action"] == "approve"


def test_missing_rate_and_index_cannot_be_approved(res):
    miss = rates.create_missing_placeholder(res, "T-1", unit="m")
    with pytest.raises(Conflict):
        rates.approve_rate(res, PROCUREMENT, miss)                    # not pending
    with pytest.raises(ValidationFailed):
        rates.submit_rate(res, ESTIMATOR, miss)                       # a missing placeholder cannot even be submitted
    idx = rates.propose_rate(res, ESTIMATOR, "T-1", unit_price="5", rate_type="Official Index or Benchmark", price_date="2026-01-01", source_id="SRC-001",
                             submit=True)
    with pytest.raises(ValidationFailed) as e:
        rates.approve_rate(res, PROCUREMENT, idx)
    assert e.value.code == "NON_PRICE_TYPE"                           # an index is never a supplier quotation / unit price
    with pytest.raises(ValidationFailed):
        rates.propose_rate(res, ESTIMATOR, "T-1", unit_price=None, rate_type="Verified Supplier Quote")       # no silent empty price
    with pytest.raises(ValidationFailed):
        rates.propose_rate(res, ESTIMATOR, "T-1", unit_price="-1", rate_type="Verified Supplier Quote")


def test_evidence_and_date_required_for_approval(res):
    r1 = rates.propose_rate(res, ESTIMATOR, "T-1", unit_price="5", rate_type="Verified Supplier Quote", submit=True)
    with pytest.raises(ValidationFailed) as e:
        rates.approve_rate(res, PROCUREMENT, r1)
    assert e.value.code == "PRICE_DATE_REQUIRED"
    r2 = rates.propose_rate(res, ESTIMATOR, "T-1", unit_price="5", rate_type="Verified Supplier Quote", price_date="2026-09-01", submit=True)
    with pytest.raises(ValidationFailed) as e:
        rates.approve_rate(res, PROCUREMENT, r2)
    assert e.value.code == "EVIDENCE_REQUIRED"


def test_ai_cannot_approve_anything(seeded):
    """Every (entity, action) in the policy refuses an AI principal, whatever role string it carries."""
    from app.models.actor import Actor
    sneaky = Actor("ai-x", "Administrator", "AI posing as admin", is_ai=True)
    for etype, acts in POLICY.items():
        for action in acts:
            for who in (AI, sneaky):
                with pytest.raises(PermissionDenied) as e:
                    ap.authorize(who, etype, action)
                assert e.value.code == "AI_CANNOT_APPROVE"
    with pytest.raises(PermissionDenied):
        ap.require_author(AI)


def test_ai_package_cannot_reach_approval_or_mutation_code():
    banned = ("approvals", "services.rates", "services.boq", "services.estimates", "services.assemblies", "services.assumptions", "services.commercial",
              "services.indirects", "services.registers", "services.offers", "services.suggestions", "procurement", "reconciliation")
    root = Path(__file__).resolve().parents[2] / "app" / "ai"
    for f in root.glob("*.py"):
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom):
                names = [(node.module or "") + "." + a.name for a in node.names] + [(("." * node.level) + (node.module or ""))]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            for n in names:
                assert not any(b in n.replace("..", "") for b in banned), f"{f.name} imports {n}"


def test_approved_data_cannot_be_silently_overwritten(res):
    rid = propose(res)
    rates.approve_rate(res, PROCUREMENT, rid)
    with pytest.raises(ImmutableRecord):
        rates.update_draft_rate(res, ESTIMATOR, rid, unit_price="999")
    with pytest.raises(ImmutableRecord):
        rates.reject_rate(res, PROCUREMENT, rid, "no")
    assert rates.get_rate(res, rid)["unit_price"] == "10"
    # a change = new version, original untouched, old one superseded on approval, history auditable
    new = rates.revise_rate(res, ESTIMATOR, rid, unit_price="12", price_date="2026-10-01")
    rates.submit_rate(res, ESTIMATOR, new)
    assert rates.get_rate(res, rid)["status"] == "Approved"
    rates.approve_rate(res, PROCUREMENT, new)
    assert rates.get_rate(res, rid)["status"] == "Superseded" and rates.get_rate(res, rid)["superseded_by"] == new
    assert rates.get_rate(res, rid)["unit_price"] == "10"                       # the old record is still intact
    assert [r["action"] for r in audit.history(res, "rate", rid)][-1] == "superseded"


def test_assumption_revisions_are_new_versions(seeded):
    assumptions.revise_assumption(seeded, ESTIMATOR, "ASMP-C-003", default_value="3")
    assumptions.submit_assumption(seeded, ESTIMATOR, "ASMP-C-003")
    assumptions.approve_assumption(seeded, COMMERCIAL, "ASMP-C-003")
    v = assumptions.revise_assumption(seeded, ESTIMATOR, "ASMP-C-003", default_value="4")
    assert v == 2 and assumptions.get_current_approved(seeded, "ASMP-C-003")["default_value"] == "3"   # v1 still the approved one
    assert assumptions.resolve(seeded, None, "ASMP-C-003").value == "3"
    assumptions.submit_assumption(seeded, ESTIMATOR, "ASMP-C-003")
    assumptions.approve_assumption(seeded, COMMERCIAL, "ASMP-C-003")
    assert assumptions.resolve(seeded, None, "ASMP-C-003").value == "4"
    assert seeded.scalar("SELECT status FROM assumptions WHERE id='ASMP-C-003' AND version=1") == "Superseded"


def test_project_override_does_not_change_global_and_needs_approval(seeded):
    pid = projects.create_project(seeded, ESTIMATOR, name="p")
    approve_g = lambda: None
    assumptions.set_override(seeded, ESTIMATOR, pid, "ASMP-C-003", "7", "site specific")
    assert assumptions.get_latest(seeded, "ASMP-C-003")["default_value"] is None              # global untouched
    ra = assumptions.resolve(seeded, pid, "ASMP-C-003")
    assert ra.value == "7" and ra.status == "Pending Review" and not ra.approved                # visible but NOT approved
    with pytest.raises(ValidationFailed):
        assumptions.set_override(seeded, ESTIMATOR, pid, "ASMP-C-003", "8", "")             # reason mandatory
    assumptions.approve_override(seeded, COMMERCIAL, pid, "ASMP-C-003")
    assert assumptions.resolve(seeded, pid, "ASMP-C-003").approved
    assert assumptions.get_latest(seeded, "ASMP-C-003")["default_value"] is None


def test_provisional_rate_requires_explicit_reason_role_and_project(res):
    rid = propose(res)
    pid = projects.create_project(res, ESTIMATOR, name="p")
    with pytest.raises(ValidationFailed) as e:
        rates.approve_rate_provisional(res, ESTIMATOR, rid, pid)               # no reason
    assert e.value.code == "REASON_REQUIRED"
    with pytest.raises(PermissionDenied):
        rates.approve_rate_provisional(res, VIEWER, rid, pid, comments="x")
    rates.approve_rate_provisional(res, ESTIMATOR, rid, pid, comments="allowance for this tender only")
    prov = [r for r in rates.rates_for(res, "T-1") if r["status"].startswith("Provisional")]
    assert len(prov) == 1 and prov[0]["project_id"] == pid
    assert rates.get_rate(res, rid)["status"] == "Pending Review"              # the global rate is NOT approved by this
    log = [a for a in ap.approval_history(res, "rate", prov[0]["id"])]
    assert log[0]["action"] == "approve_provisional" and log[0]["override_reason"]


def test_provisional_input_stays_visible_in_estimate(seeded, tmp_path):
    db = seeded
    create_resource(db, ESTIMATOR, resource_type="material", description="m", unit="m", id="T-2", cost_code="C.01", is_synthetic=True)
    approved_assembly(db, "T-ASM", "m", [dict(line_type="material", resource_id="T-2", factor="1")])
    pid = projects.create_project(db, ESTIMATOR, name="p", tax_category="VAT-STD", is_demo=True)
    from app.imports import boq as bi
    from app.services import boq
    from tests.helpers import write_boq
    bi.import_boq(db, ESTIMATOR, pid, write_boq(tmp_path / "b.csv", [("1", "x", "m", "10", "", "")]))
    boq.map_to_assembly(db, ESTIMATOR, pid, "1", "T-ASM")
    r = rates.propose_rate(db, ESTIMATOR, "T-2", unit_price="20", rate_type="Estimator-Entered Allowance", price_date="2026-09-01", evidence="allowance", submit=True)
    assert compute_estimate(db, pid).direct.direct_cost_total == 0                      # pending rate unused
    rates.approve_rate_provisional(db, ESTIMATOR, r, pid, comments="client-directed allowance")
    est = compute_estimate(db, pid)
    assert est.direct.direct_cost_total == 200 and est.flags["provisional"] and est.state != "Complete"
    assert any(f["rule_code"] == "PROVISIONAL_INPUTS" for f in recon.get_run(db, recon.run_reconciliation(db, ESTIMATOR, pid)["run_id"])["findings"])


def test_assembly_edits_create_pending_revisions(res):
    approved_assembly(res, "T-A", "m", [dict(line_type="material", resource_id="T-1", factor="1")])
    a1 = assemblies.get(res, "T-A")
    assert a1["status"] == "Approved"
    with pytest.raises(ImmutableRecord):
        assemblies.add_line(res, ESTIMATOR, a1["pk"], line_type="material", resource_id="T-1", factor="2")
    pk2 = assemblies.new_version(res, ESTIMATOR, "T-A", revision_note="adjust")
    assemblies.update_line(res, ESTIMATOR, pk2, 1, factor="2")
    assert assemblies.get(res, "T-A", 1)["status"] == "Approved"
    assert assemblies.lines(res, a1["pk"])[0]["factor"] == "1"                          # v1 lines unchanged
    assert assemblies.get_approved(res, "T-A")["version"] == 1                          # estimating still sees v1 until v2 approved
    assemblies.submit_assembly(res, ESTIMATOR, "T-A")
    assemblies.approve_assembly(res, COMMERCIAL, "T-A")
    assert assemblies.get_approved(res, "T-A")["version"] == 2 and assemblies.get(res, "T-A", 1)["status"] == "Superseded"


def test_ai_generated_assembly_cannot_be_approved_by_ai(res):
    with pytest.raises(PermissionDenied):
        assemblies.create_assembly(res, AI, code="AI-A", description="x", unit="m")
    assemblies.create_assembly(res, ESTIMATOR, code="H-A", description="x", unit="m", lines_=[dict(line_type="material", resource_id="T-1", factor="1")])
    assemblies.submit_assembly(res, ESTIMATOR, "H-A")
    with pytest.raises(PermissionDenied):
        assemblies.approve_assembly(res, AI, "H-A")
    with pytest.raises(PermissionDenied):
        assemblies.approve_assembly(res, VIEWER, "H-A")


def test_self_approval_can_be_disabled(res, settings):
    settings.allow_self_approval = False
    c = PROCUREMENT
    rid = rates.propose_rate(res, c, "T-1", unit_price="1", rate_type="Synthetic Demonstration Rate", price_date="2026-09-01", is_synthetic=True, evidence="e", submit=True)
    with pytest.raises(ApprovalBlocked) as e:
        rates.approve_rate(res, c, rid)
    assert e.value.code == "SELF_APPROVAL_BLOCKED"
    rates.approve_rate(res, COMMERCIAL, rid)                                            # a different reviewer can


def test_audit_chain_detects_tampering(res):
    propose(res)
    assert audit.verify_chain(res)["ok"]
    res.execute("UPDATE audit_log SET after_json='{\"tampered\":1}' WHERE id=(SELECT MAX(id) FROM audit_log)")
    r = audit.verify_chain(res)
    assert not r["ok"] and r["first_bad_id"]


def test_policy_role_matrix_has_no_ai_and_commercial_gates():
    for etype, acts in POLICY.items():
        for roles in acts.values():
            assert "AI Assistant" not in roles and "Viewer" not in roles
    assert POLICY[Entity.ESTIMATE.value]["approve"] == {"Commercial Approver", "Administrator"}
    assert POLICY[Entity.TENDER_EXPORT.value]["approve"] == {"Commercial Approver", "Administrator"}
    assert "Estimator" not in POLICY[Entity.RATE.value]["approve"] and "Estimator" in POLICY[Entity.RATE.value]["approve_provisional"]
