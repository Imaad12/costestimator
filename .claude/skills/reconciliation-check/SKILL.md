---
name: reconciliation-check
description: Run and interpret the reconciliation (cost vs schedule vs offer vs assumptions vs procurement) and prepare a human-readable remediation list. Use before freezing/approving an estimate or when findings are asked about.
allowed-tools: Read, Glob, Grep, Bash(python -m app.cli *), Bash(python -m pytest *)
argument-hint: <PRJ-ID>
---

# reconciliation-check

## Purpose
Find and explain every discrepancy and the correct fix path; exceptions are human decisions governed by rule severity.

## When to use
Before `freeze_version`/approval/export; after rate or assumption changes; to explain a blocked approval.

## Required context and inputs
Project ID; authenticated user to run (`run_reconciliation` needs an author role).

## Read first (exact modules, data files, docs)
- `config/reconciliation_rules.json`
- `app/reconciliation/engine.py`
- `app/reconciliation/rules.py`
- `docs/APPROVAL_WORKFLOW.md` (final gate, exceptions)
- `tests/reconciliation/test_recon.py`

## Steps
1. Run `run_reconciliation` (UI *Reconciliation* or POST action). Note run id and `open_by_severity`.
2. Group findings by rule code and severity; for each give: what it means, entity, financial impact, the system place to fix it, and the role who can resolve it.
3. Distinguish *fix the data* (missing rate, unapproved assumption, expired quotation, unmapped item, totals mismatch) from *accept an exception* (only where the rule allows; reason ≥ 10 characters; High needs a Commercial Approver; Critical never).
4. After humans fix items, re-run until no blocking-severity finding remains (blocking = Critical + High unless configured otherwise).
5. Write the remediation list (schema below).

## Outputs and schemas
`9. Reconciliation & Approvals/reconciliation_remediation_<run>.md`: `## Run`, `## Blocking findings` (table: id, rule, severity, entity, impact, fix, role), `## Non-blocking`, `## Exceptions proposed (for human decision)`. The engine also writes `reconciliation_report_*.xlsx` to the same folder when exported.

## Validation checks
- Counts in the note equal the engine's counts for that run id.
- A fresh run was executed after any fix (fingerprint-keyed exceptions only apply to unchanged findings).
- No severity or tolerance was edited to make findings disappear (`config/reconciliation_rules.json` untouched unless the human asked and approved).

## Approval requirements
Exceptions: roles per rule (Estimator/Procurement for low, Commercial Approver for High, never Critical). Final approval and export are separate human approvals.

## Failure handling
- Run errors → report the exception text; do not hand-edit findings.
- Stale findings → re-run.
- Blocking findings remain → state that final approval/export is blocked.

## Explicitly prohibited
- Measuring, inferring or generating quantities, or editing a quantity without an approved change request.
- Inventing prices, wages, productivity, wastage, suppliers, FX/tax values or benchmarks; filling a missing value with a default or a guess.
- Calling an approve/reject/publish function as, or on behalf of, a human; writing `approvals`, status or `audit_log` rows directly; weakening `app/approvals/policy.py` or a reconciliation rule.
- Editing or overwriting original files in `1. Tender Documents/` or any supplier-supplied original.
- Treating AI output, an extract, a summary or an index as authoritative over the original document.
- Lowering a rule's severity, widening tolerances or accepting exceptions on behalf of a human.

_Skills orchestrate application functions; they never bypass validation or server-side approvals. AI output remains a suggestion until an authorised human accepts it._
