# Synthetic end-to-end closure report

> **SYNTHETIC SOFTWARE VALIDATION ONLY - FICTIONAL CUSTOMER - NOT A REAL TENDER - NOT FOR SUBMISSION OR COMMERCIAL RELIANCE.**
> Everything below is SYNTHETIC TEST DATA: a fictional customer, fictional quantities, rates, quotations, productivity norms, workforce profiles and customer responses. Every actor is a registered **TEST ACTOR**; their approvals validate software behaviour and are not procurement, commercial, technical, tax or legal approvals. Nothing here is market evidence, a live quotation, a client requirement or an estimating-accuracy claim.

Reproduce: `python scripts/run_closure_scenario.py <fresh dir> --out <dir>` (driver `tests/closure/scenario.py`, independent oracle `tests/closure/oracle.py`, tests `tests/closure/`). The generated packs are in `demo_output/synthetic_closure/`.

## 1. Result

| stage | verdict |
|---|---|
| 01_enquiry | PASS |
| 02_bid_no_bid | PASS |
| 03_project_and_documents | PASS |
| 04_boq_import | PASS |
| 05_validate_and_map | PASS |
| 06_assumptions_and_missing_data | PASS |
| 07_direct_cost_and_missing_rates | PASS |
| 08_productivity_and_crew_scenarios | PASS |
| 09_resource_constrained_programme | PASS |
| 10_queries_and_clarifications | PASS |
| 11_customer_responses | PASS |
| 12_recalculate_impacts | PASS |
| 13_procurement_and_quote_levelling | PASS |
| 14_indirects_tax_risk_escalation_cashflow | PASS |
| 15_methodology_and_compliance | PASS |
| 16_applicability_matrix | PASS |
| 17_generate_document_pack | PASS |
| 18_validate_document_pack | PASS |
| 19_production_readiness_blocked | PASS |
| 20_assumption_bypass_blocked | PASS |
| 21_resolve_issues_with_test_approvals | PASS |
| 22_final_demonstration_pack | PASS |
| 23_hypothetical_handover_pack | PASS |
| 24_freeze_estimate_and_manifest | PASS |
| 25_global_library_change | PASS |
| 26_snapshot_replay | PASS |
| 27_ui_api_cli_agreement | PASS |

**All stages PASS: True.** Stages that were not run are reported `NOT TESTED`; none is omitted. Not exercised by this run (and so not claimed): landed cost / FX (SAR-only), a real client profile, supplier quotation *file* import, AI suggestions, Microsoft Excel, bespoke UI forms for the closure registers (they are reachable through reports, REST actions and the CLI `action` command), real Saudi calendars and real productivity norms.

## 2. Run identity

| item | value |
|---|---|
| Branch | `claude/wizardly-einstein-w4ykwd` |
| Code commit | `see git log (final commit on branch)` |
| Scratch run directory | `/tmp/claude-0/final2` (database `scratch_closure.db`) |
| Test environment | `KSA_ENVIRONMENT=test`, `KSA_ALLOW_SELF_APPROVAL=false` (four-eyes on) |
| Full regression suite | 458 passed |
| Project | `PRJ-9101` Dammam Industrial Utilities - Synthetic Tender Closure |
| Estimate | frozen version v2, fingerprint `48d0f9242dc910b7...` |
| Tender pack | revision 2, classification **demonstration**, production ready: **False** |
| Handover pack | revision 1, **hypothetical** (no award was made) |
| Files in the manifest | 165 |


## 3. Workflow evidence by stage
* **Enquiry and project (1-3)**: enquiry `ENQ-0001` from a fictional customer; bid/no-bid items ['capacity', 'margin', 'risk'] (statuses ['Approved', 'Approved', 'Approved']); document register: 11 current, superseded [['DWG-PR-001', 'B']], missing ['DWG-EL-010'], 11 documents registered but **not interpreted** (content status `registered_only`).
* **BOQ (4-5)**: 44 lines imported, duplicates ['C-071#2'], units not ok []; unmapped after mapping ['C-071#2']; resources deliberately without a rate ['SYN-C-045', 'SYN-C-046', 'SYN-C-047'].
* **Assumptions (6)**: classes {'Verified source data': 0, 'Company-approved internal data': 0, 'Project-approved data': 0, 'Imported but unverified': 0, 'Pending human review': 4, 'AI-proposed data': 0, 'Explicitly synthetic test data': 6, 'Missing data': 81}; the new synthetic assumptions classify as {'ASMP-Z-001': 'Explicitly synthetic test data', 'ASMP-Z-002': 'Explicitly synthetic test data', 'ASMP-Z-003': 'Explicitly synthetic test data', 'ASMP-Z-004': 'Explicitly synthetic test data', 'ASMP-Z-005': 'Explicitly synthetic test data', 'ASMP-Z-006': 'Explicitly synthetic test data'}; fully verified = False.
* **Direct cost (7)**: application SAR 3,087,310.00 = independent SAR 3,087,310.00 for the priced lines (line differences: none); state `Preliminary — Incomplete`; unpriced resources ['SYN-C-045', 'SYN-C-046', 'SYN-C-047'] stay unpriced (never zero).

### Crew-size scenarios (stage 8) - same activities, norms and calendar; SYNTHETIC norms

| profile | archetype | head-count (own direct + indirect) | subcontract capacity | working days | calendar days | finish | peak direct workers | labour-hours | resource-limited activities | planning cost (synthetic role day-costs) |
|---|---|---|---|---|---|---|---|---|---|---|
| WP-SME | sme | 15 | 4 | 400 | 564 | 2028-09-20 | 8 | 10094.60 | A-EXC, A-FORM, A-REBAR, A-STEEL, A-SUPP, A-PUMP, A-PIPE100, A-PIPE50, A-WELD, A-ROAD, A-ELV | 433170.00 |
| WP-MID | mid | 24 | 6 | 212 | 302 | 2028-01-02 | 18 | 10094.60 | A-EXC, A-EXCH, A-REBAR, A-STEEL, A-PUMP, A-PIPE50, A-WELD, A-ROAD | 710840.00 |
| WP-LARGE | large | 48 | 8 | 170 | 242 | 2027-11-03 | 24 | 10094.60 | A-SHORE, A-REBAR, A-STEEL | 1000810.00 |
| WP-ENT | enterprise | 91 | 12 | 170 | 242 | 2027-11-03 | 27 | 10094.60 | A-STEEL | 1367130.00 |

Calendar used: {"start": "2027-03-07", "work_weekdays": [0, 1, 2, 3, 6], "holidays": ["2027-03-30"], "standard_hours": "8", "reduced_hours": [{"frm": "2027-04-04", "to": "2027-04-29", "hours": "6"}], "shutdowns": [{"frm": "2027-05-16", "to": "2027-05-18"}], "confirmed": false}. Scenario results compare workforce profiles on the same activities, calendar and norms. They are not an industry benchmark; a doubled workforce does not halve the programme because of dependencies, finite work fronts, shared equipment and rounding of crews.

* **Programme (9, MID profile, first provisional run)**: unconstrained longest activity 37 wd; dependency-constrained 174 wd; procurement-constrained 174 wd; resource-constrained 212 wd (302 calendar days, 2027-03-07 to 2028-01-02); critical path `A-MOB > A-EXC > A-FORM > A-POUR > A-SUPP > A-PIPE100 > A-WELD > A-HYDRO > A-COAT > A-COMM > A-DEMOB`; gaps reported: [['A-PUMP', 'LONG_LEAD_LATE'], ['A-EXC', 'NORM_EVIDENCE_SYNTHETIC'], ['A-EXCH', 'NORM_EVIDENCE_SYNTHETIC'], ['A-SHORE', 'NORM_EVIDENCE_SYNTHETIC'], ['A-FORM', 'NORM_EVIDENCE_SYNTHETIC'], ['A-REBAR', 'NORM_EVIDENCE_SYNTHETIC'], ['A-POUR', 'NORM_EVIDENCE_SYNTHETIC'], ['A-STEEL', 'NORM_EVIDENCE_SYNTHETIC'], ['A-SUPP', 'NORM_EVIDENCE_SYNTHETIC'], ['A-PUMP', 'NORM_EVIDENCE_SYNTHETIC'], ['A-PIPE100', 'NORM_EVIDENCE_SYNTHETIC'], ['A-PIPE50', 'NORM_EVIDENCE_SYNTHETIC'], ['A-WELD', 'NORM_EVIDENCE_SYNTHETIC'], ['A-NDT', 'MISSING_NORM'], ['A-BACK', 'NORM_EVIDENCE_SYNTHETIC'], ['A-ROAD', 'NORM_EVIDENCE_SYNTHETIC'], ['A-COAT', 'NORM_EVIDENCE_SYNTHETIC'], ['A-TRAY', 'NORM_EVIDENCE_SYNTHETIC'], ['A-CABLE', 'NORM_EVIDENCE_SYNTHETIC'], ['A-ELV', 'NORM_EVIDENCE_SYNTHETIC'], ['*', 'CALENDAR_UNCONFIRMED']]; claim: **PROVISIONAL - NOT FOR RELIANCE: 21 gap(s); provisional (unapproved norm/profile/calendar); synthetic test inputs**.

| activity | status | labour-hours | crew-days | unconstrained wd | start (wd index) | finish | resource delay | float | critical |
|---|---|---|---|---|---|---|---|---|---|
| A-MOB | OK | 0.00 | 0.00 | 5 | 0 | 0 | 0 | 0 | yes |
| A-EXC | OK | 255.00 | 14.17 | 8 | 0 | 15 | 0 | 0 | yes |
| A-EXCH | OK | 180.00 | 10.00 | 10 | 43 | 53 | 30 | 151 |  |
| A-SHORE | OK | 240.00 | 10.00 | 10 | 0 | 10 | 0 | 159 |  |
| A-FORM | OK | 615.00 | 20.50 | 11 | 15 | 28 | 2 | 0 | yes |
| A-REBAR | OK | 460.00 | 15.33 | 8 | 28 | 39 | 15 | 3 |  |
| A-POUR | OK | 192.00 | 4.00 | 11 | 39 | 50 | 15 | 0 | yes |
| A-STEEL | OK | 403.20 | 11.20 | 6 | 53 | 65 | 18 | 7 |  |
| A-SUPP | OK | 230.40 | 12.80 | 13 | 50 | 63 | 15 | 0 | yes |
| A-PUMP | OK | 96.00 | 4.00 | 4 | 119 | 123 | 18 | 16 |  |
| A-PIPE100 | OK | 2600.00 | 108.33 | 37 | 65 | 102 | 17 | 0 | yes |
| A-PIPE50 | OK | 775.00 | 32.29 | 17 | 102 | 119 | 54 | 20 |  |
| A-WELD | OK | 1920.00 | 106.67 | 36 | 119 | 158 | 34 | 0 | yes |
| A-NDT | MISSING_NORM | 0.00 | 0.00 | 0 | 158 | 158 | 37 | 0 |  |
| A-HYDRO | OK | 0.00 | 0.00 | 8 | 158 | 166 | 37 | 0 | yes |
| A-BACK | OK | 144.00 | 8.00 | 8 | 166 | 174 | 37 | 20 |  |
| A-ROAD | OK | 120.00 | 4.00 | 4 | 198 | 202 | 61 | 20 |  |
| A-COAT | OK | 760.00 | 31.67 | 32 | 166 | 198 | 37 | 0 | yes |
| A-TRAY | OK | 480.00 | 20.00 | 20 | 65 | 85 | 24 | 80 |  |
| A-CABLE | OK | 480.00 | 20.00 | 20 | 85 | 105 | 24 | 80 |  |
| A-ELV | OK | 144.00 | 12.00 | 12 | 85 | 97 | 24 | 88 |  |
| A-COMM | OK | 0.00 | 0.00 | 10 | 202 | 212 | 41 | 0 | yes |
| A-DEMOB | OK | 0.00 | 0.00 | 3 | 212 | 212 | 38 | 0 | yes |

* **Queries (10-12)**: {'technical': 7, 'boq_discrepancy': 1, 'missing_input': 1, 'supplier': 4, 'assumption_confirmation': 15, 'commercial': 1, 'design_interface': 1} draft queries created by detectors (28 detector keys), all `Draft`; before release a draft cannot be issued (NOT_RELEASED) and cannot be answered (NOT_ISSUED). 6 synthetic customer responses were entered by a TEST ACTOR and labelled synthetic. Recalculation after the answers: direct cost SAR 3,087,310.00 -> SAR 3,109,010.00; delta SAR 21,700.00 = independent SAR 21,700.00.

### Quotation levelling (stage 13) - SYNTHETIC suppliers, not live quotations

| supplier | headline total (application) | headline total (hand calculation) | evaluated total after approved delivery adjustment |
|---|---|---|---|
| A | 298,400.00 | 298,400.00 | 298,400.00 |
| B | 284,800.00 | 284,800.00 | 306,300.00 |
| C | 299,200.00 | 299,200.00 | 299,200.00 |

Headline lowest: **B**; evaluated winner after delivery and validity: **A**. Publishing rates before the selection was approved was refused (SELECTION_NOT_APPROVED); published rates start `Pending Review` and needed a second approval.

### Cost, commercial chain and independent reconciliation (stage 14, before the open items were resolved)

| application total | SAR |
|---|---|
| direct_cost | 3,414,410.00 |
| indirect_cost | 332,296.90 |
| total_cost | 3,896,575.18 |
| selling_price_pre_tax | 4,208,358.62 |
| commercial_net_price | 4,208,301.19 |
| tax | 631,253.79 |
| final_payable | 4,839,612.41 |


| independent (separate formulas) | SAR (ratios unitless) |
|---|---|
| indirect | 332,296.90 |
| contingency | 149,868.28 |
| total_cost | 3,896,575.18 |
| net | 4,208,301.19 |
| schedule_total | 4,208,358.62 |
| vat | 631,253.79 |
| payable | 4,839,612.41 |
| schedule_vs_net_variance | 57.43 |
| markup_on_cost | 0.080000 |
| margin_on_price | 0.074074 |
| max_rounding_variance_allowed | 319.15 |

Findings raised at that point (all expected): [['Critical', 'EXCLUSION_UNAPPROVED'], ['High', 'BOQ_NEEDS_REVIEW'], ['High', 'INDIRECT_BASE_OVERLAP'], ['High', 'LONG_LEAD_AT_RISK'], ['High', 'PLANT_HIRE_DAYS'], ['High', 'SYSTEM_EXCEPTION'], ['High', 'TIMEPHASING_INCOMPLETE'], ['Low', 'SYNTHETIC_DEMO'], ['Medium', 'INDIRECT_ELIGIBILITY_UNSPECIFIED'], ['Medium', 'OFFER_MISSING'], ['Medium', 'POSSIBLE_DUPLICATE_ITEM'], ['Medium', 'UNAPPROVED_ADOPTED_ASSUMPTION']]. Escalation then read: *INCOMPLETE - NOT FOR RELIANCE: SAR 568,080.00 of eligible cost has no time allocation and is NOT escalated (see unescalated_lines)*. Tax is charged on the **tendered pricing schedule** (sum of printed line amounts), which differs from the commercial net price by the unit-rate rounding variance reported above (existing limitation O-9, now measured and bounded).

### Cost with no time allocation (stage 21)

| step | result |
|---|---|
| before any rule | INCOMPLETE - NOT FOR RELIANCE: SAR 568,080.00 of direct cost is allocated to no period (see unallocated_lines); SAR 700,165.40 of the price is not valued and the closing balance excludes it |
| financing proposal | refused: TIMEPHASING_INCOMPLETE |
| final gate | blocked by TIMEPHASING_INCOMPLETE: True |
| after first rule batch | INCOMPLETE - NOT FOR RELIANCE: SAR 211,380.00 of direct cost is allocated to no period (see unallocated_lines); SAR 260,528.38 of the price is not valued and the closing balance excludes it |
| still untied (exact lines) | [['C-011', '33280.00'], ['C-024', '31800.00'], ['C-055', '43500.00'], ['C-056', '35600.00'], ['C-071', '50400.00'], ['C-072', '16800.00']] |
| after second batch | COMPLETE; reconciliation checks ok: True; escalation complete: True |

Programme baseline approved after the calendar was confirmed, the missing NDT norm approved and the order date moved: 231 wd / 327 calendar days, finish 2028-01-27; claim **PROVISIONAL - NOT FOR RELIANCE: synthetic test inputs**. Exceptions accepted by the (test) Commercial Approver: [['PLANT_HIRE_DAYS', 'SYN-C-050']]; Critical findings open: []; final gate blocked: False; estimate state `Complete`.

| frozen-candidate total after resolution | SAR |
|---|---|
| direct_cost | 3,452,410.00 |
| indirect_cost | 292,543.90 |
| total_cost | 3,894,752.06 |
| selling_price_pre_tax | 4,206,320.69 |
| commercial_net_price | 4,206,332.22 |
| tax | 630,948.10 |
| final_payable | 4,837,268.79 |


## 4. Documents
* Applicability matrix (stage 16): {'Required': 41, 'Conditional': 2, 'Not Applicable': 1, 'Missing Customer Requirement': 1} (see `docs/TENDER_DOCUMENT_APPLICABILITY_MATRIX.md`).
* First pack (revision 1, before resolution): statuses {'BLOCKED': 4, 'Not Applicable': 1, 'Preliminary (DEMONSTRATION)': 40}; **blocked**: {'D06': 'letter of offer', 'D13': 'no approved payment terms (contract payment / retention / bond terms) have been supplied', 'D14': 'letter of offer validity', 'D30': 'shop drawing submittals'}; 116 files; validator: True (warnings: 6).
* Final demonstration pack (revision 2): classification **demonstration**; banner: `DEMONSTRATION EXPORT - NOT SUBMISSION READY - NOT APPROVED FOR ANY REAL TENDER | approvals by: test principals in environment 'test'`; blocked in rev 1 ['D06', 'D13', 'D14', 'D30'] -> now []; statuses {'Not Applicable': 1, 'Preliminary (DEMONSTRATION)': 44}; validation ok=True over 116 files (warnings: ["D23: contains 'TO BE COMPLETED' placeholders", "D27: contains 'TO BE COMPLETED' placeholders", "D28: contains 'TO BE COMPLETED' placeholders", "D29: contains 'TO BE COMPLETED' placeholders", "D30: contains 'TO BE COMPLETED' placeholders", "D31: contains 'TO BE COMPLETED' placeholders"]). Exports: [{'readiness': 'demonstration', 'submission_ready': 0, 'n': 4}]; files ['OFR-PRJ-9101-01.docx', 'estimate_report_PRJ-9101_DEMONSTRATION.docx', 'pricing_schedule_PRJ-9101_DEMONSTRATION.xlsx', 'reconciliation_report_PRJ-9101_run11.xlsx'].
* Hypothetical post-award handover (revision 1): 17 documents H01-H17; refused before an award scenario was recorded: `AWARD_NOT_SELECTED`; banner `HYPOTHETICAL POST-AWARD HANDOVER - SIMULATION ONLY - NO AWARD HAS BEEN MADE | DEMONSTRATION EXPORT - NOT SUBMISSION READ...`; validation ok=True (49 files).

## 5. Controls that were attacked
**Production readiness (stage 19)**

| attempt | result |
|---|---|
| approve_version | NON_HUMAN_ACTOR |
| approve_tender_export | NON_HUMAN_ACTOR |
| export_submission | NON_HUMAN_ACTOR |
| approve_document | NON_HUMAN_ACTOR |
| export_submission_without_export_approval (demo project) | EXPORT_NOT_APPROVED |
| classification of the demonstration project | demonstration |
| classification even if the environment were production | demonstration |
| exports marked submission-ready | 0 |

Resolved actor types: {'forged_display_name': 'unregistered', 'role_mismatch': 'role_mismatch', 'registered_test_actor': 'test', 'unregistered': 'unregistered'}. Structural reasons: ['the project is flagged as a demonstration project', 'synthetic data is used in the estimate'].

**Assumption / identity bypass attempts (stage 20)**

| attempt | result |
|---|---|
| author_self_approval | SELF_APPROVAL_BLOCKED |
| administrator_self_approval | SELF_APPROVAL_BLOCKED |
| viewer_approval | PERMISSION_DENIED |
| ai_approval | AI_CANNOT_APPROVE |
| ai_creates_register_row | AI_FORBIDDEN |
| manual_entry_is_not_approval | Pending Review |
| approved_by_a_second_person | test-commercial |
| sql_update_of_approved_value | IntegrityError: IMMUTABLE_RECORD: approved assumption versions cannot be changed; create a new version |
| sql_delete_of_approved | IntegrityError: IMMUTABLE_RECORD: approved assumption versions cannot be deleted |
| sql_replace_provenance | IntegrityError: IMMUTABLE_RECORD: approved assumption versions cannot be changed; create a new version |
| sql_make_synthetic_look_real | IntegrityError: IMMUTABLE_RECORD: approved assumption versions cannot be changed; create a new version |
| forged_identity_recorded_as | {'reviewer': 'forged-commercial', 'actor_type': 'unregistered', 'environment': 'test'} |
| forged_approval_counts_for_production | False |
| REST: create | 200 |
| REST: estimator_cannot_approve | [409, 'SELF_APPROVAL_BLOCKED'] |
| REST: body_field_cannot_forge_identity | [409, 'SELF_APPROVAL_BLOCKED'] |
| REST: viewer_cannot_approve | [403, 'PERMISSION_DENIED'] |
| REST: viewer_cannot_create | [403, 'PERMISSION_DENIED'] |
| REST: commercial_approves | 200 |
| REST: no_token | 401 |
| CLI: python -m app.cli action approve_assumption {"id": "ASMP-Z-090"} | exit 1: ERROR [PERMISSION_DENIED]: Role 'Viewer' may not 'approve' assumption. Allowed: Administrator, Commercial Appr |
| CLI: python -m app.cli action approve_assumption {"id": "ASMP-Z-090"} | exit 1: ERROR [AUTH_REQUIRED]: Invalid username or password. |


## 6. Freeze, library change, replay, interfaces
* Manifest: 165 files with SHA-256; tender manifest `16d13fa2d7ff910a...`, handover manifest `8083e5db19d81225...`.
* After the freeze a global rate (+25 %, new approved version) and a global assumption (new approved version) were changed: the **live** payable moved SAR 4,837,268.79 -> SAR 4,897,593.46; the **frozen** payable stayed SAR 4,837,268.79; replay ok = True; document figures in the regenerated pack differ from the previous pack in: nothing.
* Replay (26): ok = True, fingerprint `48d0f9242dc910b7...`, documents agree with frozen totals = True.
* UI/API/CLI (27): {'crew_working_days': True, 'applicability_counts': True, 'query_status_counts': True, 'assumption_classes': True, 'estimate_totals_api_vs_engine': True}; UI pages 11 all HTTP 200 without a traceback; CLI exits {'crew': 0, 'applic': 0, 'queries': 0, 'evidence': 0}.

## 7. Honest limits of this evidence
* The synthetic norms, crews, calendars, rates and quotations were written by the scenario author; agreement between the application and the oracle proves the **arithmetic and the controls**, not any real-world productivity, price or duration.
* The oracle (`tests/closure/oracle.py`) re-implements the calculations with fractions, a recursive CPM and a plain calendar loop; it shares the author and the fixtures with the application, so it is independent code, not independent judgement.
* Tax uses the seeded synthetic parameter; no tax professional verified it. Saudi labour, calendar and SBC references are in the source register as *partially verified* or *requires human acquisition*; no clause is claimed.
* The scenario runs with `KSA_ENVIRONMENT=test`; the production path (registered human approvers, production environment) is exercised separately in `tests/approvals/test_actor_isolation.py` and `tests/closure/test_production_pack_gate.py`.
