# Estimating capability matrix (five-level audit)

Audit date: 2026-10-13, repository state `ab05e06` plus the fixes listed in §6; re-assessed after iteration 4 (statuses below are the current ones). Scope: what a cost-estimation engineer in Saudi Arabia can actually do with this application today, from basic building estimates to major industrial/EPC estimates.
**Method rule:** a feature counts only if code exists, a test exercises the behaviour, and (where possible) it was run. Templates, UI screens, documentation, assumption definitions, cost codes and skills are *not* evidence of capability.
The machine-readable source is [`capability_matrix.json`](capability_matrix.json); this page's tables are rendered from it (`python scripts/gen_capability_matrix.py`) and `tests/unit/test_capability_matrix.py` verifies that every code path, symbol and test it cites exists and that status claims are consistent with their evidence.

## 1. Bottom line
*Update 2026-10-13 (iteration 4): the audit's missing engine capabilities were built and tested - see §6 and [DEVELOPMENT_AUDIT.md](DEVELOPMENT_AUDIT.md) §9. The first audit (commit `907fce6`) found 30 Missing and 42 Partial records; the roll-up and tables below are the current state.*
* **A generic building/MEP estimate (Levels 5–4)** can be produced end-to-end *structurally*: human-measured BOQ → mapping → assembly/rate pricing → indirects → commercial chain → reconciliation → approvals → gated export. The engine is well tested. **But the content that makes an estimate real is absent**: the library has **0 approved real Saudi rates** and **no productivity/consumption data**; every real estimate is Preliminary until a human loads and approves that data (LIB-07, LIB-08). These two records stay *Missing* because they are data, not code.
* **Infrastructure/large-project estimating (Level 3)** now has landed-cost build-up, resource loading and man-hour histograms, cash flow, quantified risk (EV + seeded Monte Carlo), time-phased escalation, a Basis-of-Estimate generator, a scheme-driven estimate classification and a WBS/CBS roll-up. All of these are **frameworks fed by company-supplied, approved parameters** - the software ships no factor, rate, percentage, range or scheme.
* **Industrial estimating (Levels 2–1, incl. Aramco-type work)**: industrial units, an industrial definitions pack, 23 take-off templates (piping, instruments, cables, steel, tanks, coatings, insulation, scaffolding, lifting, specialist services, shutdown, modularisation, temporary facilities, commissioning), productivity factors, method alternatives, engineering/home-office/reserve proposals, labour statutory build-up, variations, earned value, bid evaluation and a client-profile framework now exist. **They are all *Partial* where a discipline needs real factors or a client's own documents.** Level 1 remains **not supported** because the owner-controlled requirements record (SAU-07) is Missing. **No Saudi Aramco compliance is claimed or implied**; no Aramco controlled document is in the repository.
* Governance is the strongest part: server-side approvals, AI/automation boundaries, audit chain, input snapshots (now with full-estimate replay), fingerprinted gates and no autonomous submission are implemented and tested; the web app is hardened (same-origin check, headers, lockout, TLS flags) for a small trusted team, not for internet exposure.

### Roll-up by capability level (engine capabilities; data readiness reported separately)
<!-- ROLLUP_BEGIN -->
| Level | Name | Required capabilities (engine) | IT | IU | PA | MI | Verdict (engine) |
|---|---|---|---|---|---|---|---|
| 5 | Basic estimating | 37 | 33 | 1 | 3 | 0 | **CONDITIONALLY SUPPORTED (partial / unverified items)** |
| 4 | Building and MEP contractor estimating | 76 | 58 | 2 | 16 | 0 | **CONDITIONALLY SUPPORTED (partial / unverified items)** |
| 3 | Infrastructure and large-project estimating | 99 | 75 | 3 | 21 | 0 | **CONDITIONALLY SUPPORTED (partial / unverified items)** |
| 2 | Industrial / process-plant estimating | 120 | 80 | 3 | 37 | 0 | **CONDITIONALLY SUPPORTED (partial / unverified items)** |
| 1 | Major industrial / EPC estimating (Aramco-type) | 129 | 85 | 3 | 40 | 1 | **NOT SUPPORTED (missing capabilities)** |

Data readiness (applies to every level): LIB-07 evidence-backed Saudi rate library (material, labour, plant, equipment, subcontract) - **Missing**; LIB-08 productivity/consumption/wastage factors and crew data approved by humans - **Missing**.

All 131 capability records: Implemented and tested 85, Implemented but unverified 3, Partial 40, Missing 3, Not Applicable 0 (85 + 3 + 40 + 3 + 0 = 131).
<!-- ROLLUP_END -->

Reading the table: a capability needed from level *N* is needed at *N* and at every more demanding level (numerically lower). **IT** Implemented and tested · **IU** Implemented but unverified · **PA** Partial · **MI** Missing.
"Supported" means every required engine capability is *Implemented and tested*; one Partial/Unverified item makes it *Conditionally supported*; one Missing item makes it *Not supported*. This verdict is about the software, not about an estimate's accuracy.

### By area
<!-- AREAS_BEGIN -->
| Area | Records | IT | IU | PA | MI |
|---|---|---|---|---|---|
| A. Scope intake: BOQ, units, quantities, mapping, documents | 11 | 9 | 1 | 1 | 0 |
| B. Classification and libraries: CBS/WBS, catalogues, assemblies, data readiness | 9 | 4 | 0 | 3 | 2 |
| C. Building, civil, infrastructure and MEP disciplines | 11 | 0 | 0 | 11 | 0 |
| D. Industrial, oil and gas, process plant | 14 | 0 | 0 | 14 | 0 |
| E. Rates: material, labour, plant, equipment, subcontract; productivity and methodology | 18 | 16 | 1 | 1 | 0 |
| F. Engineering services, field indirects, home office, temporary facilities | 5 | 3 | 0 | 2 | 0 |
| G. Taxes, duties, logistics | 4 | 3 | 0 | 1 | 0 |
| H. Project duration, sequencing and resource loading | 5 | 5 | 0 | 0 | 0 |
| I. Basis of Estimate, scope definition, maturity and exclusions | 5 | 4 | 0 | 1 | 0 |
| J. Escalation, contingency, quantified risk, uncertainty, currency | 8 | 8 | 0 | 0 | 0 |
| K. Supplier quotations, bid levelling and procurement | 7 | 7 | 0 | 0 | 0 |
| L. Cost control: CBS roll-ups, benchmarks, cash flow, forecasts, change orders, revisions | 7 | 7 | 0 | 0 | 0 |
| M. Commissioning, start-up, handover, close-out | 3 | 1 | 0 | 2 | 0 |
| N. Saudi-specific requirements and configurable client compliance profiles | 7 | 4 | 0 | 2 | 1 |
| O. Approval gates, audit, snapshots, reproducibility, commercial exports | 12 | 11 | 0 | 1 | 0 |
| P. Excel and document outputs | 5 | 3 | 1 | 1 | 0 |
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
| SCO-04 | Industrial/process units and administrator-managed unit list (inch-diameter, weld joint, spool, instrument loop, MVA, flow/pressure/temperature, tonne-km...) | IT Implemented and tested | 2 |
| SCO-05 | Quantity integrity: quantities come only from human-supplied files; changes need a reason and approval; original text immutable; no automated takeoff | IT Implemented and tested | 5 |
| SCO-06 | Pre-calculated resource quantities priced directly (takeoff resource lines) | IT Implemented and tested | 4 |
| SCO-07 | Mapping of BOQ items to assemblies/cost codes with approval; keyword-based mapping suggestions (no AI needed) | IT Implemented and tested | 5 |
| SCO-08 | Non-assembly pricing methods: subcontract lump sum, provisional sum, prime-cost sum, allowance, excluded - each needs approval | IT Implemented and tested | 5 |
| SCO-09 | Scale: large BOQs (10k-50k lines) | PA Partial | 3 |
| SCO-10 | Tender-document intake: numbered workspace, hash/type/size index, versioned text extracts (txt/md/csv/json/xml/html/PDF/DOCX/XLSX), change and missing-file flags | IT Implemented and tested | 4 |
| SCO-11 | Requirements/clarification extraction from tender documents (procedure + deterministic scope checks) | IU Implemented but unverified | 4 |

**SCO-01 - BOQ/takeoff import from CSV/XLSX with header detection, column mapping, Arabic headers, stored original**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/imports/boq.py::import_boq`; `app/imports/boq.py::detect_header`; `app/imports/readers.py::read_sheet`; `app/api/routes.py::boq_preview`
- *Tests:* `imports/test_boq_import.py::test_standard_csv_and_xlsx_equivalent` [yes] (CSV and XLSX give identical items); `imports/test_boq_import.py::test_irregular_column_names_and_order` [yes]; `imports/test_boq_import.py::test_arabic_headers` [yes]; `imports/test_boq_import.py::test_missing_required_header_needs_explicit_mapping` [yes]; `imports/test_boq_import.py::test_malformed_and_unsupported_files` [yes]
- *Workflow / output:* UI BOQ import page / `project import-boq` / POST /api/projects/{id}/boq/import; summary + rejected rows; original copied to '3. BOQ & Takeoff'.
- *Limitations / dependencies:* Single-table BOQs. No multi-sheet consolidation, merged-cell layouts, or vendor-specific formats (e.g. client schedule-of-rates forms). Header detection is heuristic; ambiguity requires an explicit mapping.
- *Acceptance test to mark complete:* Import a 500-row client BOQ (XLSX with merged title rows and Arabic headers) and reconcile rows_read = items + headings + blank + rejected with zero silently dropped rows.

**SCO-02 - Import validation: invalid/negative/zero quantities, duplicates, blanks, headings, source-row traceability, re-import diffs as change requests**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/imports/boq.py::parse_rows`; `app/imports/boq.py::_queue_change`; `app/services/boq.py::decide_change`
- *Tests:* `imports/test_boq_import.py::test_invalid_quantities_rejected_with_reasons_never_silently` [yes]; `imports/test_boq_import.py::test_duplicate_codes_flagged_and_both_kept` [yes]; `imports/test_boq_import.py::test_source_traceability_and_original_values_preserved` [yes]; `imports/test_boq_import.py::test_reimport_never_overwrites_quantities` [yes]
- *Workflow / output:* Rejected rows list with reason codes; `change_requests` Pending Review for revised quantities.
- *Limitations / dependencies:* Rule-based; no semantic check of description-vs-unit plausibility (e.g. 'concrete' in m2).
- *Acceptance test to mark complete:* Re-import a revised BOQ where 10 quantities changed, 3 items were deleted and 2 added: exactly 10 change requests, 3 'missing in revision', 2 new items, no quantity changed before approval.

**SCO-03 - Unit registry with explicit conversion (length/area/volume/mass), ambiguity flagging, no implicit time/count conversion**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/core/units.py::UnitRegistry`; `data/units/units.csv`; `app/estimators/direct_cost.py::_convert_factor_unit`
- *Tests:* `unit/test_money_units.py::test_unit_resolution` [yes]; `unit/test_money_units.py::test_unit_conversion_rules` [yes]; `imports/test_boq_import.py::test_unknown_ambiguous_missing_units_flagged_not_normalised` [yes]; `unit/test_direct_cost.py::test_unit_conversion_t_to_kg` [yes]; `unit/test_direct_cost.py::test_incompatible_units_rejected` [yes]
- *Workflow / output:* Units shown/validated at import; conversion factors recorded on cost-line basis text.
- *Limitations / dependencies:* 28 units, building-oriented. `ton`/`tons` are deliberately ambiguous (must be resolved by a human).
- *Acceptance test to mark complete:* Every unit used in the target client's BOQ either resolves to a canonical unit or is listed as unknown with a human decision recorded.

**SCO-04 - Industrial/process units and administrator-managed unit list (inch-diameter, weld joint, spool, instrument loop, MVA, flow/pressure/temperature, tonne-km...)**  
*Status:* Implemented and tested · *needed from level:* 2 (applies at levels 2, 1) · *kind:* engine
- *Code:* `data/units/units.csv`; `app/core/units.py::CONVERTIBLE`; `app/services/units_admin.py::add_unit`; `app/api/actions.py::add_unit`
- *Tests:* `unit/test_industrial_units.py::test_industrial_units_resolve_and_convert_exactly` [yes] (inch-dia, joint, spool, loop, MVA, m3/h, bar, MPa ... resolve; exact conversions only); `unit/test_industrial_units.py::test_industrial_boq_imports_with_no_unknown_units` [yes] (a piping/E&I BOQ imports with 0 unknown units); `unit/test_industrial_units.py::test_administrator_adds_units_with_guards` [yes] (admin-only, audited, no redefinition, no spelling clash); `integration/test_industrial_flow.py::test_piping_welds_from_pack_to_basis_of_estimate` [yes] (pack -> approved rates/factors -> 200 joints -> derivation -> approval -> 22,200 -> 24,400 with height factor -> 660 h -> roll-up, loading, risk, BoE)
- *Workflow / output:* Unit registry extended (inch-dia, joint, spool, loop, tag, MW/MVA, pressure, flow, imperial length/area/volume/mass) and an administrator action `add_unit` (UI/API form data). Count-like and non-exact dimensions never convert.
- *Limitations / dependencies:* Only physically exact conversions are automatic (length, area, volume, mass, power, apparent power, pressure, volumetric flow). Ambiguous spellings (`ton`, `L/S`) are never guessed - `L/S` stays lump sum; litre/second is `LPS`. Temperature, tonne-km and other compound units are not defined.
- *Acceptance test to mark complete:* Add units inch-dia, joint, spool, loop, MVA, m3/h, bar via a controlled admin action with audit; import a piping BOQ using them with 0 unknown-unit rows; conversions only where physically exact.

**SCO-05 - Quantity integrity: quantities come only from human-supplied files; changes need a reason and approval; original text immutable; no automated takeoff**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/services/boq.py::request_quantity_change`; `app/services/boq.py::decide_change`; `app/imports/boq.py::_persist`
- *Tests:* `imports/test_boq_import.py::test_quantity_change_requires_approval_and_reason` [yes]; `imports/test_boq_import.py::test_reimport_never_overwrites_quantities` [yes]
- *Workflow / output:* Pending change requests queue; approved change updates `quantity` while `quantity_original` stays.
- *Limitations / dependencies:* Absence of any takeoff code is by design and is asserted only by code inspection (no module reads drawings/PDF geometry); there is no negative test for it.
- *Acceptance test to mark complete:* Attempt to change a quantity through every public path (API, UI, workbook import): each yields a Pending Review change request, never a direct change.

**SCO-06 - Pre-calculated resource quantities priced directly (takeoff resource lines)**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/imports/boq.py::import_takeoff_resources`; `app/estimators/direct_cost.py::_price_takeoff_item`
- *Tests:* `workspaces/test_audit_regressions.py::test_takeoff_resource_lines_are_priced_from_approved_rates_and_missing_rates_stay_unpriced` [yes] (added by this audit (pricing was previously untested)); `imports/test_boq_import.py::test_takeoff_resource_import` [partly] (tests import; pricing is exercised by the integration workflow); `integration/test_full_workflow.py::test_initial_state_matches_independent_hand_calculations` [partly]
- *Workflow / output:* Template `takeoff_import_template.xlsx` (sheet Resource Takeoff).
- *Limitations / dependencies:* No waste/productivity logic on these lines by design (quantities are final).
- *Acceptance test to mark complete:* Import resource takeoff lines for 20 items; engine amount = quantity x eligible rate for each, unpriced when the rate is missing.

**SCO-07 - Mapping of BOQ items to assemblies/cost codes with approval; keyword-based mapping suggestions (no AI needed)**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/services/boq.py::map_to_assembly`; `app/services/boq.py::approve_mapping`; `app/ai/service.py::heuristic_mapping`
- *Tests:* `approvals/test_ai_boundary.py::test_only_a_human_can_accept_a_suggestion` [yes] (suggestion changes nothing; only a human acceptance maps the item and records the approval); `approvals/test_ai_boundary.py::test_deterministic_features_work_without_any_ai` [partly] (exercises heuristic_mapping existence/output, not suggestion quality); `integration/test_full_workflow.py::test_complete_workflow_to_gated_submission_export` [partly] (manual mapping in the end-to-end flow)
- *Workflow / output:* Mapping tab; suggestions are Pending Review `ai_suggestions` until a human accepts.
- *Limitations / dependencies:* Suggestion precision/recall is unmeasured; token-overlap only; no spec/tag/discipline-aware matching.
- *Acceptance test to mark complete:* On a 200-item labelled sample, report suggestion hit rate; wrong suggestions never alter a mapping without human acceptance.

**SCO-08 - Non-assembly pricing methods: subcontract lump sum, provisional sum, prime-cost sum, allowance, excluded - each needs approval**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/services/boq.py::set_pricing`; `app/services/boq.py::decide_pricing`; `app/estimators/direct_cost.py::_price_allowance`; `app/estimators/direct_cost.py::_price_subcontract_item`
- *Tests:* `reconciliation/test_recon.py::test_scope_mismatches_exclusion_vs_priced` [partly]; `unit/test_direct_cost.py::test_subcontract_double_count_blocked` [yes]; `integration/test_full_workflow.py::test_complete_workflow_to_gated_submission_export` [partly] (allowance approvals in the flow)
- *Workflow / output:* Mapping tab pricing form; Allowances queue in Approvals.
- *Limitations / dependencies:* Sums are flat amounts; no drawdown or measured-remeasurement logic.
- *Acceptance test to mark complete:* Price one item of each method; unapproved sums produce ALLOWANCE_UNAPPROVED (Critical) and no amount in a strict estimate.

**SCO-09 - Scale: large BOQs (10k-50k lines)**  
*Status:* Partial · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/estimate.py::compute_estimate_cached`; `app/estimators/estimate.py::compute_estimate_from`; `app/excel/builder.py::write_sheet`
- *Tests:* `unit/test_estimate_cache.py::test_cache_hits_until_any_change` [yes]; `unit/test_estimate_cache.py::test_cache_sees_writes_from_another_connection` [yes]; `excel/test_workbooks.py::test_row_styles_are_identical_down_each_column_after_style_reuse` [partly] (workbook writer optimisation keeps styles identical); `unit/test_direct_cost.py::test_full_assembly_hand_calculated` [partly] (engine correctness, not scale)
- *Workflow / output:* Measured on 20,000 BOQ items (2 lines each): estimate 2.7 s, repeat call from the read-only cache 0.09 ms (any write by this or another process invalidates it), freeze + snapshot 4.4 s, full replay 3.9 s, roll-up 2.9 s, master workbook export 25.6 s (59.6 s before the style-reuse fix in the workbook writer).
- *Limitations / dependencies:* No 50,000-item run; the master workbook still takes ~26 s at 20,000 items; HTML tables are not paginated server-side; the performance budget is not enforced by an automated test (only the linear-scaling test of the estimate).
- *Acceptance test to mark complete:* 50,000-item BOQ: estimate < 10 s, any page < 3 s (cached estimate), workbook export < 3 min, memory < 2 GB; regression test with a published budget.

**SCO-10 - Tender-document intake: numbered workspace, hash/type/size index, versioned text extracts (txt/md/csv/json/xml/html/PDF/DOCX/XLSX), change and missing-file flags**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/services/project_index.py::index_project`; `app/services/project_index.py::extract_text`; `app/services/workspaces.py::ensure_workspace`
- *Tests:* `workspaces/test_workspaces.py::test_indexer_inventories_versions_and_flags_changes` [yes]; `workspaces/test_audit_regressions.py::test_real_pdf_docx_and_xlsx_text_is_extracted_and_image_only_pdf_is_reported` [yes] (added by this audit: previously no valid PDF/DOCX/XLSX was ever extracted in tests, and pypdf was not a declared dependency); `workspaces/test_workspaces.py::test_new_project_creates_complete_workspace` [yes]
- *Workflow / output:* `project index`, UI Workspace tab, `2. AI Context/project_index.json`, `project_summary.md`, `extracts/`.
- *Limitations / dependencies:* No OCR (scanned PDFs reported), no DWG/DXF/RVT/IFC extraction, no table-structure extraction from PDFs, no Arabic-specific text handling tests; summaries are counts only.
- *Acceptance test to mark complete:* Index a real 300-page tender PDF set with scanned and text pages: text pages extracted, scanned pages reported, no original modified.

**SCO-11 - Requirements/clarification extraction from tender documents (procedure + deterministic scope checks)**  
*Status:* Implemented but unverified · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `.claude/skills/requirements-extraction/SKILL.md`; `app/ai/service.py::deterministic_scope_checks`; `app/services/registers.py::add_clarification`
- *Tests:* `approvals/test_ai_boundary.py::test_clarification_suggestions_become_open_items_never_resolved` [partly] (AI draft path tested with a mock provider only); `unit/test_instruction_system.py::test_every_skill_is_well_formed_and_states_all_required_sections` [partly] (skill structure only, never executed by a live session)
- *Workflow / output:* Requirements register (markdown/JSON) + Draft clarifications/scope entries.
- *Limitations / dependencies:* The extraction itself is a Claude Code procedure (skill) and the optional AI provider; neither has run against real tender documents or the live API. No automated clause-level cross-referencing.
- *Acceptance test to mark complete:* Run on a real specification section set: every extracted requirement quote is found verbatim in the cited page; reviewer rates misses/false items on a sample.

### B. Classification and libraries: CBS/WBS, catalogues, assemblies, data readiness

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| LIB-01 | Cost breakdown structure: 3-level cost-code taxonomy A-L (152 nodes), extensible as data | IT Implemented and tested | 5 |
| LIB-02 | Work breakdown structure separate from CBS (area/unit/system/tag) and cross-walk to client-specific code lists | IT Implemented and tested | 3 |
| LIB-03 | Resource catalogue definitions for building trades and MEP (927 resources, no prices) | IT Implemented and tested | 5 |
| LIB-04 | Industrial/process resource catalogue (piping classes, valves/flanges by rating, instruments, vessels, tanks, NDT, cathodic protection, hazardous-area equipment) | PA Partial | 2 |
| LIB-05 | Assembly library: structure-only standard assemblies (26 assemblies / 72 lines in divisions B-I), no consumption factors | PA Partial | 4 |
| LIB-06 | Rate/assumption/assembly versioning: approved records immutable, new version supersedes, expiry marks Expired, full history kept | IT Implemented and tested | 5 |
| LIB-07 | DATA READINESS: evidence-backed Saudi rate library (material, labour, plant, equipment, subcontract) | MI Missing | 5 (data) |
| LIB-08 | DATA READINESS: productivity/consumption/wastage factors and crew data approved by humans | MI Missing | 5 (data) |
| LIB-09 | Source Register with provenance, access log and licence notes | PA Partial | 4 |

**LIB-01 - Cost breakdown structure: 3-level cost-code taxonomy A-L (152 nodes), extensible as data**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/services/refdata.py::load_taxonomy`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [yes]; `unit/test_library_data.py::test_new_trade_can_be_added_without_code_changes` [yes]
- *Workflow / output:* docs/TRADE_TAXONOMY.md; cost-code selectors in the UI; Trade and Cost Code Mapping sheet.
- *Limitations / dependencies:* Building-services-centred division list. Divisions A-L only; no process-plant breakdown (units/areas/systems, pipe classes). Insert-only seed.
- *Acceptance test to mark complete:* Load a client CBS of 500 codes with parents, map every BOQ item to it, and roll costs up by any level with totals equal to the estimate.

**LIB-02 - Work breakdown structure separate from CBS (area/unit/system/tag) and cross-walk to client-specific code lists**  
*Status:* Implemented and tested · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/services/wbs.py::add_node`; `app/services/wbs.py::assign_items`; `app/services/wbs.py::add_crosswalk`; `app/services/wbs.py::rollup_report`; `app/estimators/rollup.py::tree_rollup`; `app/estimators/rollup.py::crosswalk`; `app/migrations/0008_structure_params_analysis.sql`
- *Tests:* `unit/test_wbs_rollup.py::test_tree_rollup_hand_calculated_and_ties_out` [yes]; `unit/test_wbs_rollup.py::test_crosswalk_longest_prefix_unmapped_and_ambiguous` [yes]; `unit/test_wbs_rollup.py::test_rollup_report_ties_to_estimate_and_wbs_scoped_by_item` [yes]; `unit/test_wbs_rollup.py::test_wbs_structure_rules` [yes]; `unit/test_wbs_rollup.py::test_import_csv_and_crosswalk_rejects_unknown_cost_code` [yes]
- *Workflow / output:* Project WBS (area/unit/system/phase/package) separate from the cost-code tree, item assignment, client code cross-walk (longest-prefix, ambiguity reported, never split by guesswork) and roll-ups that tie out to the estimate. UI: Structure & programme; report `rollup`; CLI `wbs`.
- *Limitations / dependencies:* The client coding system itself is loaded by a person from the client's own list; none is shipped. Cross-walk is one internal cost code -> one client code; many-to-many splits are not modelled.
- *Acceptance test to mark complete:* Selecting a client code system produces a cost report in that system whose total equals the estimate's direct cost; unmapped and ambiguous amounts are listed.

**LIB-03 - Resource catalogue definitions for building trades and MEP (927 resources, no prices)**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `data/materials/materials.csv`; `data/labour/labour_categories.csv`; `data/plant/plant_categories.csv`; `data/equipment/equipment_categories.csv`; `data/subcontractors/subcontract_packages.csv`; `app/services/refdata.py::load_resource_catalogues`
- *Tests:* `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [yes]
- *Workflow / output:* Resource libraries UI/workbook sheets; coverage report.
- *Limitations / dependencies:* Definitions only. By division: A 99, B 128, C 89, D 112, E 114, F 64, G 63, H 99, I 64, J 50, K 32, L 13. Specifications are placeholders to be confirmed per project.
- *Acceptance test to mark complete:* Every catalogue resource has unit, cost code and a specification field a human has completed before first use in an approved estimate.

**LIB-04 - Industrial/process resource catalogue (piping classes, valves/flanges by rating, instruments, vessels, tanks, NDT, cathodic protection, hazardous-area equipment)**  
*Status:* Partial · *needed from level:* 2 (applies at levels 2, 1) · *kind:* engine
- *Code:* `scripts/gen_industrial_pack.py`; `app/services/refdata.py::load_pack`; `app/api/actions.py::load_pack`; `data/packs/industrial/manifest.json`
- *Tests:* `unit/test_industrial_pack.py::test_load_industrial_pack_is_definitions_only_and_idempotent` [yes] (19 cost codes + 258 definitions, Missing-rate placeholders, no price); `unit/test_industrial_pack.py::test_pack_load_is_admin_only_and_unknown_pack_refused` [yes]; `unit/test_industrial_pack.py::test_pack_with_price_column_or_unknown_unit_is_refused` [yes]; `integration/test_industrial_flow.py::test_piping_welds_from_pack_to_basis_of_estimate` [yes] (pack -> approved rates/factors -> 200 joints -> derivation -> approval -> 22,200 -> 24,400 with height factor -> 660 h -> roll-up, loading, risk, BoE)
- *Workflow / output:* Optional definitions-only pack `industrial` (division M, 18 sub-trades, 258 resource definitions across material/equipment/plant/subcontract/labour) loaded by an administrator (`python -m app.cli pack load industrial`). No price is held.
- *Limitations / dependencies:* Definitions only: no prices, no pipe-class/rating catalogue values, no standards. Specifications are `to be confirmed` attribute prompts. Equipment/instrument specifics (class, material, rating) are recorded per project.
- *Acceptance test to mark complete:* A project's piping class list and instrument index are loaded as resources/specifications; every definition has an approved rate or an open procurement requirement.

**LIB-05 - Assembly library: structure-only standard assemblies (26 assemblies / 72 lines in divisions B-I), no consumption factors**  
*Status:* Partial · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `data/assemblies/standard_assemblies.csv`; `app/services/refdata.py::load_standard_assemblies`; `app/services/assemblies.py::validate`
- *Tests:* `unit/test_library_data.py::test_standard_assemblies_are_structure_only_drafts` [yes]
- *Workflow / output:* Assemblies page; Assembly Library sheet.
- *Limitations / dependencies:* Draft structures that cannot be approved until a human supplies factors and sources. None for divisions A, J, K, L or any industrial discipline. The assembly *engine* is separately tested (EST-01/02).
- *Acceptance test to mark complete:* For a stated list of N high-use work items, approved assemblies exist with documented human-supplied factor sources and the estimate prices them with no manual line edits.

**LIB-06 - Rate/assumption/assembly versioning: approved records immutable, new version supersedes, expiry marks Expired, full history kept**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/services/rates.py::approve_rate`; `app/services/rates.py::revise_rate`; `app/services/rates.py::expire_stale_rates`; `app/services/assumptions.py::revise_assumption`; `app/services/assemblies.py::new_version`
- *Tests:* `approvals/test_approval_rules.py::test_approved_data_cannot_be_silently_overwritten` [yes]; `approvals/test_approval_rules.py::test_assumption_revisions_are_new_versions` [yes]; `approvals/test_approval_rules.py::test_assembly_edits_create_pending_revisions` [yes]; `reconciliation/test_recon.py::test_expired_rate_flagged_and_not_used` [yes]
- *Workflow / output:* Resource page version table; audit log.
- *Limitations / dependencies:* Nothing is deleted, so very long histories grow the DB; no archival policy.
- *Acceptance test to mark complete:* Approve 3 successive versions of one rate: older rows Superseded and unchanged; a frozen estimate keeps its original result.

**LIB-07 - DATA READINESS: evidence-backed Saudi rate library (material, labour, plant, equipment, subcontract)**  
*Status:* Missing · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* data
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None. `python -m app.cli coverage` on a fresh install: 927 resources, 0 real approved rates, 927 missing.
- *Limitations / dependencies:* The pipelines to load rates exist (RTE-03/04) but no rate data has been supplied or approved. No legally reusable source of SAR unit rates was found (docs/KSA_DATA_SOURCES.md). Every real estimate is therefore Preliminary until rates are loaded.
- *Acceptance test to mark complete:* For the resources used by a named pilot BOQ, 100% have an approved, in-date, evidence-backed rate; `coverage` and the project completeness report show no 'Missing Rate' for them.

**LIB-08 - DATA READINESS: productivity/consumption/wastage factors and crew data approved by humans**  
*Status:* Missing · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* data
- *Code:* none (nothing implements this)
- *Tests:* none
- *Workflow / output:* None. Assumption register ships 322 definitions with only four methodological defaults; assemblies carry no factors.
- *Limitations / dependencies:* `data/productivity/` contains a schema only. No benchmark is provided or may be invented.
- *Acceptance test to mark complete:* Pilot-trade assemblies have factors with recorded sources (historical actuals, supplier data or client norms) approved by an Estimator; productivity variance report compares them to actuals.

**LIB-09 - Source Register with provenance, access log and licence notes**  
*Status:* Partial · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
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
*Status:* Partial · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`; `data/assemblies/standard_assemblies.csv`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]
- *Workflow / output:* Estimate build-up, pricing schedule, master workbook.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. Standard assemblies are structure-only.
- *Acceptance test to mark complete:* A pilot architectural BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

**DSC-02 - Structural concrete/masonry/steel for buildings (division C, 11 sub-trades, 89 definitions)**  
*Status:* Partial · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`; `data/assemblies/standard_assemblies.csv`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]
- *Workflow / output:* As above.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. 
- *Acceptance test to mark complete:* A pilot structural BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

**DSC-03 - Civil works and earthworks (division B, plant-intensive: excavators/tippers/utilisation, mobilisation once)**  
*Status:* Partial · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`; `app/estimators/rate_build.py::build_plant`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]; `integration/test_full_workflow.py::test_initial_state_matches_independent_hand_calculations` [yes] (excavation item hand-calculated with utilisation)
- *Workflow / output:* As above.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. Haul-distance, swell/shrink, balancing and cut-fill logic are not modelled (plant output rates are user factors).
- *Acceptance test to mark complete:* A pilot earthworks BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

**DSC-04 - Infrastructure and utilities (roads, drainage, water, sewer, power ducts, external services: divisions B and K)**  
*Status:* Partial · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]
- *Workflow / output:* As above.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. No linear-project features (chainage, phasing by section, traffic management sequencing).
- *Acceptance test to mark complete:* A pilot road + drainage BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

**DSC-05 - HVAC / mechanical (division E: chillers, AHU, ductwork, VRF, BMS interface)**  
*Status:* Partial · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`; `data/assemblies/standard_assemblies.csv`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]
- *Workflow / output:* As above.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. Equipment is priced as supplied items; no capacity-based selection or duct-weight take-off.
- *Acceptance test to mark complete:* A pilot HVAC BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

**DSC-06 - Plumbing and drainage (division F)**  
*Status:* Partial · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`; `data/assemblies/standard_assemblies.csv`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]
- *Workflow / output:* As above.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. 
- *Acceptance test to mark complete:* A pilot plumbing BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

**DSC-07 - Fire protection and life safety (division G)**  
*Status:* Partial · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`; `data/assemblies/standard_assemblies.csv`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]
- *Workflow / output:* As above.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. Authority approval/inspection costs only as priced items.
- *Acceptance test to mark complete:* A pilot fire protection BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

**DSC-08 - Electrical power and lighting for buildings (division H: switchgear, transformers, DBs, cable/containment, lighting)**  
*Status:* Partial · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`; `data/assemblies/standard_assemblies.csv`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]
- *Workflow / output:* As above.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. No cable schedule/termination engine; no load-based sizing.
- *Acceptance test to mark complete:* A pilot electrical BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

**DSC-09 - ELV, ICT and security (division I)**  
*Status:* Partial · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`; `data/assemblies/standard_assemblies.csv`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]
- *Workflow / output:* As above.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. System-integration/programming effort only as priced items or subcontract packages.
- *Acceptance test to mark complete:* A pilot ELV BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

**DSC-10 - Specialist systems (division J: lifts, facade access, kitchens, medical gas, pools, EV charging, renewable)**  
*Status:* Partial · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]
- *Workflow / output:* As above.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. No standard assemblies exist for division J; 50 catalogue definitions; priced mainly as subcontract/equipment packages.
- *Acceptance test to mark complete:* A pilot specialist-systems BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

**DSC-11 - External works, landscaping and site-wide systems (division K)**  
*Status:* Partial · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_library_data.py::test_catalogues_contain_no_prices_and_use_valid_units` [partly]
- *Workflow / output:* As above.
- *Limitations / dependencies:* Definitions + generic engine only: quantities, assembly factors and rates must be supplied and approved by humans. No discipline calculators (no bar-schedule, duct-weight, pipe-sizing or cable-schedule logic) - by design quantities are human-measured. 32 definitions, no standard assemblies.
- *Acceptance test to mark complete:* A pilot external-works BOQ is imported, mapped to approved assemblies with approved rates, and priced Complete (no unpriced lines) with the hand-calculated total reproduced by the engine.

### D. Industrial, oil and gas, process plant

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| PRC-01 | Process piping: spools, inch-diameter, pipe class/schedule/material, welds, supports, NDT, hydrotest, flushing, field vs shop split | PA Partial | 2 |
| PRC-02 | Process equipment (vessels, exchangers, pumps, compressors): supply, receive, set, align, grout, vendor reps, spares | PA Partial | 2 |
| PRC-03 | Instrumentation and control (loops, I/O, junction boxes, tubing, calibration, DCS/PLC/SCADA configuration, FAT/SAT) | PA Partial | 2 |
| PRC-04 | Industrial electrical power (MV/LV switchgear, transformers, MCC, cable pulling/termination, tray, earthing, hazardous-area) | PA Partial | 2 |
| PRC-05 | Structural steel by tonnage: supply, fabricate, blast/paint, erect, bolt/weld | PA Partial | 2 |
| PRC-06 | Field-erected tanks and large vessels (plate welding, NDT, hydro/air test, settlement test) | PA Partial | 2 |
| PRC-07 | Surface preparation, coating systems and fireproofing (blast, primer/intermediate/topcoat, DFT, coverage, shop vs field) | PA Partial | 2 |
| PRC-08 | Thermal insulation and cladding (hot/cold service, thickness, jacketing) | PA Partial | 2 |
| PRC-09 | Scaffolding and temporary access for industrial work (volume-based, by phase) | PA Partial | 2 |
| PRC-10 | Heavy lifting, rigging and crane selection (lift studies, crane hire periods, mobilisation of large cranes) | PA Partial | 2 |
| PRC-11 | Cathodic protection, NDT services, specialist industrial services (hazardous-area works, hot-tapping, chemical cleaning) | PA Partial | 2 |
| PRC-12 | Shutdown/turnaround and brownfield estimating (tie-ins, live-plant restrictions, permits, hot-work, outage windows) | PA Partial | 1 |
| PRC-13 | Modularisation, prefabrication and yard-vs-site work splits | PA Partial | 1 |
| PRC-14 | Remote-site construction: camps, catering, logistics, rotation and per-diem, site mobilisation | PA Partial | 2 |

**PRC-01 - Process piping: spools, inch-diameter, pipe class/schedule/material, welds, supports, NDT, hydrotest, flushing, field vs shop split**  
*Status:* Partial · *needed from level:* 2 (applies at levels 2, 1) · *kind:* engine
- *Code:* `app/estimators/mto.py::derive`; `app/services/mto.py::apply`; `app/services/mto.py::preview`; `data/mto/templates.json`; `scripts/gen_mto_templates.py`; `data/packs/industrial/manifest.json`
- *Tests:* `unit/test_mto.py::test_engine_derive_hand_calculated_missing_and_skipped` [yes] (driver x factor x (1+waste); missing slot yields nothing); `unit/test_mto.py::test_apply_pricing_gate_and_hand_calculated_cost` [yes] (derived lines are Pending Review until a person approves the pricing); `unit/test_mto.py::test_factor_validation_against_template_slot_resource_and_unit` [yes]; `unit/test_mto.py::test_stale_detection_after_factor_or_driver_change` [yes]; `integration/test_industrial_flow.py::test_piping_welds_from_pack_to_basis_of_estimate` [yes] (pack -> approved rates/factors -> 200 joints -> derivation -> approval -> 22,200 -> 24,400 with height factor -> 660 h -> roll-up, loading, risk, BoE)
- *Workflow / output:* Take-off template(s) `piping.pipe_fab_install, piping.weld_joint, piping.spool, piping.supports, piping.valve_install, piping.hydrotest` + industrial definitions pack + governed productivity factors + MTO status/stale reconciliation; derived quantities need a pricing decision. CLI `mto`, UI Structure & programme, report `mto_preview`.
- *Limitations / dependencies:* Structure only: the template names the driver and the resource slots, but NO factor, productivity or consumption value is shipped - each is entered from company records as a governed `mto_factor` and approved. The driver quantity is the estimator's own measured figure; the software never measures drawings. Pipe class/schedule/material selection and weld-procedure logic are not modelled; shop vs field split is expressed only by separate slots. Depends on: SCO-04, LIB-04, EST-12.
- *Acceptance test to mark complete:* Estimate a 500-spool package from a MTO: man-hours derive from inch-dia x approved factors by size/schedule/material with shop/field split; weld and NDT counts reconcile to the MTO; hydrotest and flushing costed.

**PRC-02 - Process equipment (vessels, exchangers, pumps, compressors): supply, receive, set, align, grout, vendor reps, spares**  
*Status:* Partial · *needed from level:* 2 (applies at levels 2, 1) · *kind:* engine
- *Code:* `app/estimators/mto.py::derive`; `app/services/mto.py::apply`; `app/services/mto.py::preview`; `data/mto/templates.json`; `scripts/gen_mto_templates.py`; `data/packs/industrial/manifest.json`; `data/equipment/equipment_categories.csv`; `app/estimators/direct_cost.py::_material_like`
- *Tests:* `unit/test_mto.py::test_engine_derive_hand_calculated_missing_and_skipped` [yes] (driver x factor x (1+waste); missing slot yields nothing); `unit/test_mto.py::test_apply_pricing_gate_and_hand_calculated_cost` [yes] (derived lines are Pending Review until a person approves the pricing); `unit/test_mto.py::test_factor_validation_against_template_slot_resource_and_unit` [yes]; `unit/test_mto.py::test_stale_detection_after_factor_or_driver_change` [yes]; `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_direct_cost.py::test_full_assembly_hand_calculated` [partly] (generic assembly lines only)
- *Workflow / output:* Take-off template(s) `equipment.set_and_align` + industrial definitions pack + governed productivity factors + MTO status/stale reconciliation; derived quantities need a pricing decision. CLI `mto`, UI Structure & programme, report `mto_preview`.
- *Limitations / dependencies:* Structure only: the template names the driver and the resource slots, but NO factor, productivity or consumption value is shipped - each is entered from company records as a governed `mto_factor` and approved. The driver quantity is the estimator's own measured figure; the software never measures drawings. No equipment-specific logic (alignment tolerances, grouting method, vendor scope); supply price comes from quotations through the rate pipeline. Earlier audit note: No weight/tonnage-based erection model, vendor-package structure, rigging/lift linkage or spares/special-tools build-up (assumption definitions only). Depends on: PRC-10.
- *Acceptance test to mark complete:* A vendor-supplied pump skid and a field-erected vessel are each estimated with supply, freight, rigging, set/align and vendor-representative costs, all traceable to approved inputs.

**PRC-03 - Instrumentation and control (loops, I/O, junction boxes, tubing, calibration, DCS/PLC/SCADA configuration, FAT/SAT)**  
*Status:* Partial · *needed from level:* 2 (applies at levels 2, 1) · *kind:* engine
- *Code:* `app/estimators/mto.py::derive`; `app/services/mto.py::apply`; `app/services/mto.py::preview`; `data/mto/templates.json`; `scripts/gen_mto_templates.py`; `data/packs/industrial/manifest.json`
- *Tests:* `unit/test_mto.py::test_engine_derive_hand_calculated_missing_and_skipped` [yes] (driver x factor x (1+waste); missing slot yields nothing); `unit/test_mto.py::test_apply_pricing_gate_and_hand_calculated_cost` [yes] (derived lines are Pending Review until a person approves the pricing); `unit/test_mto.py::test_factor_validation_against_template_slot_resource_and_unit` [yes]; `unit/test_mto.py::test_stale_detection_after_factor_or_driver_change` [yes]
- *Workflow / output:* Take-off template(s) `instrument.loop` + industrial definitions pack + governed productivity factors + MTO status/stale reconciliation; derived quantities need a pricing decision. CLI `mto`, UI Structure & programme, report `mto_preview`.
- *Limitations / dependencies:* Structure only: the template names the driver and the resource slots, but NO factor, productivity or consumption value is shipped - each is entered from company records as a governed `mto_factor` and approved. The driver quantity is the estimator's own measured figure; the software never measures drawings. I/O counts, DCS/PLC configuration scope and calibration standards are not modelled beyond per-loop slots. Depends on: SCO-04, LIB-04.
- *Acceptance test to mark complete:* A 400-loop instrument package is estimated from an instrument index: installation, tubing, calibration and loop-check hours derive from approved per-loop factors; control-system configuration priced from vendor quotation.

**PRC-04 - Industrial electrical power (MV/LV switchgear, transformers, MCC, cable pulling/termination, tray, earthing, hazardous-area)**  
*Status:* Partial · *needed from level:* 2 (applies at levels 2, 1) · *kind:* engine
- *Code:* `app/estimators/mto.py::derive`; `app/services/mto.py::apply`; `app/services/mto.py::preview`; `data/mto/templates.json`; `scripts/gen_mto_templates.py`; `data/packs/industrial/manifest.json`; `data/materials/materials.csv`; `data/equipment/equipment_categories.csv`
- *Tests:* `unit/test_mto.py::test_engine_derive_hand_calculated_missing_and_skipped` [yes] (driver x factor x (1+waste); missing slot yields nothing); `unit/test_mto.py::test_apply_pricing_gate_and_hand_calculated_cost` [yes] (derived lines are Pending Review until a person approves the pricing); `unit/test_mto.py::test_factor_validation_against_template_slot_resource_and_unit` [yes]; `unit/test_mto.py::test_stale_detection_after_factor_or_driver_change` [yes]; `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works)
- *Workflow / output:* Take-off template(s) `electrical.cable, electrical.termination` + industrial definitions pack + governed productivity factors + MTO status/stale reconciliation; derived quantities need a pricing decision. CLI `mto`, UI Structure & programme, report `mto_preview`.
- *Limitations / dependencies:* Structure only: the template names the driver and the resource slots, but NO factor, productivity or consumption value is shipped - each is entered from company records as a governed `mto_factor` and approved. The driver quantity is the estimator's own measured figure; the software never measures drawings. Cable sizing, tray fill, hazardous-area classification and testing standards are not modelled. Earlier audit note: No cable schedule/length-by-size engine, termination counts, hazardous-area classification costs, or substation commissioning logic; MV/HV beyond a few catalogue lines is absent. Depends on: LIB-04, EST-12.
- *Acceptance test to mark complete:* A substation + 2 km cable package is estimated from a cable schedule with termination/pulling hours per approved factors and testing/commissioning scope.

**PRC-05 - Structural steel by tonnage: supply, fabricate, blast/paint, erect, bolt/weld**  
*Status:* Partial · *needed from level:* 2 (applies at levels 2, 1) · *kind:* engine
- *Code:* `app/estimators/mto.py::derive`; `app/services/mto.py::apply`; `app/services/mto.py::preview`; `data/mto/templates.json`; `scripts/gen_mto_templates.py`; `data/packs/industrial/manifest.json`; `data/materials/materials.csv`; `data/subcontractors/subcontract_packages.csv`; `app/estimators/direct_cost.py::_price_line`
- *Tests:* `unit/test_mto.py::test_engine_derive_hand_calculated_missing_and_skipped` [yes] (driver x factor x (1+waste); missing slot yields nothing); `unit/test_mto.py::test_apply_pricing_gate_and_hand_calculated_cost` [yes] (derived lines are Pending Review until a person approves the pricing); `unit/test_mto.py::test_factor_validation_against_template_slot_resource_and_unit` [yes]; `unit/test_mto.py::test_stale_detection_after_factor_or_driver_change` [yes]; `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works); `unit/test_direct_cost.py::test_unit_conversion_t_to_kg` [partly] (t<->kg conversion only)
- *Workflow / output:* Take-off template(s) `steel.structural` + industrial definitions pack + governed productivity factors + MTO status/stale reconciliation; derived quantities need a pricing decision. CLI `mto`, UI Structure & programme, report `mto_preview`.
- *Limitations / dependencies:* Structure only: the template names the driver and the resource slots, but NO factor, productivity or consumption value is shipped - each is entered from company records as a governed `mto_factor` and approved. The driver quantity is the estimator's own measured figure; the software never measures drawings. No connection-type or fabrication-complexity classification; weight is the estimator's measured tonnage. Earlier audit note: No MH/tonne by member class, connection count, fabrication vs erection split, galvanising logistics or weight-from-section library. Depends on: LIB-08.
- *Acceptance test to mark complete:* A 1,000 t steel package priced by approved MH/tonne factors and rates with shop/field split and coating tonnage reconciled to the steel MTO.

**PRC-06 - Field-erected tanks and large vessels (plate welding, NDT, hydro/air test, settlement test)**  
*Status:* Partial · *needed from level:* 2 (applies at levels 2, 1) · *kind:* engine
- *Code:* `app/estimators/mto.py::derive`; `app/services/mto.py::apply`; `app/services/mto.py::preview`; `data/mto/templates.json`; `scripts/gen_mto_templates.py`; `data/packs/industrial/manifest.json`
- *Tests:* `unit/test_mto.py::test_engine_derive_hand_calculated_missing_and_skipped` [yes] (driver x factor x (1+waste); missing slot yields nothing); `unit/test_mto.py::test_apply_pricing_gate_and_hand_calculated_cost` [yes] (derived lines are Pending Review until a person approves the pricing); `unit/test_mto.py::test_factor_validation_against_template_slot_resource_and_unit` [yes]; `unit/test_mto.py::test_stale_detection_after_factor_or_driver_change` [yes]
- *Workflow / output:* Take-off template(s) `tank.field_erected` + industrial definitions pack + governed productivity factors + MTO status/stale reconciliation; derived quantities need a pricing decision. CLI `mto`, UI Structure & programme, report `mto_preview`.
- *Limitations / dependencies:* Structure only: the template names the driver and the resource slots, but NO factor, productivity or consumption value is shipped - each is entered from company records as a governed `mto_factor` and approved. The driver quantity is the estimator's own measured figure; the software never measures drawings. No plate-sequence, welding-position, settlement or hydrotest-duration logic beyond the slots. Depends on: PRC-01.
- *Acceptance test to mark complete:* A storage-tank package estimated from plate weights, weld length, test requirements, with productivity from approved factors.

**PRC-07 - Surface preparation, coating systems and fireproofing (blast, primer/intermediate/topcoat, DFT, coverage, shop vs field)**  
*Status:* Partial · *needed from level:* 2 (applies at levels 2, 1) · *kind:* engine
- *Code:* `app/estimators/mto.py::derive`; `app/services/mto.py::apply`; `app/services/mto.py::preview`; `data/mto/templates.json`; `scripts/gen_mto_templates.py`; `data/packs/industrial/manifest.json`; `data/materials/materials.csv`; `data/plant/plant_categories.csv`
- *Tests:* `unit/test_mto.py::test_engine_derive_hand_calculated_missing_and_skipped` [yes] (driver x factor x (1+waste); missing slot yields nothing); `unit/test_mto.py::test_apply_pricing_gate_and_hand_calculated_cost` [yes] (derived lines are Pending Review until a person approves the pricing); `unit/test_mto.py::test_factor_validation_against_template_slot_resource_and_unit` [yes]; `unit/test_mto.py::test_stale_detection_after_factor_or_driver_change` [yes]; `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works)
- *Workflow / output:* Take-off template(s) `coating.surface, coating.fireproofing` + industrial definitions pack + governed productivity factors + MTO status/stale reconciliation; derived quantities need a pricing decision. CLI `mto`, UI Structure & programme, report `mto_preview`.
- *Limitations / dependencies:* Structure only: the template names the driver and the resource slots, but NO factor, productivity or consumption value is shipped - each is entered from company records as a governed `mto_factor` and approved. The driver quantity is the estimator's own measured figure; the software never measures drawings. Coating-system specification (DFT, surface standard, coats) is carried in factor basis text, not modelled. Earlier audit note: Coating system, DFT, coverage and wastage can only be encoded by hand in assembly factors; no system definition, no repair/touch-up logic.
- *Acceptance test to mark complete:* A coating specification (blast + 3 coats) is an approved assembly whose material quantity derives from stated coverage and DFT factors.

**PRC-08 - Thermal insulation and cladding (hot/cold service, thickness, jacketing)**  
*Status:* Partial · *needed from level:* 2 (applies at levels 2, 1) · *kind:* engine
- *Code:* `app/estimators/mto.py::derive`; `app/services/mto.py::apply`; `app/services/mto.py::preview`; `data/mto/templates.json`; `scripts/gen_mto_templates.py`; `data/packs/industrial/manifest.json`; `data/materials/materials.csv`
- *Tests:* `unit/test_mto.py::test_engine_derive_hand_calculated_missing_and_skipped` [yes] (driver x factor x (1+waste); missing slot yields nothing); `unit/test_mto.py::test_apply_pricing_gate_and_hand_calculated_cost` [yes] (derived lines are Pending Review until a person approves the pricing); `unit/test_mto.py::test_factor_validation_against_template_slot_resource_and_unit` [yes]; `unit/test_mto.py::test_stale_detection_after_factor_or_driver_change` [yes]; `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works)
- *Workflow / output:* Take-off template(s) `insulation.surface` + industrial definitions pack + governed productivity factors + MTO status/stale reconciliation; derived quantities need a pricing decision. CLI `mto`, UI Structure & programme, report `mto_preview`.
- *Limitations / dependencies:* Structure only: the template names the driver and the resource slots, but NO factor, productivity or consumption value is shipped - each is entered from company records as a governed `mto_factor` and approved. The driver quantity is the estimator's own measured figure; the software never measures drawings. Thickness-by-service tables and heat-loss calculations are not modelled. Earlier audit note: 8 catalogue definitions; no thickness/diameter-based area computation (quantities are human-supplied).
- *Acceptance test to mark complete:* Insulation by size/thickness priced from an approved assembly set with applicator productivity and jacketing.

**PRC-09 - Scaffolding and temporary access for industrial work (volume-based, by phase)**  
*Status:* Partial · *needed from level:* 2 (applies at levels 2, 1) · *kind:* engine
- *Code:* `app/estimators/mto.py::derive`; `app/services/mto.py::apply`; `app/services/mto.py::preview`; `data/mto/templates.json`; `scripts/gen_mto_templates.py`; `data/packs/industrial/manifest.json`; `data/plant/plant_categories.csv`; `data/taxonomy/cost_codes.csv`
- *Tests:* `unit/test_mto.py::test_engine_derive_hand_calculated_missing_and_skipped` [yes] (driver x factor x (1+waste); missing slot yields nothing); `unit/test_mto.py::test_apply_pricing_gate_and_hand_calculated_cost` [yes] (derived lines are Pending Review until a person approves the pricing); `unit/test_mto.py::test_factor_validation_against_template_slot_resource_and_unit` [yes]; `unit/test_mto.py::test_stale_detection_after_factor_or_driver_change` [yes]; `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (proves the trade nodes exist, not that estimating them works)
- *Workflow / output:* Take-off template(s) `scaffold.volume` + industrial definitions pack + governed productivity factors + MTO status/stale reconciliation; derived quantities need a pricing decision. CLI `mto`, UI Structure & programme, report `mto_preview`.
- *Limitations / dependencies:* Structure only: the template names the driver and the resource slots, but NO factor, productivity or consumption value is shipped - each is entered from company records as a governed `mto_factor` and approved. The driver quantity is the estimator's own measured figure; the software never measures drawings. Scaffold design, hire periods and inspection regimes are not modelled beyond slots. Earlier audit note: No scaffold-volume, erect/dismantle/hire-period model. Depends on: DUR-05.
- *Acceptance test to mark complete:* Scaffolding for a unit costed by volume and duration with erect/dismantle productivity and hire time from the programme.

**PRC-10 - Heavy lifting, rigging and crane selection (lift studies, crane hire periods, mobilisation of large cranes)**  
*Status:* Partial · *needed from level:* 2 (applies at levels 2, 1) · *kind:* engine
- *Code:* `app/estimators/mto.py::derive`; `app/services/mto.py::apply`; `app/services/mto.py::preview`; `data/mto/templates.json`; `scripts/gen_mto_templates.py`; `data/packs/industrial/manifest.json`; `data/plant/plant_categories.csv`; `app/estimators/rate_build.py::build_plant`
- *Tests:* `unit/test_mto.py::test_engine_derive_hand_calculated_missing_and_skipped` [yes] (driver x factor x (1+waste); missing slot yields nothing); `unit/test_mto.py::test_apply_pricing_gate_and_hand_calculated_cost` [yes] (derived lines are Pending Review until a person approves the pricing); `unit/test_mto.py::test_factor_validation_against_template_slot_resource_and_unit` [yes]; `unit/test_mto.py::test_stale_detection_after_factor_or_driver_change` [yes]; `unit/test_rate_build.py::test_plant_day_basis_uses_supplied_calendar` [yes] (plant hire build-up); `unit/test_direct_cost.py::test_full_assembly_hand_calculated` [partly]
- *Workflow / output:* Take-off template(s) `lifting.heavy_lift` + industrial definitions pack + governed productivity factors + MTO status/stale reconciliation; derived quantities need a pricing decision. CLI `mto`, UI Structure & programme, report `mto_preview`.
- *Limitations / dependencies:* Structure only: the template names the driver and the resource slots, but NO factor, productivity or consumption value is shipped - each is entered from company records as a governed `mto_factor` and approved. The driver quantity is the estimator's own measured figure; the software never measures drawings. No crane capacity / radius selection or lift-study logic. Earlier audit note: Standby/minimum-hire not applied (EST-05); no lift-plan or crane-capacity logic; hire period is not tied to a programme. Depends on: EST-05, DUR-05.
- *Acceptance test to mark complete:* A lift package priced with crane hire derived from the programme durations plus mobilisation, standby and rigging labour.

**PRC-11 - Cathodic protection, NDT services, specialist industrial services (hazardous-area works, hot-tapping, chemical cleaning)**  
*Status:* Partial · *needed from level:* 2 (applies at levels 2, 1) · *kind:* engine
- *Code:* `app/estimators/mto.py::derive`; `app/services/mto.py::apply`; `app/services/mto.py::preview`; `data/mto/templates.json`; `scripts/gen_mto_templates.py`; `data/packs/industrial/manifest.json`
- *Tests:* `unit/test_mto.py::test_engine_derive_hand_calculated_missing_and_skipped` [yes] (driver x factor x (1+waste); missing slot yields nothing); `unit/test_mto.py::test_apply_pricing_gate_and_hand_calculated_cost` [yes] (derived lines are Pending Review until a person approves the pricing); `unit/test_mto.py::test_factor_validation_against_template_slot_resource_and_unit` [yes]; `unit/test_mto.py::test_stale_detection_after_factor_or_driver_change` [yes]
- *Workflow / output:* Take-off template(s) `services.specialist` + industrial definitions pack + governed productivity factors + MTO status/stale reconciliation; derived quantities need a pricing decision. CLI `mto`, UI Structure & programme, report `mto_preview`.
- *Limitations / dependencies:* Structure only: the template names the driver and the resource slots, but NO factor, productivity or consumption value is shipped - each is entered from company records as a governed `mto_factor` and approved. The driver quantity is the estimator's own measured figure; the software never measures drawings. Specialist scopes (cathodic protection, NDT campaigns, hazardous-area packages) are generic count-based slots.
- *Acceptance test to mark complete:* Each specialist service has a catalogue definition, unit and subcontract RFQ template with scope matrix.

**PRC-12 - Shutdown/turnaround and brownfield estimating (tie-ins, live-plant restrictions, permits, hot-work, outage windows)**  
*Status:* Partial · *needed from level:* 1 (applies at levels 1) · *kind:* engine
- *Code:* `app/estimators/mto.py::derive`; `app/services/mto.py::apply`; `app/services/mto.py::preview`; `data/mto/templates.json`; `scripts/gen_mto_templates.py`; `data/packs/industrial/manifest.json`
- *Tests:* `unit/test_mto.py::test_engine_derive_hand_calculated_missing_and_skipped` [yes] (driver x factor x (1+waste); missing slot yields nothing); `unit/test_mto.py::test_apply_pricing_gate_and_hand_calculated_cost` [yes] (derived lines are Pending Review until a person approves the pricing); `unit/test_mto.py::test_factor_validation_against_template_slot_resource_and_unit` [yes]; `unit/test_mto.py::test_stale_detection_after_factor_or_driver_change` [yes]
- *Workflow / output:* Take-off template(s) `turnaround.tie_in` + industrial definitions pack + governed productivity factors + MTO status/stale reconciliation; derived quantities need a pricing decision. CLI `mto`, UI Structure & programme, report `mto_preview`.
- *Limitations / dependencies:* Structure only: the template names the driver and the resource slots, but NO factor, productivity or consumption value is shipped - each is entered from company records as a governed `mto_factor` and approved. The driver quantity is the estimator's own measured figure; the software never measures drawings. No shutdown schedule, isolation planning, permit durations or live-plant restriction logic beyond slots. Depends on: DUR-05, EST-12.
- *Acceptance test to mark complete:* A turnaround scope is estimated with window-constrained durations, access factors approved as assumptions, and permit/standby costs.

**PRC-13 - Modularisation, prefabrication and yard-vs-site work splits**  
*Status:* Partial · *needed from level:* 1 (applies at levels 1) · *kind:* engine
- *Code:* `app/estimators/mto.py::derive`; `app/services/mto.py::apply`; `app/services/mto.py::preview`; `data/mto/templates.json`; `scripts/gen_mto_templates.py`; `data/packs/industrial/manifest.json`
- *Tests:* `unit/test_mto.py::test_engine_derive_hand_calculated_missing_and_skipped` [yes] (driver x factor x (1+waste); missing slot yields nothing); `unit/test_mto.py::test_apply_pricing_gate_and_hand_calculated_cost` [yes] (derived lines are Pending Review until a person approves the pricing); `unit/test_mto.py::test_factor_validation_against_template_slot_resource_and_unit` [yes]; `unit/test_mto.py::test_stale_detection_after_factor_or_driver_change` [yes]
- *Workflow / output:* Take-off template(s) `module.prefabricated, piping.spool` + industrial definitions pack + governed productivity factors + MTO status/stale reconciliation; derived quantities need a pricing decision. CLI `mto`, UI Structure & programme, report `mto_preview`.
- *Limitations / dependencies:* Structure only: the template names the driver and the resource slots, but NO factor, productivity or consumption value is shipped - each is entered from company records as a governed `mto_factor` and approved. The driver quantity is the estimator's own measured figure; the software never measures drawings. Yard-vs-site logic, module weights and transport permits are not modelled beyond slots.
- *Acceptance test to mark complete:* A module is estimated in yard and at site with transport, lift and hook-up costs separated and reconciled.

**PRC-14 - Remote-site construction: camps, catering, logistics, rotation and per-diem, site mobilisation**  
*Status:* Partial · *needed from level:* 2 (applies at levels 2, 1) · *kind:* engine
- *Code:* `app/estimators/mto.py::derive`; `app/services/mto.py::apply`; `app/services/mto.py::preview`; `data/mto/templates.json`; `scripts/gen_mto_templates.py`; `data/packs/industrial/manifest.json`; `data/indirects/indirect_categories.csv`; `app/estimators/indirect.py::compute_indirects`; `app/services/indirects.py::add_indirect`
- *Tests:* `unit/test_mto.py::test_engine_derive_hand_calculated_missing_and_skipped` [yes] (driver x factor x (1+waste); missing slot yields nothing); `unit/test_mto.py::test_apply_pricing_gate_and_hand_calculated_cost` [yes] (derived lines are Pending Review until a person approves the pricing); `unit/test_mto.py::test_factor_validation_against_template_slot_resource_and_unit` [yes]; `unit/test_mto.py::test_stale_detection_after_factor_or_driver_change` [yes]; `unit/test_indirect_duration.py::test_methods_hand_calculated` [yes] (indirect methods); `unit/test_indirect_duration.py::test_duration_not_approved_blocks_duration_costs_but_not_fixed` [yes]
- *Workflow / output:* Take-off template(s) `temp.site_establishment` + industrial definitions pack + governed productivity factors + MTO status/stale reconciliation; derived quantities need a pricing decision. CLI `mto`, UI Structure & programme, report `mto_preview`.
- *Limitations / dependencies:* Structure only: the template names the driver and the resource slots, but NO factor, productivity or consumption value is shipped - each is entered from company records as a governed `mto_factor` and approved. The driver quantity is the estimator's own measured figure; the software never measures drawings. Camp sizing, rotation and per-diem rules are not modelled; peak persons come from the loading histogram or the estimator. Earlier audit note: No camp sizing from manpower, no rotation/leave cost model, no remote-location logistics build-up; there are intentionally no regional multipliers. Depends on: DUR-04.
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
| EST-05 | Plant standby/idle and minimum hire periods applied to cost | IT Implemented and tested | 3 |
| EST-07 | Quantity/unit conversion between BOQ unit and assembly unit | IT Implemented and tested | 5 |
| EST-10 | Man-hour aggregation and histograms by craft/trade/area/period | IT Implemented and tested | 3 |
| EST-11 | Construction methodology: method statements, equipment selection, work sequencing that drives labour/plant quantities | PA Partial | 2 |
| EST-12 | Productivity adjustment factors (height, congestion, climate, shift, remote site, learning) as approved assumptions applied to hours | IT Implemented and tested | 2 |
| EST-04 | Missing/unapproved/expired/index-only rates leave lines unpriced with indicative exposure reported separately | IT Implemented and tested | 5 |
| EST-06 | Estimate states (Complete / Complete with Provisional Inputs / Preliminary) and SHA-256 fingerprint for stale detection | IT Implemented and tested | 5 |
| EST-08 | Project-scoped provisional rate approval with mandatory reason, always disclosed | IT Implemented and tested | 5 |
| EST-09 | What-if assumption impact analysis (strict vs preliminary, override not persisted) | IT Implemented and tested | 4 |

**RTE-01 - Rate model for material, labour, plant, equipment and subcontract resources with eligibility rules (approved/provisional, date, region, real price type)**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/rate_resolution.py::resolve_rate`; `app/services/rates.py::propose_rate`; `app/services/rates.py::approve_rate`
- *Tests:* `unit/test_schedule_resolution.py::test_resolution_outcomes` [yes]; `unit/test_schedule_resolution.py::test_provisional_is_project_scoped` [yes]; `approvals/test_approval_rules.py::test_unapproved_rate_never_becomes_verified` [yes]; `unit/test_direct_cost.py::test_missing_rate_never_zero` [yes]; `unit/test_direct_cost.py::test_expired_rate_flagged_not_used` [yes]
- *Workflow / output:* Resource page, estimate build-up (UNPRICED flags, indicative exposure).
- *Limitations / dependencies:* Region applicability by code only; no rate escalation to a base date; no volume-tier pricing.
- *Acceptance test to mark complete:* For each rate state (approved, provisional, pending, expired, future, wrong-region, index-only, missing) a line is priced or left unpriced exactly as specified.

**RTE-02 - Labour and plant rate build-ups from supplied components (wage, allowances, accommodation, transport, employer cost, overtime; hire basis, operator, fuel, maintenance)**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/rate_build.py::build_labour`; `app/estimators/rate_build.py::build_plant`; `app/services/rates.py::_price_from_components`
- *Tests:* `unit/test_rate_build.py::test_labour_hourly` [yes]; `unit/test_rate_build.py::test_labour_overtime_premium_on_base_wage_only` [yes]; `unit/test_rate_build.py::test_plant_day_basis_uses_supplied_calendar` [yes]; `integration/test_api_ui.py::test_labour_buildup_via_form_and_similar_item_search` [yes]
- *Workflow / output:* Resource page form -> stored `components_json`.
- *Limitations / dependencies:* Generic components only: GOSI, iqama/levy, Saudization premiums, end-of-service, flights/leave are not separate fields (use 'other'). No shift-pattern or skill-mix model. Depends on: SAU-03.
- *Acceptance test to mark complete:* A labour category rate is rebuilt from a company wage sheet with every Saudi statutory component as an explicit approved field and reproduces the company's own hourly cost.

**RTE-03 - Supplier quotation -> approved rate publication (new Pending Review version, human approval)**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/procurement/selection.py::publish_rates`; `app/services/rates.py::propose_rate`
- *Tests:* `procurement/test_procurement.py::test_rate_publication_requires_rate_approval_and_links_quotation` [yes]; `procurement/test_procurement.py::test_published_rate_from_tax_inclusive_quote_is_pre_tax` [yes]
- *Workflow / output:* Quotations tab -> Propose rates from this quotation.
- *Limitations / dependencies:* Per-line only; no quantity-break tiers.
- *Acceptance test to mark complete:* Select a quoted supplier; each published rate links to its quotation line and cannot be used until approved.

**RTE-04 - Rate candidates from datasets/price lists: import with manifest, queue, normalisation (approved FX/units/VAT), review, publication**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/rate_updates/importer.py::import_rates_file`; `app/rate_updates/candidates.py::publish`; `app/rate_updates/normalise.py::normalise`; `app/rate_updates/manifest.py::write_manifest`
- *Tests:* `sources/test_rate_pipeline.py::test_rates_import_dry_run_then_real_creates_candidates_and_manifest` [yes]; `sources/test_rate_pipeline.py::test_normalisation_requires_approved_inputs_and_never_changes_the_original` [yes]; `sources/test_rate_pipeline.py::test_unsafe_candidates_cannot_be_approved_for_publication` [yes]; `sources/test_rate_pipeline.py::test_publication_creates_new_pending_version_keeps_old_and_does_not_mutate_frozen_estimate` [yes]
- *Workflow / output:* Rate updates UI; `rates import|pending|review|publish`.
- *Limitations / dependencies:* Never run on a real supplier price list; two overlapping dataset flows exist (legacy staging).
- *Acceptance test to mark complete:* Import a real supplier price list of 200 lines: rejects/flags match a manual audit; 100% of published rates trace to the file hash and row.

**RTE-05 - Live retrieval from public sources (KAPSARC/GASTAT CCI API) and operator web-price watchlist**  
*Status:* Implemented but unverified · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/sources/providers.py::KapsarcGastatCci`; `app/sources/providers.py::WebPriceWatchlist`; `app/sources/webprice.py::extract_candidates`; `app/sources/base.py::HttpFetcher`
- *Tests:* `sources/test_rate_pipeline.py::test_kapsarc_provider_pages_and_imports_via_mock_only` [partly] (mocked transport); `sources/test_rate_pipeline.py::test_web_extraction_edge_cases_spec_only_quote_required_foreign_stale_promo_contradictory` [partly] (fixtures, not real pages); `sources/test_rate_pipeline.py::test_fetcher_backoff_retries_only_transient_errors_and_caches` [yes]
- *Workflow / output:* `sources refresh`; Rate updates page.
- *Limitations / dependencies:* The application's own HTTP client was BLOCKED from the build sandbox (proxy 403); no live success observed. Web extraction never run on a real page.
- *Acceptance test to mark complete:* On a normal network `sources refresh --provider kapsarc-gastat-cci` imports the latest CCI months with a manifest; one permitted real product page yields a candidate with correct evidence.

**RTE-06 - Official cost-index storage (GASTAT CCI) as escalation reference, never a unit price**  
*Status:* Implemented and tested · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/rate_updates/index_import.py::import_index_file`; `data/public_data/gastat_cci/kapsarc_cci_2026-04.records.json`
- *Tests:* `sources/test_rate_pipeline.py::test_real_cci_fixture_imports_as_index_observations_never_as_rates` [yes]; `sources/test_rate_pipeline.py::test_index_revision_keeps_both_values_and_bad_rows_are_rejected_with_reasons` [yes]
- *Workflow / output:* `index import|list`; Rate updates page.
- *Limitations / dependencies:* Stored only: no engine consumes index data (see RSK-05).
- *Acceptance test to mark complete:* Escalation assumption cites the stored index series and period it was derived from.

**EST-01 - Assembly-based consumption pricing with explicit waste basis, nested assemblies, cycle guard, double-count prevention**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/direct_cost.py::_material_like`; `app/estimators/direct_cost.py::_expand`; `app/services/assemblies.py::validate`; `app/services/assemblies.py::would_create_cycle`
- *Tests:* `unit/test_direct_cost.py::test_full_assembly_hand_calculated` [yes]; `unit/test_direct_cost.py::test_waste_not_applied_twice_by_validation` [yes]; `unit/test_direct_cost.py::test_nested_assembly_and_cycle_guard` [yes]; `unit/test_direct_cost.py::test_subcontract_double_count_blocked` [yes]
- *Workflow / output:* Estimate build-up with a 'basis' string per line.
- *Limitations / dependencies:* Factors are user-supplied; no automatic quantity-take-off logic.
- *Acceptance test to mark complete:* Hand-calculated assemblies (incl. nested) match engine amounts to the halala.

**EST-02 - Labour hours and crews: productivity bases (paid hours/unit, productive hours/unit, output per crew shift), overtime share**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/direct_cost.py::_labour`; `app/estimators/direct_cost.py::_hours_params`; `app/estimators/rate_build.py::blended_labour_rate`
- *Tests:* `unit/test_direct_cost.py::test_productive_hours_conversion` [yes]; `unit/test_direct_cost.py::test_missing_shift_assumption_blocks_crew_pricing` [yes]; `integration/test_full_workflow.py::test_initial_state_matches_independent_hand_calculations` [yes]
- *Workflow / output:* Labour lines show hours and basis.
- *Limitations / dependencies:* No learning-curve, congestion, height, climate or shift-fatigue adjustments (needs approved assumptions, EST-12).
- *Acceptance test to mark complete:* Crew-based item hours match a manual productivity calculation under each basis.

**EST-03 - Plant mobilisation/demobilisation lump sums applied once per resource**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/direct_cost.py::_plant_mobilisation`
- *Tests:* `unit/test_rate_build.py::test_plant_day_basis_uses_supplied_calendar` [partly] (build-up values); `integration/test_full_workflow.py::test_initial_state_matches_independent_hand_calculations` [yes]
- *Workflow / output:* Separate mobilisation line in the build-up.
- *Limitations / dependencies:* Once per project, not per phase/site.
- *Acceptance test to mark complete:* Plant used in two items is mobilised once; used in two phases on different sites is mobilised twice when so configured.

**EST-05 - Plant standby/idle and minimum hire periods applied to cost**  
*Status:* Implemented and tested · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/direct_cost.py::_plant_hire_terms`; `app/estimators/param_kinds.py::_plant_terms`; `app/services/governed.py::propose`
- *Tests:* `unit/test_governed_params.py::test_plant_min_hire_and_standby_hand_calculated` [yes] (top-up 3 h x 400 + standby 2 h x 25% x 400); `unit/test_governed_params.py::test_authority_source_and_ai_rules` [yes]
- *Workflow / output:* Governed `plant_hire_terms` per plant resource: minimum chargeable quantity (top-up line) and standby quantity at a stated percentage of the approved rate, priced at that resource's approved rate. Lines are labelled and flagged if the terms are unapproved.
- *Limitations / dependencies:* Terms are entered from the hire quotation/contract (none shipped). Minimum hire is applied per resource over the whole project, not per mobilisation/hire period. Depends on: DUR-05.
- *Acceptance test to mark complete:* Plant with 20% standby and a 1-month minimum hire prices correctly under a hand-calculated example.

**EST-07 - Quantity/unit conversion between BOQ unit and assembly unit**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/direct_cost.py::_convert_factor_unit`
- *Tests:* `unit/test_direct_cost.py::test_item_unit_conversion_to_assembly_unit` [yes]; `unit/test_direct_cost.py::test_incompatible_units_rejected` [yes]
- *Workflow / output:* Cost-line basis text.
- *Limitations / dependencies:* Same-dimension physical conversions only (see SCO-03).
- *Acceptance test to mark complete:* Incompatible units are refused with an explanation, never converted silently.

**EST-10 - Man-hour aggregation and histograms by craft/trade/area/period**  
*Status:* Implemented and tested · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/services/programme.py::manhours_report`; `app/estimators/direct_cost.py::_price_takeoff_item`
- *Tests:* `unit/test_programme_service.py::test_manhours_by_craft_wbs_division_hand_calculated` [yes]; `unit/test_programme_service.py::test_loading_blocks_without_calendar_and_weeks_with_calendar` [yes]
- *Workflow / output:* Own-labour man-hours by craft, cost code, division, WBS and item, and histograms over the programme (reports `manhours`, `loading`); ties out to the priced labour lines.
- *Limitations / dependencies:* Own labour only: subcontract and lump-sum items carry labour that is not counted (listed as items without hours). No crew/productivity actuals feedback loop. Depends on: DUR-04.
- *Acceptance test to mark complete:* A report totals man-hours by craft and trade for any project and by month once a programme exists; totals equal the sum of labour lines.

**EST-11 - Construction methodology: method statements, equipment selection, work sequencing that drives labour/plant quantities**  
*Status:* Partial · *needed from level:* 2 (applies at levels 2, 1) · *kind:* engine
- *Code:* `app/services/methods.py::comparison_report`; `app/services/methods.py::check_alternative`; `app/estimators/context.py::load_inputs`; `app/estimators/param_kinds.py::_method_alt`
- *Tests:* `unit/test_methods.py::test_alternative_is_compared_what_if_and_changes_nothing` [yes] (lean method: direct -225, hours -15, one month less staff -100; estimate fingerprint unchanged); `unit/test_methods.py::test_alternative_validation_and_unknown_items` [yes]
- *Workflow / output:* Method alternatives: named re-mappings of BOQ items to other approved assemblies (equipment/crew choices) and an optional implied duration, compared side by side with the base (direct/indirect/total cost, man-hours, plant hours, duration) without changing the estimate. Report `method_comparison`.
- *Limitations / dependencies:* A method statement is free text in the alternative's basis; the software does not generate methods, select equipment from site conditions, or derive sequencing from them. Assemblies for each method must already exist and be approved. Adoption is a normal approved re-mapping. Depends on: DUR-05.
- *Acceptance test to mark complete:* Two methods for the same work (crane vs pump placement) compare in cost, hours and duration with each assumption traceable.

**EST-12 - Productivity adjustment factors (height, congestion, climate, shift, remote site, learning) as approved assumptions applied to hours**  
*Status:* Implemented and tested · *needed from level:* 2 (applies at levels 2, 1) · *kind:* engine
- *Code:* `app/estimators/direct_cost.py::productivity_factors_for`; `app/estimators/direct_cost.py::_adjust_hours`; `app/estimators/param_kinds.py::_productivity`
- *Tests:* `unit/test_governed_params.py::test_combined_productivity_factors_are_multiplicative_and_hand_checked` [yes] (1.20 x 1.10 -> 132 h); `unit/test_governed_params.py::test_factor_scope_cost_prefix_and_wbs` [yes]; `unit/test_governed_params.py::test_unapproved_factor_is_flagged_loudly` [yes]; `unit/test_governed_params.py::test_project_scope_overrides_company_and_estimate_reads_it` [yes]; `unit/test_mto.py::test_productivity_factor_applies_to_derived_labour_only` [yes]; `integration/test_industrial_flow.py::test_piping_welds_from_pack_to_basis_of_estimate` [yes] (pack -> approved rates/factors -> 200 joints -> derivation -> approval -> 22,200 -> 24,400 with height factor -> 660 h -> roll-up, loading, risk, BoE)
- *Workflow / output:* Governed productivity factors (height, congestion, climate/heat, shift pattern, remote site, learning curve, access, permit-to-work, weather, other), scoped by cost-code prefix and/or WBS area, applied multiplicatively to assembly and take-off-derived labour hours; company-wide or project-specific; every application is recorded on the cost line.
- *Limitations / dependencies:* No factor value is shipped; each comes from company records with a stated source and is approved. Factors compound by multiplication - enter one combined factor where compounding would overstate. Learning-curve effects over time are not modelled, only a stated factor.
- *Acceptance test to mark complete:* A congestion factor of 1.15 approved as an assumption raises hours on tagged items only, appears in the basis string, and is visible in the impact analysis.

**EST-04 - Missing/unapproved/expired/index-only rates leave lines unpriced with indicative exposure reported separately**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/direct_cost.py::_price_line`; `app/estimators/estimate.py::compute_estimate`
- *Tests:* `unit/test_direct_cost.py::test_missing_rate_never_zero` [yes]; `unit/test_direct_cost.py::test_unapproved_rate_excluded_but_exposure_reported` [yes]; `reconciliation/test_recon.py::test_unpriced_item_and_missing_rate_are_critical` [yes]
- *Workflow / output:* UNPRICED lines in the build-up, dashboard exposure, Critical findings.
- *Limitations / dependencies:* Exposure for a truly missing rate is 'unknown' by design.
- *Acceptance test to mark complete:* A BOQ with 5 missing-rate items shows exactly 5 unpriced items and a Preliminary state; no total includes a guessed value.

**EST-06 - Estimate states (Complete / Complete with Provisional Inputs / Preliminary) and SHA-256 fingerprint for stale detection**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/estimate.py::fingerprint`; `app/estimators/estimate.py::_blockers`
- *Tests:* `integration/test_final_flow.py::test_final_flow_and_gates` [yes]; `integration/test_smoke_estimate.py::test_mini_project_end_to_end` [yes]
- *Workflow / output:* State banner on estimate pages and documents.
- *Limitations / dependencies:* State is derived; there is no client-specific state vocabulary.
- *Acceptance test to mark complete:* Changing any input changes the fingerprint and invalidates an approved version.

**EST-08 - Project-scoped provisional rate approval with mandatory reason, always disclosed**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/services/rates.py::approve_rate_provisional`
- *Tests:* `approvals/test_approval_rules.py::test_provisional_rate_requires_explicit_reason_role_and_project` [yes]; `approvals/test_approval_rules.py::test_provisional_input_stays_visible_in_estimate` [yes]
- *Workflow / output:* Estimate state 'Complete with Provisional Inputs'.
- *Limitations / dependencies:* Project-scoped only; a provisional approval is a per-project override and never becomes a global rate. No expiry date on the provisional approval itself.
- *Acceptance test to mark complete:* A provisional rate never affects another project and is listed in the estimate report.

**EST-09 - What-if assumption impact analysis (strict vs preliminary, override not persisted)**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
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
| ENG-01 | Engineering services estimating (discipline man-hours, deliverables, vendor-data review, design allowance) | IT Implemented and tested | 1 |
| ENG-02 | Home-office/overhead/G&A allocation and project-management costs for EPC | IT Implemented and tested | 1 |
| PRE-01 | Preliminaries and general requirements (division A): priced as BOQ items/assemblies or as field indirects, with double-count detection between the two | PA Partial | 5 |

**IND-01 - Field indirects: fixed, percent-of-direct, per day/week/month x approved duration; allocation (pro-rata, separate line, by trade); subcontract-included exclusion**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/indirect.py::compute_indirects`; `app/services/indirects.py::add_indirect`; `app/api/actions.py::add_standard_indirects`
- *Tests:* `unit/test_indirect_duration.py::test_methods_hand_calculated` [yes]; `unit/test_indirect_duration.py::test_unapproved_and_missing_amount_never_zero` [yes]; `unit/test_indirect_duration.py::test_included_in_subcontract_excluded_to_avoid_double_count` [yes]; `integration/test_workspace_ui.py::test_standard_indirect_categories_are_created_as_drafts_without_amounts_and_block_a_complete_estimate` [yes] (added by this audit)
- *Workflow / output:* Commercials tab; Indirect Costs sheet; 16 standard categories created as Draft with no amounts.
- *Limitations / dependencies:* Amounts are in project currency; no staffing-plan/histogram tie-in; staffing is entered as person-month lumps.
- *Acceptance test to mark complete:* All standard categories carry approved amounts with sources; changing the approved duration changes per-month items by the hand-calculated amount.

**IND-02 - Temporary facilities, mobilisation/demobilisation and site establishment as priced scope**  
*Status:* Partial · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/mto.py::derive`; `app/services/mto.py::apply`; `app/services/mto.py::preview`; `app/services/provisions.py::reserve_proposals`; `data/taxonomy/cost_codes.csv`; `data/indirects/indirect_categories.csv`; `app/estimators/indirect.py::compute_indirects`
- *Tests:* `unit/test_mto.py::test_engine_derive_hand_calculated_missing_and_skipped` [yes] (driver x factor x (1+waste); missing slot yields nothing); `unit/test_mto.py::test_apply_pricing_gate_and_hand_calculated_cost` [yes] (derived lines are Pending Review until a person approves the pricing); `unit/test_provisions.py::test_reserve_proposals_are_draft_indirects_with_hand_calculated_amounts` [yes]; `unit/test_indirect_duration.py::test_methods_hand_calculated` [partly] (method arithmetic only)
- *Workflow / output:* Pricing via division A items (99 definitions incl. labour/plant) or indirects. Template and reserve-rule framework added.
- *Limitations / dependencies:* Camp/temporary-facility quantities use the `temp.site_establishment` template and reserve rules; mobilisation lump sums come from rate build-ups and indirect items. Structure only: the template names the driver and the resource slots, but NO factor, productivity or consumption value is shipped - each is entered from company records as a governed `mto_factor` and approved. The driver quantity is the estimator's own measured figure; the software never measures drawings. Earlier audit note: No sizing logic (offices, camp, laydown, utilities) and no link from manpower/area to facility quantity. Depends on: DUR-04.
- *Acceptance test to mark complete:* Site establishment is derived from an approved manpower and area schedule using approved unit allowances.

**ENG-01 - Engineering services estimating (discipline man-hours, deliverables, vendor-data review, design allowance)**  
*Status:* Implemented and tested · *needed from level:* 1 (applies at levels 1) · *kind:* engine
- *Code:* `app/services/provisions.py::engineering_report`; `app/services/provisions.py::propose_engineering_indirects`; `app/estimators/param_kinds.py::_eng_basis`
- *Tests:* `unit/test_provisions.py::test_engineering_effort_costing_hand_calculated_and_unpriced_blocks` [yes] (12x30 + 4x50 = 560 h x 80 = 44,800; unpriced rate blocks the proposal)
- *Workflow / output:* Governed `engineering_basis` (discipline, deliverable, count, hours each, labour resource) costed at the resource's eligible approved hourly rate; per-discipline hours and cost; Draft indirect items proposed. Report `engineering`.
- *Limitations / dependencies:* No hours-per-deliverable are shipped - they come from company records or the engineering contractor's proposal. Vendor-data review, design growth and client-review cycles are only modelled if the user enters them as deliverables. Depends on: ENG-02.
- *Acceptance test to mark complete:* An engineering package is estimated from a deliverables list x approved hours x discipline rates, with a home-office rate build-up and reconciliation to the allowance.

**ENG-02 - Home-office/overhead/G&A allocation and project-management costs for EPC**  
*Status:* Implemented and tested · *needed from level:* 1 (applies at levels 1) · *kind:* engine
- *Code:* `app/services/provisions.py::overhead_report`; `app/services/provisions.py::propose_overhead_indirects`; `app/services/provisions.py::reserve_proposals`; `app/estimators/param_kinds.py::_pool`
- *Tests:* `unit/test_provisions.py::test_overhead_pool_share_hand_calculated` [yes] (5% of direct cost; SAR 5 per labour hour); `unit/test_provisions.py::test_reserve_proposals_are_draft_indirects_with_hand_calculated_amounts` [yes]
- *Workflow / output:* Governed annual overhead pools (cost and recovery base: direct cost, labour hours or selling price) give a project share; reserve rules give percentage provisions; both are proposed as Draft indirect items. Reports `overhead`; actions `propose_overhead_indirects`, `propose_reserves`.
- *Limitations / dependencies:* Annual cost and base come from the company's accounts (none shipped). Time-based home-office staffing (named managers by month) is not modelled - use indirect items with per-month methods.
- *Acceptance test to mark complete:* Home-office cost is built from approved rates x staffing and shown separately from field indirects and profit.

**PRE-01 - Preliminaries and general requirements (division A): priced as BOQ items/assemblies or as field indirects, with double-count detection between the two**  
*Status:* Partial · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/reconciliation/engine.py::collect_findings`; `app/estimators/indirect.py::compute_indirects`; `data/taxonomy/cost_codes.csv`; `data/indirects/indirect_categories.csv`
- *Tests:* `workspaces/test_audit_regressions.py::test_indirect_that_overlaps_priced_preliminaries_is_flagged` [yes] (added by this audit); `reconciliation/test_recon.py::test_duplicate_items_and_cost_in_multiple_packages` [partly] (duplicate detection across items/packages); `unit/test_indirect_duration.py::test_methods_hand_calculated` [yes] (indirect arithmetic)
- *Workflow / output:* Division A (10 sub-trades, 99 catalogue definitions) priced like any BOQ item; or the 16 standard indirect categories; reconciliation flags possible overlap (POSSIBLE_DUPLICATE_INDIRECT).
- *Limitations / dependencies:* The overlap rule is keyword based (false positives/negatives; it was untested before this audit). No preliminaries template, no time-related vs fixed split report by contract form, no site-staff histogram. Depends on: IND-01.
- *Acceptance test to mark complete:* A BOQ with preliminaries items and an overlapping indirect (e.g. security) raises POSSIBLE_DUPLICATE_INDIRECT; time-related and fixed preliminaries are reported separately and reconcile to the estimate.

### G. Taxes, duties, logistics

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| TAX-01 | VAT as dated, verified tax categories; unresolved tax never assumed; tax on tendered schedule per category | IT Implemented and tested | 5 |
| TAX-02 | Import landed-cost build-up: Incoterms, freight, insurance, customs duty, clearance, port charges, inland haulage | IT Implemented and tested | 3 |
| TAX-03 | Withholding tax, zakat/income tax treatment, expatriate levy and other employer statutory costs | PA Partial | 3 |
| TAX-04 | Logistics: transport to site, laydown, handling, storage, port-to-site, project-specific logistics plans | IT Implemented and tested | 3 |

**TAX-01 - VAT as dated, verified tax categories; unresolved tax never assumed; tax on tendered schedule per category**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/services/commercial.py::propose_tax_category`; `app/services/commercial.py::approve_tax_category`; `app/estimators/estimate.py::tax_rate_for`; `app/estimators/estimate.py::_tax_from_schedule`
- *Tests:* `unit/test_commercial.py::test_unresolved_tax_rate_never_assumed` [yes]; `unit/test_commercial.py::test_fixed_discount_and_multiple_tax_categories` [yes]; `unit/test_library_data.py::test_tax_and_fx_seeds_are_pending_until_a_human_verifies` [yes]
- *Workflow / output:* Commercial tab; final payable only when tax resolves.
- *Limitations / dependencies:* VAT-STD (15%) is seeded Pending Review; zero-rated/exempt/reverse-charge categories are not pre-seeded; tax recoverability stored, unused.
- *Acceptance test to mark complete:* A Commercial Approver verifies VAT-STD against current ZATCA text; zero-rated and exempt supplies priced in the same schedule produce the hand-calculated tax.

**TAX-02 - Import landed-cost build-up: Incoterms, freight, insurance, customs duty, clearance, port charges, inland haulage**  
*Status:* Implemented and tested · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/landed_cost.py::landed`; `app/services/landed.py::compute`; `app/services/landed.py::propose_landed_rate`; `app/estimators/param_kinds.py::_landed_terms`
- *Tests:* `unit/test_landed_labour_exposure.py::test_landed_cost_hand_calculated_with_exposure` [yes] (FOB base -> freight, insurance, duty, clearance, port, handling = 4,504.0934375); `unit/test_landed_labour_exposure.py::test_landed_validation_and_missing_fx` [yes]; `unit/test_landed_labour_exposure.py::test_landed_rate_is_a_proposal_that_needs_normal_approval_and_changes_exposure` [yes]
- *Workflow / output:* Ordered landed-cost components (percentage of base / earlier components / cumulative, per unit, per shipment, in any currency) from approved terms turn an APPROVED base rate into a Draft/Pending derived rate with its build-up and currency exposure recorded; normal rate approval still applies.
- *Limitations / dependencies:* No Incoterm template, freight, insurance or duty value is shipped; tariff classification and customs rules are the user's inputs. FX is converted at the approved rate on the proposal date. Depends on: CUR-03.
- *Acceptance test to mark complete:* An imported equipment item is priced FOB -> CIF -> duty -> clearance -> delivered with each step an approved input and FX at the right date.

**TAX-03 - Withholding tax, zakat/income tax treatment, expatriate levy and other employer statutory costs**  
*Status:* Partial · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/labour_costs.py::statutory_monthly`; `app/services/labour.py::propose_labour_rate`; `app/estimators/param_kinds.py::_labour_statutory`
- *Tests:* `unit/test_landed_labour_exposure.py::test_statutory_monthly_and_workforce_blend_hand_calculated` [yes]; `unit/test_landed_labour_exposure.py::test_labour_buildup_with_user_rules_and_workforce_check` [yes]
- *Workflow / output:* Employer-side statutory/mobilisation labour on-costs (levy, social insurance, end-of-service accrual, visa/iqama, medical) as governed rules feeding the labour rate build-up.
- *Limitations / dependencies:* Withholding tax on foreign subcontractors, zakat/income tax treatment and corporate tax effects are NOT modelled (tax categories cover VAT only). No rule value is shipped. Depends on: SAU-03.
- *Acceptance test to mark complete:* Treatment of each is an explicit approved assumption with a tested effect on cost or price.

**TAX-04 - Logistics: transport to site, laydown, handling, storage, port-to-site, project-specific logistics plans**  
*Status:* Implemented and tested · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/landed_cost.py::landed`; `app/services/landed.py::propose_landed_rate`; `app/estimators/mto.py::derive`
- *Tests:* `unit/test_landed_labour_exposure.py::test_landed_rate_is_a_proposal_that_needs_normal_approval_and_changes_exposure` [yes] (local haulage per unit + freight %); `unit/test_mto.py::test_templates_are_structure_only_and_cover_the_industrial_gaps` [yes]
- *Workflow / output:* Domestic logistics (transport to site, handling, storage, port-to-site) use the same governed component terms as imports; project-specific logistics scope can also be derived from the temporary-facilities take-off template.
- *Limitations / dependencies:* Laydown/storage durations and rates are inputs. No logistics cost model for remote-site rotation beyond the template slots.
- *Acceptance test to mark complete:* Logistics cost for 50 imported items derived from weights/volumes and approved lane rates.

### H. Project duration, sequencing and resource loading

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| DUR-01 | Time-related costs require a human-approved duration and approved working calendar | IT Implemented and tested | 5 |
| DUR-02 | CPM duration from human-entered tasks (finish-to-start), converted to months with an approved calendar; proposal only | IT Implemented and tested | 4 |
| DUR-03 | Labour-hours-derived duration cross-check (formula) | IT Implemented and tested | 4 |
| DUR-04 | Resource loading: manpower/plant histograms and peaks over time | IT Implemented and tested | 3 |
| DUR-05 | Construction sequencing, phasing, areas/units and logic-linked cost-to-schedule tie-in | IT Implemented and tested | 3 |

**DUR-01 - Time-related costs require a human-approved duration and approved working calendar**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/indirect.py::compute_indirects`; `app/services/indirects.py::approve_duration`
- *Tests:* `unit/test_indirect_duration.py::test_duration_not_approved_blocks_duration_costs_but_not_fixed` [yes]; `unit/test_indirect_duration.py::test_calendar_missing_flags` [yes]
- *Workflow / output:* Commercials tab.
- *Limitations / dependencies:* Duration is a single project-level figure; per-phase or per-area durations are not supported (DUR-05).
- *Acceptance test to mark complete:* Time-based indirect lines resolve only after duration approval.

**DUR-02 - CPM duration from human-entered tasks (finish-to-start), converted to months with an approved calendar; proposal only**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/programme.py::schedule`; `app/estimators/programme.py::parse_predecessors`; `app/estimators/programme.py::Calendar`; `app/services/programme.py::schedule_report`; `app/services/indirects.py::set_tasks`; `app/services/indirects.py::propose_duration_from_schedule`; `app/estimators/duration.py::cpm`
- *Tests:* `unit/test_programme.py::test_four_relationship_types_forward_and_backward_by_hand` [yes] (FS/SS/FF/SF, lags, float, free float, critical path); `unit/test_programme.py::test_start_to_finish_and_negative_lag_lead` [yes]; `unit/test_programme.py::test_constraints_and_negative_float` [yes]; `unit/test_programme.py::test_cycle_unknown_duplicate_negative_duration_rejected` [yes]; `unit/test_programme.py::test_parse_predecessors_handles_codes_with_dashes_and_types` [yes]; `unit/test_programme.py::test_calendar_dates_skip_non_working_days_and_holidays` [yes]; `unit/test_programme_service.py::test_task_storage_syntax_and_validation` [yes]; `unit/test_indirect_duration.py::test_schedule_tasks_to_duration_proposal_needs_approved_calendar_and_human_approval` [yes] (duration stays a proposal until a person approves it); `integration/test_workspace_ui.py::test_schedule_actions_are_reachable_from_the_api_and_respect_roles` [yes]
- *Workflow / output:* Programme engine with FS/SS/FF/SF relationships, lags and leads, SNET/FNLT constraints, total/free float, driving and critical path, working calendar (start date, working weekdays, holidays) and dates. UI: Structure & programme; reports `schedule`; the duration remains a proposal until approved.
- *Limitations / dependencies:* Task durations, links, constraints and the calendar are typed in by a person (no import from Primavera/MS Project, no Gantt chart, no resource-levelling, no multiple calendars per task). Working weekdays and holidays are never assumed.
- *Acceptance test to mark complete:* A 200-task network with SS/FF/lag relationships imported from a schedule file yields the same critical path and finish as the scheduling tool (import not built).

**DUR-03 - Labour-hours-derived duration cross-check (formula)**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/duration.py::labour_derived_months`
- *Tests:* `unit/test_indirect_duration.py::test_labour_derived_duration_is_a_formula` [yes]
- *Workflow / output:* Proposal with basis note.
- *Limitations / dependencies:* Assumes constant crew size and no logic between activities.
- *Acceptance test to mark complete:* Matches a hand calculation.

**DUR-04 - Resource loading: manpower/plant histograms and peaks over time**  
*Status:* Implemented and tested · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/loading.py::spread`; `app/estimators/loading.py::histogram`; `app/services/programme.py::loading_report`; `app/services/programme.py::assign_lines_to_tasks`
- *Tests:* `unit/test_programme_service.py::test_loading_spread_is_exact_and_fractional_edges_hand_checked` [yes]; `unit/test_programme_service.py::test_loading_blocks_without_calendar_and_weeks_with_calendar` [yes] (hand-calculated weekly histogram); `unit/test_programme_service.py::test_untied_quantities_are_reported_not_smeared` [yes]; `unit/test_programme_service.py::test_equally_specific_tasks_share_in_proportion_to_duration` [yes]
- *Workflow / output:* Time-phased labour hours / plant hours / cost histograms by week, month or working-day block with peaks per resource and an explicit 'unscheduled' bucket; ties out to the estimate. Report `loading`.
- *Limitations / dependencies:* Uniform spread over each task's working days (stated simplification, no S-curve shaping); cost lines reach tasks only through the task's declared cost-code prefix / WBS scope; manpower from subcontract lump sums is not counted. Depends on: EST-10, DUR-05.
- *Acceptance test to mark complete:* Monthly manpower by craft from the programme x hours; peak and total reconcile to the estimate's total hours.

**DUR-05 - Construction sequencing, phasing, areas/units and logic-linked cost-to-schedule tie-in**  
*Status:* Implemented and tested · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/services/programme.py::assign_lines_to_tasks`; `app/services/programme.py::loading_report`; `app/estimators/programme.py::schedule`; `app/services/wbs.py::assign_items`
- *Tests:* `unit/test_programme_service.py::test_loading_blocks_without_calendar_and_weeks_with_calendar` [yes]; `unit/test_programme_service.py::test_equally_specific_tasks_share_in_proportion_to_duration` [yes]; `unit/test_wbs_rollup.py::test_wbs_scoped_productivity_factor_changes_only_that_area` [yes]
- *Workflow / output:* Cost-to-schedule tie-in: tasks declare the WBS node and/or cost-code prefix they carry; the most specific task takes the cost and hours; shared scopes split by duration. Areas/units come from the WBS.
- *Limitations / dependencies:* Construction logic (which task follows which) is the estimator's input; the software does not propose sequences or phasing. Cost not tied to any task is reported separately. Depends on: LIB-02.
- *Acceptance test to mark complete:* Costs are assigned to activities; the programme can be re-sequenced and time-dependent costs and escalation update accordingly.

### I. Basis of Estimate, scope definition, maturity and exclusions

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| BOE-01 | Scope register: inclusions, exclusions, qualifications, clarifications (with evidence), cross-checks against priced scope and the offer | IT Implemented and tested | 4 |
| BOE-02 | Assumptions register (322 definitions) with approval, project overrides, validity and impact analysis | IT Implemented and tested | 5 |
| BOE-03 | Basis of Estimate document (scope, design basis, methodology, rate/productivity sources, exclusions, assumptions, risks, maturity, accuracy) | IT Implemented and tested | 3 |
| BOE-04 | Estimate classification (AACE or client-specific) with maturity indicators and accuracy range | IT Implemented and tested | 3 |
| BOE-05 | Design-maturity/completeness checks (MTO completeness, % engineered, drawing/spec revision control) | PA Partial | 3 |

**BOE-01 - Scope register: inclusions, exclusions, qualifications, clarifications (with evidence), cross-checks against priced scope and the offer**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/services/registers.py::add_scope_entry`; `app/services/registers.py::resolve_clarification`; `app/reconciliation/engine.py::collect_findings`
- *Tests:* `reconciliation/test_recon.py::test_scope_mismatches_exclusion_vs_priced` [yes]; `reconciliation/test_recon.py::test_offer_and_pricing_schedule_discrepancies` [yes]; `approvals/test_ai_boundary.py::test_clarification_suggestions_become_open_items_never_resolved` [partly]
- *Workflow / output:* Clarifications & risk tab; Inclusions and Exclusions sheet; offer letter.
- *Limitations / dependencies:* Free text; no clause library or requirement-to-scope traceability matrix.
- *Acceptance test to mark complete:* Every tender requirement maps to a scope entry or clarification; unmapped requirements are listed.

**BOE-02 - Assumptions register (322 definitions) with approval, project overrides, validity and impact analysis**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/services/assumptions.py::set_override`; `app/services/assumptions.py::resolve`; `data/assumptions/assumptions_register.csv`
- *Tests:* `approvals/test_approval_rules.py::test_project_override_does_not_change_global_and_needs_approval` [yes]; `unit/test_library_data.py::test_assumption_register_has_no_invented_numbers` [yes]; `workspaces/test_workspaces.py::test_project_assumption_override_does_not_change_global_default` [yes]
- *Workflow / output:* Assumptions tab; estimate report lists assumptions in use.
- *Limitations / dependencies:* Only a minority of definitions are consumed by an engine (labour hours, plant utilisation, calendar, rounding, waste refs); the rest are documentation obligations.
- *Acceptance test to mark complete:* Every assumption an engine reads is listed in the BoE with value, status, source.

**BOE-03 - Basis of Estimate document (scope, design basis, methodology, rate/productivity sources, exclusions, assumptions, risks, maturity, accuracy)**  
*Status:* Implemented and tested · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/services/boe.py::build_boe`; `app/services/boe.py::generate_boe`; `app/services/boe.py::render_markdown`; `app/services/boe.py::render_docx`
- *Tests:* `unit/test_profiles_boe.py::test_boe_contains_facts_flags_synthetic_and_leaves_judgement_blank` [yes]
- *Workflow / output:* Basis of Estimate generated as .md and .docx into the project workspace (scope, BOQ imports, pricing basis and rate sources, assemblies, factors, assumptions, take-off derivations, indirects, programme, commercial, risks, classification, client-profile status, exceptions, approvals) with six judgement sections left as [TO BE COMPLETED BY ESTIMATOR].
- *Limitations / dependencies:* Facts only - methodology, design basis, site conditions and risk commentary must be written by the estimator. Not a client-format BoE (no client template). Depends on: BOE-04.
- *Acceptance test to mark complete:* A BoE generated for a project contains every section of the client's/organisation's BoE template populated from recorded data, with missing sections explicitly shown as missing.

**BOE-04 - Estimate classification (AACE or client-specific) with maturity indicators and accuracy range**  
*Status:* Implemented and tested · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/services/profiles.py::classification_report`; `app/estimators/param_kinds.py::_classification_scheme`; `app/estimators/param_kinds.py::_maturity`
- *Tests:* `unit/test_profiles_boe.py::test_classification_requires_scheme_and_maturity_and_follows_them` [yes] (class from approved scheme bands; range applied to total cost; band edge)
- *Workflow / output:* Class and accuracy range follow an APPROVED classification scheme (bands, ranges and source document entered by the company) and the estimator's approved maturity statement, shown beside measured maturity facts. Report `classification`.
- *Limitations / dependencies:* The software holds no AACE or client scheme: class definitions and ranges are entered with their source. The class is not derived from drawings or by the software. No client-specific classification scheme is claimed.
- *Acceptance test to mark complete:* A selectable classification profile (configuration file) sets required deliverable-maturity checks; the estimate shows its class, unmet criteria and the profile's stated accuracy range, and approval is blocked if mandatory criteria fail.

**BOE-05 - Design-maturity/completeness checks (MTO completeness, % engineered, drawing/spec revision control)**  
*Status:* Partial · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/services/profiles.py::project_facts`; `app/services/mto.py::status_report`; `app/reporting/completeness.py::project_completeness`; `app/services/profiles.py::classification_report`
- *Tests:* `unit/test_profiles_boe.py::test_compliance_matrix_never_claims_beyond_loaded_requirements` [yes]; `unit/test_mto.py::test_stale_detection_after_factor_or_driver_change` [yes]
- *Workflow / output:* Measured maturity facts (unpriced %, WBS-assigned %, open clarifications, stale take-off derivations, synthetic/provisional use) in classification, profile checks and the completeness report.
- *Limitations / dependencies:* No % engineered or MTO-completeness measure exists (the software does not know what the drawings contain); drawing/spec revision is recorded text. Completeness is counted from the database only. Depends on: BOE-04.
- *Acceptance test to mark complete:* Completeness lists unresolved design items per discipline against the chosen classification profile.

### J. Escalation, contingency, quantified risk, uncertainty, currency

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| RSK-01 | Contingency with explicit base (direct or direct+indirect) and rate as policy fields; double-count guards | IT Implemented and tested | 5 |
| RSK-02 | Named risk allowances (percentage or fixed) in the commercial policy | IT Implemented and tested | 4 |
| RSK-03 | Risk register (probability, impact, cost exposure, mitigation) | IT Implemented and tested | 3 |
| RSK-04 | Quantified risk and uncertainty: expected value, range estimating or Monte Carlo (P50/P80), correlation, contingency derivation | IT Implemented and tested | 3 |
| RSK-05 | Escalation: single percentage on an explicit base | IT Implemented and tested | 4 |
| CUR-01 | Foreign-currency rates converted with APPROVED, dated FX; unresolved FX leaves the line unpriced | IT Implemented and tested | 4 |
| CUR-02 | Non-SAR project currency with SAR rates converted by approved FX | IT Implemented and tested | 3 |
| CUR-03 | Currency exposure and hedging (multi-currency packages, exposure by currency, FX sensitivity) | IT Implemented and tested | 2 |

**RSK-01 - Contingency with explicit base (direct or direct+indirect) and rate as policy fields; double-count guards**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/commercial.py::compute_commercial`; `app/estimators/commercial.py::validate_policy`
- *Tests:* `unit/test_commercial.py::test_contingency_base_is_explicit_and_changes_result` [yes]; `unit/test_commercial.py::test_policy_validation_and_double_count_guards` [yes]
- *Workflow / output:* Commercial calculation trace; policy approval by Commercial Approver.
- *Limitations / dependencies:* Single project-wide percentage; no per-discipline or risk-derived contingency.
- *Acceptance test to mark complete:* Contingency of x% on the stated base reproduces by hand.

**RSK-02 - Named risk allowances (percentage or fixed) in the commercial policy**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/commercial.py::compute_commercial`
- *Tests:* `unit/test_commercial.py::test_trace_documents_every_step` [partly]; `unit/test_commercial.py::test_policy_validation_and_double_count_guards` [yes]
- *Workflow / output:* Risk allowances in the commercial trace.
- *Limitations / dependencies:* Allowances are entered by hand; they are not derived from the risk register. Depends on: RSK-03.
- *Acceptance test to mark complete:* Each allowance traces to a named, approved risk entry.

**RSK-03 - Risk register (probability, impact, cost exposure, mitigation)**  
*Status:* Implemented and tested · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/services/registers.py::quantify_risk`; `app/services/registers.py::add_risk`; `app/reconciliation/ext_rules.py::collect_extended`
- *Tests:* `unit/test_risk_escalation.py::test_quantify_risk_validation` [yes]; `reconciliation/test_extended_rules.py::test_extended_findings_raised_with_configured_severity` [yes] (unquantified open risks are flagged)
- *Workflow / output:* Risk register entries carry a human-entered probability, three-point cost range, schedule days, category and response with the stated basis; unquantified open risks raise a Low reconciliation finding.
- *Limitations / dependencies:* No default probabilities or ranges; risks are identified by people. Correlations between risks are not modelled.
- *Acceptance test to mark complete:* Risks have numeric probability and impact distributions and feed RSK-04.

**RSK-04 - Quantified risk and uncertainty: expected value, range estimating or Monte Carlo (P50/P80), correlation, contingency derivation**  
*Status:* Implemented and tested · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/montecarlo.py::simulate`; `app/estimators/montecarlo.py::expected_value`; `app/services/risk.py::risk_report`
- *Tests:* `unit/test_risk_escalation.py::test_expected_value_hand_calculated` [yes]; `unit/test_risk_escalation.py::test_simulation_is_reproducible_ordered_and_close_to_expected_value` [yes] (seeded, reproducible, P10-P90 ordered); `unit/test_risk_escalation.py::test_degenerate_cases_are_exact` [yes]; `unit/test_risk_escalation.py::test_risk_report_proposes_provision_and_compares_with_policy` [yes]
- *Workflow / output:* Expected value and seeded Monte Carlo (independent Bernoulli x triangular risks plus range-estimate deviations) giving P10/P50/Pxx/P90, per-risk contribution, histogram and schedule-days percentiles; proposes a provision and compares it with the commercial policy's contingency + risk. Report `risk`.
- *Limitations / dependencies:* Independence assumed (no correlation matrix), triangular distributions only, schedule impacts summed without critical-path logic. The result is a PROPOSAL; the commercial policy is changed only by an approved policy revision. No inputs shipped. Depends on: RSK-03.
- *Acceptance test to mark complete:* A seeded Monte Carlo over approved distributions reproduces published P50/P80 within tolerance; contingency derived at a client-selected confidence level.

**RSK-05 - Escalation: single percentage on an explicit base**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/escalation.py::phase`; `app/estimators/escalation.py::factor`; `app/services/risk.py::escalation_report`; `app/estimators/param_kinds.py::_escalation`
- *Tests:* `unit/test_risk_escalation.py::test_escalation_factor_and_phasing_hand_calculated` [yes] ((1+10%)^(6/12) = 1.0488...); `unit/test_risk_escalation.py::test_escalation_report_hand_calculated_and_scoped` [yes]; `unit/test_risk_escalation.py::test_escalation_scope_by_kind_and_overlap_protection` [yes] (overlapping profiles refused)
- *Workflow / output:* Time-phased escalation by programme month from each approved profile's base date, scoped by cost kind and/or cost-code prefix; overlap is refused so nothing is escalated twice; official index values can be shown beside it. Report `escalation`. The policy's single-percentage escalation remains available.
- *Limitations / dependencies:* Percentages and base dates are the company's decision (no forecast, no index-derived default). Cost not tied to a task is not escalated and is listed. Compounding is annual-rate continuous-fraction. Depends on: DUR-05, RTE-06.
- *Acceptance test to mark complete:* Escalation is computed per cost element over the programme from an approved index and base date with hand-checkable results.

**CUR-01 - Foreign-currency rates converted with APPROVED, dated FX; unresolved FX leaves the line unpriced**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/direct_cost.py::_fx`; `app/services/commercial.py::approve_fx`
- *Tests:* `unit/test_direct_cost.py::test_foreign_currency_requires_approved_fx` [yes]; `procurement/test_procurement.py::test_leveling_normalisation_tax_currency_units` [yes]
- *Workflow / output:* FX_MISSING exception; Settings FX table.
- *Limitations / dependencies:* USD/SAR 3.75 seeded Pending Review. Single rate per pair/date; indirect items are not currency-tagged.
- *Acceptance test to mark complete:* A USD rate converts at the approved dated rate; a Pending Review rate is never used.

**CUR-02 - Non-SAR project currency with SAR rates converted by approved FX**  
*Status:* Implemented and tested · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/direct_cost.py::_Ctx`; `app/estimators/direct_cost.py::_fx`
- *Tests:* `workspaces/test_audit_regressions.py::test_non_sar_project_currency_needs_an_approved_fx_rate_then_converts` [yes] (added by this audit)
- *Workflow / output:* Estimate in the project currency.
- *Limitations / dependencies:* The UI project form does not expose project currency (set through the service/API); commercial policy amounts and tax are not currency-aware.
- *Acceptance test to mark complete:* A USD project with mixed SAR/USD rates produces a USD schedule, with every conversion in the basis text.

**CUR-03 - Currency exposure and hedging (multi-currency packages, exposure by currency, FX sensitivity)**  
*Status:* Implemented and tested · *needed from level:* 2 (applies at levels 2, 1) · *kind:* engine
- *Code:* `app/services/landed.py::exposure_report`; `app/estimators/param_kinds.py::_hedge`
- *Tests:* `unit/test_landed_labour_exposure.py::test_exposure_report_split_hedge_and_sensitivity` [yes] (USD 3,750 SAR-equivalent, 60% hedged, 10% shock -> 150); `unit/test_landed_labour_exposure.py::test_landed_rate_is_a_proposal_that_needs_normal_approval_and_changes_exposure` [yes]
- *Workflow / output:* Priced direct cost by quotation currency (landed-cost rates split by their recorded exposure), approved hedge cover per currency and what-if sensitivity steps. Report `currency_exposure`.
- *Limitations / dependencies:* Sensitivity steps are what-if magnitudes, not forecasts. Hedge instruments are recorded as cover percentages, not modelled. Home-currency items carry no FX exposure in the view. Depends on: CUR-01.
- *Acceptance test to mark complete:* A report lists cost by original currency and the effect of +/-x% FX movement.

### K. Supplier quotations, bid levelling and procurement

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| PRO-01 | Procurement needs detection from the strict estimate (missing/expired/unapproved/low-confidence rates), packages by trade | IT Implemented and tested | 4 |
| PRO-02 | RFQ drafting (English; Arabic draft) with XLSX/DOCX export for manual issue; no email sent, no invented contacts | IT Implemented and tested | 4 |
| PRO-03 | Quotation capture, validity/expiry, tax and delivery basis, unit/currency, deviations/exclusions; import from completed RFQ sheet | IT Implemented and tested | 4 |
| PRO-04 | Bid levelling: normalised price (tax, currency, units), coverage, missing items, adjustments (approved), spec differences | IT Implemented and tested | 4 |
| PRO-05 | Supplier selection requiring human approval with reasons and value-threshold role | IT Implemented and tested | 4 |
| PRO-06 | Vendor prequalification, technical bid evaluation scoring, long-lead tracking, vendor data/ITP, PO/subcontract award management | IT Implemented and tested | 2 |
| PRO-07 | Subcontract package scope/interface matrix and double-count control across packages | IT Implemented and tested | 4 |

**PRO-01 - Procurement needs detection from the strict estimate (missing/expired/unapproved/low-confidence rates), packages by trade**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/procurement/needs.py::detect_needs`
- *Tests:* `procurement/test_procurement.py::test_missing_rates_become_procurement_requirements` [yes]; `procurement/test_procurement.py::test_unapproved_and_expired_rates_detected_with_indicative_exposure` [yes]
- *Workflow / output:* Procurement & RFQs tab.
- *Limitations / dependencies:* Packaging is by cost-code division; no custom bid packages or long-lead flags.
- *Acceptance test to mark complete:* Needs register equals the unpriced-line set of the estimate.

**PRO-02 - RFQ drafting (English; Arabic draft) with XLSX/DOCX export for manual issue; no email sent, no invented contacts**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/procurement/rfq.py::create_rfq`; `app/procurement/rfq.py::export_xlsx`; `app/procurement/rfq.py::export_docx`
- *Tests:* `procurement/test_procurement.py::test_rfq_generation_content_and_exports` [yes]; `procurement/test_procurement.py::test_arabic_rfq_template_and_unknown_language` [yes]; `procurement/test_procurement.py::test_supplier_contacts_need_a_source` [yes]
- *Workflow / output:* RFQ page; files in '6. Procurement & Quotations'.
- *Limitations / dependencies:* Generic RFQ; no client technical-requirements appendices, ITB forms, vendor-data-requirements lists. Arabic text is a machine draft. Depends on: SAU-06.
- *Acceptance test to mark complete:* Client RFQ template (profile) populated with scope, specs and mandatory forms.

**PRO-03 - Quotation capture, validity/expiry, tax and delivery basis, unit/currency, deviations/exclusions; import from completed RFQ sheet**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/procurement/quotes.py::create_quotation`; `app/procurement/quotes.py::import_quotation_lines`; `app/procurement/quotes.py::validity`
- *Tests:* `procurement/test_procurement.py::test_quote_import_from_completed_rfq_sheet` [yes]; `procurement/test_procurement.py::test_quote_validity_and_expiry` [yes]; `procurement/test_procurement.py::test_quote_edit_rules_and_approval` [yes]
- *Workflow / output:* Quotations tab.
- *Limitations / dependencies:* Manual entry/CSV/XLSX; no PDF quotation parsing (optional AI extraction takes pasted text only and is live-unverified).
- *Acceptance test to mark complete:* Quote totals and line values equal the supplier document.

**PRO-04 - Bid levelling: normalised price (tax, currency, units), coverage, missing items, adjustments (approved), spec differences**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/procurement/leveling.py::level_package`; `app/procurement/leveling.py::add_adjustment`
- *Tests:* `procurement/test_procurement.py::test_leveling_normalisation_tax_currency_units` [yes]; `procurement/test_procurement.py::test_leveling_missing_items_quantity_difference_discount_and_adjustments` [yes]
- *Workflow / output:* Compare quotations; Quote Comparison sheet.
- *Limitations / dependencies:* Price-only levelling; no weighted technical/commercial scoring or technical-compliance matrix beyond compliance flags.
- *Acceptance test to mark complete:* A 5-bidder package is levelled with each difference explained and reproduces by hand.

**PRO-05 - Supplier selection requiring human approval with reasons and value-threshold role**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/procurement/selection.py::propose_selection`; `app/procurement/selection.py::decide_selection`
- *Tests:* `procurement/test_procurement.py::test_supplier_selection_needs_human_approval_and_reasons` [yes]; `procurement/test_procurement.py::test_high_value_selection_requires_commercial_approver` [yes]
- *Workflow / output:* Quotations tab.
- *Limitations / dependencies:* Threshold is a single configured SAR value (approval_thresholds); no award/PO document, delegation-of-authority matrix or multi-stage approval chain.
- *Acceptance test to mark complete:* Selection cannot be approved without reason when not lowest like-for-like; threshold role enforced.

**PRO-06 - Vendor prequalification, technical bid evaluation scoring, long-lead tracking, vendor data/ITP, PO/subcontract award management**  
*Status:* Implemented and tested · *needed from level:* 2 (applies at levels 2, 1) · *kind:* engine
- *Code:* `app/estimators/bid_eval.py::evaluate`; `app/services/bids.py::record_score`; `app/services/bids.py::evaluation_report`; `app/services/bids.py::add_long_lead`; `app/services/bids.py::long_lead_report`; `app/estimators/param_kinds.py::_eval_criteria`
- *Tests:* `unit/test_bids_scope.py::test_evaluation_hand_calculated_with_gate_minimum_and_incomplete` [yes] (Q2 79 > Q1 76; gate and minimum disqualify; incomplete not ranked); `unit/test_bids_scope.py::test_weights_must_total_100_and_passfail_has_no_weight` [yes]; `unit/test_bids_scope.py::test_scores_need_evidence_valid_ranges_and_authority` [yes]; `unit/test_bids_scope.py::test_report_uses_levelled_prices_and_latest_score` [yes]; `unit/test_bids_scope.py::test_long_lead_dates_hand_calculated` [yes]
- *Workflow / output:* Approved evaluation criteria (weights sum to 100, pass/fail gates, minimum scores, prequalification or bid stage), evidence-bearing scores, weighted ranking with levelled prices, and long-lead tracking (latest order date, float, vendor-data due/received). Reports `bid_evaluation`, `long_lead`; late items raise reconciliation findings. Advisory: selection/award stay the separate human-approved procurement decision.
- *Limitations / dependencies:* Criteria and weights come from the tender evaluation plan (none shipped). Vendor prequalification is scored with the same engine; certificates/financial checks are recorded as evidence text, not verified. No supplier performance history.
- *Acceptance test to mark complete:* A package award produces an award record, delivery milestones and technical/commercial scores traceable to the bid evaluation.

**PRO-07 - Subcontract package scope/interface matrix and double-count control across packages**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/services/bids.py::set_scope`; `app/services/bids.py::interface_report`; `app/reconciliation/ext_rules.py::collect_extended`
- *Tests:* `unit/test_bids_scope.py::test_interface_matrix_detects_double_count_gap_and_open_interface` [yes]; `reconciliation/test_extended_rules.py::test_package_double_count_is_critical_and_cannot_be_waived` [yes]
- *Workflow / output:* Package scope / interface matrix per BOQ item or cost-code prefix (included / excluded / by others with a named counterpart); finds items included in two packages (Critical, cannot be waived), subcontract items in no package and interfaces the counterpart does not close. Report `interface_matrix`.
- *Limitations / dependencies:* The matrix is typed by people; the software does not read subcontract documents. It is only checked once at least one scope entry exists.
- *Acceptance test to mark complete:* Interface matrix completeness is reported per package.

### L. Cost control: CBS roll-ups, benchmarks, cash flow, forecasts, change orders, revisions

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| CTL-01 | Actual-cost capture with mandatory source; estimate-vs-actual and productivity variance by cost code/resource | IT Implemented and tested | 4 |
| CTL-02 | Estimate revision control: frozen versions, version differences, approval status per version | IT Implemented and tested | 4 |
| CTL-03 | Benchmarking: cost ratios, historical analogues, rate/productivity reasonableness checks | IT Implemented and tested | 3 |
| CTL-04 | Cash flow / S-curve / payment-schedule forecast and financing cost | IT Implemented and tested | 3 |
| CTL-05 | Forecasting and earned-value control during execution | IT Implemented and tested | 1 |
| CTL-06 | Change orders / variation management after award (pricing, approval, audit, cumulative effect) | IT Implemented and tested | 1 |
| CTL-07 | Cost roll-up by CBS level (division, sub-trade, cost code) | IT Implemented and tested | 4 |

**CTL-01 - Actual-cost capture with mandatory source; estimate-vs-actual and productivity variance by cost code/resource**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/reporting/history.py::record_actual`; `app/reporting/history.py::estimate_vs_actual`; `app/reporting/history.py::productivity_variance`
- *Tests:* `integration/test_backup_datasets_cli.py::test_actuals_need_a_source_and_variance_uses_only_entered_data` [yes]
- *Workflow / output:* Reports tab (enter actual; variance tables).
- *Limitations / dependencies:* Manual entry; no ledger import; no commitment tracking.
- *Acceptance test to mark complete:* Import a project cost ledger and reconcile variance to ledger totals.

**CTL-02 - Estimate revision control: frozen versions, version differences, approval status per version**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/services/estimates.py::freeze_version`; `app/reconciliation/engine.py::collect_findings`
- *Tests:* `reconciliation/test_recon.py::test_version_difference_and_report` [yes]; `integration/test_final_flow.py::test_final_flow_and_gates` [yes]
- *Workflow / output:* Reconciliation tab versions list.
- *Limitations / dependencies:* No revision-comparison report by cost code; only a finding.
- *Acceptance test to mark complete:* Compare v1 and v2 by CBS code with explained deltas.

**CTL-03 - Benchmarking: cost ratios, historical analogues, rate/productivity reasonableness checks**  
*Status:* Implemented and tested · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/services/provisions.py::benchmark_report`; `app/estimators/param_kinds.py::_benchmark`; `app/reconciliation/ext_rules.py::collect_extended`
- *Tests:* `unit/test_provisions.py::test_benchmark_report_flags_outliers_and_says_nothing_without_ranges` [yes]; `unit/test_provisions.py::test_benchmark_validation` [yes]; `reconciliation/test_extended_rules.py::test_extended_findings_raised_with_configured_severity` [yes]
- *Workflow / output:* Reasonableness checks against the company's own approved ranges: unit cost per BOQ unit by cost prefix, share of direct cost by kind, hours per unit; outliers raise a Medium reconciliation finding. Report `benchmarks`.
- *Limitations / dependencies:* No benchmark ranges are shipped - without them no check is made (and it says so). Currency must match (no silent conversion). Historical analogue search beyond the existing similar-item search is not built.
- *Acceptance test to mark complete:* Estimate is compared with approved benchmark ranges; deviations beyond an approved threshold raise findings.

**CTL-04 - Cash flow / S-curve / payment-schedule forecast and financing cost**  
*Status:* Implemented and tested · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/cashflow.py::build`; `app/services/cashflow.py::cashflow_report`; `app/services/cashflow.py::propose_financing_indirects`; `app/estimators/param_kinds.py::_payment_terms`
- *Tests:* `unit/test_cashflow.py::test_cashflow_hand_worked_schedule` [yes] (balances -50, -144.25, -33.1925, 85.225575; interest 2.274425; bond 1.25); `unit/test_cashflow.py::test_supplier_credit_and_zero_financing_cases` [yes]; `unit/test_cashflow.py::test_service_report_proposals_and_estimate_unchanged` [yes]
- *Workflow / output:* Monthly contract cash flow from approved payment terms (advance, retention and release, certification/payment lags, supplier credit, performance bond, financing rate): peak funding, interest and bond cost; financing and bond cost proposed as Draft indirect items. Report `cashflow`.
- *Limitations / dependencies:* Value earned follows cost incurred (no margin loading), VAT excluded, interest on negative balances only, one bond type. All terms come from the contract/bank/supplier; none shipped. Depends on: DUR-05.
- *Acceptance test to mark complete:* Monthly cash flow from a cost-loaded programme and approved payment terms reconciles to the total price.

**CTL-05 - Forecasting and earned-value control during execution**  
*Status:* Implemented and tested · *needed from level:* 1 (applies at levels 1) · *kind:* engine
- *Code:* `app/estimators/evm.py::metrics`; `app/services/controls.py::evm_report`; `app/services/controls.py::record_progress`
- *Tests:* `unit/test_controls.py::test_evm_arithmetic_and_undefined_ratios` [yes]; `unit/test_controls.py::test_evm_report_hand_calculated` [yes] (PV 937.5, EV 750, AC 800 -> CPI 0.9375, SPI 0.8, EAC 2000); `unit/test_controls.py::test_progress_validation_and_frozen_version_baseline` [yes]
- *Workflow / output:* Earned value at a data date: planned value from the programme, earned value from human-entered task progress (with basis), actuals from recorded costs; CPI/SPI, EAC (two methods), ETC, VAC, TCPI; baseline from the live estimate or a frozen version's snapshot. Report `earned_value`.
- *Limitations / dependencies:* Progress percentages and actual costs are entered by people with their basis/source; linear planned value; cost not tied to a task is outside the metrics. Forecasts are analyses. Depends on: CTL-01, LIB-02.
- *Acceptance test to mark complete:* EAC/ETC from actuals and progress per control account.

**CTL-06 - Change orders / variation management after award (pricing, approval, audit, cumulative effect)**  
*Status:* Implemented and tested · *needed from level:* 1 (applies at levels 1) · *kind:* engine
- *Code:* `app/services/controls.py::create_variation`; `app/services/controls.py::price_variation`; `app/services/controls.py::submit_variation`; `app/services/controls.py::decide_variation`; `app/services/controls.py::contract_status`
- *Tests:* `unit/test_controls.py::test_variation_pricing_lifecycle_and_authority` [yes] (1,000 + 10% + 5% = 1,155; Commercial Approver only; self-approval blockable); `unit/test_controls.py::test_unpriced_resource_blocks_submission_never_priced_at_zero` [yes]; `unit/test_controls.py::test_contract_status_original_plus_approved_variations` [yes]
- *Workflow / output:* Variations priced from eligible approved rates with the approved contract markup, frozen at submission, decided by a Commercial Approver, with original/revised contract sum, pending exposure and time impact. Report `contract_status`.
- *Limitations / dependencies:* Resource-based pricing only (lump-sum quotations from subcontractors are not modelled as variation lines); claims, notices and entitlement assessment are outside scope. Contract baseline is entered from the signed contract. Depends on: CTL-02.
- *Acceptance test to mark complete:* A variation is priced from approved rates against the awarded baseline, approved, and cumulatively reported.

**CTL-07 - Cost roll-up by CBS level (division, sub-trade, cost code)**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/services/wbs.py::rollup_report`; `app/estimators/rollup.py::tree_rollup`
- *Tests:* `unit/test_wbs_rollup.py::test_rollup_report_ties_to_estimate_and_wbs_scoped_by_item` [yes] (parent includes child; ties out; unassigned shown)
- *Workflow / output:* Direct cost rolled up the full cost-code tree (division, sub-trade, code) and the WBS, with a WBS x division matrix; ties out to the estimate. Report `rollup`.
- *Limitations / dependencies:* Direct cost only; indirects and commercial adders are shown at project level, not allocated down the tree in this report. Depends on: LIB-01.
- *Acceptance test to mark complete:* Roll-up report by any level whose total equals the estimate.

### M. Commissioning, start-up, handover, close-out

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| CLO-01 | Testing, pre-commissioning, commissioning, start-up and performance tests | PA Partial | 3 |
| CLO-02 | Handover documentation, training, O&M manuals, warranties/defects-liability and spares | PA Partial | 4 |
| CLO-03 | Retention, bonds, advance payments, financing and final-account/close-out costing | IT Implemented and tested | 3 |

**CLO-01 - Testing, pre-commissioning, commissioning, start-up and performance tests**  
*Status:* Partial · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/mto.py::derive`; `app/services/mto.py::apply`; `app/services/mto.py::preview`; `app/services/provisions.py::reserve_proposals`; `data/taxonomy/cost_codes.csv`; `app/estimators/direct_cost.py::compute_direct_cost`
- *Tests:* `unit/test_mto.py::test_engine_derive_hand_calculated_missing_and_skipped` [yes] (driver x factor x (1+waste); missing slot yields nothing); `unit/test_mto.py::test_apply_pricing_gate_and_hand_calculated_cost` [yes] (derived lines are Pending Review until a person approves the pricing); `unit/test_provisions.py::test_reserve_proposals_are_draft_indirects_with_hand_calculated_amounts` [yes]; `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (cost codes exist)
- *Workflow / output:* Priceable via L.09, H.13, I.10, A.08 and commissioning labour definitions. Template and reserve-rule framework added.
- *Limitations / dependencies:* Pre-commissioning/commissioning/start-up use the `commissioning.system` template (per system) plus a governed reserve rule; performance-test costing and client commissioning procedures are not modelled. Structure only: the template names the driver and the resource slots, but NO factor, productivity or consumption value is shipped - each is entered from company records as a governed `mto_factor` and approved. The driver quantity is the estimator's own measured figure; the software never measures drawings. Earlier audit note: No system/loop-based commissioning model, vendor-representative, consumables/spares, or start-up support build-up; no commissioning sequencing. Depends on: EST-12.
- *Acceptance test to mark complete:* Commissioning cost is derived from a systems/loops list with approved hours, vendor-rep rates and consumables.

**CLO-02 - Handover documentation, training, O&M manuals, warranties/defects-liability and spares**  
*Status:* Partial · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/mto.py::derive`; `app/services/mto.py::apply`; `app/services/mto.py::preview`; `app/services/provisions.py::reserve_proposals`; `data/taxonomy/cost_codes.csv`
- *Tests:* `unit/test_mto.py::test_engine_derive_hand_calculated_missing_and_skipped` [yes] (driver x factor x (1+waste); missing slot yields nothing); `unit/test_mto.py::test_apply_pricing_gate_and_hand_calculated_cost` [yes] (derived lines are Pending Review until a person approves the pricing); `unit/test_provisions.py::test_reserve_proposals_are_draft_indirects_with_hand_calculated_amounts` [yes]; `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (cost codes exist)
- *Workflow / output:* Priceable as items under L.07/L.08/A.10. Template and reserve-rule framework added.
- *Limitations / dependencies:* Handover documentation/training use `handover.documentation` plus warranty/defects reserve rules (`reserve_rule`); O&M content, warranty claims and spares optimisation are not modelled. Structure only: the template names the driver and the resource slots, but NO factor, productivity or consumption value is shipped - each is entered from company records as a governed `mto_factor` and approved. The driver quantity is the estimator's own measured figure; the software never measures drawings. Earlier audit note: No warranty-reserve or spares-list logic.
- *Acceptance test to mark complete:* Warranty/DLP reserve derived from an approved method and period.

**CLO-03 - Retention, bonds, advance payments, financing and final-account/close-out costing**  
*Status:* Implemented and tested · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/cashflow.py::build`; `app/services/cashflow.py::propose_financing_indirects`; `app/services/controls.py::contract_status`
- *Tests:* `unit/test_cashflow.py::test_cashflow_hand_worked_schedule` [yes]; `unit/test_controls.py::test_contract_status_original_plus_approved_variations` [yes]
- *Workflow / output:* Retention (with release at completion and after the defects period), advance payment and recovery, performance-bond fee, financing interest and the revised contract sum after approved variations.
- *Limitations / dependencies:* Final-account statements, certificates and retention release correspondence are not generated. Advance bonds and parent-company guarantees are not modelled separately. Depends on: CTL-04.
- *Acceptance test to mark complete:* Bond/retention/financing costs derive from approved terms and the cash-flow forecast.

### N. Saudi-specific requirements and configurable client compliance profiles

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| SAU-01 | Saudi basics: SAR default, region applicability by code (no multipliers), Arabic BOQ headers/descriptions, Arabic RFQ draft | IT Implemented and tested | 5 |
| SAU-02 | VAT 15% as a dated, verified category (seeded Pending Review) with verification evidence | IT Implemented and tested | 5 |
| SAU-03 | Saudi labour cost rules: Saudization/Nitaqat, expatriate levy, iqama and visa, GOSI, end-of-service, Ramadan and overtime working-hours rules | IT Implemented and tested | 2 |
| SAU-04 | Local content / in-kingdom value (e.g. IKTVA-type evaluation), national procurement preferences | PA Partial | 1 |
| SAU-05 | Saudi Building Code, authority fees/permits, municipal and utility approvals | PA Partial | 4 |
| SAU-06 | Configurable client compliance profiles (mandatory forms, templates, code lists, rules, estimate classification, approvals) per client | IT Implemented and tested | 1 |
| SAU-07 | Saudi Aramco-type project requirements (controlled standards, forms, estimating procedures, vendor lists) | MI Missing | 1 |

**SAU-01 - Saudi basics: SAR default, region applicability by code (no multipliers), Arabic BOQ headers/descriptions, Arabic RFQ draft**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `data/regions/regions.csv`; `app/imports/boq.py::detect_header`; `app/procurement/rfq.py::create_rfq`
- *Tests:* `imports/test_boq_import.py::test_arabic_headers` [yes]; `procurement/test_procurement.py::test_arabic_rfq_template_and_unknown_language` [yes]; `unit/test_schedule_resolution.py::test_resolution_outcomes` [partly] (region applicability)
- *Workflow / output:* Region codes in rates/projects.
- *Limitations / dependencies:* 6 regions; UI is English only (no RTL); Arabic RFQ is a machine draft; no Hijri calendar.
- *Acceptance test to mark complete:* Native review of Arabic outputs; region list matches the client's.

**SAU-02 - VAT 15% as a dated, verified category (seeded Pending Review) with verification evidence**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/services/refdata.py::seed_tax_categories`; `app/services/commercial.py::approve_tax_category`
- *Tests:* `unit/test_library_data.py::test_tax_and_fx_seeds_are_pending_until_a_human_verifies` [yes]
- *Workflow / output:* Commercial tab: tax categories.
- *Limitations / dependencies:* Not yet verified/approved by a human against current ZATCA text; no e-invoicing.
- *Acceptance test to mark complete:* Commercial Approver approves with evidence; estimate resolves tax.

**SAU-03 - Saudi labour cost rules: Saudization/Nitaqat, expatriate levy, iqama and visa, GOSI, end-of-service, Ramadan and overtime working-hours rules**  
*Status:* Implemented and tested · *needed from level:* 2 (applies at levels 2, 1) · *kind:* engine
- *Code:* `app/estimators/labour_costs.py::statutory_monthly`; `app/estimators/labour_costs.py::blend`; `app/estimators/labour_costs.py::national_target_check`; `app/services/labour.py::propose_labour_rate`; `app/services/labour.py::workforce_report`
- *Tests:* `unit/test_landed_labour_exposure.py::test_statutory_monthly_and_workforce_blend_hand_calculated` [yes] (10% + 800 levy + 1200/12 visa + 5% + 2400/12 = 1,200/500); `unit/test_landed_labour_exposure.py::test_labour_buildup_with_user_rules_and_workforce_check` [yes]
- *Workflow / output:* Labour build-up with governed statutory/mobilisation rules per nationality group, workforce-mix blended cost and a check of the national-workforce share against an approved target (programme/contract), proposed as a Draft/Pending labour rate with the rule versions recorded.
- *Limitations / dependencies:* The framework contains no wage, levy, insurance or accrual value and no nationalisation-programme band definitions: they are entered from the applicable regulation and approved. Compliance with any programme is not asserted - only the arithmetic against the target the user supplied. Depends on: RTE-02.
- *Acceptance test to mark complete:* A labour rate is built from approved statutory components and a Ramadan/overtime pattern, reproducing the company's payroll costing.

**SAU-04 - Local content / in-kingdom value (e.g. IKTVA-type evaluation), national procurement preferences**  
*Status:* Partial · *needed from level:* 1 (applies at levels 1) · *kind:* engine
- *Code:* `app/estimators/bid_eval.py::evaluate`; `app/services/bids.py::evaluation_report`; `app/estimators/param_kinds.py::_eval_criteria`
- *Tests:* `unit/test_bids_scope.py::test_evaluation_hand_calculated_with_gate_minimum_and_incomplete` [yes]; `unit/test_bids_scope.py::test_weights_must_total_100_and_passfail_has_no_weight` [yes]
- *Workflow / output:* A local-content / in-country-value criterion can be one of the weighted, evidence-scored criteria of a bid evaluation (weight, minimum score or pass/fail gate) as set by the tender's evaluation plan.
- *Limitations / dependencies:* No owner's local-content method (e.g. an in-kingdom value formula, certificates, supplier lists) is implemented or supplied; the evaluator enters the score with evidence. No national-preference price adjustments are computed. Depends on: SAU-06.
- *Acceptance test to mark complete:* Scoring inputs captured per bid package and the client's published scoring method reproduced from controlled documents.

**SAU-05 - Saudi Building Code, authority fees/permits, municipal and utility approvals**  
*Status:* Partial · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `data/taxonomy/cost_codes.csv`
- *Tests:* `unit/test_library_data.py::test_every_required_trade_division_and_subtrade_is_present` [partly] (L.02 'Authority fees and permits' exists)
- *Workflow / output:* Fees/permits as priced items under L.02.
- *Limitations / dependencies:* SBC not accessible to the build environment (documented); no code-driven scope or cost checks.
- *Acceptance test to mark complete:* Permit/fee schedule per authority maintained as approved data.

**SAU-06 - Configurable client compliance profiles (mandatory forms, templates, code lists, rules, estimate classification, approvals) per client**  
*Status:* Implemented and tested · *needed from level:* 1 (applies at levels 1) · *kind:* engine
- *Code:* `app/services/profiles.py::create_profile`; `app/services/profiles.py::approve_profile`; `app/services/profiles.py::compliance_report`; `app/estimators/profile_checks.py::evaluate`; `app/reconciliation/ext_rules.py::collect_extended`
- *Tests:* `unit/test_profiles_boe.py::test_check_evaluation_and_unknown_facts_are_not_assessable` [yes]; `unit/test_profiles_boe.py::test_profile_validation_and_authority` [yes]; `unit/test_profiles_boe.py::test_compliance_matrix_never_claims_beyond_loaded_requirements` [yes]; `reconciliation/test_extended_rules.py::test_extended_findings_raised_with_configured_severity` [yes]
- *Workflow / output:* Client/owner profile framework: a versioned list of requirements loaded from the owner's controlled documents, each with a source reference and either an automatic check on measured facts or a human attestation with evidence; approved by a Commercial Approver; mandatory unmet items raise reconciliation findings; the statement is scoped to the loaded requirements. CLI `profile`, report `compliance`.
- *Limitations / dependencies:* The software ships NO profile content. Templates, forms, code lists and bilingual deliverables of a client (OUT-05) are not generated. Only the fact checks in `profile_checks.FACT_HELP` can be automated; everything else is an attestation. Depends on: BOE-04, LIB-02.
- *Acceptance test to mark complete:* Selecting a profile applies its CBS/WBS cross-walk, mandatory checks and class definitions; the profile records the controlled document/revision it implements (template generation not built).

**SAU-07 - Saudi Aramco-type project requirements (controlled standards, forms, estimating procedures, vendor lists)**  
*Status:* Missing · *needed from level:* 1 (applies at levels 1) · *kind:* engine
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
| GOV-05 | Full replay of a frozen estimate (indirects, commercial, tax, schedule) from its snapshot | IT Implemented and tested | 3 |
| GOV-06 | Reconciliation: 37 configurable rules, exceptions, final gate re-run at approval and export | IT Implemented and tested | 5 |
| GOV-07 | Gated commercial exports: SUBMISSION READY only after approved version + offer + tender-export approval + fresh reconciliation; otherwise PRELIMINARY watermark | IT Implemented and tested | 5 |
| GOV-08 | No autonomous tender submission: no e-mail/FTP/portal automation; outputs are files for a human to send | IT Implemented and tested | 5 |
| GOV-09 | Backup/restore/validation and project package export (workspace, imports, DB) | IT Implemented and tested | 4 |
| GOV-10 | Numbered project workspaces, project CLAUDE.md, isolation between projects, copy-only legacy migration | IT Implemented and tested | 4 |
| GOV-11 | Self-approval segregation (configurable) | IT Implemented and tested | 4 |
| GOV-12 | Multi-user operation, concurrency, security hardening (TLS, CSRF tokens, lockout, MFA/SSO) | PA Partial | 2 |

**GOV-01 - Server-side role-based approvals for every commercially significant decision**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/approvals/policy.py::POLICY`; `app/approvals/engine.py::authorize`
- *Tests:* `approvals/test_approval_rules.py::test_policy_role_matrix_has_no_ai_and_commercial_gates` [yes]; `integration/test_api_ui.py::test_server_side_permissions_on_the_api` [yes]; `integration/test_api_ui.py::test_ui_forms_enforce_permissions_server_side` [yes]
- *Workflow / output:* Approvals page; approvals table.
- *Limitations / dependencies:* Role matrix defined in code; no per-project or per-value delegation of authority beyond the supplier-selection threshold.
- *Acceptance test to mark complete:* Every approve/reject path refuses an unauthorised role.

**GOV-02 - AI/automation cannot approve; AI output is review-pending; automated source code cannot reach approve/publish**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/ai/service.py::_store`; `app/approvals/engine.py::authorize`
- *Tests:* `approvals/test_approval_rules.py::test_ai_cannot_approve_anything` [yes]; `approvals/test_approval_rules.py::test_ai_package_cannot_reach_approval_or_mutation_code` [yes]; `approvals/test_source_boundary.py::test_automated_source_code_never_references_approval_or_publication_functions` [yes]
- *Workflow / output:* ai_suggestions Pending Review.
- *Limitations / dependencies:* Structural (AST) and behavioural tests cover app/ai and the source/refresh modules; a new module outside those packages would need its own review and boundary test.
- *Acceptance test to mark complete:* No code path from automation to an approved state.

**GOV-03 - Hash-chained audit log; backup validation re-verifies it (tamper-evident, not tamper-proof)**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/services/audit.py::log`; `app/services/audit.py::verify_chain`
- *Tests:* `approvals/test_approval_rules.py::test_audit_chain_detects_tampering` [yes]; `integration/test_backup_datasets_cli.py::test_backup_with_tampered_audit_chain_flagged` [yes]
- *Workflow / output:* `audit-verify`; Settings page.
- *Limitations / dependencies:* Someone with DB write access can rebuild the chain; no external anchoring or signing.
- *Acceptance test to mark complete:* Chain verification passes after restore; any edit is detected.

**GOV-04 - Estimate input snapshots: verify pinned rate rows unchanged, list newer approved rates, replay direct cost from the snapshot**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/services/snapshots.py::store_snapshot`; `app/services/snapshots.py::verify_snapshot`; `app/services/snapshots.py::replay_direct_cost`
- *Tests:* `workspaces/test_workspaces.py::test_snapshot_keeps_frozen_estimate_reproducible_after_a_new_rate_is_approved` [yes]; `sources/test_rate_pipeline.py::test_publication_creates_new_pending_version_keeps_old_and_does_not_mutate_frozen_estimate` [yes]
- *Workflow / output:* `project verify-snapshot`; Workspace tab.
- *Limitations / dependencies:* Snapshots exist only for versions frozen after migration 0007.
- *Acceptance test to mark complete:* Approve a new global rate; replay of an old version equals its frozen direct cost.

**GOV-05 - Full replay of a frozen estimate (indirects, commercial, tax, schedule) from its snapshot**  
*Status:* Implemented and tested · *needed from level:* 3 (applies at levels 3, 2, 1) · *kind:* engine
- *Code:* `app/estimators/estimate.py::compute_estimate_from`; `app/estimators/estimate.py::EstimateExtras`; `app/services/snapshots.py::replay_estimate`; `app/services/snapshots.py::extras_from_snapshot`
- *Tests:* `unit/test_full_replay.py::test_replay_reproduces_frozen_totals_after_everything_changes` [yes] (rate, factor, indirect, tax changed afterwards; full replay still equals the frozen totals); `unit/test_full_replay.py::test_legacy_snapshot_without_extras_still_replays` [yes]; `unit/test_full_replay.py::test_replay_detects_a_tampered_snapshot_and_changed_engine_inputs` [yes]
- *Workflow / output:* `replay_estimate(version)` recomputes direct cost, indirects, commercial policy, pricing schedule and tax from the stored snapshot alone (pure `compute_estimate_from`) and compares state, fingerprint and every total; `project verify-snapshot` shows it.
- *Limitations / dependencies:* Versions frozen before migration 0007 have no snapshot. Replays use the current engine code: an engine change that alters results shows as a difference (by design - that is what replay detects).
- *Acceptance test to mark complete:* `replay_estimate` equals every frozen total.

**GOV-06 - Reconciliation: 37 configurable rules, exceptions, final gate re-run at approval and export**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/reconciliation/engine.py::run_reconciliation`; `app/reconciliation/engine.py::final_gate`; `config/reconciliation_rules.json`
- *Tests:* `reconciliation/test_recon.py::test_clean_project_has_no_blocking_findings` [yes]; `reconciliation/test_recon.py::test_exceptions_policy_and_roles` [yes]; `reconciliation/test_recon.py::test_high_exception_needs_commercial_role_and_configurable_rules` [yes]
- *Workflow / output:* Reconciliation tab; reconciliation_report xlsx.
- *Limitations / dependencies:* Rule coverage is for the generic estimate; no industrial/EPC rules (e.g. MTO completeness, weld/NDT counts).
- *Acceptance test to mark complete:* Each rule has a positive and negative test; client rules can be added by configuration.

**GOV-07 - Gated commercial exports: SUBMISSION READY only after approved version + offer + tender-export approval + fresh reconciliation; otherwise PRELIMINARY watermark**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/services/estimates.py::export_submission`; `app/services/estimates.py::approve_tender_export`; `app/exports/documents.py::client_pricing_schedule`
- *Tests:* `integration/test_final_flow.py::test_final_flow_and_gates` [yes]; `integration/test_final_flow.py::test_critical_blocks_final` [yes]; `integration/test_full_workflow.py::test_complete_workflow_to_gated_submission_export` [yes]
- *Workflow / output:* Reports tab; pricing schedule xlsx, offer letter docx, estimate report docx.
- *Limitations / dependencies:* Outputs are the application's own formats, not client-mandated forms (SAU-06).
- *Acceptance test to mark complete:* Export refused when any gate fails; produced when all pass.

**GOV-08 - No autonomous tender submission: no e-mail/FTP/portal automation; outputs are files for a human to send**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/exports/documents.py::client_pricing_schedule`; `app/sources/base.py::HttpFetcher`
- *Tests:* `workspaces/test_audit_regressions.py::test_application_has_no_autonomous_submission_channel` [yes] (added by this audit (static scan of imports and the fetcher))
- *Workflow / output:* Files in '8. Commercial Submission' / '10. Exports & Archive'.
- *Limitations / dependencies:* A static scan cannot prove a user script will not submit; it proves the application has no channel.
- *Acceptance test to mark complete:* Static scan stays green; any new outbound channel requires an explicit approved design.

**GOV-09 - Backup/restore/validation and project package export (workspace, imports, DB)**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/services/backup.py::create_backup`; `app/services/backup.py::restore_backup`; `app/services/backup.py::export_project_package`
- *Tests:* `integration/test_backup_datasets_cli.py::test_backup_validate_restore_cycle` [yes]; `integration/test_backup_datasets_cli.py::test_corrupt_backup_is_rejected_and_nothing_changes` [yes]; `integration/test_backup_datasets_cli.py::test_project_package_and_archive` [yes]
- *Workflow / output:* `backup`, `validate-backup`, `restore --yes`, `export-project`.
- *Limitations / dependencies:* Not encrypted; local files only.
- *Acceptance test to mark complete:* Restore on a clean machine reproduces estimates and audit chain.

**GOV-10 - Numbered project workspaces, project CLAUDE.md, isolation between projects, copy-only legacy migration**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/services/workspaces.py::ensure_workspace`; `app/services/workspace_migration.py::migrate`
- *Tests:* `workspaces/test_workspaces.py::test_new_project_creates_complete_workspace` [yes]; `workspaces/test_workspaces.py::test_project_isolation_files_and_quotes_stay_in_their_own_workspace` [yes]; `workspaces/test_cli_and_migration.py::test_workspace_migration_dry_run_then_copy_without_destroying_legacy_files` [yes]
- *Workflow / output:* `project create/refresh/index`; Workspace tab.
- *Limitations / dependencies:* No per-workspace ACL; single local user model.
- *Acceptance test to mark complete:* Two projects never share files or quotations.

**GOV-11 - Self-approval segregation (configurable)**  
*Status:* Implemented and tested · *needed from level:* 4 (applies at levels 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/approvals/engine.py::authorize`
- *Tests:* `approvals/test_approval_rules.py::test_self_approval_can_be_disabled` [yes]
- *Workflow / output:* KSA_ALLOW_SELF_APPROVAL=false.
- *Limitations / dependencies:* Off by default (single-user MVP default).
- *Acceptance test to mark complete:* With the setting off, no user can approve a record they created (admin exempt).

**GOV-12 - Multi-user operation, concurrency, security hardening (TLS, CSRF tokens, lockout, MFA/SSO)**  
*Status:* Partial · *needed from level:* 2 (applies at levels 2, 1) · *kind:* engine
- *Code:* `app/security.py::Hardening`; `app/services/auth.py::authenticate`; `app/services/auth.py::unlock_user`; `app/main.py::SerializeRequests`; `app/cli.py::cmd_run`
- *Tests:* `integration/test_security_hardening.py::test_cookie_authenticated_write_needs_same_origin` [yes]; `integration/test_security_hardening.py::test_security_headers_present_and_pages_not_cached` [yes]; `integration/test_security_hardening.py::test_lockout_after_repeated_failures_even_for_unknown_names_and_admin_unlock` [yes]; `integration/test_security_hardening.py::test_cli_refuses_open_network_without_tls` [yes]; `integration/test_api_ui.py::test_authentication_required_and_bad_tokens_rejected` [yes]
- *Workflow / output:* Same-origin check for cookie-authenticated writes, CSP and other security headers, no-store caching, Secure cookies and HSTS over TLS, sign-in lockout with administrator unlock, TLS flags on `run` and refusal to listen on a non-loopback address without TLS.
- *Limitations / dependencies:* Not provided: MFA/SSO, per-folder ACLs, encrypted backups, rotation of the signing key, true multi-user concurrency (requests are serialised), rate limiting by IP, a third-party penetration test. Not for internet exposure without a reverse proxy and a security review.
- *Acceptance test to mark complete:* Security review passed and load-tested with concurrent estimators.

### P. Excel and document outputs

| ID | Capability | Status | Needed from level |
|---|---|---|---|
| OUT-01 | 27-sheet master workbook + 10 standalone workbooks + 2 Word templates, spec-driven, recalculated and checked with LibreOffice | IT Implemented and tested | 5 |
| OUT-02 | Round-trip import: edits become drafts/proposals; status/approval columns and forged values ignored; formula tampering detected | IT Implemented and tested | 5 |
| OUT-03 | Microsoft Excel compatibility (recalculation on open, MINIFS, protection, validations) | IU Implemented but unverified | 5 |
| OUT-04 | Client pricing schedule, letter of offer and estimate report with exact reconciliation, hash-matched offer and visible exceptions | IT Implemented and tested | 5 |
| OUT-05 | Client-specific tender forms/schedules of rates and bilingual deliverables | PA Partial | 2 |

**OUT-01 - 27-sheet master workbook + 10 standalone workbooks + 2 Word templates, spec-driven, recalculated and checked with LibreOffice**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/excel/master.py::build_master`; `app/excel/templates.py::generate_all`; `app/excel/recalc.py::verify_workbook`
- *Tests:* `excel/test_workbooks.py::test_required_sheets_present_and_ordered` [yes]; `excel/test_workbooks.py::test_libreoffice_recalculation_has_no_errors_or_mismatches` [yes] (LibreOffice only); `excel/test_workbooks.py::test_populated_workbook_matches_engine_and_ids` [yes]
- *Workflow / output:* `export-workbook`, `verify-workbook`, Reports tab download.
- *Limitations / dependencies:* Master export of a 20,000-item project took ~62 s (SCO-09).
- *Acceptance test to mark complete:* Round-trip and recalculation clean on a pilot project in LibreOffice and Excel.

**OUT-02 - Round-trip import: edits become drafts/proposals; status/approval columns and forged values ignored; formula tampering detected**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/excel/roundtrip.py::import_master`; `app/excel/roundtrip.py::validate_structure`
- *Tests:* `excel/test_workbooks.py::test_roundtrip_edits_become_drafts_and_approval_columns_are_ignored` [yes]; `excel/test_workbooks.py::test_structure_validation_detects_tampering` [yes]; `excel/test_workbooks.py::test_round_trip_into_a_fresh_project_reproduces_the_boq` [yes]
- *Workflow / output:* Reports tab re-import.
- *Limitations / dependencies:* Covers the 27 master sheets documented in EXCEL_WORKBOOK_GUIDE; unsupported sheets are ignored, not imported. Imports of very large workbooks are untested.
- *Acceptance test to mark complete:* Edited workbook import creates only drafts.

**OUT-03 - Microsoft Excel compatibility (recalculation on open, MINIFS, protection, validations)**  
*Status:* Implemented but unverified · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/excel/builder.py::write_sheet`
- *Tests:* `excel/test_workbooks.py::test_libreoffice_recalculation_has_no_errors_or_mismatches` [partly] (LibreOffice is not Excel)
- *Workflow / output:* Workbooks open in LibreOffice; fullCalcOnLoad set.
- *Limitations / dependencies:* Microsoft Excel has never been available to this project.
- *Acceptance test to mark complete:* A person opens each template and the populated master in Microsoft Excel 365 and 2019 and confirms recalculation, validations and protection.

**OUT-04 - Client pricing schedule, letter of offer and estimate report with exact reconciliation, hash-matched offer and visible exceptions**  
*Status:* Implemented and tested · *needed from level:* 5 (applies at levels 5, 4, 3, 2, 1) · *kind:* engine
- *Code:* `app/exports/documents.py::client_pricing_schedule`; `app/exports/documents.py::estimate_report_docx`; `app/services/offers.py::generate_offer`; `app/estimators/pricing_schedule.py::build_schedule`
- *Tests:* `unit/test_schedule_resolution.py::test_schedule_spread_reconciles_exactly_to_net_price` [yes]; `reconciliation/test_recon.py::test_offer_and_pricing_schedule_discrepancies` [yes]
- *Workflow / output:* Reports tab.
- *Limitations / dependencies:* Application formats only; offer text is a draft for legal review.
- *Acceptance test to mark complete:* Schedule total equals net price to the halala (or the bounded rounding variance is reported).

**OUT-05 - Client-specific tender forms/schedules of rates and bilingual deliverables**  
*Status:* Partial · *needed from level:* 2 (applies at levels 2, 1) · *kind:* engine
- *Code:* `app/exports/client_form.py::fill`; `app/services/estimates.py::export_client_form`; `app/services/estimates.py::require_export_gate`; `app/api/actions_ext.py::export_client_form`
- *Tests:* `integration/test_full_workflow.py::test_complete_workflow_to_gated_submission_export` [yes] (client form filled by item code; formulas untouched; gated like the submission package; preliminary copy labelled)
- *Workflow / output:* A CLIENT-SUPPLIED schedule-of-rates / tender-form workbook is filled from the pricing schedule using a user-written JSON mapping (item-code match, quantity/unit/rate/amount/description columns, total cells, banner cell). Submission-ready only through the same tender-export approval gate; otherwise a PRELIMINARY copy. Unmatched rows on either side are reported.
- *Limitations / dependencies:* The software ships no client form or mapping - the user supplies both. No bilingual (Arabic/English) deliverable generation, no PDF, no multi-sheet forms with merged-row structures beyond cell mapping. Forms are not validated against the client's rules. Depends on: SAU-06.
- *Acceptance test to mark complete:* A real client tender form is filled by mapping alone and the sum of the filled amounts equals the offer total (only if every client row has a schedule item).

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
