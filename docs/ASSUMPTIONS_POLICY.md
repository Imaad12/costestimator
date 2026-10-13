# Assumptions policy

## What an assumption is here
A versioned record (`assumptions`) with: ID (`ASMP-<family>-NNN`), name, description, applicability (`applies_to` cost code or ALL), value type, default value, unit, optional `engine_key`,
source/evidence, confidence, validity dates, status, version history, creator/approver. The register ships with **322 definitions across families A-L** (scope & design basis, quantity &
measurement, materials, labour & productivity, plant, logistics, location, indirects, commercial, tax, testing & handover, risk & confidence).

## No invented numbers
Only four assumptions carry a default, and all are methodological, not market data: `qty.rounding_dp = 3`, `money.rounding_dp = 2`, `tax.default_category = VAT-STD`, `rates.age_warning_days = 180`.
Wastage, productivity, wages, shift hours, markup, margin, contingency, escalation, tax rates and durations are **blank** and must be decided by a human. Every shipped assumption is *Pending Review*.

## Lifecycle
`Draft -> Pending Review -> Approved -> Superseded` (or `Rejected`). Approved versions are immutable; `revise_assumption` creates the next version as a Draft, and approving it supersedes the previous one.
Approval roles: Estimator, Commercial Approver, Administrator (not the AI, not Viewers). Approval records keep reviewer, role, timestamp, previous and approved values, evidence and comments.

## Project overrides
A project may *adopt* assumptions (mandatory ones are adopted automatically at project creation) and *override* a value with a mandatory reason. An override is **Pending Review** until approved; it never
changes the global register. Resolution order for a project: approved override > pending/draft override (visible, flagged, not used in a strict estimate) > approved global default > unapproved global
default (flagged) > unset. Publishing a project value to the global library is a separate act: revise the global assumption and approve it.

## How assumptions are consumed
* **Engine keys** (`labour.shift_hours`, `labour.productive_hours_per_shift`, `plant.utilisation_pct`, `calendar.working_days_per_week/month`, `calendar.hours_per_day`, `money.rounding_dp`, `qty.rounding_dp`, `rates.age_warning_days`) are read by the calculation engine.
* **Assembly lines** reference an assumption explicitly (`waste_ref`, `utilisation_ref`, `shift_hours_ref`, `productive_hours_ref`); the *calculation basis is recorded on the cost line*. Waste is never applied twice: a line with `factor_includes_waste` cannot also carry a waste basis.
* **Commercial policy / indirects** may reference an assumption as `"@ASMP-I-001"` in place of a literal; unresolved or unapproved references raise exceptions.
* The remaining definitions are *documentation obligations*: mandatory ones must be decided per project, and the reconciliation rule `UNAPPROVED_ADOPTED_ASSUMPTION` lists adopted ones still unapproved.

## Explaining impact
Assumptions -> *Show effect* re-runs the strict-or-preliminary estimate with a what-if value and shows the change in direct cost and the pricing schedule; the exact assumptions used are tracked in `used_assumptions`.

## Tax assumptions
Tax categories are separate dated records (`tax_categories`): code, rate, validity period, source reference, verification note and status. `VAT-STD` is seeded at 15% **Pending Review** with the
evidence trail in `data/sources/ACCESS_LOG.md`; a Commercial Approver must record verification evidence before it can be approved. Different supplies may carry different categories (item-level `tax_category`).
Approving a rate requires evidence text; the rate used is the approved category valid on the estimate date.

## Isolation from the global register, and index data
A project override lives only in `project_assumptions` (with its reason and approval) and is resolved for that project; other projects and the global default are untouched (tested). Each frozen estimate version stores the resolved assumption values it used (`estimate_snapshots`).
Escalation: the GASTAT Construction Cost Index observations in `index_observations` are a *reference* a human may cite when deciding an escalation assumption. They are never applied automatically and are not a unit rate.
