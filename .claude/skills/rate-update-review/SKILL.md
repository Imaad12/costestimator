---
name: rate-update-review
description: Review the rate-candidate queue with a human: verify evidence, basis (VAT/delivery/unit/currency), matching and normalisation, then guide approve-for-publication → publish → rate approval. Use when candidates are pending or after an import/refresh.
allowed-tools: Read, Glob, Grep, Bash(python -m app.cli *)
argument-hint: [queue name | candidate ref]
disable-model-invocation: true
---

# rate-update-review

## Purpose
Make human review fast and rigorous. The skill prepares evidence and recommendations; the decisions are made by authorised humans through the application.

## When to use
After `rates import`, `sources refresh`, or a web-watchlist run; weekly queue review; before relying on any new rate.

## Required context and inputs
Queue/candidate refs; the reviewing user's role; the original source (open the URL/file yourself to confirm).

## Read first (exact modules, data files, docs)
- `docs/RATE_UPDATE_WORKFLOW.md`
- `docs/RATE_PROVENANCE.md`
- `app/rate_updates/candidates.py` (`publishable_price`, `classify_queue`)
- `app/rate_updates/normalise.py`
- `docs/APPROVAL_WORKFLOW.md`

## Steps
1. List: `python -m app.cli rates pending [--queue Conflicting]`; open `/rates/updates/<RC-ref>` for evidence and flags.
2. For each candidate verify against the ORIGINAL source: price, currency, unit, VAT statement, delivery/installation, date/validity, geography, specification equivalence to the resource. Note contradictions and stale dates.
3. Matching: if `resource_id` is empty, check the suggestion (`suggested_resource_id`) against the resource specification; only a human sets it (`edit_rate_candidate`).
4. Normalisation: confirm each step (FX row approved and date-valid; unit factor physical; VAT from approved category). If inputs are missing, say which approvals/records a human must create first (e.g. approve an FX rate).
5. Prepare a recommendation per candidate: approve / needs verification (what to ask) / reject (why). Conflicting queue: compare both sources and recommend one with reasons.
6. Present to the human. They decide with `rates review <ref> approve|reject|needs_verification --comment …` (needs Procurement Reviewer/Commercial Approver/Administrator). Then `rates publish <ref>` (creates a *Pending Review* version) and a human approves the rate (`approve_rate`).
7. After approval: confirm the old version is `Superseded` (kept), frozen estimates are unchanged (`project verify-snapshot`), and re-run reconciliation on affected projects.

## Outputs and schemas
`rate_review_<date>.md` (e.g. in `9. Reconciliation & Approvals/` of the relevant project or `var/`): table `ref | resource | original price/unit/currency | source | basis | normalisation | recommendation | reason`. DB changes only through the human actions above.

## Validation checks
- Recommended 'approve' items pass `publishable_price` (price, resource, VAT basis, price kind, complete normalisation).
- Original price in the candidate equals the source; the evidence snippet matches.
- No candidate is approved for a price kind of Promotional/Quote required/Specification only.

## Approval requirements
Candidate review: Procurement Reviewer / Commercial Approver / Administrator (`rate_candidate`). Rate approval: same roles (`rate`). Estimators may only propose, edit matching fields, publish approved candidates, or approve provisionally for one project with a reason. AI: never.

## Failure handling
- `NOT_PUBLISHABLE` → show the listed reasons; fix the data (human) or reject.
- `SELF_APPROVAL_BLOCKED` → another reviewer must act.
- Source unreachable now → keep 'Needs verification'; do not approve from memory.

## Explicitly prohibited
- Measuring, inferring or generating quantities, or editing a quantity without an approved change request.
- Inventing prices, wages, productivity, wastage, suppliers, FX/tax values or benchmarks; filling a missing value with a default or a guess.
- Calling an approve/reject/publish function as, or on behalf of, a human; writing `approvals`, status or `audit_log` rows directly; weakening `app/approvals/policy.py` or a reconciliation rule.
- Editing or overwriting original files in `1. Tender Documents/` or any supplier-supplied original.
- Treating AI output, an extract, a summary or an index as authoritative over the original document.
- Running `rates review … approve` or `approve_rate` yourself without the human reviewer explicitly acting as themselves.
- Changing original price/currency/source fields; bulk-approving a queue.

_Skills orchestrate application functions; they never bypass validation or server-side approvals. AI output remains a suggestion until an authorised human accepts it._
