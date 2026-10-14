# Pilot readiness (real-data pilot)

Purpose: say exactly what a person must supply, approve and check before the suite is used on a **representative real BOQ**, and what still stops its output from being a live commercial submission. Nothing here is a default or a recommendation of a value: **no price, productivity, wage, factor, calendar, tax rate or client standard is shipped**, and none is to be invented to make a pilot run. Read [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) first.

Capability counts are generated from the records, not typed here: see [ESTIMATING_CAPABILITY_MATRIX.md](ESTIMATING_CAPABILITY_MATRIX.md).

## 1. Preliminary vs approved estimate

| | Preliminary | Complete with Provisional Inputs | Complete (approved basis) |
|---|---|---|---|
| Engine state | `Preliminary — Incomplete` | `Complete with Provisional Inputs` | `Complete` |
| Arises when | any blocker (missing rate, unmapped line, unapproved basis) **or** the view was run with `include_unapproved` | all lines priced, but at least one rate has *project-Provisional* approval (Estimator may grant, project-scoped only) | all lines priced from Approved, in-date, in-region, real-price-type rates; FX/tax approved |
| May be used for | internal what-if, gap finding, discussion | internal review with the provisional items visible | candidate for the final gate |
| Missing rate | line unpriced, `amount=None` (never 0) | same | not allowed (blocker) |
| Unapproved governed parameter | applied **and loudly flagged** only in a preliminary view; ignored (baseline) otherwise | n/a | ignored until approved |
| Can be frozen / approved / exported for tender | **No** | **No** (reconciliation flags provisional inputs; the Commercial Approver decides) | Only after the final gate + Commercial Approver's estimate approval + tender-export approval |

A preliminary estimate is a **to-do list with arithmetic**, not a price. Every preliminary output carries the state label; client-form exports of a preliminary estimate are watermarked as such.

## 2. Minimum real data for a representative pilot BOQ

Choose a BOQ that exercises one trade end to end (suggestion: a piping/mechanical package, because the industrial pack, take-off templates and landed-cost/labour rules are all in play) of **roughly 30–100 priced lines**, with quantities **already measured by a person**. The suite never measures.

| # | Input | Minimum for the pilot | Where it goes | Template |
|---|---|---|---|---|
| 1 | Measured BOQ (item no., description, unit, quantity) | the whole pilot package | `project import-boq` / BOQ import | `templates/boq_import_template.xlsx` |
| 2 | Cost-code mapping of every BOQ line | every line | BOQ mapping (Estimator proposes, Estimator/Commercial approve) | in the BOQ template |
| 3 | Approved resource rates for **every resource the mapped assemblies/take-off use** | 100 % of used resources; a missing one keeps the line unpriced | rate candidates → publication → `approve_rate` | `templates/pilot/rates_template.csv`, `templates/resource_rate_template.xlsx` |
| 4 | Supplier / subcontract quotations backing the above | at least one quotation (with validity, VAT and delivery basis) per bought-out and subcontract item | RFQ → quotation lines → levelling → selection | `templates/pilot/quotation_lines_template.csv`, `templates/vendor_quote_template.xlsx` |
| 5 | Productivity / take-off factors (labour hours per unit, consumption, wastage) | one approved factor per slot of every take-off template used; one per assembly component used | governed parameters `mto_factor`, `productivity_factor`; assembly components | `templates/pilot/governed_parameters_template.csv` |
| 6 | Wage/crew rates, statutory labour on-costs, workforce mix | every labour resource used; `labour_statutory` rules the company applies | rates + governed `labour_statutory`, `national_workforce_target` | same CSV |
| 7 | Plant hire terms | each plant resource used | governed `plant_hire_terms` | same CSV |
| 8 | Project calendar (start, working weekdays, holidays) | the contract/client calendar | governed `calendar` | same CSV |
| 9 | Programme logic (tasks, durations, predecessors) | enough to drive duration and loading | schedule tasks / programme import | schedule import |
| 10 | Indirects (site staff, facilities, bonds, insurance) | amounts and bases from company records | indirects (amount-less drafts until filled) | indirects sheet |
| 11 | Commercial policy (overhead, profit, contingency, discount, rounding) | one approved policy | commercial policy (Commercial Approver only) | — |
| 12 | Tax category and FX | VAT category verified against current official guidance; FX only if non-SAR prices are used | tax / FX records (seeds ship *Pending Review*) | — |
| 13 | Payment terms, retention, bonds, escalation, hedge | those the contract states | governed `payment_terms`, `escalation_profile`, `hedge_cover` | same CSV |
| 14 | Risk ranges / reserve rules | those the company uses | governed `range_item`, `reserve_rule` | same CSV |
| 15 | Client requirements (if an owner profile applies) | the requirements that will be checked, each with document + clause | client profile | `templates/pilot/client_requirements_template.csv` |
| 16 | Tender documents, clarifications, exclusions | the real issue set for the pilot project | project workspace `1. Tender Documents`, clarification register | `templates/clarification_register_template.xlsx` |
| 17 | Independent comparison figure (the company's own previous estimate or a manual build-up of the same package) | one | outside the suite, used for the pilot acceptance in §4 | — |

The library ships **empty**: `python -m app.cli coverage` reports 927 catalogue resources, 0 with an approved rate. Part of the pilot is raising that coverage *for the resources the pilot BOQ uses*, from evidence.

## 3. Missing inputs and the responsible human owner

"Owner" is the role that must **supply the evidence and take the approval decision**; the suite enforces the approver roles server-side (`app/approvals/policy.py`, `app/estimators/param_kinds.py`). Named individuals are for the company to assign.

| Missing today | Supplies evidence | Approves | Status |
|---|---|---|---|
| Resource rates (material, equipment, subcontract) | Procurement Reviewer | Procurement Reviewer / Commercial Approver (`approve_rate`; Estimator may only grant project-Provisional) | **Missing – 0 approved** |
| Labour wage rates and crew costs | Estimator with HR/commercial records | Procurement Reviewer / Commercial Approver | **Missing** |
| Plant hire terms | Procurement Reviewer (hire contracts/quotes) | Procurement Reviewer / Commercial Approver | **Missing** |
| Productivity and take-off factors | Estimator (company site records) | Estimator / Commercial Approver / Administrator | **Missing – library empty** |
| Statutory labour rules, nationalisation targets | Commercial / HR with the authority reference | Commercial Approver / Administrator | **Missing** |
| Calendar (weekdays, holidays) | Estimator from the contract | Estimator / Commercial Approver | **Missing** |
| Commercial policy, payment terms, escalation, hedge, reserve rules | Commercial Approver | Commercial Approver / Administrator | **Missing** |
| VAT category verification and FX | Commercial Approver / finance | Commercial Approver (tax); Procurement/Commercial (FX) | Seeded *Pending Review*, unverified |
| Client requirements and any compliance statement | the person who holds the owner's controlled documents | Commercial Approver (profile) + attestation by a person | **Missing – no owner profile loaded; the suite states nothing about compliance with any client's standards** |
| Quotations | Procurement Reviewer (from suppliers) | Procurement Reviewer / Commercial Approver | **Missing** |
| Reconciliation exceptions | Estimator/Procurement raise | Per-severity limits; Critical can never be waived | n/a until data exists |
| Tender-export approval | — | Commercial Approver / Administrator only | n/a until a Complete estimate exists |

## 4. Pilot workflow stages and acceptance criteria

Each criterion is checkable in the product; "automated check" lists the test that already proves the *mechanism* with SYNTHETIC data (it does not prove your real data is right).

| Stage | What happens | Acceptance criterion (real data) | Mechanism proven by |
|---|---|---|---|
| 0 Setup | `init`, create project, workspace folders created, no `projects/*` committed | project workspace has the 10 fixed folders; `project.json` matches the DB | `tests/workspaces/test_workspaces.py` |
| 1 Documents | originals placed in `1. Tender Documents`; `project index` | every tender file inventoried with a hash; originals unmodified | `test_workspaces.py` (indexer) |
| 2 BOQ import | measured BOQ imported as a draft | rejected rows = 0 or each explained; line count and quantity total equal the source file | `tests/imports/test_boq_import.py` |
| 3 Mapping | every line gets a cost code/WBS and a unit that converts | 0 unmapped lines; 0 `unit_status` ≠ ok, or each has a person's decision | `tests/imports/test_boq_import.py`, `test_industrial_flow.py` |
| 4 Rates & quotations | candidates from evidence → published *Pending Review* → approved by a human | for every used resource: an Approved, in-date rate with a source/evidence and original price preserved; **index sources refused as prices** | `tests/sources/test_rate_pipeline.py`, `tests/approvals/` |
| 5 Governed inputs | productivity/take-off factors, calendar, hire terms proposed (Draft), submitted, approved | every factor has a source; no Draft/Pending value used in the approved view | `tests/unit/test_governed_params.py`, `test_pilot_templates.py` |
| 6 Direct cost | build-up per line | each line's amount equals an independent spreadsheet re-computation of the same inputs to the rounding rule; no line silently 0 | `tests/unit/test_direct_cost.py`, `test_full_workflow.py` |
| 7 Take-off derivation (if used) | derive resource quantities from the *human* BOQ quantity | derived quantity = BOQ quantity × approved factor; pricing decision approved by a person; no double pricing | `tests/unit/test_mto.py`, `test_industrial_flow.py` |
| 8 Indirects, programme, loading | indirects, CPM duration, man-hours/histogram | duration proposal approved by a person against the company's own programme; man-hours agree with the labour build-up | `tests/unit/test_programme*.py` |
| 9 Commercial | overhead/profit/contingency/discount/tax | totals agree with a hand calculation using the approved policy; rounding variance reported | `tests/unit/test_commercial.py` |
| 10 Risk, escalation, cash flow | EV/Monte Carlo from approved ranges; cash flow from payment terms | outputs are labelled as derived from the approved ranges; seeds reproducible | `tests/unit/test_risk_escalation.py`, `test_cashflow.py` |
| 11 Reconciliation | rule findings | 0 open Critical; every other finding fixed or accepted by a permitted role with a reason | `tests/reconciliation/` |
| 12 Freeze & replay | estimate version frozen with snapshot | `project verify-snapshot` reproduces the frozen total after later rate changes | `tests/unit/test_full_replay.py`, `test_workspaces.py::test_snapshot_keeps_frozen_estimate_reproducible…` |
| 13 Basis of Estimate | generated from approved data | every statement traces to an approved record; open items listed; no compliance claim | `tests/unit/test_profiles_boe.py` |
| 14 Approval | Commercial Approver approves estimate; offer; tender-export | each approval row + hash-chained audit entry; `audit-verify` passes | `tests/approvals/`, `test_final_flow.py` |
| 15 Pilot comparison | compare to the independent figure (§2 item 17) | differences explained line by line; **the pilot is judged on explained variance, not on matching a target** | manual |

## 5. What remains manual (by design or by gap)

* Measuring quantities, reading drawings, deciding the scope of each BOQ line, and checking the BOQ against the drawings.
* Obtaining rates, quotations, productivity data, wages, calendars and any owner requirements, and judging whether the evidence is good.
* Every approval (rates, quotations, selections, assumptions, factors, policy, tax, estimate, offer, tender export) and every attestation of a client requirement.
* Programme logic (tasks and predecessors) is typed/imported; there is no resource levelling and no calendar-aware CPM beyond the governed calendar.
* Legal review of the offer letter, exclusions and contract terms.
* Excel: formulas were verified only with LibreOffice, not Microsoft Excel.
* Comparing results with an independent estimate (§4 stage 15).

## 6. What prevents a live commercial submission today

1. **No approved real data**: with an empty library nothing can reach the `Complete` state; a Preliminary estimate cannot pass the final gate or export.
2. **Gates are intentionally closed**: `export_submission` / client-form export need a Commercial Approver tender-export approval for the exact frozen version, a clean reconciliation gate (Critical findings cannot be waived), an approved estimate and an unchanged input fingerprint.
3. **Unverified seeds**: VAT and the USD/SAR peg are *Pending Review*.
4. **No validated benchmarks**: nothing has been calibrated or compared with a real completed estimate; accuracy on real work is unmeasured (stage 15).
5. **Unproven at scale / on live systems**: large BOQs not load-tested; Microsoft Excel and the live Claude API not exercised; no TLS/SSO/MFA (local use only).
6. **Client standards**: no owner profile is loaded; nothing may be said about compliance with any owner's requirements until a person loads them from the controlled documents and attests each.
7. **Legal/commercial sign-off** sits outside the system.

Until 1–4 are closed on real data and the pilot comparison is explained, treat every output as **preliminary**.

## 7. Industrial flow: what is verified, synthetic, or structural

Honest reading of `tests/integration/test_industrial_flow.py` and the data it uses (all numbers are SYNTHETIC and hand-computed; the pack holds no prices):

| Item | Verified by | Nature |
|---|---|---|
| Industrial pack loads definitions only (units, resources without prices), idempotent, admin-only | `test_industrial_pack.py` and the flow test | **Implemented; real structure, no real data** |
| Joint-unit BOQ with an exact `joint` unit and no silent conversion | flow test (SCO-04) | **Implemented** |
| Take-off derivation from a *human* BOQ quantity using approved `mto_factor` rows (200 joints → 22,200 → 24,400 with a 1.2 height factor) | flow test | **Implemented; factors and rates SYNTHETIC** |
| Man-hours (660), WBS roll-up, programme loading, risk EV, Basis of Estimate | flow test | **Implemented; inputs SYNTHETIC; BoE contains placeholders for facts nobody supplied** |
| Every one of the 23 take-off templates (103 slots) has at least one *unit-compatible* resource in the pack | `test_every_template_slot_has_a_compatible_catalogue_resource_in_the_pack` | **Structural check** – proves resources of the right kind/unit exist, **not** that they are the right resources |
| Every template can be derived and priced mechanically with synthetic factors/rates | `test_every_template_can_be_derived_and_priced_mechanically_with_synthetic_inputs` | **Mechanical check** – proves the arithmetic path, **not** that any template's slots reflect real practice |
| Template slot lists (23 templates) | `data/mto/templates.json` | **Structural placeholders**: slot names/dimensions are a skeleton for a company to fill; they carry no factors, wastage or norms |
| Only the piping weld-joint template is exercised with full downstream outputs (BoE, risk, loading) | flow test | The other 22 templates are covered only by the mechanical test above |

Known missing tests (not claimed as covered): a second trade end to end through programme/loading (e.g. electrical cable pulling); a multi-package industrial BOQ with WBS cross-walk to a client structure; negative paths in the flow (unapproved factor ignored in the approved view, missing rate leaves the line unpriced, stale take-off after a factor revision) are proven in unit tests, not repeated in the flow; real-file BOQ with Arabic descriptions and mixed units; replay of an estimate that uses take-off + landed cost + escalation together in one frozen version; load test with a few thousand lines.

A SYNTHETIC mechanical run of the whole chain exists ([SYNTHETIC_PILOT_RUN.md](SYNTHETIC_PILOT_RUN.md), `scripts/run_synthetic_pilot.py`). It exercises the engine path with invented numbers and test actors; it does not turn any template slot or structural placeholder into validated practice, and it does not change the readiness gaps above.

## 8. Real-data import preparation

Everything below creates **Drafts / candidates only**. A status column in any file is ignored.

### 8.1 Authorised rates
Template: `templates/pilot/rates_template.csv` (CSV/XLSX; first sheet or `--sheet`). Header synonyms are matched case-insensitively. **Required: a price column** (`Unit Price`, `Rate`, `Price`, `Unit Rate`, `Original Price`, `Price (SAR)`). Strongly expected for approval: `Currency`, `Unit`, `Price Date`, `Source URL` or `Source Name`, `VAT`, `Delivery`, `Installation`, `Evidence` (verbatim snippet or document reference). `Valid Until` is needed for the rate to price in-date. The original price and file are preserved and never overwritten.

```
python -m app.cli rates import FILE --source-name "Supplier X quotation Q-123" --url <ref> --dry-run    # first
python -m app.cli rates validate / pending / review / publish          # humans approve; publish creates Pending Review rates
```
Source metadata that must exist (Source Register, `data/sources/`, columns): `source_id, name, organisation, url, type, date_accessed, publication_date, geographic_relevance, currency, unit_price_basis, applicable_trades, licence_reuse_conditions, extraction_method, access_status, limitations, confidence`. For price sources `unit_price_basis` must describe a *price* (quotation, price list, contract rate).

### 8.2 Index data is not a price
GASTAT/KAPSARC CCI sources (SRC-001/002/003) have `unit_price_basis` beginning "Index" and type "Official statistics". Controls (all tested in `test_index_data_cannot_be_imported_or_approved_as_unit_prices`): the rate importer **refuses** such a source (`SOURCE_NOT_PRICE`) and any file declared "Official statistics"; an index-shaped table has no price column and is refused (`NO_HEADER`); `index import` writes only `index_observations` and never a rate or candidate; rate type "Official Index or Benchmark" is non-priceable and cannot be approved as a price; no regional multiplier exists. Never add an index source with a price-like `unit_price_basis`.

### 8.3 Productivity, take-off factors, calendars, terms (governed parameters)
Template: `templates/pilot/governed_parameters_template.csv`, columns `kind, code, source, basis_note, project_id, is_synthetic, data_json`. `data_json` is the kind's field object (see `python -m app.cli param kinds`, or [GOVERNED_PARAMETERS.md](GOVERNED_PARAMETERS.md)). `source` is **mandatory** unless `is_synthetic` is set (then it is labelled synthetic and reconciliation flags it in real projects).

```
python -m app.cli param import FILE [--project PRJ-…]     # Drafts only; bad rows reported, not loaded
python -m app.cli param submit ID                          # then a permitted human: param approve ID
```
The template's placeholder row is rejected by the validators, by design (tested).

### 8.4 Supplier quotations
Template: `templates/pilot/quotation_lines_template.csv` or the RFQ sheet exported by the suite (`templates/vendor_quote_template.xlsx`). Header detection needs a unit-rate column (`Unit Rate`, `Rate`, `Unit Price`, `Price`) plus `Item` (the procurement item id) or `Description`; optional `Specification, Qty, Unit, Discount %, Lead Time (days), Remarks`. Quotation header data (supplier, date, validity, currency, VAT/delivery basis) is entered on the quotation record, then lines are imported against it. Quotations are compared in levelling; **selection and rate publication are human approvals**.

### 8.5 Client requirements
Template: `templates/pilot/client_requirements_template.csv`: `req_id, category, title, source_ref, mandatory[, fact, op, value]`. Every requirement needs `source_ref` = document number and clause from the owner's controlled document. Machine-checkable rules (`fact, op, value`) are optional. A profile is a Draft until a Commercial Approver approves it; compliance is a person's attestation per requirement. The suite reports what was loaded and checked, never "compliant with <owner>".

## 9. Control verification (this pass)

Run with the full suite; see the result in [DEVELOPMENT_AUDIT.md](DEVELOPMENT_AUDIT.md) §10.

| Control | Existing tests that prove it |
|---|---|
| Frozen-estimate replay | `tests/unit/test_full_replay.py` (reproduces totals after rate/factor/indirect/tax change; detects tamper and changed engine inputs), `tests/workspaces/test_workspaces.py::test_snapshot_keeps_frozen_estimate_reproducible_after_a_new_rate_is_approved` |
| Human approvals | `tests/approvals/test_approval_rules.py` (AI cannot approve, self-approval switch, provisional rules, immutability, policy matrix), AST tests that `app/ai` and the source/importer modules never reference approval code |
| Provenance | `tests/sources/test_rate_pipeline.py` (original price preserved, manifest, duplicates refused, evidence required), `tests/approvals/` (evidence and date required) |
| Workspace isolation | `tests/workspaces/test_workspaces.py::test_project_isolation_files_and_quotes_stay_in_their_own_workspace`, duplicate/foreign folder refusal |
| Tender-export gating | `tests/integration/test_final_flow.py`, `test_full_workflow.py` (no approval → `EXPORT_NOT_APPROVED`, changed state/blocking findings → `EXPORT_BLOCKED`, client-form export gated) |
| Audit chain | `test_audit_chain_detects_tampering` |

## 10. After the end-to-end closure (2026-10-14)
A **controlled real-project pilot** on one authorised package is now feasible *with the registers*: enquiry, document register, queries, norms, workforce profile, calendar, programme baseline, procurement, commercial chain and the document pack all run through the real services.
What a pilot must still bring (none of it is shipped or defaulted): the project's confirmed calendar, company productivity norms with sources, workforce profiles, the customer's actual requirements (`tender_context.customer_requires`), real rates/quotations, and registered **human** approvers in a production environment.
Not ready for production: identity assurance (no MFA/SSO), audit anchoring, content of quality/HSE/ITP registers (needs competent authors), unverified standards (see `docs/STANDARDS_AND_EVIDENCE_REGISTER.md`), and any claim that depends on synthetic norms.
