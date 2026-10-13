"""Regenerates the data-derived documentation: docs/TRADE_TAXONOMY.md, docs/KSA_DATA_SOURCES.md (table), docs/EXCEL_DATA_DICTIONARY.md.
Run: python scripts/gen_docs.py"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def taxonomy() -> None:
    rows = list(csv.DictReader(open(ROOT / "data/taxonomy/cost_codes.csv", encoding="utf-8-sig")))
    out = ["# Trade taxonomy and cost codes", "",
           "Generated from `data/taxonomy/cost_codes.csv` by `scripts/gen_docs.py`. The taxonomy is **data, not code**: add a trade, sub-trade or",
           "cost code in *Settings -> Add cost code* (Administrator) or by adding rows to the CSV (loaded idempotently by `refdata.load_taxonomy`).",
           "No calculation-engine change is needed. Codes are stable identifiers used in resources, assemblies, BOQ items, workbooks and reports.", "",
           "Level 1 = division (A-L); level 2 = sub-trade; level 3+ = user-added cost codes (e.g. `D.07.01`).",
           "A project records its applicable trades (project settings / `project.json`); the cost-code tree itself is global and shared by resources, assemblies, BOQ items and reports.", ""]
    for d in [r for r in rows if r["level"] == "1"]:
        out.append(f"## {d['code']} - {d['name']}")
        out.append("")
        out.append("| Code | Sub-trade |")
        out.append("|---|---|")
        for r in rows:
            if r["parent_code"] == d["code"]:
                out.append(f"| `{r['code']}` | {r['name']} |")
        out.append("")
    (ROOT / "docs/TRADE_TAXONOMY.md").write_text("\n".join(out), encoding="utf-8")


def sources_table() -> str:
    rows = list(csv.DictReader(open(ROOT / "data/sources/source_register.csv", encoding="utf-8-sig")))
    out = ["| ID | Source | Organisation | Access status | Accessed | Licence / reuse (as observed) | Data collected |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        f = lambda k: (r[k] or "").replace("|", "/").replace("\n", " ")[:160]  # noqa: E731
        out.append(f"| {r['source_id']} | {f('name')} | {f('organisation')} | {f('access_status')} | {f('date_accessed') or '-'} | {f('licence_reuse_conditions')} | {f('data_collected') or 'none'} |")
    return "\n".join(out)


def excel_dictionary() -> None:
    from app.excel.master import REQUIRED_SHEETS
    from app.excel.spec import S
    out = ["# Excel data dictionary", "", "Generated from `app/excel/spec.py` (the single source of truth for all workbooks). Row 5 = headers, hidden row 4 = machine keys, data from row 6.", ""]
    cls = {"input": "Input (yellow)", "calc": "Formula (grey, locked)", "ro": "Read-only (blue)"}
    for name in REQUIRED_SHEETS:
        sp = S.get(name)
        if not sp:
            continue
        out += [f"## {name}", "", sp.instructions, "", "| Header | Key | Class | Format / list |", "|---|---|---|---|"]
        for c in sp.cols:
            out.append(f"| {c.header} | `{c.key}` | {cls[c.kind]} | {(c.fmt or '')}{(' / list ' + c.dv) if c.dv else ''}{(' / `' + c.formula + '`') if c.formula else ''} |".replace("|  /", "| "))
        out.append("")
    (ROOT / "docs/EXCEL_DATA_DICTIONARY.md").write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    (ROOT / "docs").mkdir(exist_ok=True)
    taxonomy()
    excel_dictionary()
    tbl = sources_table()
    (ROOT / "docs/_sources_table.md").write_text(tbl, encoding="utf-8")
    ks = ROOT / "docs/KSA_DATA_SOURCES.md"
    txt = ks.read_text(encoding="utf-8")
    b, e = "<!-- SOURCES_TABLE_BEGIN -->", "<!-- SOURCES_TABLE_END -->"
    if b in txt and e in txt:
        ks.write_text(txt[:txt.index(b) + len(b)] + "\n## Register (generated)\n" + tbl + "\n" + txt[txt.index(e):], encoding="utf-8")
    print("docs generated")
