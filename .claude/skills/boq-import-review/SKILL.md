---
name: boq-import-review
description: Import a client BOQ/takeoff file and review the import report (rejected rows, ambiguous units, duplicates, change requests) for the human. Use when a BOQ or revised BOQ arrives.
allowed-tools: Read, Glob, Grep, Bash(python -m app.cli *), Bash(python -m pytest *)
argument-hint: <PRJ-ID> <boq file>
---

# boq-import-review

## Purpose
Bring human-measured quantities into the project exactly as supplied, surface every problem, and leave all decisions (unit choices, quantity changes, mapping) to humans.

## When to use
First BOQ import; BOQ revision/re-import; reviewing why items were rejected or flagged.

## Required context and inputs
Project ID, BOQ/takeoff file (CSV/XLSX; ideally from `templates/boq_import_template.xlsx`), revision label from the human. No quantity may come from anywhere but the file.

## Read first (exact modules, data files, docs)
- `docs/IMPORT_EXPORT_FORMATS.md`
- `app/imports/boq.py` (FIELDS, detect_header, parse_rows)
- `app/services/boq.py` (change requests, mapping)
- `docs/APPROVAL_WORKFLOW.md` (BOQ rows)
- `projects/<id>/CLAUDE.md`

## Steps
1. Keep the original in `1. Tender Documents/` (do not move it). Preview: UI *BOQ import → upload* or POST `/api/projects/<id>/boq/preview`; check the detected header row/column mapping; if required columns are unmapped, ask the human for the mapping.
2. Import: `python -m app.cli project import-boq <PRJ-ID> <file> --revision <label>` (or the UI with explicit mapping). A copy is stored in `3. BOQ & Takeoff/<sha10>_<name>`.
3. Read the summary: items new/unchanged, headings, blank rows, `rejected_rows` (code + reason), `needs_review`, `duplicates`, `change_requests`, `missing_in_revision`, `by_trade`.
4. Write the review note (schema below) listing every rejected row, ambiguous/unknown unit, duplicate code, zero/negative/text quantity and every pending change request with old→new values.
5. Tell the human what only they can decide: choose canonical units for ambiguous ones (e.g. `ton` → `t`), approve/reject quantity change requests, acknowledge duplicate flags with a reason (`acknowledge_issues`), correct the source file where wrong.
6. Do not map or price here; hand over to the estimating-workflow skill.

## Outputs and schemas
`3. BOQ & Takeoff/boq_import_review_<revision>.md` with sections `## Summary` (counts), `## Rejected rows` (row, code, reason), `## Unit decisions needed`, `## Duplicates`, `## Change requests (old → new)`, `## Questions for the client`. DB: `boq_imports`, `boq_items`, `boq_rejected_rows`, `change_requests` (Pending Review).

## Validation checks
- `items + headings + blank + rejected` accounts for every source row (`rows_read`).
- Original quantity text is retained per item; no quantity changed outside a change request.
- Re-importing the same file creates 0 new items and 0 change requests.
- `python -m pytest tests/imports -q` passes if importer code changed.

## Approval requirements
Importing needs an author role. Unit choices, quantity changes and mapping are approved by an Estimator/Commercial Approver/Administrator (`boq_unit`, `boq_quantity`, `boq_mapping`). This skill never approves them.

## Failure handling
- `MAPPING_INCOMPLETE`/`NO_HEADER` → show detected columns, ask for the mapping; never guess a column.
- `MALFORMED_FILE` → ask for a re-export; do not repair data by hand.
- Archived project → read-only; ask the Commercial Approver to unarchive.

## Explicitly prohibited
- Measuring, inferring or generating quantities, or editing a quantity without an approved change request.
- Inventing prices, wages, productivity, wastage, suppliers, FX/tax values or benchmarks; filling a missing value with a default or a guess.
- Calling an approve/reject/publish function as, or on behalf of, a human; writing `approvals`, status or `audit_log` rows directly; weakening `app/approvals/policy.py` or a reconciliation rule.
- Editing or overwriting original files in `1. Tender Documents/` or any supplier-supplied original.
- Treating AI output, an extract, a summary or an index as authoritative over the original document.
- Replacing 'TBA' or blank quantities with numbers; deleting rejected rows; merging duplicates silently.

_Skills orchestrate application functions; they never bypass validation or server-side approvals. AI output remains a suggestion until an authorised human accepts it._
