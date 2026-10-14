"""Reusable SYNTHETIC end-to-end pilot (tests/synthetic_pilot/pilot.py; evidence report docs/SYNTHETIC_PILOT_RUN.md).

Drives the real services/CLI/API against a scratch database. Every figure is SYNTHETIC / TEST ONLY / NOT A MARKET QUOTE; 'TEST ACTOR' approvals validate software behaviour only.
Expected values below are computed independently of the engine (see pilot.independent_total and the hand arithmetic in the comments)."""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from app import config as cfg
from app.database import set_db
from tests.synthetic_pilot import pilot


@pytest.fixture(scope="module")
def ev(tmp_path_factory):
    work = tmp_path_factory.mktemp("synthetic_pilot")
    try:
        yield pilot.run(work)
    finally:
        set_db(None)
        cfg.set_settings(None)


def test_every_stage_passes(ev):
    v = pilot.verdicts(ev)
    assert v and all(x == "PASS" for x in v.values()), v


def test_independent_boq_total_and_engine_reconcile(ev):
    ext, tot = pilot.independent_total()
    assert len(ext) == 30 and tot == D("365361")                    # hand sum of the 30 extensions (quantity x synthetic baseline rate)
    e = ev["11_12_13_cost_commercial_risk_cashflow"]
    assert e["direct_total_engine"] == "366261.00" and e["line_extension_differences"] == {"P-020": "900.00"}      # + crane standby: 1 day x 1,800 x 50%
    c = e["commercial_chain"]["engine"]
    # eligible base = E/D/F scope 302,691 (division A, 63,570 incl. the standby, excluded by the approved eligibility rules); indirects 8% + 3% of it = 24,215.28 + 9,080.73 = 33,296.01
    # (the legacy whole-direct-cost base gave 40,288.71) ; contingency 5% of 399,557.01 = 19,977.85 ; markup 7% of 419,534.86 = 448,902.30
    assert (c["indirect"], c["contingency"], c["total_cost"], c["net_price"]) == ("33296.01", "19977.85", "419534.86", "448902.30")
    assert e["commercial_chain"]["indirect_on_whole_direct_cost_legacy"] == "40288.71" and e["commercial_chain"]["eligible_base"] == "302691"


def test_quotation_levelling_recommends_a_not_the_headline_lowest_b(ev):
    q = ev["7_quotation_levelling"]
    assert q["headline_lowest"] == "B" and q["recommendation"] == "A"
    assert {r["supplier"]: str(r["evaluated_total"]) for r in q["table"]} == {"A": "86350.40", "B": "88019.55", "C": "90065.70"}          # hand-computed, B includes the 2,500 delivery
    assert q["selection_status_when_proposed"] == "Pending Review" and q["publish_before_approval_blocked_with"] == "SELECTION_NOT_APPROVED"


def test_frozen_estimate_replays_identically_after_parameter_and_rate_change(ev):
    r = ev["16_freeze_and_replay"]
    assert r["replay_after_changes"]["ok"] and r["replay_after_changes"]["fingerprint"] == r["v1"]["fingerprint"] and r["v1_row_unchanged"]
    assert r["current_fingerprint_after_changes"] != r["v1"]["fingerprint"] and r["current_totals_after"]["direct_cost"] == "373901.00"     # +7,640: hours x1.10 and welder 65->70
    assert r["export_of_frozen_v1_after_changes_refused_with"] == "EXPORT_BLOCKED" and r["audit_chain"]["ok"]


def test_preliminary_estimate_cannot_become_final_or_exportable(ev):
    n = ev["15_preliminary_cannot_be_final"]
    assert n["state"].startswith("Preliminary") and n["approve_version"] == "ESTIMATE_PRELIMINARY" and n["export_submission"] == "EXPORT_NOT_APPROVED"
    assert ("Critical", "SYNTHETIC_IN_REAL_PROJECT") in [tuple(x) for x in n["reconciliation_findings"]]
    g = ev["15_gates_and_17_export"]
    assert [f for f in g["findings_before"] if f[1] == "PLANT_HIRE_DAYS"] and not [f for f in g["findings_before"] if f[1] in ("TIMEPHASING_INCOMPLETE", "SYSTEM_EXCEPTION")]
    assert g["approve_before_exceptions"] == "RECON_BLOCKED" and g["ai_cannot_approve"] == "AI_CANNOT_APPROVE" and g["export_without_approval"] == "EXPORT_NOT_APPROVED"


def test_index_sources_and_unit_rules_hold_in_the_pilot(ev):
    assert set(ev["6_rate_import"]["index_source_results"].values()) == {"SOURCE_NOT_PRICE"}
    u = ev["3_project_workspace"]
    assert set(u["units_flagged_on_import"]) == {"P-016", "P-022", "P-024"} and u["unit_decisions"] == {"P-016": "inch_dia", "P-022": "m2_day", "P-024": "test"}


def test_takeoff_replay_and_stale_derivation(ev):
    t = ev["16b_replay_with_takeoff"]
    assert t["replay_ok"] and t["replayed_fingerprint_equals_frozen"] and t["estimate_unchanged_until_a_person_re_applies"]
    assert t["stale_applications_flagged"] and t["stale_applications_flagged"][0][2] == ["FACTORS_CHANGED"]
    d = ev["10_takeoff_templates"]
    assert all(v["pricing_status"] == "Pending Review" for v in d["derived"].values()) and d["boq_quantities_unchanged"] and not d["items_priced_before_human_approval"]


def test_actual_cli_import_commands_dry_run_then_draft_and_index_refusal(ev):
    cli = ev["17_reports_api_ui_export"]["cli_imports"]
    assert [c["exit"] for c in cli] == [0, 0, 0, 0, 0, 1]
    assert '"would_create": 1' in cli[0]["out"] and '"status": "Draft"' in cli[1]["out"] and "SOURCE_NOT_PRICE" in cli[5]["out"]
    assert ev["17_reports_api_ui_export"]["cross_checks"]["cli_rollup_tie_out"]["cbs"] is True


def test_untied_costs_block_until_explicit_allocation_then_reconcile(ev):
    t = ev["13d_time_allocation"]
    b, a = t["before"], t["after"]
    assert b["unallocated_direct_cost"] == "37950.00" and b["cashflow_status"].startswith("INCOMPLETE - NOT FOR RELIANCE") and b["escalation_status"].startswith("INCOMPLETE - NOT FOR RELIANCE")
    assert sorted(u[0] for u in b["unallocated_lines"]) == ["P-020", "P-020", "P-021", "P-022", "P-030"] and b["financing_proposal_refused_with"] == "TIMEPHASING_INCOMPLETE" and b["final_gate_blocked_by_it"]
    # 17,000 + 4,050 + 10,800 + 900 + 5,200 = 37,950 ; price share not valued = price x 37,950/366,261 (stated, never smeared)
    assert a["cashflow_status"] == "COMPLETE" and a["escalation_status"].startswith("COMPLETE") and not a["findings_remaining"]
    assert a["allocated_by_rule"] == {"SUP-ALL": "17000.00", "LIFT-INST-WELD": "16900.00", "SCAFFOLD": "4050.00"} and all(c["ok"] for c in a["reconciliation"]["checks"])


def test_day_priced_plant_terms_and_programme_window(ev):
    g = ev["15_gates_and_17_export"]["findings_before"]
    assert sum(1 for f in g if f[1] == "PLANT_HIRE_DAYS") == 2                           # BOQ bills 6 / 8 days; the programme window INST..WELD is 10 working days (hand check in the report)


def test_pilot_can_never_be_production_ready(ev):
    p = ev["19_production_isolation"]
    assert p["verdict"] == "PASS" and not p["production_ready"] and p["classification_in_pilot_environment"] == "demonstration" and p["exports_marked_submission_ready"] == 0
    assert p["approvals_by_actor_type_and_environment"] == [{"actor_type": "test", "environment": "test", "n": p["approvals_by_actor_type_and_environment"][0]["n"]}]
    assert p["resolved_actor_types"]["forged_display_name"] == "unregistered" and p["resolved_actor_types"]["role_mismatch"] == "role_mismatch"
    assert p["test_actor_approving_a_real_project_in_production"] == "NON_HUMAN_ACTOR" and p["direct_export_attempt_on_a_real_project_by_a_test_actor"] == "NON_HUMAN_ACTOR"
    banner = ev["15_gates_and_17_export"]["submission_banner_cells"][1]
    assert banner.startswith("DEMONSTRATION EXPORT - NOT SUBMISSION READY - NOT APPROVED FOR ANY REAL TENDER") and "test principals" in banner
