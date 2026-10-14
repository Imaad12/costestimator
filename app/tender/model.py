"""Document content model and deterministic renderers (DOCX, XLSX, PDF) for the tender / handover packs.

One structured `Doc` is rendered to every format, so the formats cannot disagree. Rendering is deterministic: zip timestamps and document properties are pinned
and the PDF is written in invariant mode, so identical inputs and template versions give byte-identical files (checked by sha256 in the manifest).
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

MISSING = "[[MISSING: "
FIXED_ZIP_TIME = (2000, 1, 1, 0, 0, 0)
PDF_MAP = {"—": "-", "–": "-", "≥": ">=", "≤": "<=", "→": "->", "‘": "'", "’": "'", "“": '"', "”": '"', "×": "x", "…": "...", " ": " "}


def missing(what: str) -> str:
    return f"{MISSING}{what}]]"


@dataclass
class Table:
    headers: list[str]
    rows: list[list]
    caption: str = ""


@dataclass
class Section:
    heading: str
    paras: list[str] = field(default_factory=list)
    table: Table | None = None
    bullets: list[str] = field(default_factory=list)


@dataclass
class Doc:
    code: str                              # catalogue code D01..D45
    title: str
    sections: list[Section] = field(default_factory=list)
    facts: dict = field(default_factory=dict)
    refs: list[str] = field(default_factory=list)         # stable ids of related documents / queries / assumptions
    sources: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    xlsx: bool = False

    def all_text(self) -> str:
        out = [self.title]
        for s in self.sections:
            out.append(s.heading)
            out += s.paras + s.bullets
            if s.table:
                out += [str(h) for h in s.table.headers] + [str(c) for r in s.table.rows for c in r]
        out += self.limitations + self.sources
        return "\n".join(out)

    def missing_inputs(self) -> list[str]:
        return sorted(set(re.findall(r"\[\[MISSING: ([^\]]+)\]\]", self.all_text())))

    def content_hash(self, meta: dict) -> str:
        blob = json.dumps({"meta": meta, "title": self.title, "sections": [vars(s) | {"table": vars(s.table) if s.table else None} for s in self.sections],
                           "facts": self.facts, "refs": self.refs, "limitations": self.limitations}, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for ch in iter(lambda: f.read(65536), b""):
            h.update(ch)
    return h.hexdigest()


def _pin_zip(path: Path) -> None:
    """Rewrite an OOXML zip with fixed entry timestamps so the bytes are reproducible."""
    buf = io.BytesIO()
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in sorted(zin.infolist(), key=lambda i: i.filename):
            zi = zipfile.ZipInfo(info.filename, FIXED_ZIP_TIME)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o600 << 16
            zout.writestr(zi, zin.read(info.filename))
    path.write_bytes(buf.getvalue())


def _pdf_safe(s: str) -> str:
    for k, v in PDF_MAP.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


def meta_rows(meta: dict) -> list[tuple[str, str]]:
    keys = [("Project ID", "project_id"), ("Project name", "project_name"), ("Customer", "customer"), ("Document ID", "doc_id"), ("Title", "title"), ("Revision", "revision"),
            ("Issue date", "issue_date"), ("Status", "status"), ("Author", "author"), ("Reviewer", "reviewer"), ("Estimate version", "estimate_version"),
            ("Estimate fingerprint", "fingerprint"), ("Template", "template"), ("Confidentiality", "confidentiality")]
    return [(lbl, str(meta.get(k, ""))) for lbl, k in keys]


# ------------------------------------------------------------------------------------------------ DOCX
def render_docx(doc: Doc, meta: dict, path: Path) -> None:
    from datetime import datetime

    from docx import Document
    from docx.shared import Pt
    d = Document()
    cp = d.core_properties
    cp.author, cp.last_modified_by, cp.title = "KSA Construction Estimating Suite", "KSA Construction Estimating Suite", doc.title
    cp.created = cp.modified = datetime.fromisoformat(meta["issue_date"] + "T00:00:00")
    cp.comments = meta["banner"][:250]
    sec = d.sections[0]
    sec.header.paragraphs[0].text = f"{meta['doc_id']} | {doc.title} | Rev {meta['revision']} | {meta['status']}"
    sec.footer.paragraphs[0].text = meta["banner"]
    d.add_heading(doc.title, 0)
    p = d.add_paragraph(meta["banner"])
    p.runs[0].bold = True
    if meta.get("synthetic_mark"):
        q = d.add_paragraph(meta["synthetic_mark"])
        q.runs[0].bold = True
    t = d.add_table(rows=0, cols=2)
    t.style = "Table Grid"
    for k, v in meta_rows(meta):
        r = t.add_row().cells
        r[0].text, r[1].text = k, v
    for s in doc.sections:
        d.add_heading(s.heading, 1)
        for para in s.paras:
            d.add_paragraph(para)
        for b in s.bullets:
            d.add_paragraph(b, style="List Bullet")
        if s.table:
            if s.table.caption:
                d.add_paragraph(s.table.caption).runs[0].italic = True
            tb = d.add_table(rows=1, cols=len(s.table.headers))
            tb.style = "Table Grid"
            for i, h in enumerate(s.table.headers):
                tb.rows[0].cells[i].text = str(h)
                for r_ in tb.rows[0].cells[i].paragraphs[0].runs:
                    r_.bold = True
                    r_.font.size = Pt(9)
            for row in s.table.rows:
                cells = tb.add_row().cells
                for i, c in enumerate(row):
                    cells[i].text = "" if c is None else str(c)
    if doc.limitations:
        d.add_heading("Assumptions, exclusions and limitations", 1)
        for x in doc.limitations:
            d.add_paragraph(x, style="List Bullet")
    if doc.sources:
        d.add_heading("Source references", 1)
        for x in doc.sources:
            d.add_paragraph(x, style="List Bullet")
    d.save(str(path))
    _pin_zip(path)


# ------------------------------------------------------------------------------------------------ XLSX
def render_xlsx(doc: Doc, meta: dict, path: Path) -> None:
    from datetime import datetime

    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Document"
    ws.append(["SYNTHETIC / DEMONSTRATION MARKINGS AND STATUS"])
    ws["A1"].font = Font(bold=True)
    ws.append([meta["banner"]])
    for k, v in meta_rows(meta):
        ws.append([k, v])
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 100
    used = {"Document"}
    for i, s in enumerate(x for x in doc.sections if x.table):
        name = re.sub(r"[\[\]\*\?/\\:]", "", s.heading)[:28] or f"Table{i}"
        base, n = name, 1
        while name in used:
            n += 1
            name = f"{base[:25]}_{n}"
        used.add(name)
        w = wb.create_sheet(name)
        w.append(s.table.headers)
        for c in w[1]:
            c.font = Font(bold=True)
        for row in s.table.rows:
            w.append(["" if c is None else (c if isinstance(c, (int, float)) else str(c)) for c in row])
        for col in w.columns:
            w.column_dimensions[col[0].column_letter].width = min(60, max(12, max(len(str(c.value or "")) for c in col[:50]) + 2))
    wb.properties.creator = wb.properties.lastModifiedBy = "KSA Construction Estimating Suite"
    wb.properties.created = wb.properties.modified = datetime.fromisoformat(meta["issue_date"] + "T00:00:00")
    wb.save(str(path))
    _pin_zip(path)


# ------------------------------------------------------------------------------------------------ PDF
def render_pdf(doc: Doc, meta: dict, path: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table as RTable, TableStyle
    ss = getSampleStyleSheet()
    small = ss["BodyText"].clone("small", fontSize=7.5, leading=9)
    esc = lambda x: _pdf_safe(str(x)).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")      # noqa: E731

    def footer(c, d_):
        c.saveState()
        c.setFont("Helvetica", 7)
        c.drawString(12 * mm, 8 * mm, _pdf_safe(f"{meta['doc_id']} rev {meta['revision']} | {meta['status']} | {meta['banner']}")[:190])
        c.drawRightString(285 * mm, 8 * mm, f"Page {d_.page}")
        c.restoreState()
    pdf = SimpleDocTemplate(str(path), pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=14 * mm, invariant=1,
                            title=_pdf_safe(doc.title), author="KSA Construction Estimating Suite")
    story = [Paragraph(esc(doc.title), ss["Title"]), Paragraph(f"<b>{esc(meta['banner'])}</b>", ss["BodyText"])]
    if meta.get("synthetic_mark"):
        story.append(Paragraph(f"<b>{esc(meta['synthetic_mark'])}</b>", ss["BodyText"]))
    mt = RTable([[Paragraph(esc(k), small), Paragraph(esc(v), small)] for k, v in meta_rows(meta)], colWidths=[40 * mm, 220 * mm])
    mt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [Spacer(1, 4), mt]
    for s in doc.sections:
        story.append(Paragraph(esc(s.heading), ss["Heading2"]))
        for p in s.paras:
            story.append(Paragraph(esc(p), ss["BodyText"]))
        for b in s.bullets:
            story.append(Paragraph("&bull; " + esc(b), ss["BodyText"]))
        if s.table and s.table.rows is not None:
            if s.table.caption:
                story.append(Paragraph(f"<i>{esc(s.table.caption)}</i>", small))
            data = [[Paragraph(f"<b>{esc(h)}</b>", small) for h in s.table.headers]] + [[Paragraph(esc("" if c is None else c), small) for c in r] for r in s.table.rows]
            n = max(1, len(s.table.headers))
            tb = RTable(data, colWidths=[(262 * mm) / n] * n, repeatRows=1)
            tb.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story.append(tb)
    if doc.limitations:
        story.append(Paragraph("Assumptions, exclusions and limitations", ss["Heading2"]))
        story += [Paragraph("&bull; " + esc(x), ss["BodyText"]) for x in doc.limitations]
    if doc.sources:
        story.append(Paragraph("Source references", ss["Heading2"]))
        story += [Paragraph("&bull; " + esc(x), ss["BodyText"]) for x in doc.sources]
    pdf.build(story, onFirstPage=footer, onLaterPages=footer)


# ------------------------------------------------------------------------------------------------ parse-back (used by the pack validator and tests)
def parse_back(path: Path) -> dict:
    """Open the file with an independent reader and return its text; raises if the file is not a genuine document of its type."""
    ext = path.suffix.lower()
    if ext == ".docx":
        from docx import Document
        d = Document(str(path))
        text = "\n".join(p.text for p in d.paragraphs) + "\n" + "\n".join(c.text for t in d.tables for r in t.rows for c in r.cells)
        return dict(format="docx", text=text, header=d.sections[0].header.paragraphs[0].text)
    if ext == ".xlsx":
        from openpyxl import load_workbook
        wb = load_workbook(str(path))
        text = "\n".join(str(c.value) for ws in wb for row in ws.iter_rows() for c in row if c.value is not None)
        return dict(format="xlsx", text=text, sheets=wb.sheetnames)
    if ext == ".pdf":
        raw = path.read_bytes()
        if not raw.startswith(b"%PDF-"):
            raise ValueError("not a PDF (missing %PDF header)")
        from pypdf import PdfReader
        r = PdfReader(str(path))
        return dict(format="pdf", text="\n".join((pg.extract_text() or "") for pg in r.pages), pages=len(r.pages))
    raise ValueError(f"unsupported {ext}")
