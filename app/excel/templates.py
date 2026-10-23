"""Standalone workbook templates (templates/*.xlsx, *.docx). Same sheet specs as the master => identical headers & IDs."""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from ..database import Database
from ..exports.docx_templates import generate_docx_templates
from .builder import write_lists_sheet, write_sheet
from .master import _text_sheet, build_master
from .spec import C, DATE, QTY, SAR, S, TAKEOFF_COLS, TEMPLATE_ROWS, Sheet

RATE_DATASET = Sheet("Rate Dataset", "Rate Dataset (for ingestion)",
                     "Upload rate datasets with full provenance. Rows are STAGED, validated (duplicates, units, currency, dates, conflicts, unusual changes) and published only as 'Pending Review' rates after explicit reviewer action. Rate types: see Lists.",
                     [C("resource_id", "Resource ID", 14), C("description", "Description (for new resources)", 40, wrap=True), C("unit", "Unit", 8, dv="units"),
                      C("unit_price", "Unit price", 14, fmt=SAR), C("currency", "Currency", 9), C("rate_type", "Rate type", 26, dv="RateType"),
                      C("region", "Region", 12, dv="regions"), C("price_date", "Price date", 13, fmt=DATE), C("valid_until", "Valid until", 13, fmt=DATE),
                      C("source_id", "Source ID (Source Register)", 14), C("supplier_id", "Supplier ID", 12), C("tax_basis", "Tax basis", 16),
                      C("delivery_basis", "Delivery basis", 18), C("evidence", "Evidence / reference", 34, wrap=True)], importable=True)
RESOURCE_TAKEOFF = Sheet("Resource Takeoff", "Pre-calculated resource quantities per BOQ item",
                         "Use when the measured take-off already includes resource quantities. Each row prices a BOQ item directly from resource quantity x approved rate (no assembly factors, no extra waste).",
                         [C("item_code", "Item", 12), C("resource_id", "Resource ID", 16), C("description", "Description", 36, wrap=True),
                          C("quantity", "Quantity", 14, fmt=QTY), C("unit", "Unit", 8, dv="units")], importable=True)
TAKEOFF = Sheet("Takeoff", "Measured Take-off (quantities measured by a human)",
                "Enter or paste the quantities you measured. The application imports them as-is and never alters or invents quantities.", TAKEOFF_COLS, importable=True)
RFQ = Sheet("RFQ", "Request for Quotation items",
            "Completed by the supplier (yellow). Return to the procurement team; import with Vendor Quotations.",
            [C("id", "Item", 18, "ro"), C("description", "Description", 46, "ro", wrap=True), C("specification", "Specification", 44, "ro", wrap=True),
             C("quantity", "Qty", 10, "ro", QTY), C("unit", "Unit", 8, "ro"), C("unit_rate", "Your unit rate", 14, fmt=SAR), C("lead_time_days", "Lead time (days)", 12),
             C("comments", "Remarks / deviations", 36, wrap=True)])


def _single(path: Path, db: Database | None, specs: list[Sheet], title: str, intro: str) -> Path:
    wb = Workbook()
    wb.remove(wb.active)
    _text_sheet(wb, "Instructions", [(title, "h"), (intro, ""),
                                     ("Yellow = input, grey = formula (locked), blue = read-only. Sheets are protected without a password to prevent accidents.", ""),
                                     ("Imports create DRAFT / PENDING proposals only. Approval statuses typed into a file are ignored; approvals happen in the application.", ""),
                                     ("SYNTHETIC / DEMO figures, where present, are labelled and are NOT market quotes.", "")], width=110)
    for s in specs:
        write_sheet(wb, s, [], meta="BLANK TEMPLATE", template_rows=TEMPLATE_ROWS)
    units = [r["code"] for r in db.all("SELECT code FROM units ORDER BY code")] if db else []
    regions = [r["code"] for r in db.all("SELECT code FROM regions ORDER BY code")] if db else []
    codes = [r["code"] for r in db.all("SELECT code FROM cost_codes ORDER BY code")] if db else []
    write_lists_sheet(wb, units, regions, codes)
    wb.calculation.fullCalcOnLoad = True
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


TEMPLATE_FILES = [
    "estimate_master.xlsx", "boq_import_template.xlsx", "takeoff_import_template.xlsx", "resource_rate_template.xlsx",
    "assembly_library_template.xlsx", "assumption_register_template.xlsx", "rfq_template.xlsx", "vendor_quote_template.xlsx",
    "quote_comparison_template.xlsx", "clarification_register_template.xlsx", "pricing_schedule_template.xlsx",
    "letter_of_offer_template.docx", "estimate_report_template.docx",
]


def generate_all(out_dir: Path, db: Database | None = None) -> list[Path]:
    out_dir = Path(out_dir)
    out: list[Path] = []
    out.append(build_master(out_dir / "estimate_master.xlsx", db, blank=True))
    out.append(_single(out_dir / "boq_import_template.xlsx", db, [S["BOQ Import"]], "BOQ Import Template",
                       "Paste the client BOQ into the yellow columns (column headers may also be mapped in the application's import dialog)."))
    out.append(_single(out_dir / "takeoff_import_template.xlsx", db, [TAKEOFF, RESOURCE_TAKEOFF], "Take-off Import Template",
                       "Sheet 'Takeoff' carries measured quantities; sheet 'Resource Takeoff' optionally carries pre-calculated resource quantities."))
    out.append(_single(out_dir / "resource_rate_template.xlsx", db, [RATE_DATASET, S["Material Library"]], "Resource & Rate Template",
                       "'Rate Dataset' is the ingestion format (with provenance). 'Material Library' shows the library layout; other libraries use the same columns."))
    out.append(_single(out_dir / "assembly_library_template.xlsx", db, [S["Assembly Library"]], "Assembly Library Template",
                       "One row per assembly line. Waste/productivity bases must be explicit; approved versions are immutable."))
    out.append(_single(out_dir / "assumption_register_template.xlsx", db, [S["Assumptions Register"]], "Assumption Register Template",
                       "Effective assumption values and proposed project overrides."))
    out.append(_single(out_dir / "rfq_template.xlsx", db, [RFQ], "RFQ Template", "Request-for-quotation response sheet for suppliers."))
    out.append(_single(out_dir / "vendor_quote_template.xlsx", db, [S["Vendor Quotations"]], "Vendor Quotation Template",
                       "One row per quotation line with header terms repeated on each row."))
    out.append(_single(out_dir / "quote_comparison_template.xlsx", db, [S["Quote Comparison"]], "Quote Comparison Template",
                       "Levelled comparison. Quoted prices and normalised values are always shown separately."))
    out.append(_single(out_dir / "clarification_register_template.xlsx", db, [S["Clarification Register"]], "Clarification Register Template",
                       "Raise clarifications OPEN; resolve only with the client response and evidence."))
    out.append(_single(out_dir / "pricing_schedule_template.xlsx", db, [S["Pricing Schedule"]], "Pricing Schedule Template",
                       "Quantities x unit rates with an engine check column."))
    out += generate_docx_templates(out_dir)
    return out


def rate_workbook(path: Path, db: Database | None = None) -> Path:
    """The rates-entry workbook: the shipped 'Rate Dataset' layout plus a read-only 'Resource List' (ids, descriptions, units - no prices) to copy resource ids from."""
    _single(path, db, [RATE_DATASET], "Rates workbook",
            "Fill the yellow 'Rate Dataset' rows: one price per row with currency, price date and an evidence reference. Use 'Resource List' to find resource ids. "
            "After upload every row is a candidate for review - nothing becomes a rate until a different person approves it.")
    if db:
        from openpyxl import load_workbook
        wb = load_workbook(path)
        ws = wb.create_sheet("Resource List")
        ws.append(["Resource ID", "Description", "Unit", "Type"])
        for r in db.all("SELECT id, description, unit, resource_type FROM resources WHERE is_active=1 ORDER BY id"):
            ws.append([r["id"], r["description"], r["unit"], r["resource_type"]])
        ws.freeze_panes = "A2"
        ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 18, 70
        wb.save(path)
    return path


PRICE_LIST_HEADERS = ["Resource ID", "Description (for new resources)", "Unit", "Unit price", "Currency", "Rate type", "Region", "Price date", "Valid until",
                      "Source ID (Source Register)", "Supplier ID", "Tax basis", "Delivery basis", "Evidence / reference"]
PRICE_LIST_REFERENCE = ["Trade", "Type", "Category", "Specification (read only)"]


def price_list_workbook(path: Path, db: Database) -> Path:
    """One row per active catalogue resource (materials, labour, plant, equipment, subcontract packages), ordered by trade, with the price columns left BLANK for a person to fill.
    Same headers as the 'Rate Dataset' so it uploads as-is; rows left without a price are skipped on import (the rate stays missing)."""
    from openpyxl.styles import Alignment, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    ws = wb.active
    ws.title = "Rate Dataset"
    intro = ["Price list - every resource in the catalogue (no prices supplied).",
             "Fill the yellow cells for the items you have prices for: Unit price + Currency (required, never assumed). Add the price date, tax basis and where the price came from. Leave a row blank if you have no price - it simply stays missing.",
             "Do not change Resource ID or the grey columns. Then upload this file on the Rates workbook page - every priced row becomes a candidate that a different person approves."]
    for i, t in enumerate(intro, 1):
        ws.cell(i, 1, t).font = Font(bold=(i == 1), size=12 if i == 1 else 10)
        ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=10)
        ws.cell(i, 1).alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[2].height = ws.row_dimensions[3].height = 30
    hdr = 5
    for c, h in enumerate(PRICE_LIST_HEADERS + PRICE_LIST_REFERENCE, 1):
        cell = ws.cell(hdr, c, h)
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="DDE3F5" if c <= len(PRICE_LIST_HEADERS) else "E7E7E7")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    rows = db.all("SELECT r.id, r.description, r.unit, r.resource_type, r.cost_code, r.category, r.specification, c.name AS trade FROM resources r "
                  "LEFT JOIN cost_codes c ON c.code = r.cost_code WHERE r.is_active=1 ORDER BY r.cost_code, r.resource_type, r.id")
    yellow, grey = PatternFill("solid", fgColor="FFF8D6"), PatternFill("solid", fgColor="F2F2F2")
    for n, r in enumerate(rows, hdr + 1):
        vals = {1: r["id"], 2: r["description"], 3: r["unit"], 15: f'{r["cost_code"] or ""} {r["trade"] or ""}'.strip(), 16: r["resource_type"], 17: r["category"], 18: r["specification"]}
        for c in range(1, len(PRICE_LIST_HEADERS) + len(PRICE_LIST_REFERENCE) + 1):
            cell = ws.cell(n, c, vals.get(c))
            cell.fill = yellow if 4 <= c <= 14 else grey
        ws.cell(n, 4).number_format = "#,##0.00"
        ws.cell(n, 8).number_format = ws.cell(n, 9).number_format = "yyyy-mm-dd"
    last = hdr + len(rows)
    ws.freeze_panes = ws.cell(hdr + 1, 3)
    ws.auto_filter.ref = f"A{hdr}:{get_column_letter(len(PRICE_LIST_HEADERS) + len(PRICE_LIST_REFERENCE))}{last}"
    for c, w in enumerate([14, 46, 8, 14, 10, 24, 12, 13, 13, 16, 12, 14, 18, 34, 30, 12, 18, 40], 1):
        ws.column_dimensions[get_column_letter(c)].width = w
    dv = DataValidation(type="list", formula1='"Included,Excluded"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"L{hdr + 1}:L{last}")
    dv2 = DataValidation(type="list", formula1='"Verified Supplier Quote,Published Market Price,Official Index or Benchmark,Historical Actual"', allow_blank=True)
    ws.add_data_validation(dv2)
    dv2.add(f"F{hdr + 1}:F{last}")
    wb.save(path)
    return path
