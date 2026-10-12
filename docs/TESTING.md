# Testing

```
. .venv/bin/activate
pytest                      # or scripts/test.sh ; 163 tests, ~50 s
pytest tests/unit -q        # fast engine tests
pytest -k workflow -s       # the end-to-end nine-package scenario
pytest -m libreoffice       # (marker registered; LibreOffice tests auto-skip when `soffice` is missing)
```
Tests never write into the repository: databases are in-memory or in `tmp_path`, project/output/backup folders are redirected (`tests/conftest.py`).

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
| **End to end** | `tests/integration/test_full_workflow.py`, `test_final_flow.py` | **nine-package SYNTHETIC project**: BOQ import -> mapping -> build-up (hand-computed expected values) -> procurement -> RFQ -> quotations -> levelling -> selection -> approved rates -> commercial (independent re-derivation) -> reconciliation -> final approval -> offer -> gated export; blocked paths asserted along the way |

Financial tests use fixed expected values computed independently (separate arithmetic in the test, not the engine). All test data is labelled SYNTHETIC.
Not covered: the live Claude API, Microsoft Excel, browsers (only HTTP-level), very large BOQs.
