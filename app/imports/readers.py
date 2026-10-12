"""Tabular file readers returning raw rows with their source row numbers. Never modifies the source file."""
from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.errors import ValidationFailed


@dataclass
class RawSheet:
    name: str
    rows: list[tuple[int, list[Any]]]       # (1-based source row number, cell values)
    warnings: list[str] = field(default_factory=list)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def list_sheets(path: Path) -> list[str]:
    if path.suffix.lower() in (".csv", ".txt"):
        return ["CSV"]
    import openpyxl
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as e:
        raise ValidationFailed(f"Cannot open workbook '{path.name}': {e}", code="MALFORMED_FILE")
    names = wb.sheetnames
    wb.close()
    return names


def read_sheet(path: Path, sheet: str | None = None) -> RawSheet:
    path = Path(path)
    if not path.exists():
        raise ValidationFailed(f"File not found: {path}", code="FILE_NOT_FOUND")
    ext = path.suffix.lower()
    if ext in (".csv", ".txt"):
        raw = path.read_bytes()
        warnings: list[str] = []
        for enc in ("utf-8-sig", "cp1256", "latin-1"):
            try:
                text = raw.decode(enc)
                if enc != "utf-8-sig":
                    warnings.append(f"File decoded as {enc} (not UTF-8); check Arabic/special characters.")
                break
            except UnicodeDecodeError:
                continue
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        rows = [(i, list(r)) for i, r in enumerate(csv.reader(io.StringIO(text), dialect), start=1)]
        return RawSheet("CSV", rows, warnings)
    if ext in (".xlsx", ".xlsm"):
        import openpyxl
        try:
            wb = openpyxl.load_workbook(path, data_only=True)
        except Exception as e:
            raise ValidationFailed(f"Cannot open workbook '{path.name}': {e}", code="MALFORMED_FILE")
        if sheet is None:
            # first visible sheet that has data
            for ws in wb.worksheets:
                if ws.sheet_state == "visible" and ws.max_row >= 1:
                    sheet = ws.title
                    break
            sheet = sheet or wb.sheetnames[0]
        if sheet not in wb.sheetnames:
            raise ValidationFailed(f"Sheet '{sheet}' not found. Available: {wb.sheetnames}")
        ws = wb[sheet]
        rows = [(i, list(r)) for i, r in enumerate(ws.iter_rows(values_only=True), start=1)]
        warnings = []
        # formulas without cached values read as None under data_only
        wb_f = openpyxl.load_workbook(path, data_only=False)
        wsf = wb_f[sheet]
        uncached = 0
        for rf, rv in zip(wsf.iter_rows(), ws.iter_rows()):
            for cf, cv in zip(rf, rv):
                if isinstance(cf.value, str) and cf.value.startswith("=") and cv.value is None:
                    uncached += 1
        if uncached:
            warnings.append(f"{uncached} formula cell(s) have no cached value (workbook not recalculated); "
                            "they were read as empty. Open and save in Excel/LibreOffice, then re-import.")
        return RawSheet(sheet, rows, warnings)
    raise ValidationFailed(f"Unsupported file type '{ext}'. Use .xlsx or .csv.", code="UNSUPPORTED_FILE")
