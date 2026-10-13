---
name: requirements-extraction
description: Extract contractual/technical requirements from indexed tender documents into a cited requirements register and DRAFT clarifications/scope entries for human review. Use after indexing tender documents.
allowed-tools: Read, Glob, Grep, Bash(python -m app.cli *)
argument-hint: <PRJ-ID> [document or trade]
---

# requirements-extraction

## Purpose
Turn specification/ITT text into a traceable list of requirements, assumptions to confirm, exclusions and clarification questions — each with a verbatim quote and location — so humans can price correctly. It produces proposals only.

## When to use
Tender documents are indexed and the estimator needs a requirements/clarification list, or an addendum arrived.

## Required context and inputs
Project ID with indexed documents; optional scope (a document, a trade). Original documents are read directly where extracts are partial.

## Read first (exact modules, data files, docs)
- `projects/<id>/CLAUDE.md`
- `projects/<id>/2. AI Context/project_summary.md`
- `docs/ASSUMPTIONS_POLICY.md`
- `app/services/registers.py`
- `app/ai/service.py` (`ai_draft_clarifications`, `ai_suggest_scope_gaps`, `deterministic_scope_checks`)
- `docs/APPROVAL_WORKFLOW.md` (AI section)

## Steps
1. List candidate sources with `project search <id> "term"` (e.g. 'shall', 'exclude', 'provisional', 'warranty', 'testing', 'approved make') and open each ORIGINAL file at the cited place; extracts may be partial or mis-ordered.
2. For each requirement record: verbatim quote (short), file, page/section, category (scope / technical / commercial / programme / compliance / exclusion), trade/cost code, and *proposed action* (price it / raise clarification / add exclusion or qualification / note assumption). Mark anything unclear as a question, not a requirement.
3. Write `projects/<id>/4. Clarifications & Assumptions/requirements_register.md` and a JSON twin (schema below).
4. Offer the human drafts: clarification questions (`add_clarification` – status Open) and scope entries (`add_scope_entry` – status Draft, human approves). Create them only when the user asks you to act as their authenticated session; otherwise list them.
5. Run `scope_checks` (deterministic) if the BOQ exists and report findings as suggestions (`ai_suggestions`, Pending Review).

## Outputs and schemas
`requirements_register.md` + `requirements_register.json`: array of `{id, quote, source_file, location, category, trade, cost_code, proposed_action, confidence_note, status: "Proposed"}`. `confidence_note` is free text (e.g. 'scanned page, partial extract') — never a numeric score presented as fact.

## Validation checks
- Every item has a source file and location and its quote is found verbatim in that original (grep it).
- No item states a quantity, price or rate that is not literally in the source.
- Items from extracts that could not be verified against the original are marked 'unverified'.

## Approval requirements
Clarification resolution and scope entries require human approval (`clarification`, `exclusion`); AI/heuristic suggestions need human acceptance (`accept_suggestion`). Nothing here becomes a decision on its own.

## Failure handling
- Scanned/CAD-only documents → say so; request text-searchable PDFs; do not infer content.
- Conflicting clauses → record both with locations as a clarification candidate; do not choose.
- Document Arabic/English mismatch → record both texts; do not translate as authoritative.

## Explicitly prohibited
- Measuring, inferring or generating quantities, or editing a quantity without an approved change request.
- Inventing prices, wages, productivity, wastage, suppliers, FX/tax values or benchmarks; filling a missing value with a default or a guess.
- Calling an approve/reject/publish function as, or on behalf of, a human; writing `approvals`, status or `audit_log` rows directly; weakening `app/approvals/policy.py` or a reconciliation rule.
- Editing or overwriting original files in `1. Tender Documents/` or any supplier-supplied original.
- Treating AI output, an extract, a summary or an index as authoritative over the original document.
- Converting requirements into quantities or rates.
- Marking a clarification resolved or a scope entry approved.

_Skills orchestrate application functions; they never bypass validation or server-side approvals. AI output remains a suggestion until an authorised human accepts it._
