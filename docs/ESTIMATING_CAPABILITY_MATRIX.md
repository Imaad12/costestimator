# Estimating capability matrix (five-level audit)

Audit date: 2026-10-13, repository state `ab05e06` plus the fixes listed in §6. Scope: what a cost-estimation engineer in Saudi Arabia can actually do with this application today, from basic building estimates to major industrial/EPC estimates.
**Method rule:** a feature counts only if code exists, a test exercises the behaviour, and (where possible) it was run. Templates, UI screens, documentation, assumption definitions, cost codes and skills are *not* evidence of capability.
The machine-readable source is [`capability_matrix.json`](capability_matrix.json); this page's tables are rendered from it (`python scripts/gen_capability_matrix.py`) and `tests/unit/test_capability_matrix.py` verifies that every code path, symbol and test it cites exists and that status claims are consistent with their evidence.

## 1. Bottom line
* **A generic building/MEP estimate (Levels 5–4)** can be produced end-to-end *structurally*: human-measured BOQ → mapping → assembly/rate pricing → indirects → commercial chain → reconciliation → approvals → gated export. The engine is well tested. **But the content that makes an estimate real is absent**: the library has **0 approved real Saudi rates** and **no productivity/consumption data**; every real estimate is Preliminary until a human loads and approves that data (LIB-07, LIB-08).
* **Infrastructure/large-project estimating (Level 3)** lacks landed-cost build-up, resource loading/man-hour histograms, cash flow, quantified risk, a Basis-of-Estimate document and estimate classification.
* **Comprehensive industrial estimating (Levels 2–1, incl. Aramco-type work)** is **not supported**: no industrial units (inch-diameter, joints, loops, MVA), no piping/instrument/tank/shutdown/modularisation models, no methodology-driven man-hours, no engineering/home-office model, no probabilistic risk, no client compliance profiles, no controlled client requirements. **No Saudi Aramco compliance is claimed or implied**; no Aramco controlled document is in the repository.
* Governance is the strongest part: server-side approvals, AI/automation boundaries, audit chain, input snapshots, fingerprinted gates and no autonomous submission are implemented and tested.

### Roll-up by capability level (engine capabilities; data readiness reported separately)
<!-- ROLLUP_BEGIN -->
| Level | Name | Required capabilities (engine) | IT | IU | PA | MI | Verdict (engine) |
|---|---|---|---|---|---|---|---|
| 5 | Basic estimating | 37 | 33 | 1 | 3 | 0 | **CONDITIONALLY SUPPORTED (partial / unverified items)** |
| 4 | Building and MEP contractor estimating | 76 | 54 | 2 | 20 | 0 | **CONDITIONALLY SUPPORTED (partial / unverified items)** |
| 3 | Infrastructure and large-project estimating | 99 | 56 | 3 | 29 | 11 | **NOT SUPPORTED (missing capabilities)** |
| 2 | Industrial / process-plant estimating | 120 | 56 | 3 | 40 | 21 | **NOT SUPPORTED (missing capabilities)** |
| 1 | Major industrial / EPC estimating (Aramco-type) | 129 | 56 | 3 | 42 | 28 | **NOT SUPPORTED (missing capabilities)** |

Data readiness (applies to every level): LIB-07 evidence-backed Saudi rate library (material, labour, plant, equipment, subcontract) - **Missing**; LIB-08 productivity/consumption/wastage factors and crew data approved by humans - **Missing**.

All 131 capability records: Implemented and tested 56, Implemented but unverified 3, Partial 42, Missing 30, Not Applicable 0.
<!-- ROLLUP_END -->

Reading the table: a capability needed from level *N* is needed at *N* and at every more demanding level (numerically lower). **IT** Implemented and tested · **IU** Implemented but unverified · **PA** Partial · **MI** Missing.
"Supported" means every required engine capability is *Implemented and tested*; one Partial/Unverified item makes it *Conditionally supported*; one Missing item makes it *Not supported*. This verdict is about the software, not about an estimate's accuracy.

### By area
<!-- AREAS_BEGIN -->
| Area | Records | IT | IU | PA | MI |
|---|---|---|---|---|---|
| A. Scope intake: BOQ, units, quantities, mapping, documents | 11 | 8 | 1 | 1 | 1 |
| B. Classification and libraries: CBS/WBS, catalogues, assemblies, data readiness | 9 | 3 | 0 | 3 | 3 |
| C. Building, civil, infrastructure and MEP disciplines | 11 | 0 | 0 | 11 | 0 |
| D. Industrial, oil and gas, process plant | 14 | 0 | 0 | 8 | 6 |
| E. Rates: material, labour, plant, equipment, subcontract; productivity and methodology | 18 | 13 | 1 | 0 | 4 |
| F. Engineering services, field indirects, home office, temporary facilities | 5 | 1 | 0 | 4 | 0 |
| G. Taxes, duties, logistics | 4 | 1 | 0 | 1 | 2 |
| H. Project duration, sequencing and resource loading | 5 | 2 | 0 | 1 | 2 |
| I. Basis of Estimate, scope definition, maturity and exclusions | 5 | 2 | 0 | 2 | 1 |
| J. Escalation, contingency, quantified risk, uncertainty, currency | 8 | 4 | 0 | 2 | 2 |
| K. Supplier quotations, bid levelling and procurement | 7 | 5 | 0 | 2 | 0 |
| L. Cost control: CBS roll-ups, benchmarks, cash flow, forecasts, change orders, revisions | 7 | 2 | 0 | 2 | 3 |
| M. Commissioning, start-up, handover, close-out | 3 | 0 | 0 | 2 | 1 |
| N. Saudi-specific requirements and configurable client compliance profiles | 7 | 2 | 0 | 1 | 4 |
| O. Approval gates, audit, snapshots, reproducibility, commercial exports | 12 | 10 | 0 | 2 | 0 |
| P. Excel and document outputs | 5 | 3 | 1 | 0 | 1 |
<!-- AREAS_END -->

## 2. Two independent classification systems (never conflate them)
### 2.1 Internal Capability Levels 1–5 (this product's own yardstick)
Defined in `capability_matrix.json` (`levels`) and used only to ask "which estimating work can this software support?". They are not official Saudi Aramco levels, not AACE classes and not any client's categories.

| Level | Name | Scope |
|---|---|---|
| 5 | Basic estimating | Small building, fit-out, repair or maintenance works priced from a human-measured BOQ with approved assemblies/rates, one site, SAR, one commercial policy, VAT |
| 4 | Building and MEP contractor estimating | Multi-discipline building projects with subcontract packages, RFQ/bid levelling, preliminaries by duration, reconciliation, formal approvals |
| 3 | Infrastructure and large-project estimating | Level 4 plus infrastructure/utilities, imports and currency, customs/logistics, phasing and resource loading, Basis of Estimate, classification, escalation and quantified risk, cash flow |
| 2 | Industrial / process-plant estimating | Level 3 plus piping, equipment, instrumentation, industrial E&I, steel, tanks, coatings, insulation, man-hour/methodology estimating, remote site, commissioning/start-up, classification, client compliance |
| 1 | Major industrial / EPC estimating (Aramco-type) | Level 2 plus engineering services/home office, modularisation, shutdown/turnaround, probabilistic risk, forecasting/change control, owner-controlled requirements via compliance profiles |

Each capability record carries `required_from` (the least demanding level at which it becomes necessary). The assignment is this audit's engineering judgement and is open to challenge; changing it is a one-line edit in the JSON.

### 2.2 Estimate classification: AACE classes and client-specific systems
**Status in the application: not implemented (BOE-04 Missing).** There is no class field, no per-class deliverable/maturity checklist and no accuracy-range output. `ASMP-A-001` (design stage) and `ASMP-L-004` (design maturity) are free-form assumption *definitions* that nothing reads.

Reference summary (from the publicly known structure of AACE International Recommended Practice 17R-97 and the process-industry guideline 18R-97; **the RPs are copyright documents that are not in this repository — verify every figure against the licensed text before using it, and other AACE RPs, e.g. for building or infrastructure, use different ranges**):
* Five classes, **Class 5 = least project definition (concept screening) … Class 1 = most (check/bid estimate)**. Primary characteristic is the *level of project definition* (order of 0–2 % for Class 5 rising to roughly 50/65–100 % for Class 1); secondary characteristics are end use, methodology and an *expected accuracy range* (wider for lower definition). Typical methodologies run from capacity-factored/parametric (Class 5/4) to detailed unit-cost with detailed take-off (Class 2/1).
* **AACE numbering runs the opposite way to our internal levels** (our Level 1 is the most demanding capability; AACE Class 1 is the best-defined estimate). Do not map them one-to-one: a Level-2 *software capability* can produce estimates of several AACE classes depending on project definition.
* **Client-specific classifications** (an owner's capital-project stage gates, estimate phases, accuracy bands, mandatory estimate templates) come from that owner's controlled documents. None are in the repository, none are configured, and none are assumed.

Planned configuration design (see roadmap, ESTIMATING_GAP_ROADMAP.md item G-07): `config/classification_profiles/<profile-id>.json`, selected per project, each with `issuing_body`, `document_reference` + `revision` (mandatory, supplied by an authorised user from the controlled document), `classes[]` with `code`, `label`, `definition_range`, `required_deliverables[]`, `required_checks[]`, `expected_accuracy_low/high` (user-supplied, never defaulted), and rules that block approval when mandatory criteria are unmet. AACE and a client profile would be two *independent* profiles; a project may select both. Until that exists the application must not display any estimate class or accuracy range.

## 3. Evidence method and probes run during this audit
1. Read `CLAUDE.md`, `docs/DEVELOPMENT_AUDIT.md`, `NEXT_STEPS.md`, `ARCHITECTURE.md`, `DATA_MODEL.md`, `PROJECT_WORKSPACES.md`, `RATE_UPDATE_WORKFLOW.md` and the skills; then read the engines (`app/estimators/*`), services, importers, procurement, reconciliation, exports and the 210 pre-audit tests (230 after the audit additions) (listed by function).
2. Keyword probes over code, configuration and seed data for every capability named in the brief (WBS, class/maturity, Basis of Estimate, Aramco/SAES/SAMSS, Saudization/levy, local content/IKTVA, customs/duty, withholding/zakat, cash flow, Monte Carlo/P50, resource loading, variation/change order, forecasting/EVM, client profile, retention/bond, pre-commissioning, weld/inch-diameter, spares). Hits in `data/assumptions/assumptions_register.csv` are **definitions that no engine consumes** and were classified accordingly.
3. Catalogue probe: 927 resource definitions searched for ~45 industrial terms (see LIB-04): piping/valves/vessels/transformers/switchgear/coatings/insulation/scaffold/cranes exist at building scale; transmitters, DCS/PLC/SCADA, NDT/radiography, cathodic protection, boilers, turbines, manifolds, refractory, shutdown, hot work: none.
4. Runtime probes (synthetic data, scratch databases):
   * BOQ with industrial units — `inch-dia`, `joint`, `spool`, `loop`, `MVA`, `m3/h` all imported as **unknown unit (needs review)**; `ton` ambiguous; `MT`, `m2`, `LS` fine → SCO-04 Missing.
   * Scale — 2,000 / 20,000 BOQ items: import 0.2 / 1.1 s, mapping 0.3 / 3.1 s, estimate 0.3 / **13.8 s (before fix)** → 2.7 s after fix, freeze+snapshot 18.7 → 4.6 s, master workbook 7.5 / 62 s.
   * Non-SAR project currency — a SAR rate in a USD project is unpriced (`FX_MISSING`) until an approved SAR→USD rate exists, then converts → CUR-02.
   * PDF/DOCX/XLSX extraction with real files, schedule-task and duration path, API reachability, archived-project protection, standard-indirects action, what-if numbers.
5. Test review: for every record the cited tests are marked **yes** (verifies the required behaviour), **partly** (touches it) or **no**. Records are `Implemented and tested` only with at least one *yes* test.

## 4. Generic construction estimate vs comprehensive industrial estimate
| Question | Generic building/MEP estimate | Major industrial/EPC estimate |
|---|---|---|
| Quantity source | human-measured BOQ (supported) | MTOs by discipline (piping spools, cable schedules, instrument index) — import of these structures is **not supported**; units missing (SCO-04) |
| Pricing basis | assemblies × approved rates (supported) | man-hours by craft from approved factors, method-driven (EST-10/11/12 **Missing**) |
| Indirects | duration-based field indirects (supported) | + home office, engineering, camp/logistics, cost-loaded programme (ENG-01/02, PRC-14, DUR-04/05 **Missing/Partial**) |
| Commercials | markup/margin, contingency, escalation %, VAT (supported) | + quantified risk, time-phased escalation, currency exposure, landed cost, financing/retention (RSK-04/05, CUR-03, TAX-02, CLO-03 **Missing**) |
| Basis of Estimate / class | estimate report summary only (BOE-03 Partial) | formal BoE, class, accuracy, owner templates (BOE-04, SAU-06 **Missing**) |
| Governance | approvals, audit, snapshots, gates (supported) | + client-controlled forms, change control, forecasting (CTL-05/06, SAU-07 **Missing**) |

## 5. Capability records
Statuses: **Implemented and tested**, **Implemented but unverified**, **Partial**, **Missing**, **Not Applicable** (none currently assigned). Every record states code location, tests and whether they truly test the behaviour, workflow/output, levels, limitations/dependencies and the **acceptance test required to mark it complete**.

<!-- DETAIL_BEGIN -->
### A. Scope intake: BOQ, units, quantities, mapping, documents

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| SCO-01 | BOQ/takeoff import from CSV/XLSX with header detection, column mapping, Arabic headers, stored original | IT Implemented and tested | 5 |
| SCO-02 | Import validation: invalid/negative/zero quantities, duplicates, blanks, headings, source-row traceability, re-import diffs as change requests | IT Implemented and tested | 5 |
| SCO-03 | Unit registry with explicit conversion (length/area/volume/mass), ambiguity flagging, no implicit time/count conversion | IT Implemented and tested | 5 |
| SCO-04 | Industrial/process units and administrator-managed unit list (inch-diameter, weld joint, spool, instrument loop, MVA, flow/pressure/temperature, tonne-km...) | MI Missing | 2 |
| SCO-05 | Quantity integrity: quantities come only from human-supplied files; changes need a reason and approval; original text immutable; no automated takeoff | IT Implemented and tested | 5 |
| SCO-06 | Pre-calculated resource quantities priced directly (takeoff resource lines) | IT Implemented and tested | 4 |
| SCO-07 | Mapping of BOQ items to assemblies/cost codes with approval; keyword-based mapping suggestions (no AI needed) | IT Implemented and tested | 5 |
| SCO-08 | Non-assembly pricing methods: subcontract lump sum, provisional sum, prime-cost sum, allowance, excluded - each needs approval | IT Implemented and tested | 5 |
| SCO-09 | Scale: large BOQs (10k-50k lines) | PA Partial | 3 |
| SCO-10 | Tender-document intake: numbered workspace, hash/type/size index, versioned text extracts (txt/md/csv/json/xml/html/PDF/DOCX/XLSX), change and missing-file flags | IT Implemented and tested | 4 |
| SCO-11 | Requirements/clarification extraction from tender documents (procedure + deterministic scope checks) | IU Implemented but unverified | 4 |

**SCO-01 - BOQ/takeoff import from CSV/XLSX with header detection, column mapping, Arabic headers, stored original**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/imports/boq.py::import_boq`; `app/imports/boq.py::detect_header`; `app/imports/readers.py::read_sheet`; `app/api/routes.py::boq_preview`
- *Tests:* `imports/test_boq_import.py::test_standard_csv_and_xlsx_equivalent` [yes] (CSV and XLSX give identical items); `imports/test_boq_import.py::test_irregular_column_names_and_order` [yes]; `imports/test_boq_import.py::test_arabic_headers` [yes]; `imports/test_boq_import.py::test_missing_required_header_needs_explicit_mapping` [yes]; `imports/test_boq_import.py::test_malformed_and_unsupported_files` [yes]
- *Workflow / output:* UI BOQ import page / `project import-boq` / POST /api/projects/{id}/boq/import; summary + rejected rows; original copied to '3. BOQ & Takeoff'.
- *Limitations / dependencies:* Single-table BOQs. No multi-sheet consolidation, merged-cell layouts, or vendor-specific formats (e.g. client schedule-of-rates forms). Header detection is heuristic; ambiguity requires an explicit mapping.
- *Acceptance test to mark complete:* Import a 500-row client BOQ (XLSX with merged title rows and Arabic headers) and reconcile rows_read = items + headings + blank + rejected with zero silently dropped rows.

**SCO-02 - Import validation: invalid/negative/zero quantities, duplicates, blanks, headings, source-row traceability, re-import diffs as change requests**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/imports/boq.py::parse_rows`; `app/imports/boq.py::_queue_change`; `app/services/boq.py::decide_change`
- *Tests:* `imports/test_boq_import.py::test_invalid_quantities_rejected_with_reasons_never_silently` [yes]; `imports/test_boq_import.py::test_duplicate_codes_flagged_and_both_kept` [yes]; `imports/test_boq_import.py::test_source_traceability_and_original_values_preserved` [yes]; `imports/test_boq_import.py::test_reimport_never_overwrites_quantities` [yes]
- *Workflow / output:* Rejected rows list with reason codes; `change_requests` Pending Review for revised quantities.
- *Limitations / dependencies:* Rule-based; no semantic check of description-vs-unit plausibility (e.g. 'concrete' in m2).
- *Acceptance test to mark complete:* Re-import a revised BOQ where 10 quantities changed, 3 items were deleted and 2 added: exactly 10 change requests, 3 'missing in revision', 2 new items, no quantity changed before approval.

**SCO-03 - Unit registry with explicit conversion (length/area/volume/mass), ambiguity flagging, no implicit time/count conversion**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/core/units.py::UnitRegistry`; `data/units/units.csv`; `app/estimators/direct_cost.py::_convert_factor_unit`
- *Tests:* `unit/test_money_units.py::test_unit_resolution` [yes]; `unit/test_money_units.py::test_unit_conversion_rules` [yes]; `imports/test_boq_import.py::test_unknown_ambiguous_missing_units_flagged_not_normalised` [yes]; `unit/test_direct_cost.py::test_unit_conversion_t_to_kg` [yes]; `unit/test_direct_cost.py::test_incompatible_units_rejected` [yes]
- *Workflow / output:* Units shown/validated at import; conversion factors recorded on cost-line basis text.
- *Limitations / dependencies:* 28 units, building-oriented. `ton`/`tons` are deliberately ambiguous (must be resolved by a human).
- *Acceptance test to mark complete:* Every unit used in the target client's BOQ either resolves to a canonical unit or is listed as unknown with a human decision recorded.

**SCO-04 - Industrial/process units and administrator-managed unit list (inch-diameter, weld joint, spool, instrument loop, MVA, flow/pressure/temperature, tonne-km...)**  
*Status:* Missing · *needed from level:* 2 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None. Audit probe: BOQ rows with units 'inch-dia', 'joint', 'spool', 'loop', 'MVA', 'm3/h' were all imported as unit_status=unknown (needs review) and cannot be priced.
- *Limitations / dependencies:* Closest existing: `data/units/units.csv` (insert-only seed; no UI/API to add units; no dimensions for power-MVA, flow, pressure). Items with unknown units stay unpriced - safe but a hard blocker for piping/E&I BOQs.
- *Acceptance test to mark complete:* Add units inch-dia, joint, spool, loop, MVA, m3/h, bar via a controlled admin action with audit; import a piping BOQ using them with 0 unknown-unit rows; conversions only where physically exact.

**SCO-05 - Quantity integrity: quantities come only from human-supplied files; changes need a reason and approval; original text immutable; no automated takeoff**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/services/boq.py::request_quantity_change`; `app/services/boq.py::decide_change`; `app/imports/boq.py::_persist`
- *Tests:* `imports/test_boq_import.py::test_quantity_change_requires_approval_and_reason` [yes]; `imports/test_boq_import.py::test_reimport_never_overwrites_quantities` [yes]
- *Workflow / output:* Pending change requests queue; approved change updates `quantity` while `quantity_original` stays.
- *Limitations / dependencies:* Absence of any takeoff code is by design and is asserted only by code inspection (no module reads drawings/PDF geometry); there is no negative test for it.
- *Acceptance test to mark complete:* Attempt to change a quantity through every public path (API, UI, workbook import): each yields a Pending Review change request, never a direct change.

**SCO-06 - Pre-calculated resource quantities priced directly (takeoff resource lines)**  
*Status:* Implemented and tested · *needed from level:* 4 · *kind:* engine
- *Code:* `app/imports/boq.py::import_takeoff_resources`; `app/estimators/direct_cost.py::_price_takeoff_item`
- *Tests:* `workspaces/test_audit_regressions.py::test_takeoff_resource_lines_are_priced_from_approved_rates_and_missing_rates_stay_unpriced` [yes] (added by this audit (pricing was previously untested)); `imports/test_boq_import.py::test_takeoff_resource_import` [partly] (tests import; pricing is exercised by the integration workflow); `integration/test_full_workflow.py::test_initial_state_matches_independent_hand_calculations` [partly]
- *Workflow / output:* Template `takeoff_import_template.xlsx` (sheet Resource Takeoff).
- *Limitations / dependencies:* No waste/productivity logic on these lines by design (quantities are final).
- *Acceptance test to mark complete:* Import resource takeoff lines for 20 items; engine amount = quantity x eligible rate for each, unpriced when the rate is missing.

**SCO-07 - Mapping of BOQ items to assemblies/cost codes with approval; keyword-based mapping suggestions (no AI needed)**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/services/boq.py::map_to_assembly`; `app/services/boq.py::approve_mapping`; `app/ai/service.py::heuristic_mapping`
- *Tests:* `approvals/test_ai_boundary.py::test_only_a_human_can_accept_a_suggestion` [yes] (suggestion changes nothing; only a human acceptance maps the item and records the approval); `approvals/test_ai_boundary.py::test_deterministic_features_work_without_any_ai` [partly] (exercises heuristic_mapping existence/output, not suggestion quality); `integration/test_full_workflow.py::test_complete_workflow_to_gated_submission_export` [partly] (manual mapping in the end-to-end flow)
- *Workflow / output:* Mapping tab; suggestions are Pending Review `ai_suggestions` until a human accepts.
- *Limitations / dependencies:* Suggestion precision/recall is unmeasured; token-overlap only; no spec/tag/discipline-aware matching.
- *Acceptance test to mark complete:* On a 200-item labelled sample, report suggestion hit rate; wrong suggestions never alter a mapping without human acceptance.

**SCO-08 - Non-assembly pricing methods: subcontract lump sum, provisional sum, prime-cost sum, allowance, excluded - each needs approval**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/services/boq.py::set_pricing`; `app/services/boq.py::decide_pricing`; `app/estimators/direct_cost.py::_price_allowance`; `app/estimators/direct_cost.py::_price_subcontract_item`
- *Tests:* `reconciliation/test_recon.py::test_scope_mismatches_exclusion_vs_priced` [partly]; `unit/test_direct_cost.py::test_subcontract_double_count_blocked` [yes]; `integration/test_full_workflow.py::test_complete_workflow_to_gated_submission_export` [partly] (allowance approvals in the flow)
- *Workflow / output:* Mapping tab pricing form; Allowances queue in Approvals.
- *Limitations / dependencies:* Sums are flat amounts; no drawdown or measured-remeasurement logic.
- *Acceptance test to mark complete:* Price one item of each method; unapproved sums produce ALLOWANCE_UNAPPROVED (Critical) and no amount in a strict estimate.

**SCO-09 - Scale: large BOQs (10k-50k lines)**  
*Status:* Partial · *needed from level:* 3 · *kind:* engine
- *Code:* `app/estimators/estimate.py::compute_estimate`; `app/excel/master.py::build_master`; `app/services/snapshots.py::build_snapshot`
- *Tests:* `workspaces/test_audit_regressions.py::test_estimate_computation_scales_roughly_linearly_with_boq_size` [yes] (ratio test guards the O(n^2) defect found by this audit)
- *Workflow / output:* Audit measurement (this sandbox, synthetic 20,000-item BOQ, 40,000 lines): import 1.1 s, mapping 3.1 s, compute_estimate 2.7 s (was 13.8 s before the fix), freeze+snapshot 4.6 s, master workbook export 62 s.
- *Limitations / dependencies:* Every UI page recomputes the whole estimate; workbook export of 20k rows takes about a minute; snapshots store full inputs (large JSON). No pagination in several tables. Single SQLite connection, serialised requests.
- *Acceptance test to mark complete:* 50,000-item BOQ: estimate < 10 s, any page < 3 s (cached estimate), workbook export < 3 min, memory < 2 GB; regression test with a published budget.

**SCO-10 - Tender-document intake: numbered workspace, hash/type/size index, versioned text extracts (txt/md/csv/json/xml/html/PDF/DOCX/XLSX), change and missing-file flags**  
*Status:* Implemented and tested · *needed from level:* 4 · *kind:* engine
- *Code:* `app/services/project_index.py::index_project`; `app/services/project_index.py::extract_text`; `app/services/workspaces.py::ensure_workspace`
- *Tests:* `workspaces/test_workspaces.py::test_indexer_inventories_versions_and_flags_changes` [yes]; `workspaces/test_audit_regressions.py::test_real_pdf_docx_and_xlsx_text_is_extracted_and_image_only_pdf_is_reported` [yes] (added by this audit: previously no valid PDF/DOCX/XLSX was ever extracted in tests, and pypdf was not a declared dependency); `workspaces/test_workspaces.py::test_new_project_creates_complete_workspace` [yes]
- *Workflow / output:* `project index`, UI Workspace tab, `2. AI Context/project_index.json`, `project_summary.md`, `extracts/`.
- *Limitations / dependencies:* No OCR (scanned PDFs reported), no DWG/DXF/RVT/IFC extraction, no table-structure extraction from PDFs, no Arabic-specific text handling tests; summaries are counts only.
- *Acceptance test to mark complete:* Index a real 300-page tender PDF set with scanned and text pages: text pages extracted, scanned pages reported, no original modified.

**SCO-11 - Requirements/clarification extraction from tender documents (procedure + deterministic scope checks)**  
*Status:* Implemented but unverified · *needed from level:* 4 · *kind:* engine
- *Code:* `.claude/skills/requirements-extraction/SKILL.md`; `app/ai/service.py::deterministic_scope_checks`; `app/services/registers.py::add_clarification`
- *Tests:* `approvals/test_ai_boundary.py::test_clarification_suggestions_become_open_items_never_resolved` [partly] (AI draft path tested with a mock provider only); `unit/test_instruction_system.py::test_every_skill_is_well_formed_and_states_all_required_sections` [partly] (skill structure only, never executed by a live session)
- *Workflow / output:* Requirements register (markdown/JSON) + Draft clarifications/scope entries.
- *Limitations / dependencies:* The extraction itself is a Claude Code procedure (skill) and the optional AI provider; neither has run against real tender documents or the live API. No automated clause-level cross-referencing.
- *Acceptance test to mark complete:* Run on a real specification section set: every extracted requirement quote is found verbatim in the cited page; reviewer rates misses/false items on a sample.

### B. Classification and libraries: CBS/WBS, catalogues, assemblies, data readiness

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| LIB-01 | Cost breakdown structure: 3-level cost-code taxonomy A-L (152 nodes), extensible as data | IT Implemented and tested | 5 |
| LIB-02 | Work breakdown structure separate from CBS (area/unit/system/tag) and cross-walk to client-specific code lists | MI Missing | 3 |
| LIB-03 | Resource catalogue definitions for building trades and MEP (927 resources, no prices) | IT Implemented and tested | 5 |
| LIB-04 | Industrial/process resource catalogue (piping classes, valves/flanges by rating, instruments, vessels, tanks, NDT, cathodic protection, hazardous-area equipment) | PA Partial | 2 |
| LIB-05 | Assembly library: structure-only standard assemblies (26 assemblies / 72 lines in divisions B-I), no consumption factors | PA Partial | 4 |
| LIB-06 | Rate/assumption/assembly versioning: approved records immutable, new version supersedes, expiry marks Expired, full history kept | IT Implemented and tested | 5 |
| LIB-07 | DATA READINESS: evidence-backed Saudi rate library (material, labour, plant, equipment, subcontract) | MI Missing | 5 (data) |
| LIB-08 | DATA READINESS: productivity/consumption/wastage factors and crew data approved by humans | MI Missing | 5 (data) |
| LIB-09 | Source Register with provenance, access log and licence notes | PA Partial | 4 |

**LIB-01 - Cost breakdown structure: 3-level cost-code taxonomy A-L (152 nodes), extensible as data**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/services/refdata.py::load_taxonomy`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [yes]; `unit/test_library_data.py::test_new_trade_can_be_added_without_code_changes` [yes]
- *Workflow / output:* docs/TRADE_TAXONOMY.md; cost-code selectors in the UI; Trade and Cost Code Mapping sheet.
- *Limitations / dependencies:* Building-services-centred division list. Divisions A-L only; no process-plant breakdown (units/areas/systems, pipe classes). Insert-only seed.
- *Acceptance test to mark complete:* Load a client CBS of 500 codes with parents, map every BOQ item to it, and roll costs up by any level with totals equal to the estimate.

**LIB-02 - Work breakdown structure separate from CBS (area/unit/system/tag) and cross-walk to client-specific code lists**  
*Status:* Missing · *needed from level:* 3 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None. BOQ items carry `section`, `trade`, `cost_code`, `drawing_ref`, `spec_ref` only (migration 0003).
- *Limitations / dependencies:* Closest existing: `boq_items.section` (free text heading) and `cost_code`. No area/unit/system/tag fields; no code cross-walk table; no roll-up report by WBS element.
- *Acceptance test to mark complete:* Define a WBS (area > unit > system) and a CBS-to-client-code map; every item gets both; reports roll up by either and reconcile to the same total.

**LIB-03 - Resource catalogue definitions for building trades and MEP (927 resources, no prices)**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `data/materials/materials.csv`; `data/labour/labour_categories.csv`; `data/plant/plant_categories.csv`; `data/equipment/equipment_categories.csv`; `data/subcontractors/subcontract_packages.csv`; `app/services/refdata.py::load_resource_catalogues`
- *Tests:* `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [yes]
- *Workflow / output:* Resource libraries UI/workbook sheets; coverage report.
- *Limitations / dependencies:* Definitions only. By division: A 99, B 128, C 89, D 112, E 114, F 64, G 63, H 99, I 64, J 50, K 32, L 13. Specifications are placeholders to be confirmed per project.
- *Acceptance test to mark complete:* Every catalogue resource has unit, cost code and a specification field a human has completed before first use in an approved estimate.

**LIB-04 - Industrial/process resource catalogue (piping classes, valves/flanges by rating, instruments, vessels, tanks, NDT, cathodic protection, hazardous-area equipment)**  
*Status:* Partial · *needed from level:* 2 · *kind:* engine
- *Code:* `data/equipment/equipment_categories.csv`; `data/materials/materials.csv`; `data/plant/plant_categories.csv`
- *Tests:* `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly] (validates the existing rows only)
- *Workflow / output:* Existing industrial-adjacent rows are searchable in the libraries UI (J.05 'Industrial and process equipment', pressure vessel, intumescent coating, shot-blasting plant, hydrotest pump, pipe welder labour, structural steel supply/erect package).
- *Limitations / dependencies:* Audit keyword probe of the 927 definitions: no transmitters/DCS/PLC/SCADA/NDT/radiography/cathodic/boiler/turbine/manifold/refractory/shutdown rows; piping limited to building services and water mains; valves are building-grade.
- *Acceptance test to mark complete:* Catalogue extended (definitions only) for each industrial discipline with specification fields reviewed by a discipline lead; coverage report shows counts by discipline.

**LIB-05 - Assembly library: structure-only standard assemblies (26 assemblies / 72 lines in divisions B-I), no consumption factors**  
*Status:* Partial · *needed from level:* 4 · *kind:* engine
- *Code:* `data/assemblies/standard_assemblies.csv`; `app/services/refdata.py::load_standard_assemblies`; `app/services/assemblies.py::validate`
- *Tests:* `unit/test_library_data.py::test_standard_assemblies_are_structure_only_drafts` [yes]
- *Workflow / output:* Assemblies page; Assembly Library sheet.
- *Limitations / dependencies:* Draft structures that cannot be approved until a human supplies factors and sources. None for divisions A, J, K, L or any industrial discipline. The assembly *engine* is separately tested (EST-01/02).
- *Acceptance test to mark complete:* For a stated list of N high-use work items, approved assemblies exist with documented human-supplied factor sources and the estimate prices them with no manual line edits.

**LIB-06 - Rate/assumption/assembly versioning: approved records immutable, new version supersedes, expiry marks Expired, full history kept**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/services/rates.py::approve_rate`; `app/services/rates.py::revise_rate`; `app/services/rates.py::expire_stale_rates`; `app/services/assumptions.py::revise_assumption`; `app/services/assemblies.py::new_version`
- *Tests:* `approvals/test_approval_rules.py::test_approved_data_cannot_be_silently_overwritten` [yes]; `approvals/test_approval_rules.py::test_assumption_revisions_are_new_versions` [yes]; `approvals/test_approval_rules.py::test_assembly_edits_create_pending_revisions` [yes]; `reconciliation/test_recon.py::test_expired_rate_flagged_and_not_used` [yes]
- *Workflow / output:* Resource page version table; audit log.
- *Limitations / dependencies:* Nothing is deleted, so very long histories grow the DB; no archival policy.
- *Acceptance test to mark complete:* Approve 3 successive versions of one rate: older rows Superseded and unchanged; a frozen estimate keeps its original result.

**LIB-07 - DATA READINESS: evidence-backed Saudi rate library (material, labour, plant, equipment, subcontract)**  
*Status:* Missing · *needed from level:* 5 · *kind:* data
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None. `python -m app.cli coverage` on a fresh install: 927 resources, 0 real approved rates, 927 missing.
- *Limitations / dependencies:* The pipelines to load rates exist (RTE-03/04) but no rate data has been supplied or approved. No legally reusable source of SAR unit rates was found (docs/KSA_DATA_SOURCES.md). Every real estimate is therefore Preliminary until rates are loaded.
- *Acceptance test to mark complete:* For the resources used by a named pilot BOQ, 100% have an approved, in-date, evidence-backed rate; `coverage` and the project completeness report show no 'Missing Rate' for them.

**LIB-08 - DATA READINESS: productivity/consumption/wastage factors and crew data approved by humans**  
*Status:* Missing · *needed from level:* 5 · *kind:* data
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None. Assumption register ships 322 definitions with only four methodological defaults; assemblies carry no factors.
- *Limitations / dependencies:* `data/productivity/` contains a schema only. No benchmark is provided or may be invented.
- *Acceptance test to mark complete:* Pilot-trade assemblies have factors with recorded sources (historical actuals, supplier data or client norms) approved by an Estimator; productivity variance report compares them to actuals.

**LIB-09 - Source Register with provenance, access log and licence notes**  
*Status:* Partial · *needed from level:* 4 · *kind:* engine
- *Code:* `data/sources/source_register.csv`; `data/sources/ACCESS_LOG.md`; `app/services/refdata.py::load_sources`
- *Tests:* `sources/test_rate_pipeline.py::test_real_cci_fixture_imports_as_index_observations_never_as_rates` [partly] (exercises SRC-002 linkage); `unit/test_library_data.py::test_integration_points_are_honest` [partly]
- *Workflow / output:* Settings > sources; docs/KSA_DATA_SOURCES.md (generated table).
- *Limitations / dependencies:* Register and access log are documentation, partly generated into docs/KSA_DATA_SOURCES.md. Licence text was read for few sources; 'Terms not reviewed' for most. Source ids are checked at dataset/candidate import (SOURCE_UNKNOWN) but nothing forces a rate's source to have a reviewed licence.
- *Acceptance test to mark complete:* Each source used for an approved rate has a register row with licence conditions actually read and an access-log entry.

### C. Building, civil, infrastructure and MEP disciplines

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| DSC-01 | Architectural and finishes (division D, 15 sub-trades, 112 definitions, 17 assembly lines) | PA Partial | 5 |
| DSC-02 | Structural concrete/masonry/steel for buildings (division C, 11 sub-trades, 89 definitions) | PA Partial | 5 |
| DSC-03 | Civil works and earthworks (division B, plant-intensive: excavators/tippers/utilisation, mobilisation once) | PA Partial | 4 |
| DSC-04 | Infrastructure and utilities (roads, drainage, water, sewer, power ducts, external services: divisions B and K) | PA Partial | 3 |
| DSC-05 | HVAC / mechanical (division E: chillers, AHU, ductwork, VRF, BMS interface) | PA Partial | 4 |
| DSC-06 | Plumbing and drainage (division F) | PA Partial | 4 |
| DSC-07 | Fire protection and life safety (division G) | PA Partial | 4 |
| DSC-08 | Electrical power and lighting for buildings (division H: switchgear, transformers, DBs, cable/containment, lighting) | PA Partial | 4 |
| DSC-09 | ELV, ICT and security (division I) | PA Partial | 4 |
| DSC-10 | Specialist systems (division J: lifts, facade access, kitchens, medical gas, pools, EV charging, renewable) | PA Partial | 4 |
| DSC-11 | External works, landscaping and site-wide systems (division K) | PA Partial | 4 |

**DSC-01 - Architectural and finishes (division D, 15 sub-trades, 112 definitions, 17 assembly lines)**  
*Status:* Partial · *needed from level:* 5 · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`; `data/assemblies/standard_assemblies.csv`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]
- *Workflow / output:* Estimate build-up, pricing schedule, master workbook.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. Standard assemblies are structure-only.
- *Acceptance test to mark complete:* A pilot architectural BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

**DSC-02 - Structural concrete/masonry/steel for buildings (division C, 11 sub-trades, 89 definitions)**  
*Status:* Partial · *needed from level:* 5 · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`; `data/assemblies/standard_assemblies.csv`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]
- *Workflow / output:* As above.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. 
- *Acceptance test to mark complete:* A pilot structural BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

**DSC-03 - Civil works and earthworks (division B, plant-intensive: excavators/tippers/utilisation, mobilisation once)**  
*Status:* Partial · *needed from level:* 4 · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`; `app/estimators/rate_build.py::build_plant`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]; `integration/test_full_workflow.py::test_initial_state_matches_independent_hand_calculations` [yes] (excavation item hand-calculated with utilisation)
- *Workflow / output:* As above.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. Haul-distance, swell/shrink, balancing and cut-fill logic are not modelled (plant output rates are user factors).
- *Acceptance test to mark complete:* A pilot earthworks BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

**DSC-04 - Infrastructure and utilities (roads, drainage, water, sewer, power ducts, external services: divisions B and K)**  
*Status:* Partial · *needed from level:* 3 · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]
- *Workflow / output:* As above.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. No linear-project features (chainage, phasing by section, traffic management sequencing).
- *Acceptance test to mark complete:* A pilot road + drainage BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

**DSC-05 - HVAC / mechanical (division E: chillers, AHU, ductwork, VRF, BMS interface)**  
*Status:* Partial · *needed from level:* 4 · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`; `data/assemblies/standard_assemblies.csv`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]
- *Workflow / output:* As above.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. Equipment is priced as supplied items; no capacity-based selection or duct-weight take-off.
- *Acceptance test to mark complete:* A pilot HVAC BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

**DSC-06 - Plumbing and drainage (division F)**  
*Status:* Partial · *needed from level:* 4 · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`; `data/assemblies/standard_assemblies.csv`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]
- *Workflow / output:* As above.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. 
- *Acceptance test to mark complete:* A pilot plumbing BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

**DSC-07 - Fire protection and life safety (division G)**  
*Status:* Partial · *needed from level:* 4 · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`; `data/assemblies/standard_assemblies.csv`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]
- *Workflow / output:* As above.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. Authority approval/inspection costs only as priced items.
- *Acceptance test to mark complete:* A pilot fire protection BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

**DSC-08 - Electrical power and lighting for buildings (division H: switchgear, transformers, DBs, cable/containment, lighting)**  
*Status:* Partial · *needed from level:* 4 · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`; `data/assemblies/standard_assemblies.csv`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]
- *Workflow / output:* As above.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. No cable schedule/termination engine; no load-based sizing.
- *Acceptance test to mark complete:* A pilot electrical BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

**DSC-09 - ELV, ICT and security (division I)**  
*Status:* Partial · *needed from level:* 4 · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`; `data/assemblies/standard_assemblies.csv`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]
- *Workflow / output:* As above.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. System-integration/programming effort only as priced items or subcontract packages.
- *Acceptance test to mark complete:* A pilot ELV BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

**DSC-10 - Specialist systems (division J: lifts, facade access, kitchens, medical gas, pools, EV charging, renewable)**  
*Status:* Partial · *needed from level:* 4 · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]
- *Workflow / output:* As above.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. No standard assemblies exist for division J; 50 catalogue definitions; priced mainly as subcontract/equipment packages.
- *Acceptance test to mark complete:* A pilot specialist-systems BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

**DSC-11 - External works, landscaping and site-wide systems (division K)**  
*Status:* Partial · *needed from level:* 4 · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]
- *Workflow / output:* As above.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. 32 definitions, no standard assemblies.
- *Acceptance test to mark complete:* A pilot external-works BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

### D. Industrial, oil and gas, process plant

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| PRC-01 | Process piping: spools, inch-diameter, pipe class/schedule/material, welds, supports, NDT, hydrotest, flushing, field vs shop split | MI Missing | 2 |
| PRC-02 | Process equipment (vessels, exchangers, pumps, compressors): supply, receive, set, align, grout, vendor reps, spares | PA Partial | 2 |
| PRC-03 | Instrumentation and control (loops, I/O, junction boxes, tubing, calibration, DCS/PLC/SCADA configuration, FAT/SAT) | MI Missing | 2 |
| PRC-04 | Industrial electrical power (MV/LV switchgear, transformers, MCC, cable pulling/termination, tray, earthing, hazardous-area) | PA Partial | 2 |
| PRC-05 | Structural steel by tonnage: supply, fabricate, blast/paint, erect, bolt/weld | PA Partial | 2 |
| PRC-06 | Field-erected tanks and large vessels (plate welding, NDT, hydro/air test, settlement test) | MI Missing | 2 |
| PRC-07 | Surface preparation, coating systems and fireproofing (blast, primer/intermediate/topcoat, DFT, coverage, shop vs field) | PA Partial | 2 |
| PRC-08 | Thermal insulation and cladding (hot/cold service, thickness, jacketing) | PA Partial | 2 |
| PRC-09 | Scaffolding and temporary access for industrial work (volume-based, by phase) | PA Partial | 2 |
| PRC-10 | Heavy lifting, rigging and crane selection (lift studies, crane hire periods, mobilisation of large cranes) | PA Partial | 2 |
| PRC-11 | Cathodic protection, NDT services, specialist industrial services (hazardous-area works, hot-tapping, chemical cleaning) | MI Missing | 2 |
| PRC-12 | Shutdown/turnaround and brownfield estimating (tie-ins, live-plant restrictions, permits, hot-work, outage windows) | MI Missing | 1 |
| PRC-13 | Modularisation, prefabrication and yard-vs-site work splits | MI Missing | 1 |
| PRC-14 | Remote-site construction: camps, catering, logistics, rotation and per-diem, site mobilisation | PA Partial | 2 |

**PRC-01 - Process piping: spools, inch-diameter, pipe class/schedule/material, welds, supports, NDT, hydrotest, flushing, field vs shop split**  
*Status:* Missing · *needed from level:* 2 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None.
- *Limitations / dependencies:* Closest existing: generic assembly lines (kg/m/nr) and a pipe-welder labour definition; no unit for inch-dia/joint (SCO-04), no weld/NDT/test sequence logic, no pipe-class catalogue. Depends on: SCO-04, LIB-04, EST-12.
- *Acceptance test to mark complete:* Estimate a 500-spool package from a MTO: man-hours derive from inch-dia x approved factors by size/schedule/material with shop/field split; weld and NDT counts reconcile to the MTO; hydrotest and flushing costed.

**PRC-02 - Process equipment (vessels, exchangers, pumps, compressors): supply, receive, set, align, grout, vendor reps, spares**  
*Status:* Partial · *needed from level:* 2 · *kind:* engine
- *Code:* `data/equipment/equipment_categories.csv`; `app/estimators/direct_cost.py::_material_like`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_direct_cost.py::test_full_assembly_hand_calculated` [partly] (generic assembly lines only)
- *Workflow / output:* Equipment can be priced as supplied items plus an installation assembly.
- *Limitations / dependencies:* No weight/tonnage-based erection model, vendor-package structure, rigging/lift linkage or spares/special-tools build-up (assumption definitions only). Depends on: PRC-10.
- *Acceptance test to mark complete:* A vendor-supplied pump skid and a field-erected vessel are each estimated with supply, freight, rigging, set/align and vendor-representative costs, all traceable to approved inputs.

**PRC-03 - Instrumentation and control (loops, I/O, junction boxes, tubing, calibration, DCS/PLC/SCADA configuration, FAT/SAT)**  
*Status:* Missing · *needed from level:* 2 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None.
- *Limitations / dependencies:* Closest existing: ELV/BMS definitions (division I) and an instrumentation-technician labour definition. No loop/I-O driven estimating, no loop-check/calibration productivity, no unit 'loop'. Depends on: SCO-04, LIB-04.
- *Acceptance test to mark complete:* A 400-loop instrument package is estimated from an instrument index: installation, tubing, calibration and loop-check hours derive from approved per-loop factors; control-system configuration priced from vendor quotation.

**PRC-04 - Industrial electrical power (MV/LV switchgear, transformers, MCC, cable pulling/termination, tray, earthing, hazardous-area)**  
*Status:* Partial · *needed from level:* 2 · *kind:* engine
- *Code:* `data/materials/materials.csv`; `data/equipment/equipment_categories.csv`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works)
- *Workflow / output:* As building electrical (DSC-08).
- *Limitations / dependencies:* No cable schedule/length-by-size engine, termination counts, hazardous-area classification costs, or substation commissioning logic; MV/HV beyond a few catalogue lines is absent. Depends on: LIB-04, EST-12.
- *Acceptance test to mark complete:* A substation + 2 km cable package is estimated from a cable schedule with termination/pulling hours per approved factors and testing/commissioning scope.

**PRC-05 - Structural steel by tonnage: supply, fabricate, blast/paint, erect, bolt/weld**  
*Status:* Partial · *needed from level:* 2 · *kind:* engine
- *Code:* `data/materials/materials.csv`; `data/subcontractors/subcontract_packages.csv`; `app/estimators/direct_cost.py::_price_line`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_direct_cost.py::test_unit_conversion_t_to_kg` [partly] (t<->kg conversion only)
- *Workflow / output:* Priceable per tonne through an assembly or a subcontract lump.
- *Limitations / dependencies:* No MH/tonne by member class, connection count, fabrication vs erection split, galvanising logistics or weight-from-section library. Depends on: LIB-08.
- *Acceptance test to mark complete:* A 1,000 t steel package priced by approved MH/tonne factors and rates with shop/field split and coating tonnage reconciled to the steel MTO.

**PRC-06 - Field-erected tanks and large vessels (plate welding, NDT, hydro/air test, settlement test)**  
*Status:* Missing · *needed from level:* 2 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None.
- *Limitations / dependencies:* Closest existing: generic welder labour and plant lines. No plate-weight/seam-length models. Depends on: PRC-01.
- *Acceptance test to mark complete:* A storage-tank package estimated from plate weights, weld length, test requirements, with productivity from approved factors.

**PRC-07 - Surface preparation, coating systems and fireproofing (blast, primer/intermediate/topcoat, DFT, coverage, shop vs field)**  
*Status:* Partial · *needed from level:* 2 · *kind:* engine
- *Code:* `data/materials/materials.csv`; `data/plant/plant_categories.csv`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works)
- *Workflow / output:* Priceable by area (m2) through an assembly.
- *Limitations / dependencies:* Coating system, DFT, coverage and wastage can only be encoded by hand in assembly factors; no system definition, no repair/touch-up logic.
- *Acceptance test to mark complete:* A coating specification (blast + 3 coats) is an approved assembly whose material quantity derives from stated coverage and DFT factors.

**PRC-08 - Thermal insulation and cladding (hot/cold service, thickness, jacketing)**  
*Status:* Partial · *needed from level:* 2 · *kind:* engine
- *Code:* `data/materials/materials.csv`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works)
- *Workflow / output:* Priceable by m2 or m through assemblies.
- *Limitations / dependencies:* 8 catalogue definitions; no thickness/diameter-based area computation (quantities are human-supplied).
- *Acceptance test to mark complete:* Insulation by size/thickness priced from an approved assembly set with applicator productivity and jacketing.

**PRC-09 - Scaffolding and temporary access for industrial work (volume-based, by phase)**  
*Status:* Partial · *needed from level:* 2 · *kind:* engine
- *Code:* `data/plant/plant_categories.csv`; `data/taxonomy/cost_codes.csv`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works)
- *Workflow / output:* Priceable through A.06 items/assemblies or indirects.
- *Limitations / dependencies:* No scaffold-volume, erect/dismantle/hire-period model. Depends on: DUR-05.
- *Acceptance test to mark complete:* Scaffolding for a unit costed by volume and duration with erect/dismantle productivity and hire time from the programme.

**PRC-10 - Heavy lifting, rigging and crane selection (lift studies, crane hire periods, mobilisation of large cranes)**  
*Status:* Partial · *needed from level:* 2 · *kind:* engine
- *Code:* `data/plant/plant_categories.csv`; `app/estimators/rate_build.py::build_plant`
- *Tests:* `unit/test_rate_build.py::test_plant_day_basis_uses_supplied_calendar` [yes] (plant hire build-up); `unit/test_direct_cost.py::test_full_assembly_hand_calculated` [partly]
- *Workflow / output:* Crane lines priced as plant with mobilisation once.
- *Limitations / dependencies:* Standby/minimum-hire not applied (EST-05); no lift-plan or crane-capacity logic; hire period is not tied to a programme. Depends on: EST-05, DUR-05.
- *Acceptance test to mark complete:* A lift package priced with crane hire derived from the programme durations plus mobilisation, standby and rigging labour.

**PRC-11 - Cathodic protection, NDT services, specialist industrial services (hazardous-area works, hot-tapping, chemical cleaning)**  
*Status:* Missing · *needed from level:* 2 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None.
- *Limitations / dependencies:* Only expressible as generic subcontract packages with human-entered amounts.
- *Acceptance test to mark complete:* Each specialist service has a catalogue definition, unit and subcontract RFQ template with scope matrix.

**PRC-12 - Shutdown/turnaround and brownfield estimating (tie-ins, live-plant restrictions, permits, hot-work, outage windows)**  
*Status:* Missing · *needed from level:* 1 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None.
- *Limitations / dependencies:* No calendar windows, restricted-access productivity factors, or outage-critical path. Depends on: DUR-05, EST-12.
- *Acceptance test to mark complete:* A turnaround scope is estimated with window-constrained durations, access factors approved as assumptions, and permit/standby costs.

**PRC-13 - Modularisation, prefabrication and yard-vs-site work splits**  
*Status:* Missing · *needed from level:* 1 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None.
- *Limitations / dependencies:* No module/lift/transport/hook-up model.
- *Acceptance test to mark complete:* A module is estimated in yard and at site with transport, lift and hook-up costs separated and reconciled.

**PRC-14 - Remote-site construction: camps, catering, logistics, rotation and per-diem, site mobilisation**  
*Status:* Partial · *needed from level:* 2 · *kind:* engine
- *Code:* `data/indirects/indirect_categories.csv`; `app/estimators/indirect.py::compute_indirects`; `app/services/indirects.py::add_indirect`
- *Tests:* `unit/test_indirect_duration.py::test_methods_hand_calculated` [yes] (indirect methods); `unit/test_indirect_duration.py::test_duration_not_approved_blocks_duration_costs_but_not_fixed` [yes]
- *Workflow / output:* Accommodation/transport/offices as duration-based indirects.
- *Limitations / dependencies:* No camp sizing from manpower, no rotation/leave cost model, no remote-location logistics build-up; there are intentionally no regional multipliers. Depends on: DUR-04.
- *Acceptance test to mark complete:* Camp, catering and transport costs derive from the manpower histogram and programme with approved unit costs.

### E. Rates: material, labour, plant, equipment, subcontract; productivity and methodology

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| RTE-01 | Rate model for material, labour, plant, equipment and subcontract resources with eligibility rules (approved/provisional, date, region, real price type) | IT Implemented and tested | 5 |
| RTE-02 | Labour and plant rate build-ups from supplied components (wage, allowances, accommodation, transport, employer cost, overtime; hire basis, operator, fuel, maintenance) | IT Implemented and tested | 5 |
| RTE-03 | Supplier quotation -> approved rate publication (new Pending Review version, human approval) | IT Implemented and tested | 4 |
| RTE-04 | Rate candidates from datasets/price lists: import with manifest, queue, normalisation (approved FX/units/VAT), review, publication | IT Implemented and tested | 4 |
| RTE-05 | Live retrieval from public sources (KAPSARC/GASTAT CCI API) and operator web-price watchlist | IU Implemented but unverified | 3 |
| RTE-06 | Official cost-index storage (GASTAT CCI) as escalation reference, never a unit price | IT Implemented and tested | 3 |
| EST-01 | Assembly-based consumption pricing with explicit waste basis, nested assemblies, cycle guard, double-count prevention | IT Implemented and tested | 5 |
| EST-02 | Labour hours and crews: productivity bases (paid hours/unit, productive hours/unit, output per crew shift), overtime share | IT Implemented and tested | 5 |
| EST-03 | Plant mobilisation/demobilisation lump sums applied once per resource | IT Implemented and tested | 4 |
| EST-05 | Plant standby/idle and minimum hire periods applied to cost | MI Missing | 3 |
| EST-07 | Quantity/unit conversion between BOQ unit and assembly unit | IT Implemented and tested | 5 |
| EST-10 | Man-hour aggregation and histograms by craft/trade/area/period | MI Missing | 3 |
| EST-11 | Construction methodology: method statements, equipment selection, work sequencing that drives labour/plant quantities | MI Missing | 2 |
| EST-12 | Productivity adjustment factors (height, congestion, climate, shift, remote site, learning) as approved assumptions applied to hours | MI Missing | 2 |
| EST-04 | Missing/unapproved/expired/index-only rates leave lines unpriced with indicative exposure reported separately | IT Implemented and tested | 5 |
| EST-06 | Estimate states (Complete / Complete with Provisional Inputs / Preliminary) and SHA-256 fingerprint for stale detection | IT Implemented and tested | 5 |
| EST-08 | Project-scoped provisional rate approval with mandatory reason, always disclosed | IT Implemented and tested | 5 |
| EST-09 | What-if assumption impact analysis (strict vs preliminary, override not persisted) | IT Implemented and tested | 4 |

**RTE-01 - Rate model for material, labour, plant, equipment and subcontract resources with eligibility rules (approved/provisional, date, region, real price type)**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/estimators/rate_resolution.py::resolve_rate`; `app/services/rates.py::propose_rate`; `app/services/rates.py::approve_rate`
- *Tests:* `unit/test_schedule_resolution.py::test_resolution_outcomes` [yes]; `unit/test_schedule_resolution.py::test_provisional_is_project_scoped` [yes]; `approvals/test_approval_rules.py::test_unapproved_rate_never_becomes_verified` [yes]; `unit/test_direct_cost.py::test_missing_rate_never_zero` [yes]; `unit/test_direct_cost.py::test_expired_rate_flagged_not_used` [yes]
- *Workflow / output:* Resource page, estimate build-up (UNPRICED flags, indicative exposure).
- *Limitations / dependencies:* Region applicability by code only; no rate escalation to a base date; no volume-tier pricing.
- *Acceptance test to mark complete:* For each rate state (approved, provisional, pending, expired, future, wrong-region, index-only, missing) a line is priced or left unpriced exactly as specified.

**RTE-02 - Labour and plant rate build-ups from supplied components (wage, allowances, accommodation, transport, employer cost, overtime; hire basis, operator, fuel, maintenance)**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/estimators/rate_build.py::build_labour`; `app/estimators/rate_build.py::build_plant`; `app/services/rates.py::_price_from_components`
- *Tests:* `unit/test_rate_build.py::test_labour_hourly` [yes]; `unit/test_rate_build.py::test_labour_overtime_premium_on_base_wage_only` [yes]; `unit/test_rate_build.py::test_plant_day_basis_uses_supplied_calendar` [yes]; `integration/test_api_ui.py::test_labour_buildup_via_form_and_similar_item_search` [yes]
- *Workflow / output:* Resource page form -> stored `components_json`.
- *Limitations / dependencies:* Generic components only: GOSI, iqama/levy, Saudization premiums, end-of-service, flights/leave are not separate fields (use 'other'). No shift-pattern or skill-mix model. Depends on: SAU-03.
- *Acceptance test to mark complete:* A labour category rate is rebuilt from a company wage sheet with every Saudi statutory component as an explicit approved field and reproduces the company's own hourly cost.

**RTE-03 - Supplier quotation -> approved rate publication (new Pending Review version, human approval)**  
*Status:* Implemented and tested · *needed from level:* 4 · *kind:* engine
- *Code:* `app/procurement/selection.py::publish_rates`; `app/services/rates.py::propose_rate`
- *Tests:* `procurement/test_procurement.py::test_rate_publication_requires_rate_approval_and_links_quotation` [yes]; `procurement/test_procurement.py::test_published_rate_from_tax_inclusive_quote_is_pre_tax` [yes]
- *Workflow / output:* Quotations tab -> Propose rates from this quotation.
- *Limitations / dependencies:* Per-line only; no quantity-break tiers.
- *Acceptance test to mark complete:* Select a quoted supplier; each published rate links to its quotation line and cannot be used until approved.

**RTE-04 - Rate candidates from datasets/price lists: import with manifest, queue, normalisation (approved FX/units/VAT), review, publication**  
*Status:* Implemented and tested · *needed from level:* 4 · *kind:* engine
- *Code:* `app/rate_updates/importer.py::import_rates_file`; `app/rate_updates/candidates.py::publish`; `app/rate_updates/normalise.py::normalise`; `app/rate_updates/manifest.py::write_manifest`
- *Tests:* `sources/test_rate_pipeline.py::test_rates_import_dry_run_then_real_creates_candidates_and_manifest` [yes]; `sources/test_rate_pipeline.py::test_normalisation_requires_approved_inputs_and_never_changes_the_original` [yes]; `sources/test_rate_pipeline.py::test_unsafe_candidates_cannot_be_approved_for_publication` [yes]; `sources/test_rate_pipeline.py::test_publication_creates_new_pending_version_keeps_old_and_does_not_mutate_frozen_estimate` [yes]
- *Workflow / output:* Rate updates UI; `rates import|pending|review|publish`.
- *Limitations / dependencies:* Never run on a real supplier price list; two overlapping dataset flows exist (legacy staging).
- *Acceptance test to mark complete:* Import a real supplier price list of 200 lines: rejects/flags match a manual audit; 100% of published rates trace to the file hash and row.

**RTE-05 - Live retrieval from public sources (KAPSARC/GASTAT CCI API) and operator web-price watchlist**  
*Status:* Implemented but unverified · *needed from level:* 3 · *kind:* engine
- *Code:* `app/sources/providers.py::KapsarcGastatCci`; `app/sources/providers.py::WebPriceWatchlist`; `app/sources/webprice.py::extract_candidates`; `app/sources/base.py::HttpFetcher`
- *Tests:* `sources/test_rate_pipeline.py::test_kapsarc_provider_pages_and_imports_via_mock_only` [partly] (mocked transport); `sources/test_rate_pipeline.py::test_web_extraction_edge_cases_spec_only_quote_required_foreign_stale_promo_contradictory` [partly] (fixtures, not real pages); `sources/test_rate_pipeline.py::test_fetcher_backoff_retries_only_transient_errors_and_caches` [yes]
- *Workflow / output:* `sources refresh`; Rate updates page.
- *Limitations / dependencies:* The application's own HTTP client was BLOCKED from the build sandbox (proxy 403); no live success observed. Web extraction never run on a real page.
- *Acceptance test to mark complete:* On a normal network `sources refresh --provider kapsarc-gastat-cci` imports the latest CCI months with a manifest; one permitted real product page yields a candidate with correct evidence.

**RTE-06 - Official cost-index storage (GASTAT CCI) as escalation reference, never a unit price**  
*Status:* Implemented and tested · *needed from level:* 3 · *kind:* engine
- *Code:* `app/rate_updates/index_import.py::import_index_file`; `data/public_data/gastat_cci/kapsarc_cci_2026-04.records.json`
- *Tests:* `sources/test_rate_pipeline.py::test_real_cci_fixture_imports_as_index_observations_never_as_rates` [yes]; `sources/test_rate_pipeline.py::test_index_revision_keeps_both_values_and_bad_rows_are_rejected_with_reasons` [yes]
- *Workflow / output:* `index import|list`; Rate updates page.
- *Limitations / dependencies:* Stored only: no engine consumes index data (see RSK-05).
- *Acceptance test to mark complete:* Escalation assumption cites the stored index series and period it was derived from.

**EST-01 - Assembly-based consumption pricing with explicit waste basis, nested assemblies, cycle guard, double-count prevention**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/estimators/direct_cost.py::_material_like`; `app/estimators/direct_cost.py::_expand`; `app/services/assemblies.py::validate`; `app/services/assemblies.py::would_create_cycle`
- *Tests:* `unit/test_direct_cost.py::test_full_assembly_hand_calculated` [yes]; `unit/test_direct_cost.py::test_waste_not_applied_twice_by_validation` [yes]; `unit/test_direct_cost.py::test_nested_assembly_and_cycle_guard` [yes]; `unit/test_direct_cost.py::test_subcontract_double_count_blocked` [yes]
- *Workflow / output:* Estimate build-up with a 'basis' string per line.
- *Limitations / dependencies:* Factors are user-supplied; no automatic quantity-take-off logic.
- *Acceptance test to mark complete:* Hand-calculated assemblies (incl. nested) match engine amounts to the halala.

**EST-02 - Labour hours and crews: productivity bases (paid hours/unit, productive hours/unit, output per crew shift), overtime share**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/estimators/direct_cost.py::_labour`; `app/estimators/direct_cost.py::_hours_params`; `app/estimators/rate_build.py::blended_labour_rate`
- *Tests:* `unit/test_direct_cost.py::test_productive_hours_conversion` [yes]; `unit/test_direct_cost.py::test_missing_shift_assumption_blocks_crew_pricing` [yes]; `integration/test_full_workflow.py::test_initial_state_matches_independent_hand_calculations` [yes]
- *Workflow / output:* Labour lines show hours and basis.
- *Limitations / dependencies:* No learning-curve, congestion, height, climate or shift-fatigue adjustments (needs approved assumptions, EST-12).
- *Acceptance test to mark complete:* Crew-based item hours match a manual productivity calculation under each basis.

**EST-03 - Plant mobilisation/demobilisation lump sums applied once per resource**  
*Status:* Implemented and tested · *needed from level:* 4 · *kind:* engine
- *Code:* `app/estimators/direct_cost.py::_plant_mobilisation`
- *Tests:* `unit/test_rate_build.py::test_plant_day_basis_uses_supplied_calendar` [partly] (build-up values); `integration/test_full_workflow.py::test_initial_state_matches_independent_hand_calculations` [yes]
- *Workflow / output:* Separate mobilisation line in the build-up.
- *Limitations / dependencies:* Once per project, not per phase/site.
- *Acceptance test to mark complete:* Plant used in two items is mobilised once; used in two phases on different sites is mobilised twice when so configured.

**EST-05 - Plant standby/idle and minimum hire periods applied to cost**  
*Status:* Missing · *needed from level:* 3 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None. `standby_pct` is read into the build-up (app/estimators/rate_build.py) but not applied by any cost line.
- *Limitations / dependencies:* Documented in KNOWN_LIMITATIONS; unit-tested only as a stored value. Depends on: DUR-05.
- *Acceptance test to mark complete:* Plant with 20% standby and a 1-month minimum hire prices correctly under a hand-calculated example.

**EST-07 - Quantity/unit conversion between BOQ unit and assembly unit**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/estimators/direct_cost.py::_convert_factor_unit`
- *Tests:* `unit/test_direct_cost.py::test_item_unit_conversion_to_assembly_unit` [yes]; `unit/test_direct_cost.py::test_incompatible_units_rejected` [yes]
- *Workflow / output:* Cost-line basis text.
- *Limitations / dependencies:* Same-dimension physical conversions only (see SCO-03).
- *Acceptance test to mark complete:* Incompatible units are refused with an explanation, never converted silently.

**EST-10 - Man-hour aggregation and histograms by craft/trade/area/period**  
*Status:* Missing · *needed from level:* 3 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None. Per-line labour hours exist in the build-up (quantity in hr); no aggregate report. Only `productivity_variance` compares estimated and actual hours per resource.
- *Limitations / dependencies:* Closest existing: app/reporting/history.py::productivity_variance (needs actuals). Depends on: DUR-04.
- *Acceptance test to mark complete:* A report totals man-hours by craft and trade for any project and by month once a programme exists; totals equal the sum of labour lines.

**EST-11 - Construction methodology: method statements, equipment selection, work sequencing that drives labour/plant quantities**  
*Status:* Missing · *needed from level:* 2 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None. The estimator encodes methodology by hand in assembly factors; nothing records or checks it.
- *Limitations / dependencies:* No method library, no link between method and programme. Depends on: DUR-05.
- *Acceptance test to mark complete:* A method (e.g. slip-form vs conventional) is a recorded, approved option that selects assembly sets and durations, with both alternatives priceable and compared.

**EST-12 - Productivity adjustment factors (height, congestion, climate, shift, remote site, learning) as approved assumptions applied to hours**  
*Status:* Missing · *needed from level:* 2 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None. By design no unexplained multipliers exist.
- *Limitations / dependencies:* Would need approved, evidence-backed factor tables and an explicit engine step with traceable basis text.
- *Acceptance test to mark complete:* A congestion factor of 1.15 approved as an assumption raises hours on tagged items only, appears in the basis string, and is visible in the impact analysis.

**EST-04 - Missing/unapproved/expired/index-only rates leave lines unpriced with indicative exposure reported separately**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/estimators/direct_cost.py::_price_line`; `app/estimators/estimate.py::compute_estimate`
- *Tests:* `unit/test_direct_cost.py::test_missing_rate_never_zero` [yes]; `unit/test_direct_cost.py::test_unapproved_rate_excluded_but_exposure_reported` [yes]; `reconciliation/test_recon.py::test_unpriced_item_and_missing_rate_are_critical` [yes]
- *Workflow / output:* UNPRICED lines in the build-up, dashboard exposure, Critical findings.
- *Limitations / dependencies:* Exposure for a truly missing rate is 'unknown' by design.
- *Acceptance test to mark complete:* A BOQ with 5 missing-rate items shows exactly 5 unpriced items and a Preliminary state; no total includes a guessed value.

**EST-06 - Estimate states (Complete / Complete with Provisional Inputs / Preliminary) and SHA-256 fingerprint for stale detection**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/estimators/estimate.py::fingerprint`; `app/estimators/estimate.py::_blockers`
- *Tests:* `integration/test_final_flow.py::test_final_flow_and_gates` [yes]; `integration/test_smoke_estimate.py::test_mini_project_end_to_end` [yes]
- *Workflow / output:* State banner on estimate pages and documents.
- *Limitations / dependencies:* State is derived; there is no client-specific state vocabulary.
- *Acceptance test to mark complete:* Changing any input changes the fingerprint and invalidates an approved version.

**EST-08 - Project-scoped provisional rate approval with mandatory reason, always disclosed**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/services/rates.py::approve_rate_provisional`
- *Tests:* `approvals/test_approval_rules.py::test_provisional_rate_requires_explicit_reason_role_and_project` [yes]; `approvals/test_approval_rules.py::test_provisional_input_stays_visible_in_estimate` [yes]
- *Workflow / output:* Estimate state 'Complete with Provisional Inputs'.
- *Limitations / dependencies:* Project-scoped only; a provisional approval is a per-project override and never becomes a global rate. No expiry date on the provisional approval itself.
- *Acceptance test to mark complete:* A provisional rate never affects another project and is listed in the estimate report.

**EST-09 - What-if assumption impact analysis (strict vs preliminary, override not persisted)**  
*Status:* Implemented and tested · *needed from level:* 4 · *kind:* engine
- *Code:* `app/estimators/context.py::load_inputs`; `app/estimators/estimate.py::compute_estimate`
- *Tests:* `workspaces/test_audit_regressions.py::test_what_if_assumption_override_changes_the_estimate_by_the_expected_amount_and_leaves_stored_data_alone` [yes] (added by this audit (previously only page rendering was tested))
- *Workflow / output:* Assumptions > Show effect.
- *Limitations / dependencies:* Single-assumption what-if; no multi-variable sensitivity or tornado output.
- *Acceptance test to mark complete:* Override one assumption: delta equals a hand calculation; nothing persists.

### F. Engineering services, field indirects, home office, temporary facilities

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| IND-01 | Field indirects: fixed, percent-of-direct, per day/week/month x approved duration; allocation (pro-rata, separate line, by trade); subcontract-included exclusion | IT Implemented and tested | 5 |
| IND-02 | Temporary facilities, mobilisation/demobilisation and site establishment as priced scope | PA Partial | 4 |
| ENG-01 | Engineering services estimating (discipline man-hours, deliverables, vendor-data review, design allowance) | PA Partial | 1 |
| ENG-02 | Home-office/overhead/G&A allocation and project-management costs for EPC | PA Partial | 1 |
| PRE-01 | Preliminaries and general requirements (division A): priced as BOQ items/assemblies or as field indirects, with double-count detection between the two | PA Partial | 5 |

**IND-01 - Field indirects: fixed, percent-of-direct, per day/week/month x approved duration; allocation (pro-rata, separate line, by trade); subcontract-included exclusion**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/estimators/indirect.py::compute_indirects`; `app/services/indirects.py::add_indirect`; `app/api/actions.py::add_standard_indirects`
- *Tests:* `unit/test_indirect_duration.py::test_methods_hand_calculated` [yes]; `unit/test_indirect_duration.py::test_unapproved_and_missing_amount_never_zero` [yes]; `unit/test_indirect_duration.py::test_included_in_subcontract_excluded_to_avoid_double_count` [yes]; `integration/test_workspace_ui.py::test_standard_indirect_categories_are_created_as_drafts_without_amounts_and_block_a_complete_estimate` [yes] (added by this audit)
- *Workflow / output:* Commercials tab; Indirect Costs sheet; 16 standard categories created as Draft with no amounts.
- *Limitations / dependencies:* Amounts are in project currency; no staffing-plan/histogram tie-in; staffing is entered as person-month lumps.
- *Acceptance test to mark complete:* All standard categories carry approved amounts with sources; changing the approved duration changes per-month items by the hand-calculated amount.

**IND-02 - Temporary facilities, mobilisation/demobilisation and site establishment as priced scope**  
*Status:* Partial · *needed from level:* 4 · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `data/indirects/indirect_categories.csv`; `app/estimators/indirect.py::compute_indirects`
- *Tests:* `unit/test_indirect_duration.py::test_methods_hand_calculated` [partly] (method arithmetic only)
- *Workflow / output:* Pricing via division A items (99 definitions incl. labour/plant) or indirects.
- *Limitations / dependencies:* No sizing logic (offices, camp, laydown, utilities) and no link from manpower/area to facility quantity. Depends on: DUR-04.
- *Acceptance test to mark complete:* Site establishment is derived from an approved manpower and area schedule using approved unit allowances.

**ENG-01 - Engineering services estimating (discipline man-hours, deliverables, vendor-data review, design allowance)**  
*Status:* Partial · *needed from level:* 1 · *kind:* engine
- *Code:* `app/services/boq.py::set_pricing`; `data/taxonomy/cost_codes.csv`
- *Tests:* `integration/test_full_workflow.py::test_complete_workflow_to_gated_submission_export` [partly] (allowance approvals only)
- *Workflow / output:* Cost code L.01 'Design and engineering allowances'; priceable as an approved allowance or lump sum.
- *Limitations / dependencies:* No engineering deliverable/man-hour model, no discipline rates, no EPC phase split (FEED/detail/procurement support). Depends on: ENG-02.
- *Acceptance test to mark complete:* An engineering package is estimated from a deliverables list x approved hours x discipline rates, with a home-office rate build-up and reconciliation to the allowance.

**ENG-02 - Home-office/overhead/G&A allocation and project-management costs for EPC**  
*Status:* Partial · *needed from level:* 1 · *kind:* engine
- *Code:* `app/estimators/indirect.py::compute_indirects`; `app/estimators/commercial.py::compute_commercial`
- *Tests:* `unit/test_commercial.py::test_markup_method_independent_calculation` [partly] (markup on cost, not home-office build-up)
- *Workflow / output:* Expressible as an indirect item (fixed or % of direct) or via the commercial markup.
- *Limitations / dependencies:* No separate home-office cost pool, labour-burden/overhead rate build-up, or allocation across projects.
- *Acceptance test to mark complete:* Home-office cost is built from approved rates x staffing and shown separately from field indirects and profit.

**PRE-01 - Preliminaries and general requirements (division A): priced as BOQ items/assemblies or as field indirects, with double-count detection between the two**  
*Status:* Partial · *needed from level:* 5 · *kind:* engine
- *Code:* `app/reconciliation/engine.py::collect_findings`; `app/estimators/indirect.py::compute_indirects`; `data/taxonomy/cost_codes.csv`; `data/indirects/indirect_categories.csv`
- *Tests:* `workspaces/test_audit_regressions.py::test_indirect_that_overlaps_priced_preliminaries_is_flagged` [yes] (added by this audit); `reconciliation/test_recon.py::test_duplicate_items_and_cost_in_multiple_packages` [partly] (duplicate detection across items/packages); `unit/test_indirect_duration.py::test_methods_hand_calculated` [yes] (indirect arithmetic)
- *Workflow / output:* Division A (10 sub-trades, 99 catalogue definitions) priced like any BOQ item; or the 16 standard indirect categories; reconciliation flags possible overlap (POSSIBLE_DUPLICATE_INDIRECT).
- *Limitations / dependencies:* The overlap rule is keyword based (false positives/negatives; it was untested before this audit). No preliminaries template, no time-related vs fixed split report by contract form, no site-staff histogram. Depends on: IND-01.
- *Acceptance test to mark complete:* A BOQ with preliminaries items and an overlapping indirect (e.g. security) raises POSSIBLE_DUPLICATE_INDIRECT; time-related and fixed preliminaries are reported separately and reconcile to the estimate.

### G. Taxes, duties, logistics

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| TAX-01 | VAT as dated, verified tax categories; unresolved tax never assumed; tax on tendered schedule per category | IT Implemented and tested | 5 |
| TAX-02 | Import landed-cost build-up: Incoterms, freight, insurance, customs duty, clearance, port charges, inland haulage | MI Missing | 3 |
| TAX-03 | Withholding tax, zakat/income tax treatment, expatriate levy and other employer statutory costs | MI Missing | 3 |
| TAX-04 | Logistics: transport to site, laydown, handling, storage, port-to-site, project-specific logistics plans | PA Partial | 3 |

**TAX-01 - VAT as dated, verified tax categories; unresolved tax never assumed; tax on tendered schedule per category**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/services/commercial.py::propose_tax_category`; `app/services/commercial.py::approve_tax_category`; `app/estimators/estimate.py::tax_rate_for`; `app/estimators/estimate.py::_tax_from_schedule`
- *Tests:* `unit/test_commercial.py::test_unresolved_tax_rate_never_assumed` [yes]; `unit/test_commercial.py::test_fixed_discount_and_multiple_tax_categories` [yes]; `unit/test_library_data.py::test_tax_and_fx_seeds_are_pending_until_a_human_verifies` [yes]
- *Workflow / output:* Commercial tab; final payable only when tax resolves.
- *Limitations / dependencies:* VAT-STD (15%) is seeded Pending Review; zero-rated/exempt/reverse-charge categories are not pre-seeded; tax recoverability stored, unused.
- *Acceptance test to mark complete:* A Commercial Approver verifies VAT-STD against current ZATCA text; zero-rated and exempt supplies priced in the same schedule produce the hand-calculated tax.

**TAX-02 - Import landed-cost build-up: Incoterms, freight, insurance, customs duty, clearance, port charges, inland haulage**  
*Status:* Missing · *needed from level:* 3 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None. Assumption definitions exist (ASMP-F-003/004/005, ASMP-J-013) but no calculation consumes them.
- *Limitations / dependencies:* Closest existing: rate `delivery_basis` text and `L.04 Freight, customs and logistics` cost code (manual items). Depends on: CUR-03.
- *Acceptance test to mark complete:* An imported equipment item is priced FOB -> CIF -> duty -> clearance -> delivered with each step an approved input and FX at the right date.

**TAX-03 - Withholding tax, zakat/income tax treatment, expatriate levy and other employer statutory costs**  
*Status:* Missing · *needed from level:* 3 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None as calculations (assumption definitions ASMP-J-011/012/014 only).
- *Limitations / dependencies:* Out of scope of the cost engine by design unless a client profile requires them. Depends on: SAU-03.
- *Acceptance test to mark complete:* Treatment of each is an explicit approved assumption with a tested effect on cost or price.

**TAX-04 - Logistics: transport to site, laydown, handling, storage, port-to-site, project-specific logistics plans**  
*Status:* Partial · *needed from level:* 3 · *kind:* engine
- *Code:* `app/services/indirects.py::add_indirect`; `app/services/rates.py::propose_rate`
- *Tests:* `procurement/test_procurement.py::test_leveling_normalisation_tax_currency_units` [partly] (delivery included/excluded in levelling)
- *Workflow / output:* Delivery basis recorded on rates/quotes; transport as indirect items.
- *Limitations / dependencies:* No haul/lead-time/laydown model; no per-item logistics factor.
- *Acceptance test to mark complete:* Logistics cost for 50 imported items derived from weights/volumes and approved lane rates.

### H. Project duration, sequencing and resource loading

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| DUR-01 | Time-related costs require a human-approved duration and approved working calendar | IT Implemented and tested | 5 |
| DUR-02 | CPM duration from human-entered tasks (finish-to-start), converted to months with an approved calendar; proposal only | PA Partial | 4 |
| DUR-03 | Labour-hours-derived duration cross-check (formula) | IT Implemented and tested | 4 |
| DUR-04 | Resource loading: manpower/plant histograms and peaks over time | MI Missing | 3 |
| DUR-05 | Construction sequencing, phasing, areas/units and logic-linked cost-to-schedule tie-in | MI Missing | 3 |

**DUR-01 - Time-related costs require a human-approved duration and approved working calendar**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/estimators/indirect.py::compute_indirects`; `app/services/indirects.py::approve_duration`
- *Tests:* `unit/test_indirect_duration.py::test_duration_not_approved_blocks_duration_costs_but_not_fixed` [yes]; `unit/test_indirect_duration.py::test_calendar_missing_flags` [yes]
- *Workflow / output:* Commercials tab.
- *Limitations / dependencies:* Duration is a single project-level figure; per-phase or per-area durations are not supported (DUR-05).
- *Acceptance test to mark complete:* Time-based indirect lines resolve only after duration approval.

**DUR-02 - CPM duration from human-entered tasks (finish-to-start), converted to months with an approved calendar; proposal only**  
*Status:* Partial · *needed from level:* 4 · *kind:* engine
- *Code:* `app/estimators/duration.py::cpm`; `app/services/indirects.py::set_tasks`; `app/services/indirects.py::propose_duration_from_schedule`; `app/api/actions.py::set_schedule_tasks`
- *Tests:* `unit/test_indirect_duration.py::test_cpm` [yes]; `unit/test_indirect_duration.py::test_schedule_tasks_to_duration_proposal_needs_approved_calendar_and_human_approval` [yes] (added by this audit); `integration/test_workspace_ui.py::test_schedule_actions_are_reachable_from_the_api_and_respect_roles` [yes] (added by this audit)
- *Workflow / output:* Actions `set_schedule_tasks` / `propose_duration_from_schedule` (API/UI form data); no UI page or chart.
- *Limitations / dependencies:* Finish-to-start only: no lags, other relationship types, constraints, float/backward pass, calendars/holidays/Ramadan, no import from Primavera/MS Project, no Gantt output. Two defects found and fixed by this audit: the path was untestable from the API and archived projects were not protected.
- *Acceptance test to mark complete:* A 200-task network with SS/FF/lag relationships imported from a schedule file yields the same critical path and finish as the scheduling tool.

**DUR-03 - Labour-hours-derived duration cross-check (formula)**  
*Status:* Implemented and tested · *needed from level:* 4 · *kind:* engine
- *Code:* `app/estimators/duration.py::labour_derived_months`
- *Tests:* `unit/test_indirect_duration.py::test_labour_derived_duration_is_a_formula` [yes]
- *Workflow / output:* Proposal with basis note.
- *Limitations / dependencies:* Assumes constant crew size and no logic between activities.
- *Acceptance test to mark complete:* Matches a hand calculation.

**DUR-04 - Resource loading: manpower/plant histograms and peaks over time**  
*Status:* Missing · *needed from level:* 3 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None.
- *Limitations / dependencies:* Needs a programme linked to hours (EST-10, DUR-05). Depends on: EST-10, DUR-05.
- *Acceptance test to mark complete:* Monthly manpower by craft from the programme x hours; peak and total reconcile to the estimate's total hours.

**DUR-05 - Construction sequencing, phasing, areas/units and logic-linked cost-to-schedule tie-in**  
*Status:* Missing · *needed from level:* 3 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None. `schedule_tasks.cost_code` exists but nothing reads it.
- *Limitations / dependencies:* No phase/area structure on BOQ items; no cost-loaded programme. Depends on: LIB-02.
- *Acceptance test to mark complete:* Costs are assigned to activities; the programme can be re-sequenced and time-dependent costs and escalation update accordingly.

### I. Basis of Estimate, scope definition, maturity and exclusions

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| BOE-01 | Scope register: inclusions, exclusions, qualifications, clarifications (with evidence), cross-checks against priced scope and the offer | IT Implemented and tested | 4 |
| BOE-02 | Assumptions register (322 definitions) with approval, project overrides, validity and impact analysis | IT Implemented and tested | 5 |
| BOE-03 | Basis of Estimate document (scope, design basis, methodology, rate/productivity sources, exclusions, assumptions, risks, maturity, accuracy) | PA Partial | 3 |
| BOE-04 | Estimate classification (AACE or client-specific) with maturity indicators and accuracy range | MI Missing | 3 |
| BOE-05 | Design-maturity/completeness checks (MTO completeness, % engineered, drawing/spec revision control) | PA Partial | 3 |

**BOE-01 - Scope register: inclusions, exclusions, qualifications, clarifications (with evidence), cross-checks against priced scope and the offer**  
*Status:* Implemented and tested · *needed from level:* 4 · *kind:* engine
- *Code:* `app/services/registers.py::add_scope_entry`; `app/services/registers.py::resolve_clarification`; `app/reconciliation/engine.py::collect_findings`
- *Tests:* `reconciliation/test_recon.py::test_scope_mismatches_exclusion_vs_priced` [yes]; `reconciliation/test_recon.py::test_offer_and_pricing_schedule_discrepancies` [yes]; `approvals/test_ai_boundary.py::test_clarification_suggestions_become_open_items_never_resolved` [partly]
- *Workflow / output:* Clarifications & risk tab; Inclusions and Exclusions sheet; offer letter.
- *Limitations / dependencies:* Free text; no clause library or requirement-to-scope traceability matrix.
- *Acceptance test to mark complete:* Every tender requirement maps to a scope entry or clarification; unmapped requirements are listed.

**BOE-02 - Assumptions register (322 definitions) with approval, project overrides, validity and impact analysis**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/services/assumptions.py::set_override`; `app/services/assumptions.py::resolve`; `data/assumptions/assumptions_register.csv`
- *Tests:* `approvals/test_approval_rules.py::test_project_override_does_not_change_global_and_needs_approval` [yes]; `unit/test_library_data.py::test_assumption_register_has_no_invented_numbers` [yes]; `workspaces/test_workspaces.py::test_project_assumption_override_does_not_change_global_default` [yes]
- *Workflow / output:* Assumptions tab; estimate report lists assumptions in use.
- *Limitations / dependencies:* Only a minority of definitions are consumed by an engine (labour hours, plant utilisation, calendar, rounding, waste refs); the rest are documentation obligations.
- *Acceptance test to mark complete:* Every assumption an engine reads is listed in the BoE with value, status, source.

**BOE-03 - Basis of Estimate document (scope, design basis, methodology, rate/productivity sources, exclusions, assumptions, risks, maturity, accuracy)**  
*Status:* Partial · *needed from level:* 3 · *kind:* engine
- *Code:* `app/exports/documents.py::estimate_report_docx`; `app/services/workspaces.py::render_generated_block`
- *Tests:* `integration/test_final_flow.py::test_final_flow_and_gates` [partly] (report is generated; contents not validated against a BoE standard)
- *Workflow / output:* Estimate report (.docx): summary, cost reconciliation, exceptions, assumptions in use, watermark.
- *Limitations / dependencies:* It is an estimate summary, not a BoE: no design-basis/deliverables list, methodology, rate-source summary, maturity or accuracy statement. Depends on: BOE-04.
- *Acceptance test to mark complete:* A BoE generated for a project contains every section of the client's/organisation's BoE template populated from recorded data, with missing sections explicitly shown as missing.

**BOE-04 - Estimate classification (AACE or client-specific) with maturity indicators and accuracy range**  
*Status:* Missing · *needed from level:* 3 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None. ASMP-A-001 (design stage) and ASMP-L-004 (design maturity) are definitions only; nothing stores or checks a class.
- *Limitations / dependencies:* No class field, no profile of required deliverables per class, no accuracy-range output. See the two-systems section of the matrix document.
- *Acceptance test to mark complete:* A selectable classification profile (configuration file) sets required deliverable-maturity checks; the estimate shows its class, unmet criteria and the profile's stated accuracy range, and approval is blocked if mandatory criteria fail.

**BOE-05 - Design-maturity/completeness checks (MTO completeness, % engineered, drawing/spec revision control)**  
*Status:* Partial · *needed from level:* 3 · *kind:* engine
- *Code:* `app/reporting/completeness.py::project_completeness`; `app/services/workspaces.py::outstanding_issues`
- *Tests:* `integration/test_workspace_ui.py::test_create_project_shows_workspace_path_next_action_and_numbered_folders` [partly] (completeness page renders and shows blockers)
- *Workflow / output:* Completeness tab; reconciliation BOQ_ITEM_MISSING_IN_REVISION.
- *Limitations / dependencies:* Counts records; does not assess design maturity. Drawing/spec revisions are recorded text. Depends on: BOE-04.
- *Acceptance test to mark complete:* Completeness lists unresolved design items per discipline against the chosen classification profile.

### J. Escalation, contingency, quantified risk, uncertainty, currency

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| RSK-01 | Contingency with explicit base (direct or direct+indirect) and rate as policy fields; double-count guards | IT Implemented and tested | 5 |
| RSK-02 | Named risk allowances (percentage or fixed) in the commercial policy | IT Implemented and tested | 4 |
| RSK-03 | Risk register (probability, impact, cost exposure, mitigation) | PA Partial | 3 |
| RSK-04 | Quantified risk and uncertainty: expected value, range estimating or Monte Carlo (P50/P80), correlation, contingency derivation | MI Missing | 3 |
| RSK-05 | Escalation: single percentage on an explicit base | PA Partial | 4 |
| CUR-01 | Foreign-currency rates converted with APPROVED, dated FX; unresolved FX leaves the line unpriced | IT Implemented and tested | 4 |
| CUR-02 | Non-SAR project currency with SAR rates converted by approved FX | IT Implemented and tested | 3 |
| CUR-03 | Currency exposure and hedging (multi-currency packages, exposure by currency, FX sensitivity) | MI Missing | 2 |

**RSK-01 - Contingency with explicit base (direct or direct+indirect) and rate as policy fields; double-count guards**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/estimators/commercial.py::compute_commercial`; `app/estimators/commercial.py::validate_policy`
- *Tests:* `unit/test_commercial.py::test_contingency_base_is_explicit_and_changes_result` [yes]; `unit/test_commercial.py::test_policy_validation_and_double_count_guards` [yes]
- *Workflow / output:* Commercial calculation trace; policy approval by Commercial Approver.
- *Limitations / dependencies:* Single project-wide percentage; no per-discipline or risk-derived contingency.
- *Acceptance test to mark complete:* Contingency of x% on the stated base reproduces by hand.

**RSK-02 - Named risk allowances (percentage or fixed) in the commercial policy**  
*Status:* Implemented and tested · *needed from level:* 4 · *kind:* engine
- *Code:* `app/estimators/commercial.py::compute_commercial`
- *Tests:* `unit/test_commercial.py::test_trace_documents_every_step` [partly]; `unit/test_commercial.py::test_policy_validation_and_double_count_guards` [yes]
- *Workflow / output:* Risk allowances in the commercial trace.
- *Limitations / dependencies:* Allowances are entered by hand; they are not derived from the risk register. Depends on: RSK-03.
- *Acceptance test to mark complete:* Each allowance traces to a named, approved risk entry.

**RSK-03 - Risk register (probability, impact, cost exposure, mitigation)**  
*Status:* Partial · *needed from level:* 3 · *kind:* engine
- *Code:* `app/services/registers.py::add_risk`; `app/services/registers.py::list_risks`
- *Tests:* `excel/test_workbooks.py::test_populated_workbook_matches_engine_and_ids` [partly] (risk sheet populated)
- *Workflow / output:* Risk Register sheet; Clarifications & risk tab.
- *Limitations / dependencies:* Stored only: not used by any calculation, reconciliation rule or export. Probability/impact are free text.
- *Acceptance test to mark complete:* Risks have numeric probability and impact distributions and feed RSK-04.

**RSK-04 - Quantified risk and uncertainty: expected value, range estimating or Monte Carlo (P50/P80), correlation, contingency derivation**  
*Status:* Missing · *needed from level:* 3 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None.
- *Limitations / dependencies:* Nothing probabilistic exists in the engines. Depends on: RSK-03.
- *Acceptance test to mark complete:* A seeded Monte Carlo over approved distributions reproduces published P50/P80 within tolerance; contingency derived at a client-selected confidence level.

**RSK-05 - Escalation: single percentage on an explicit base**  
*Status:* Partial · *needed from level:* 4 · *kind:* engine
- *Code:* `app/estimators/commercial.py::compute_commercial`
- *Tests:* `unit/test_commercial.py::test_contingency_base_is_explicit_and_changes_result` [partly] (escalation base shares the validation path)
- *Workflow / output:* Escalation line in the commercial trace.
- *Limitations / dependencies:* No time-phasing against the programme, no index-linked escalation (stored CCI data is not consumed), no per-commodity/labour/currency escalation, no base-date handling. Depends on: DUR-05, RTE-06.
- *Acceptance test to mark complete:* Escalation is computed per cost element over the programme from an approved index and base date with hand-checkable results.

**CUR-01 - Foreign-currency rates converted with APPROVED, dated FX; unresolved FX leaves the line unpriced**  
*Status:* Implemented and tested · *needed from level:* 4 · *kind:* engine
- *Code:* `app/estimators/direct_cost.py::_fx`; `app/services/commercial.py::approve_fx`
- *Tests:* `unit/test_direct_cost.py::test_foreign_currency_requires_approved_fx` [yes]; `procurement/test_procurement.py::test_leveling_normalisation_tax_currency_units` [yes]
- *Workflow / output:* FX_MISSING exception; Settings FX table.
- *Limitations / dependencies:* USD/SAR 3.75 seeded Pending Review. Single rate per pair/date; indirect items are not currency-tagged.
- *Acceptance test to mark complete:* A USD rate converts at the approved dated rate; a Pending Review rate is never used.

**CUR-02 - Non-SAR project currency with SAR rates converted by approved FX**  
*Status:* Implemented and tested · *needed from level:* 3 · *kind:* engine
- *Code:* `app/estimators/direct_cost.py::_Ctx`; `app/estimators/direct_cost.py::_fx`
- *Tests:* `workspaces/test_audit_regressions.py::test_non_sar_project_currency_needs_an_approved_fx_rate_then_converts` [yes] (added by this audit)
- *Workflow / output:* Estimate in the project currency.
- *Limitations / dependencies:* The UI project form does not expose project currency (set through the service/API); commercial policy amounts and tax are not currency-aware.
- *Acceptance test to mark complete:* A USD project with mixed SAR/USD rates produces a USD schedule, with every conversion in the basis text.

**CUR-03 - Currency exposure and hedging (multi-currency packages, exposure by currency, FX sensitivity)**  
*Status:* Missing · *needed from level:* 2 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None.
- *Limitations / dependencies:* Cost lines record currency and FX, but no exposure report or sensitivity exists. Depends on: CUR-01.
- *Acceptance test to mark complete:* A report lists cost by original currency and the effect of +/-x% FX movement.

### K. Supplier quotations, bid levelling and procurement

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| PRO-01 | Procurement needs detection from the strict estimate (missing/expired/unapproved/low-confidence rates), packages by trade | IT Implemented and tested | 4 |
| PRO-02 | RFQ drafting (English; Arabic draft) with XLSX/DOCX export for manual issue; no email sent, no invented contacts | IT Implemented and tested | 4 |
| PRO-03 | Quotation capture, validity/expiry, tax and delivery basis, unit/currency, deviations/exclusions; import from completed RFQ sheet | IT Implemented and tested | 4 |
| PRO-04 | Bid levelling: normalised price (tax, currency, units), coverage, missing items, adjustments (approved), spec differences | IT Implemented and tested | 4 |
| PRO-05 | Supplier selection requiring human approval with reasons and value-threshold role | IT Implemented and tested | 4 |
| PRO-06 | Vendor prequalification, technical bid evaluation scoring, long-lead tracking, vendor data/ITP, PO/subcontract award management | PA Partial | 2 |
| PRO-07 | Subcontract package scope/interface matrix and double-count control across packages | PA Partial | 4 |

**PRO-01 - Procurement needs detection from the strict estimate (missing/expired/unapproved/low-confidence rates), packages by trade**  
*Status:* Implemented and tested · *needed from level:* 4 · *kind:* engine
- *Code:* `app/procurement/needs.py::detect_needs`
- *Tests:* `procurement/test_procurement.py::test_missing_rates_become_procurement_requirements` [yes]; `procurement/test_procurement.py::test_unapproved_and_expired_rates_detected_with_indicative_exposure` [yes]
- *Workflow / output:* Procurement & RFQs tab.
- *Limitations / dependencies:* Packaging is by cost-code division; no custom bid packages or long-lead flags.
- *Acceptance test to mark complete:* Needs register equals the unpriced-line set of the estimate.

**PRO-02 - RFQ drafting (English; Arabic draft) with XLSX/DOCX export for manual issue; no email sent, no invented contacts**  
*Status:* Implemented and tested · *needed from level:* 4 · *kind:* engine
- *Code:* `app/procurement/rfq.py::create_rfq`; `app/procurement/rfq.py::export_xlsx`; `app/procurement/rfq.py::export_docx`
- *Tests:* `procurement/test_procurement.py::test_rfq_generation_content_and_exports` [yes]; `procurement/test_procurement.py::test_arabic_rfq_template_and_unknown_language` [yes]; `procurement/test_procurement.py::test_supplier_contacts_need_a_source` [yes]
- *Workflow / output:* RFQ page; files in '6. Procurement & Quotations'.
- *Limitations / dependencies:* Generic RFQ; no client technical-requirements appendices, ITB forms, vendor-data-requirements lists. Arabic text is a machine draft. Depends on: SAU-06.
- *Acceptance test to mark complete:* Client RFQ template (profile) populated with scope, specs and mandatory forms.

**PRO-03 - Quotation capture, validity/expiry, tax and delivery basis, unit/currency, deviations/exclusions; import from completed RFQ sheet**  
*Status:* Implemented and tested · *needed from level:* 4 · *kind:* engine
- *Code:* `app/procurement/quotes.py::create_quotation`; `app/procurement/quotes.py::import_quotation_lines`; `app/procurement/quotes.py::validity`
- *Tests:* `procurement/test_procurement.py::test_quote_import_from_completed_rfq_sheet` [yes]; `procurement/test_procurement.py::test_quote_validity_and_expiry` [yes]; `procurement/test_procurement.py::test_quote_edit_rules_and_approval` [yes]
- *Workflow / output:* Quotations tab.
- *Limitations / dependencies:* Manual entry/CSV/XLSX; no PDF quotation parsing (optional AI extraction takes pasted text only and is live-unverified).
- *Acceptance test to mark complete:* Quote totals and line values equal the supplier document.

**PRO-04 - Bid levelling: normalised price (tax, currency, units), coverage, missing items, adjustments (approved), spec differences**  
*Status:* Implemented and tested · *needed from level:* 4 · *kind:* engine
- *Code:* `app/procurement/leveling.py::level_package`; `app/procurement/leveling.py::add_adjustment`
- *Tests:* `procurement/test_procurement.py::test_leveling_normalisation_tax_currency_units` [yes]; `procurement/test_procurement.py::test_leveling_missing_items_quantity_difference_discount_and_adjustments` [yes]
- *Workflow / output:* Compare quotations; Quote Comparison sheet.
- *Limitations / dependencies:* Price-only levelling; no weighted technical/commercial scoring or technical-compliance matrix beyond compliance flags.
- *Acceptance test to mark complete:* A 5-bidder package is levelled with each difference explained and reproduces by hand.

**PRO-05 - Supplier selection requiring human approval with reasons and value-threshold role**  
*Status:* Implemented and tested · *needed from level:* 4 · *kind:* engine
- *Code:* `app/procurement/selection.py::propose_selection`; `app/procurement/selection.py::decide_selection`
- *Tests:* `procurement/test_procurement.py::test_supplier_selection_needs_human_approval_and_reasons` [yes]; `procurement/test_procurement.py::test_high_value_selection_requires_commercial_approver` [yes]
- *Workflow / output:* Quotations tab.
- *Limitations / dependencies:* Threshold is a single configured SAR value (approval_thresholds); no award/PO document, delegation-of-authority matrix or multi-stage approval chain.
- *Acceptance test to mark complete:* Selection cannot be approved without reason when not lowest like-for-like; threshold role enforced.

**PRO-06 - Vendor prequalification, technical bid evaluation scoring, long-lead tracking, vendor data/ITP, PO/subcontract award management**  
*Status:* Partial · *needed from level:* 2 · *kind:* engine
- *Code:* `app/services/suppliers.py::qualify_supplier`
- *Tests:* `procurement/test_procurement.py::test_supplier_contacts_need_a_source` [partly] (supplier master data only)
- *Workflow / output:* Supplier directory with qualification flag.
- *Limitations / dependencies:* No scoring model, award/PO documents, delivery schedules, expediting, inspection or vendor-document control.
- *Acceptance test to mark complete:* A package award produces an award record, delivery milestones and technical/commercial scores traceable to the bid evaluation.

**PRO-07 - Subcontract package scope/interface matrix and double-count control across packages**  
*Status:* Partial · *needed from level:* 4 · *kind:* engine
- *Code:* `app/reconciliation/engine.py::collect_findings`; `app/ai/service.py::spec_diff`
- *Tests:* `reconciliation/test_recon.py::test_double_count_subcontract_is_critical` [yes]; `reconciliation/test_recon.py::test_duplicate_items_and_cost_in_multiple_packages` [yes]
- *Workflow / output:* DOUBLE_COUNT / PRICED_BUT_EXCLUDED findings.
- *Limitations / dependencies:* No interface-responsibility matrix; detection is rule-based with false positives/negatives.
- *Acceptance test to mark complete:* Interface matrix completeness is reported per package.

### L. Cost control: CBS roll-ups, benchmarks, cash flow, forecasts, change orders, revisions

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| CTL-01 | Actual-cost capture with mandatory source; estimate-vs-actual and productivity variance by cost code/resource | IT Implemented and tested | 4 |
| CTL-02 | Estimate revision control: frozen versions, version differences, approval status per version | IT Implemented and tested | 4 |
| CTL-03 | Benchmarking: cost ratios, historical analogues, rate/productivity reasonableness checks | PA Partial | 3 |
| CTL-04 | Cash flow / S-curve / payment-schedule forecast and financing cost | MI Missing | 3 |
| CTL-05 | Forecasting and earned-value control during execution | MI Missing | 1 |
| CTL-06 | Change orders / variation management after award (pricing, approval, audit, cumulative effect) | MI Missing | 1 |
| CTL-07 | Cost roll-up by CBS level (division, sub-trade, cost code) | PA Partial | 4 |

**CTL-01 - Actual-cost capture with mandatory source; estimate-vs-actual and productivity variance by cost code/resource**  
*Status:* Implemented and tested · *needed from level:* 4 · *kind:* engine
- *Code:* `app/reporting/history.py::record_actual`; `app/reporting/history.py::estimate_vs_actual`; `app/reporting/history.py::productivity_variance`
- *Tests:* `integration/test_backup_datasets_cli.py::test_actuals_need_a_source_and_variance_uses_only_entered_data` [yes]
- *Workflow / output:* Reports tab (enter actual; variance tables).
- *Limitations / dependencies:* Manual entry; no ledger import; no commitment tracking.
- *Acceptance test to mark complete:* Import a project cost ledger and reconcile variance to ledger totals.

**CTL-02 - Estimate revision control: frozen versions, version differences, approval status per version**  
*Status:* Implemented and tested · *needed from level:* 4 · *kind:* engine
- *Code:* `app/services/estimates.py::freeze_version`; `app/reconciliation/engine.py::collect_findings`
- *Tests:* `reconciliation/test_recon.py::test_version_difference_and_report` [yes]; `integration/test_final_flow.py::test_final_flow_and_gates` [yes]
- *Workflow / output:* Reconciliation tab versions list.
- *Limitations / dependencies:* No revision-comparison report by cost code; only a finding.
- *Acceptance test to mark complete:* Compare v1 and v2 by CBS code with explained deltas.

**CTL-03 - Benchmarking: cost ratios, historical analogues, rate/productivity reasonableness checks**  
*Status:* Partial · *needed from level:* 3 · *kind:* engine
- *Code:* `app/ai/service.py::find_historical`; `app/reporting/history.py::rate_changes`
- *Tests:* `approvals/test_ai_boundary.py::test_deterministic_features_work_without_any_ai` [partly] (find_historical returns [] on empty history; quality untested)
- *Workflow / output:* Similar-item search on the Mapping page.
- *Limitations / dependencies:* Keyword search of past BOQ items only. No cost/m2, cost/inch-dia, MH/unit or %-of-direct benchmark library; ASMP-L-013 (deviation threshold) is a definition only.
- *Acceptance test to mark complete:* Estimate is compared with approved benchmark ranges; deviations beyond an approved threshold raise findings.

**CTL-04 - Cash flow / S-curve / payment-schedule forecast and financing cost**  
*Status:* Missing · *needed from level:* 3 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None.
- *Limitations / dependencies:* Needs a cost-loaded programme and payment terms (DUR-05). Depends on: DUR-05.
- *Acceptance test to mark complete:* Monthly cash flow from a cost-loaded programme and approved payment terms reconciles to the total price.

**CTL-05 - Forecasting and earned-value control during execution**  
*Status:* Missing · *needed from level:* 1 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None.
- *Limitations / dependencies:* Application scope ends at tender; no progress, commitments or forecast-to-complete. Depends on: CTL-01, LIB-02.
- *Acceptance test to mark complete:* EAC/ETC from actuals and progress per control account.

**CTL-06 - Change orders / variation management after award (pricing, approval, audit, cumulative effect)**  
*Status:* Missing · *needed from level:* 1 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None. Pre-award BOQ change requests exist (SCO-05) but they are not contract variations.
- *Limitations / dependencies:* No variation register, no pricing from the approved library against a baseline, no approval chain with client reference. Depends on: CTL-02.
- *Acceptance test to mark complete:* A variation is priced from approved rates against the awarded baseline, approved, and cumulatively reported.

**CTL-07 - Cost roll-up by CBS level (division, sub-trade, cost code)**  
*Status:* Partial · *needed from level:* 4 · *kind:* engine
- *Code:* `app/estimators/types.py::DirectCostResult`; `app/reporting/history.py::estimate_vs_actual`
- *Tests:* `integration/test_final_flow.py::test_estimate_numbers` [partly] (totals tested, per-code roll-up not)
- *Workflow / output:* `DirectCostResult.by_cost_code()` feeds variance reports; no stand-alone roll-up page/report.
- *Limitations / dependencies:* Direct cost only; indirects/commercials not allocated to codes in a report. Depends on: LIB-01.
- *Acceptance test to mark complete:* Roll-up report by any level whose total equals the estimate.

### M. Commissioning, start-up, handover, close-out

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| CLO-01 | Testing, pre-commissioning, commissioning, start-up and performance tests | PA Partial | 3 |
| CLO-02 | Handover documentation, training, O&M manuals, warranties/defects-liability and spares | PA Partial | 4 |
| CLO-03 | Retention, bonds, advance payments, financing and final-account/close-out costing | MI Missing | 3 |

**CLO-01 - Testing, pre-commissioning, commissioning, start-up and performance tests**  
*Status:* Partial · *needed from level:* 3 · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (cost codes exist)
- *Workflow / output:* Priceable via L.09, H.13, I.10, A.08 and commissioning labour definitions.
- *Limitations / dependencies:* No system/loop-based commissioning model, vendor-representative, consumables/spares, or start-up support build-up; no commissioning sequencing. Depends on: EST-12.
- *Acceptance test to mark complete:* Commissioning cost is derived from a systems/loops list with approved hours, vendor-rep rates and consumables.

**CLO-02 - Handover documentation, training, O&M manuals, warranties/defects-liability and spares**  
*Status:* Partial · *needed from level:* 4 · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (cost codes exist)
- *Workflow / output:* Priceable as items under L.07/L.08/A.10.
- *Limitations / dependencies:* No warranty-reserve or spares-list logic.
- *Acceptance test to mark complete:* Warranty/DLP reserve derived from an approved method and period.

**CLO-03 - Retention, bonds, advance payments, financing and final-account/close-out costing**  
*Status:* Missing · *needed from level:* 3 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None. ASMP-I-019..I-028 are definitions only.
- *Limitations / dependencies:* Not consumed by the commercial engine. Depends on: CTL-04.
- *Acceptance test to mark complete:* Bond/retention/financing costs derive from approved terms and the cash-flow forecast.

### N. Saudi-specific requirements and configurable client compliance profiles

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| SAU-01 | Saudi basics: SAR default, region applicability by code (no multipliers), Arabic BOQ headers/descriptions, Arabic RFQ draft | IT Implemented and tested | 5 |
| SAU-02 | VAT 15% as a dated, verified category (seeded Pending Review) with verification evidence | IT Implemented and tested | 5 |
| SAU-03 | Saudi labour cost rules: Saudization/Nitaqat, expatriate levy, iqama and visa, GOSI, end-of-service, Ramadan and overtime working-hours rules | MI Missing | 2 |
| SAU-04 | Local content / in-kingdom value (e.g. IKTVA-type evaluation), national procurement preferences | MI Missing | 1 |
| SAU-05 | Saudi Building Code, authority fees/permits, municipal and utility approvals | PA Partial | 4 |
| SAU-06 | Configurable client compliance profiles (mandatory forms, templates, code lists, rules, estimate classification, approvals) per client | MI Missing | 1 |
| SAU-07 | Saudi Aramco-type project requirements (controlled standards, forms, estimating procedures, vendor lists) | MI Missing | 1 |

**SAU-01 - Saudi basics: SAR default, region applicability by code (no multipliers), Arabic BOQ headers/descriptions, Arabic RFQ draft**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `data/regions/regions.csv`; `app/imports/boq.py::detect_header`; `app/procurement/rfq.py::create_rfq`
- *Tests:* `imports/test_boq_import.py::test_arabic_headers` [yes]; `procurement/test_procurement.py::test_arabic_rfq_template_and_unknown_language` [yes]; `unit/test_schedule_resolution.py::test_resolution_outcomes` [partly] (region applicability)
- *Workflow / output:* Region codes in rates/projects.
- *Limitations / dependencies:* 6 regions; UI is English only (no RTL); Arabic RFQ is a machine draft; no Hijri calendar.
- *Acceptance test to mark complete:* Native review of Arabic outputs; region list matches the client's.

**SAU-02 - VAT 15% as a dated, verified category (seeded Pending Review) with verification evidence**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/services/refdata.py::seed_tax_categories`; `app/services/commercial.py::approve_tax_category`
- *Tests:* `unit/test_library_data.py::test_tax_and_fx_seeds_are_pending_until_a_human_verifies` [yes]
- *Workflow / output:* Commercial tab: tax categories.
- *Limitations / dependencies:* Not yet verified/approved by a human against current ZATCA text; no e-invoicing.
- *Acceptance test to mark complete:* Commercial Approver approves with evidence; estimate resolves tax.

**SAU-03 - Saudi labour cost rules: Saudization/Nitaqat, expatriate levy, iqama and visa, GOSI, end-of-service, Ramadan and overtime working-hours rules**  
*Status:* Missing · *needed from level:* 2 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None. Working-hours rules (HRSD) are recorded as a reference note only; labour components are generic.
- *Limitations / dependencies:* Would need approved rule data (not available in-repo) and a labour build-up that uses it. Depends on: RTE-02.
- *Acceptance test to mark complete:* A labour rate is built from approved statutory components and a Ramadan/overtime pattern, reproducing the company's payroll costing.

**SAU-04 - Local content / in-kingdom value (e.g. IKTVA-type evaluation), national procurement preferences**  
*Status:* Missing · *needed from level:* 1 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None.
- *Limitations / dependencies:* Client-specific controlled methodology required; none is in the repository. Depends on: SAU-06.
- *Acceptance test to mark complete:* Scoring inputs captured per bid package and the client's published scoring method reproduced from controlled documents.

**SAU-05 - Saudi Building Code, authority fees/permits, municipal and utility approvals**  
*Status:* Partial · *needed from level:* 4 · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (L.02 'Authority fees and permits' exists)
- *Workflow / output:* Fees/permits as priced items under L.02.
- *Limitations / dependencies:* SBC not accessible to the build environment (documented); no code-driven scope or cost checks.
- *Acceptance test to mark complete:* Permit/fee schedule per authority maintained as approved data.

**SAU-06 - Configurable client compliance profiles (mandatory forms, templates, code lists, rules, estimate classification, approvals) per client**  
*Status:* Missing · *needed from level:* 1 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None. Reconciliation rules are configurable (config/reconciliation_rules.json) but there is no client-profile layer and no client template mechanism beyond editing files.
- *Limitations / dependencies:* Needs a profile schema, controlled-document references, versioning, and per-profile templates/validators. See the profile design in ESTIMATING_GAP_ROADMAP.md. Depends on: BOE-04, LIB-02.
- *Acceptance test to mark complete:* Selecting a profile applies its CBS/WBS mapping, forms, class definitions and mandatory checks; export is blocked for unmet mandatory items; the profile records which controlled document/revision it implements.

**SAU-07 - Saudi Aramco-type project requirements (controlled standards, forms, estimating procedures, vendor lists)**  
*Status:* Missing · *needed from level:* 1 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None. No Aramco controlled document is in the repository and no compliance is claimed. Public-source research found only unofficial copies of Aramco standards (SRC-016).
- *Limitations / dependencies:* Compliance can only be claimed against documents the user is authorised to hold; implement through SAU-06 using those documents. Depends on: SAU-06.
- *Acceptance test to mark complete:* The owner's controlled requirements (with revisions) are loaded as a profile and every mandatory item is traceably checked.

### O. Approval gates, audit, snapshots, reproducibility, commercial exports

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| GOV-01 | Server-side role-based approvals for every commercially significant decision | IT Implemented and tested | 5 |
| GOV-02 | AI/automation cannot approve; AI output is review-pending; automated source code cannot reach approve/publish | IT Implemented and tested | 5 |
| GOV-03 | Hash-chained audit log; backup validation re-verifies it (tamper-evident, not tamper-proof) | IT Implemented and tested | 5 |
| GOV-04 | Estimate input snapshots: verify pinned rate rows unchanged, list newer approved rates, replay direct cost from the snapshot | IT Implemented and tested | 4 |
| GOV-05 | Full replay of a frozen estimate (indirects, commercial, tax, schedule) from its snapshot | PA Partial | 3 |
| GOV-06 | Reconciliation: 37 configurable rules, exceptions, final gate re-run at approval and export | IT Implemented and tested | 5 |
| GOV-07 | Gated commercial exports: SUBMISSION READY only after approved version + offer + tender-export approval + fresh reconciliation; otherwise PRELIMINARY watermark | IT Implemented and tested | 5 |
| GOV-08 | No autonomous tender submission: no e-mail/FTP/portal automation; outputs are files for a human to send | IT Implemented and tested | 5 |
| GOV-09 | Backup/restore/validation and project package export (workspace, imports, DB) | IT Implemented and tested | 4 |
| GOV-10 | Numbered project workspaces, project CLAUDE.md, isolation between projects, copy-only legacy migration | IT Implemented and tested | 4 |
| GOV-11 | Self-approval segregation (configurable) | IT Implemented and tested | 4 |
| GOV-12 | Multi-user operation, concurrency, security hardening (TLS, CSRF tokens, lockout, MFA/SSO) | PA Partial | 2 |

**GOV-01 - Server-side role-based approvals for every commercially significant decision**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/approvals/policy.py::POLICY`; `app/approvals/engine.py::authorize`
- *Tests:* `approvals/test_approval_rules.py::test_policy_role_matrix_has_no_ai_and_commercial_gates` [yes]; `integration/test_api_ui.py::test_server_side_permissions_on_the_api` [yes]; `integration/test_api_ui.py::test_ui_forms_enforce_permissions_server_side` [yes]
- *Workflow / output:* Approvals page; approvals table.
- *Limitations / dependencies:* Role matrix defined in code; no per-project or per-value delegation of authority beyond the supplier-selection threshold.
- *Acceptance test to mark complete:* Every approve/reject path refuses an unauthorised role.

**GOV-02 - AI/automation cannot approve; AI output is review-pending; automated source code cannot reach approve/publish**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/ai/service.py::_store`; `app/approvals/engine.py::authorize`
- *Tests:* `approvals/test_approval_rules.py::test_ai_cannot_approve_anything` [yes]; `approvals/test_approval_rules.py::test_ai_package_cannot_reach_approval_or_mutation_code` [yes]; `approvals/test_source_boundary.py::test_automated_source_code_never_references_approval_or_publication_functions` [yes]
- *Workflow / output:* ai_suggestions Pending Review.
- *Limitations / dependencies:* Structural (AST) and behavioural tests cover app/ai and the source/refresh modules; a new module outside those packages would need its own review and boundary test.
- *Acceptance test to mark complete:* No code path from automation to an approved state.

**GOV-03 - Hash-chained audit log; backup validation re-verifies it (tamper-evident, not tamper-proof)**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/services/audit.py::log`; `app/services/audit.py::verify_chain`
- *Tests:* `approvals/test_approval_rules.py::test_audit_chain_detects_tampering` [yes]; `integration/test_backup_datasets_cli.py::test_backup_with_tampered_audit_chain_flagged` [yes]
- *Workflow / output:* `audit-verify`; Settings page.
- *Limitations / dependencies:* Someone with DB write access can rebuild the chain; no external anchoring or signing.
- *Acceptance test to mark complete:* Chain verification passes after restore; any edit is detected.

**GOV-04 - Estimate input snapshots: verify pinned rate rows unchanged, list newer approved rates, replay direct cost from the snapshot**  
*Status:* Implemented and tested · *needed from level:* 4 · *kind:* engine
- *Code:* `app/services/snapshots.py::store_snapshot`; `app/services/snapshots.py::verify_snapshot`; `app/services/snapshots.py::replay_direct_cost`
- *Tests:* `workspaces/test_workspaces.py::test_snapshot_keeps_frozen_estimate_reproducible_after_a_new_rate_is_approved` [yes]; `sources/test_rate_pipeline.py::test_publication_creates_new_pending_version_keeps_old_and_does_not_mutate_frozen_estimate` [yes]
- *Workflow / output:* `project verify-snapshot`; Workspace tab.
- *Limitations / dependencies:* Snapshots exist only for versions frozen after migration 0007.
- *Acceptance test to mark complete:* Approve a new global rate; replay of an old version equals its frozen direct cost.

**GOV-05 - Full replay of a frozen estimate (indirects, commercial, tax, schedule) from its snapshot**  
*Status:* Partial · *needed from level:* 3 · *kind:* engine
- *Code:* `app/services/snapshots.py::replay_direct_cost`
- *Tests:* `workspaces/test_workspaces.py::test_snapshot_keeps_frozen_estimate_reproducible_after_a_new_rate_is_approved` [partly] (direct cost only)
- *Workflow / output:* Snapshot JSON stores policy, tax, indirect rows and duration for audit.
- *Limitations / dependencies:* Replay engine covers direct cost only; the commercial tail is not recomputed.
- *Acceptance test to mark complete:* `replay_estimate` equals every frozen total.

**GOV-06 - Reconciliation: 37 configurable rules, exceptions, final gate re-run at approval and export**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/reconciliation/engine.py::run_reconciliation`; `app/reconciliation/engine.py::final_gate`; `config/reconciliation_rules.json`
- *Tests:* `reconciliation/test_recon.py::test_clean_project_has_no_blocking_findings` [yes]; `reconciliation/test_recon.py::test_exceptions_policy_and_roles` [yes]; `reconciliation/test_recon.py::test_high_exception_needs_commercial_role_and_configurable_rules` [yes]
- *Workflow / output:* Reconciliation tab; reconciliation_report xlsx.
- *Limitations / dependencies:* Rule coverage is for the generic estimate; no industrial/EPC rules (e.g. MTO completeness, weld/NDT counts).
- *Acceptance test to mark complete:* Each rule has a positive and negative test; client rules can be added by configuration.

**GOV-07 - Gated commercial exports: SUBMISSION READY only after approved version + offer + tender-export approval + fresh reconciliation; otherwise PRELIMINARY watermark**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/services/estimates.py::export_submission`; `app/services/estimates.py::approve_tender_export`; `app/exports/documents.py::client_pricing_schedule`
- *Tests:* `integration/test_final_flow.py::test_final_flow_and_gates` [yes]; `integration/test_final_flow.py::test_critical_blocks_final` [yes]; `integration/test_full_workflow.py::test_complete_workflow_to_gated_submission_export` [yes]
- *Workflow / output:* Reports tab; pricing schedule xlsx, offer letter docx, estimate report docx.
- *Limitations / dependencies:* Outputs are the application's own formats, not client-mandated forms (SAU-06).
- *Acceptance test to mark complete:* Export refused when any gate fails; produced when all pass.

**GOV-08 - No autonomous tender submission: no e-mail/FTP/portal automation; outputs are files for a human to send**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/exports/documents.py::client_pricing_schedule`; `app/sources/base.py::HttpFetcher`
- *Tests:* `workspaces/test_audit_regressions.py::test_application_has_no_autonomous_submission_channel` [yes] (added by this audit (static scan of imports and the fetcher))
- *Workflow / output:* Files in '8. Commercial Submission' / '10. Exports & Archive'.
- *Limitations / dependencies:* A static scan cannot prove a user script will not submit; it proves the application has no channel.
- *Acceptance test to mark complete:* Static scan stays green; any new outbound channel requires an explicit approved design.

**GOV-09 - Backup/restore/validation and project package export (workspace, imports, DB)**  
*Status:* Implemented and tested · *needed from level:* 4 · *kind:* engine
- *Code:* `app/services/backup.py::create_backup`; `app/services/backup.py::restore_backup`; `app/services/backup.py::export_project_package`
- *Tests:* `integration/test_backup_datasets_cli.py::test_backup_validate_restore_cycle` [yes]; `integration/test_backup_datasets_cli.py::test_corrupt_backup_is_rejected_and_nothing_changes` [yes]; `integration/test_backup_datasets_cli.py::test_project_package_and_archive` [yes]
- *Workflow / output:* `backup`, `validate-backup`, `restore --yes`, `export-project`.
- *Limitations / dependencies:* Not encrypted; local files only.
- *Acceptance test to mark complete:* Restore on a clean machine reproduces estimates and audit chain.

**GOV-10 - Numbered project workspaces, project CLAUDE.md, isolation between projects, copy-only legacy migration**  
*Status:* Implemented and tested · *needed from level:* 4 · *kind:* engine
- *Code:* `app/services/workspaces.py::ensure_workspace`; `app/services/workspace_migration.py::migrate`
- *Tests:* `workspaces/test_workspaces.py::test_new_project_creates_complete_workspace` [yes]; `workspaces/test_workspaces.py::test_project_isolation_files_and_quotes_stay_in_their_own_workspace` [yes]; `workspaces/test_cli_and_migration.py::test_workspace_migration_dry_run_then_copy_without_destroying_legacy_files` [yes]
- *Workflow / output:* `project create/refresh/index`; Workspace tab.
- *Limitations / dependencies:* No per-workspace ACL; single local user model.
- *Acceptance test to mark complete:* Two projects never share files or quotations.

**GOV-11 - Self-approval segregation (configurable)**  
*Status:* Implemented and tested · *needed from level:* 4 · *kind:* engine
- *Code:* `app/approvals/engine.py::authorize`
- *Tests:* `approvals/test_approval_rules.py::test_self_approval_can_be_disabled` [yes]
- *Workflow / output:* KSA_ALLOW_SELF_APPROVAL=false.
- *Limitations / dependencies:* Off by default (single-user MVP default).
- *Acceptance test to mark complete:* With the setting off, no user can approve a record they created (admin exempt).

**GOV-12 - Multi-user operation, concurrency, security hardening (TLS, CSRF tokens, lockout, MFA/SSO)**  
*Status:* Partial · *needed from level:* 2 · *kind:* engine
- *Code:* `app/main.py::SerializeRequests`; `app/services/auth.py::authenticate`
- *Tests:* `integration/test_api_ui.py::test_authentication_required_and_bad_tokens_rejected` [partly] (auth basics only)
- *Workflow / output:* Local single-user/small-team tool.
- *Limitations / dependencies:* Requests are serialised; no TLS, CSRF token, lockout, MFA or SSO; not for internet exposure.
- *Acceptance test to mark complete:* Security review passed and load-tested with concurrent estimators.

### P. Excel and document outputs

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| OUT-01 | 27-sheet master workbook + 10 standalone workbooks + 2 Word templates, spec-driven, recalculated and checked with LibreOffice | IT Implemented and tested | 5 |
| OUT-02 | Round-trip import: edits become drafts/proposals; status/approval columns and forged values ignored; formula tampering detected | IT Implemented and tested | 5 |
| OUT-03 | Microsoft Excel compatibility (recalculation on open, MINIFS, protection, validations) | IU Implemented but unverified | 5 |
| OUT-04 | Client pricing schedule, letter of offer and estimate report with exact reconciliation, hash-matched offer and visible exceptions | IT Implemented and tested | 5 |
| OUT-05 | Client-specific tender forms/schedules of rates and bilingual deliverables | MI Missing | 2 |

**OUT-01 - 27-sheet master workbook + 10 standalone workbooks + 2 Word templates, spec-driven, recalculated and checked with LibreOffice**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/excel/master.py::build_master`; `app/excel/templates.py::generate_all`; `app/excel/recalc.py::verify_workbook`
- *Tests:* `excel/test_workbooks.py::test_required_sheets_present_and_ordered` [yes]; `excel/test_workbooks.py::test_libreoffice_recalculation_has_no_errors_or_mismatches` [yes] (LibreOffice only); `excel/test_workbooks.py::test_populated_workbook_matches_engine_and_ids` [yes]
- *Workflow / output:* `export-workbook`, `verify-workbook`, Reports tab download.
- *Limitations / dependencies:* Master export of a 20,000-item project took ~62 s (SCO-09).
- *Acceptance test to mark complete:* Round-trip and recalculation clean on a pilot project in LibreOffice and Excel.

**OUT-02 - Round-trip import: edits become drafts/proposals; status/approval columns and forged values ignored; formula tampering detected**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/excel/roundtrip.py::import_master`; `app/excel/roundtrip.py::validate_structure`
- *Tests:* `excel/test_workbooks.py::test_roundtrip_edits_become_drafts_and_approval_columns_are_ignored` [yes]; `excel/test_workbooks.py::test_structure_validation_detects_tampering` [yes]; `excel/test_workbooks.py::test_round_trip_into_a_fresh_project_reproduces_the_boq` [yes]
- *Workflow / output:* Reports tab re-import.
- *Limitations / dependencies:* Covers the 27 master sheets documented in EXCEL_WORKBOOK_GUIDE; unsupported sheets are ignored, not imported. Imports of very large workbooks are untested.
- *Acceptance test to mark complete:* Edited workbook import creates only drafts.

**OUT-03 - Microsoft Excel compatibility (recalculation on open, MINIFS, protection, validations)**  
*Status:* Implemented but unverified · *needed from level:* 5 · *kind:* engine
- *Code:* `app/excel/builder.py::write_sheet`
- *Tests:* `excel/test_workbooks.py::test_libreoffice_recalculation_has_no_errors_or_mismatches` [partly] (LibreOffice is not Excel)
- *Workflow / output:* Workbooks open in LibreOffice; fullCalcOnLoad set.
- *Limitations / dependencies:* Microsoft Excel has never been available to this project.
- *Acceptance test to mark complete:* A person opens each template and the populated master in Microsoft Excel 365 and 2019 and confirms recalculation, validations and protection.

**OUT-04 - Client pricing schedule, letter of offer and estimate report with exact reconciliation, hash-matched offer and visible exceptions**  
*Status:* Implemented and tested · *needed from level:* 5 · *kind:* engine
- *Code:* `app/exports/documents.py::client_pricing_schedule`; `app/exports/documents.py::estimate_report_docx`; `app/services/offers.py::generate_offer`; `app/estimators/pricing_schedule.py::build_schedule`
- *Tests:* `unit/test_schedule_resolution.py::test_schedule_spread_reconciles_exactly_to_net_price` [yes]; `reconciliation/test_recon.py::test_offer_and_pricing_schedule_discrepancies` [yes]
- *Workflow / output:* Reports tab.
- *Limitations / dependencies:* Application formats only; offer text is a draft for legal review.
- *Acceptance test to mark complete:* Schedule total equals net price to the halala (or the bounded rounding variance is reported).

**OUT-05 - Client-specific tender forms/schedules of rates and bilingual deliverables**  
*Status:* Missing · *needed from level:* 2 · *kind:* engine
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None.
- *Limitations / dependencies:* Depends on client profiles (SAU-06) and templates the user is authorised to hold. Depends on: SAU-06.
- *Acceptance test to mark complete:* Each mandatory client form is generated or pre-filled from recorded data.

<!-- DETAIL_END -->

## 6. Defects found by the audit and fixed (each with a regression test)
| # | Defect | Evidence | Fix | Test |
|---|---|---|---|---|
| 1 | Estimate computation was **O(n²)** in BOQ size (per-item linear scan for the tax category): 20,000 items took 13.8 s per page view | profile: `estimate.py` genexpr 2.2 s of 4.7 s at 8,000 items | single-pass dict lookup | `test_estimate_computation_scales_roughly_linearly_with_boq_size` (fails on the old code, passes now) |
| 2 | **PDF text extraction never worked on a default install**: `pypdf` was imported but not a declared dependency (tender PDFs were silently "indexed but not text-extracted"); no test had ever extracted a real PDF/DOCX/XLSX | `import pypdf` failed in the project venv | `pypdf>=4.0` added to `pyproject.toml` | `test_pypdf_is_a_declared_dependency…`, `test_real_pdf_docx_and_xlsx_text_is_extracted_and_image_only_pdf_is_reported` |
| 3 | The schedule→duration path (`set_tasks`, `propose_duration_from_schedule`) had **no test and no API/UI action** although the Gantt skill relied on it | grep of tests/actions | actions `set_schedule_tasks`, `propose_duration_from_schedule` added; tests for CPM result, calendar requirement, human approval | `test_schedule_tasks_to_duration_proposal_…`, `test_schedule_actions_are_reachable_from_the_api_and_respect_roles` |
| 4 | **Archived (read-only) projects accepted** schedule-task, duration-proposal changes; duplicate task codes collapsed silently | code review | `require_active` on the three functions; duplicate task codes rejected | `test_archived_project_refuses_schedule_and_duration_changes` |
| 5 | Untested claims: what-if impact numbers, non-SAR project currency, `add_standard_indirects`, absence of an outbound submission channel | test inventory | tests added | `test_what_if_…`, `test_non_sar_project_currency_…`, `test_standard_indirect_categories_…`, `test_application_has_no_autonomous_submission_channel` |

Gaps that were **not** fixed because they are features, not defects, are in [ESTIMATING_GAP_ROADMAP.md](ESTIMATING_GAP_ROADMAP.md).

## 7. Maintaining this matrix
Edit `docs/capability_matrix.json`, run `python scripts/gen_capability_matrix.py`, run `python -m pytest tests/unit/test_capability_matrix.py`. Rules enforced by the test: Missing ⇒ no code and no tests claimed; Implemented-and-tested ⇒ at least one *yes* test; Partial/Unverified ⇒ code cited and limitations stated; every record has an acceptance test; every cited file, symbol and test exists; dependencies exist; the rendered page is current.
Changing a status upward requires the record's acceptance test to be implemented as an automated test (or, for live/Excel items, a dated manual verification recorded in `docs/DEVELOPMENT_AUDIT.md`).
