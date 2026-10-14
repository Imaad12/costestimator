# End-to-end closure plan and requirements matrix

Mission: close the loop from a customer enquiry to a tender pack, internal approvals, a submission-readiness assessment and a (simulated) handover package, inside the existing architecture.
Baseline verified at the start of this iteration (not assumed): branch `claude/wizardly-einstein-w4ykwd`, HEAD `50e17f2`, clean working tree, **385 tests passed** (`python -m pytest -o addopts="" -q`, 186 s),
migrations 0001-0014. Nothing in `main`, `projects/*` or `var/` was touched; every run used a scratch database.

## 1. Inventory before coding (what existed, what was only described)

| Area | Existing and working | Partial / disconnected | Missing |
|---|---|---|---|
| Estimate chain, frozen replay, reconciliation, readiness gate, actor types | yes (iterations 1-5, pilot) | | |
| Programme | CPM with human durations, calendar (weekdays + holidays), loading, man-hours | duration was a typed number, no norm, no crew, no resource limit | productivity engine, workforce profiles, reduced hours, shutdowns, scenarios |
| Assumptions | versioned library, project overrides, approval workflow | no category/origin/impact fields, no DB-level immutability, self-approval **allowed by default**, no create path via UI/API/CLI | governance fields, guards, four-eyes default, evidence classification |
| Clarifications / scope / risk registers | clarification, scope and risk tables | no technical-query register, no detectors, no document register | RFI/query registers, document register, enquiry, generic registers |
| Documents | letter of offer, BOE, estimate/reconciliation reports, workbooks, RFQ files | no pack, no manifest, no applicability, no PDF | 45-document pack, 17 handover documents, validator |
| Standards | none | | source register with verification status |
| Synthetic pilot | 30-line piping package, all stages PASS | piping only | multi-discipline tender scenario |

## 2. Requirements matrix

Result key: **PASS** = implemented and the cited test/stage passed in the final run; **PARTIAL** = implemented with the stated limit; **NOT DONE** = not implemented (reason given).

| ID | Capability | Existing implementation | Missing work | Dependencies | Implementation location | Acceptance test | Result and evidence |
|---|---|---|---|---|---|---|---|
| R-01 | Verify baseline | HEAD 50e17f2, 385 tests | - | - | - | full suite + `scripts/run_synthetic_pilot.py` | PASS: 385 passed before changes; pilot rerun at the end (see report) |
| R-02 | Standards and evidence register | none | register, verification states, acquisition list, manual import | web research (blocked pages recorded) | `app/services/standards.py`, `data/standards/standards_register.json`, CLI `standards`, migration 0015 | `test_security_backup_migration_standards.py::test_standards_register_rules` | PARTIAL: 12 sources, **2 verified, 4 partially verified, 6 need human acquisition**; SBC and procurement-law pages could not be read |
| R-03 | AACE vs internal levels | capability matrix levels 1-5 | wording | - | `docs/WORKFORCE_PRODUCTIVITY_AND_PROGRAMME_METHOD.md` section 7, `docs/STANDARDS_AND_EVIDENCE_REGISTER.md` | doc review | PASS: internal levels stated as not AACE/owner classes; only PGD 01 pointers recorded, no accuracy ranges |
| R-04 | Workforce archetypes (4-15 / 15-25 / 26-50 / 51+) | none | editable, versioned, labelled planning assumptions | R-07 | `workforce_profiles`, `services/workforce.py::create_profile` | `test_workforce_service.py::test_profile_band_and_approval`; scenario stage 8 | PASS: bands refused outside range; label stored; approval by another person |
| R-05 | Role split, indirect, shifts, overtime, attendance, fronts, mobilisation, subcontract capacity | none | profile fields, pool semantics | R-04 | `productivity.Profile`, `usable_pool` | `test_productivity_engine.py` (pool, attendance, overtime, shift, equipment) | PASS |
| R-06 | Work calendar (weekends, holidays, hours, reduced windows, shutdowns, overrides, visible) | calendar kind (weekdays, holidays) | hours, reduced windows, shutdowns, confirmation flag, visibility | - | `param_kinds._calendar`, `productivity.WorkCalendar`, D19 | `test_negative_controls.py::test_invalid_calendar...`, engine reduced-hours test, scenario stage 9/21 | PASS: project calendars never modify a global; unconfirmed calendar = provisional; no Saudi default is shipped (**by design**) |
| R-07 | Deterministic productivity engine | none | labour-hours and crew-output bases, factors, double-count guard, fronts, fixed days, dependencies, procurement, resources | R-05, R-06 | `app/estimators/productivity.py` | 15 unit tests + oracle (`test_programme_matches_independent_oracle`) | PASS: hand-computed expectations; oracle agrees on hours, crew-days, durations, CPM, critical path, calendar dates |
| R-08 | Five durations kept apart; forecast vs baseline | | | R-07 | `productivity.run`, `workforce.forecast_vs_baseline`, `programme_baselines` | engine reforecast test; service test | PASS |
| R-09 | Productivity governance (states, provenance, immutability) | | | - | `productivity_norms`, triggers, `workforce.*_norm` | `test_workforce_service.py::test_norm_lifecycle...`, `::test_norm_needs_source...` | PASS: 7 states, 4-eyes, immutable approved rows, synthetic never `verified` |
| R-10 | Workforce scenario engine and report | | | R-07 | `workforce.crew_scenarios`, report `crew_scenarios`, D20 | `test_crew_scenarios_use_constraints_not_headcount_division` | PASS on **synthetic norms**; large = enterprise (crane/dependency bound); not a benchmark |
| R-11 | Assumptions audit | | | - | `docs/ASSUMPTIONS_GOVERNANCE_AND_SECURITY_AUDIT.md` | 15 questions answered with code/test evidence | PASS; one finding fixed (self-approval default), one documented (CLI user reset was unaudited -> now audited) |
| R-12 | Unified register (categories, origin, impact, uncertainty, consequence...) | partial | 17 categories, data classes, history, evidence report | - | `services/assumptions.py`, migration 0015 | `test_assumptions_governance.py` (9 tests) | PASS |
| R-13 | Secure workflow, immutability, project override, audit | partial | DB guards, four-eyes default, Administrator non-exemption | - | triggers, `policy.SEPARATION_ENTITIES`, `config.py`, `settings.toml` | governance tests + scenario stage 20 | PASS (tamper-**evident** only; DB-file owner can drop triggers) |
| R-14 | Frozen replay from captured versions after global change | yes | tested with closure inputs | - | `snapshots.py` | scenario stages 25-26 | PASS: live payable moved, frozen unchanged, regenerated documents carry the same figures |
| R-15 | Stage A: enquiry, brief, acknowledgement, bid/no-bid, checklist, responsibilities | none | enquiry table, generic registers | - | `services/tender.py`, `tender_enquiries`, `tender_register_items` | scenario stages 1-3 | PARTIAL: enquiry, bid/no-bid, required-input and responsibility registers exist; the acknowledgement is text in the evidence, not a generated letter |
| R-16 | Stage B: document intake with revisions, no interpretation claim | none | register, supersession, content status | - | `tender_documents` | `test_tender_services.py` (register, conflicts, content status) | PASS |
| R-17 | Stage C: BOQ import, mapping, validation | yes | duplicate/revision conflicts surfaced as queries | - | `imports/boq.py` + detectors | scenario stages 4-7 | PASS (manual take-off only; no drawing extraction) |
| R-18 | Stage D: query/RFI registers (8 linked registers), draft-only, no fabricated answers | clarifications only | detectors, workflow, impact, audit | R-16 | `tender_queries`, `generate_draft_queries` | `test_tender_services.py` (detectors, workflow gates); scenario 10-12 | PASS: 9 detector families; drafts only; responses entered by a person and labelled synthetic |
| R-19 | Stage E: methodology and programme from norms/calendars/resources | | | R-07 | D18, D19, D20, D37 | scenario 8, 9, 15 | PASS (content entered by a person; the system assembles, it does not author engineering) |
| R-20 | Stage F: quality/HSE/compliance registers | none | registers, skeleton generators with explicit placeholders | - | `skeleton_registers`, D23, D24, D27-D31 | scenario 15; validator warns on placeholders | PARTIAL: structures and skeletons only; **no inspection criteria, HSE controls or compliance statements are generated** |
| R-21 | Stage G: procurement, quote levelling, long lead | yes | pack documents | - | D22, D36 | scenario 13 | PASS: non-obvious winner after delivery/validity |
| R-22 | Stage H: reconciliation of cost, risk, escalation, cash flow, plant, tax | yes + iteration 5 | untied costs, plant window, quantised reports | - | existing + `quantise_tree` | scenario 14, 21; oracle tests | PASS: independent chain agrees; 28-digit residue removed from reports |
| R-23 | Stage I: 45-document pack, applicability, DOCX/XLSX/PDF, manifest | none | catalogue, builders, renderers, manifest | R-26 | `app/tender/` | scenario 16-18, 22; `test_every_generated_file_opens...` | PASS (see report); **placeholders remain in 6 documents by design** |
| R-24 | Stage J: human approvals and final gate extended | readiness gate | open queries, missing documents, synthetic assumptions, baseline, norms, document approvals | - | `readiness._closure_gate`, `packs.approve_document` | `test_stage_j_gate_reasons`, `test_production_pack_gate.py` | PASS |
| R-25 | Stage K: handover pack (hypothetical) | none | 17 documents, award guard | - | `tender/handover.py` | scenario 23; `test_handover_pack_is_labelled_hypothetical...` | PASS: refuses without an explicit `award_scenario = hypothetical` |
| R-26 | Single-source document architecture, versioned templates, manifest, deterministic regeneration | | | - | `tender/model.py`, `packs.py` | determinism test (byte-identical per format); manifest checks | PASS |
| R-27 | Pack validator | | | R-26 | `packs.validate_pack` | `test_validator_detects_tampering...`, `test_validator_flags_a_missing_required_document`, unsupported-claim test | PASS: checksum, genuine-format, placeholder, stale-reference, arithmetic, consistency, banned-claim checks |
| R-28 | Self-running scenario through real services, CLI, API | pilot (piping) | 27-stage multi-discipline scenario | all | `tests/closure/scenario.py`, `scripts/run_closure_scenario.py` | all 27 stages | PASS (see report) |
| R-29 | Independent oracle | | | - | `tests/closure/oracle.py` | oracle tests | PASS (independent code, same author) |
| R-30 | Negative tests | partial | the brief's list | - | `tests/closure/test_negative_controls.py` + stages 19-20 | see section 3 | PASS |
| R-31 | Security review, backup/restore/migration tests, hardening backlog | iteration 5 | closure tables in backups, migration test, audit doc | - | `backup.py`, tests | `test_backup_restore_preserves...`, `test_migration_0015...` | PARTIAL: no MFA/SSO/immutable audit storage - backlog in the audit |
| R-32 | Outputs and machine-readable results | | | - | `demo_output/synthetic_closure/` | `MANIFEST.json`, `acceptance_results.json` | PASS |
| R-33 | Capability matrix updated from tested evidence | yes | new records | - | `docs/capability_matrix.json` | `tests/unit/test_capability_matrix.py` | PASS |

## 3. Negative-test coverage (brief section 9)

| Case | Where proved |
|---|---|
| Missing rates | scenario stage 7 (three unpriced resources stay unpriced), `needs` -> RFQ -> levelling |
| Invalid units | `test_negative_controls.py::test_invalid_unit_between_norm_and_boq...`; BOQ unit statuses |
| Unapproved assumptions | `test_unapproved_adopted_assumptions_surface_as_findings_not_silence`; data classes |
| Conflicting revisions | `test_revision_conflict_is_detected_between_boq_and_register`; stage 10 |
| Duplicate / unmapped BOQ items | stages 4-5, 10, 21 (duplicate `C-071#2` flagged, queried, excluded with an approved exclusion) |
| Unresolved technical queries, missing required documents | `test_stage_j_gate_reasons`, `test_validator_flags_a_missing_required_document`, stage 10-12 |
| Invalid or incomplete programme | engine gap tests, `test_programme_without_confirmed_calendar_or_profile...`, baseline gate |
| Invalid tax inputs | `test_invalid_tax_and_commercial_inputs_are_refused_or_block` |
| Unallocated costs | stage 21 (exact amounts before/after each rule batch), `test_time_allocation_before_after_exact_amounts` |
| Plant-hire mismatch | stage 14/21 + `test_plant_hire_window_matches_independent_count` (plus iteration-5 tests) |
| Forged actor names, role mismatch | stage 19-20, `tests/approvals/test_actor_isolation.py` |
| Test actor on a production project | stage 19, `test_test_actor_cannot_approve_documents_on_a_real_project_in_production` |
| Attempted self-approval | stage 20, governance tests, REST four-eyes test |
| Direct API / CLI gate bypass | stage 20 and 27, `test_closure_api_actions_enforce_roles_and_four_eyes`, `test_actor_isolation_api.py` |
| Modified approved assumptions | six SQL attempts refused (`test_approved_versions_are_immutable...`), stage 20 |
| Library changed after freeze | stage 25 |
| Synthetic data labelled production-ready | `test_synthetic_data_on_a_real_project_is_never_production_ready_even_with_humans`, stage 19 |

## 4. Order of execution actually followed

1. verify baseline; 2. read the pilot, audit, security, limitations documents; 3. standards research (agent, read-only) and register; 4. migration 0015; 5. assumptions governance;
6. productivity/workforce engine and service with hand-computed tests; 7. tender registers and detectors; 8. documents (model, catalogue, builders, validator, handover); 9. scenario and oracle;
10. negative tests; 11. full suite and scenario rerun from a fresh directory; 12. documents regenerated from evidence; 13. commit on the feature branch (no merge, no PR).
