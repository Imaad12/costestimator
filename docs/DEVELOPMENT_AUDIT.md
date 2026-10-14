# Development audit (second iteration, 2026-10-12/13; capability audit appended 2026-10-13)

Purpose: record what was found when the existing implementation was inspected, what was verified by actually running it, what is incomplete or broken, and where the earlier report did not match the code.
Method: inspect before changing; re-run; compare claims with code; then implement.

## 1. Repository state at the start
| Item | Finding (commands run) |
|---|---|
| Working directory / remote | `/home/user/costestimator`, remote `origin` = `https://github.com/Imaad12/costestimator` |
| Branch / commit | `claude/wizardly-einstein-w4ykwd` at `bf7d43a` ("Labour/plant build-up form, similar-item search, …"); same commit on `origin/claude/wizardly-einstein-w4ykwd` (the first push had succeeded) |
| `main` | only `5b65ebe` ("Initial commit"); all implementation lives on the feature branch; **nothing was merged into `main`** (not authorised) |
| Working tree | clean (`git status --short` empty) — no uncommitted user changes to protect |
| Instruction files | **none**: no root `CLAUDE.md`, no `.claude/`, no `docs/DATA_MODEL.md`, `PROJECT_WORKSPACES.md`, `RATE_UPDATE_WORKFLOW.md`, `DEVELOPMENT_AUDIT.md`, `NEXT_STEPS.md` |
| Size | ~11.9k lines of Python under `app/` at the start; 6 SQL migrations; 164 tests |
| Tooling present | Python 3.13, `.venv`, LibreOffice (`/usr/bin/soffice`), Claude Code 2.1.296 |

## 2. What exists and was verified
| Claim in the earlier report | Check performed | Result |
|---|---|---|
| 164 passing tests | `python -m pytest -o addopts="" -q` | **164 passed in 68.9 s** — confirmed |
| 27-sheet master workbook | `len(app.excel.master.REQUIRED_SHEETS)` | 27 — confirmed |
| Populated demo workbook: 217 formulas, 0 errors, 0 mismatches | `export-workbook` + `verify-workbook` (LibreOffice recalculation) on a fresh scratch DB, re-done after all changes | **structure_ok true, 217 formulas, 0 errors, 0 mismatches, not stale** — confirmed |
| 927 catalogue resources, no prices | `init` on a scratch DB, `coverage` | 927 resources, 0 real approved rates, 0 synthetic, 927 missing — confirmed |
| Audit hash chain | `audit-verify` on the demo DB | `{"ok": true, "checked": 431}` |
| Approval enforcement server-side, AI refused | existing tests (`tests/approvals`) re-run | pass |

## 3. Conflicts between the reported implementation and the actual code
1. **"11 standalone workbook templates"** — `templates/` holds **11 `.xlsx` files of which one is the master** (`estimate_master.xlsx`), i.e. 10 standalone workbooks + the master, plus 2 `.docx`. Documentation now says so.
2. **`coverage` showing zeros** — on a fresh checkout the default `var/ksa_estimator.db` is uninitialised (git-ignored), so `coverage` printed all zeros without explanation. Not a calculation defect; `coverage` now prints a hint to run `init`.
3. **"Estimates reference stable versions"** — true for rate ids on each cost line, but a frozen `estimate_versions` row stored only results, **not the inputs**; after a newer rate was approved the old estimate could not be re-derived. Fixed by `estimate_snapshots` (migration 0007) + `verify_snapshot` / `replay_direct_cost`. Replay covers the direct-cost engine only (see §5).
4. **Project files** lived in `data/projects/<id>/uploads` and `data/outputs/<id>` (git-ignored), not in a per-project workspace; the original brief's numbered folders did not exist. Replaced by workspaces; a copy-only migration was added for legacy layouts.
5. **Backups** did not include any workspace/import files (they did not exist yet). Backup/restore/project export now include `workspaces/` and `imports/`.
6. **GASTAT adapter "stub"** — still true for the GASTAT website, but the research showed a documented open-data API exists for the same series (KAPSARC, Opendatasoft v2.1). A real provider now exists. It is **not live-verified** from this sandbox (see §4).
7. **Test isolation** — during this iteration a new import-manifest feature wrote original files into `data/public_data/imports/` while running tests, and they were committed once by mistake (commit `965dfdb` contains them). The directory was moved to `var/imports/` (git-ignored, redirected by every test fixture) and the files removed from the index; they remain in earlier commits' history (not rewritten, as history rewriting is prohibited). They are small test files, no client data.
8. **`rate_staging` vs candidates** — two overlapping dataset-ingestion flows now exist (legacy and new). Documented; consolidation is NEXT_STEPS #12.

## 4. What was verified in this iteration
| Area | Evidence |
|---|---|
| Full suite after all changes | **210 passed** (`python -m pytest -o addopts="" -q`) |
| Fresh synthetic project + numbered workspace | CLI `project create --demo` on a scratch DB created `PRJ-0001-office-fit-out-synthetic-test/` with the ten folders, `CLAUDE.md`, `project.json`; generated `CLAUDE.md` content inspected |
| BOQ import into the workspace | `project import-boq` of `data/demo/demo_boq.csv`: 26 items, 9 headings, 1 rejected (`TBA` quantity), copy stored in `3. BOQ & Takeoff/` |
| Indexer | 3 documents indexed, extracts and `project_summary.md` written; re-run idempotent (tests) |
| External dataset import | real KAPSARC/GASTAT CCI sample (39 records) imported with manifest; SYNTHETIC price list validated (dry-run) then imported as 2 candidates |
| Proposal cannot be used as a rate | after import: `resource_rates` rows with a price = 0; candidates `Pending Review`; the strict resolver would still return MISSING |
| New rate approval vs history | live script on the demo project: froze version, approved a new global rate for `DEMO-MAT-001` (old `30` → Superseded, new `999.99` Approved): frozen totals and fingerprint **unchanged**, `verify_snapshot` ok (1 newer rate listed), `replay_direct_cost` ok |
| Workbooks | `export-workbook` + LibreOffice `verify-workbook`: 217 formulas, 0 errors, 0 mismatches. **Microsoft Excel was not available** |
| Live access from the application | `sources refresh --provider kapsarc-gastat-cci` (twice) → `BLOCKED`: `URLError: Tunnel connection failed: 403 Forbidden` reading robots.txt; no data request was made. `curl` HEAD to stats.gov.sa, datasaudi.sa, opendata.stats.gov.sa, KAPSARC, data.gov.sa, tenders.etimad.sa → code 000. **So no live fetch by the application has succeeded from this sandbox.** |
| Real network facts obtained | through the Firecrawl fetch tool (not by the application): KAPSARC dataset metadata and the 2026-04 records (see `data/public_data/gastat_cci/PROVENANCE.md`, `ACCESS_LOG.md` rows 37–43) |

## 5. Incomplete, partial or broken (honest list)
* **No real approved rates (0).** No source of SAR unit rates was found that could be reused; the pipeline to load them exists, the data does not.
* KAPSARC provider: mock-tested only; robots.txt/pagination behaviour of the real host unverified. GASTAT website and Etimad: manual-only. Web-price extraction: fixture-tested, never run on a real page.
* Snapshot replay covers direct cost only; versions frozen before migration 0007 have no snapshot.
* Skills and `CLAUDE.md` files were structurally tested (well-formed, referenced paths exist) but have **not been executed by a live Claude Code session**; treat them as untested procedures until used.
* Indexer: no OCR, no CAD/BIM; file-name-based classification only.
* Optional Claude features never exercised against the live API; Microsoft Excel never exercised.
* Security: local single-user design (no TLS/CSRF tokens/lockout/MFA); workspace folders have no per-user ACL.
* Known broken items: **none found** — the suite is green. Items above are gaps, not failures.

## 6. Changes made in this iteration (summary)
Root `CLAUDE.md`; 14 skills (`.claude/skills/`, generator `scripts/gen_skills.py`); numbered workspaces + project `CLAUDE.md` + manifest (`app/services/workspaces.py`); document indexer; estimate input snapshots; copy-only workspace migration with dry-run/backup/report; migration `0007`; public-source layer (`app/sources`, `app/rate_updates`): provider interface, polite fetcher, KAPSARC/GASTAT CCI provider, Etimad/GASTAT manual-only providers, web evidence extractor, manifests, index import, rate candidates + review queue + normalisation + publication, refresh/status reports;
CLI (`project`, `sources`, `rates`, `index`, `migrate-workspaces`, authenticated state-changing commands); UI (Rate updates, candidate detail, Workspace & documents, Completeness, first-run guidance, no-real-rates banner, approvals queue entry); documentation (this set + updates); 46 new tests.

## 7. What should be changed next
See [NEXT_STEPS.md](NEXT_STEPS.md): (1) load evidence-backed rates, (2) confirm the live KAPSARC path on a normal network, (3) test workbooks in Microsoft Excel; then consolidate the two dataset flows and extend snapshot replay.

## 8. Five-level capability audit (2026-10-13)
Full results: [ESTIMATING_CAPABILITY_MATRIX.md](ESTIMATING_CAPABILITY_MATRIX.md); gaps and order of work: [ESTIMATING_GAP_ROADMAP.md](ESTIMATING_GAP_ROADMAP.md).
* **Verdicts at the time of the first audit (software capability):** Level 5 and 4 conditionally supported; Levels 3, 2, 1 not supported (Missing capabilities). Superseded by §9. Data readiness (0 approved real rates, no productivity data) applies to every level.
* **Defects found and fixed, each with a regression test:** O(n²) estimate computation (20,000 items: 13.8 s → 2.7 s); `pypdf` undeclared so tender PDFs were never extracted on a default install; schedule→duration path untested, unreachable from API/UI and unprotected for archived projects (+ duplicate task codes); previously untested claims (what-if numbers, non-SAR project currency, takeoff-resource pricing, standard indirects, preliminaries-overlap rule, no outbound submission channel) now tested.
* **Corrections to earlier claims:** the glossary of "capabilities" in earlier docs counted cost codes, assumption definitions and templates; the matrix counts only implemented, tested behaviour. Division-level "support" (e.g. HVAC, electrical) is *definitions + generic engine*, not discipline-specific estimating logic.
* **Not claimed:** any Saudi Aramco or other client compliance; any AACE class or accuracy range (no classification exists); any live source retrieval by the application.
* A guard test (`tests/unit/test_capability_matrix.py`) now prevents the matrix from citing code, symbols or tests that do not exist and from claiming "tested" without a test that verifies the behaviour.

## 9. Iteration 4 - "run everything that is missing" (2026-10-13)
Request: implement what the capability audit found missing, fix what does not work, verify, report honestly. Constraints kept: no invented prices/rates/factors/standards, no automatic approval, no silent overwrite of approved or frozen data, no automated quantity take-off, no autonomous tender submission, **no claim of Saudi Aramco (or any client) compliance**, no merge to `main`, no PR.

### 9.1 What was built (all with automated tests using hand-calculated expectations)
| Area | Delivered | Matrix records |
|---|---|---|
| Units / catalogue | exact industrial units (inch-dia, joint, spool, loop, MVA, flow, pressure ...), administrator `add_unit`, optional definitions-only `industrial` pack (division M, 258 definitions, loader `pack load industrial`) | SCO-04 IT, LIB-04 PA |
| Governed parameters | one validated, versioned, sourced, human-approved store for ~20 kinds of company-supplied numbers; ships empty; frozen into snapshots | (foundation) |
| Structure | WBS, client code cross-walk, CBS/WBS roll-ups that tie out | LIB-02, CTL-07 IT |
| Programme | FS/SS/FF/SF, lags, float, constraints, calendar; loading histograms; man-hours; cost-to-task tie-in | DUR-02, DUR-04, DUR-05, EST-10 IT |
| Direct cost | productivity factors (scoped, multiplicative), plant minimum-hire/standby; derived labour carries hours | EST-12, EST-05 IT |
| Take-off derivation | 23 structure-only templates (103 slots), approved factors, Pending Review pricing gate, stale detection | PRC-01..14, IND-02, CLO-01/02 PA |
| Commercial/tax | landed cost + logistics (derived-rate proposals), currency exposure + hedge cover, Saudi-style statutory labour build-up + workforce check | TAX-02, TAX-04, CUR-03, SAU-03 IT; TAX-03 PA |
| Risk / finance | quantified register, expected value, seeded Monte Carlo (proposal), time-phased escalation, cash flow/retention/bonds/financing (Draft-indirect proposals) | RSK-03/04/05, CTL-04, CLO-03 IT |
| Basis of estimate | BoE generator (facts + six estimator-only sections), classification from an approved scheme, client-profile framework, method alternatives, client-form export | BOE-03, BOE-04, SAU-06 IT; BOE-05, EST-11, OUT-05, SAU-04 PA |
| Procurement / control | bid evaluation, long-lead, interface matrix; variations, contract status, earned value; benchmarks; reserves/engineering/overhead proposals; 9 new reconciliation rules | PRO-06, PRO-07, CTL-03/05/06, ENG-01/02 IT |
| Governance | **full-estimate replay** from snapshot (`compute_estimate_from`), read-only estimate cache | GOV-05 IT, SCO-09 PA |
| Security | same-origin (CSRF) check, security headers/CSP (no inline scripts), sign-in lockout + unlock, TLS flags and refusal to listen openly without TLS | GOV-12 PA |
| Surfaces | UI pages *Structure & programme*, *Analysis & controls*, *Inputs & parameters*; 22 reports shared by UI/REST/CLI; 35 new actions; CLI `report/param/wbs/mto/profile/pack/unlock-user`; 2 new skills | |
Migrations 0008-0013 (forward-only). Generated references: GOVERNED_PARAMETERS, ANALYSIS_REPORTS, MTO_TEMPLATES, SECURITY.

### 9.2 Defects found and fixed during this iteration (each has a regression test)
1. `L/S` already means *lump sum*: litre-per-second must not shadow it - found by the unit test; litre/second is `LPS`.
2. A package-gap rule fired on every project that has subcontract items but no package matrix (it broke the full-workflow test) - the interface checks now run only once a scope matrix exists.
3. Imported take-off labour lines carried no hours (invisible to man-hour reports) - hours are now recorded.
4. The master workbook writer re-hashed a style object for every cell: 20,000 items took 59.6 s; styles are now built once per column and copied (**25.6 s**, styles proven identical by a test).
5. A naive cache would have served stale estimates after a CLI import while the server runs - the cache also keys on SQLite `data_version` (test with a second connection).
6. A client-form template path could point anywhere on disk - restricted to the project workspace (`FORM_PATH`).
7. Cookie-authenticated writes had no cross-site protection (SameSite only) - same-origin check added; the existing UI tests now emulate a browser's `Origin`.
8. Take-off slots demanded `hr`/`count` units while the pack prices plant per day/month and subcontracts per `item`/`joint`/`loop` - found by the end-to-end industrial test; slots now accept unit *groups* (`time`, `count*`).
9. (Own mistakes caught by tests) audit-log argument order in the pack loader; a vacuous assertion in two new tests; an incorrect expected value in a cash-flow horizon.

### 9.3 Verification performed
* **Full suite: 341 passed** (`python -m pytest -o addopts="" -q`, ~75 s). Before this iteration: 230. `tests/integration/test_industrial_flow.py` runs the whole industrial chain against the real pack (200 weld joints: 22,200 -> 24,400 with a height factor; 660 man-hours; roll-up, loading, risk, Basis of Estimate).
* Live run on a scratch DB: `init` -> `demo` -> every registered report via the CLI -> server started on a port -> login, 7 pages (200), CSRF refused without Origin and accepted with it, headers present -> Playwright/Chromium: login, screenshots of the new pages, a real browser form submission (WBS node) succeeded with the Origin check on, no CSP console errors.
* Master workbook of the demo project recalculated in LibreOffice: **217 formulas, 0 errors, 0 mismatches**, structure OK. `audit-verify`: chain OK (433 entries).
* Measured at 20,000 BOQ items: estimate 2.7 s; repeat from cache 0.09 ms; freeze + snapshot 4.4 s; **full replay 3.9 s (ok)**; roll-up 2.9 s; master workbook 25.6 s.
* Capability matrix: <!-- MATRIX_COUNTS_BEGIN -->141 records = 93 IT + 3 IU + 42 PA + 3 MI + 0 NA (IT implemented and tested, IU implemented but unverified, PA partial, MI missing, NA not applicable) - generated from `docs/capability_matrix.json`<!-- MATRIX_COUNTS_END --> (at the first audit: 56 IT, 3 IU, 42 PA, 30 MI). Levels 5-2 conditionally supported; Level 1 not supported (SAU-07).

### 9.4 What is NOT done and why
* **Real rates and factors (LIB-07, LIB-08)** - data; only the user can supply and approve them. The new framework ships no value of any kind.
* **SAU-07 (Saudi Aramco-type requirements)** - requires the owner's controlled documents, which are not in the repository. The profile framework exists; **no compliance is claimed**.
* **Microsoft Excel** and **live source retrieval from a normal network** - not available in the sandbox (OUT-03, RTE-05 remain *Implemented but unverified*).
* Discipline records stay *Partial*: templates and the pack are structure; every factor, pipe-class rule, shutdown logic or camp-sizing rule is the company's to supply. Also not built: schedule-file import and Gantt, withholding tax/zakat, bilingual deliverables, MFA/SSO, per-folder ACLs, server-side pagination, a 50,000-item run.
* The 2 new skills and the CLI/UI flows were exercised by tests and a live run, **not by a live Claude Code session**.


## 10. Pilot validation pass (2026-10-13)
Scope: validation and readiness only, no new feature breadth.
* **Matrix reconciliation.** The "131 = 85 + 40 + 3" report omitted the 3 *Implemented/Unit-tested (IU)* records; the generated rollup now states every status and asserts they sum to the record count. Counts in this file, `NEXT_STEPS.md` and `ESTIMATING_GAP_ROADMAP.md` are generated from `capability_matrix.json`, and a test fails if they drift.
* **Defects found and fixed.** (1) The rate importer would have accepted a price column from an *index* source - now refused (`SOURCE_NOT_PRICE`). (2) Take-off template `instrument.loop/dcs_config` had no compatible pack resource (subcontract with an hour unit) - changed to a labour slot.
* **Added, minimal:** `governed.import_csv` + `param import` (Drafts only), `templates/pilot/*.csv`, [PILOT_READINESS.md](PILOT_READINESS.md).
* **Controls re-verified by the full suite** (replay, approvals, provenance, workspace isolation, tender-export gating): see PILOT_READINESS §9 for the tests that prove each. Result recorded in the commit/final report.
* **Not claimed:** accuracy on real work, any client compliance, Microsoft Excel behaviour, live Claude API behaviour.


## 11. Synthetic end-to-end pilot (2026-10-14)
A SYNTHETIC 30-line piping package was run through project creation, BOQ import (unit flags), mapping, rate import, governed parameters, assemblies, procurement/levelling, programme, take-off templates, direct/indirect/commercial calculation, risk, escalation, cash flow, Basis of Estimate, reconciliation, freeze/replay, export, CLI/API/UI. Result and evidence: [SYNTHETIC_PILOT_RUN.md](SYNTHETIC_PILOT_RUN.md). Defects fixed (with tests): synthetic candidates were published as market prices (D-1), `param import` lacked a dry run (D-2), the BOE could not carry a project's validation-only statement (D-3). Open observations (not fixed): cash flow/escalation cover only cost tied to programme activities and the cash-flow balance is then overstated; `percent_of_direct` indirects have no eligibility base; day-priced plant needs a documented exception. The pilot proves the software path with synthetic data and test actors only; it does not validate estimating accuracy.

## 12. Pilot findings closed (2026-10-14)
The four findings of the synthetic pilot were closed and re-demonstrated by the reusable pilot (stages 13d and 19, [SYNTHETIC_PILOT_RUN.md](SYNTHETIC_PILOT_RUN.md) §4b): (1) cost with no time allocation is never spread - explicit approved `time_allocation` rules or an INCOMPLETE label + blocking High finding; cash flow reconciles under documented conventions; (2) percentage indirects/adders have an explicit eligibility base with an audit breakdown and overlap detection, legacy bases and frozen estimates unchanged; (3) day-priced plant uses extended hire terms read against the programme window (working vs calendar days, minimum hire, standby, mobilisation); (4) approval identity is a durable record (`actor_type`, `environment`) and `services/readiness.py` makes SUBMISSION READY impossible for demo/synthetic projects, test or unregistered principals and non-production environments. Migration 0014. Suite: 385 passed. Not claimed: real-data accuracy, identity assurance (no MFA/SSO), Microsoft Excel behaviour; allocation/eligibility/plant terms in the pilot are synthetic decisions.

## 13. End-to-end closure (2026-10-14)
Starting point `50e17f2` (385 tests). Added: migration `0015` (assumption governance columns + immutability triggers; `productivity_norms`, `workforce_profiles`, `work_activities`, `programme_baselines`; tender registers; `standards_register`; `tender_packs`, `generated_documents`, `open_actions`),
the productivity/workforce/calendar engine, assumptions governance, tender intake and query registers, the 45-document pack with applicability, manifest and validator, the hypothetical handover pack, Stage-J readiness extensions, standards register, the CLI `action` command, and a 27-stage synthetic scenario with an independent oracle.
Defects found and fixed on the way: self-approval was **allowed by default** (and the Administrator exempt); `config/settings.toml` also set it true; the CLI `create-user --reset` was unaudited; the demo seeder relied on self-approval; time-phased reports showed 28-digit residues; equipment and subcontract capacity were wrongly scaled by attendance in the first draft of the engine (caught by the scenario, fixed, test added).
Evidence: `docs/END_TO_END_CLOSURE_PLAN.md` (requirements matrix), `docs/SYNTHETIC_END_TO_END_CLOSURE_REPORT.md` (generated from the run), `docs/ASSUMPTIONS_GOVERNANCE_AND_SECURITY_AUDIT.md`, `docs/WORKFORCE_PRODUCTIVITY_AND_PROGRAMME_METHOD.md`, `docs/TENDER_DOCUMENT_APPLICABILITY_MATRIX.md`, `docs/STANDARDS_AND_EVIDENCE_REGISTER.md`.
