---
name: governed-inputs-and-analysis
description: Record company-supplied numbers (productivity factors, hire terms, calendar, escalation, payment terms, benchmark ranges, take-off factors, statutory rules ...) as governed parameters with their sources, then run the read-only analyses (roll-up, programme, loading, man-hours, risk, cash flow, earned value ...). Use when the user supplies factors/terms/ranges or asks for an analysis or a Basis of Estimate.
allowed-tools: Read, Glob, Grep, Bash(python -m app.cli *), Bash(python -m pytest *)
argument-hint: <PRJ-ID> [report name]
---

# governed-inputs-and-analysis

## Purpose
Turn evidence the human provides into validated, versioned, approvable parameters - and use them - without ever supplying a value yourself. Analyses and proposals inform decisions; people approve.

## When to use
The user gives you factors, rates of recovery, terms, ranges or a calendar from their records; they ask for a loading histogram, man-hours, risk analysis, cash flow, escalation, earned value, benchmark check, method comparison or a Basis of Estimate.

## Required context and inputs
Project ID; the user's evidence for every number (document/record/contract clause) - without a source the parameter is refused; an authenticated author user. If a number is missing, **ask**; never fill it.

## Read first (exact modules, data files, docs)
- `CLAUDE.md` (root)
- `docs/GOVERNED_PARAMETERS.md`
- `docs/ANALYSIS_REPORTS.md`
- `docs/MTO_TEMPLATES.md`
- `app/estimators/param_kinds.py`
- `app/reporting/registry.py`

## Steps
1. List kinds: `python -m app.cli param kinds`; pick the kind that matches the user's evidence; read its field skeleton (names only).
2. Propose with the user's exact figures: `python -m app.cli param propose KIND CODE '<json>' --project <PRJ> --source "<where the number comes from>" [--submit]`. Validation errors are returned verbatim - fix the input with the user, do not adjust numbers to pass.
3. Tell the human which role approves the kind (see the doc table) and that only *Approved* values enter a strict estimate. Do not call approve yourself unless the user explicitly asks you to act as their own signed-in session.
4. Run reports: `python -m app.cli report <PRJ> <name> [--param k=v] [--save]`; read the `note`, `notes` and `estimate_state` fields and repeat them to the user. A report that stops for a missing input is correct behaviour - say what is missing.
5. For take-off derivation: `mto preview` first, confirm the driver quantity is the **user's measured figure** (or the BOQ quantity), then `mto apply`; remind the user that the item is now a Pending Review pricing decision.
6. For proposals (`propose_*`): they create Draft indirect items; tell the user to review and submit/approve them in *Indirects & commercials*.
7. Generate the Basis of Estimate with the `generate_boe` action and list the six sections the estimator must still write.

## Outputs and schemas
`governed_params` rows (Draft/Pending), saved `analysis_runs` (immutable, not approvals), Draft indirect items from proposals, `5. Estimate & Cost Build-Up/basis_of_estimate/BoE_*.md/.docx`.

## Validation checks
- Every proposed parameter has a source quoted from the user; none was derived, defaulted or rounded by you.
- A report's `tie_out` fields are true where present (roll-up, loading, man-hours).
- After running proposals the estimate totals are unchanged until a human approves.
- `python -m pytest tests/unit/test_governed_params.py -q` passes if you touched parameter code.

## Approval requirements
Parameters: the roles listed per kind in `docs/GOVERNED_PARAMETERS.md` (AI never). Analyses need no approval and approve nothing. Indirect proposals and pricing decisions use the existing approvals.

## Failure handling
- `PARAM_SOURCE` / `PARAM_FIELD` -> ask the user for the missing evidence/field.
- `CALENDAR_REQUIRED`, `TERMS_NONE`, `ESC_NONE`, `RISK_NONE`, `BASELINE_NONE` -> the report needs an approved input: explain which and stop.
- `MTO_FACTORS_MISSING` -> list the slots without an approved factor; do not skip slots unless the user decides to (explicit skip is recorded).

## Explicitly prohibited
- Measuring, inferring or generating quantities, or editing a quantity without an approved change request.
- Inventing prices, wages, productivity, wastage, suppliers, FX/tax values or benchmarks; filling a missing value with a default or a guess.
- Calling an approve/reject/publish function as, or on behalf of, a human; writing `approvals`, status or `audit_log` rows directly; weakening `app/approvals/policy.py` or a reconciliation rule.
- Editing or overwriting original files in `1. Tender Documents/` or any supplier-supplied original.
- Treating AI output, an extract, a summary or an index as authoritative over the original document.
- Proposing a factor, percentage, range, rate or hours figure from your own knowledge or 'typical' practice.
- Using the output of an analysis as if it were an approved estimate or adding it to the price without the normal approval.
- Stating that a client's or owner's standards are met.

_Skills orchestrate application functions; they never bypass validation or server-side approvals. AI output remains a suggestion until an authorised human accepts it._
