# Synthetic end-to-end pilot run (evidence report)

> **SYNTHETIC SOFTWARE VALIDATION ONLY — NOT A MARKET ESTIMATE, NOT FOR TENDER, NOT FOR PROCUREMENT, AND NOT FOR COMMERCIAL RELIANCE.**
> Every rate, quotation, supplier, productivity value, commercial term and approval below is SYNTHETIC TEST DATA. The approvals were performed by `TEST ACTOR` principals created for the run; they validate software behaviour and are **not** procurement, commercial, tax or legal approvals. Nothing here is a Saudi market rate, a genuine quotation, a client requirement or tax advice, and success here says nothing about estimating accuracy on real work.

The run is reproducible: `python scripts/run_synthetic_pilot.py [FRESH_DIR]` (driver `tests/synthetic_pilot/pilot.py`, fixtures `tests/fixtures/synthetic_pilot/`, regression test `tests/integration/test_synthetic_pilot.py`). It writes only to the scratch directory it is given.

## 1. Run identity

| item | value |
|---|---|
| Branch | `claude/wizardly-einstein-w4ykwd` |
| Starting commit (this iteration) | `d688a1e` (previous pilot run; code commit `4265168`, before that `bd05f7e`) |
| Code commit for this run | `5421c6d` (fixes, tests, driver changes). This report is committed after it; `git log` shows the final commit. |
| Scratch database | `scratch_pilot.db` inside a fresh temporary directory (this run: `$WORK`); the shared `var/` database, `projects/`, `data/` libraries and the public-data archive were not touched |
| Temporary projects | `PRJ-9001` main project (30-line BOQ); `PRJ-9002` bottom-up variant + supply sourcing; `PRJ-9003` take-off derivation check; `PRJ-9004` negative control (not flagged demo). IDs follow the application's `PRJ-nnnn` rule. |
| External access | None. No website, live API, email or supplier contact. No network was used by the run or the tests. |


## 2. Commands actually run (exit status)
Service-level stages call the real service functions in-process (the same functions the CLI/API call). The CLI, REST API and UI stages below were executed for real.


| command | exit status |
|---|---|
| `python scripts/run_synthetic_pilot.py <fresh dir>` | 0 (all stage verdicts PASS) |
| `python -m pytest -o addopts="" -q` (before changes, at `d688a1e`) | 0 — 359 passed in 121.53s (recorded in the previous pass) |
| `python -m pytest -o addopts="" -q` (after changes) | 0 — 385 passed in 142.38s (0:02:22) |
| `python -m app.cli param import $WORK/cli_params_SYNTHETIC.csv --project PRJ-9004 --dry-run` | 0 |
| `python -m app.cli param import $WORK/cli_params_SYNTHETIC.csv --project PRJ-9004` | 0 |
| `python -m app.cli param import tests/fixtures/synthetic_pilot/governed_parameters_SYNTHETIC_TEST_ONLY.csv --dry-run` | 0 |
| `python -m app.cli rates import tests/fixtures/synthetic_pilot/rates_SYNTHETIC_TEST_ONLY.csv --source-name SYNTHETIC TEST DATA --url SYNTHETIC-TEST-FIXTURE --synthetic --dry-run` | 0 |
| `python -m app.cli rates import $WORK/cli_rates_SYNTHETIC.csv --source-name SYNTHETIC TEST DATA --url SYNTHETIC-TEST-FIXTURE --synthetic` | 0 |
| `python -m app.cli rates import tests/fixtures/synthetic_pilot/rates_SYNTHETIC_TEST_ONLY.csv --source SRC-002 --dry-run` | 1 |
| `python -m app.cli report PRJ-9001 rollup` | 0 |
| `python -m app.cli report PRJ-9001 manhours` | 0 |
| `python -m app.cli report PRJ-9001 schedule` | 0 |
| `python -m app.cli project verify-snapshot 2` | 0 |
| `python -m app.cli audit-verify` | 0 |
| `python -m app.cli coverage` | 0 |
| `python -m app.cli param list --project PRJ-9001` | 0 |
| `python -m app.cli rates pending` | 0 |
| `python -m app.cli export-workbook PRJ-9001 --out $WORK/PRJ-9001_master_SYNTHETIC.xlsx` | 0 |
| `python -m app.cli verify-workbook $WORK/PRJ-9001_master_SYNTHETIC.xlsx --project PRJ-9001` (LibreOffice recalculation) | 0 |


State-changing CLI commands ran as `cli-est`, a TEST ACTOR Estimator created in the scratch database. The exit status `1` on the `--source SRC-002` import is the *expected refusal* (`SOURCE_NOT_PRICE`).

## 3. Test results

|  | result |
|---|---|
| Before (starting commit `d688a1e`) | 359 passed |
| After | 385 passed in 142.38s (0:02:22) |
| New / changed tests | `tests/unit/test_time_allocation.py` (4), `tests/unit/test_indirect_eligibility.py` (5), `tests/unit/test_plant_hire.py` (5), `tests/approvals/test_actor_isolation.py` (8), `tests/integration/test_actor_isolation_api.py` (1), `tests/integration/test_synthetic_pilot.py` (+3, updated figures); changed expectations: `tests/integration/test_full_workflow.py` (demo exports are DEMONSTRATION, a High overlap finding must be accepted by a Commercial Approver), `tests/unit/test_cashflow.py` (money-conservation identity under the documented convention) |

No test was removed. Two tests changed their expectations because behaviour changed on purpose (see above); no role, gate or severity was weakened: new rules are *additional* blockers, and demo exports are now *less* privileged (never submission-ready).

## 4. Stage verdicts (summary)

| # | stage | verdict | evidence |
|---|---|---|---|
| 0 | Protect repository and real data | PASS | scratch DB/workspaces only; `git status` shows only intended files; no external access; PRJ-0001 untouched |
| 1 | Hypothetical project | PASS | fixture `boq_SYNTHETIC_TEST_ONLY.csv`, all files named/labelled SYNTHETIC / TEST ONLY |
| 2 | 30-line measured BOQ | PASS | 30 lines imported; 3 unit texts flagged and resolved by explicit human decision (§5) |
| 3 | Project workspace | PASS | 10 folders, CLAUDE.md, project.json, original fixture + stored copy, 3 documents indexed and searchable, no other project IDs referenced |
| 4 | Cost-code and WBS structure | PASS | 30/30 mapped; CBS, WBS and fictional client cross-walk tie out; no parent/child double count |
| 5 | Synthetic resources and assemblies | PASS | 10 library resources + 30 installed-rate resources; 3 required assemblies + 2 valve assemblies with explicit synthetic norms (§9) |
| 6 | Rate import and approval workflow | PASS | dry-run, import, pending, index refusal, synthetic labelling (defect D-1 fixed) |
| 7 | Supplier quotations and levelling | PASS | A recommended; selection stayed Pending Review until the TEST ACTOR decision |
| 8 | Governed parameters | PASS | 7 rows (incl. forklift terms and the extended crane terms); dry-run, Draft-only import, approval via TEST ACTOR; site indirects, overhead, contingency and profit have no governed kind (modelled as approved indirects / policy), VAT is a tax-category record (§8) |
| 9 | Programme and loading | PASS | 29 working days / 33 calendar days; man-hours 1,220 tie out; the 37,950.00 untied cost is now allocated by explicit rules (13d) |
| 10 | Take-off templates | PASS | 6 templates derived mechanically, all Pending Review; STRUCTURAL/MECHANICAL validation only |
| 11 | Direct cost and commercial build-up | PASS | 366,261.00 = independent 365,361 + 900.00 explained; chain reproduced independently with the eligible indirect base |
| 12 | Independent BOQ total | PASS | 365,361.00 (Decimal arithmetic), compared line by line: only P-020 differs (+900.00 standby) |
| 13a | Risk (seeded Monte Carlo) | PASS | reproducible with the seed; expected value checked by hand; proposal only |
| 13b | Time-phased escalation | PASS | factors checked independently; covers ALL direct cost after the allocation rules; INCOMPLETE label and block without them (13d) |
| 13c | Cash flow, retention, bond | PASS | reconciled: valuations, cash paid, cash received, retention and closing balance on one base (previous run: FAIL, balance overstated) |
| 13d | Untied cost: allocation, exposure and blocking | PASS | before: 37,950.00 exposed, INCOMPLETE labels, financing refused, gate blocked; after explicit rules: complete and reconciled |
| 14 | Basis of Estimate | PASS | all required sections present incl. the validation-only statement (via the new PROJECT NOTE banner, D-3) |
| 15 | Completeness, reconciliation, approval gates | PASS / PASS | preliminary estimate cannot be approved or exported; Critical findings in the non-demo control; role gates verified; PLANT_HIRE_DAYS (High) needs a Commercial Approver |
| 16 | Freeze and replay | PASS | frozen v1 replays with the identical fingerprint and totals after a parameter and a rate change; take-off replay PASS (16b) |
| 17 | Reports, API, UI, export | PASS | CLI/API/UI agree; workbook recalculated by LibreOffice (192 formulas, no mismatch). Microsoft Excel NOT TESTED |
| 18 | Tests and defect handling | PASS | 4 further findings (D-4..D-7) fixed with regression tests; full suite green |
| 19 | Production isolation of the pilot | PASS | classification `demonstration`; never production ready; test actors/forged names/role mismatch resolved as non-human; real-project attempts refused |


Other items: client requirements / owner profile **NOT TESTED** (no controlled owner document exists; no compliance with any client is claimed). Landed cost, FX and hedge **NOT TESTED** (SAR-only brief). File import of quotation lines **NOT TESTED** in this pilot (quotation lines were entered as structured data; the importer has its own tests). AI features **NOT TESTED**. Microsoft Excel **NOT TESTED**.

## 4b. Closure of the four pilot findings — what was run and what changed
### Finding 1 — cash flow and escalation (release-blocking): PASS

|  | before the allocation rules | after explicit approved rules |
|---|---|---|
| Untied cost (exact) | 37,950.00 | 0.00 |
| Untied lines | P-020 plant 10,800.00; P-021 plant 5,200.00; P-022 subcontract 4,050.00; P-030 subcontract 17,000.00; P-020 plant_standby 900.00 | none (rules: SUP-ALL, LIFT-INST-WELD, SCAFFOLD) |
| Cash-flow status | INCOMPLETE - NOT FOR RELIANCE: SAR 37,950.00 of direct cost is allocated to no period (see unallocated_lines); SAR 46,512.85 of the price is not valued and the closing balance excludes it | COMPLETE |
| Escalation status | INCOMPLETE - NOT FOR RELIANCE: SAR 37,950.00 of eligible cost has no time allocation and is NOT escalated (see unescalated_lines) | COMPLETE for the cost within profile scope |
| Price valued | 402,389.45 (unvalued share 46,512.85) | 448,902.30 |
| Escalation total / base | 1,609.55 / 328,311.00 (37,950.00 not escalated) | 1,798.67 / 366,261.00 |
| Closing balance | 44,232.40 (excludes the unallocated share; flagged) | 49,345.29 |
| Financing proposal | TIMEPHASING_INCOMPLETE (refused) | allowed |
| Final gate | blocked by `TIMEPHASING_INCOMPLETE` (High) | finding gone |

The rules are governed `time_allocation` parameters: `SUP-ALL` (A.03 → all activities, duration-weighted), `LIFT-INST-WELD` (A.07 → INST 60 % / WELD 40 %), `SCAFFOLD` (A.06 → INST, WELD, PAINT, duration-weighted); allocated: LIFT-INST-WELD 16,900.00, SCAFFOLD 4,050.00, SUP-ALL 17,000.00. **Without them nothing is spread:** the cash flow says INCOMPLETE - NOT FOR RELIANCE and the gate blocks. Also tested: missing task, conflicting/duplicate rules, shares summing to ≠ 100 %, zero-duration activities, unapproved rules (`tests/unit/test_time_allocation.py`).
### Finding 2 — percentage indirects: PASS (stage 11; unit tests)

|  | previous run (`d688a1e`) | this run |
|---|---|---|
| Indirect base | whole direct cost 366,261.00 | eligible base 302,691.00 (division A excluded) |
| Indirect (8 % + 3 %) | 40,288.71 | 33,296.01 |
| Contingency 5 % of (D + I) | 20,327.49 | 19,977.85 |
| Total cost | 426,877.20 | 419,534.86 |
| Net price | 456,758.60 | 448,902.30 |
| VAT 15 % on the schedule | 68,513.90 | 67,335.76 |
| Final payable | 525,273.26 | 516,240.81 |

The net price falls by 7,856.30 because the percentage indirects no longer apply to preliminaries priced as BOQ lines — a *consequence of the synthetic eligibility decision*, not a correction toward a market figure. Overlap detection, partial eligibility, unclassified cost and the unspecified legacy base are proven in `tests/unit/test_indirect_eligibility.py` (e.g. 8 % on 5,500 = 440.00 legacy; excluding A.* = 80.00; overlap exposure 360.00).
### Finding 3 — day-priced plant: PASS (stage 11; unit tests)

| plant | billing basis | window (from the programme: INST..WELD) | working days | calendar days | required | billed | difference | exposure SAR | status |
|---|---|---|---|---|---|---|---|---|---|
| SYN-P-020 | working_day | 2026-11-13 .. 2026-11-24 | 10 | 12 | 10 | 6 | 4 | 7,200.00 | PRICED_BELOW_PROGRAMME_WINDOW |
| SYN-P-021 | working_day | 2026-11-13 .. 2026-11-24 | 10 | 12 | 10 | 8 | 2 | 1,300.00 | PRICED_BELOW_PROGRAMME_WINDOW |

The BOQ quantities (crane 6 days, forklift 8 days) are human-supplied and were **not** changed; the programme window needs 10 working days, so both plant lines raised `PLANT_HIRE_DAYS` (High) and blocked the estimate approval until a Commercial Approver (TEST ACTOR) accepted them with a documented reason (an Estimator was refused). No PLANT_UNIT assumption remains (the assembly lines declare `factor_unit = day`), and the earlier `SYSTEM_EXCEPTION`s are gone. Minimum hire, standby, mobilisation/demobilisation, calendar-day billing, programme delay and missing terms: `tests/unit/test_plant_hire.py` (e.g. working 10 days vs calendar 12; a 3-day slip makes the calendar window 17 days).
### Finding 4 — test-actor and synthetic isolation (release-blocking): PASS

| check | result |
|---|---|
| Pilot classification | `demonstration`; production_ready = False |
| Why (pilot environment) | the project is flagged as a demonstration project; synthetic data is used in the estimate; the environment is 'test', not 'production'; estimate approval: approved by a 'test' principal (test-commercial); only registered human users count; estimate approval: recorded in environment 'test', not 'production' … |
| If the environment were `production` | still `demonstration` — the project is flagged as a demonstration project; synthetic data is used in the estimate … |
| Approvals by actor type / environment | 54 × test/test |
| Forged display name / role mismatch / registered test actor / missing actor | `unregistered`, `role_mismatch`, `test`, `unregistered` |
| Test actor approving a tender export on the real-project control (production) | NON_HUMAN_ACTOR |
| Direct export attempt by a test actor (production) | NON_HUMAN_ACTOR |
| Exports marked submission-ready | 0 |
| Export readiness labels | 2 × preliminary, 4 × demonstration |

Production readiness (the only route to SUBMISSION READY) is covered by tests with registered human users (`tests/approvals/test_actor_isolation.py`): the human chain is ready; test principals, unregistered/forged names, role mismatch, a `test` environment, copied or hand-written approval rows, demo projects and exceptions by test principals are not.

## 5. BOQ import, units and independent total (stages 2, 12)
Unit rules: the standard registry has no `dia-in`, `m2-day` or `test`. On import these three lines were **flagged** (`unit_status=unknown`, unit left empty) and not converted:

| item | status on import | explicit human decision |
|---|---|---|
| P-016 | unknown | inch_dia |
| P-022 | unknown | m2_day |
| P-024 | unknown | test |

`dia-in` was mapped to the existing `inch_dia`; an Administrator added `m2_day` (own dimension, never `m2`) and `test` (own dimension). Other mappings, recorded: `ea→nr`, `hour→hr`, `LS→ls`, `weld→joint` (registry synonym), `set→set`, `kg→kg`, `m→m`, `m2→m2`, `day→day`. `LS` was never confused with `LPS`/`l_s`.

Independent extensions (quantity × synthetic baseline rate, `Decimal`, no rounding needed) and the application's line amounts:

| item | description | unit | qty | synthetic rate | independent extension | application amount |
|---|---|---|---|---|---|---|
| P-001 | Carbon steel pipe DN50 | m | 120 | 185.00 | 22,200.00 | 22,200.00 |
| P-002 | Carbon steel pipe DN100 | m | 240 | 315.00 | 75,600.00 | 75,600.00 |
| P-003 | Carbon steel pipe DN150 | m | 80 | 480.00 | 38,400.00 | 38,400.00 |
| P-004 | 90-degree elbow DN50 | ea | 24 | 95.00 | 2,280.00 | 2,280.00 |
| P-005 | 90-degree elbow DN100 | ea | 40 | 165.00 | 6,600.00 | 6,600.00 |
| P-006 | Tee DN100 | ea | 12 | 280.00 | 3,360.00 | 3,360.00 |
| P-007 | Reducer DN100 x DN50 | ea | 8 | 190.00 | 1,520.00 | 1,520.00 |
| P-008 | Flange DN100 | ea | 32 | 140.00 | 4,480.00 | 4,480.00 |
| P-009 | Gasket DN100 | ea | 32 | 28.00 | 896.00 | 896.00 |
| P-010 | Bolt and nut set DN100 | set | 32 | 45.00 | 1,440.00 | 1,440.00 |
| P-011 | Gate valve DN50 | ea | 8 | 620.00 | 4,960.00 | 4,960.00 |
| P-012 | Gate valve DN100 | ea | 6 | 1,450.00 | 8,700.00 | 8,700.00 |
| P-013 | Check valve DN100 | ea | 4 | 1,850.00 | 7,400.00 | 7,400.00 |
| P-014 | Fabricated pipe supports | kg | 650 | 24.00 | 15,600.00 | 15,600.00 |
| P-015 | Mechanical anchors | ea | 80 | 22.00 | 1,760.00 | 1,760.00 |
| P-016 | Welding and consumables | dia-in | 420 | 38.00 | 15,960.00 | 15,960.00 |
| P-017 | Welder labour | hour | 320 | 65.00 | 20,800.00 | 20,800.00 |
| P-018 | Pipe fitter labour | hour | 400 | 55.00 | 22,000.00 | 22,000.00 |
| P-019 | Helper labour | hour | 500 | 32.00 | 16,000.00 | 16,000.00 |
| P-020 | 25-ton crane hire | day | 6 | 1,800.00 | 10,800.00 | 11,700.00 |
| P-021 | 3-ton forklift hire | day | 8 | 650.00 | 5,200.00 | 5,200.00 |
| P-022 | Scaffolding access | m2-day | 450 | 9.00 | 4,050.00 | 4,050.00 |
| P-023 | Radiographic testing | weld | 42 | 260.00 | 10,920.00 | 10,920.00 |
| P-024 | Positive material identification | test | 15 | 180.00 | 2,700.00 | 2,700.00 |
| P-025 | Hydrotesting package | LS | 1 | 8,500.00 | 8,500.00 | 8,500.00 |
| P-026 | Flushing package | LS | 1 | 4,800.00 | 4,800.00 | 4,800.00 |
| P-027 | Surface preparation and painting | m2 | 180 | 42.00 | 7,560.00 | 7,560.00 |
| P-028 | Piping insulation | m2 | 95 | 125.00 | 11,875.00 | 11,875.00 |
| P-029 | Mobilisation and demobilisation | LS | 1 | 12,000.00 | 12,000.00 | 12,000.00 |
| P-030 | Site supervision | day | 20 | 850.00 | 17,000.00 | 17,000.00 |
|  | **Grand total** |  |  |  | **365,361.00** | **366,261.00** |


Difference **900.00** = the approved TEST-ONLY crane standby (`plant_hire_terms` CRANE-TERMS: 1 day × 1,800 × 50 %), booked on P-020 (10,800 + 900 = 11,700). Crane minimum hire (1 day) is below the 6 days used, so no top-up arose; the forklift has no terms, so none applied. No baseline rate was changed to force a match.

## 6. Rate import and approval-state results (stage 6)
* Fixture `rates_SYNTHETIC_TEST_ONLY.csv`: 40 rows (30 installed baseline rates + 10 library resource rates), importer schema headers (`Resource ID, Description, Unit, Unit Price, Currency, Price Date, Valid Until, VAT, Delivery, Installation, Price Kind, Source Name, Evidence`).
* Dry run: accepted 40, rejected 0, errors none (also executed through the CLI: `rates import … --synthetic --dry-run`, exit 0). Import: accepted 40, rejected 0, manifest 2.
* All 40 candidates were `Pending Review` after import; `resource_rates` held no new priced row until the review → publish → `approve_rate` chain was run by TEST ACTORs for 37 of them. Source name, currency, unit, price date, VAT basis, evidence snippet and the SYNTHETIC flag are stored on each candidate. The three supply materials that were quoted (DN100 pipe, DN50 pipe, support steel) were deliberately left at candidate stage: the quotations are their evidence route.
* Index sources: `SRC-001`, `SRC-002`, `SRC-003` each refused with `SOURCE_NOT_PRICE`; also via CLI (exit 1).
* Published rates are typed **Synthetic Demonstration Rate** with `is_synthetic=1` (37 Approved; defect D-1). Importing never approved anything by itself.
* Confidence: the file was imported with `confidence=Medium` for synthetic rates; at the default `Unverified` every approved rate raises a `RATE_WARNING` and a procurement 're-confirm' need (observation O-1).

## 7. Quotation levelling (stage 7, project PRJ-9002)
Project PRJ-9002 prices the same measured quantities of five lines **bottom-up from assemblies**, so that the supply resources have missing rates and the procurement chain (needs → draft RFQ → quotations → levelling → selection → publication) is genuinely driven. Quotations are procurement evidence for those supply resources only; they are **not** added to the installed baseline rates of PRJ-9001.
Needs detected: 5 (draft RFQ `RFQ-PRJ-9002-001`; nothing is sent by the application).


| supplier | base price | delivery adjustment | tax status | validity | coverage | non-compliant | missing | like-for-like | evaluated total |
|---|---|---|---|---|---|---|---|---|---|
| A | 86,350.40 | 0.00 | excl (UNVERIFIED, synthetic) | Valid (to 2026-10-28) | 5/5 | none | none | yes | 86,350.40 |
| B | 85,519.55 | 2,500.00 | excl (UNVERIFIED, synthetic) | Valid (to 2026-11-04) | 5/5 | none | none | yes | 88,019.55 |
| C | 90,065.70 | 0.00 | excl (UNVERIFIED, synthetic) | Valid (to 2026-10-21) | 5/5 | none | none | yes | 90,065.70 |


Hand check (quantities from the assemblies: DN100 pipe 244.8 m, DN50 pipe 122.4 m, support steel 682.5 kg, 6 gate valves, 4 check valves): A = 47,001.60 + 13,708.80 + 10,920.00 + 7,920.00 + 6,800.00 = **86,350.40**; B = 46,022.40 + 14,198.40 + 10,578.75 + 7,680.00 + 7,040.00 = 85,519.55, + SAR 2,500 delivery = **88,019.55**; C = **90,065.70**.
* Headline-lowest is **B** (85,519.55); after the approved delivery adjustment the evaluated lowest like-for-like is **A**. **Proposed recommendation: Supplier A.** The 2,500 delivery charge is applied once at package level (the engine's documented adjustment is package-level; no per-item allocation method exists).
* Validity: at the run date all three are valid (A 14, B 21, C 7 days); re-levelled 10 days later, Supplier C is `Expired` and no longer like-for-like.
* Tax status: the brief says tax treatment is unverified; the engine needs a stated treatment to normalise, so the quotations were recorded as `excl` with a deviation note "tax treatment NOT verified". The same treatment on all three leaves the ranking unaffected, but the evaluated totals rest on that unverified assumption.
* Human approval status: the selection was `Pending Review`; publication before approval was refused (`SELECTION_NOT_APPROVED`); only then did the TEST ACTOR decision publish five `Pending Review` synthetic rates, which a TEST ACTOR approved.

Bottom-up vs baseline for the five lines (informational; not forced to agree):

| item | baseline installed (SAR) | bottom-up from assembly (SAR) | difference |
|---|---|---|---|
| P-001 | 22,200.00 | 19,600.32 | -2,599.68 |
| P-002 | 75,600.00 | 68,482.56 | -7,117.44 |
| P-012 | 8,700.00 | 8,703.00 | 3.00 |
| P-013 | 7,400.00 | 7,322.00 | -78.00 |
| P-014 | 15,600.00 | 13,552.50 | -2,047.50 |

The differences are a property of the synthetic norms, not an error; they show why installed BOQ rates and resource build-ups must be reconciled by a person before use.

## 8. Governed parameters (stage 8)
`param import` dry run: would create 7, errors none, **rows and audit entries unchanged** (rolled-back transaction; test added). Import created 7 rows, all `Draft`; a Draft calendar was **not** in force; after TEST ACTOR submit/approve they were. Items from the brief:

| brief item | how it was recorded | status |
|---|---|---|
| Working calendar 6 days/week, 10 h/day | `calendar` PILOT-CAL (weekdays 0–5, `hours_per_day` 10) | supported |
| Productivity factor 1.00 baseline | `productivity_factor` BASELINE-1.00 | supported |
| Pipe-fitting productivity (synthetic) | `productivity_factor` PIPEFIT-SYNTH, scope `E.06`, **1.00 in v1**, revised to 1.10 as v2 (§15) | supported |
| Crane minimum hire 1 day; standby rule (test-only) | `plant_hire_terms` CRANE-TERMS (1 day; standby 1 day at 50 %) | supported |
| Annual escalation 4 % | `escalation_profile` ESC-4PCT (base date 2026-10-01) | supported (report only) |
| Payment terms 30 days, retention 5 %, bond 10 % | `payment_terms` PAY-SYNTH; the unspecified mandatory fields (advance 0, release-at-completion 50 %, defects 12 months, certification lag 0, supplier lag 1, financing 0, bond fee 0) carry the label SYNTHETIC TEST ASSUMPTION | supported |
| Site indirects 8 %, home-office 3 % | approved indirect items `IND-SITE`, `IND-HO` (`percent_of_direct`, base = ALL direct cost) | no governed kind; engine input is an approved indirect |
| Contingency 5 %, target profit 7 % | approved commercial policy POL-SYNTH (contingency 5 % of direct+indirect; markup 7 % on total cost) | no governed kind; engine input is the approved policy |
| VAT 15 % | tax category VAT-STD approved by TEST ACTOR with evidence "TEST ONLY … NOT a verified tax determination" | before approval the estimate was `Preliminary — Incomplete` ("Tax rate unresolved") |
| FX | SAR-only; none required | not applicable |


## 9. Assemblies, norms and man-hours (stages 5, 9)
Explicit synthetic norms are stored in each assembly's `notes` and as assembly lines (no norm lives in application code). Three required assemblies + two valve assemblies:

| assembly | resource quantities (SYNTHETIC norms) | calculated unit cost (hand) |
|---|---|---|
| ASM-DN100-INST (m) | pipe DN100 + 2 % waste (candidate SAR 190/m, replaced by the selected quotation rate); welder 0.50 h; fitter 0.60 h; helper 0.50 h; consumables 0.667 dia-in (SAR 12) | per metre = 192×1.02 + 0.5×65 + 0.6×55 + 0.5×32 + 0.667×12 = 195.84 + 32.50 + 33.00 + 16.00 + 8.004 = 285.344 (pipe at the selected Supplier A quotation rate 192) |
| ASM-DN50-INST (m) | pipe DN50 + 2 % waste (SAR 110/m); welder 0.25 h; fitter 0.35 h; helper 0.30 h; consumables 0.333 dia-in | per metre = 112×1.02 + 16.25 + 19.25 + 9.60 + 3.996 = 163.336 (pipe at the selected rate 112) |
| ASM-SUPPORT-KG (kg) | support steel + 5 % waste (SAR 15/kg); welder 0.02 h; fitter 0.03 h; helper 0.03 h; paint material 0.01 m2 | per kg = 16×1.05 + 1.30 + 1.65 + 0.96 + 0.14 = 20.85 (steel at the selected rate 16.0; paint material 14) |

Application results (after the supply rates came from the selected quotation): P-002 = 240 × 285.344 = 68,482.56; P-001 = 120 × 163.336 = 19,600.32; P-014 = 650 × 20.85 = 13,552.50 — all equal to the hand calculation. Valve assemblies: gate valve 1,320 + 1.5×55 + 1.5×32 = 1,450.50 (×6 = 8,703.00); check valve 1,700 + 130.50 = 1,830.50 (×4 = 7,322.00). Resource unit rates are supply-only; installed BOQ rates are kept in the separate `SYN-P-nnn` resources, so **the same material is never counted twice**: PRJ-9001 prices only installed rates, PRJ-9002 prices only assemblies.
Man-hours: **1,220 h** = welder 320 + fitter 400 + helper 500 (equal to the labour lines of the BOQ). Loading: scheduled 1,220, unscheduled 0, tie-out true. Hours were traced to WBS `3.0`. Plant hire minimum/standby applied only to the crane (configured), not the forklift.

## 10. WBS and cost-code reconciliation (stage 4)
30/30 lines have a valid cost code and a mapped assembly; WBS nodes 1.0–8.0 created (8.0 stays empty: indirects are not BOQ lines). CBS top-level sum **366,261.00**, leaf sum **366,261.00**, WBS sum **366,261.00**, all equal to the direct cost; tie-outs `{'cbs': True, 'wbs': True, 'crosswalk': {'FICTIONAL-CLIENT-CBS': True}}`. The fictional client system `FICTIONAL-CLIENT-CBS` (30 codes) ties out. Unmapped lines are visible in the negative control (N-2 `UNPRICED_ITEM`, Critical).

| cost code | total (SAR) |
|---|---|
| A | 63,570.00 |
| A.01 | 12,000.00 |
| A.03 | 17,000.00 |
| A.06 | 4,050.00 |
| A.07 | 16,900.00 |
| A.08 | 13,620.00 |
| D | 7,560.00 |
| D.07 | 7,560.00 |
| E | 269,956.00 |
| E.06 | 231,536.00 |
| E.08 | 38,420.00 |
| F | 25,175.00 |
| F.09 | 11,875.00 |
| F.10 | 13,300.00 |


## 11. Programme (stage 9)
Calendar: Monday–Saturday from 2026-11-02, 10 h/day (approved parameter). Result: **29 working days**, finish **2026-12-04** = **33 calendar days**, i.e. the 30-calendar-day planning assumption is **exceeded by 3 days**; the assumption was not forced onto the calculation.
Critical path (zero float): MOB → PROC → INST → WELD → NDT → HYDRO → PAINT → FINAL. Driving path: PROC → INST → WELD → HYDRO → PAINT → FINAL. `MOB` shows zero float and is listed as critical although it is not on the driving path (`PROC` is linked start-to-start to it); `SUPFAB` has 2 days of float.

| task | ES | EF | float | critical | start | finish |
|---|---|---|---|---|---|---|
| MOB | 0 | 3 | 0 | yes | 2026-11-02 | 2026-11-04 |
| PROC | 0 | 10 | 0 | yes | 2026-11-02 | 2026-11-12 |
| SUPFAB | 3 | 8 | 2 | no | 2026-11-05 | 2026-11-10 |
| INST | 10 | 18 | 0 | yes | 2026-11-13 | 2026-11-21 |
| WELD | 15 | 20 | 0 | yes | 2026-11-19 | 2026-11-24 |
| NDT | 17 | 20 | 0 | yes | 2026-11-21 | 2026-11-24 |
| HYDRO | 20 | 23 | 0 | yes | 2026-11-25 | 2026-11-27 |
| PAINT | 23 | 27 | 0 | yes | 2026-11-28 | 2026-12-02 |
| FINAL | 27 | 29 | 0 | yes | 2026-12-03 | 2026-12-04 |

Links used: FS, SS (MOB→PROC), SS+3 and FF+2 (INST→WELD overlap), SS+2 (WELD→NDT). **SF (start-to-finish) was not exercised** in this programme (the engine supports it and the unit tests cover it); no logic was unsupported. The duration proposal from the schedule was approved by a TEST ACTOR and feeds duration-based items (none are used here: both indirects are percentage-based).

## 12. Indirects, escalation, risk, cash flow, profit, tax (stage 13) — cost bases

| step | SAR | basis |
|---|---|---|
| Direct cost (D) | 366,261.00 | approved rates × quantities (+ 900.00 standby on P-020) |
| Eligible base for the percentage indirects | 302,691.00 | E/D/F scope: 302,691.00 = D − division A (preliminaries, 63,570.00 incl. standby); explicit rules approved in the project |
| Site indirects | 24,215.28 | 8 % × eligible base |
| Home-office overhead | 9,080.73 | 3 % × eligible base |
| Indirect total (I) | 33,296.01 | was 40,288.71 on the whole direct cost (previous run) |
| Contingency | 19,977.85 | 5 % × (D + I); applied once; no risk adder; no escalation adder |
| Total cost (T) | 419,534.86 | D + I + contingency |
| Selling price (markup 7 %) | 448,902.30 | T × 1.07 (method label: markup on total cost) |
| Net price after commercial rounding | 448,902.30 | no discount |
| Tendered pricing schedule total | 448,905.05 | unit-rate rounding variance 2.75 (reported, bounded) |
| VAT 15 % (synthetic parameter) | 67,335.76 | 15 % × tendered schedule total = 67,335.76 (tax base is the **schedule**, not the net price) |
| Final payable | 516,240.81 | schedule + VAT |

The commercial chain was re-derived independently in Decimal before comparison; every figure above matches (`chain_matches_independent: true`).
**Double-count review.** Quotations are not added on top of installed rates (PRJ-9002 is a separate project). Contingency is applied once, and the Monte Carlo output is a *proposal* that changes nothing. Escalation is **not** in the selling price (no policy escalation adder; the 4 % profile feeds only the report). Plant hire counted once (rate line + configured standby; mobilisation/demobilisation days are 0). **Percentage-indirect base (finding O-5, now closed):** the indirect eligibility base states that division A (supervision P-030, mobilisation P-029, crane/forklift, scaffolding, PMI/RT in A.08) is excluded, so those BOQ lines are no longer inside the 8 % / 3 % base; the `indirect_base` report lists eligible, excluded and unclassified cost by cost code, BOQ line and kind (unclassified: 0.00).

**Escalation (4 %, base 2026-10-01), after the time-allocation rules (§4b):** engine total 1,798.67 on a base of 366,261.00 (**all** direct cost; previously 328,311.00 with 37,950.00 not escalated). Independent check of the factors: 1.04^((months from 1 Oct to mid-month)/12) = 1.04^((1+14/30)/12) = 1.004805 (Nov) and 1.04^((2+14/30)/12) = 1.008095 (Dec) ✓; status `COMPLETE for the cost within profile scope`.
**Risk (seed 20260101, 5000 simulations; three SYNTHETIC risks, probability 100 %):** SAR ranges were derived from the estimate's own subtotals because the engine accepts SAR ranges only: material 0/8,446.24/21,115.60 (0/4/10 % of 211,156.00), productivity 0/2,940/8,820 (0/5/15 % of labour 58,800.00), rework 0/5,000/15,000. Expected value (hand: (0+8,446.24+21,115.60)/3 + (0+2,940+8,820)/3 + 20,000/3) = **20,440.61**; simulated mean 20,403.43, P10 13,080.13, **P50 20,273.07, P80 25,355.38, P90 28,023.02**; re-run with the same seed identical: **True**. Proposed provision at P80 25,355.38 vs policy contingency 19,977.85 (difference 5,377.53) — proposal only, not applied. Limitations: independent risks, no correlation, no schedule logic, triangular shapes assumed by the brief. This is a software exercise, not a forecast.
**Cash flow (payment terms PAY-SYNTH), reconciled under the documented conventions** (indirects are paid with the direct cost they follow; contingency, risk allowances and margin are not cash-out; only allocated cost is paid and valued):

| item | SAR |
|---|---|
| Net price | 448,902.30 |
| Valued price (= net price: nothing unallocated) | 448,902.30 |
| Allocated direct cost | 366,261.00 |
| Indirect cost / cash factor | 33,296.01 / 1.090908 |
| Cash paid (direct × factor) | 399,557.01 |
| Cash received | 448,902.30 |
| Retention withheld (5 % × price) | 22,445.11 |
| Interest | 0.00 |
| Closing balance | 49,345.29 |
| Reserve not cash-out (contingency + risk) | 19,977.85 |
| Identity checks | valuations sum to the valued price: OK; cash received equals the valued price: OK; cash paid equals allocated direct cost x (1 + indirect/direct): OK; closing balance = valued price - cash paid - interest: OK |

Hand check: closing balance = valued price − cash paid − interest = 448,902.30 − 399,557.01 − 0 = 49,345.29 (= margin 29,367.44 + contingency 19,977.85, since indirects are paid and contingency is not). Retention 5 % × 448,902.30 = 22,445.11 ✓. Performance-bond cost 0.00 (fee percentage is a test value of 0); bond months 14 (2 programme months + 12 defects).

## 13. Take-off templates (stage 10, project PRJ-9003)
Industrial pack loaded (definitions only, no prices). For each of six templates the driver is the **human BOQ quantity**; factors are SYNTHETIC mechanical-test norms approved by a TEST ACTOR in the project; every application left its item `Pending Review`, no item priced until a person decides, and the measured BOQ quantities were unchanged.

| BOQ item | template | driver (human quantity) | derived quantities (formula: driver × factor) | slots skipped (no unit-compatible library resource) |
|---|---|---|---|---|
| P-016 | piping.pipe_fab_install | 420 inch_dia | fab_labour=210.000000 (LIB-LAB-WELDER); erect_labour=168.000000 (LIB-LAB-FITTER); fit_up_labour=126.000000 (LIB-LAB-HELPER); pipe_material=210.000000 (LIB-PIPE-DN100); crane_plant=4.200000 (LIB-PLT-CRANE) | welding_consumables |
| P-023 | piping.weld_joint | 42 joint | welder_labour=63.000000 (LIB-LAB-WELDER); fitter_labour=42.000000 (LIB-LAB-FITTER); grinding_labour=10.500000 (LIB-LAB-HELPER) | consumables, ndt, pwht |
| P-014 | piping.supports | 0.650 t | fab_labour=26.000000 (LIB-LAB-WELDER); install_labour=19.500000 (LIB-LAB-FITTER); steel=682.500000 (LIB-MAT-SUPPORT) | paint |
| P-027 | coating.surface | 180 m2 | blast_labour=54.000000 (LIB-LAB-HELPER); apply_labour=36.000000 (LIB-LAB-HELPER) | primer, intermediate, topcoat, blast_media, inspection |
| P-028 | insulation.surface | 95 m2 | install_labour=76.000000 (LIB-LAB-FITTER) | insulation, cladding, fixings |
| P-012 | piping.valve_install | 6 nr | install_labour=9.000000 (LIB-LAB-FITTER); test_labour=3.000000 (LIB-LAB-HELPER) | gaskets_bolting |

**Discrepancies / human decisions required:** (1) derived labour (e.g. 504 h for P-016 plus 63+42+10.5 h for 42 welds) is a *different decomposition* from the BOQ's 1,220 h of labour lines — a person must decide whether template output supersedes or complements those lines; applying both would double count. (2) The weld-count driver was taken from the radiographic-test line (42 welds) and may understate total joints. (3) Derived pipe 210 m (DN100) ≠ BOQ DN100 pipe 240 m; derived steel 682.5 kg = 650 kg × 1.05 (the 1,050 kg/t factor). (4) Slots with no compatible resource (consumables priced per inch-diameter vs a mass slot; NDT/PWHT as subcontract; paint volumes; insulation material) were skipped explicitly and cost nothing — they are not covered. **This is structural/mechanical validation of the engine path; it is not validation of any template against real practice.**

## 14. Basis of Estimate and completeness (stages 14, 15)
BOE generated by the application (`generate_boe`, files BoE_PRJ-9001_draft01.md, BoE_PRJ-9001_draft01.docx). Sections present: project scope, exclusions/scope register, BOQ source, estimate date and currency, synthetic rate designation, assemblies, productivity assumptions, programme, indirects/duration, commercial, risk, classification, client profile / no compliance claim, validation-only statement. Missing: none. The validation-only statement appears as a banner via the project note (D-3). The BOE contains 6 placeholders for judgement sections that only a person can write — by design they are not filled. The estimate classification is **not determined**: there is no approved classification scheme (governed kind `classification_scheme` ships empty) and none was invented. No client profile is linked: "no compliance statement can be made". The BOE was generated at the frozen v1 state (before the §15 changes).

**Reconciliation / completeness on the main project (PRJ-9001), before exceptions:** High PLANT_HIRE_DAYS; High PLANT_HIRE_DAYS; Medium OFFER_MISSING; Medium POSSIBLE_DUPLICATE_INDIRECT; Medium UNAPPROVED_ADOPTED_ASSUMPTION; Low SYNTHETIC_DEMO. Two High `PLANT_HIRE_DAYS` findings come from the crane and forklift (BOQ days differ from the programme window, §4b); they blocked final approval (`RECON_BLOCKED`) until a Commercial Approver TEST ACTOR accepted them with a documented reason (an Estimator attempting it was refused, `EXCEPTION_ROLE`). `POSSIBLE_DUPLICATE_INDIRECT` (Medium, an existing keyword-overlap rule) and `OFFER_MISSING` are non-blocking; the Medium `UNAPPROVED_ADOPTED_ASSUMPTION` stays open: the mandatory company assumptions have no values (none may be invented).

**Negative control PRJ-9004 (not a demo project):**

| check | result |
|---|---|
| state | Preliminary — Incomplete |
| blockers | 3 BOQ item(s) are unpriced or incomplete.; No computable commercial policy. |
| engine exception codes | MISSING_RATE, UNPRICED_ITEM |
| unmapped / unpriced items | N-2, N-3, N-4 |
| reconciliation findings | Critical MISSING_RATE; Critical POLICY_UNAPPROVED; Critical SYNTHETIC_IN_REAL_PROJECT; Critical UNPRICED_ITEM; Critical UNPRICED_ITEM; Critical UNPRICED_ITEM; High BOQ_CHANGE_PENDING; High INDIRECT_UNAPPROVED; High UNIT_INCONSISTENT; Medium OFFER_MISSING; Medium UNAPPROVED_ADOPTED_ASSUMPTION; Low PARAMETER_UNAPPROVED |
| `approve_version` | ESTIMATE_PRELIMINARY |
| tender-export approval | ESTIMATE_NOT_APPROVED |
| `export_submission` | EXPORT_NOT_APPROVED |
| preliminary export banner | PRELIMINARY - NOT FOR SUBMISSION | CONTAINS SYNTHETIC DATA |
| owner requirements | `compliance` report: No client profile is linked to this project: no compliance statement can be made. |
| classification | No approved classification scheme: enter the scheme the company/client works to (governed parameter 'classification_scheme') and have it approved. |

Covered by the control: missing rate (`MISSING_RATE`), unmapped line (`UNPRICED_ITEM`), invalid unit (`UNIT_INCONSISTENT` + `BOQ_CHANGE_PENDING`), unapproved policy/indirect/parameter/assumptions, synthetic data in a real project (`SYNTHETIC_IN_REAL_PROJECT`, Critical — cannot be waived), missing owner requirements, unverified tax (§8: "Tax rate unresolved" before approval), missing offer. **A preliminary estimate with unresolved mandatory inputs cannot be represented as a complete approved tender.**

## 15. Freeze and replay (stage 16)

| check | result |
|---|---|
| v1 fingerprint | `87f41514c281c89539d5bcb9b1d424ec5040e3f4c18f5dac45d978d35fdb5d6b` |
| v1 totals | commercial_net_price 448902.3, direct_cost 366261, final_payable 516240.81, indirect_cost 33296.01, selling_price_pre_tax 448905.05, tax 67335.76, total_cost 419534.86 |
| v1 status | Approved |
| changes made | productivity_factor PIPEFIT-SYNTH 1.00 -> 1.10 (new version, approved by TEST ACTOR); SYN-P-017 welder rate 65 -> 70 (new rate version, approved by TEST ACTOR) |
| current fingerprint after changes | `be58fb017f4cfc76c9adcb8b8cadd00aaae9d6228d71770e18c651dac9e32d81` (different) |
| current totals after changes | direct_cost 373901.00, indirect_cost 34136.41, total_cost 428439.28, selling_price_pre_tax 458433.09, commercial_net_price 458430.03, tax 68764.96, final_payable 527198.05 |
| v1 row unchanged | True |
| replay of v1 after changes | ok=True, differences none, fingerprint `87f41514c281c89539d5bcb9b1d424ec5040e3f4c18f5dac45d978d35fdb5d6b` = frozen |
| direct-cost-only replay | ok=True (366261) |
| snapshot drift report | ok; `newer_rates_available`: [{"resource_id": "SYN-P-017", "used_rate_id": 944, "used_price": "65", "newer_rate_id": 1228, "newer_price": "70"}] |
| export of frozen v1 after the change | EXPORT_BLOCKED |
| audit chain | ok, 809 rows verified |

The new inputs moved the current direct cost by +7,640.00 (hours ×1.10: welder 352 h × 70, fitter 440 h × 55, helper 550 h × 32 vs 20,800 + 22,000 + 16,000), exactly as hand-computed; the frozen version still reproduces its original totals. A new frozen version v2 (Draft) was created from the changed inputs; v1 stays `Approved`.
**Take-off replay (16b, PRJ-9003):** frozen state `Complete`, direct 102876.5. Revising the approved `mto_factor` flagged the application stale (`[['P-023', 'piping.weld_joint', ['FACTORS_CHANGED']]]`) but did **not** change the estimate until a person re-applied the template and re-approved its pricing (then 104,241.50); replay of the frozen version reproduced the original fingerprint and totals. Landed cost/FX and escalation are not part of this replay (**NOT TESTED**: escalation is a read-only report and not an estimate input; the brief is SAR-only).

## 16. Export and gating (stage 17)
Preliminary export banner: `DRAFT - NOT YET APPROVED FOR SUBMISSION | DEMONSTRATION PROJECT - SYNTHETIC DATA - NOT A MARKET QUOTE`. Gate sequence on PRJ-9001 (all approvals by TEST ACTORS): approve_before_exceptions → RECON_BLOCKED; self_role_cannot_approve → PERMISSION_DENIED; ai_cannot_approve → AI_CANNOT_APPROVE; tender_export_approval_before_estimate_approved → ESTIMATE_NOT_APPROVED; export_without_approval → EXPORT_NOT_APPROVED; exception_by_estimator_refused → EXCEPTION_ROLE; tender_export_before_offer → OFFER_NOT_APPROVED.
After the exceptions, the estimate approval, an approved offer and a TEST ACTOR tender-export approval, `export_submission` produced a **demonstration** package in the scratch workspace (pricing schedule `*_DEMONSTRATION.xlsx`, estimate report, letter of offer, reconciliation report). Its pricing-schedule banner now reads: *DEMONSTRATION EXPORT - NOT SUBMISSION READY - NOT APPROVED FOR ANY REAL TENDER | approvals by: test principals in environment 'test' | DEMONSTRATION PROJECT - SYNTHETIC DATA - NOT A MARKET QUOTE*. The wording is generated from the verified approval chain (actor types and environment), so it can no longer say "approved by an authorised human reviewer" for a test approval; `exports.submission_ready` is 0 for all of them and `exports.readiness` = `demonstration`. **Nothing was sent, published or submitted.**
Workbook: the master workbook (28 sheets, including Vendor Quotations, Quote Comparison, Risk Register, Reconciliation, Approval Log) exported for PRJ-9001 and recalculated with LibreOffice: structure ok, 192 formulas, **0 formula errors, 0 mismatches**. The BOE is a separate `.md`/`.docx` in `5. Estimate & Cost Build-Up/basis_of_estimate`; the Monte Carlo output is not a workbook sheet (only the register is). PRJ-9001 has no quotations (those live in PRJ-9002), so its quotation sheets are empty. Microsoft Excel was **not** available.

## 17. UI / API / CLI evidence

| interface | result |
|---|---|
| CLI reports | rollup, manhours, schedule, project verify-snapshot, audit-verify, coverage, param list, rates pending — all exit 0; CLI man-hours total equals the engine's, CLI rollup tie-out true: {"cli_manhours_total": "1342.0", "engine_manhours_total": "1342.0", "cli_rollup_tie_out": {"cbs": true, "wbs": true, "crosswalk": {"FICTIONAL-CLIENT-CBS": true}}, "cli_programme_working_days": "29"} |
| REST API | `/api/projects/PRJ-9001/estimate` totals equal the engine's current totals; rollup tie-out `{"cbs": true, "wbs": true, "crosswalk": {"FICTIONAL-CLIENT-CBS": true}}`; versions [[1, "Approved"], [2, "Draft"]]; audit verify ok (835 rows) |
| API permission checks | Viewer `approve_tender_export` → [403, 'PERMISSION_DENIED']; Estimator `approve_tender_export` → [403, 'PERMISSION_DENIED']; Estimator `approve_rate` → [403, 'PERMISSION_DENIED'] |
| UI (TestClient, signed-in Estimator) | /projects/PRJ-9001/ 200; /projects/PRJ-9001/estimate 200; /projects/PRJ-9001/boq 200; /projects/PRJ-9001/reconciliation 200; /projects/PRJ-9001/analysis 200; /projects/PRJ-9001/analysis/rollup 200; /projects/PRJ-9001/analysis/schedule 200; /projects/PRJ-9001/completeness 200; /projects/PRJ-9001/workspace 200; /projects/PRJ-9002/quotes 200; no tracebacks; every page shows the SYNTHETIC designation; the estimate page shows the direct-cost total |


## 18. Defects found, fixes and tests

| id | finding | fix | regression test |
|---|---|---|---|
| D-1 | **Fixed (previous pass).** Synthetic rate candidates were published as `Published Market Price` with no synthetic marker. | `SYNTHETIC_DATA` flag; published as Synthetic Demonstration Rate | `test_synthetic_flag_survives_publication_as_a_synthetic_rate_not_a_market_price` |
| D-2 | **Fixed (previous pass).** `param import` had no dry run. | `--dry-run` in a rolled-back transaction | `test_governed_csv_dry_run_validates_without_writing_anything` |
| D-3 | **Fixed (previous pass).** The BOE could not carry a project's own validation-only statement. | `PROJECT NOTE` banner | pilot stage 14 |
| D-4 | **Fixed (release-blocking).** Cost not tied to a programme activity was excluded from cash-out and escalation while the valuations spread the whole price (SAR 37,950.00 here; closing balance overstated). | explicit approved `time_allocation` rules; unallocated cost exposed by line; INCOMPLETE labels; only allocated price valued; financing proposals refused; High `TIMEPHASING_INCOMPLETE` finding; documented cash-flow conventions and identity checks | `tests/unit/test_time_allocation.py`; pilot stage 13d |
| D-5 | **Fixed.** The 8 % indirect included supervision/mobilisation/preliminaries BOQ lines with no way to exclude them or detect the overlap. | `eligibility` base on percentage indirects and commercial adders; `indirect_base` report; `INDIRECT_BASE_OVERLAP` (High) and `INDIRECT_ELIGIBILITY_UNSPECIFIED` (Medium); legacy bases unchanged and reported as unspecified; approved items/frozen estimates untouched | `tests/unit/test_indirect_eligibility.py`; pilot stage 11 |
| D-6 | **Fixed.** Day-priced plant was handled through an hours-based assumption (`PLANT_UNIT`) and a High exception that only a Commercial Approver could waive; working days, calendar days, minimum hire, standby, mobilisation were not distinguished. | extended `plant_hire_terms` (billing basis, programme activities, mobilisation/demobilisation days); `plant_hire` report reads the on-site window from the programme; `PLANT_HIRE_DAYS` (High) and `PLANT_TERMS_MISSING` (High); `factor_unit` declares a day basis | `tests/unit/test_plant_hire.py`; pilot stage 11 |
| D-7 | **Fixed (release-blocking).** A demonstration/synthetic project could reach `SUBMISSION READY` output with test-actor approvals, and the banner described an approval as coming from an authorised human reviewer. | durable `users.actor_type`, `approvals.actor_type`/`environment`, `recon_exceptions.accepted_actor_type`; `services/readiness.py`; production readiness needs registered human approvers in a production environment, no demo/synthetic data, verifying audit entries; banner states the real status; enforced in the services (UI/API/CLI share them) | `tests/approvals/test_actor_isolation.py`, `tests/integration/test_actor_isolation_api.py`; pilot stage 19 |


**Observations (not fixed or accepted by design):**

| id | observation |
|---|---|
| O-1 | Rates with `Unverified` confidence raise `RATE_WARNING` exceptions and a procurement 're-confirm' need for every priced resource; the pilot imported synthetic rates at `Medium` to keep the comparison clean. |
| O-3 | Loading, escalation and cash-flow reports still expose 28-digit Decimal residue (e.g. 319.9999999999999999999999999 h); tie-outs use a tolerance. Cosmetic; displayed values should be quantised. |
| O-7 | Supplier selection is package-level only (no split award); delivery adjustments are package-level. |
| O-8 | Programme: no resource levelling; the SS-linked MOB shows as critical although it is not on the driving path. |
| O-9 | Tax is computed on the tendered schedule total, not the net price; the difference is the reported rounding variance. |
| O-10 | The allocation rules, eligibility rules and plant terms used in the pilot are SYNTHETIC test decisions; a real project needs company/contract inputs for each (no default is supplied). |
| O-11 | A person with administrator or database access can register a `human` user or edit rows; actor types are a control against mistakes and test data, not identity assurance. |
| O-12 | Only day-priced plant is compared with the programme window; week/month-priced plant is reported as unsupported. |


## 19. Skipped steps and limits of this run
* Client requirements / owner profile: not run (no controlled owner document; nothing is claimed about any client or standard).
* Landed cost, FX conversion and hedge cover: not run (SAR-only brief).
* Quotation-line **file** import (`import_quotation_lines`): not run in this pilot; lines were entered as structured data.
* AI-assisted suggestions: not run (no live API, none needed).
* Microsoft Excel: not available; LibreOffice only.
* Incomplete quotations and missing supporting evidence were not scripted as separate negative cases in the final run (an incomplete quotation was seen incidentally during development: coverage 5/10, not like-for-like); the existing suites cover them (`tests/integration/test_full_workflow.py`, `tests/approvals/`).
* Programme logic SF (start-to-finish) links were not exercised (supported; unit-tested).
* Performance/scale: a 30-line BOQ only.
* Real approvals: none. Every 'approval' is a TEST ACTOR.

## 20. What remains blocked by real company data or human approval
Everything that makes an estimate usable: real approved rates and quotations, company productivity/norms and wages, a real calendar, commercial policy, payment terms, tax verification by a competent person, an approved classification scheme, owner requirements and attestations, the mandatory company assumptions (currently without values), and the human approvals themselves (estimate, offer, tender export). See [PILOT_READINESS.md](PILOT_READINESS.md). The synthetic numbers here must not be reused.

## 21. Three most important remaining defects / verification steps
1. **Repeat this pilot with real, authorised data** on a 30–100 line package and registered human approvers in a production environment (PILOT_READINESS §4); compare with the company's independent estimate line by line. Until then nothing is validated for estimating accuracy and no output can be submission ready.
2. **Display precision (O-3) and rate-confidence noise (O-1):** quantise time-phased report values and decide how `Unverified` approved rates should surface (warning vs procurement need).
3. **Identity assurance (O-11):** MFA/SSO and administrator separation of duties if the suite is ever shared beyond a trusted team; and company-specific allocation/eligibility policies loaded as approved parameters.

