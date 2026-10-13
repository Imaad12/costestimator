# Estimating methodology, formulas and bases

All formulas are implemented in `app/estimators/` using `Decimal`. Money is rounded half-up to `money.rounding_dp` (assumption, default 2) **per cost line**;
quantities are never rounded for costing (only for display, `qty.rounding_dp`). Percentages are *percent points* (5 = 5%).

## 1. Inputs and eligibility
* **Quantities** come only from imported BOQ/take-off files, as measured by a human. `quantity_original` (text) is immutable; `quantity` changes only through an
  approved change request. No measurement of drawings, PDFs or BIM is performed.
* **A rate is usable** when: status *Approved* (or *Provisional - Approved for This Estimate* scoped to this project), not superseded, price type is a real price
  (never *Official Index or Benchmark* / *Missing Rate*), `price_date <= estimate date`, `valid_until` not passed, region applicable (rate region = `KSA-ALL`, = project region,
  or a parent region), currency convertible with an **approved** FX rate. Otherwise the line is **unpriced** (`amount = None`) with an exception - never zero, never a default.
  Outcomes: ELIGIBLE, PROVISIONAL, EXPIRED, FUTURE, UNAPPROVED, REGION, NON_PRICE, MISSING.
* **Indicative exposure**: where a non-eligible rate exists its value is shown *separately* (not in totals) so missing-rate exposure is visible. No indicative value exists
  for a truly missing rate - that exposure is reported as "unknown" (count of lines).
* **Assumptions** used by a calculation must be *Approved* (project override approved, or global approved). Unapproved values are used only in the explicit
  *Preliminary view* (`include_unapproved=True`), where every use is flagged and the estimate state is *Preliminary*.

## 2. Direct cost (per BOQ item)
`Qa = BOQ qty x unit conversion(BOQ unit -> assembly unit)` (only same-dimension length/area/volume/mass convert automatically; anything else is an exception).

| Line type | Formula |
|---|---|
| Material / equipment / subcontract | `Q = Qa x factor` (converted from `factor_unit` to the resource unit); if `waste_basis = fixed_pct`: `Q x (1 + w/100)`; if `assumption`: `Q x (1 + A/100)` with A the approved assumption; if `factor_includes_waste = 1` no further waste. **One waste basis only** (enforced). |
| Labour `paid_hours_per_unit` | `H = Qa x factor` |
| Labour `productive_hours_per_unit` | `H = Qa x factor x shift_hours / productive_hours_per_shift` (assumptions `labour.shift_hours`, `labour.productive_hours_per_shift`) |
| Labour `output_per_crew_shift` | `shifts = Qa / output`; each crew member: `H_i = shifts x count_i x shift_hours` |
| Labour overtime | blended rate `= hourly + share x (OT multiplier - 1) x base_wage_hourly` (premium on base wage only; needs a build-up) |
| Plant | `productive h = Qa x factor`; with utilisation `u%`: `charged h = productive h / (u/100)`. With a component build-up: `charged h x (hire + operator + maintenance)/h + productive h x fuel/h`. Mobilisation + demobilisation lumps are added **once per distinct plant item**. |
| Amount | `round(Q_in_rate_unit x rate x FX, dp)`; rate unit converted to the resource unit when different (e.g. priced per tonne, consumed in kg) |

* **Lump-sum / subcontract package** (`subcontract_lump`): `qty x approved subcontract rate`, one line; *no* labour/material/plant lines are generated.
* **Take-off resources**: `resource qty x rate`, no factors or waste added.
* **Provisional / prime-cost sums and allowances**: stated amount, included only when approved (or approved provisionally); shown as provisional.
* **Double-count prevention**: an assembly line of type labour/material/plant is refused when a *subcontract* line in the same assembly already includes that component (unless
  explicitly marked separate); checked at assembly approval **and** at calculation time; indirect items flagged *included in subcontract* are excluded.

Labour rate build-up: `hourly = (base + allowances + accommodation + transport + employer costs + other, per month) / normal paid hours per month`.
Plant hire per hour from the supplied calendar: day = `rate / hours_per_day`; week = `/ (hours_per_day x days_per_week)`; month = `/ (hours_per_day x days_per_month)` - none assumed.

## 3. Indirects (`indirect.py`)
`fixed = amount x qty`; `percent_of_direct = pct x direct`; `per_month = amount x qty x M`; `per_week = amount x qty x M x wd_month / wd_week`; `per_day = amount x qty x M x wd_month`,
with `M` the **approved** project duration (months). Duration sources (all *proposals* until approved): estimator input, labour-derived (`hours / (crew x h/day) / wd_month`), CPM schedule model
(`duration.cpm`, forward pass with cycle detection), AI proposal. Missing amounts/durations leave the item unresolved (exception), never zero.
Allocation to the pricing schedule: `pro_rata_direct` (largest-remainder by direct-cost weight), `direct_trade` (items whose cost code starts with the target), or `separate_line`.

## 4. Commercial (`commercial.py`) - order of operations, each adder applied once from an explicit base
```
C0  = Direct + Indirect                                  (pre-contingency cost)
Ct  = pct x base(direct | direct_indirect)               contingency
R   = sum( pct x base(direct | direct_indirect)  or  fixed amount )   risk allowances
E   = pct x base(direct | direct_indirect | cost_before_escalation = C0+Ct+R)   escalation
T   = C0 + Ct + R + E                                    total cost
S   = T x (1 + markup%)            [method = markup]   or   T / (1 - margin%)   [method = margin]  -- the method label is always shown
N   = S - discount(pct x S | fixed)                      net price before tax;  rounded by the policy rule (to a step, e.g. 1 SAR)
Tax = per tax category: rate(date-valid, APPROVED) x tendered category amount ; Final payable = tendered total + tax
```
Guards: method must be explicit; `margin >= 100%` rejected; duplicate/overlapping risk names and a "contingency" risk item alongside the contingency adder are rejected; contingency/risk/escalation
bases must be named. No default markup, margin, contingency or tax is assumed anywhere.

## 5. Pricing schedule and reconciliation of cost to price
`pricing_schedule.build_schedule` spreads indirects (by allocation method) and the commercial adders/margin/discount over priced items by weight (direct + allocated indirect) using
**largest-remainder** allocation so the unrounded item amounts sum exactly to the commercial net price. Tendered unit rate = `round(net / qty, rate_dp)`; amount = `round(qty x rate, 2)`.
The difference to the commercial net price is the reported **rounding variance** (bounded by `max_rounding_variance`); reconciliation raises a finding if it is exceeded. Tax is then computed on the
tendered schedule amounts per category. Items that are unpriced appear as *Unpriced* (blank), excluded items as *Excluded*; the schedule is flagged incomplete.

## 6. State, completeness and fingerprint
State is **Complete**, **Complete with Provisional Inputs**, or **Preliminary - Incomplete** (any unpriced item, unresolved indirect, missing/unapproved policy, unverified tax, unapproved duration, or preliminary view).
Completeness reports `items fully priced / items` (undefined -> "n/a" when there are no priced scope items). The SHA-256 fingerprint covers all lines, indirects, commercial result, schedule, policy and date.

## 7. Sensitivity
`assumption_overrides` re-run the whole estimate in memory (nothing saved) to show the effect of changing an assumption (Assumptions -> Show effect).

## Reproducibility of a frozen estimate
`freeze_version` stores the results and an input snapshot (`estimate_snapshots`): BOQ rows, assembly definitions with versions, all rate rows of the involved resources with their status at freeze time, resolved assumptions, takeoff lines, FX, policy, tax and indirect rows.
`snapshots.replay_direct_cost` recomputes direct cost from the snapshot only and must equal the frozen figure, even after newer rates were approved (tested). Indirect/commercial/tax figures are frozen results; their inputs are stored but not re-run automatically.
## Index data
Published cost indices (e.g. GASTAT CCI) are not used by any engine formula. They exist only as reference observations for a human deciding an escalation assumption.
