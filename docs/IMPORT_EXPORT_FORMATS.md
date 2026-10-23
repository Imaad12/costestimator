# Import / export formats

## BOQ / take-off (CSV, XLSX, XLSM)
Header row is auto-detected (first 40 rows; ≥2 recognised headers). Recognised synonyms (English and Arabic, case-insensitive): item code (`Item`, `Item No`, `Ref`, `S/N`, `البند`), description (`Description`, `Particulars`, `Work Item`, `الوصف`), trade, unit (`Unit`, `UOM`, `الوحدة`),
quantity (`Qty`, `Quantity`, `الكمية`), client rate, client amount, drawing ref, spec ref, cost code, revision. Required: **description, unit, quantity** (map manually if not detected). CSV delimiter and encoding (UTF-8, Windows-1256, Latin-1) are detected; the file's sheet and source row are stored per item.

Row handling: blank row -> counted; description-only row -> heading (kept, gives the `section`); qty present but not numeric / negative (unless `allow_negative`) / missing -> **rejected with reason** (table `boq_rejected_rows`); zero quantity -> flagged; missing/unknown/ambiguous unit -> imported with the unit left empty and flagged;
duplicate code -> kept as `code#2`, flagged; missing description -> flagged; client amount ≠ qty × rate -> flagged. Re-import of the same project: unchanged rows skipped, differing quantity/description/unit become **pending change requests**, items absent from the new file are marked *Missing in latest revision*, new items added.
Unit synonyms/ambiguity: `data/units/units.csv` (`m, mm, km, m2, ha, m3, l, kg, t, nr, pair, set, item, ls, point, roll, bag, sheet, length_piece, tr, kw, kva, hr, day, week, month, trip, percent`). Ambiguous spellings (`ton`, `tons`, `cm`, `sum`) are never normalised silently.

**Take-off with pre-calculated resource quantities:** columns `Item`, `Resource ID`, `Quantity` (+ `Unit`, `Description`); each row prices the item directly from the resource quantity and approved rate (no factors, no extra waste).

## Rate datasets (`Rate Dataset` sheet / CSV / JSON)
`resource_id, description, unit, unit_price, currency, rate_type, region, price_date, valid_until, source_id, supplier_id, tax_basis, delivery_basis, evidence` - staged, validated, published as Pending Review (see KSA_DATA_SOURCES).

**Full price list** (`/rates/workbook/price-list.xlsx`, button on the Rates workbook page): one row per active catalogue resource (materials, labour, plant, equipment, subcontract packages) ordered by trade, in the `Rate Dataset` column layout with the price columns blank and read-only reference columns (Trade, Type, Category, Specification). It uploads as-is. A listed resource whose **Unit price is left blank is skipped** - it is not a candidate and not an error; the count is reported as "not filled" and the rate stays missing. Rows with a price still need a currency (never assumed) and become candidates for human review.

## BOQ builder (menu: BOQ builder)
Pick catalogue items (work-item assemblies and resources, grouped by trade A-L) and type a quantity for each; only items with a quantity above zero are used. Outputs: (a) a **BOQ document** `.xlsx` (headings per trade, item, description, unit, quantity, unit rate and a formula amount **only where an Approved rate with a price exists**, a total, a DRAFT banner, a count of unpriced lines, and a SYNTHETIC banner when any synthetic item or rate is used); (b) **Add to the project's BOQ**: the same selection written to the project's uploads folder as a plain Item/Description/Unit/Quantity/Cost code/Spec ref file (no rate column) and imported through the normal BOQ importer (drafts, same checks, same change-request rules). The software never measures, suggests or completes a quantity.

## Catalogues and seeds (`data/`)
`taxonomy/cost_codes.csv` · `units/units.csv` · `regions/regions.csv` · `materials/materials.csv`, `labour/labour_categories.csv`, `plant/plant_categories.csv`, `equipment/equipment_categories.csv`, `subcontractors/subcontract_packages.csv`
(columns `id,resource_type,cost_code,category,description,aliases,specification,brand_requirements,unit,notes`; **no prices**) · `assumptions/assumptions_register.csv` (`id,family,name,description,applies_to,applicability,value_type,default_value,unit,engine_key,mandatory_for_projects,confidence,source,notes`) ·
`assemblies/standard_assemblies.csv` (structure only) · `indirects/indirect_categories.csv` · `commercial_rules/policy_template.json` · `sources/source_register.csv` · `suppliers/*_schema.csv` · `demo/demo_boq.{xlsx,csv}` (SYNTHETIC).

## Quotation lines (XLSX/CSV)
Header with a unit-rate column plus `Item`/`Description`: `Item` (procurement item id), `Description`, `Specification`, `Qty`, `Unit`, `Your unit rate`, `Discount %`, `Lead time`, `Remarks / deviations`. Rows with no rate are treated as *not quoted*; non-numeric rates are reported and skipped. Imported quotations are Drafts.

## Exports
* **RFQ**: `.xlsx` (items + terms sheet), `.docx`, plain-text email body (Subject + body).
* **Client pricing schedule** `.xlsx`: item, description, unit, quantity, unit rate, amount, note; totals by formula; tax lines; banner (PRELIMINARY / SUBMISSION READY / DEMO / SYNTHETIC / PROVISIONAL). **No internal cost, markup or allocation is included.**
* **Letter of offer** `.docx` from `templates/letter_of_offer_template.docx` (`{{placeholders}}`: company, project, totals, tax, validity, payment terms, inclusions, exclusions, qualifications, clarifications).
* **Estimate report** `.docx` (summary, cost-to-price reconciliation, exceptions, assumptions) and **reconciliation/audit report** `.xlsx`.
* **Master workbook** `.xlsx`; **project package** `.zip` (JSON of all project tables + uploads + outputs + manifest hashes); **backup** `.zip`.
* Files are written under `data/outputs/<PROJECT>/`; uploads under `data/projects/<PROJECT>/uploads/` and are never overwritten or modified (a same-named upload gets a numeric suffix; the importer also keeps a hashed copy).

## PDFs and images are not read by the application (by design)
There is deliberately **no OCR and no PDF-table extraction** in the application. The importer reads `.xlsx` and `.csv` only (a `.pdf` is refused with `UNSUPPORTED_FILE`). When a BOQ arrives as a PDF, a person - or any outside tool - extracts the table into CSV/XLSX, and that file is imported with provenance:
`import_boq(..., derived_from={"source_file", "source_sha256", "method", "note"})` (REST/CLI: the same keys). Such an import is flagged **UNVERIFIED TRANSCRIPTION**: the completeness report shows an Open row, the readiness gate lists it as a reason, and it clears only when a *different* person records `record_transcription_check` (what was compared with what). The project indexer still extracts a PDF's text layer for searching; if the layer has a Quantity header and units but no numbers it is stored as `Extracted - incomplete`.
