---
name: client-profile-loading
description: Load a client's or owner's estimating requirements from the controlled documents the user is authorised to provide into a versioned client profile, link it to a project and keep the compliance matrix honest. Use when the user supplies client estimating requirements, forms or procedures.
allowed-tools: Read, Glob, Grep, Bash(python -m app.cli *)
argument-hint: <PRJ-ID> <profile code>
---

# client-profile-loading

## Purpose
Make owner requirements traceable (document, revision, clause) and checkable, without claiming compliance with anything that has not been loaded and traced.

## When to use
The user provides an owner's estimating procedure, form list, code list or deliverable requirements and wants them checked on a project.

## Required context and inputs
The owner's documents as provided by the user (with their ids/revisions); the user's decision which requirements are mandatory. Do not rely on memory of any owner's standards.

## Read first (exact modules, data files, docs)
- `CLAUDE.md` (root)
- `app/services/profiles.py`
- `app/estimators/profile_checks.py`
- `docs/ESTIMATING_CAPABILITY_MATRIX.md` (records SAU-06, SAU-07)

## Steps
1. Read the provided documents; list each requirement with `req_id`, category, title and **source_ref** (document id + revision + clause). Skip anything you cannot trace to a clause.
2. Where a requirement can be tested on measured facts (see `profile_checks.FACT_HELP`), give `fact`, `op`, `value` exactly as the document states; otherwise leave it as a manual attestation.
3. Create the profile: `python -m app.cli profile create CODE "Name" --client "…" --requirements reqs.csv --documents @docs.json`; then `profile submit ID`; a Commercial Approver runs `profile approve ID`.
4. Link: `python -m app.cli profile link <PRJ> CODE`. Humans record evidence: `profile attest <PRJ> REQ Met "evidence ref"`.
5. Report with `report <PRJ> compliance`; repeat the generated statement verbatim, including its scope sentence.

## Outputs and schemas
`client_profiles`, `profile_requirements`, `project_profiles`, `profile_assessments`; the compliance matrix report.

## Validation checks
- Every requirement has a source_ref; mandatory flags match the user's instruction.
- No requirement was added from memory or inference.
- The compliance statement is quoted unchanged.

## Approval requirements
Profile approval: Commercial Approver / Administrator. Attestations: any author role, with evidence. AI never approves or attests.

## Failure handling
- `PROFILE_REQ`/`PROFILE_CHECK` -> fix the requirement with the user.
- Document not provided -> say that no requirements are loaded and that no statement can be made.

## Explicitly prohibited
- Measuring, inferring or generating quantities, or editing a quantity without an approved change request.
- Inventing prices, wages, productivity, wastage, suppliers, FX/tax values or benchmarks; filling a missing value with a default or a guess.
- Calling an approve/reject/publish function as, or on behalf of, a human; writing `approvals`, status or `audit_log` rows directly; weakening `app/approvals/policy.py` or a reconciliation rule.
- Editing or overwriting original files in `1. Tender Documents/` or any supplier-supplied original.
- Treating AI output, an extract, a summary or an index as authoritative over the original document.
- Writing requirements from general knowledge of any owner's standards (e.g. Saudi Aramco).
- Claiming or implying compliance with an owner's standards.

_Skills orchestrate application functions; they never bypass validation or server-side approvals. AI output remains a suggestion until an authorised human accepts it._
