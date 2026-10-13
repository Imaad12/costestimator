---
name: subcontractor-quote-analysis
description: Analyse subcontractor/supplier quotations for a package: completeness, scope gaps, exclusions, tax/delivery basis, normalisation and like-for-like comparison, producing a recommendation for the human reviewer. Use when quotations are received.
allowed-tools: Read, Glob, Grep, Bash(python -m app.cli *)
argument-hint: <PRJ-ID> <package id>
---

# subcontractor-quote-analysis

## Purpose
Make levelling transparent: quoted prices stay as quoted; normalised/comparison values are separate; every difference is explained; selection remains a human decision.

## When to use
Quotes arrive for an RFQ package; before a supplier selection; to check an expired/low-confidence quote.

## Required context and inputs
Quotation records or files in `6. Procurement & Quotations/`; the package id; the specification. Quote text may be pasted for optional AI extraction (review-only).

## Read first (exact modules, data files, docs)
- `docs/PROCUREMENT_GUIDE.md`
- `app/procurement/quotes.py`
- `app/procurement/leveling.py` (`level_package`)
- `app/procurement/selection.py`
- `app/ai/service.py` (`ai_extract_quotation`, `spec_diff`)
- `docs/APPROVAL_WORKFLOW.md`

## Steps
1. Ensure each quotation is entered against the project/package (`create_quotation`, `add_quote_line` or `import_quotation_lines`) with the supplier's own figures, validity, currency, tax treatment, delivery/unloading, exclusions and deviations — copied from the document, blanks left blank.
2. A Procurement Reviewer verifies each quotation against the original (`approve_quotation`); AI-extracted data needs explicit verification.
3. Level: UI *Compare quotations* or `leveling.level_package`. Read coverage, missing items, tax/FX/unit normalisation, `spec_differences`, expired quotes, lowest like-for-like.
4. Build the analysis note (schema below): scope coverage matrix, exclusions that shift cost to the contractor, deviations, validity/lead time, payment terms, price per normalised unit, risks.
5. Recommend (not decide): preferred supplier(s) with reasons; if not lowest like-for-like, draft the justification text for `propose_selection`. Adjustments (`add_adjustment`) are proposals until approved.
6. After human approval of the selection, `publish_rates` creates *Pending Review* rates; each still needs rate approval.

## Outputs and schemas
`6. Procurement & Quotations/quote_analysis_<package>_<date>.md`: `## Quotations received`, `## Coverage matrix`, `## Exclusions & deviations`, `## Normalised comparison (quoted vs normalised, shown separately)`, `## Recommendation & rationale`, `## Open questions to suppliers`.

## Validation checks
- Quoted totals equal the supplier documents; normalised totals reproduce from stated FX/tax/unit steps.
- Every missing item is listed, not priced.
- No supplier contact or price is invented; no email is sent.

## Approval requirements
Quotation verification, supplier selection (value threshold may require a Commercial Approver), adjustments and rate publication are human approvals (`quotation`, `supplier_selection`, `rate`).

## Failure handling
- Quote expired → mark/flag; request re-validation; exclude from selection.
- Foreign currency without approved FX → leave unnormalised and say why.
- Non-comparable scope → do not force a ranking; list the gaps.

## Explicitly prohibited
- Measuring, inferring or generating quantities, or editing a quantity without an approved change request.
- Inventing prices, wages, productivity, wastage, suppliers, FX/tax values or benchmarks; filling a missing value with a default or a guess.
- Calling an approve/reject/publish function as, or on behalf of, a human; writing `approvals`, status or `audit_log` rows directly; weakening `app/approvals/policy.py` or a reconciliation rule.
- Editing or overwriting original files in `1. Tender Documents/` or any supplier-supplied original.
- Treating AI output, an extract, a summary or an index as authoritative over the original document.
- Selecting a supplier; waiving a not-like-for-like difference; averaging quotes into a rate.

_Skills orchestrate application functions; they never bypass validation or server-side approvals. AI output remains a suggestion until an authorised human accepts it._
