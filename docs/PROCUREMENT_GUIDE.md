# Procurement guide

## 1. Detect needs
*Procurement & RFQs -> Detect procurement needs* runs the **strict** estimate and creates one register line per (resource, reason): `MISSING_RATE`, `EXPIRED_RATE`, `UNAPPROVED_RATE`, `RATE_REGION_MISMATCH`, `INDEX_ONLY_NO_PRICE`,
`RATE_NOT_YET_EFFECTIVE`, or `RATE_WARNING` (low-confidence / aged rate in use). Each line shows project, package (one per trade division), trade, resource, description, specification, aggregated quantity and unit, delivery location,
required date, preferred suppliers, RFQ status, response deadline, quotation status, approval status and the **indicative exposure** (blank = unknown, never 0). Re-running is idempotent; lines close when an approved rate resolves them.
Scope items needing subcontract pricing appear when their subcontract resource has no eligible rate.

## 2. RFQs
Create an RFQ per package (optionally for a specific supplier). English (and a draft Arabic template that needs human review) include: project reference, scope/specification, BOQ items, quantities & units, delivery location, required date, datasheet & compliance
requirements, lead time, unit-price basis, delivery/unloading, tax treatment, payment terms, validity, exclusions/deviations, response deadline and your company contact. Export **XLSX** (supplier completes the yellow columns), **DOCX**, or copy the **email body**.
The application never sends email. *I have issued this RFQ manually* only records your action. Supplier contacts are never invented; a contact requires a `contact_source` and permitted use.

## 3. Quotations
Enter manually, import the completed RFQ sheet (`Your unit rate`, `Lead time`, `Remarks` columns), or accept an AI-extracted draft (a human must still choose the supplier and verify). Capture supplier, reference, date, validity, currency, tax treatment (+rate),
payment & delivery terms, exclusions, deviations, per line: quantity, unit, rate, discount, delivery/unloading/installation/tax inclusion, lead time, compliance. Status: Draft -> Pending Review -> Approved by a **Procurement Reviewer** (verified against the supplier's document).
Approved quotations are immutable (issue a revised quotation); `mark_expired` flags validity lapses.

## 4. Levelling (like-for-like)
For a package, each quotation shows: **quoted total (as quoted, original currency)** and a separate **normalised comparison value (SAR, pre-tax)**:
`required qty x rate x (1 - discount) x FX / (1 + tax rate if prices include tax)` per item, plus **approved** adjustments only (pending adjustments are listed, not applied). Also shown: coverage, missing items, quantity differences, unit issues,
delivery/unloading exclusions, validity, lead time, payment terms, exclusions, deviations. A quotation is *like-for-like* only if every item is covered, units convert, FX & tax basis are known, nothing is non-compliant and it is valid.
The tool shows an **advisory** lowest like-for-like quotation; it never awards.

## 5. Selection and rate publication
Propose a selection with a justification; selecting something other than the lowest like-for-like (or a non-like-for-like quotation) requires a documented reason. A Procurement Reviewer (or Commercial Approver at/above the value threshold) approves.
*Propose rates from this quotation* then creates **Pending Review** rates (rate type *Verified Supplier Quote*, or *Synthetic* if the quote is synthetic) linked to the quotation line, supplier, quote date and validity, with the pre-tax price derived when prices include tax.
Each rate still needs its own rate approval. Only then does the estimate price the item and the procurement line close.

## 6. Tips
* Use *Libraries -> without approved rate* to see catalogue gaps; all 927 catalogue resources start as Missing Rate.
* Foreign-currency quotes need an approved FX rate (Settings); the original currency is always preserved.
* Keep quotation validity realistic: an approved rate inherits `valid_until`, and expiry makes the item unpriced again (and raises `QUOTATION_EXPIRED` if a quotation lapses behind a used rate).
