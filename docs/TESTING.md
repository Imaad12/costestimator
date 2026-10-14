# Testing

```
. .venv/bin/activate
pytest                      # or scripts/test.sh ; see the current count in DEVELOPMENT_AUDIT.md §9, ~95 s
pytest tests/unit -q        # fast engine tests
pytest -k workflow -s       # the end-to-end nine-package scenario
pytest -m libreoffice       # (marker registered; LibreOffice tests auto-skip when `soffice` is missing)
```
Tests never write into the repository: databases are in-memory or in `tmp_path`, project/workspace/output/backup/import folders are redirected (`tests/conftest.py`; imports live under the DB directory). **No test needs internet access**: external requests are mocked (`FakeFetcher`, fake `urllib` openers); the KAPSARC fixture is the real saved response in `data/public_data/gastat_cci/`.

| Area | File | What is proven |
|---|---|---|
| Calculations | `tests/unit/test_direct_cost.py`, `test_rate_build.py`, `test_indirect_duration.py`, `test_commercial.py`, `test_schedule_resolution.py`, `test_money_units.py` | quantity x rate, assembly consumption, waste (fixed/assumption/none, never twice), labour productivity (3 bases, OT), plant (utilisation, build-up, mobilisation), subcontract, indirect methods & duration, CPM, markup vs gross margin, contingency bases, discount, rounding step, tax separation, FX, unit conversion, missing-rate handling, double-count prevention, exact allocation (largest remainder), rate eligibility rules |
| Imports | `tests/imports/test_boq_import.py` | standard/irregular/Arabic headers, missing headers, invalid/negative/zero quantities, unknown/ambiguous/missing units, duplicates, blanks/headings, malformed & unsupported files, XLSX = CSV, source-row traceability, rejected rows, re-import (change requests, never overwritten), take-off resources, permissions, archived projects |
| Approvals | `tests/approvals/` | unapproved rates cannot become verified; index/missing rates cannot be approved; AI refused for every policy action (also when posing as admin); `app/ai` imports no approval/mutation code (AST test); approved data immutable; revisions/versions & audit; provisional approvals need reason+role and stay visible; self-approval switch; audit tamper detection; AI output schema/injection tests |
| Procurement | `tests/procurement/test_procurement.py` | needs detection, RFQ content/exports/Arabic/no invented contacts, quote import, validity & expiry, unit conversion, tax-inclusive normalisation, FX, missing items, adjustments (pending not applied), selection approval, value threshold role, rate publication (Pending Review, synthetic stays synthetic) |
| Reconciliation | `tests/reconciliation/test_recon.py` | unpriced/missing rates (Critical), unapproved assumptions, expired rates/quotations, duplicates, double count, exclusion contradictions, missing-in-revision, offer/schedule discrepancies, non-reconciling totals, exception policy (roles, Critical never waivable), configurable severities, version differences, audit report |
| Excel | `tests/excel/test_workbooks.py` | 27 required sheets & order, keys/headers, frozen panes, filters, validations, formulas & references, formats/protection, data dictionary, templates, populated values & IDs, **LibreOffice recalculation (0 errors/mismatches)**, tamper detection, round-trip & forged-status ignoring |
| API/UI | `tests/integration/test_api_ui.py` | auth, bad/forged tokens, server-side role checks on API and UI forms, uploads (no overwrite), downloads, every UI page rendering on the demo project, authoring forms |
| Data/ops | `tests/unit/test_library_data.py`, `tests/integration/test_backup_datasets_cli.py` | taxonomy completeness, no prices in catalogues, no invented assumption values, draft-only standard assemblies, circular assemblies, backup/restore/validate/corruption/safety, dataset ingestion issues, actuals & variance, CLI |
| Workspaces | `tests/workspaces/test_workspaces.py`, `test_cli_and_migration.py` | numbered folder names/order, project.json, project CLAUDE.md content (no secrets), duplicate IDs refused, idempotent repair, human notes preserved, adoption of existing folders, foreign-folder refusal, project isolation, override isolation, indexer (types, errors, versioned extracts, change flags, missing files, originals untouched), snapshot verify/replay after a newer rate, CLI project/sources/rates/index commands, authenticated CLI, copy-only workspace migration (dry run, no overwrite, idempotent) |
| Public sources | `tests/sources/test_rate_pipeline.py` | real CCI fixture import (exact values, manifests, duplicate refusal, revisions), mocked KAPSARC paging/dry-run/blocked/API-error, manual-only providers never fetch, fetcher backoff/no-retry-on-403/cache/robots/allow-list/proxy-blocked, rate import dry-run+real+manifest, candidate validation & provenance, queue classes, normalisation (FX/unit/VAT, originals untouched), review authority, unsafe candidates refused, publication → Pending Review, old version kept, frozen estimate unchanged, web extraction cases, watchlist refresh, Rate Dataset template import |
| Workspace/rate UI | `tests/integration/test_workspace_ui.py` | first-run dashboard, create project → workspace page, uploads never overwrite, indexing, completeness, rate-update screens, role enforcement on every decision |
| **End to end** | `tests/integration/test_full_workflow.py`, `test_final_flow.py` | **nine-package SYNTHETIC project**: BOQ import -> mapping -> build-up (hand-computed expected values) -> procurement -> RFQ -> quotations -> levelling -> selection -> approved rates -> commercial (independent re-derivation) -> reconciliation -> final approval -> offer -> gated export; blocked paths asserted along the way |

Financial tests use fixed expected values computed independently (separate arithmetic in the test, not the engine). All test data is labelled SYNTHETIC.
Not covered: the live Claude API, Microsoft Excel, browsers (only HTTP-level), very large BOQs.

## Audit-added tests (2026-10-13)
| File | What is proven |
|---|---|
| `tests/workspaces/test_audit_regressions.py` | estimate scaling ratio guard (fails on the old O(n²) code), real PDF/DOCX/XLSX extraction and image-only PDF reporting, `pypdf` declared, non-SAR project currency, what-if numbers, takeoff-resource pricing, preliminaries-overlap finding, no autonomous submission channel (static import scan) |
| `tests/unit/test_indirect_duration.py` (additions) | schedule tasks → CPM → duration proposal needs an approved calendar and human approval; archived projects refuse schedule/duration changes |
| `tests/integration/test_workspace_ui.py` (additions) | schedule actions via API with roles; standard indirect categories created as amount-less drafts |
| `tests/unit/test_capability_matrix.py` | the capability matrix cites only existing code/symbols/tests, status claims match evidence, no Aramco compliance claim, roadmap covers every open gap, rendered page is current |

## Iteration-4 additions (2026-10-13)
Every numeric test uses figures worked out by hand in the test (comments show the arithmetic); nothing is copied from the code under test. All data is SYNTHETIC.
| File | Covers |
|---|---|
| `tests/unit/test_industrial_units.py`, `test_industrial_pack.py` | exact industrial unit conversions and refusals, admin unit management, definitions-only industrial pack (idempotent, admin-only, no price column accepted) |
| `tests/unit/test_governed_params.py` | parameter lifecycle (propose/submit/approve, versions, effective resolution, project over company), roles (AI/viewer/procurement refused, self-approval switch), validators, productivity factors (multiplicative, scoped by cost prefix/WBS, unapproved flagged), plant minimum-hire/standby |
| `tests/unit/test_wbs_rollup.py` | tree roll-up and client cross-walk (longest prefix, ambiguity, unmapped) tie out to the estimate; WBS rules; WBS-scoped factors |
| `tests/unit/test_programme.py`, `test_programme_service.py` | FS/SS/FF/SF, lags, leads, float, constraints, cycles, predecessor syntax, calendar dates; loading histograms and man-hours (exact spreading, unscheduled bucket, shared tasks) |
| `tests/unit/test_mto.py` | derivation arithmetic, factor validation, pricing gate (Pending Review until approved), double-pricing guard, stale detection |
| `tests/unit/test_profiles_boe.py` | fact checks, profile lifecycle and attestation, compliance statement limits, classification from approved scheme, Basis of Estimate content and placeholders |
| `tests/unit/test_landed_labour_exposure.py` | landed cost step by step (4,504.0934375), exposure, hedge, statutory labour build-up, workforce mix |
| `tests/unit/test_risk_escalation.py`, `test_cashflow.py` | expected value, seeded Monte Carlo (reproducible, bounded, degenerate cases), escalation factors; hand-worked monthly cash flow with retention, bond and interest |
| `tests/unit/test_full_replay.py` | full-estimate replay after rate/factor/indirect/tax changes, legacy snapshots, tamper detection |
| `tests/unit/test_bids_scope.py`, `test_controls.py`, `test_provisions.py`, `test_methods.py` | bid scoring/gates/long-lead dates/interface matrix; variations, contract status, earned value; benchmarks, reserves, engineering, overhead; method alternatives |
| `tests/reconciliation/test_extended_rules.py` | new reconciliation findings and severities; package double count cannot be waived |
| `tests/integration/test_security_hardening.py` | CSRF origin check, headers, lockout/unlock, TLS refusal |
| `tests/integration/test_ext_ui.py` | every registered report renders (or explains), API listing/422s, inputs and structure pages enforce roles |
| `tests/unit/test_estimate_cache.py`, `tests/excel/test_workbooks.py` (addition) | cache hit/invalidation (also by another process), workbook style reuse equivalence |
| `tests/integration/test_full_workflow.py` (addition) | client-form export (item-code matching, formulas untouched, gated, preliminary copy labelled) |
| `tests/unit/test_generated_docs.py` | the generated reference docs list every governed kind, report and template |

## Pilot-validation additions (2026-10-13)
| File | Covers |
|---|---|
| `tests/unit/test_capability_matrix.py` (additions) | every record has exactly one status, a unique id, applicable levels and a detail section; counts quoted in other docs are generated from the records |
| `tests/integration/test_industrial_flow.py` (additions) | **structural**: each of the 23 take-off templates has a unit-compatible pack resource per slot; **mechanical**: each template derives and prices with SYNTHETIC factors/rates. These do not show that any template reflects real practice. See [PILOT_READINESS.md](PILOT_READINESS.md) §7 for what is verified vs synthetic vs placeholder |
| `tests/sources/test_rate_pipeline.py` (additions) | index sources/files cannot be imported as unit prices; the shipped pilot rate template's placeholder row creates no candidate |
| `tests/unit/test_pilot_templates.py` | governed-parameter CSV import creates Drafts only, reports bad rows, rejects the template's placeholders |

## Synthetic end-to-end pilot (2026-10-14)
`tests/synthetic_pilot/pilot.py` drives a SYNTHETIC 30-line piping project through the real services, CLI, REST API and UI against a scratch database (fixtures in `tests/fixtures/synthetic_pilot/`; run it with `python scripts/run_synthetic_pilot.py [FRESH_DIR]`). `tests/integration/test_synthetic_pilot.py` asserts the stage verdicts and the independently computed figures (BOQ total 365,361; commercial chain; quotation levelling 86,350.40 / 88,019.55 / 90,065.70; frozen-estimate replay after a parameter and a rate change; preliminary estimate cannot be approved or exported; index sources refused; unit flags). Every number is SYNTHETIC and every approval is a `TEST ACTOR`; passing proves the software path, not estimating accuracy. Evidence and findings: [SYNTHETIC_PILOT_RUN.md](SYNTHETIC_PILOT_RUN.md).
