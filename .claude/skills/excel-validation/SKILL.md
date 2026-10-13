---
name: excel-validation
description: Generate, validate and (with LibreOffice) recalculate the master/standalone workbooks and check round-trip imports. Use when workbooks are generated, changed, received back from a user, or when `app/excel/spec.py` changes.
allowed-tools: Read, Glob, Grep, Bash(python -m app.cli *), Bash(python -m pytest *), Bash(soffice *)
argument-hint: <workbook file> [PRJ-ID]
---

# excel-validation

## Purpose
Prove workbooks are structurally sound, formulas compute, and imports create only drafts — and state clearly what was not tested (Microsoft Excel).

## When to use
After changing `app/excel/*`; before sending a workbook; when a user returns an edited workbook; after regenerating templates.

## Required context and inputs
A workbook path; optionally a project id to compare with the database. LibreOffice (`soffice`) for recalculation.

## Read first (exact modules, data files, docs)
- `docs/EXCEL_WORKBOOK_GUIDE.md`
- `docs/EXCEL_DATA_DICTIONARY.md`
- `app/excel/spec.py`
- `app/excel/roundtrip.py` (`validate_workbook`)
- `app/excel/recalc.py`
- `tests/excel/test_workbooks.py`

## Steps
1. Regenerate templates if the spec changed: `python -m app.cli templates` then `python scripts/gen_docs.py`.
2. Export a populated master: `python -m app.cli export-workbook <PRJ-ID> --out <file>` (UI download writes to `5. Estimate & Cost Build-Up/`).
3. Verify: `python -m app.cli verify-workbook <file> --project <PRJ-ID>` → read `structure_ok`, `missing_sheets`, `header_problems`, `overwritten_formulas`, `stale`, `recalculated`, `formula_errors`, `mismatches`, `formulas`.
4. For a user-edited file import via the UI/API round-trip (`import_master`): only drafts/proposals are created; status columns are ignored. Review the import report.
5. State what was verified: LibreOffice recalculation yes/no; Microsoft Excel not available unless you actually ran it.
6. Run `python -m pytest tests/excel -q`.

## Outputs and schemas
Verification JSON from the CLI (paste into the report) and optional `5. Estimate & Cost Build-Up/workbook_verification_<date>.md`: file, project, sheets, formula count, errors, mismatches, stale flag, tool versions, limitations.

## Validation checks
- 27 required sheets present, keys/headers unchanged, no formula cell replaced by a constant, `formula_errors` empty, `mismatches` empty, workbook fingerprint equals the current estimate (else *stale*).

## Approval requirements
None for validation. Importing edits creates proposals; approvals still happen in the application.

## Failure handling
- `soffice` missing/timeouts → report recalculation as not performed (`recalculated: false`); do not claim success.
- `overwritten_formulas` non-empty → ask the user to restore formulas; do not import.
- `stale` → regenerate from the current database.

## Explicitly prohibited
- Measuring, inferring or generating quantities, or editing a quantity without an approved change request.
- Inventing prices, wages, productivity, wastage, suppliers, FX/tax values or benchmarks; filling a missing value with a default or a guess.
- Calling an approve/reject/publish function as, or on behalf of, a human; writing `approvals`, status or `audit_log` rows directly; weakening `app/approvals/policy.py` or a reconciliation rule.
- Editing or overwriting original files in `1. Tender Documents/` or any supplier-supplied original.
- Treating AI output, an extract, a summary or an index as authoritative over the original document.
- Editing formulas in an exported workbook to 'fix' mismatches (fix the engine/spec instead); claiming Excel compatibility beyond what was tested.

_Skills orchestrate application functions; they never bypass validation or server-side approvals. AI output remains a suggestion until an authorised human accepts it._
