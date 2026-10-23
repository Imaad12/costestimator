"""BOQ builder (pick items -> BOQ document / project lines) and the full price-list workbook. SYNTHETIC data."""
from __future__ import annotations

import io
import re

import openpyxl

from app.database import get_db
from tests.integration.test_api_ui import client  # noqa: F401  (shared fixture)
from tests.integration.test_web_tender_pages import _login


def _fill(content, prices):
    """Open the downloaded price list, type prices (resource id -> (price, currency)) on whichever trade sheet holds the item, return xlsx bytes."""
    wb = openpyxl.load_workbook(io.BytesIO(content))
    for ws in wb.worksheets[1:]:
        hdr = {str(c.value): c.column for c in ws[5] if c.value}
        for row in range(6, ws.max_row + 1):
            rid = ws.cell(row, 1).value
            if rid in prices:
                ws.cell(row, hdr["Unit price"], prices[rid][0]); ws.cell(row, hdr["Currency"], prices[rid][1])
    buf = io.BytesIO(); wb.save(buf)
    return buf.getvalue()


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_price_list_has_one_sheet_per_trade_with_every_resource_and_blank_prices(client):
    db = get_db()
    _login(client, "proc")
    r = client.get("/rates/workbook/price-list.xlsx")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/vnd.openxmlformats")
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames[0] == "Start here" and len(wb.sheetnames) > 5 and wb.sheetnames[1].startswith("A ")
    rows = []
    for ws in wb.worksheets[1:]:
        hdr = {str(c.value): c.column for c in ws[5] if c.value}
        assert "Resource ID" in hdr and "Unit price" in hdr
        for row in ws.iter_rows(min_row=6, values_only=True):
            if row[0]:
                assert row[hdr["Unit price"] - 1] is None and row[hdr["Currency"] - 1] is None             # no price is ever supplied
                rows.append(row[0])
    assert len(rows) == len(set(rows)) == db.scalar("SELECT COUNT(*) FROM resources WHERE is_active=1") > 0


def test_price_list_is_filled_in_parts_and_the_latest_upload_wins(client):
    db = get_db()
    _login(client, "proc")
    pl = client.get("/rates/workbook/price-list.xlsx").content
    ids = [r["id"] for r in db.all("SELECT id FROM resources WHERE is_active=1 ORDER BY cost_code, id")]
    first, second = ids[0], ids[-1]                                         # different trades -> different sheets
    meta = {"source_name": "Price list parts test (SYNTHETIC)", "source_type": "Quotation", "default_currency": "SAR", "default_tax_basis": "Excluded"}
    chk = client.post("/rates/workbook/preview", data=meta, files={"file": ("a.xlsx", _fill(pl, {first: (10, "SAR")}), XLSX)})
    assert chk.status_code == 200 and "Listed rows with no price" in chk.text
    from app.config import get_settings
    from app.rate_updates import importer
    from app.models.actor import Actor
    proc = Actor("proc", "Procurement Reviewer", "proc")
    up = get_settings().projects_dir / "_uploads"
    def run(content, name):
        p = up / name; p.write_bytes(content)
        return importer.import_rates_file(db, proc, p, source_name=meta["source_name"], source_type="Quotation", default_currency="SAR", default_tax_basis="Excluded")
    r1 = run(_fill(pl, {first: (10, "SAR")}), "round1.xlsx")
    assert (r1["accepted"], r1["rejected"], r1["unchanged"], r1["replaces"]) == (1, 0, 0, 0) and r1["not_filled"] == len(ids) - 1
    r2 = run(_fill(pl, {first: (10, "SAR"), second: (7.5, "SAR")}), "round2.xlsx")                 # round 2: the first price is repeated, a second sheet is filled
    assert (r2["accepted"], r2["unchanged"], r2["replaces"]) == (1, 1, 0)
    r3 = run(_fill(pl, {first: (12, "SAR")}), "round3.xlsx")                                          # round 3: a corrected price for the first item; the second is not mentioned
    assert (r3["accepted"], r3["unchanged"], r3["replaces"]) == (1, 0, 1)
    st = {r["resource_id"] + ":" + r["original_price"]: r["status"] for r in db.all("SELECT resource_id, original_price, status FROM rate_candidates WHERE source_name=?", (meta["source_name"],))}
    assert st[f"{first}:10"] == "Rejected" and st[f"{first}:12"] == "Pending Review" and st[f"{second}:7.5"] == "Pending Review"        # latest wins; blank never retracts
    assert "Superseded by" in db.scalar("SELECT review_comments FROM rate_candidates WHERE resource_id=? AND original_price='10'", (first,))
    ids_open = db.scalar("SELECT COUNT(*) FROM rate_candidates WHERE source_name=? AND status='Pending Review'", (meta["source_name"],))
    assert ids_open == 2
    from app.rate_updates import candidates as cand
    cid = db.scalar("SELECT id FROM rate_candidates WHERE resource_id=? AND original_price='7.5'", (second,))
    cand.review(db, Actor("com", "Commercial Approver", "com"), cid, "approve", "checked")
    r4 = run(_fill(pl, {second: (9, "SAR")}), "round4.xlsx")                                           # a person already approved the 7.5: it is never touched, the new price is a new candidate
    assert (r4["accepted"], r4["replaces"]) == (1, 0)
    assert db.scalar("SELECT status FROM rate_candidates WHERE id=?", (cid,)) == "Approved for Publication"


def test_builder_page_lists_catalogue_and_builds_a_boq_with_only_approved_rates(client):
    db = get_db()
    _login(client, "est")
    page = client.get("/boq-builder")
    assert page.status_code == 200 and "BOQ builder" in page.text and 'name="q_MAT-A-001"' in page.text
    assert client.post("/boq-builder/build", data={"title": "x"}, follow_redirects=False).headers["location"].startswith("/boq-builder?err=")        # nothing picked
    bad = client.post("/boq-builder/build", data={"q_MAT-A-001": "abc"}, follow_redirects=False)
    assert "not+a+number" in bad.headers["location"]
    neg = client.post("/boq-builder/build", data={"q_MAT-A-001": "-2"}, follow_redirects=False)
    assert "greater+than+zero" in neg.headers["location"]
    r = client.post("/boq-builder/build", data={"title": "Package A", "mode": "download", "q_MAT-A-001": "12.5", "q_MAT-A-002": "", "q_NOPE-1": ""})
    assert r.status_code == 200 and "Package_A.xlsx" in r.headers["content-disposition"]
    ws = openpyxl.load_workbook(io.BytesIO(r.content)).active
    cells = [[c for c in row] for row in ws.iter_rows(values_only=True)]
    line = next(c for c in cells if c[7] and str(c[7]).startswith("MAT-A-001"))
    assert line[3] == 12.5 and line[4] is None and line[6] is None                      # quantity as typed; no approved rate -> rate and amount stay blank
    assert any("have no approved rate" in str(c[0]) for c in cells)
    assert len([c for c in cells if c[7]]) == 2                                          # header + the one selected line; the empty quantity was left out


def test_builder_adds_lines_to_a_project_boq(client):
    db = get_db()
    _login(client, "est")
    made = client.post("/ui/do/create_project", data={"name": "Builder test (SYNTHETIC)", "client": "FICTIONAL", "_next": "/projects/{result}/tower"}, follow_redirects=False)
    pid = made.headers["location"].split("/")[2]
    r = client.post("/boq-builder/build", data={"title": "From builder", "mode": "project", "project": pid, "q_MAT-A-001": "7"}, follow_redirects=False)
    assert r.headers["location"].startswith(f"/projects/{pid}/boq?ok="), r.headers["location"]
    row = db.one("SELECT quantity, unit, spec_ref FROM boq_items WHERE project_id=? AND spec_ref='MAT-A-001'", (pid,))
    assert row is not None and row["quantity"] in ("7", "7.0")
    no_proj = client.post("/boq-builder/build", data={"mode": "project", "q_MAT-A-001": "1"}, follow_redirects=False)
    assert "Choose+the+project" in no_proj.headers["location"]


def test_boq_upload_reads_a_workbook_and_creates_the_project_from_its_details(client, tmp_path):
    from tests.imports.test_boq_workbook import make
    f = make(tmp_path / "w.xlsx").read_bytes()
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    _login(client, "est")
    assert "BOQ upload" in client.get("/boq-upload").text
    r = client.post("/boq-upload/analyse", data={"project": ""}, files={"file": ("w.xlsx", f, mime)})
    assert r.status_code == 200 and "Totals only" in r.text and "swapped" in r.text and 'value="TEST WAREHOUSE (SYNTHETIC)"' in r.text
    stored = re.search(r'name="stored" value="([^"]+)"', r.text).group(1)
    nothing = client.post("/boq-upload/import", data={"stored": stored, "project": "", "new_name": "X"}, follow_redirects=False)
    assert "Tick+at+least+one+sheet" in nothing.headers["location"]
    done = client.post("/boq-upload/import", data={"stored": stored, "project": "", "new_name": "Test Warehouse (Synthetic)", "new_client": "Fictional Owner Co", "sheet": ["PLUMBING", "FIRE ALARM"]}, follow_redirects=False)
    loc = done.headers["location"]
    assert re.match(r"/projects/PRJ-\d+/boq\?ok=Imported\+8\+new", loc), loc
    pid = loc.split("/")[2]
    assert get_db().scalar("SELECT COUNT(*) FROM boq_items WHERE project_id=? AND item_type='item'", (pid,)) == 8
    assert client.post("/boq-upload/analyse", data={"project": ""}, files={"file": ("w.pdf", b"%PDF", "application/pdf")}, follow_redirects=False).headers["location"].startswith("/boq-upload?err=")


def test_rates_upload_page_imports_every_trade_sheet_of_the_price_list(client):
    db = get_db()
    _login(client, "proc")
    pl = client.get("/rates/workbook/price-list.xlsx").content
    ids = [r["id"] for r in db.all("SELECT id FROM resources WHERE is_active=1 ORDER BY cost_code, id")]
    meta = {"source_name": "Web parts test (SYNTHETIC)", "source_type": "Quotation", "default_currency": "SAR", "default_tax_basis": "Excluded"}
    chk = client.post("/rates/workbook/preview", data=meta, files={"file": ("p.xlsx", _fill(pl, {ids[0]: (5, "SAR"), ids[-1]: (6, "SAR")}), XLSX)})
    assert "All " in chk.text and "trade sheets" in chk.text and "Import 2 row" in chk.text                 # the page offers 'all trade sheets' and counts rows from both
    stored = re.search(r'name="stored" value="([^"]+)"', chk.text).group(1)
    done = client.post("/rates/workbook/import", data={**meta, "stored": stored, "sheet": "*", "header_row": "5"}, follow_redirects=False)
    assert "2+price+row" in done.headers["location"], done.headers["location"]
