# Extending the system without editing core logic

Everything below is data or UI/API actions; no calculation-engine code changes.

## New trade, sub-trade or cost code
* UI: *Settings -> Add cost code* (Administrator): code (e.g. `E.14` or `E.14.01`), name, parent (`E`), optional default unit. Or add rows to `data/taxonomy/cost_codes.csv` (loaded idempotently at `init`).
* The new code is immediately selectable for resources, assemblies, BOQ mapping, indirect allocation targets, exclusions and reports. Divisions use level 1; sub-trades level 2; further levels are free.

## New resource (material, labour, plant, equipment, subcontract)
* UI: *Create resource* via the API action `create_resource` (type, description, canonical unit, cost code, specification) or add a row to the catalogue CSV (`data/materials/materials.csv` etc.; columns `id,resource_type,cost_code,category,description,aliases,specification,brand_requirements,unit,notes`).
  A new resource starts with **no rate** (Missing Rate placeholder when loaded from CSV).
* Add a rate: *Resource page -> Propose a new rate* (rate type, price, currency, dates, evidence). For labour/plant provide `components` (wage/allowance/accommodation/transport/employer cost + normal hours; or hire rate + calendar + operator/fuel/maintenance) and the hourly rate is derived deterministically.

## New assembly
* *Assemblies*: clone an existing/Draft one (*Clone*), or create via the API action/service `create_assembly` with lines. For each line choose the type, resource, **factor** (consumption per unit), the **waste basis** (`factor_includes_waste` / `fixed_pct` / `assumption` - only one), labour **productivity basis** and crew, plant utilisation, subcontract inclusions.
* Submit -> approve (validation blocks missing factors, missing labour productivity basis, circular nesting, and labour/material/plant duplicated inside a subcontract). Approved versions are immutable; use *New draft version* to change one.
* Alternatively edit the *Assembly Library* sheet in the workbook and re-import (creates a new draft version).

## New assumption
* Add a row to `data/assumptions/assumptions_register.csv` (id `ASMP-<family>-NNN`, family A-L, `value_type`, optional `unit`, `engine_key`, `mandatory_for_projects`), or call the service `create_assumption`. Reference it from an assembly line (`waste_ref`) or a commercial policy value (`"@ASMP-..."`). Approve it (or approve a project override).
* A **new engine key** (read directly by the calculator) is the only case needing code; all existing keys are listed in `docs/ASSUMPTIONS_POLICY.md`.

## New supplier quotation
* *Vendor quotations -> New quotation* (supplier, package, reference, dates, currency, tax treatment) -> add lines linked to procurement items -> submit -> Procurement Reviewer approves. Or fill the exported RFQ sheet and use *Import completed RFQ sheet*. Then levelling and selection (see PROCUREMENT_GUIDE).

## New RFQ language
`app/procurement/rfq.py::TEMPLATES` is a dictionary keyed by language code; add a new entry (subject/greeting/intro/requirements/columns). Arabic is included as a draft.

## Reconciliation severity / rules
Edit `config/reconciliation_rules.json` (severity, `exception_allowed`, `blocking_severities`) or store an override JSON in the `settings` table under `recon_rules_override`. Adding a brand-new rule requires a function in `reconciliation/engine.py::collect_findings`.

## New commercial policy
*Commercials -> policies*: create a policy from `data/commercial_rules/policy_template.json` (all values null on purpose), choose markup or gross-margin, fill every value, submit, have it approved, assign to the project.
