# CLAUDE.md — KSA Construction Estimating Suite

Operating guide for Claude Code sessions in this repository. Keep it short: detail lives in `docs/` and `.claude/skills/`. If this file and the code disagree, the code wins — fix this file.

## 1. Purpose and users
A local-first, Excel-first estimating and procurement-support system for Saudi construction contractors. Users: **Estimator** (authors BOQ mapping, assemblies, assumptions), **Procurement Reviewer** (rates, quotations, supplier selection),
**Commercial Approver** (commercial policy, tax, final estimate, offer, tender export), **Administrator**, **Viewer**. An AI Assistant principal exists but has **no authority**.

## 2. Scope
All trades: preliminaries, civil/earthworks, infrastructure, structural, architectural, external works, MEP — HVAC/mechanical, plumbing/drainage, fire protection, electrical, ELV — specialist systems (lifts, façade, kitchens, BMS…), subcontract packages
(cost-code divisions A–L; tree in `data/taxonomy/cost_codes.csv`, rendered in `docs/TRADE_TAXONOMY.md`). Taxonomy is data, not code.

## 3. Non-negotiable rules (human in the loop)
1. **Quantities are human-measured.** Never measure drawings, infer, generate or "complete" quantities. No automated takeoff.
2. **AI proposes; humans approve.** AI output = `ai_suggestions` / rate candidates / index rows in *Pending Review*. `app/ai` must never import approval or mutation code, and `app/sources` + the importer/refresh modules of `app/rate_updates` must never reference review/publish/approve functions (AST tests in `tests/approvals/`).
3. **Never invent data**: no prices, suppliers, wages, productivity, benchmarks, tax or FX values. A missing rate stays missing (`amount=None`, never 0). Synthetic data must be labelled `SYNTHETIC / DEMO / NOT A MARKET QUOTE`.
4. Approval is enforced **server-side** in services via `approvals.engine.authorize` using `app/approvals/policy.py`. Never move a check into the UI, never write `approvals`/status rows directly, never weaken a role or gate to make a test pass.
5. Approved records are immutable. Change = new version / pending revision. Frozen estimate versions are never rewritten. A new global rate must not alter an existing estimate version.
6. Index data (GASTAT CCI) is **not a price**. No regional multipliers. Originals of imported prices are never overwritten.
7. Do not claim something works unless you ran it. Report blocked/unverified things plainly (live APIs, Microsoft Excel, real rates: see `docs/KNOWN_LIMITATIONS.md`).

## 4. Repository map (read the matching doc before editing a subsystem)
| Path | Responsibility | Read first |
|---|---|---|
| `app/estimators/` | PURE Decimal engines (direct cost, indirects, CPM duration, commercial, pricing schedule, orchestrator `estimate.py`, `context.py` = the only SQL reader) | `docs/ESTIMATING_METHODOLOGY.md` |
| `app/approvals/` | role matrix `policy.py`, `engine.py` (`authorize`, `record`) | `docs/APPROVAL_WORKFLOW.md` |
| `app/services/` | DB domain services: rates, assumptions, assemblies, boq, projects, **workspaces**, **project_index**, **snapshots**, estimates, commercial, offers, backup, audit, auth, refdata | `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md` |
| `app/imports/` | BOQ/takeoff importer, legacy dataset staging (`datasets.py`) | `docs/IMPORT_EXPORT_FORMATS.md` |
| `app/procurement/` | needs → RFQ → quotes → levelling → selection → rate publication | `docs/PROCUREMENT_GUIDE.md` |
| `app/reconciliation/` + `config/reconciliation_rules.json` | findings, exceptions, final gate | `docs/APPROVAL_WORKFLOW.md` |
| `app/excel/` | `spec.py` is the single source of column truth; builder, master (27 sheets), templates, roundtrip, LibreOffice `recalc.py` | `docs/EXCEL_WORKBOOK_GUIDE.md`, `docs/EXCEL_DATA_DICTIONARY.md` |
| `app/sources/`, `app/rate_updates/` | public-source providers, fetcher, web evidence extraction; manifests, candidates, normalisation, importer, refresh | `docs/RATE_UPDATE_WORKFLOW.md`, `docs/KSA_DATA_SOURCES.md`, `docs/RATE_PROVENANCE.md` |
| `app/ai/` | optional, review-only suggestions | `docs/APPROVAL_WORKFLOW.md` (AI section) |
| `app/estimators/param_kinds.py`, `app/services/governed.py` | **governed parameters**: every company-supplied number (productivity, hire terms, calendar, escalation, payment terms, benchmarks, take-off factors, statutory rules ...) is a versioned, sourced, human-approved row; the library ships **empty** | `docs/GOVERNED_PARAMETERS.md` |
| `app/reporting/registry.py`, `app/api/actions_ext.py` | one registry of read-only reports (UI+REST+CLI) and the iteration-4 actions; `propose_*` actions create Drafts only | `docs/ANALYSIS_REPORTS.md`, `docs/MTO_TEMPLATES.md` |
| `app/services/{wbs,programme,mto,profiles,boe,landed,labour,risk,cashflow,bids,controls,provisions,methods}.py` | WBS/CBS roll-ups, programme+loading+man-hours, take-off derivation, client profiles/classification/BoE, landed cost/FX/statutory labour, risk+escalation, cash flow, bids/long-lead/interfaces, variations+EVM, benchmarks/reserves/engineering/overhead, method alternatives | `docs/ESTIMATING_CAPABILITY_MATRIX.md`, `docs/ESTIMATING_GAP_ROADMAP.md` |
| `app/security.py` | same-origin (CSRF) check + security headers; sign-in lockout is in `services/auth.py` | `docs/SECURITY.md` |
| `app/api/actions.py` | single action registry used by UI + REST | `docs/ARCHITECTURE.md` |
| `app/web/` , `app/cli.py`, `app/main.py` | UI templates, CLI, FastAPI factory | `docs/USER_GUIDE.md` |
| `app/migrations/*.sql` | forward-only schema (0001–0013) | `docs/DATA_MODEL.md` |
| `data/` | seed CSVs (taxonomy, catalogues **without prices**, assumptions, assemblies, source register), `public_data/` evidence samples | `docs/DATA_MODEL.md` |
| `projects/` | per-project numbered workspaces (git-ignored, never commit client files) | `docs/PROJECT_WORKSPACES.md` |
| `var/` | runtime: SQLite DB, backups, `imports/` originals + manifests, source cache (git-ignored) | |
| `tests/` | pytest suite (`unit imports approvals procurement reconciliation excel integration workspaces sources`) | `docs/TESTING.md` |

## 5. Source of truth
The **SQLite database** holds every number and approval. Files are evidence or generated views (`project.json`, project `CLAUDE.md`, `2. AI Context/*`, workbooks, docs generated by `scripts/gen_docs.py`). Never create a second authoritative copy (JSON/CSV mirror) of rates, approvals or estimates.
Seed CSVs are insert-only into the DB. Table groups and the 11 data classes: `docs/DATA_MODEL.md`.

## 6. Estimating flow
`context.load_inputs` (SQL → immutable `EstimateInputs`) → `compute_direct_cost` → `compute_indirects` → `compute_commercial` → `build_schedule` → tax on the tendered schedule → state/blockers/completeness + SHA-256 fingerprint. A rate prices a line only if Approved (or project-Provisional), in date, in region, a real price type, FX approved; else the line is unpriced with an exception.
Reconciliation (configurable severities) gates final approval; `export_submission` re-checks everything and needs the Commercial Approver's tender-export approval. Money is `Decimal`, rounded half-up per line.

## 7. Excel conventions
Spec-driven (`app/excel/spec.py`): hidden key row 4, header row 5, data from row 6; yellow input / grey formula (locked) / blue read-only; `fullCalcOnLoad`. Python is authoritative; formulas mirror it. Verify with LibreOffice: `python -m app.cli verify-workbook FILE --project PRJ-…`.
Imports create **drafts/proposals only**; status columns in files are ignored. After changing a spec: `python -m app.cli templates`, `python scripts/gen_docs.py`.

## 8. Approvals and audit
Roles → actions in `app/approvals/policy.py`. Self-approval can be blocked (`KSA_ALLOW_SELF_APPROVAL=false`). Every approval writes `approvals` + a hash-chained `audit_log` row (`python -m app.cli audit-verify`; tamper-evident only). Reconciliation Critical findings can never be waived.
Rate path: candidate → *Approved for Publication* (human) → published as *Pending Review* rate → `approve_rate` (human).

## 9. Project workspaces
`projects/PRJ-nnnn-slug/` with fixed folders `1. Tender Documents`, `2. AI Context`, `3. BOQ & Takeoff`, `4. Clarifications & Assumptions`, `5. Estimate & Cost Build-Up`, `6. Procurement & Quotations`, `7. Programme & Indirects`, `8. Commercial Submission`, `9. Reconciliation & Approvals`, `10. Exports & Archive`, plus `CLAUDE.md` and `project.json`.
Created automatically by `projects.create_project` → `workspaces.ensure_workspace` (idempotent; never overwrites). **When working on a project, read `projects/<id>/CLAUDE.md` first.** Never edit originals in `1. Tender Documents`. Index documents with `project index`.

## 10. Provenance and rate updates
Every candidate keeps exact URL/file, retrieval date, original price (immutable), basis flags, evidence snippet, manifest. Sources are accessed politely (robots, rate limit, backoff, cache) and never circumvented. Blocked sources are logged, not retried in loops. A rate update never mutates a frozen estimate.
Commands: `sources list|status|refresh [--dry-run]`, `rates import|validate|pending|review|publish`, `index import`, `coverage`.

## 11. Commands
```
python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
python -m app.cli init --demo-users && python -m app.cli demo && python -m app.cli run     # http://127.0.0.1:8000
python -m pytest -o addopts="" -q          # full suite (≈65 s); targeted: pytest tests/sources -q
python -m app.cli coverage | audit-verify | verify-workbook FILE | templates | project create|index|search|refresh|import-boq|verify-snapshot | migrate-workspaces --dry-run
python -m app.cli report PRJ-… NAME [--param k=v --save] | param kinds|list|propose|approve … | wbs PRJ FILE | mto templates|preview|apply | profile create|link|attest … | pack load industrial
```
State-changing CLI commands act as a real user: `KSA_CLI_USER`/`--user` + `KSA_CLI_PASSWORD`. Acceptance for any change: relevant tests added and the **full suite green**, docs updated, no approval rule weakened, no invented data, no network needed by tests.

## 12. Git workflow
Work on the feature branch given for the session (currently `claude/wizardly-einstein-w4ykwd`); never commit to or merge into `main` without explicit authorisation; no force-push, reset or history rewrite; do not open a PR unless asked.
Check `git status` first and never overwrite uncommitted user changes. Commit with clear messages; push only with `git push -u origin <branch>` and report the real result. No model identifiers in repo artifacts. Never commit `projects/*`, `var/`, `.env`, client documents or secrets.

## 13. Adding a feature or a trade
* **New trade / sub-trade / cost code:** data only — add rows to `data/taxonomy/cost_codes.csv` (or Settings → Add cost code), catalogue rows (no prices) in `data/<type>/…csv`, then `python scripts/gen_docs.py`. No engine change. See `docs/EXTENDING.md`.
* **New feature:** put calculation in `app/estimators/` (pure, with independently computed expected values in tests), persistence in a service, approval via `policy.py` + `authorize`, expose via `api/actions.py` (UI and API share it), add a migration if the schema changes (never edit an applied migration), add tests, update docs. Use `.claude/skills/architecture-maintenance`.
* **New data source:** a provider in `app/sources/providers.py` with an `AccessPolicy`, offline tests with a fake fetcher, a Source Register row, and an `ACCESS_LOG.md` entry. See `.claude/skills/rate-source-research`.

* **New company-supplied number:** a governed parameter kind (`param_kinds.py`) - never a default in code, never a seed value. **New analysis:** a `@report` in `reporting/registry.py`; anything that writes goes through an action + service. A proposal (`propose_*`) must end as a Draft/Pending record that a person approves; an analysis run is saved, never approved.
* **Client/owner requirements** (e.g. Saudi Aramco) enter only as a client profile loaded by a person from that owner's controlled documents, each requirement with its source reference. Never state compliance with an owner's standards; say what was loaded and checked.

## 14. Skills (`.claude/skills/*/SKILL.md`)
project-initializer · project-indexer · boq-import-review · requirements-extraction · assembly-management · estimating-workflow · rate-source-research · rate-update-review · subcontractor-quote-analysis · procurement-rfq · gantt-duration-estimation · reconciliation-check · excel-validation · architecture-maintenance · governed-inputs-and-analysis · client-profile-loading.
Skills orchestrate existing functions; they do not bypass validation or approvals.

## 15. Where things are documented
`docs/ESTIMATING_CAPABILITY_MATRIX.md` (evidence-checked capability records, levels 1–5; source `docs/capability_matrix.json`; regenerate with `python scripts/gen_capability_matrix.py`) and `docs/ESTIMATING_GAP_ROADMAP.md` (gap work packages) — **update the matrix record when a capability changes; never raise a status without its acceptance test**. `docs/DEVELOPMENT_AUDIT.md` (verified state), `docs/NEXT_STEPS.md` (roadmap), `docs/KNOWN_LIMITATIONS.md` (read before relying on output), `docs/GOVERNED_PARAMETERS.md`, `docs/ANALYSIS_REPORTS.md`, `docs/MTO_TEMPLATES.md`, `docs/SECURITY.md`, `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`, `docs/PROJECT_WORKSPACES.md`, `docs/RATE_UPDATE_WORKFLOW.md`, `docs/KSA_DATA_SOURCES.md`, `docs/RATE_PROVENANCE.md`, `docs/ASSUMPTIONS_POLICY.md`, `docs/APPROVAL_WORKFLOW.md`, `docs/EXCEL_WORKBOOK_GUIDE.md`, `docs/TESTING.md`, `README.md`.
