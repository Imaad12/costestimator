# Known limitations (read before relying on any output)

## Data
* **There is no Saudi rate library.** Measured coverage (`python -m app.cli coverage`, fresh install): 927 catalogue resources (395 material, 99 labour, 64 plant, 149 equipment, 220 subcontract) - **0 with a real approved rate, 0 synthetic, 927 Missing Rate** (0.0% coverage).
  The catalogue defines *what* to price; every price, wage, productivity, consumption and wastage figure must come from you. Only the clearly labelled `DEMO-*` resources in the synthetic demo project carry (invented) prices.
* **Public-data research was limited.** The build environment could not reach Saudi government sites directly; a search/scrape service was used (some cached results). 27 sources recorded: 10 accessed, 12 partially, 3 blocked, 2 not attempted. **No free reusable source of SAR unit rates was found**; none was copied. See [KSA_DATA_SOURCES.md](KSA_DATA_SOURCES.md).
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

## Not implemented (documented integration points)
GASTAT/KAPSARC index adapter, Etimad award adapter (no verified, permitted, stable endpoint); DuckDB analytics (architecture-compatible); automated tests of the browser UI beyond HTTP-level rendering and form posts.
