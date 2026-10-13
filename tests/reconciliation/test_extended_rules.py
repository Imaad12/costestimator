"""Reconciliation rules for the extended controls: they appear as findings with the configured severities; a package double count can never be waived."""
from __future__ import annotations

import pytest

from app.core.errors import PermissionDenied
from app.reconciliation import engine as recon
from app.services import bids, governed, profiles, registers
from tests.conftest import COMMERCIAL, ESTIMATOR
from tests.helpers import build_mini


def _ok(db, kind, code, data, pid=None):
    i = governed.propose(db, ESTIMATOR, kind, code, data, project_id=pid, source="Company records (test)", submit=True)
    governed.approve(db, COMMERCIAL, i)


def _findings(db, pid):
    run = recon.run_reconciliation(db, ESTIMATOR, pid)
    return recon.get_run(db, run["run_id"])["findings"]


def test_extended_findings_raised_with_configured_severity(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    base = {f["rule_code"] for f in _findings(seeded, pid)}
    assert not base & {"BENCHMARK_OUTSIDE_RANGE", "MTO_STALE", "PACKAGE_DOUBLE_COUNT", "INTERFACE_OPEN", "LONG_LEAD_AT_RISK", "RISK_UNQUANTIFIED", "PROFILE_MANDATORY_UNMET", "PARAMETER_UNAPPROVED"}
    _ok(seeded, "benchmark_range", "UC", dict(name="Concrete low (test)", metric="item_unit_cost", cost_prefix="C", unit="m3", low="10", high="100", currency="SAR", source_note="old job"), pid)
    registers.add_risk(seeded, ESTIMATOR, pid, "Unquantified risk")
    bids.add_long_lead(seeded, ESTIMATOR, pid, "Transformer", 1000, "2026-12-01")                                    # latest order date long past
    i = governed.propose(seeded, ESTIMATOR, "productivity_factor", "PENDING", {"category": "height", "factor": "1.2"}, source="s", submit=True)
    pr = profiles.create_profile(seeded, ESTIMATOR, "PRF", "Test profile", requirements=[dict(req_id="R1", category="form", title="Form 1", source_ref="DOC-1 cl 1")])
    profiles.submit_profile(seeded, ESTIMATOR, pr); profiles.approve_profile(seeded, COMMERCIAL, pr); profiles.link_project(seeded, ESTIMATOR, pid, "PRF")
    fs = {f["rule_code"]: f for f in _findings(seeded, pid)}
    assert fs["BENCHMARK_OUTSIDE_RANGE"]["severity"] == "Medium" and fs["RISK_UNQUANTIFIED"]["severity"] == "Low" and fs["PARAMETER_UNAPPROVED"]["severity"] == "Low"
    assert fs["LONG_LEAD_AT_RISK"]["severity"] == "High" and fs["PROFILE_MANDATORY_UNMET"]["severity"] == "High" and "R1" in fs["PROFILE_MANDATORY_UNMET"]["detail"]
    assert "Pending Review" in fs["PARAMETER_UNAPPROVED"]["detail"]


def test_package_double_count_is_critical_and_cannot_be_waived(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    for p in ("PKG-A", "PKG-B"):
        seeded.insert("procurement_packages", dict(id=p, project_id=pid, name=p, status="Open", created_by="t", created_at="2026-01-01"))
    bids.set_scope(seeded, ESTIMATOR, pid, "PKG-A", "boq_item", "1.1", "included")
    bids.set_scope(seeded, ESTIMATOR, pid, "PKG-B", "boq_item", "1.1", "included")
    f = next(x for x in _findings(seeded, pid) if x["rule_code"] == "PACKAGE_DOUBLE_COUNT")
    assert f["severity"] == "Critical"
    with pytest.raises(PermissionDenied) as e:
        recon.accept_exception(seeded, ESTIMATOR, f["id"], "We checked and it is fine")
    assert e.value.code == "EXCEPTION_NOT_ALLOWED"
    gate = recon.final_gate(seeded, ESTIMATOR, pid)
    assert gate["blocked"] and any(b["rule_code"] == "PACKAGE_DOUBLE_COUNT" for b in gate["blockers"])
