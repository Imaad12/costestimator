# Workforce, productivity and programme method

Code: `app/estimators/productivity.py` (pure Decimal engine), `app/services/workforce.py` (norms, profiles, activities, baselines, scenarios), `app/estimators/param_kinds.py` (calendar kind),
tables `productivity_norms`, `workforce_profiles`, `work_activities`, `programme_baselines` (migration `0015`). Tests: `tests/unit/test_productivity_engine.py`,
`tests/integration/test_workforce_service.py`, `tests/closure/test_closure_scenario.py` (independent oracle in `tests/closure/oracle.py`).

**No productivity value, crew split, workforce size, shift efficiency or role cost lives in the code or ships in the library.** Every number is entered by a person as a versioned, sourced, approvable record.
The values used in the synthetic closure scenario are fixtures labelled *SYNTHETIC TEST DATA - NOT AN INDUSTRY BENCHMARK*.

## 1. Workforce profiles (initial planning archetypes)

| Archetype | Initial planning band (head-count) |
|---|---:|
| `sme` SME / small contractor | 4-15 |
| `mid` Mid-sized contractor | 15-25 |
| `large` Large contractor | 26-50 |
| `enterprise` Enterprise / major-project contractor | 51+ |

These are **initial company planning profiles from the business brief, not industry-standard workforce categories**. The band is stored on each profile row (editable per profile; use `custom` for no band),
the profile carries the label *Configurable company planning assumption - not an industry-standard workforce category*, is versioned and needs approval by a person other than its author.
Head-count = direct roles + indirect roles (equipment `eq:` keys and subcontract capacity are not counted); a profile outside its band is refused (`ARCHETYPE_BAND`) unless the band is changed explicitly.

A profile records: direct roles (skilled, semi-skilled, labourers, operators/drivers, specialist-subcontract capacity as `sub:` keys), indirect personnel (foremen/supervisors, engineers/technical, QC/inspection, HSE),
shifts (1-3) with a night-shift efficiency (required when shifts > 1), attendance %, availability %, productive hours per worker per shift, overtime hours and overtime efficiency, work-front limit, mobilisation
(working days before the workforce is available), subcontract capacity, and optional role day-costs (each person-entered).

## 2. Work calendar

The calendar is the governed parameter kind `calendar` (project scope, approved): start date, working weekdays (0 = Monday), holidays, `hours_per_day` (the standard day), **reduced-hour windows**
(`from`, `to`, `hours`, mandatory `reason`/approval reference; hours may not exceed the standard day), **shutdowns** (non-working windows), `calendar_source` and `requires_confirmation`.
Saudi calendars are **not assumed**: with no approved calendar the programme refuses (`CALENDAR_REQUIRED`). A default profile may be entered with `requires_confirmation = true`; any programme built on it is flagged
`CALENDAR_UNCONFIRMED` and *provisional*, and a baseline built on it cannot be approved. The calendar actually used is printed in every programme report and document (D19).
Weather, access, permits, inspections and client working hours are expressed through shutdowns, reduced-hour windows, fixed days on activities and finish-to-start lags - there is no hidden factor.

Capacity on a day = `day_factor × (1 + overtime_hours × overtime_efficiency / productive_hours) × shift_multiplier`, where `day_factor = hours that day / standard hours` (1 normally, <1 in a reduced window, 0 on a non-working day)
and `shift_multiplier = 1 + night_efficiency × (shifts − 1)`. This scaling is a documented planning rule, not a legal or industry statement.

## 3. Productivity calculation

For every activity (BOQ quantity read from the human-measured BOQ item; the application never types or infers a quantity):

* **Labour-hours basis** (`labour_hours_per_unit`): `hours = Q × norm × Π(site factors)`; `crew-days = hours ÷ (productive hours per worker-day × crew size)` (the crew is the norm's crew).
* **Crew-output basis** (`crew_output_per_crew_day`): `crew-days = Q ÷ norm × Π(site factors)`. The labour-hours formula is **not** applied again; labour-hours are reported for information as `crew-days × crew size × productive hours`.
* **Double counting**: a norm flagged `includes_productivity_factors` already contains site factors - a further factor is ignored and reported (`DOUBLE_COUNT`).
* `effective crews = min(crews, work fronts, profile front limit)`; **unconstrained duration** = `ceil(crew-days ÷ effective crews)` working days (rounding up to whole days) + set-up/mobilisation days before + curing/testing/inspection days after (person-entered fixed days).
* A norm's `output_unit` must equal the BOQ unit, else the activity is excluded with `UNIT_MISMATCH`.

Rounding: arithmetic is `Decimal`; durations round **up** to whole working days; reported hours and crew-days are quantised half-up to 2 decimals (calculation precision is kept internally).
Money in time-phased reports (cash flow, escalation, loading) is quantised to 2 decimals at report level (`core.money.quantise_tree`); engines keep full precision.

## 4. The five durations (never mixed)

| Duration | Definition |
|---|---|
| Unconstrained | one activity, its own crews, no predecessors, no limits |
| Dependency-constrained | CPM over finish-to-start links with lags, unconstrained durations |
| Procurement-constrained | CPM plus the material-ready working-day index from the linked long-lead item (`planned/actual order date + lead weeks` converted to the calendar) |
| Resource-constrained | daily simulation against the finite pool (role head-count × attendance × availability, equipment and subcontract capacity as stated), work fronts, shifts, overtime, calendar hours; priority = in-progress first, then latest finish from the CPM, then user priority, then code |
| Approved baseline / forecast | a saved, reviewed `programme_baselines` row; the re-forecast re-runs from progress (% complete at a status day) and reports the variance to the baseline |

Calendar days are derived from the working-day index through the calendar (a plain date walk, verified by the oracle). Working days and calendar days are always both reported.
Critical path = zero total float on the procurement-constrained CPM; resource-limited activities and each activity's resource delay are listed separately (`resource_limited`, `resource_delay_wd`).
A role the pool cannot supply even once (`RESOURCE_UNAVAILABLE`) blocks the activity and everything behind it: the profile is reported **NOT SCHEDULABLE**, not given a short duration.

## 5. Governance of norms and profiles

Norm states: `Draft`, `Proposed` (a user proposes), `Imported - Unverified`, `Pending Review`, `Approved`, `Rejected`, `Superseded`; origin `user` / `system` / `import` / `synthetic`; evidence status
`unverified` / `verified` / `synthetic` (a synthetic norm can never be `verified`). *Missing* is not a stored state: an activity without an approved norm is a reported gap with its effect
(duration carried as 0 and the programme labelled **PROVISIONAL / NOT FOR RELIANCE**). Each norm has id and version, trade, activity, output unit, applicability (region, project type, conditions), crew composition,
source, evidence, confidence, effective and review dates, author, reviewer and approver, exclusions and restrictions. Approval needs a source and an effective date, a different person than the author
(four-eyes default), and cannot be given by a Viewer, AI or test principal for a real project. Approved rows are immutable (service and trigger); a change is a new version.
A *provisional* scenario (`allow_provisional`) may use unapproved norms for planning; it is labelled, cannot be baselined, and `readiness` blocks any production claim that depends on it.

## 6. Crew scenarios

`crew_scenarios` schedules the same activities, norms and calendar for several profiles and reports duration (all five forms), head-count, productive hours, peak manpower, labour-hours, critical path,
resource-limited activities, constraints, cost impact (only when role day-costs were entered; otherwise "not computed") and the claim. Doubling a workforce does not halve a programme: finite work fronts, the single shared crane
(`eq:crane`), dependencies and whole-crew rounding bind. In the closure scenario the large and enterprise profiles finish on the same day. Scenario numbers are *comparisons on synthetic norms*, never industry benchmarks.
Where no approved norm exists no range is invented: a sensitivity range needs two person-entered, sourced norms.

## 7. Standards and evidence

The register (`standards_register`, `data/standards/standards_register.json`, CLI `standards list|acquire|import`) records title, publisher, URL/file, edition, access date, clause/page, scope, limitations,
verification status and a short paraphrase. Status of the entries actually read: see `docs/STANDARDS_AND_EVIDENCE_REGISTER.md`. Nothing is reproduced in full and **no compliance claim is made by the product**.
The internal capability levels 1-5 of the capability matrix are **not** AACE estimate classes or any owner's classification; an AACE-style class can only come from a company-approved classification scheme entered as a governed parameter.
Productivity references (RSMeans, Spon's, CIOB, manufacturer instructions, company actuals) are listed by **name only** as *requires human acquisition - not verified*; no number from them is stored.
Manual evidence import: obtain the document, record edition/clause/page, then `python -m app.cli standards import FILE --user NAME` (status `Verified` requires the URL/file that was read), then cite the row as the `source` of a governed norm.

## 8. Limitations

No resource levelling beyond the priority rule; no multi-calendar per resource; overtime and night-shift gains are person-entered efficiencies; no weather model; subcontract crews are capacity pools, not schedules;
fixed days are not resource-loaded; crews are indivisible (a 3-person crew cannot run with 2); `labour_hours_per_unit` quantities and role names must match the norm's crew keys exactly; no import of P6/MSP files;
no automatic drawing/BIM take-off. Reforecast accepts % complete per activity only.
