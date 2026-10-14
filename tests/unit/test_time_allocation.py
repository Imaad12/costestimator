"""Untied cost (supervision, crane, forklift, scaffolding) is never silently spread or dropped: it is allocated by an explicit approved rule, or exposed to the exact amount and
the cash-flow / escalation outputs are marked INCOMPLETE and the reconciliation gate blocks. All figures SYNTHETIC; expected values are hand-worked in the comments."""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.core.errors import ValidationFailed
from app.estimators.estimate import compute_estimate
from app.imports import boq as bi
from app.reconciliation import engine as recon
from app.services import boq, cashflow, governed, indirects, programme, projects, risk
from app.services.rates import create_resource
from tests.conftest import COMMERCIAL, ESTIMATOR
from tests.helpers import approve_vat, approved_assembly, approved_rate, std_policy, write_boq

TERMS = dict(name="SYNTHETIC terms", advance_pct="0", retention_pct="10", retention_release_at_completion_pct="50", defects_months="3", certification_lag_months="0",
             payment_lag_months="1", supplier_payment_lag_months="0", financing_rate_annual_pct="0", performance_bond_pct="0", performance_bond_fee_annual_pct="0")


def approve(db, kind, code, data, pid, actor=COMMERCIAL):
    i = governed.propose(db, ESTIMATOR, kind, code, data, project_id=pid, source="SYNTHETIC test", is_synthetic=True, submit=True)
    governed.approve(db, actor, i)
    return i


@pytest.fixture()
def proj(seeded, tmp_path):
    db = seeded
    spec = [("SUP", "subcontract", "day", "A.03", "100", "10"), ("CRN", "plant", "day", "A.07", "500", "4"), ("FRK", "plant", "day", "A.07", "200", "5"),
            ("SCF", "subcontract", "m2", "A.06", "5", "100"), ("PIP", "material", "m", "E.06", "10", "100")]
    rows = []
    for code, rtype, unit, cc, rate, qty in spec:
        create_resource(db, ESTIMATOR, resource_type=rtype, description=f"SYNTHETIC {code}", unit=unit, cost_code=cc, id=f"R-{code}", is_synthetic=True)
        approved_rate(db, f"R-{code}", rate)
        line = dict(line_type=rtype, resource_id=f"R-{code}", factor="1") | ({"factor_unit": "day"} if rtype == "plant" else {}) | ({"factor_includes_waste": 1} if rtype == "material" else {})
        approved_assembly(db, f"A-{code}", unit, [line], cost_code=cc)
        rows.append((code, f"SYNTHETIC {code}", unit, qty, "", ""))
    pid = projects.create_project(db, ESTIMATOR, name="Allocation (SYNTHETIC)", is_demo=True, tax_category="VAT-STD")
    bi.import_boq(db, ESTIMATOR, pid, write_boq(tmp_path / "b.csv", rows))
    for code, *_ in spec:
        boq.map_to_assembly(db, ESTIMATOR, pid, code, f"A-{code}")
        boq.set_cost_code(db, ESTIMATOR, pid, code, {"SUP": "A.03", "CRN": "A.07", "FRK": "A.07", "SCF": "A.06", "PIP": "E.06"}[code])
    std_policy(db, pid)
    approve_vat(db)
    approve(db, "calendar", "CAL", {"start_date": "2026-03-02", "work_weekdays": [0, 1, 2, 3, 4], "holidays": []}, pid)
    approve(db, "payment_terms", "PT", TERMS, pid)
    approve(db, "escalation_profile", "ESC", {"name": "SYNTHETIC esc", "annual_pct": "5", "base_date": "2026-03-01", "scope_kind": "all", "basis": "SYNTHETIC"}, pid)
    indirects.set_tasks(db, ESTIMATOR, pid, [dict(task_code="T1", name="Pipe work", duration_days="20", cost_code="E.06"),
                                             dict(task_code="T2", name="Handover", duration_days="10", predecessors="T1", cost_code="Z.99")])
    return db, pid


# direct cost by hand: SUP 10x100=1,000 ; CRN 4x500=2,000 ; FRK 5x200=1,000 ; SCF 100x5=500 ; PIP 100x10=1,000 -> 5,500 ; only PIP (1,000) is tied to a task (T1 by E.06)
def test_untied_costs_are_exposed_to_the_exact_amount_and_outputs_are_marked_incomplete(proj):
    db, pid = proj
    est = compute_estimate(db, pid)
    assert est.direct.direct_cost_total == D("5500.00")
    rep = programme.loading_report(db, pid, measure="cost", period="month", est=est)
    assert rep["unscheduled_total"] == D("4500") and rep["scheduled_total"] == D("1000")
    assert {(u["item_key"], u["amount"]) for u in rep["unscheduled_lines"]} == {("SUP", D("1000.00")), ("CRN", D("2000.00")), ("FRK", D("1000.00")), ("SCF", D("500.00"))}
    assert all(u["reason"] == "no_task_and_no_allocation_rule" for u in rep["unscheduled_lines"])
    cf = cashflow.cashflow_report(db, pid, est=est)
    assert cf["complete"] is False and cf["status"].startswith("INCOMPLETE - NOT FOR RELIANCE") and cf["unscheduled_cost"] == D("4500")
    rc = cf["reconciliation"]
    # only the allocated 1,000 of 5,500 direct is valued: valued price = net price x 1,000/5,500 ; the rest of the price is stated as unvalued, not smeared
    assert rc["valued_price"] + rc["unallocated_price_share"] == rc["net_price"] and abs(rc["valued_price"] - rc["net_price"] * D(1000) / D(5500)) < D("0.01")
    assert all(c["ok"] for c in rc["checks"])
    with pytest.raises(ValidationFailed) as e:
        cashflow.propose_financing_indirects(db, ESTIMATOR, pid)
    assert e.value.code == "TIMEPHASING_INCOMPLETE"
    es = risk.escalation_report(db, pid, est=est)
    assert es["complete"] is False and es["unescalated_eligible_cost"] == D("4500") and es["status"].startswith("INCOMPLETE - NOT FOR RELIANCE")
    findings = [(f["rule_code"], f["severity"], f["status"]) for f in recon.get_run(db, recon.run_reconciliation(db, ESTIMATOR, pid)["run_id"])["findings"]]
    assert ("TIMEPHASING_INCOMPLETE", "High", "Open") in findings                                # blocks the final gate (High is a blocking severity)
    assert any(b["rule_code"] == "TIMEPHASING_INCOMPLETE" for b in recon.final_gate(db, COMMERCIAL, pid)["blockers"])


def test_explicit_allocation_rules_make_cash_flow_and_escalation_complete_and_reconcile(proj):
    db, pid = proj
    approve(db, "time_allocation", "SUP-ALL", {"name": "Supervision over the whole programme", "scope_cost_prefix": "A.03", "tasks": ["ALL"], "basis": "SYNTHETIC: supervision runs for the whole programme"}, pid)
    approve(db, "time_allocation", "PLANT-T1", {"name": "Lifting plant on piping", "scope_cost_prefix": "A.07", "tasks": ["T1"], "shares": {"T1": "100"}, "basis": "SYNTHETIC"}, pid)
    approve(db, "time_allocation", "SCAF", {"name": "Scaffold split", "scope_cost_prefix": "A.06", "tasks": ["T1", "T2"], "shares": {"T1": "60", "T2": "40"}, "basis": "SYNTHETIC"}, pid)
    est = compute_estimate(db, pid)
    rep = programme.loading_report(db, pid, measure="cost", period="month", est=est)
    assert rep["unscheduled_total"] == 0 and abs(rep["scheduled_total"] - D("5500")) < D("0.0001") and rep["tie_out"]
    assert rep["allocated_by_rule"] == {"SUP-ALL": D("1000.00"), "PLANT-T1": D("3000.00"), "SCAF": D("500.00")}
    cf = cashflow.cashflow_report(db, pid, est=est)
    rc = cf["reconciliation"]
    assert cf["complete"] and cf["status"] == "COMPLETE" and rc["unallocated_price_share"] == 0 and all(c["ok"] for c in rc["checks"])
    # conventions: cash-out = direct (5,500) + indirect (0) ; retention 10 % of the price ; closing balance = price - cash-out (no interest) once retention is released
    assert abs(rc["cash_out_total"] - D("5500")) < D("0.0001") and abs(rc["retention_total"] - est.commercial.net_price * D("0.10")) < D("0.01")
    assert abs(cf["final_balance"] - (est.commercial.net_price - D("5500"))) < D("0.01")
    es = risk.escalation_report(db, pid, est=est)
    assert es["complete"] and es["unescalated_eligible_cost"] == 0 and abs(es["scheduled_base_total"] - D("5500")) < D("0.0001") and es["outside_profile_scope_cost"] == 0
    f = [(x["rule_code"]) for x in recon.get_run(db, recon.run_reconciliation(db, ESTIMATOR, pid)["run_id"])["findings"]]
    assert "TIMEPHASING_INCOMPLETE" not in f
    assert cashflow.propose_financing_indirects(db, ESTIMATOR, pid) is not None


def test_missing_mapping_conflict_and_invalid_rules_are_exposed_not_guessed(proj):
    db, pid = proj
    approve(db, "time_allocation", "GHOST", {"name": "Names a task that is not in the programme", "scope_cost_prefix": "A.03", "tasks": ["NOPE"], "basis": "SYNTHETIC"}, pid)
    approve(db, "time_allocation", "DUP-1", {"name": "one", "scope_cost_prefix": "A.07", "tasks": ["T1"], "basis": "SYNTHETIC"}, pid)
    approve(db, "time_allocation", "DUP-2", {"name": "two (same scope)", "scope_cost_prefix": "A.07", "tasks": ["T2"], "basis": "SYNTHETIC"}, pid)
    rep = programme.loading_report(db, pid, measure="cost", period="month", est=compute_estimate(db, pid))
    reasons = {u["item_key"]: u["reason"] for u in rep["unscheduled_lines"]}
    assert reasons["SUP"].startswith("rule_task_missing: GHOST") and reasons["CRN"].startswith("rule_conflict: DUP-1, DUP-2") and reasons["FRK"].startswith("rule_conflict")
    assert reasons["SCF"] == "no_task_and_no_allocation_rule" and rep["unscheduled_total"] == D("4500")                 # nothing was dropped or smeared
    bad = dict(name="x", scope_cost_prefix="A.06", basis="b")
    for data, why in (({**bad, "tasks": ["T1", "T1"]}, "twice"), ({**bad, "tasks": ["T1", "T2"], "shares": {"T1": "70", "T2": "40"}}, "exceeds"),
                      ({**bad, "tasks": ["T1", "T2"], "shares": {"T1": "30", "T2": "40"}}, "does not cover"), ({**bad, "tasks": ["T1"], "shares": {"T2": "100"}}, "exactly one entry"),
                      ({"name": "x", "tasks": ["T1"], "basis": "b"}, "scope"), ({**bad, "tasks": ["ALL", "T1"]}, "ALL")):
        with pytest.raises(ValidationFailed) as e:
            governed.propose(db, ESTIMATOR, "time_allocation", "BAD", data, project_id=pid, source="s", is_synthetic=True)
        assert why in e.value.message, (why, e.value.message)


def test_zero_duration_activities_and_unapproved_rules(proj):
    db, pid = proj
    indirects.set_tasks(db, ESTIMATOR, pid, [dict(task_code="T1", name="Pipe work", duration_days="0", cost_code="E.06"), dict(task_code="T2", name="Milestone", duration_days="0", predecessors="T1")])
    approve(db, "time_allocation", "SUP-ALL", {"name": "all", "scope_cost_prefix": "A.03", "tasks": ["ALL"], "basis": "SYNTHETIC"}, pid)
    rep = programme.loading_report(db, pid, measure="cost", period="month", est=compute_estimate(db, pid))
    # all activities are zero-duration: ALL splits equally, everything lands on the start day, no division by zero, totals conserved
    assert rep["allocated_by_rule"] == {"SUP-ALL": D("1000.00")} and abs(rep["scheduled_total"] + rep["unscheduled_total"] - rep["source_total"]) < D("0.0001")
    # a Draft/pending rule is not in force: the cost stays unallocated
    i = governed.propose(db, ESTIMATOR, "time_allocation", "PLANT-T1", {"name": "p", "scope_cost_prefix": "A.07", "tasks": ["T1"], "basis": "SYNTHETIC"}, project_id=pid, source="s", is_synthetic=True, submit=True)
    rep2 = programme.loading_report(db, pid, measure="cost", period="month", est=compute_estimate(db, pid))
    assert {u["item_key"] for u in rep2["unscheduled_lines"]} >= {"CRN", "FRK"}
    governed.approve(db, COMMERCIAL, i)
    assert {u["item_key"] for u in programme.loading_report(db, pid, measure="cost", period="month", est=compute_estimate(db, pid))["unscheduled_lines"]} == {"SCF"}
