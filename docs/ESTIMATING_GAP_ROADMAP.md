# Estimating gap roadmap (from the five-level capability audit)

Source: [ESTIMATING_CAPABILITY_MATRIX.md](ESTIMATING_CAPABILITY_MATRIX.md) (record ids such as `PRC-01` refer to it). Every record that is not *Implemented and tested* is covered by exactly one work package below; `tests/unit/test_capability_matrix.py` fails if one is missing.
This roadmap orders work by **dependency and risk**: first data and foundations that block everything, then structures that several later modules need, then the industrial/EPC modules, then client-specific profiles. It does not schedule calendar dates.
**Standing constraints for every work package:** no invented prices/rates/productivities/standards; no automatic approval; no silent overwrite of approved data or frozen estimates; no automated quantity takeoff; no autonomous tender submission; no claim of Saudi Aramco (or any client) compliance without that owner's controlled documents loaded as a profile and traced.

## 0. How the levels become "supported"
A level is *Supported* when every engine capability required at that level is *Implemented and tested* (matrix roll-up) **and** its data prerequisites are met for the project at hand. Verdicts after iteration 4 (computed by the matrix roll-up): Levels 5, 4, 3 and 2 *Conditionally supported* (every required engine capability exists; the Partial ones are listed with their limits); Level 1 *Not supported* (SAU-07, owner-controlled requirements, is Missing by design - it needs the owner's documents). The first audit (commit `907fce6`) had Levels 5-4 conditional and 3-1 not supported. Exit criteria:
| Level | Work packages that must be complete (software) | Data/human prerequisites |
|---|---|---|
| 5 | WP-00b (Excel check), WP-17 (DSC-01/02/PRE-01 acceptance with a pilot) | LIB-07, LIB-08 for the pilot BOQ |
| 4 | Level 5 + WP-17 (all DSC acceptance pilots), WP-16 (PRO-06/07), WP-02 (CTL-07 roll-up), WP-11 (RTE-05 live), WP-18 (SCO-11, SAU-05, LIB-05) | rate library for all pilot trades |
| 3 | Level 4 + WP-01, 02, 03, 05, 07, 08, 09, 10 | approved FX, customs/duty and escalation inputs |
| 2 | Level 3 + WP-04, 06, 12, 13, 14, 15 | industrial catalogue, factor tables with sources, labour statutory rules (SAU-03) |
| 1 | Level 2 + WP-19, 20, 21 | owner's controlled documents (never assumed) |

## 0a. Status after iteration 4 (2026-10-13)
Each row says what was **built and tested** and what is **still open**. "Open" is almost always data, a document the user must supply, a real network, or Microsoft Excel - not missing code.
| WP | Status | Built and tested (matrix records) | Still open |
|---|---|---|---|
| WP-00a | **Open (data)** | pipeline exists (`rates import`, RFQ, candidates) | real rates and factors (LIB-07, LIB-08) - only the user can supply them |
| WP-00b | **Open** | LibreOffice verified (217 formulas, 0 errors/mismatches) | open the workbooks in Microsoft Excel (OUT-03) |
| WP-01 | **Done** | industrial units, admin unit management, definitions pack (SCO-04, LIB-04 partly) | - |
| WP-02 | **Done** | WBS, cross-walk, roll-ups (LIB-02, CTL-07) | client code lists are loaded by the user |
| WP-03 | **Done** | FS/SS/FF/SF, lags, float, constraints, calendar (DUR-02, DUR-05) | schedule-file import, Gantt, levelling |
| WP-04 | **Done** | man-hours and loading (EST-10, DUR-04) | - |
| WP-05 | **Partial** | productivity factors, plant minimum-hire/standby, method alternatives (EST-12, EST-05, EST-11 partial) | factor values (user data); no equipment-selection logic |
| WP-06 | **Partial** | piping/tank templates (PRC-01, PRC-06 partial) | pipe-class and weld logic; factors |
| WP-07 | **Done (framework)** | Basis of Estimate, classification from an approved scheme (BOE-03, BOE-04) | the scheme and ranges are the company's (BOE-05 partial) |
| WP-08 | **Done** | landed cost, logistics, currency exposure, statutory labour (TAX-02, TAX-04, CUR-03, SAU-03) | withholding tax / zakat (TAX-03 partial) |
| WP-09 | **Done** | quantified risk, Monte Carlo, escalation (RSK-03/04/05) | correlation between risks |
| WP-10 | **Done** | cash flow, retention, bonds, financing (CTL-04, CLO-03) | - |
| WP-11 | **Open** | provider tested with mocks | live run on an unrestricted network (RTE-05) |
| WP-12 | **Partial** | pack + templates for E&I, steel, coatings, insulation, scaffolding, lifting (PRC-02/04/05/07/08/09/10 partial) | discipline assemblies need the user's factors |
| WP-13 | **Partial** | instrument-loop and specialist-service templates (PRC-03, PRC-11) | factors |
| WP-14 | **Partial** | temporary-facility, commissioning and handover templates + reserve rules (PRC-14, IND-02, CLO-01, CLO-02) | camp sizing, performance tests |
| WP-15 | **Done** | statutory labour model, full replay (SAU-03, GOV-05) | - |
| WP-16 | **Done** | bid evaluation, long-lead, interface matrix (PRO-06, PRO-07) | supplier performance history |
| WP-17 | **Open (data)** | - | pilot BOQs per discipline (DSC-01..11, PRE-01) |
| WP-18 | **Open** | - | live validation of requirements extraction (SCO-11), SBC/authority fees (SAU-05), OCR/CAD |
| WP-19 | **Partial** | engineering and overhead models, shutdown and modularisation templates (ENG-01, ENG-02; PRC-12, PRC-13 partial) | shutdown logic |
| WP-20 | **Done** | variations, contract status, earned value, benchmarks (CTL-03/05/06) | - |
| WP-21 | **Partial** | client-profile framework, client-form export (SAU-06; OUT-05, SAU-04 partial) | **SAU-07 stays Missing**: no owner's document is loaded - no Aramco compliance is claimed |
| WP-22 | **Partial** | estimate cache, same-origin check, headers, lockout, TLS flags; workbook export 2.3x faster (SCO-09, GOV-12 partial) | MFA/SSO, pagination, 50k-item run, ACLs |

## 1. Priority order and work packages
Priority: **P0** blocks real use or blocks many other packages · **P1** high value, unblocks a level · **P2** needed for Level 2 · **P3** Level 1 / specialised.

| WP | Priority | Records covered | Work | Depends on | Acceptance (summary; full text in the matrix records) | Validation | Human approval needed | External needs |
|---|---|---|---|---|---|---|---|---|
| WP-00a | **P0** | LIB-07, LIB-08 | **Load evidence-backed data**: rates via RFQ/quotations/permitted price lists (`rates import`), productivity/consumption factors from company actuals or supplier data, with Source Register entries. Not a coding task | none | pilot BOQ resources 100 % approved, in date, evidence-linked; assemblies have sourced factors | `coverage`, completeness report, productivity variance | Yes — every rate/factor | Real quotations/price lists |
| WP-00b | **P0** | OUT-03 | Open master + templates in Microsoft Excel 365/2019; record result | none | recalc/validation/protection confirmed | dated entry in DEVELOPMENT_AUDIT | Yes (user) | Microsoft Excel |
| WP-01 | **P0** | SCO-04 | **Unit & dimension management**: admin action to add units with dimension/conversion (audited, never silently overriding), new dimensions for inch-dia, joint, spool, loop, power (MVA), flow, pressure, temperature; seed industrial units | none | piping/E&I BOQ imports with 0 unknown units; conversions only where exact | unit tests; import test with an industrial BOQ | Yes (admin) | none |
| WP-02 | **P0** | LIB-02, CTL-07 | **WBS + CBS cross-walk + roll-ups**: WBS elements (area/unit/system), item-to-WBS mapping, client code cross-walk table, roll-up reports by CBS/WBS/level reconciling to totals | none (enables WP-04/05/08/10/20) | totals identical at every level | roll-up property tests; workbook sheet | Yes (mapping approvals) | client code list (user supplies) |
| WP-03 | **P0** | DUR-02, DUR-05 | **Programme model v2**: relationship types, lags, constraints, float, calendars (incl. Ramadan/holidays as approved data), phases/areas, cost-to-activity assignment, import from a schedule export file | WP-02 | CPM equals reference tool on a 200-task network | golden-file tests vs exported schedules | Yes (duration approval stays human) | sample schedule files |
| WP-04 | **P1** | EST-10, DUR-04 | **Man-hour aggregation and resource loading**: totals by craft/trade/area/period, histograms/peaks from the cost-loaded programme | WP-02, WP-03 | monthly manpower reconciles to total hours | reconciliation tests; report | No | none |
| WP-05 | **P1** | EST-12, EST-11, EST-05 | **Methodology & productivity factors**: approved factor tables (height, congestion, climate, shift, remote) applied to tagged items with basis text; method options selecting assembly sets/durations; plant standby and minimum-hire calculation | WP-02, WP-03 | adjusted hours visible in basis string and impact analysis; method alternatives comparable | hand-calculation tests; what-if tests | Yes (factors are approved assumptions) | factor evidence from the user |
| WP-06 | P2 | PRC-01, PRC-06 | **Piping and tank estimating**: MTO import (spool, size, schedule, material, joints), inch-dia/weld counts, shop vs field, NDT, hydrotest/flush; plate/seam based tank erection | WP-01, WP-05, WP-12 | 500-spool package reproduces by hand from approved factors | golden fixtures (synthetic) | Yes | pipe class/factor evidence |
| WP-07 | **P1** | BOE-03, BOE-04, BOE-05 | **Classification profiles and Basis of Estimate**: `config/classification_profiles/*.json` (AACE and/or client; reference document + revision mandatory; accuracy ranges user-supplied), per-class deliverable/maturity checks, BoE document with every required section populated or flagged missing; blocks approval on unmet mandatory criteria | WP-02 | profile selection changes checks and BoE; nothing defaulted | config-validation tests; docx content tests | Yes | licensed AACE text or owner documents |
| WP-08 | **P1** | TAX-02, TAX-03, TAX-04, CUR-03 | **Landed cost, duties, logistics and currency exposure**: Incoterm/FOB→delivered build-up with approved duty/clearance/freight inputs and dated FX; exposure by currency and sensitivity; statutory tax treatments as approved assumptions | CUR-01/02 (done) | imported item priced step by step; exposure report reconciles | hand tests | Yes (duty/tax inputs approved) | tariff/freight evidence |
| WP-09 | **P1** | RSK-03, RSK-04, RSK-05 | **Risk, escalation and uncertainty**: numeric risk register with distributions, expected value, seeded Monte Carlo (P50/P80) feeding contingency at a chosen confidence; time-phased/index-linked escalation using stored CCI observations and the programme | WP-03 | seeded results reproduce; escalation per element and period traceable | deterministic seeded tests | Yes (risk inputs, confidence level) | none |
| WP-10 | P1 | CTL-04, CLO-03 | **Cash flow and financing**: cost-loaded payment forecast, retention/bonds/advance, financing cost from approved terms | WP-03, WP-09 | monthly cash flow reconciles to price | tests | Yes | payment terms |
| WP-11 | P1 | RTE-05 | **Live source verification**: run `sources refresh` on an unrestricted network; confirm robots/pagination; one permitted real product page end-to-end | none | CCI months imported with manifest; one real candidate with correct evidence | dated access-log entries | Yes | Internet |
| WP-12 | P2 | LIB-04, PRC-02, PRC-04, PRC-05, PRC-07, PRC-08, PRC-09, PRC-10 | **Industrial catalogue and discipline assemblies** (definitions only, no prices) for process equipment, E&I, steel, coatings, insulation, scaffolding, heavy lifts, specialist services; weight-/area-/volume-based assembly patterns | WP-01 | coverage report by discipline; assemblies draft until factors supplied | catalogue tests | Yes | discipline lead review |
| WP-13 | P2 | PRC-03, PRC-11 | **Instrumentation & specialist industrial services** (loop/I-O driven estimating, FAT/SAT, NDT, cathodic protection) | WP-01, WP-12 | 400-loop package reproduces | fixtures | Yes | factor evidence |
| WP-14 | P2 | PRC-14, IND-02, CLO-01, CLO-02 | **Remote-site, temporary facilities and commissioning models**: manpower-driven camp/facility sizing, rotation, logistics; systems/loop-based pre-commissioning, commissioning, start-up, vendor reps, spares, warranty/DLP | WP-04, WP-08 | derived from manpower and systems lists | tests | Yes | unit costs |
| WP-15 | P2 | SAU-03, GOV-05 | **Saudi labour statutory model** (approved rule data: Saudization/levy/GOSI/EOSB/Ramadan/overtime) used by labour build-ups; **full replay** of frozen estimates (indirects, commercial, tax) | RTE-02 | payroll costing reproduced; `replay_estimate` equals every frozen total | tests | Yes | authoritative rule texts supplied by the user |
| WP-16 | P1 | PRO-06, PRO-07 | **Bid evaluation and award**: weighted technical/commercial scoring, compliance matrix, interface matrix, award record, delivery milestones | none | scores trace to evidence | tests | Yes | none |
| WP-17 | **P1** | DSC-01, DSC-02, DSC-03, DSC-04, DSC-05, DSC-06, DSC-07, DSC-08, DSC-09, DSC-10, DSC-11, PRE-01 | **Pilot acceptance per discipline**: for each division an approved assembly set + rates priced Complete on a pilot BOQ; preliminaries template with time-related/fixed split | WP-00a | each DSC acceptance test (matrix) passes | pilot reports, hand totals | Yes | pilot data |
| WP-18 | P2 | SCO-11, SAU-05, LIB-05, LIB-09, SCO-10 | **Document & library quality**: live validation of requirements extraction on real documents; authority-fee schedules; licence review for sources used; OCR/CAD extraction option | none | extraction sample audited by a reviewer | reviewer sample | Yes | real documents |
| WP-19 | P3 | PRC-12, PRC-13, ENG-01, ENG-02 | **Shutdown/turnaround, modularisation, engineering services and home-office models** | WP-03, WP-05, WP-15 | each acceptance test in the matrix | tests | Yes | owner/company data |
| WP-20 | P3 | CTL-05, CTL-06, CTL-03 | **Change control and forecasting; benchmark library**: variation register priced against the awarded baseline; EAC/ETC; approved benchmark ranges and findings | WP-02, WP-10 | cumulative variation reporting reconciles | tests | Yes | actuals |
| WP-21 | P3 | SAU-06, SAU-07, SAU-04, OUT-05 | **Client compliance profile framework** (versioned profiles referencing controlled documents; CBS/WBS maps, forms, mandatory checks, templates), then a *specific owner's* profile **only from documents the user is authorised to supply**; local-content scoring where the owner's method is supplied | WP-07, WP-02 | export blocked when mandatory profile items are unmet; profile records document and revision | profile validation tests | Yes | owner's controlled documents |
| WP-22 | P1 (before shared deployment) | SCO-09, GOV-12 | **Scale and hardening**: cached estimate per request, paginated tables, incremental workbook export, security review items (TLS, CSRF, lockout, MFA/SSO), concurrency | none | 50k items: estimate < 10 s, pages < 3 s | published performance budget tests | Yes | review |

## 2. Dependency graph (critical path)
`WP-00a` ∥ `WP-01` → `WP-02` → `WP-03` → (`WP-04`, `WP-05`, `WP-09`, `WP-10`) → `WP-06`/`WP-13`/`WP-14` → `WP-19`.
`WP-07` and `WP-21` run after `WP-02` (profiles need the CBS/WBS cross-walk). `WP-08`, `WP-11`, `WP-16`, `WP-17`, `WP-22` are independent and can proceed in parallel.
**Foundational blockers, in order:** (1) real rates and factors (WP-00a), (2) units (WP-01), (3) WBS/CBS cross-walk (WP-02), (4) programme model (WP-03). Nothing in Levels 2–1 can be credibly built before 2–4.

## 3. Profile design sketch (client compliance and classification)
A *profile* is a versioned JSON/YAML configuration, never code: `id`, `kind` (`classification` | `client`), `issuing_body`, `document_reference`, `document_revision`, `effective_date`, `supplied_by` (user), `classes[]`, `cbs_wbs_map`, `required_forms[]`, `mandatory_checks[]` (references to reconciliation rules), `templates[]`, `numeric_parameters{}` (all user-supplied, none defaulted). Projects select zero or more profiles; the final gate evaluates the union of their mandatory checks; exports record profile ids and revisions. Without a loaded profile the application states "no client profile applied" and makes no compliance statement.

## 4. Cross-cutting rules for implementers
Use `.claude/skills/architecture-maintenance`: pure engines with independently computed expected values, services with `authorize`, actions in `api/actions.py`, forward-only migrations, tests with fake network and `tmp_path`, docs updated in the same change, and the matrix record's acceptance test turned into an automated test before its status is raised.
