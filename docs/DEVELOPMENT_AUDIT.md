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
* **Verdicts (software capability):** Level 5 and 4 conditionally supported; Levels 3, 2, 1 not supported (Missing capabilities). Data readiness (0 approved real rates, no productivity data) applies to every level.
* **Defects found and fixed, each with a regression test:** O(n²) estimate computation (20,000 items: 13.8 s → 2.7 s); `pypdf` undeclared so tender PDFs were never extracted on a default install; schedule→duration path untested, unreachable from API/UI and unprotected for archived projects (+ duplicate task codes); previously untested claims (what-if numbers, non-SAR project currency, takeoff-resource pricing, standard indirects, preliminaries-overlap rule, no outbound submission channel) now tested.
* **Corrections to earlier claims:** the glossary of "capabilities" in earlier docs counted cost codes, assumption definitions and templates; the matrix counts only implemented, tested behaviour. Division-level "support" (e.g. HVAC, electrical) is *definitions + generic engine*, not discipline-specific estimating logic.
* **Not claimed:** any Saudi Aramco or other client compliance; any AACE class or accuracy range (no classification exists); any live source retrieval by the application.
* A guard test (`tests/unit/test_capability_matrix.py`) now prevents the matrix from citing code, symbols or tests that do not exist and from claiming "tested" without a test that verifies the behaviour.
