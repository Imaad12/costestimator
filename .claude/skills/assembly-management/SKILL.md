---
name: assembly-management
description: Create, review and version assembly (unit-rate build-up) definitions safely: explicit waste and productivity bases, no double counting. Use when adding or editing assemblies or mapping items to them.
allowed-tools: Read, Glob, Grep, Bash(python -m app.cli *), Bash(python -m pytest *)
argument-hint: <assembly code or task>
---

# assembly-management

## Purpose
Keep assemblies structurally correct and auditable. Assemblies carry consumption factors, **not prices**; factors are supplied by humans with a source.

## When to use
Adding/changing an assembly; checking why an assembly cannot be approved; mapping BOQ items; importing assembly sheets.

## Required context and inputs
Assembly code, unit, cost code, line definitions (resource ids, factors, waste basis, productivity basis, crew) **provided or confirmed by the estimator with their source**. Resources must exist.

## Read first (exact modules, data files, docs)
- `docs/ESTIMATING_METHODOLOGY.md` (sections 2–3)
- `docs/ASSUMPTIONS_POLICY.md`
- `app/services/assemblies.py` (`validate`, `add_line`)
- `app/estimators/direct_cost.py`
- `data/assemblies/standard_assemblies.csv`
- `docs/EXTENDING.md`

## Steps
1. Search for an existing assembly first (`/assemblies?code=…` or `assemblies.list_assemblies`); prefer `clone_assembly`/`new_assembly_version` to creating duplicates.
2. Create: action `create_assembly`, then `add_assembly_line` per line. Material: `factor`, `factor_unit`, and exactly one waste approach (`factor_includes_waste` OR `waste_basis` = fixed_pct/assumption — never both). Labour: `productivity_basis` (paid_hours_per_unit | productive_hours_per_unit | output_per_crew_shift) and crew if used. Plant: utilisation basis. Subcontract: say what the lump sum includes (prevents double count). Nested assemblies: no cycles.
3. Run validation (`assemblies.validate`) and read every error; fix the definition, not the validator.
4. Hand to the human to `submit_assembly` and have an Estimator/Commercial Approver `approve_assembly`. Approved versions are immutable — edit via `new_assembly_version`.
5. Confirm effect: freeze nothing; run the estimate (UI Estimate build-up) and inspect the line `basis` text for the assembly.

## Outputs and schemas
DB: `assemblies` (+version), `assembly_lines`; audit entries. Optional `4. Clarifications & Assumptions/assembly_notes_<code>.md` recording the human-given source of each factor.

## Validation checks
- `assemblies.validate` returns no errors; no `DOUBLE_WASTE`, no missing productivity basis, no cycle.
- Every factor has a stated human source in `source`/notes; none invented.
- `python -m pytest tests/unit/test_direct_cost.py tests/unit/test_library_data.py -q` passes.

## Approval requirements
Assembly approval: Estimator, Commercial Approver or Administrator (`policy.py` `assembly`). AI cannot approve. Project-scoped assemblies still need approval.

## Failure handling
- Validation errors → report them; never bypass with direct SQL.
- Unknown resource → create the resource (no price) via `create_resource`, then continue.
- Approved assembly needs a change → new version, not an edit.

## Explicitly prohibited
- Measuring, inferring or generating quantities, or editing a quantity without an approved change request.
- Inventing prices, wages, productivity, wastage, suppliers, FX/tax values or benchmarks; filling a missing value with a default or a guess.
- Calling an approve/reject/publish function as, or on behalf of, a human; writing `approvals`, status or `audit_log` rows directly; weakening `app/approvals/policy.py` or a reconciliation rule.
- Editing or overwriting original files in `1. Tender Documents/` or any supplier-supplied original.
- Treating AI output, an extract, a summary or an index as authoritative over the original document.
- Typing consumption/productivity/waste numbers from memory or 'industry norms'.
- Adding prices to assemblies.

_Skills orchestrate application functions; they never bypass validation or server-side approvals. AI output remains a suggestion until an authorised human accepts it._
