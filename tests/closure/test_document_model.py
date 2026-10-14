"""Renderers: very long cells, many rows, empty tables, non-Latin text and missing-input markers (SYNTHETIC)."""
from __future__ import annotations

from app.tender import model

META = dict(project_id="P", project_name="n", customer="c", doc_id="P-D98", title="t", revision=1, issue_date="2027-01-01", status="Draft", author="a", reviewer="r", estimate_version="v1",
            fingerprint="ab", template="t", confidentiality="c", banner="B", synthetic_mark="S")


def _render_all(doc, tmp_path, name="x"):
    out = {}
    for fmt, fn in (("docx", model.render_docx), ("xlsx", model.render_xlsx), ("pdf", model.render_pdf)):
        p = tmp_path / f"{name}.{fmt}"
        fn(doc, {**META, "title": doc.title}, p)
        out[fmt] = model.parse_back(p)
    return out


def test_very_long_cell_and_many_rows_do_not_break_the_pdf(tmp_path):
    long_text = "word " * 6000                                                       # a single cell taller than a page
    rows = [[f"R{i}", "x" * 40, long_text if i == 3 else "short"] for i in range(250)]
    doc = model.Doc("D98", "Long content", [model.Section("S", ["p"], model.Table(["a", "b", "c"], rows))], xlsx=True)
    got = _render_all(doc, tmp_path)
    assert got["pdf"]["pages"] > 5 and "R249" in got["pdf"]["text"] and "R249" in got["docx"]["text"] and "R249" in got["xlsx"]["text"]


def test_empty_tables_non_latin_text_and_missing_markers(tmp_path):
    doc = model.Doc("D98", "Arabic العربية and symbols ≥ —", [model.Section("S", ["مرحبا " + model.missing("customer name")], model.Table(["a"], []))])
    got = _render_all(doc, tmp_path)
    assert "مرحبا" in got["docx"]["text"]                      # DOCX keeps the Arabic text; the PDF base font cannot draw it (documented limit) but must not fail
    assert doc.missing_inputs() == ["customer name"] and got["pdf"]["pages"] >= 1
