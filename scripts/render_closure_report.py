"""Render docs/SYNTHETIC_END_TO_END_CLOSURE_REPORT.md and docs/TENDER_DOCUMENT_APPLICABILITY_MATRIX.md from the machine-readable results of a closure run.

Usage: python scripts/render_closure_report.py RESULTS_DIR [--code-commit SHA] [--suite "N passed in T s"] [--scratch PATH]
RESULTS_DIR holds acceptance_results.json and MANIFEST.json written by scripts/run_closure_scenario.py. Nothing is typed in by hand: every number comes from the run's evidence.
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.tender import catalogue  # noqa: E402
from tests.closure import data as Dt  # noqa: E402


def money(x) -> str:
    return f"{D(str(x)):,.2f}"


def table(rows, cols) -> str:
    out = ["", "| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in r) + " |")
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    args = list(argv)
    opt = {}
    for k in ("--code-commit", "--suite", "--scratch"):
        if k in args:
            i = args.index(k)
            opt[k] = args[i + 1]
            del args[i:i + 2]
    res_dir = Path(args[0])
    R = json.loads((res_dir / "acceptance_results.json").read_text())
    M = json.loads((res_dir / "MANIFEST.json").read_text())
    S = R["stages"]
    v = R["verdicts"]
    L: list[str] = []
    A = L.append
    A("# Synthetic end-to-end closure report")
    A("")
    A("> **" + Dt.BANNER + "**")
    A("> Everything below is SYNTHETIC TEST DATA: a fictional customer, fictional quantities, rates, quotations, productivity norms, workforce profiles and customer responses. Every actor is a registered **TEST ACTOR**; "
      "their approvals validate software behaviour and are not procurement, commercial, technical, tax or legal approvals. Nothing here is market evidence, a live quotation, a client requirement or an estimating-accuracy claim.")
    A("")
    A("Reproduce: `python scripts/run_closure_scenario.py <fresh dir> --out <dir>` (driver `tests/closure/scenario.py`, independent oracle `tests/closure/oracle.py`, tests `tests/closure/`). "
      "The generated packs are in `demo_output/synthetic_closure/`.")
    A("")
    A("## 1. Result")
    A(table([(k, x) for k, x in v.items()], ["stage", "verdict"]))
    A(f"**All stages PASS: {R['all_pass']}.** Stages that were not run are reported `NOT TESTED`; none is omitted. Not exercised by this run (and so not claimed): landed cost / FX (SAR-only), a real client profile, supplier quotation *file* import, "
      "AI suggestions, Microsoft Excel, bespoke UI forms for the closure registers (they are reachable through reports, REST actions and the CLI `action` command), real Saudi calendars and real productivity norms.")
    A("")
    A("## 2. Run identity")
    A(table([("Branch", "`claude/wizardly-einstein-w4ykwd`"), ("Code commit", f"`{opt.get('--code-commit', 'see git log')}`"), ("Scratch run directory", f"`{opt.get('--scratch', 'a fresh temporary directory')}` (database `scratch_closure.db`)"),
             ("Test environment", "`KSA_ENVIRONMENT=test`, `KSA_ALLOW_SELF_APPROVAL=false` (four-eyes on)"), ("Full regression suite", opt.get("--suite", "see TESTING.md")),
             ("Project", f"`{M['project']}` {M['scenario']}"), ("Estimate", f"frozen version v{M['estimate_version']}, fingerprint `{M['estimate_fingerprint'][:16]}...`"),
             ("Tender pack", f"revision {M['tender_pack']['revision']}, classification **{M['tender_pack']['classification']}**, production ready: **{M['tender_pack']['production_ready']}**"),
             ("Handover pack", f"revision {M['handover_pack']['revision']}, **hypothetical** (no award was made)"), ("Files in the manifest", len(M["files"]))], ["item", "value"]))
    A("")
    A("## 3. Workflow evidence by stage")
    e = S["03_project_and_documents"]
    A(f"* **Enquiry and project (1-3)**: enquiry `{S['01_enquiry']['enquiry']}` from a fictional customer; bid/no-bid items {S['02_bid_no_bid']['items']} (statuses {S['02_bid_no_bid']['statuses']}); document register: {e['current']} current, "
      f"superseded {e['superseded']}, missing {e['missing']}, {e['not_interpreted']} documents registered but **not interpreted** (content status `registered_only`).")
    b = S["04_boq_import"]
    A(f"* **BOQ (4-5)**: {b['items']} lines imported, duplicates {b['duplicates']}, units not ok {b['units_not_ok']}; unmapped after mapping {S['05_validate_and_map']['unmapped']}; resources deliberately without a rate {S['05_validate_and_map']['resources_without_rate']}.")
    a6 = S["06_assumptions_and_missing_data"]
    A(f"* **Assumptions (6)**: classes {a6['counts']}; the new synthetic assumptions classify as {a6['classes_of_new_assumptions']}; fully verified = {a6['fully_verified']}.")
    d7 = S["07_direct_cost_and_missing_rates"]
    A(f"* **Direct cost (7)**: application SAR {money(d7['application_direct_cost'])} = independent SAR {money(d7['independent_direct_cost_priced_lines'])} for the priced lines (line differences: {d7['line_differences'] or 'none'}); "
      f"state `{d7['state']}`; unpriced resources {d7['unpriced_resources']} stay unpriced (never zero).")
    A("")
    A("### Crew-size scenarios (stage 8) - same activities, norms and calendar; SYNTHETIC norms")
    s8 = S["08_productivity_and_crew_scenarios"]
    A(table([(s["profile"], s["archetype"], s["headcount"], s.get("subcontract_capacity", ""), s["working_days"], s["calendar_days"], s["finish"], s["peak_workers"], s["labour_hours"], ", ".join(s["resource_limited"]) or "-", s["cost"].get("total") if s["cost"].get("computed") else "not computed")
             for s in s8["scenarios"]], ["profile", "archetype", "head-count (own direct + indirect)", "subcontract capacity", "working days", "calendar days", "finish", "peak direct workers", "labour-hours", "resource-limited activities", "planning cost (synthetic role day-costs)"]))
    A(f"Calendar used: {json.dumps(s8['calendar'])}. {s8['note']}")
    A("")
    s9 = S["09_resource_constrained_programme"]
    A(f"* **Programme (9, MID profile, first provisional run)**: unconstrained longest activity {s9['unconstrained_activity_max_wd']} wd; dependency-constrained {s9['dependency_constrained_wd']} wd; procurement-constrained {s9['procurement_constrained_wd']} wd; "
      f"resource-constrained {s9['resource_constrained_wd']} wd ({s9['calendar_days']} calendar days, {s9['start']} to {s9['finish']}); critical path `{' > '.join(s9['critical_path'])}`; gaps reported: {s9['gaps']}; claim: **{s9['claim']}**.")
    A(table([(a["code"], a["status"], a["hours"], a["crew_days"], a["unconstrained"], a["start"], a["finish"], a["delay"], a["float"], "yes" if a["critical"] else "") for a in s9["activity_rows"]],
            ["activity", "status", "labour-hours", "crew-days", "unconstrained wd", "start (wd index)", "finish", "resource delay", "float", "critical"]))
    s10, s11, s12 = S["10_queries_and_clarifications"], S["11_customer_responses"], S["12_recalculate_impacts"]
    A(f"* **Queries (10-12)**: {s10['by_register']} draft queries created by detectors ({len(s10['detector_keys'])} detector keys), all `Draft`; before release a draft cannot be issued ({s10['refused']['issue_draft']}) and cannot be answered "
      f"({s10['refused']['response_before_issue']}). {len(s11['answered'])} synthetic customer responses were entered by a TEST ACTOR and labelled synthetic. Recalculation after the answers: direct cost SAR {money(s12['direct_before'])} -> "
      f"SAR {money(s12['direct_after'])}; delta SAR {money(s12['delta_application'])} = independent SAR {money(s12['delta_independent'])}.")
    s13 = S["13_procurement_and_quote_levelling"]
    A("")
    A("### Quotation levelling (stage 13) - SYNTHETIC suppliers, not live quotations")
    A(table([(k, money(s13["headline_totals"][k]), money(s13["expected_headline"][k]), money(s13["evaluated_totals"][k])) for k in sorted(s13["headline_totals"])], ["supplier", "headline total (application)", "headline total (hand calculation)", "evaluated total after approved delivery adjustment"]))
    A(f"Headline lowest: **{s13['headline_lowest']}**; evaluated winner after delivery and validity: **{s13['evaluated_winner']}**. Publishing rates before the selection was approved was refused ({s13['publish_before_approval_blocked_with']}); "
      f"published rates start `{s13['rates_status_on_publish'][0]}` and needed a second approval.")
    A("")
    s14 = S["14_indirects_tax_risk_escalation_cashflow"]
    A("### Cost, commercial chain and independent reconciliation (stage 14, before the open items were resolved)")
    A(table([(k, money(s14["totals"][k]) if k in s14["totals"] else "") for k in ("direct_cost", "indirect_cost", "total_cost", "selling_price_pre_tax", "commercial_net_price", "tax", "final_payable")], ["application total", "SAR"]))
    A(table([(k, x if k in ("markup_on_cost", "margin_on_price") else money(x)) for k, x in s14["independent"].items()], ["independent (separate formulas)", "SAR (ratios unitless)"]))
    A(f"Findings raised at that point (all expected): {s14['findings']}. Escalation then read: *{s14['escalation_status']}*. Tax is charged on the **tendered pricing schedule** (sum of printed line amounts), "
      "which differs from the commercial net price by the unit-rate rounding variance reported above (existing limitation O-9, now measured and bounded).")
    s21 = S["21_resolve_issues_with_test_approvals"]
    ta = s21["time_allocation"]
    A("")
    A("### Cost with no time allocation (stage 21)")
    A(table([("before any rule", ta["before"]["cashflow_status"]), ("financing proposal", f"refused: {ta['before']['financing_refused_with']}"), ("final gate", f"blocked by TIMEPHASING_INCOMPLETE: {ta['before']['final_gate_blocked_by_it']}"),
             ("after first rule batch", ta["first_batch"]["cashflow_status"]), ("still untied (exact lines)", ta["first_batch"]["unallocated_lines"]), ("after second batch", f"{ta['after']['cashflow_status']}; reconciliation checks ok: {ta['after']['reconciliation_checks_ok']}; escalation complete: {ta['after']['escalation_complete']}")],
            ["step", "result"]))
    A(f"Programme baseline approved after the calendar was confirmed, the missing NDT norm approved and the order date moved: {s21['programme']['working_days']} wd / {s21['programme']['calendar_days']} calendar days, finish {s21['programme']['finish']}; claim **{s21['programme']['claim']}**. "
      f"Exceptions accepted by the (test) Commercial Approver: {s21['exceptions_accepted']}; Critical findings open: {s21['critical_open']}; final gate blocked: {s21['gate_blocked']}; estimate state `{s21['estimate_state']}`.")
    A(table([(k, money(x)) for k, x in s21["totals"].items()], ["frozen-candidate total after resolution", "SAR"]))
    A("")
    A("## 4. Documents")
    s16, s17, s22, s23 = S["16_applicability_matrix"], S["17_generate_document_pack"], S["22_final_demonstration_pack"], S["23_hypothetical_handover_pack"]
    A(f"* Applicability matrix (stage 16): {s16['counts']} (see `docs/TENDER_DOCUMENT_APPLICABILITY_MATRIX.md`).")
    A(f"* First pack (revision {s17['pack_revision']}, before resolution): statuses {s17['statuses']}; **blocked**: {s17['blocked']}; {s17['files']} files; validator: {S['18_validate_document_pack']['ok']} (warnings: {len(S['18_validate_document_pack']['warnings'])}).")
    A(f"* Final demonstration pack (revision {s22['pack_revision']}): classification **{s22['classification']}**; banner: `{s22['banner']}`; blocked in rev 1 {s22['blocked_in_rev1']} -> now {s22['blocked_now']}; statuses {s22['statuses']}; "
      f"validation ok={s22['validation']['ok']} over {s22['validation']['files']} files (warnings: {s22['validation']['warnings']}). Exports: {s22['exports']}; files {s22['export_files']}.")
    A(f"* Hypothetical post-award handover (revision {s23['pack_revision']}): 17 documents H01-H17; refused before an award scenario was recorded: `{s23['refused_before_award_scenario']}`; banner `{s23['banner'][:120]}...`; validation ok={s23['validation']['ok']} ({s23['validation']['files']} files).")
    A("")
    A("## 5. Controls that were attacked")
    s19, s20 = S["19_production_readiness_blocked"], S["20_assumption_bypass_blocked"]
    A("**Production readiness (stage 19)**")
    A(table([(k, x) for k, x in s19["real_project_attempts_in_production_env"].items()] + [("classification of the demonstration project", s19["classification_in_test_environment"]),
                                                                                         ("classification even if the environment were production", s19["classification_if_production_environment"]), ("exports marked submission-ready", s19["exports_marked_submission_ready"])],
            ["attempt", "result"]))
    A(f"Resolved actor types: {s19['resolved_actor_types']}. Structural reasons: {s19['structural_reasons']}.")
    A("")
    A("**Assumption / identity bypass attempts (stage 20)**")
    rows = [(k, s20[k]) for k in ("author_self_approval", "administrator_self_approval", "viewer_approval", "ai_approval", "ai_creates_register_row", "manual_entry_is_not_approval", "approved_by_a_second_person",
                                  "sql_update_of_approved_value", "sql_delete_of_approved", "sql_replace_provenance", "sql_make_synthetic_look_real", "forged_identity_recorded_as", "forged_approval_counts_for_production")]
    rows += [(f"REST: {k}", x) for k, x in s20["api"].items()] + [(f"CLI: {c['cmd']}", f"exit {c['exit']}: {c['err'].strip()[:110]}") for c in s20["cli"]]
    A(table(rows, ["attempt", "result"]))
    A("")
    A("## 6. Freeze, library change, replay, interfaces")
    s24, s25, s26, s27 = S["24_freeze_estimate_and_manifest"], S["25_global_library_change"], S["26_snapshot_replay"], S["27_ui_api_cli_agreement"]
    A(f"* Manifest: {s24['files_in_manifest']} files with SHA-256; tender manifest `{s24['tender_manifest_sha256'][:16]}...`, handover manifest `{s24['handover_manifest_sha256'][:16]}...`.")
    A(f"* After the freeze a global rate (+25 %, new approved version) and a global assumption (new approved version) were changed: the **live** payable moved SAR {money(s25['live_total_before'])} -> SAR {money(s25['live_total_after'])}; "
      f"the **frozen** payable stayed SAR {money(s25['frozen_total'])}; replay ok = {s25['frozen_replay_ok']}; document figures in the regenerated pack differ from the previous pack in: {s25['document_figure_differences_rev_after_vs_before'] or 'nothing'}.")
    A(f"* Replay (26): ok = {s26['replay_ok']}, fingerprint `{s26['replay_fingerprint']}...`, documents agree with frozen totals = {s26['documents_agree_with_frozen_totals']}.")
    A(f"* UI/API/CLI (27): {s27['agreement']}; UI pages {len(s27['ui'])} all HTTP 200 without a traceback; CLI exits {s27['cli_exit']}.")
    A("")
    A("## 7. Honest limits of this evidence")
    A("* The synthetic norms, crews, calendars, rates and quotations were written by the scenario author; agreement between the application and the oracle proves the **arithmetic and the controls**, not any real-world productivity, price or duration.")
    A("* The oracle (`tests/closure/oracle.py`) re-implements the calculations with fractions, a recursive CPM and a plain calendar loop; it shares the author and the fixtures with the application, so it is independent code, not independent judgement.")
    A("* Tax uses the seeded synthetic parameter; no tax professional verified it. Saudi labour, calendar and SBC references are in the source register as *partially verified* or *requires human acquisition*; no clause is claimed.")
    A("* The scenario runs with `KSA_ENVIRONMENT=test`; the production path (registered human approvers, production environment) is exercised separately in `tests/approvals/test_actor_isolation.py` and `tests/closure/test_production_pack_gate.py`.")
    (ROOT / "docs" / "SYNTHETIC_END_TO_END_CLOSURE_REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    # ------------------------------------------------------------------ applicability matrix document
    mxf = res_dir / "applicability_matrix_rev1_before_resolution.json"
    if not mxf.exists():
        c = sorted(res_dir.glob("PRJ-*_tender_pack_r*/applicability_matrix.json"))
        mxf = c[0] if c else None
    mx = json.loads(mxf.read_text()) if mxf else None
    T: list[str] = []
    B = T.append
    B("# Tender document applicability matrix")
    B("")
    B("Not every tender needs every document. `app/tender/catalogue.py` classifies each of the 45 catalogue items as **Required**, **Conditional**, **Not Applicable** or **Missing Customer Requirement** with a stated reason, "
      "from the project's trades, delivery model, contract type, the customer's *recorded* requirements, the documents received and the project stage. Report: `python -m app.cli report PRJ-nnnn applicability`.")
    B("")
    B("## Inputs the matrix reads")
    B("* `tender_context` register item: `contract_type`, `delivery_model`, `customer_requires` (e.g. `{technical_proposal: yes|no, quality_plan: yes|no}`), `award_scenario` (`hypothetical` only for simulations).")
    B("* The received-document register (a current `specification` makes compliance documents Required; its absence makes them *Missing Customer Requirement*).")
    B("* Work activities, payment terms, long-lead items, indirect items, plant-hire terms, BOQ trades and commissioned trades (mechanical, HVAC, electrical, ELV, fire, piping, plumbing, industrial, instrument).")
    B("")
    B("## Rules (the whole rule set)")
    B(table([("always Required", "D01-D09, D11, D12, D14, D15, D25, D29, D33-D36, D40-D43, D45 - core tender record for every tender"), ("D10", "Required when a commercial clarification is registered, else Conditional"),
             ("D13", "Required with approved payment terms, else Missing Customer Requirement"), ("D16-D18", "customer_requires.technical_proposal: yes -> Required, no -> Not Applicable, unrecorded -> Missing Customer Requirement"),
             ("D19-D20", "Required when work activities exist, else Missing Customer Requirement"), ("D21", "Required with plant-hire terms, else Conditional"), ("D22", "Required with long-lead items, else Conditional"),
             ("D23-D24", "Required when a specification is received, else Missing Customer Requirement"), ("D26", "Required for design-build / EPC delivery, else Conditional"),
             ("D27, D28, D30", "customer_requires.quality_plan decides; with a specification and no statement -> Required"), ("D31", "Required with a commissioned trade, else Conditional"), ("D32", "Conditional (confirm customer handover requirements)"),
             ("D37", "Required when activities exist, else Conditional"), ("D38", "Required when indirect items exist, else Not Applicable"), ("D39", "Required when plant-hire terms exist, else Not Applicable"),
             ("D44", "Required only with an award scenario selected, else Not Applicable (tender stage)")], ["documents", "rule"]))
    B("")
    B("## The catalogue")
    B(table([(f"D{n:02d}", g, t, "DOCX, PDF" + (", XLSX" if x else ""), tid) for n, g, t, x, tid in catalogue.CATALOGUE], ["code", "group", "document", "formats", "template id (version " + catalogue.TEMPLATE_VERSION + ")"]))
    B("Handover (simulated post-award) documents H01-H17: " + "; ".join(f"{c} {t}" for c, t, _ in catalogue.HANDOVER_DOCS) + ".")
    if mx:
        B("")
        B(f"## Matrix produced for the synthetic closure project (revision 1 pack, before the open items were resolved)")
        B(f"Counts: {mx['counts']}. Inputs: {mx['inputs']}.")
        B(table([(r["code"], r["title"], r["applicability"], r["reason"]) for r in mx["rows"]], ["code", "document", "applicability", "reason"]))
    B("")
    B("## What a status means")
    B(table([("BLOCKED", "the document contains an explicit `[[MISSING: ...]]` marker (missing input or Missing Customer Requirement); it cannot be approved until the input exists"),
             ("Preliminary (DEMONSTRATION)", "pack classification is `demonstration` (demo/synthetic data, test environment or test actors) - never submission-ready"), ("Draft", "classification `not_ready`"),
             ("For Review", "the approval chain verifies in a production environment **and** the pack has no BLOCKED documents and no placeholders; awaiting document approval"),
             ("Approved for Submission", "as above **and** that document was approved by a registered human Commercial Approver/Administrator in production"), ("Not Applicable", "no files; reason recorded")], ["status", "meaning"]))
    (ROOT / "docs" / "TENDER_DOCUMENT_APPLICABILITY_MATRIX.md").write_text("\n".join(T) + "\n", encoding="utf-8")
    print("rendered docs/SYNTHETIC_END_TO_END_CLOSURE_REPORT.md and docs/TENDER_DOCUMENT_APPLICABILITY_MATRIX.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
