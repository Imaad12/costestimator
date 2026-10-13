---
name: procurement-rfq
description: Detect procurement needs from the estimate and prepare RFQ packages (English/Arabic drafts, XLSX/DOCX) for manual issue. Use when rates are missing/expired or when an RFQ is requested.
allowed-tools: Read, Glob, Grep, Bash(python -m app.cli *)
argument-hint: <PRJ-ID> [package]
---

# procurement-rfq

## Purpose
Turn unpriced/expired/low-confidence lines into clear RFQ packages. The application never sends email and never invents supplier contacts.

## When to use
Estimate shows unpriced lines; rates expired; a specification changed; a human asks for an RFQ.

## Required context and inputs
Project ID; supplier ids from the supplier directory (human-created); response deadline from the human; specifications from the BOQ/assemblies/documents.

## Read first (exact modules, data files, docs)
- `docs/PROCUREMENT_GUIDE.md`
- `app/procurement/needs.py`
- `app/procurement/rfq.py`
- `templates/rfq_template.xlsx`
- `projects/<id>/CLAUDE.md`

## Steps
1. Run `detect_needs` (UI *Procurement & RFQs* or POST `/api/actions/detect_needs`). Review the register: reason code, exposure (indicative only when an unapproved rate exists; otherwise 'unknown').
2. Check each item's specification text against the tender documents (use project search + originals). Add missing specification via the procurement item update (human-confirmed).
3. Create RFQs per package (`create_rfq`; language en/ar; deadline). Export XLSX/DOCX or copy the email text; the Arabic text is a draft for human review.
4. Give the human the files from `6. Procurement & Quotations/` to issue manually; they press *Mark issued* (`mark_rfq_issued`) after sending.
5. When quotes return use subcontractor-quote-analysis.

## Outputs and schemas
RFQ files `RFQ-…xlsx/docx` in `6. Procurement & Quotations/`; DB `procurement_packages`, `procurement_items`, `rfqs`, `rfq_items`. Optional `rfq_cover_note_<package>.md`: scope summary, clarifications, deadline — all from recorded data.

## Validation checks
- Every RFQ line has description, specification (or an explicit 'to be confirmed' note), quantity and unit from the BOQ/takeoff; no price or budget appears in the RFQ.
- No supplier address/email appears unless recorded by a human.
- `python -m pytest tests/procurement -q` passes if procurement code changed.

## Approval requirements
Creating RFQs needs an author role; issuing is a manual human act. Supplier qualification (`qualify_supplier`) and later selection are human approvals.

## Failure handling
- No supplier recorded → leave the supplier blank; ask the human to add one (`create_supplier`).
- Missing specification → raise a clarification or ask the estimator; never write one from memory.

## Explicitly prohibited
- Measuring, inferring or generating quantities, or editing a quantity without an approved change request.
- Inventing prices, wages, productivity, wastage, suppliers, FX/tax values or benchmarks; filling a missing value with a default or a guess.
- Calling an approve/reject/publish function as, or on behalf of, a human; writing `approvals`, status or `audit_log` rows directly; weakening `app/approvals/policy.py` or a reconciliation rule.
- Editing or overwriting original files in `1. Tender Documents/` or any supplier-supplied original.
- Treating AI output, an extract, a summary or an index as authoritative over the original document.
- Sending email or contacting suppliers; disclosing the estimate's internal rates or budget in an RFQ.

_Skills orchestrate application functions; they never bypass validation or server-side approvals. AI output remains a suggestion until an authorised human accepts it._
