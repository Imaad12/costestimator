"""Regression tests for four defects found by the real-document practice test (all data SYNTHETIC / test fixtures)."""
from __future__ import annotations

import pytest

from app.core.errors import Conflict
from app.imports import boq as bi
from app.reporting import completeness
from app.services import estimates, project_index, projects, readiness, tender, workspaces
from tests.conftest import ESTIMATOR
from tests.helpers import write_boq


def _pdf(path, rows, header):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    c.drawString(40, y, "  ".join(header))
    for r in rows:
        y -= 18
        c.drawString(40, y, "  ".join(r))
    c.save()


# ---- D-1: a text layer that has a Quantity header and units but no numbers is flagged, not reported as plainly "Extracted"
def test_pdf_table_without_numbers_is_extracted_incomplete(seeded, tmp_path):
    pid = projects.create_project(seeded, ESTIMATOR, name="Index test (SYNTHETIC)", is_demo=True, region="KSA-ALL", currency="SAR")
    root = workspaces.resolve_dir(pid, seeded)
    items = [("Excavation", "m3"), ("Blinding", "m3"), ("Formwork", "m2"), ("Doors", "nos"), ("Railing", "m"), ("Steel", "kg")]
    _pdf(root / "1. Tender Documents" / "no_numbers.pdf", [(f"{i + 1}.1", n, u, "derived from plan") for i, (n, u) in enumerate(items)], ("No.", "Item", "Unit", "Quantity", "Basis"))
    _pdf(root / "1. Tender Documents" / "with_numbers.pdf", [(f"{i + 1}.1", n, u, f"{10 + i}.50") for i, (n, u) in enumerate(items)], ("No.", "Item", "Unit", "Quantity", "Basis"))
    project_index.index_project(seeded, ESTIMATOR, pid)
    st = {d["file_name"]: d for d in project_index.list_documents(seeded, pid)}
    assert st["no_numbers.pdf"]["extraction_status"] == "Extracted - incomplete" and "NOT in the extracted text" in st["no_numbers.pdf"]["extraction_error"]
    assert st["with_numbers.pdf"]["extraction_status"] == "Extracted"
    row = next(r for r in completeness.project_completeness(seeded, pid)["rows"] if r["check"] == "Document index")
    assert row["status"] != "OK" and "INCOMPLETE" in row["detail"]
    assert project_index.search(seeded, pid, "Excavation")           # an incomplete extract is still searchable for what it does contain


# ---- D-3: wording in ANY text column (remarks) and near-duplicate sizes raise draft queries
def test_detectors_read_remarks_and_near_duplicate_sizes(seeded, tmp_path):
    pid = projects.create_project(seeded, ESTIMATOR, name="Detector test (SYNTHETIC)", is_demo=True, region="KSA-ALL", currency="SAR")
    f = write_boq(tmp_path / "b.csv", [("1.1", "Excavation in pits", "m3", "314.04", "Assumption: ground level not printed - assumed at +/-0.00; confirm"),
                                      ("5.2", "Door 800 x 2400 mm", "nos", "4", "count"), ("5.3", "Door 802 x 2400 mm", "nos", "1", "count"),
                                      ("5.4", "Door 900 x 2400 mm", "nos", "7", "count"), ("5.5", "Door 736 x 2400 mm", "nos", "1", "count")],
                  header=("Item", "Description", "Unit", "Qty", "Remarks"))
    bi.import_boq(seeded, ESTIMATOR, pid, f)
    tender.generate_draft_queries(seeded, "system:detector", pid)
    qs = {q["detector_key"]: q for q in tender.list_queries(seeded, pid) if q["detector_key"]}
    assert "AMBIG:1.1" in qs and "assumed" in qs["AMBIG:1.1"]["question"] and "Remarks" in qs["AMBIG:1.1"]["question"]
    assert "NEARDUP:5.2:5.3" in qs and qs["NEARDUP:5.2:5.3"]["register"] == "boq_discrepancy"
    assert not any(k.startswith("NEARDUP") and ("5.4" in k or "5.5" in k) for k in qs)      # 900 and 736 are not within 1 % of 800
    assert all(q["status"] == "Draft" for q in qs.values())


# ---- D-7: region/currency defaults are flagged until a person confirms them
def test_default_region_currency_is_flagged_and_confirmable(seeded):
    pid = projects.create_project(seeded, ESTIMATOR, name="Basis default (SYNTHETIC)", is_demo=True)
    p = projects.get_project(seeded, pid)
    assert (p["region"], p["currency"], p["basis_defaulted"]) == ("KSA-ALL", "SAR", 1)
    row = next(r for r in completeness.project_completeness(seeded, pid)["rows"] if r["check"] == "Region and currency confirmed by a person")
    assert row["status"] == "Open" and "system defaults" in row["detail"]
    from app.services import boe
    b = boe.build_boe(seeded, pid)
    assert any("SYSTEM DEFAULTS" in x for x in b["banner"]) and b["project"]["basis_confirmed"] is False
    projects.confirm_basis(seeded, ESTIMATOR, pid, "KSA-ALL", "SAR")
    assert projects.get_project(seeded, pid)["basis_defaulted"] == 0
    assert not any("SYSTEM DEFAULTS" in x for x in boe.build_boe(seeded, pid)["banner"])
    explicit = projects.create_project(seeded, ESTIMATOR, name="Explicit (SYNTHETIC)", is_demo=True, region="KSA-ALL", currency="SAR")
    assert projects.get_project(seeded, explicit)["basis_defaulted"] == 0


def test_basis_cannot_change_after_a_frozen_version(seeded):
    pid = projects.create_project(seeded, ESTIMATOR, name="Basis lock (SYNTHETIC)", is_demo=True)
    estimates.freeze_version(seeded, ESTIMATOR, pid, "v1")
    with pytest.raises(Conflict) as e:
        projects.confirm_basis(seeded, ESTIMATOR, pid, "KSA-ALL", "USD")
    assert e.value.code == "BASIS_LOCKED"
    projects.confirm_basis(seeded, ESTIMATOR, pid, "KSA-ALL", "SAR")          # confirming the same values is allowed


def test_readiness_lists_the_defaulted_basis(seeded):
    pid = projects.create_project(seeded, ESTIMATOR, name="Basis readiness (SYNTHETIC)", is_demo=True)
    vid = estimates.freeze_version(seeded, ESTIMATOR, pid, "v1")
    assert any("system defaults" in r for r in readiness.evaluate(seeded, pid, vid, None)["reasons"])
    projects.confirm_basis(seeded, ESTIMATOR, pid, "KSA-ALL", "SAR")
    assert not any("system defaults" in r for r in readiness.evaluate(seeded, pid, vid, None)["reasons"])


# ---- D-4: the missing-rate report lists unmapped/unpriced lines and does not call open exceptions "resolved"
def test_d36_lists_unpriced_unmapped_lines(seeded, tmp_path):
    from app.tender import builders, packs
    pid = projects.create_project(seeded, ESTIMATOR, name="D36 test (SYNTHETIC)", is_demo=True, region="KSA-ALL", currency="SAR")
    f = write_boq(tmp_path / "b.csv", [("1", "Pipe", "m", "10", "x"), ("2", "Pump", "nos", "2", "x")], header=("Item", "Description", "Unit", "Qty", "Remarks"))
    bi.import_boq(seeded, ESTIMATOR, pid, f)
    vid = estimates.freeze_version(seeded, ESTIMATOR, pid, "v1")
    c = builders.Ctx(seeded, pid, vid, issue_date="2026-10-14", revision=1)
    doc = builders.d36(c)
    heads = [s.heading for s in doc.sections]
    assert "Unpriced or incomplete BOQ lines" in heads and not any("Resolved exceptions" in h for h in heads)
    t = next(s.table for s in doc.sections if s.heading == "Unpriced or incomplete BOQ lines")
    assert [r[0] for r in t.rows] == ["1", "2"] and all(r[3] == "Unmapped" for r in t.rows)
    summary = next(s for s in doc.sections if s.heading == "Summary")
    assert "2 of 2 BOQ line(s) are unpriced" in summary.paras[0]
    need = next(s for s in doc.sections if s.heading == "Procurement needs")
    assert any("MAPPED lines only" in x for x in need.paras)


# ---- D-2: the application does not read PDFs (by design); a transcription is imported with provenance and flagged until a second person checks it
def test_pdf_is_not_read_and_transcription_needs_provenance_and_a_second_checker(seeded, tmp_path):
    from app.core.errors import ValidationFailed
    from tests.conftest import COMMERCIAL
    pid = projects.create_project(seeded, ESTIMATOR, name="Transcription (SYNTHETIC)", is_demo=True, region="KSA-ALL", currency="SAR")
    pdf = tmp_path / "boq.pdf"
    _pdf(pdf, [("1", "Pipe", "m", "10")], ("No.", "Item", "Unit", "Quantity"))
    with pytest.raises(ValidationFailed) as e:
        bi.import_boq(seeded, ESTIMATOR, pid, pdf)
    assert e.value.code == "UNSUPPORTED_FILE"
    f = write_boq(tmp_path / "t.csv", [("1", "Pipe", "m", "10")])
    with pytest.raises(ValidationFailed) as e:
        bi.import_boq(seeded, ESTIMATOR, pid, f, derived_from={"source_file": "boq.pdf"})
    assert e.value.code == "DERIVED_FROM_INCOMPLETE"
    imp = bi.import_boq(seeded, ESTIMATOR, pid, f, derived_from={"source_file": "boq.pdf", "source_sha256": "ab" * 32, "method": "read by eye from the rendered pages"})
    assert imp["unverified_transcription"] is True and imp["derived_from"]["source_file"] == "boq.pdf"
    row = next(r for r in completeness.project_completeness(seeded, pid)["rows"] if r["check"].startswith("Transcribed BOQ import"))
    assert row["status"] == "Open" and "UNVERIFIED" in row["detail"]
    with pytest.raises(ValidationFailed) as e:
        bi.record_transcription_check(seeded, ESTIMATOR, imp["import_id"], "compared all lines")
    assert e.value.code == "SELF_CHECK_BLOCKED"
    with pytest.raises(ValidationFailed):
        bi.record_transcription_check(seeded, COMMERCIAL, imp["import_id"], " ")
    bi.record_transcription_check(seeded, COMMERCIAL, imp["import_id"], "compared 1 of 1 lines with page 3")
    row = next(r for r in completeness.project_completeness(seeded, pid)["rows"] if r["check"].startswith("Transcribed BOQ import"))
    assert row["status"] == "OK"


# ---- D-5: "Lines priced" is not OK while lines are unpriced; no hard-coded "uses SYNTHETIC rates" claim
def test_rates_row_is_blocked_when_lines_are_unpriced(seeded, tmp_path):
    pid = projects.create_project(seeded, ESTIMATOR, name="Rates row (SYNTHETIC)", is_demo=True, region="KSA-ALL", currency="SAR")
    bi.import_boq(seeded, ESTIMATOR, pid, write_boq(tmp_path / "b.csv", [("1", "Pipe", "m", "10"), ("2", "Pump", "nos", "2")]))
    rows = completeness.project_completeness(seeded, pid)["rows"]
    r = next(x for x in rows if x["check"] == "Lines priced from eligible rates")
    assert r["status"] == "Blocked" and "0/2 items fully priced" in r["detail"] and "2 of them unmapped" in r["detail"] and "not computable for 2 unmapped" in r["detail"]
    g = next(x for x in rows if x["check"] == "Approved real (non-synthetic) rates")
    assert "uses SYNTHETIC rates" not in g["detail"]


# ---- D-6: a demonstration project on non-synthetic data is not labelled synthetic; synthetic content still is
def test_demo_is_not_conflated_with_synthetic(seeded, tmp_path):
    from app.estimators.estimate import compute_estimate
    from app.services import boe
    from app.tender import builders
    pid = projects.create_project(seeded, ESTIMATOR, name="Demo not synthetic", is_demo=True, region="KSA-ALL", currency="SAR")
    bi.import_boq(seeded, ESTIMATOR, pid, write_boq(tmp_path / "b.csv", [("1", "Pipe", "m", "10")]))
    vid = estimates.freeze_version(seeded, ESTIMATOR, pid, "v1")
    c = builders.Ctx(seeded, pid, vid, issue_date="2026-10-14", revision=1)
    assert c.demo and not c.synthetic
    assert any("DEMONSTRATION / PRACTICE" in x for x in builders._lim(c)) and not any("SYNTHETIC / DEMONSTRATION data" in x for x in builders._lim(c))
    banner = boe.build_boe(seeded, pid)["banner"]
    assert any("DEMONSTRATION PROJECT - NOT A MARKET QUOTE" == x for x in banner) and not any("SYNTHETIC DATA" in x for x in banner)
    tender.create_enquiry(seeded, ESTIMATOR, customer_name="FICTIONAL CO", title="t", received_date="2026-10-01", customer_is_synthetic=True)
    eid = seeded.scalar("SELECT id FROM tender_enquiries ORDER BY rowid DESC LIMIT 1")
    tender.link_enquiry(seeded, ESTIMATOR, eid, pid)
    assert builders.Ctx(seeded, pid, vid, issue_date="2026-10-14", revision=1).synthetic


# ---- D-8: unknown is not zero
def test_totals_are_none_not_zero_when_nothing_is_priced(seeded, tmp_path):
    from app.estimators.estimate import compute_estimate
    pid = projects.create_project(seeded, ESTIMATOR, name="Totals (SYNTHETIC)", is_demo=True, region="KSA-ALL", currency="SAR")
    bi.import_boq(seeded, ESTIMATOR, pid, write_boq(tmp_path / "b.csv", [("1", "Pipe", "m", "10")]))
    t = compute_estimate(seeded, pid).totals()
    assert t["direct_cost"] is None and t["indirect_cost"] is None and t["total_cost"] is None


def test_readiness_lists_an_unchecked_transcription(seeded, tmp_path):
    from tests.conftest import COMMERCIAL
    pid = projects.create_project(seeded, ESTIMATOR, name="Transcription readiness (SYNTHETIC)", is_demo=True, region="KSA-ALL", currency="SAR")
    imp = bi.import_boq(seeded, ESTIMATOR, pid, write_boq(tmp_path / "t.csv", [("1", "Pipe", "m", "10")]), derived_from={"source_file": "boq.pdf", "source_sha256": "cd" * 32, "method": "by eye"})
    vid = estimates.freeze_version(seeded, ESTIMATOR, pid, "v1")
    assert any("no second person has checked" in r for r in readiness.evaluate(seeded, pid, vid, None)["reasons"])
    bi.record_transcription_check(seeded, COMMERCIAL, imp["import_id"], "compared with the source page")
    assert not any("no second person has checked" in r for r in readiness.evaluate(seeded, pid, vid, None)["reasons"])
