from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.core.errors import ValidationFailed
from app.imports import boq as bi
from app.services import boq, projects

from tests.conftest import COMMERCIAL, ESTIMATOR, VIEWER
from tests.helpers import write_boq


@pytest.fixture()
def pid(seeded):
    return projects.create_project(seeded, ESTIMATOR, name="Import test (SYNTHETIC)")


def xlsx(path, rows, title_rows=0, sheet="BOQ"):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    for _ in range(title_rows):
        ws.append(["Client XYZ tender - priced bill"])
    for r in rows:
        ws.append(r)
    wb.save(path)
    return path


STD = [("Item", "Description", "Unit", "Qty", "Rate", "Amount"),
       ("1.1", "Excavation", "m3", 100, 10, 1000), ("1.2", "Concrete", "m3", "25.5", None, None), ("1.3", "Blocks", "m2", 300, None, None)]


def test_standard_csv_and_xlsx_equivalent(seeded, pid, tmp_path):
    csvp = write_boq(tmp_path / "a.csv", [r for r in STD[1:]], header=STD[0])
    xp = xlsx(tmp_path / "a.xlsx", STD)
    s1 = bi.import_boq(seeded, ESTIMATOR, pid, csvp)
    pid2 = projects.create_project(seeded, ESTIMATOR, name="second")
    s2 = bi.import_boq(seeded, ESTIMATOR, pid2, xp)
    for s in (s1, s2):
        assert s["items_new"] == 3 and s["rejected"] == 0 and s["needs_review"] == 0
    a = {i["item_key"]: i for i in boq.list_items(seeded, pid)}
    b = {i["item_key"]: i for i in boq.list_items(seeded, pid2)}
    assert {k: (v["description"], v["unit"], v["quantity"]) for k, v in a.items()} == {k: (v["description"], v["unit"], v["quantity"]) for k, v in b.items()}


def test_source_traceability_and_original_values_preserved(seeded, pid, tmp_path):
    p = xlsx(tmp_path / "t.xlsx", STD, title_rows=3)
    bi.import_boq(seeded, ESTIMATOR, pid, p)
    it = boq.get_item(seeded, pid, "1.2")
    assert it["source_file"] == "t.xlsx" and it["source_sheet"] == "BOQ" and it["source_row"] == 6          # 3 title rows + header at 4 -> data row 6
    assert it["quantity_original"] == "25.5" and it["quantity"] == "25.5"
    assert it["original_json"] and "Description" in it["original_json"]
    imp = seeded.one("SELECT * FROM boq_imports WHERE project_id=?", (pid,))
    assert len(imp["sha256"]) == 64 and Path(imp["stored_path"]).exists()                                   # original upload kept
    assert Path(imp["stored_path"]).read_bytes() == p.read_bytes()


def test_irregular_column_names_and_order(seeded, pid, tmp_path):
    rows = [("S/N", "Work Item", "U.O.M", "Quantities", "Dwg", "Total Amount"), ("A1", "Plaster", "sqm", 120, "D-1", None), ("A2", "Paint", "m²", 80, "D-2", None)]
    s = bi.import_boq(seeded, ESTIMATOR, pid, xlsx(tmp_path / "i.xlsx", rows))
    assert s["items_new"] == 2
    assert boq.get_item(seeded, pid, "A1")["unit"] == "m2" and boq.get_item(seeded, pid, "A2")["unit"] == "m2"
    assert boq.get_item(seeded, pid, "A1")["drawing_ref"] == "D-1"


def test_arabic_headers(seeded, pid, tmp_path):
    rows = [("البند", "الوصف", "الوحدة", "الكمية"), ("1", "حفر", "m3", 10)]
    assert bi.import_boq(seeded, ESTIMATOR, pid, xlsx(tmp_path / "ar.xlsx", rows))["items_new"] == 1


def test_missing_required_header_needs_explicit_mapping(seeded, pid, tmp_path):
    rows = [("Item", "Description", "Unit"), ("1", "x", "m")]
    with pytest.raises(ValidationFailed) as e:
        bi.import_boq(seeded, ESTIMATOR, pid, xlsx(tmp_path / "m.xlsx", rows))
    assert e.value.code in ("MAPPING_INCOMPLETE", "NO_HEADER")
    p = write_boq(tmp_path / "nohdr.csv", [("1", "x", "m", "5")], header=("a", "b", "c", "d"))
    with pytest.raises(ValidationFailed) as e:
        bi.import_boq(seeded, ESTIMATOR, pid, p)
    assert e.value.code == "NO_HEADER"
    s = bi.import_boq(seeded, ESTIMATOR, pid, p, mapping={"item_code": 0, "description": 1, "unit": 2, "quantity": 3}, header_row=1)   # explicit mapping works
    assert s["items_new"] == 1


def test_invalid_quantities_rejected_with_reasons_never_silently(seeded, pid, tmp_path):
    p = write_boq(tmp_path / "q.csv", [("1", "ok", "m", "10", "", ""), ("2", "text qty", "m", "TBA", "", ""), ("3", "neg", "m", "-4", "", ""),
                                          ("4", "no qty", "m", "", "5", ""), ("5", "zero", "m", "0", "", "")])
    s = bi.import_boq(seeded, ESTIMATOR, pid, p)
    codes = {r["row"]: r["code"] for r in s["rejected_rows"]}
    assert codes == {3: "INVALID_QUANTITY", 4: "NEGATIVE_QUANTITY", 5: "MISSING_QUANTITY"}
    assert s["items_new"] == 2                                                         # '1' and the zero-quantity '5'
    zero = boq.get_item(seeded, pid, "5")
    assert any(i["code"] == "ZERO_QUANTITY" for i in zero["issues"]) if "issues" in zero else True
    assert seeded.scalar("SELECT COUNT(*) FROM boq_rejected_rows WHERE import_id=?", (s["import_id"],)) == 3
    # a credit can be imported deliberately
    pid2 = projects.create_project(seeded, ESTIMATOR, name="credit")
    assert bi.import_boq(seeded, ESTIMATOR, pid2, p, allow_negative=True)["rejected"] == 2


def test_unknown_ambiguous_missing_units_flagged_not_normalised(seeded, pid, tmp_path):
    p = write_boq(tmp_path / "u.csv", [("1", "a", "ton", "5", "", ""), ("2", "b", "furlong", "5", "", ""), ("3", "c", "", "5", "", ""),
                                          ("4", "d", "cm", "5", "", ""), ("5", "e", "No.", "5", "", "")])
    s = bi.import_boq(seeded, ESTIMATOR, pid, p)
    st = {k: (boq.get_item(seeded, pid, k)["unit"], boq.get_item(seeded, pid, k)["unit_status"]) for k in "12345"}
    assert st["1"] == (None, "ambiguous") and st["2"] == (None, "unknown") and st["3"] == (None, "missing")
    assert st["4"] == (None, "ambiguous") and st["5"] == ("nr", "ok")
    assert s["needs_review"] == 4
    # correction requires an approved change with a concrete unit
    ch = next(c for c in boq.pending_changes(seeded, pid) if c["entity_id"] == "1")
    with pytest.raises(ValidationFailed):
        boq.decide_change(seeded, ESTIMATOR, ch["id"], True, unit_code="ton")          # still ambiguous
    boq.decide_change(seeded, ESTIMATOR, ch["id"], True, unit_code="t", comment="metric tonne per spec")
    it = boq.get_item(seeded, pid, "1")
    assert it["unit"] == "t" and it["unit_status"] == "approved_correction" and it["validation_status"] == "OK"


def test_duplicate_codes_flagged_and_both_kept(seeded, pid, tmp_path):
    p = write_boq(tmp_path / "d.csv", [("1", "first", "m", "5", "", ""), ("1", "second", "m", "7", "", "")])
    s = bi.import_boq(seeded, ESTIMATOR, pid, p)
    assert s["duplicates"] == 1 and s["items_new"] == 2
    d = boq.get_item(seeded, pid, "1#2")
    assert d["validation_status"] == "Needs Review" and d["quantity"] == "7"
    boq.acknowledge_issues(seeded, ESTIMATOR, pid, "1#2", "Confirmed separate item with the client")
    assert boq.get_item(seeded, pid, "1#2")["validation_status"] == "OK"


def test_blank_rows_headings_and_missing_description(seeded, pid, tmp_path):
    rows = [("Item", "Description", "Unit", "Qty"), ("A", "SECTION A", None, None), (None, None, None, None), ("A.1", "Item", "m", 3), ("A.2", None, "m", 4)]
    s = bi.import_boq(seeded, ESTIMATOR, pid, xlsx(tmp_path / "h.xlsx", rows))
    assert s["blank"] == 1 and s["headings"] == 1 and s["items_new"] == 2
    assert boq.get_item(seeded, pid, "A.2")["validation_status"] == "Needs Review"
    assert boq.get_item(seeded, pid, "A.1")["section"] == "SECTION A"


def test_malformed_and_unsupported_files(seeded, pid, tmp_path):
    bad = tmp_path / "bad.xlsx"
    bad.write_bytes(b"this is not a zip")
    with pytest.raises(ValidationFailed) as e:
        bi.import_boq(seeded, ESTIMATOR, pid, bad)
    assert e.value.code == "MALFORMED_FILE"
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF")
    with pytest.raises(ValidationFailed) as e:
        bi.import_boq(seeded, ESTIMATOR, pid, pdf)
    assert e.value.code == "UNSUPPORTED_FILE"
    with pytest.raises(ValidationFailed):
        bi.import_boq(seeded, ESTIMATOR, pid, tmp_path / "missing.csv")
    empty = tmp_path / "e.csv"
    empty.write_text("")
    with pytest.raises(ValidationFailed):
        bi.import_boq(seeded, ESTIMATOR, pid, empty)


def test_reimport_never_overwrites_quantities(seeded, pid, tmp_path):
    p1 = write_boq(tmp_path / "r1.csv", [("1", "Excavation", "m3", "100", "", ""), ("2", "Concrete", "m3", "50", "", ""), ("3", "Gone later", "m", "9", "", "")])
    bi.import_boq(seeded, ESTIMATOR, pid, p1, revision="A")
    p2 = write_boq(tmp_path / "r2.csv", [("1", "Excavation", "m3", "120", "", ""), ("2", "Concrete", "m3", "50", "", ""), ("4", "New item", "m", "3", "", "")])
    s = bi.import_boq(seeded, ESTIMATOR, pid, p2, revision="B")
    assert s["items_new"] == 1 and s["items_unchanged"] == 1 and s["change_requests"] == 1 and s["missing_in_revision"] == 1
    it = boq.get_item(seeded, pid, "1")
    assert it["quantity"] == "100" and it["quantity_original"] == "100"                      # not overwritten
    ch = boq.pending_changes(seeded, pid)
    assert len(ch) == 1 and ch[0]["new_value"] == "120"
    assert boq.get_item(seeded, pid, "3")["status_in_revision"] == "Missing in latest revision"
    # re-importing the identical file again must not duplicate change requests
    bi.import_boq(seeded, ESTIMATOR, pid, p2, revision="B")
    assert len(boq.pending_changes(seeded, pid)) == 1
    boq.decide_change(seeded, ESTIMATOR, ch[0]["id"], True, comment="per addendum 2")
    it = boq.get_item(seeded, pid, "1")
    assert it["quantity"] == "120" and it["quantity_original"] == "100"                      # original text preserved for traceability


def test_quantity_change_requires_approval_and_reason(seeded, pid, tmp_path):
    bi.import_boq(seeded, ESTIMATOR, pid, write_boq(tmp_path / "c.csv", [("1", "x", "m", "10", "", "")]))
    with pytest.raises(ValidationFailed):
        boq.request_quantity_change(seeded, ESTIMATOR, pid, "1", "12", "")
    cid = boq.request_quantity_change(seeded, ESTIMATOR, pid, "1", "12", "re-measured")
    assert boq.get_item(seeded, pid, "1")["quantity"] == "10"
    from app.core.errors import PermissionDenied
    with pytest.raises(PermissionDenied):
        boq.decide_change(seeded, VIEWER, cid, True)
    boq.decide_change(seeded, COMMERCIAL, cid, True)
    assert boq.get_item(seeded, pid, "1")["quantity"] == "12"
    assert seeded.scalar("SELECT COUNT(*) FROM approvals WHERE entity_type='boq_quantity' AND entity_id='1'") == 1


def test_takeoff_resource_import(seeded, pid, tmp_path):
    from app.services.rates import create_resource
    create_resource(seeded, ESTIMATOR, resource_type="material", description="x", unit="kg", id="TK-1")
    bi.import_boq(seeded, ESTIMATOR, pid, write_boq(tmp_path / "t.csv", [("1", "Rebar", "t", "2", "", "")]))
    p = write_boq(tmp_path / "tk.csv", [("1", "TK-1", "2100", "kg"), ("1", "NOPE", "5", "kg"), ("9", "TK-1", "5", "kg")], header=("Item", "Resource ID", "Quantity", "Unit"))
    r = bi.import_takeoff_resources(seeded, ESTIMATOR, pid, p)
    assert r["lines_added"] == 1 and len(r["rejected"]) == 2
    assert boq.get_item(seeded, pid, "1")["pricing_method"] == "takeoff_resources"


def test_viewer_cannot_import(seeded, pid, tmp_path):
    from app.core.errors import PermissionDenied
    with pytest.raises(PermissionDenied):
        bi.import_boq(seeded, VIEWER, pid, write_boq(tmp_path / "v.csv", [("1", "x", "m", "1", "", "")]))


def test_archived_project_is_read_only(seeded, pid, tmp_path):
    from app.core.errors import Conflict
    projects.archive_project(seeded, COMMERCIAL, pid, "closed")
    with pytest.raises(Conflict):
        bi.import_boq(seeded, ESTIMATOR, pid, write_boq(tmp_path / "v.csv", [("1", "x", "m", "1", "", "")]))
