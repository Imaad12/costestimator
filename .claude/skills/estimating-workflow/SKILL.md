---
name: estimating-workflow
description: Run and interpret the end-to-end estimating workflow for a project: mapping → build-up → procurement needs → indirects/commercial → reconciliation → versions → gated export, stating what is blocked and which human must act. Use when asked 'where is this estimate', 'what blocks submission', or to progress a project.
allowed-tools: Read, Glob, Grep, Bash(python -m app.cli *), Bash(python -m pytest *)
argument-hint: <PRJ-ID>
---

# estimating-workflow

## Purpose
Give an accurate, evidence-based status and next human actions; run deterministic steps the user's role permits; never push anything past a gate.

## When to use
Progressing or reviewing a project; explaining Preliminary state; before a submission.

## Required context and inputs
Project ID; the user's authenticated session for any write. For read-only status, only the database.

## Read first (exact modules, data files, docs)
- `projects/<id>/CLAUDE.md`
- `docs/ESTIMATING_METHODOLOGY.md`
- `docs/APPROVAL_WORKFLOW.md`
- `docs/USER_GUIDE.md` (walkthrough)
- `app/estimators/estimate.py` (`_blockers`)
- `app/reporting/completeness.py`

## Steps
1. Read status: UI *Completeness* tab or `app.reporting.completeness.project_completeness`; note Blocked/Open rows and the estimate state (Complete / Complete with Provisional Inputs / Preliminary — Incomplete).
2. Missing rates: run `detect_needs` (procurement-rfq skill). An approved real rate is required per line; explain that the global library has no approved real rates until imported (rate-update-review skill). Provisional (project-scoped) approvals need a human reason.
3. Assumptions: list those in use but unapproved (Assumptions tab / dashboard); humans approve.
4. Indirects/duration/policy/tax: propose via the UI/actions; Commercial Approver approves policy and tax category (tax needs verification evidence).
5. Run reconciliation (`run_reconciliation`); review findings by severity; exceptions only where the rule allows and with a documented human reason; Critical never waived.
6. Freeze a version (`freeze_version`; a snapshot is stored), submit, Commercial Approver approves; offer approved; tender export approved; only then `export_submission`. Preliminary outputs are always available and watermarked.
7. Report a table: step · state · blocking item · responsible role.

## Outputs and schemas
Status report (chat or `9. Reconciliation & Approvals/status_<date>.md`): `## State`, `## Blocking items` (table: item, why, role who can resolve, where in UI), `## Open items`, `## Next three actions`. Frozen versions: DB + `5. …/versions/*_inputs_snapshot.json`.

## Validation checks
- Every blocking item cites the exact blocker string or finding id from the system.
- Numbers quoted come from the engine/UI, not mental arithmetic.
- After freezing: `python -m app.cli project verify-snapshot <version_id>` shows ok.

## Approval requirements
Estimate final approval, offer approval and tender export approval are Commercial Approver/Administrator decisions; supplier selection and rate approval are Procurement/Commercial decisions. Never perform them for a human.

## Failure handling
- `STALE_VERSION` → inputs changed; freeze a new version.
- `RECON_BLOCKED` → resolve findings; do not lower severities.
- `ESTIMATE_PRELIMINARY` → unresolved inputs remain; list them.

## Explicitly prohibited
- Measuring, inferring or generating quantities, or editing a quantity without an approved change request.
- Inventing prices, wages, productivity, wastage, suppliers, FX/tax values or benchmarks; filling a missing value with a default or a guess.
- Calling an approve/reject/publish function as, or on behalf of, a human; writing `approvals`, status or `audit_log` rows directly; weakening `app/approvals/policy.py` or a reconciliation rule.
- Editing or overwriting original files in `1. Tender Documents/` or any supplier-supplied original.
- Treating AI output, an extract, a summary or an index as authoritative over the original document.
- Using `include_unapproved` (preliminary) numbers as a tender price.
- Exporting a submission-ready package without the recorded approvals.

_Skills orchestrate application functions; they never bypass validation or server-side approvals. AI output remains a suggestion until an authorised human accepts it._
