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
    # indirects 8% + 3% of 366,261 = 29,300.88 + 10,987.83 ; contingency 5% of 406,549.71 = 20,327.49 ; markup 7% of 426,877.20 = 456,758.60
    assert (c["indirect"], c["contingency"], c["total_cost"], c["net_price"]) == ("40288.71", "20327.49", "426877.20", "456758.60")


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
