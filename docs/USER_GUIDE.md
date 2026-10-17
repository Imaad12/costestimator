# User guide

This guide walks through the **synthetic demonstration project** (everything labelled SYNTHETIC / DEMO / NOT A MARKET QUOTE), then explains each section of the application. The same steps apply to a real project.

## 0. Start
```
python -m app.cli init --demo-users      # prints the admin password once
python -m app.cli demo                    # creates PRJ-0001 with nine packages, deliberately left with realistic open issues
python -m app.cli run                     # http://127.0.0.1:8000
```
Demo logins (if `--demo-users`): `estimator`, `procurement`, `commercial` / `demo-only-change-me`. Use the matching role for each step - the server enforces it.

## 1. Walkthrough (what to do, in order)
1. **Dashboard** - PRJ-0001 shows *Preliminary - Incomplete*, unpriced lines, indicative exposure, unapproved assumptions in use, no reconciliation run yet. Percentages show "n/a" when undefined.
2. **BOQ import** - the demo BOQ was imported from `data/demo/demo_boq.xlsx`: 26 items, 9 headings, 1 blank row, 1 rejected row (quantity `TBA`), item `2.2` with the **ambiguous unit "ton"**, and duplicate code `6.1`.
   *Estimator*: approve the pending unit change for 2.2 (choose `t`), and *Acknowledge flags* on `6.1#2` with a reason. To import your own BOQ: *BOQ import -> upload -> check the detected header/mapping -> Import*.
3. **Mapping** - items are mapped to approved synthetic assemblies. Try *Suggest mappings (keyword match)* on any unmapped item and approve/reject the suggestion. Set a pricing method for lump-sum/subcontract, provisional sum, PC sum, allowance or excluded items.
4. **Estimate build-up** - see every resource line with its rate, status, calculation *basis*, and flags; items without an eligible rate show **UNPRICED** (with indicative value if a non-approved rate exists). Toggle *Preliminary view* to include unapproved inputs (clearly flagged).
5. **Resource libraries** - tile rate (DEMO-MAT-009) is *Pending Review*; cable tray (DEMO-MAT-014) is *Expired*. *Procurement Reviewer*: approve the tile rate; propose a new tray rate (new version) and approve it.
6. **Procurement & RFQs** - *Detect procurement needs*: sprinkler heads, AHU, CCTV cameras and lifts have no rate. Create an RFQ per package, export XLSX/DOCX or copy the email text. You send it yourself.
7. **Quotations** - enter the supplier's quotation (or import the completed RFQ sheet), submit, then the **Procurement Reviewer** verifies it. Open *Compare quotations*: quoted totals vs normalised values, coverage and notes. Propose a selection (a reason is required if not the lowest like-for-like), approve it, *Propose rates from this quotation*, then approve each rate on the resource page.
8. **Indirects & commercials** - indirects, duration and the commercial policy are approved (synthetic). The tax category **VAT-STD is Pending Review**: a *Commercial Approver* must enter verification evidence and approve it before tax and final payable resolve.
9. **Clarifications & risk** - resolve the two open clarifications (client response + evidence), approve the scope entries (inclusion/exclusion/qualification). Approve the provisional sum / PC sum / allowance decisions on the Mapping page.
10. **Reconciliation** - *Run reconciliation*. Fix or (where the rule allows) accept documented exceptions; Critical findings can never be waived.
11. **Reports & exports** - generate the **offer letter**, have it approved; freeze an estimate version, submit it and have a **Commercial Approver** approve it (Reconciliation page); approve the tender export; then *Export submission package*. Preliminary outputs are available at any time and are watermarked.

`tests/integration/test_full_workflow.py` performs exactly this journey with explicit human actors and independently computed expected values.

## 2. Sections
| Section | Purpose |
|---|---|
| Dashboard | per-project value, missing-rate exposure, unapproved assumptions, pending/expired quotations, clarifications, Critical findings, approval status, completeness |
| Projects | create (name, client, region, stage, tax category); archive (read-only); project package export |
| BOQ import | preview, header detection, column mapping, validation summary, rejected rows, pending change requests, re-import diff, take-off resource lines |
| Mapping | cost code, assembly, pricing method; suggestions; allowance approvals |
| Estimate build-up | lines, items, exceptions, cost-to-price reconciliation, strict vs preliminary |
| Resource libraries | search/filter 927+ resources, rate versions, propose/approve rates, history |
| Assumptions | global register and project overrides; what-if effect |
| Procurement & RFQs, Vendor quotations, Quote levelling | see [PROCUREMENT_GUIDE.md](PROCUREMENT_GUIDE.md) |
| Indirects & commercials | indirect items and allocation, duration proposals/approval, commercial policy, tax categories |
| Clarifications & risk | clarification register, inclusions/exclusions/qualifications, risk register, rule-based scope checks |
| Reconciliation | findings by severity, exceptions, version freeze/approval |
| Approvals | queue of everything awaiting a decision + the approval log |
| Reports & exports | workbook download/re-import, offer, preliminary and final exports, estimate-vs-actual |
| Settings & data sources | company details, users, tax/FX, source register, rate dataset ingestion, taxonomy, backups |

## 3. Working in Excel
*Reports -> Download master workbook* gives a 27-sheet workbook (see [EXCEL_WORKBOOK_GUIDE.md](EXCEL_WORKBOOK_GUIDE.md)). Edit only yellow cells, then *Re-import*. Imports create drafts/proposals; status columns typed in the file are ignored.

## 4. Optional AI
Set `KSA_AI_ENABLED=true` and `ANTHROPIC_API_KEY` (environment only). AI can suggest mappings, extract quotation fields from text you paste, draft clarifications and flag scope gaps. Everything lands as *Pending Review* with a confidence and source references; you accept or reject it.
Without a key every deterministic feature still works.

## 5. Adding things without touching code
See [EXTENDING.md](EXTENDING.md).

## 6. Project workspaces, documents and completeness
Creating a project (Projects page or `python -m app.cli project create …`) creates `projects/PRJ-nnnn-slug/` with the ten numbered folders, `project.json` and a project `CLAUDE.md`; the page that follows shows the path and the next action.
*Workspace & documents* lets you upload tender documents (originals are never overwritten), press *Index documents* (read-only scan; versioned extracts in *2. AI Context*), record the trades and approved drawing/specification revisions, and see frozen-estimate input snapshots.
*Completeness* lists, from the database, what is done, open or blocking (no scores). Details: [PROJECT_WORKSPACES.md](PROJECT_WORKSPACES.md).

## 7. Getting real rates in (Rate updates)
The global library ships with **no prices**. Open *Rate updates*: import a price list/public dataset as candidates (dry-run first), review each candidate (evidence, VAT, unit, resource), *Approve for publication*, *Publish* (creates a Pending Review rate), then approve the rate (Procurement Reviewer / Commercial Approver).
Missing rates still go through *Procurement & RFQs*. Index data (GASTAT CCI) can be imported for escalation reference only. Details: [RATE_UPDATE_WORKFLOW.md](RATE_UPDATE_WORKFLOW.md).

## 8. Structure, inputs and analyses (iteration 4)
Three project pages hold the new capabilities; nothing on them invents a number.
* **Inputs & parameters** - the company's own numbers (productivity factors, hire terms, calendar, escalation, payment terms, benchmark ranges, take-off factors, evaluation criteria ...). Pick a *kind*, give a *code*, enter the JSON fields from your records and a **source**, save, submit, and a permitted person approves ([GOVERNED_PARAMETERS.md](GOVERNED_PARAMETERS.md)). Approved values are never edited; change = new version.
* **Structure & programme** - WBS (area/unit/system), client code cross-walk, programme tasks (`B-SS+2` style links, WBS and cost-code scope), take-off derivation (template x approved factors -> a *Pending Review* pricing decision), risk quantification, client profile link and attestations.
* **Analysis & controls** - read-only reports: cost roll-up, programme dates/float, resource loading, man-hours, landed-cost/currency exposure, risk (expected value + seeded Monte Carlo), escalation, cash flow, Basis of Estimate facts, classification, compliance matrix, bid evaluation, long-lead, interface matrix, variations/contract value, earned value, benchmarks, method alternatives ([ANALYSIS_REPORTS.md](ANALYSIS_REPORTS.md)). *Save this run* keeps an immutable record; it is **not** an approval and changes no estimate.
Typical order for an industrial package: load the optional pack (`python -m app.cli pack load industrial`, administrator) -> approve factors -> enter the measured driver quantities -> *Apply* the template -> approve the pricing decision -> check roll-up, man-hours, loading and risk -> generate the Basis of Estimate (`generate_boe`) -> normal reconciliation and approvals.
Proposals (`propose_*`: financing and bond cost, reserves, engineering effort, overhead) create **Draft indirect items** that you submit and approve like any other indirect. Security notes: [SECURITY.md](SECURITY.md).

## 9. Tender delivery: enquiry to handover (iteration 6)
All of it is reachable as reports (UI Analysis tab, `GET /api/projects/{id}/report/{name}`, `python -m app.cli report PRJ-nnnn NAME`) and as actions (`POST /api/actions/{name}`, `python -m app.cli action NAME '{json}' --user NAME`).
1. `create_enquiry`, `create_project`, `register_document` (revisions supersede; a document is *registered*, not interpreted), `upsert_register_item` (`tender_context` holds contract type, delivery model and `customer_requires`).
2. `generate_queries` creates **draft** queries from detected ambiguities, duplicates, revision conflicts, missing documents and unconfirmed assumptions; a person edits, `release_query`s, issues it outside the application, then `record_query_response` (as received) and `close_query`.
3. `create_norm` / `submit_norm` / `approve_norm`, `create_profile` / `approve_profile`, `set_activities` (quantity comes from the BOQ item), then reports `productivity_programme` and `crew_scenarios`; `save_baseline` / `approve_baseline`; `baseline_to_schedule` feeds the existing CPM, cash-flow and escalation analyses.
4. Report `applicability` shows which of the 45 documents apply and why. `generate_tender_pack` (needs a frozen estimate version) writes DOCX/PDF/XLSX + `manifest.json`; `validate_pack` checks it; `approve_document` records a document approval.
5. `generate_handover_pack` works only after `tender_context.award_scenario = hypothetical` is recorded and always says **HYPOTHETICAL**.
Status words: BLOCKED (missing input), Preliminary (DEMONSTRATION), Draft, For Review, Approved for Submission - see `docs/TENDER_DOCUMENT_APPLICABILITY_MATRIX.md`.

## 10. The tender workflow pages (web UI)
Open a project: the top row **Tender** has seven tabs.
* **Control tower** - the eleven workflow stages A-K with their status (done / in progress / blocked / not started), counts read from the database, and a list of what stops a submission-ready status.
* **Tender desk** - the enquiry, the received-document register (with revision, discipline and Missing documents) and the discipline-by-document completeness matrix.
* **Queries & RFIs** - run the detectors (drafts only), add a query, approve it to issue, mark it issued (you send it yourself, outside the application), record the customer's response, close or withdraw it.
* **Registers & actions** - compliance, ITP, method statements, HSE, permits, submittals, testing and handover items (skeleton rows are marked TO BE COMPLETED BY A COMPETENT PERSON) and the open-action / takeoff-task list.
* **Workforce & programme** - productivity norms, workforce profiles and the project's activities (create them with the forms — crew and roles are row editors, activities a table; submit, then a different person approves), programme baselines and crew-size comparisons.
* **Tender pack** - generate the 45-document pack and the hypothetical handover pack, see each document's status and why it is BLOCKED, download DOCX/PDF/XLSX and the manifest, run the validator, and **approve a document** (a recorded, audited decision; a blocked document cannot be approved; an approval by a test principal is shown as not counting for readiness).
* **Readiness** - the final gate for a frozen estimate version: classification, every reason it is not submission ready, and the standing of every assumption.
Global pages: **Standards & evidence**, **Audit trail** (with hash-chain verification) and **Help** (the project documents, including the built-vs-missing diagrams).

### Governed parameters (Inputs & parameters tab)
Pick the kind (work calendar, payment terms, plant-hire terms, escalation, productivity factor, time allocation, ... 22 kinds); the form shows that kind's fields, **all blank** - lists are comma-separated (calendar weekdays `0,1,2,3,4`, 0 = Monday), nested items (reduced-hours windows, shutdowns, criteria) are row editors. Name the source, tick *submit for review* or submit later. The service validates the whole record; an incomplete one is refused with the missing field named. Approval is by a different permitted person. Quick links on the page jump to the calendar and payment-terms forms; the raw-JSON box remains for advanced use.
