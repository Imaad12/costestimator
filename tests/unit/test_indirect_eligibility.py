"""Explicit eligibility base for percentage indirects and commercial adders: included, excluded, partially eligible and unclassified cost; overlap with preliminaries
priced as BOQ items; legacy (unspecified) behaviour unchanged; approved policies and frozen estimates never rewritten. SYNTHETIC; expected values hand-worked below."""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.core.errors import ValidationFailed
from app.estimators import eligibility as elig
from app.estimators.estimate import compute_estimate
from app.reconciliation import engine as recon
from app.services import commercial, estimates, indirect_base, indirects, snapshots
from tests.conftest import COMMERCIAL, ESTIMATOR
from tests.unit.test_time_allocation import proj  # noqa: F401  (fixture: SUP 1,000 A.03 ; CRN 2,000 + FRK 1,000 A.07 ; SCF 500 A.06 ; PIP 1,000 E.06 = 5,500)

LINES = [dict(item_key="SUP", cost_code="A.03", kind="subcontract", amount="1000"), dict(item_key="CRN", cost_code="A.07", kind="plant", amount="2000"),
         dict(item_key="PIP", cost_code="E.06", kind="material", amount="1000"), dict(item_key="X", cost_code=None, kind="labour", amount="500")]


def test_pure_eligibility_included_excluded_partial_unclassified():
    assert elig.eligible_base(LINES, None)["eligible"] == D(4500) and not elig.eligible_base(LINES, None)["specified"]                 # legacy: everything, flagged unspecified
    s = elig.validate_spec({"default": "include", "rules": [{"cost_prefix": "A", "eligible_pct": 0}]})
    b = elig.eligible_base(LINES, s)
    assert (b["eligible"], b["excluded"], b["unclassified"]) == (D(1500), D(3000), D(1500))                                         # PIP + X take the default (unclassified)
    s = elig.validate_spec({"default": "exclude", "rules": [{"cost_prefix": "A.07", "eligible_pct": 50}, {"kind": "material", "eligible_pct": 100}, {"item_key": "SUP", "eligible_pct": "25"}]})
    b = elig.eligible_base(LINES, s)
    assert b["eligible"] == D(1000) + D(1000) + D(250) and b["unclassified"] == D(500) and b["by_cost_code"]["A.07"] == dict(total=D(2000), eligible=D(1000))   # first matching rule wins; partial share
    assert b["by_kind"]["plant"]["eligible"] == D(1000) and {r["item_key"]: r["decided_by"] for r in b["rows"]}["X"].startswith("default exclude (unclassified)")
    for bad in ({"default": "maybe"}, {"default": "include", "rules": [{"eligible_pct": 50}]}, {"default": "include", "rules": [{"cost_prefix": "A", "eligible_pct": 120}]},
                {"default": "include", "rules": [{"cost_prefix": "A", "eligible_pct": -1}]}, {"default": "include", "rules": [{"cost_prefix": "A", "eligible_pct": 10, "bogus": 1}]}):
        with pytest.raises(ValidationFailed):
            elig.validate_spec(bad)


def site(db, pid, spec=None, pct="8"):
    indirects.add_indirect(db, ESTIMATOR, pid, code="IND-SITE", category="Site", description="SYNTHETIC site indirects", method="percent_of_direct", amount=pct, eligibility=spec, source="SYNTHETIC")
    indirects.submit_indirect(db, ESTIMATOR, pid, "IND-SITE")
    indirects.approve_indirect(db, COMMERCIAL, pid, "IND-SITE")


def test_indirect_uses_the_eligible_base_and_exposes_the_breakdown(proj):
    db, pid = proj
    site(db, pid)                                                                                       # unspecified: legacy whole direct cost, 8 % x 5,500 = 440
    est = compute_estimate(db, pid)
    assert est.indirect.total == D("440.00")
    rep = indirect_base.indirect_base_report(db, pid, est=est)
    assert rep["unspecified"] == ["IND-SITE"] and rep["indirects"][0]["specified"] is False and rep["indirects"][0]["eligible_base"] == D(5500)
    codes = {f["rule_code"] for f in recon.get_run(db, recon.run_reconciliation(db, ESTIMATOR, pid)["run_id"])["findings"]}
    assert {"INDIRECT_ELIGIBILITY_UNSPECIFIED", "INDIRECT_BASE_OVERLAP"} <= codes                         # preliminaries (A.*) priced as BOQ items sit inside the % base
    ov = rep["overlaps"][0]
    assert {r["item_key"] for r in ov["preliminaries_in_base"]} == {"SUP", "CRN", "FRK", "SCF"} and ov["overlap_exposure"] == D("360.00")      # 8 % x 4,500


def test_revision_with_exclusion_clears_overlap_without_rewriting_the_approved_version_or_a_frozen_estimate(proj):
    db, pid = proj
    site(db, pid)
    vid = estimates.freeze_version(db, ESTIMATOR, pid, "v1")
    frozen = estimates.get_version(db, vid)
    # a revision is a NEW Draft version: the approved legacy indirect stays in force until the revision is approved
    indirects.revise_indirect(db, ESTIMATOR, pid, "IND-SITE", eligibility={"default": "include", "rules": [{"cost_prefix": "A", "eligible_pct": 0}]})
    assert compute_estimate(db, pid).indirect.total == D("440.00")
    indirects.submit_indirect(db, ESTIMATOR, pid, "IND-SITE")
    indirects.approve_indirect(db, COMMERCIAL, pid, "IND-SITE")
    est = compute_estimate(db, pid)
    assert est.indirect.total == D("80.00")                                                              # 8 % x PIP 1,000 (A.* excluded, E.06 takes the default include = unclassified)
    rep = indirect_base.indirect_base_report(db, pid, est=est)
    assert rep["unspecified"] == [] and rep["overlaps"] == [] and rep["indirects"][0]["excluded"] == D(4500) and rep["indirects"][0]["unclassified"] == D(1000)
    assert est.fingerprint != frozen["inputs_hash"]
    rp = snapshots.replay_estimate(db, vid)
    assert rp["ok"] and rp["fingerprint"] == frozen["inputs_hash"] and estimates.get_version(db, vid)["inputs_hash"] == frozen["inputs_hash"]     # frozen v1 replays unchanged
    codes = {f["rule_code"] for f in recon.get_run(db, recon.run_reconciliation(db, ESTIMATOR, pid)["run_id"])["findings"]}
    assert "INDIRECT_BASE_OVERLAP" not in codes and "INDIRECT_ELIGIBILITY_UNSPECIFIED" not in codes


def test_partial_eligibility_and_validation_on_the_service(proj):
    db, pid = proj
    site(db, pid, {"default": "exclude", "rules": [{"cost_prefix": "A.07", "eligible_pct": 50}, {"cost_prefix": "E", "eligible_pct": 100}]})
    est = compute_estimate(db, pid)
    assert est.indirect.total == D("200.00")                                                              # 8 % x (1,000 + 50 % x 3,000) = 8 % x 2,500
    assert "eligible direct cost 2500" in est.indirect.lines[0].basis
    with pytest.raises(ValidationFailed):
        indirects.add_indirect(db, ESTIMATOR, pid, code="IND-X", category="x", description="x", method="fixed", amount="10", eligibility={"default": "include"})   # only for percent_of_direct
    with pytest.raises(ValidationFailed):
        indirects.add_indirect(db, ESTIMATOR, pid, code="IND-Y", category="x", description="x", method="percent_of_direct", amount="1", eligibility={"default": "include", "rules": [{"kind": "plant", "eligible_pct": 101}]})


def test_commercial_adder_eligibility(proj):
    db, pid = proj
    # contingency 5 % of the DIRECT base, restricted to non-preliminaries: 5 % x 1,000 = 50 (instead of 5 % x 5,500 = 275)
    from tests.helpers import std_policy
    base = compute_estimate(db, pid).commercial
    assert base.contingency == D("275.00")                                                               # fixture policy: 5 % x (D + I) = 5 % x 5,500
    pid2 = commercial.create_policy(db, ESTIMATOR, code="POL-ELIG", name="elig", config={"method": "markup", "markup_pct": "10", "default_tax_category": "VAT-STD", "rounding": {"dp": 2},
                                    "contingency": {"pct": "5", "base": "direct", "eligibility": {"default": "include", "rules": [{"cost_prefix": "A", "eligible_pct": 0}]}}}, is_synthetic=True)
    commercial.submit_policy(db, ESTIMATOR, pid2)
    commercial.approve_policy(db, COMMERCIAL, pid2)
    commercial.assign_policy(db, ESTIMATOR, pid, pid2)
    c = compute_estimate(db, pid).commercial
    assert c.contingency == D("50.00") and "eligible direct 1000" in next(t for t in c.trace if t.name == "Contingency").formula
    with pytest.raises(ValidationFailed):
        commercial.create_policy(db, ESTIMATOR, code="POL-BAD", name="bad", config={"method": "markup", "markup_pct": "10", "contingency": {"pct": "5", "base": "cost_before_escalation",
                                 "eligibility": {"default": "include"}}}, is_synthetic=True)
