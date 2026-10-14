# Analysis reports (read-only)

Generated from `app/reporting/registry.py` by `scripts/gen_docs.py`. Every report is available identically from the web UI (*Analysis & controls*), the REST API
(`GET /api/projects/{id}/report/{name}?param=value`), and the CLI (`python -m app.cli report PRJ-.. NAME --param k=v [--save]`). A report **never changes an estimate and never approves anything**;
*Save* stores an immutable `analysis_runs` record (parameters, input hash, result) that is explicitly not an approved record. A report that lacks an approved input says so instead of guessing.

| Report | Group | What it shows | Parameters |
|---|---|---|---|
| `indirect_base` | Risk and commercial | **Percentage-indirect eligibility base** - What each percentage indirect is applied to: eligible, excluded and unclassified direct cost by cost code, BOQ line and kind, and preliminaries inside the base. | - |
| `plant_hire` | Programme | **Day-priced plant: billable days vs programme window** - Working days vs calendar days, minimum hire, standby, mobilisation and the on-site window read from the programme. | - |
| `rollup` | Structure | **Cost roll-up (CBS / WBS / client cross-walk)** - Direct cost rolled up by cost-code tree, WBS, WBS x division matrix and each client code system; ties out to the estimate. | `preliminary`=0 |
| `schedule` | Programme | **Programme: dates, float, critical path** - CPM with relationship types, lags and an optional working calendar. | - |
| `loading` | Programme | **Resource loading histogram** - Labour hours, plant hours or cost spread over the programme and bucketed by week / month / block. | `measure`=labour_hours, `period`=week, `block_days`=5, `preliminary`=0 |
| `manhours` | Programme | **Man-hour aggregation** - Own-labour hours by craft, cost code, division and WBS (subcontract labour is not included). | `preliminary`=0 |
| `classification` | Basis of estimate | **Estimate classification and maturity** - Class and accuracy range from the APPROVED classification scheme and the estimator's stated maturity, next to measured maturity facts. | - |
| `compliance` | Basis of estimate | **Client profile compliance matrix** - Requirements loaded from the owner's controlled documents, evaluated against measured facts or human attestations. | - |
| `mto_status` | Structure | **Take-off derivation status** - Applications of take-off templates and whether their factors / drivers have changed since. | - |
| `mto_preview` | Structure | **Take-off derivation preview** - What a template would derive for an item (nothing is written). | `item_key`="", `template`="", `driver_qty`="", `driver_source`="" |
| `boe` | Basis of estimate | **Basis of Estimate (facts)** - Structured facts for the Basis of Estimate; generate the document with the generate_boe action. | - |
| `currency_exposure` | Commercial | **Currency exposure and hedge cover** - Priced direct cost by quotation currency (landed-cost rates split by recorded exposure), approved hedge cover and what-if sensitivity. | `shocks`=5,10, `preliminary`=0 |
| `risk` | Risk and commercial | **Quantified risk: expected value and Monte Carlo** - Seeded simulation over quantified risks and cost ranges; proposes a provision at the chosen confidence level (never applied automatically). | `trials`=10000, `seed`=20260101, `target_pct`=80, `preliminary`=0 |
| `escalation` | Risk and commercial | **Time-phased escalation** - Escalation by programme month from each approved profile's base date; index values shown as information. | `index_dataset`="", `preliminary`=0 |
| `cashflow` | Risk and commercial | **Cash flow, retention, bonds and financing** - Monthly cash position from approved payment terms; peak funding, interest and bond cost. | `terms_code`="", `preliminary`=0 |
| `bid_evaluation` | Procurement | **Bid evaluation (weighted, advisory)** - Weighted scores from approved criteria and recorded evidence plus levelled prices; ranking is advisory. | `package_id`="", `criteria_code`="" |
| `long_lead` | Procurement | **Long-lead items** - Latest order date, float and status for long-lead items and vendor data. | `on`="" |
| `interface_matrix` | Procurement | **Package scope / interface matrix** - Who includes each BOQ item; double counts, gaps and open interfaces. | - |
| `contract_status` | Post-award control | **Contract value and variations** - Original contract sum, approved and pending variations, revised sum and time impact. | - |
| `earned_value` | Post-award control | **Earned value and forecast** - PV / EV / AC, CPI / SPI and forecasts at a data date from entered progress and recorded actuals. | `data_date`="", `version_id`="" |
| `benchmarks` | Risk and commercial | **Benchmark reasonableness check** - Estimate values compared with the company's approved benchmark ranges. | `preliminary`=0 |
| `engineering` | Risk and commercial | **Engineering effort and cost** - Hours and cost of declared engineering deliverables at approved labour rates. | - |
| `overhead` | Risk and commercial | **Overhead pool allocation** - Project share of approved annual overhead pools. | `pool_code`="" |
| `method_comparison` | Structure | **Construction-method alternatives (what-if)** - Base estimate beside each approved method alternative: direct / indirect / total cost, man-hours, plant hours and duration. | `preliminary`=0 |
| `assumption_evidence` | Governance | **Assumptions: standing of every adopted value** - Each adopted/mandatory assumption classified as verified, company-approved, project-approved, imported-unverified, pending review, AI-proposed, synthetic or missing. | - |
| `productivity_programme` | Programme | **Productivity-based, resource-constrained programme** - Activities scheduled from approved (or explicitly provisional) productivity norms, a workforce profile and the project calendar; reports gaps and what they do to the programme. | `profile`="", `provisional`=false |
| `crew_scenarios` | Programme | **Crew-size scenarios** - The same activities, norms and calendar scheduled for several workforce profiles: duration, staffing, labour-hours, critical path, constraints and (when role costs are entered) cost. | `profiles`="", `provisional`=false |
| `tender_queries` | Tender | **Technical / commercial query registers** - All draft and issued queries by register and status; unresolved material queries block submission. | - |
| `tender_documents` | Tender | **Received tender documents and revisions** - Documents received, revisions, superseded and missing ones, BOQ-vs-register revision conflicts; says what was only registered, not interpreted. | - |
| `discipline_completeness` | Tender | **Discipline x document completeness** - For each discipline the project expects: drawings, specification and other documents received / missing, and BOQ lines carrying that discipline. | - |
| `applicability` | Tender | **Tender document applicability matrix** - Each of the 45 tender documents classified Required / Conditional / Not Applicable / Missing Customer Requirement with a reason. | - |
