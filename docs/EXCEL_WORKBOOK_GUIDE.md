# Excel workbook guide

Generated from one specification (`app/excel/spec.py`) so every workbook shares identical headers, keys and IDs. Column-level detail: [EXCEL_DATA_DICTIONARY.md](EXCEL_DATA_DICTIONARY.md).

## Files (`templates/`) — 11 workbooks (the master + 10 standalone) and 2 Word templates
`estimate_master.xlsx` (27 sheets) · `boq_import_template.xlsx` · `takeoff_import_template.xlsx` (Takeoff + Resource Takeoff) · `resource_rate_template.xlsx` (Rate Dataset + Material Library) · `assembly_library_template.xlsx` ·
`assumption_register_template.xlsx` · `rfq_template.xlsx` · `vendor_quote_template.xlsx` · `quote_comparison_template.xlsx` · `clarification_register_template.xlsx` · `pricing_schedule_template.xlsx` ·
`letter_of_offer_template.docx` · `estimate_report_template.docx`. Regenerate with `python -m app.cli templates`. A project-populated master: *Reports -> Download master workbook* or `python -m app.cli export-workbook PRJ-0001 --out wb.xlsx`.

## Master sheets
1 Read Me · 2 Project Setup · 3 Project Summary · 4 Trade and Cost Code Mapping · 5 Pricing Schedule · 6 BOQ Import · 7 Direct Cost Build-Up · 8 Labour Library · 9 Material Library · 10 Plant and Equipment Library · 11 Subcontract Library ·
12 Assembly Library · 13 Assumptions Register · 14 Indirect Costs · 15 Commercial Calculation · 16 Procurement Register · 17 Vendor Directory · 18 Vendor Quotations · 19 Quote Comparison · 20 Clarification Register ·
21 Inclusions and Exclusions · 22 Risk Register · 23 Reconciliation · 24 Approval Log · 25 AI Instructions · 26 Data Dictionary · 27 Source Register (+ hidden `Lists` for validations).

## Conventions
Frozen panes at `B6`, filters on the header row, header row 5 (human), hidden row 4 (machine keys), data from row 6. **Yellow** = input (unlocked), **grey** = formula (locked), **blue** = read-only value from the application. Sheets are protected *without a password* (accident prevention, not security).
Data validation lists: statuses, rate types, resource types, canonical units, cost codes, pricing methods, line types, waste/productivity bases, severities, etc. Currency format `#,##0.00` (SAR); quantities `#,##0.000`; status and `MISMATCH` cells are highlighted by conditional formatting. Every workbook carries source/version info (Project Setup: project, fingerprint, generated time).

## Calculation strategy and compatibility
* The **Python engine is authoritative**; formulas mirror it for transparency (e.g. `Pricing Schedule!F = ROUND(D*E,2)`, the full commercial chain on *Commercial Calculation*, `Direct Cost Build-Up` amounts, `Quote Comparison` differences with `MINIFS`).
* openpyxl writes formulas **without cached values**. Workbooks set `fullCalcOnLoad`, so Excel recalculates on open. We never assume it happened: `verify-workbook` recalculates a **copy** with LibreOffice headless and checks every formula for errors and every *Check/Diff* column for `MISMATCH`.
* Tested with LibreOffice 7+/24+; formulas use only widely supported functions (`IF`, `ROUND`, `SUM`, `ABS`, `OR`, `AND`, `MINIFS` - Excel 2019+/365).
* A populated demo workbook recalculates with 217 formulas, 0 errors, 0 mismatches (see tests/excel).

## Validation on import (`excel/roundtrip.py`)
* Structure: all 27 sheets present; column keys unchanged; **formula cells overwritten by constants are detected**; the embedded estimate fingerprint is compared with the current data (**stale** warning).
* Import creates **drafts and proposals only**: new BOQ rows (re-import diff -> pending change requests), mapping, assumption overrides (Pending Review), indirect revisions (new Draft version), clarifications, scope entries, risks, vendors, rate proposals from the library sheets (Draft), assembly edits (new Draft version).
* Status/approval columns in a file are ignored; read-only values are never imported.
* Round-trip integrity is tested: export -> edit -> import -> identical BOQ in a fresh project.

## Rate Dataset sheet and the candidate importer
`resource_rate_template.xlsx` → sheet *Rate Dataset* is accepted by `python -m app.cli rates import` (header row 5 / hidden key row 4). Rows become **rate candidates** for review (not rates); currency and a known resource id are mandatory.
## Verification status
Workbooks are verified by LibreOffice headless recalculation (`verify-workbook`). **Microsoft Excel itself has not been available for testing**; recalculation on open (`fullCalcOnLoad`) is relied on there.
The numbered workspace receives the project master workbook in `5. Estimate & Cost Build-Up/`.
