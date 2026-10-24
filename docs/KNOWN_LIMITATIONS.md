# Known limitations (read before relying on any output)

## Data
* **There is no Saudi rate library.** Measured coverage (`python -m app.cli coverage`, fresh install): 927 catalogue resources (395 material, 99 labour, 64 plant, 149 equipment, 220 subcontract) - **0 with a real approved rate, 0 synthetic, 927 Missing Rate** (0.0% coverage).
  The catalogue defines *what* to price; every price, wage, productivity, consumption and wastage figure must come from you. Only the clearly labelled `DEMO-*` resources in the synthetic demo project carry (invented) prices.
* **Public-data research was limited.** The build environment could not reach Saudi government sites directly; a search/scrape service was used (some cached results). 27 sources recorded. **No free reusable source of SAR unit rates was found**; none was copied. The only data stored is a 39-record **index** sample (GASTAT CCI, period 2026-04, via KAPSARC) — not a price. See [KSA_DATA_SOURCES.md](KSA_DATA_SOURCES.md).
* **Tax and FX are unverified seeds.** `VAT-STD` (15%) and the USD/SAR peg (3.75) are seeded *Pending Review* with evidence; a human must verify against current official guidance before any estimate can resolve tax or convert currency. Tax recoverability is stored but not used in any calculation.
* The assumptions register (322 definitions) ships with only four methodological defaults; the standard assemblies (26) are structure only and cannot be approved until factors are supplied. No productivity benchmarks are provided.
* Synthetic figures are round invented numbers for demonstration and tests; they must never be mixed into a real library (reconciliation flags this as Critical in non-demo projects).

## Calculation scope
* Implemented: resource-based direct cost (waste, labour productivity/crew/overtime share, plant utilisation and build-up, subcontract lump sums, take-off resources, sums/allowances), indirects (fixed/%/day/week/month), CPM duration, commercial chain, pricing-schedule spreading with exact reconciliation, tax per category.
* **Not applied in costing** although they can be recorded: plant *standby* percentage and *minimum hire period* (in plant components), retention, bonds, warranty and payment-terms cost of money, tax recoverability, cash-flow/time-phased escalation. The indirect `currency` column is not converted (indirects are SAR). Discount is applied at total level (one percentage or amount).
* Unit conversion is automatic only within length, area, volume and mass. Density/volume-to-mass or hour-to-day conversions need explicit assumptions or assembly factors; time units never convert implicitly.
* Overtime is modelled as a blended share on the base-wage portion; Ramadan hours, shift allowances and calendars with holidays are not modelled. CPM durations are in working days without calendars or resource levelling.
* Per-line rounding to `money.rounding_dp` means totals can differ by cents from a spreadsheet that rounds only at the end. Tendered unit-rate rounding creates a reported *rounding variance* (bounded and shown).
* No measurement logic of any kind (by design): no drawing/PDF/BIM takeoff, no deduction rules, no quantity optimisation.

* **Time-phasing needs an allocation for every cost.** Cash flow, time-phased escalation and loading place a cost line in time only through an activity's own cost-code/WBS scope or an *approved* `time_allocation` rule (governed parameter: scope, activities or ALL, optional percentage shares summing to exactly 100). Cost with neither is **never spread or dropped**: it is listed with its exact amount, the cash flow / escalation are labelled `INCOMPLETE - NOT FOR RELIANCE`, only the allocated share of the price is valued, financing proposals are refused, and the High finding `TIMEPHASING_INCOMPLETE` blocks the final gate until the cost is allocated or a Commercial Approver accepts an exception. Cash-out convention: indirects follow the direct cost they are a percentage of; contingency, risk and margin are not cash-out.
* **Percentage indirects and adders:** a `percent_of_direct` indirect (and contingency/risk/escalation percentages) may carry an explicit eligibility base (`{default, rules}` by cost-code prefix, BOQ line, cost kind, with partial shares). Without one the legacy whole-direct-cost base still applies and is reported as *unspecified* (`INDIRECT_ELIGIBILITY_UNSPECIFIED`); a base that includes preliminaries (division A) BOQ lines raises `INDIRECT_BASE_OVERLAP` (High). Existing approved policies/indirects are not changed; a revision is a new Draft version.
* **Day-priced plant:** hire terms (`plant_hire_terms`) state billing basis (working vs calendar days), the programme activities that define the on-site window, minimum hire, standby and mobilisation/demobilisation days. The on-site window is read from the programme; a difference to the BOQ days is reported (`plant_hire` report, `PLANT_HIRE_DAYS` High finding) and never adjusted silently. A day/week/month-priced plant without approved terms raises `PLANT_TERMS_MISSING` (High). Only day-priced plant is compared with the programme; week/month units are not.
* **Synthetic and test-principal output can never be submission ready** (see SECURITY.md); a real tender still needs real approved data and registered human approvers.

## Reconciliation / procurement
* Duplicate detection is rule-based (same description/unit/quantity; same resource+quantity under different trades; keyword overlap between indirects and priced preliminaries) and will have false positives and false negatives; it is a prompt for review, not proof.
* Offer-vs-estimate checks work on structured scope entries, the schedule hash and totals; the `.docx` text is not parsed back. Offer letters and pricing schedules are drafts for human/legal review.
* Levelling normalises price, currency, tax and unit; qualitative differences (scope wording, technical compliance) rely on the reviewer's compliance flags and approved adjustments.
* The Arabic RFQ template is a machine-written draft requiring human review; the user interface is English only (Arabic descriptions are stored but there is no RTL layout).
* No email is ever sent, by design; supplier contacts are never inferred.

## AI
* AI features are optional and **were not exercised against the live Claude API** in the build/test environment (no key, restricted network). They are tested with a deterministic mock provider (schema validation, injection resistance, review gating). Output quality is therefore unmeasured.
* The AI path works on text you paste; there is no PDF/OCR/spreadsheet parser for quotation documents.

## Excel
* Formulas were verified by LibreOffice recalculation; **Microsoft Excel itself was not available** for testing (formulas use only common functions plus `MINIFS`). Sheet protection has no password (accident prevention only).
* Workbook import covers the sheets documented in EXCEL_WORKBOOK_GUIDE (BOQ, mapping, assumptions, indirects, registers, vendors, library rate proposals, assemblies). Approvals, statuses and read-only data are never imported.

## Security and operations
* Local single-user / small-team design. Password hashing (PBKDF2) and HMAC-signed tokens are implemented; there is **no TLS, rate limiting, account lockout, CSRF token (SameSite=Strict cookie only), MFA or SSO**. Bind to 127.0.0.1; do not expose to the internet.
* The audit log is a hash chain: **tamper-evident, not tamper-proof**. The SQLite file and backups are not encrypted.
* One SQLite connection; requests are serialised. Large BOQs (tens of thousands of lines) were not load-tested; pages recompute the estimate on every view and the build-up table shows the first 1,500 lines.
* The role matrix is defined in code (`approvals/policy.py`), not editable in the UI. Requires running from the repository layout (`config/`, `data/`, `templates/`).
* Restore is command-line only by design.

## Public sources and rate updates (second iteration)
* **Still 0 approved real rates.** The pipeline (import → candidates → review → publish → approve) is implemented and tested, but no real price has been loaded or approved.
* The KAPSARC/GASTAT CCI provider is implemented and tested against mocked/recorded responses; **no live fetch by the application has succeeded from the build sandbox** (proxy refusal). Real-network behaviour is unverified.
* GASTAT's own site and Etimad are manual-only; the layout of GASTAT's xlsx files was never inspected; Etimad awards are contract values, not quotes.
* The web-price extractor reads only machine-readable markup and a low-confidence text fallback. It was tested on fixtures, **never on a real supplier page**; many sites need JavaScript rendering (not supported) or forbid automated access.
* Candidate normalisation covers currency (approved FX), fixed physical unit factors and VAT only. No quantity-break, delivery or installation adjustment.
* Two overlapping dataset flows exist (legacy `rate_staging`, new `rate_candidates`).
* Estimate snapshots exist only for versions frozen after migration 0007; snapshot replay re-runs the direct-cost engine, not the commercial tail.
* The document indexer has no OCR and no CAD/BIM extraction; revision/category/trade come from file names only; summaries are counts, not content summaries.

## Iteration 4: frameworks without data (read before relying on any output)
* **Every governed parameter kind ships empty** ([GOVERNED_PARAMETERS.md](GOVERNED_PARAMETERS.md)): productivity factors, take-off factors, hire terms, calendars, escalation, payment terms, benchmark ranges, statutory labour rules, evaluation criteria, classification schemes ... A report that needs one says so and stops. Nothing is estimated "typically".
* Take-off templates ([MTO_TEMPLATES.md](MTO_TEMPLATES.md)) are structure only; they do not know pipe classes, weld procedures, coating systems, crane capacities, camp rotations or shutdown logic. Discipline records PRC-01..14 are therefore **Partial**.
* Programme: working-day arithmetic with one calendar per project and typed-in tasks; no schedule-file import, no resource levelling, no Gantt chart. Loading spreads each task's quantity **uniformly**; cost reaches tasks only through the task's declared cost-code prefix / WBS.
* Risk: independent risks, triangular distributions, no correlation, schedule days summed (no critical-path logic). Results are proposals; the commercial policy is changed only by an approved policy revision.
* Escalation compounds a company-chosen annual percentage; index series are shown as information only. Cash flow assumes value earned follows cost incurred and excludes VAT.
* Client profiles: no profile content is shipped. **No Saudi Aramco (or other owner) compliance is claimed.** A profile only checks the requirements a person loaded from the owner's controlled documents; a "met" statement is scoped to those.
* The client tender-form export fills a form the user supplies using a mapping the user writes; it does not validate the form against client rules and does not generate bilingual deliverables.
* Withholding tax / zakat / corporate tax treatment is not modelled (VAT only). Method statements are free text; equipment selection from site conditions is not automated.
* Security hardening is for a trusted LAN ([SECURITY.md](SECURITY.md)): no MFA/SSO, no per-folder ACLs, no encrypted backups, serialised requests.
* Performance (20,000 BOQ items): estimate 2.7 s, master workbook 25.6 s, not tested at 50,000.

## Not implemented (documented integration points)
DuckDB analytics (architecture-compatible); GASTAT website adapter, Etimad adapter (manual import only); automated tests of the browser UI beyond HTTP-level rendering and form posts.

## End-to-end closure (iteration 6): read before relying on any output
* **Productivity and programme**: every norm, crew, profile, calendar, shift/overtime efficiency and role day-cost is person-entered; the closure scenario uses *synthetic* values, so its agreement with the oracle proves arithmetic and controls, not real productivity or duration.
  Scheduling is a daily priority simulation (no levelling beyond the priority rule, indivisible crews, no weather model, no multi-calendar resources, no P6/MSP import). Archetype bands (4-15, 15-25, 26-50, 51+) are initial company planning assumptions, not industry categories.
* **No default Saudi calendar or labour rule is shipped.** The standards register records what was read: 2 sources verified on the primary page, 4 partially verified, 6 requiring human acquisition (Saudi Building Code pages and the procurement law could not be read; AACE recommended-practice texts are paid).
  The product states no compliance with any standard, owner requirement or AACE class.
* **Registers and documents**: detectors are heuristic (wording markers, import flags, register comparisons) and raise **draft** queries only; documents are *registered*, not interpreted; the quality, ITP, method-statement, HSE and commissioning registers hold structure and explicit
  placeholders - no inspection criteria, HSE controls or compliance statements are generated. Generated documents are assembled from registers and the frozen estimate; template content is code (versioned), English only, PDF layout is functional.
* **Cash flow and escalation are not part of the frozen snapshot** (they read the current approved payment terms and programme); the estimate totals and every printed estimate figure are frozen. Tax is charged on the tendered pricing schedule, which differs from the commercial net price by the reported rounding variance (O-9).
* **Interfaces**: the closure registers are reachable through reports (UI/REST/CLI), REST actions and the CLI `action` command; there are no bespoke UI forms for norms, profiles, queries or registers.
* **Identity**: in-process service calls trust the `Actor` they receive (the approval is *recorded* as `unregistered`/`role_mismatch`/`test` and never counts for readiness); there is no MFA/SSO; an Administrator can register a user typed `human`. A hypothetical handover pack is a simulation: no award is recorded and none is assumed.

## Practice-test follow-ups (2026-10-14)
* PDF/image BOQs are not read (no OCR by design); transcribe to CSV/XLSX and import with `derived_from`; a second person must check it before production readiness.
* Estimate totals show `None` (not 0) for direct cost when nothing is priced and for indirect cost when no indirect item exists; a partially priced estimate still shows the partial direct-cost sum, labelled by the estimate state (Incomplete).
* The estimate state does not itself consider an unchecked transcription or placeholder rates; the readiness gate and banners do.
* A demonstration project on non-synthetic data is labelled DEMONSTRATION / PRACTICE, not SYNTHETIC; synthetic content is detected from the customer flag, synthetic rates in the frozen estimate and synthetic registers.
* Frozen estimate versions created before this change store the state label without the synthetic suffix; replaying them compares against the new label (affects only demo/synthetic databases).
* The discipline matrix depends on a person assigning a discipline to each registered document and on BOQ trade text; a document without a discipline is listed, never guessed.
* `python -m app.cli run` binds to 127.0.0.1:8000 by default. If another program already uses that port (including an IPv6-only, wildcard-bound or Windows/WSL-side listener that a plain connect test cannot see), a browser may show that other program instead of this one. `scripts/demo_web.sh` therefore starts at port 8731, skips any port that answers or cannot be bound on IPv4/IPv6, and verifies the page title ("KSA Construction Estimating Suite") before printing the URL; always use the printed URL. Reaching the app from another machine (or from a cloud container) needs port forwarding or `HOST=0.0.0.0` on a trusted network only.

## Standards evidence ingested (2026-10-17)
Six supplied PDFs are held in `data/standards/evidence/` (git-ignored; SHA-256 in `evidence_manifest.json`) and the register rows STD-003/005/006/007/013 were updated from them (`python -m app.cli standards import FILE --update`, audited). Read: HRSD working-hours/overtime/holidays pages, ZATCA VAT amendments guideline (Apr 2025), Government Tenders and Procurement Law (law text only, no Implementing Regulations), SBC 201 **Arabic** AR-18 volume. Still not obtained: other SBC volumes/English edition, gazetted Labor Law and Executive Regulations, a primary document for Founding Day (the user states 22 February; recorded in STD-006 as user-supplied, not yet a calendar parameter), productivity references. The register records provenance only; no value was seeded as a governed parameter and no compliance is claimed.

**Labor Law read (2026-10-17):** the English official translation and the Arabic consolidated text (amended to M/44 of 1446H) were supplied and read; register row STD-014 is Verified for Arts. 98-107 (hours, rests, Friday weekly rest day - Art. 104, overtime). Still unread: the Executive Regulations, Minister decisions (Art. 99 categories, Art. 106 overtime ceiling) and the paid-Eid list (Art. 112). No value was turned into an approved parameter: a person still enters and approves the project calendar.

**Building-code summaries read (2026-10-17):** the official SBC system overview leaflet (STD-004, now Verified for the list of code families), the SBC 201-CR-18 summary of content (STD-015) and the SBC 302-CR-18 summary of content (STD-016) were supplied and read. They are summaries: no clause text, limits or tables, so no value (curing time, hot-weather limit, testing frequency, inspection hold point) may be entered from them. The full SBC 301-309, 401, 501, 601/602, 701/702, 801 and 901 texts, the English full text of SBC 201 and the 2024 edition status remain to be obtained.


## Web-sourced prices (24 Oct 2026)
Public web prices were gathered for phase-1 verification (see `data/public_data/web_price_research_2026-10-24/PROVENANCE.md`). They are indicative retail / list prices or published ranges, mostly without a stated date, VAT or delivery basis; a range is entered as its midpoint; the catalogue's items are generic, so many matches are approximate and flagged "APPROX MATCH" in the evidence. Only a small share of the catalogue could be priced from public pages (no public prices were found for chillers, AHUs, VRF, pumps, grooved pipe and fittings, fire pumps, structural sections, PEB supply and erection, most subcontract packages and labour). Terms of use of the sites were not reviewed. Nothing from this research is an approved rate.
