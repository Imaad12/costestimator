---
name: project-indexer
description: Inventory and text-extract a project's documents into `2. AI Context/` (versioned, non-authoritative) and report what needs human review. Use after documents are added or changed, or when asked what documents a project has.
allowed-tools: Read, Glob, Grep, Bash(python -m app.cli *)
argument-hint: <PRJ-ID>
---

# project-indexer

## Purpose
Create/refresh the searchable document index (`project_documents`, `project_index.json`, `project_summary.md`, `extracts/docNNNNN_vN.txt`) without touching originals.

## When to use
New tender documents/addenda/revisions arrived; before requirements extraction; when a source file changed (flagged *Source changed - review*).

## Required context and inputs
Project ID; documents already placed in the workspace by a human. Authenticated author user.

## Read first (exact modules, data files, docs)
- `projects/<id>/CLAUDE.md`
- `docs/PROJECT_WORKSPACES.md` (indexer section)
- `app/services/project_index.py`

## Steps
1. Run `python -m app.cli project index <PRJ-ID>`; read the printed counts (new/changed/unchanged/missing/extracted/not_extracted/errors).
2. Open `projects/<id>/2. AI Context/project_summary.md`: list files *Not text-extracted* (CAD/BIM, scanned PDFs, unsupported types) and *Extraction error* with the stored reason.
3. For each *Source changed - review* or *Missing* document, tell the human which file and why; they decide whether the new revision supersedes the old (use the UI *Mark reviewed* or `mark_document_reviewed`). Do not mark reviewed yourself on their behalf unless they explicitly ask you to act as their session user.
4. Use `python -m app.cli project search <id> "term"` to locate text; always open the **original** file to confirm any fact before relying on it.
5. Report revisions seen in file names as *observations*; never write them into the project's approved drawing/spec revision fields.

## Outputs and schemas
`2. AI Context/project_index.json` (schema `ksa-estimator/project-index/1`; per document: id, rel_path, file_name, file_type, size_bytes, modified_at, sha256, area, category, trade_hint, revision, extraction_status, extraction_error, extract_version, extract_path, text_chars, review_status), `project_summary.md`, `extracts/`.

## Validation checks
- `unchanged` equals the file count on an immediate re-run (idempotent).
- A changed file produced a *new* extract version and the old extract file still exists.
- Every extraction failure has an `extraction_error` message; none is silently skipped.
- Originals' hashes unchanged.

## Approval requirements
None for indexing. Marking a document *Reviewed* is a human acknowledgement (informational; it approves no estimating data).

## Failure handling
- Parser missing/corrupt/encrypted/scanned PDF → record as indexed but not text-extracted (the tool does this); tell the user an OCR or a PDF plot is needed — do not paraphrase the drawing.
- File > 150 MB → indexed without hash/extract; report.
- Workspace missing → run `project refresh <id>` first.

## Explicitly prohibited
- Measuring, inferring or generating quantities, or editing a quantity without an approved change request.
- Inventing prices, wages, productivity, wastage, suppliers, FX/tax values or benchmarks; filling a missing value with a default or a guess.
- Calling an approve/reject/publish function as, or on behalf of, a human; writing `approvals`, status or `audit_log` rows directly; weakening `app/approvals/policy.py` or a reconciliation rule.
- Editing or overwriting original files in `1. Tender Documents/` or any supplier-supplied original.
- Treating AI output, an extract, a summary or an index as authoritative over the original document.
- Summarising drawings/specifications from memory or from partial extracts as if complete.
- Deleting old extract versions.

_Skills orchestrate application functions; they never bypass validation or server-side approvals. AI output remains a suggestion until an authorised human accepts it._
