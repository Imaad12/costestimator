---
name: gantt-duration-estimation
description: Build a CPM programme from human-supplied tasks and derive a project duration proposal for indirect costs. Use when duration/time-related indirects must be estimated.
allowed-tools: Read, Glob, Grep, Bash(python -m app.cli *), Bash(python -m pytest *)
argument-hint: <PRJ-ID>
---

# gantt-duration-estimation

## Purpose
Compute a transparent duration from tasks, durations and dependencies the estimator provides, and propose it (never approve it) so time-based indirects can resolve.

## When to use
Indirects use per-day/week/month methods; programme changed; a duration is missing or unapproved.

## Required context and inputs
Task list with id, name, duration (working days), predecessors — **given by the estimator** with the basis for each duration; working-calendar assumptions (`calendar.working_days_per_week/month`, approved by a human). Optional labour-hours-derived cross-check.

## Read first (exact modules, data files, docs)
- `app/estimators/duration.py`
- `app/services/indirects.py` (`set_tasks`, `propose_duration_from_schedule`, `propose_duration`)
- `docs/ESTIMATING_METHODOLOGY.md` (duration/indirects)
- `docs/ASSUMPTIONS_POLICY.md`
- `tests/unit/test_indirect_duration.py`

## Steps
1. Collect the tasks and their basis from the human; record in `7. Programme & Indirects/programme_inputs.md` (schema below). Do not derive durations from drawings or from 'typical' productivities.
2. Check calendars: working days/week and per month must be approved assumptions; otherwise the conversion to months is unresolved — report it.
3. Load tasks (`indirects.set_tasks`) and run CPM (`duration.cpm`) via `propose_duration_from_schedule`; inspect critical path, total working days, cycle errors.
4. Optionally cross-check with `labour_derived_months` using hours from the estimate and a crew size the human gives; show both and the difference.
5. Propose the duration (`propose_duration` with source_type and basis note); the human approves (`approve_duration`). Time-based indirects remain unresolved until then.

## Outputs and schemas
`7. Programme & Indirects/programme_inputs.md`: table `id | task | duration (working days) | predecessors | basis (who/what)`; `programme_result.md`: critical path, total days, months, calendar assumptions used; DB `schedule_tasks`, `project_durations` (Pending Review).

## Validation checks
- No cycles; every predecessor id exists; total = longest path (hand-check one path).
- Months conversion uses the approved calendar assumption values quoted in the note.
- `python -m pytest tests/unit/test_indirect_duration.py -q` passes.

## Approval requirements
Project duration approval: Estimator, Commercial Approver or Administrator (`project_duration`); an AI-proposed duration needs a reviewer comment.

## Failure handling
- Cycle detected → list the cycle; ask the human to fix dependencies.
- Calendar assumption unapproved → duration stays unresolved; say which assumption.
- No task data → stop and ask; do not fabricate a programme.

## Explicitly prohibited
- Measuring, inferring or generating quantities, or editing a quantity without an approved change request.
- Inventing prices, wages, productivity, wastage, suppliers, FX/tax values or benchmarks; filling a missing value with a default or a guess.
- Calling an approve/reject/publish function as, or on behalf of, a human; writing `approvals`, status or `audit_log` rows directly; weakening `app/approvals/policy.py` or a reconciliation rule.
- Editing or overwriting original files in `1. Tender Documents/` or any supplier-supplied original.
- Treating AI output, an extract, a summary or an index as authoritative over the original document.
- Inventing task durations or productivity; approving the duration.

_Skills orchestrate application functions; they never bypass validation or server-side approvals. AI output remains a suggestion until an authorised human accepts it._
