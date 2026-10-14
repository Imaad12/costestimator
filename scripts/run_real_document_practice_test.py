"""REAL-DOCUMENT PRACTICE TEST runner (not a tender, not a submission).

Usage:  python scripts/run_real_document_practice_test.py <fresh scratch dir> [--input practice_test/input] [--out practice_test/real_document]

Drives the REAL application services against a scratch database. The only input document is whatever PDF/XLSX/CSV is in the input folder (currently one third-party sample BOQ PDF).
Every actor is a registered TEST ACTOR except two clearly-labelled `human`-typed users that exist only inside the scratch DB for the negative gate test. Nothing is approved, sent or submitted.
Evidence is written to <out>/results.json; PRACTICE_TEST_RESULTS.md is written by scripts/render_practice_test_report.py from that file plus the findings recorded here.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
import traceback
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import _practice_boq_transcription as T  # noqa: E402

D = Decimal
PID = "PRJ-9201"
NEG = "PRJ-9202"
BANNER = "PRACTICE TEST - NOT A TENDER - NOT FOR SUBMISSION. Third-party sample BOQ; quantities TRANSCRIBED, NOT VERIFIED; no rates, no productivity values."


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


class Ev(dict):
    def stage(self, key, verdict, **facts):
        self[key] = {"verdict": verdict, **facts}


def guarded(ev, key, fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:                       # noqa: BLE001 - recorded as a FAILED STAGE, never hidden
        ev.stage(key, "ERROR", error=f"{type(e).__name__}: {e}", trace=traceback.format_exc()[-1500:])
        return None


def code_of(fn, *a, **k):
    from app.core.errors import AppError
    try:
        fn(*a, **k)
        return "NOT REFUSED"
    except AppError as e:
        return e.code
    except Exception as e:                       # noqa: BLE001
        return f"{type(e).__name__}: {str(e)[:100]}"


# ------------------------------------------------------------------------------------------------ A: inventory
def inventory(inp: Path) -> list[dict]:
    import pypdf
    rows = []
    for p in sorted(inp.iterdir()):
        if not p.is_file() or p.name.startswith("."):
            continue
        r = dict(filename=p.name, format=p.suffix.lower().lstrip("."), bytes=p.stat().st_size, sha256=sha256(p), pages=None, revision_or_date_visible=None, discipline=None, status=None, text_layer=None)
        if r["format"] == "pdf":
            rd = pypdf.PdfReader(str(p))
            r["pages"] = len(rd.pages)
            txt = "\n".join((pg.extract_text() or "") for pg in rd.pages)
            r["text_chars"] = len(txt)
            r["pdf_title"] = (rd.metadata or {}).get("/Title")
            r["pdf_producer"] = (rd.metadata or {}).get("/Producer")
            r["pdf_created"] = (rd.metadata or {}).get("/CreationDate")
            r["revision_or_date_visible"] = "Published 1 October 2026 (p.1); 'Quantities as delivered on 6 September 2026' (p.5); no revision identifier"
            r["discipline"] = "Multi-trade BOQ extract: earthwork, structural RCC/formwork, masonry, openings, railings, roof (civil/structural/architectural only)"
            r["status"] = "Marketing web page printed to PDF - NOT a contract document, NOT an issued-for-tender BOQ; quantity column has no text layer"
            import re
            nos = {x[0] for x in T.R}
            dec = [x for x in T.R if "." in x[3] and x[3] not in nos]
            r["text_layer"] = dict(decimal_quantities_checked=len(dec), found_in_text_layer=sum(1 for x in dec if re.search(r"(?<![\d.,])" + re.escape(x[3]) + r"(?![\d])", txt)),
                                   note="integer counts (doors/windows) cannot be tested this way; item numbers that look like quantities (e.g. 5.21) are excluded")
        rows.append(r)
    return rows


# ------------------------------------------------------------------------------------------------ K: priced run with SYNTHETIC placeholder rates
PLACEHOLDER_NOTE = "SYNTHETIC / DEMO / NOT A MARKET QUOTE - placeholder unit rate = 100 x BOQ section number (SAR per unit) so the pipeline can be verified; it is NOT a price and has no source"


def priced_run(db, ev, A, out, csv_path, derived, scratch):
    """Same real quantities as PRJ-9201, priced with labelled SYNTHETIC placeholder rates so that the estimate can be independently re-computed. Separate project; PRJ-9201 stays rate-free."""
    from decimal import ROUND_HALF_UP
    from app.estimators.estimate import compute_estimate
    from app.imports import boq as bi
    from app.services import assemblies, boq, commercial, estimates, projects, rates
    from app.tender import packs
    PID3 = "PRJ-9203"
    pid = projects.create_project(db, A["est"], name="PRACTICE TEST - priced run (real quantities, SYNTHETIC placeholder rates)", client="NONE - practice exercise", id=PID3, is_demo=True, tax_category="VAT-STD",
                                  region="KSA-ALL", currency="SAR", tender_ref="PRACTICE-TEST-NOT-A-TENDER", notes=BANNER + " " + PLACEHOLDER_NOTE)
    imp = bi.import_boq(db, A["est"], pid, csv_path, derived_from=derived)
    items = db.all("SELECT item_key, description, quantity_original, unit FROM boq_items WHERE project_id=? AND item_type='item' ORDER BY id", (pid,))
    rate_of = {}
    for r in items:
        key = r["item_key"]
        sec = int(key.split(".")[0])
        rid, acode = f"PT-{key}", f"PTA-{key}"
        rates.create_resource(db, A["est"], resource_type="subcontract", description=f"PLACEHOLDER installed baseline: {r['description']}", unit=r["unit"], cost_code="C.01", id=rid, is_synthetic=True)
        assemblies.create_assembly(db, A["est"], code=acode, description=f"PLACEHOLDER installed-rate assembly {key}", unit=r["unit"], cost_code="C.01", is_synthetic=True,
                                   source="SYNTHETIC placeholder assembly - one installed-rate line", lines_=[dict(line_type="subcontract", resource_id=rid, factor="1")])
        assemblies.submit_assembly(db, A["est"], acode)
        assemblies.approve_assembly(db, A["com"], acode, comments="TEST ACTOR: SYNTHETIC placeholder")
        price = Decimal(100 * sec)
        rate_of[key] = price
        rid_rate = rates.propose_rate(db, A["est"], rid, unit_price=str(price), rate_type="Synthetic Demonstration Rate", unit=r["unit"], price_date="2026-10-01", confidence="Low", is_synthetic=True,
                                      evidence=PLACEHOLDER_NOTE, submit=True)
        rates.approve_rate(db, A["proc"], rid_rate, comments="TEST ACTOR: SYNTHETIC placeholder rate (not a real procurement approval)")
        boq.map_to_assembly(db, A["est"], pid, key, acode)
        boq.set_cost_code(db, A["est"], pid, key, "C.01")
    cfg = {"method": "markup", "markup_pct": "10", "margin_pct": "10", "default_tax_category": "VAT-STD", "contingency": {"pct": "5", "base": "direct_indirect"}, "risk_items": [], "rounding": {"dp": 2}}
    pol = commercial.create_policy(db, A["est"], code="POL-PT", name="PLACEHOLDER policy (SYNTHETIC): 10 % markup, 5 % contingency", config=cfg, is_synthetic=True)
    commercial.submit_policy(db, A["est"], pol)
    commercial.approve_policy(db, A["com"], pol)
    commercial.assign_policy(db, A["est"], pid, pol)
    tid = db.scalar("SELECT id FROM tax_categories WHERE code='VAT-STD'")
    commercial.approve_tax_category(db, A["com"], tid, evidence="TEST ACTOR: fixture approval for the practice run (not an official verification)")
    est = compute_estimate(db, pid)
    t = est.totals()
    r2 = lambda x: Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)           # noqa: E731
    # ---- independent re-computation: from the transcription (not from the database), half-up per line
    tr = {x[0]: x for x in T.R}
    rows, direct = [], Decimal(0)
    for key, row in tr.items():
        amt = r2(Decimal(row[3]) * rate_of[key])
        direct += amt
        eng = next((i for i in (est.direct.items.values()) if i.item_key == key), None)
        rows.append(dict(item=key, description=row[1], unit=row[2], quantity=row[3], placeholder_rate=str(rate_of[key]), independent_amount=str(amt), engine_amount=str(eng.direct_cost) if eng else None,
                         match=bool(eng) and r2(eng.direct_cost) == amt))
    cont = r2(direct * Decimal("0.05"))
    total_cost = direct + cont
    with open(out / "priced_run_verification.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    by_sec = {}
    for k, row in tr.items():
        by_sec[k.split(".")[0]] = by_sec.get(k.split(".")[0], Decimal(0)) + r2(Decimal(row[3]) * rate_of[k])
    ident = {}
    if t.get("selling_price_pre_tax") is not None and t.get("tax") is not None and t.get("final_payable") is not None:
        ident["schedule_total_plus_tax_equals_payable"] = Decimal(str(t["selling_price_pre_tax"])) + Decimal(str(t["tax"])) == Decimal(str(t["final_payable"]))
    vid = estimates.freeze_version(db, A["est"], pid, "practice-priced-v1", "PRACTICE TEST: priced with SYNTHETIC placeholder rates")
    pack = packs.generate_pack(db, A["est"], pid, out_root=out / "priced_run", issue_date="2026-10-14", version_id=vid)
    d05 = next(d for d in pack["documents"] if d["code"] == "D05")
    ok = Decimal(str(t["direct_cost"])) == direct and all(x["match"] for x in rows)
    ev.stage("K1_priced_run_synthetic_placeholder_rates", "PASS" if ok else "FAIL", project=pid, placeholder_rule=PLACEHOLDER_NOTE, import_flag=dict(unverified_transcription=imp.get("unverified_transcription"), derived_from=imp.get("derived_from")),
             lines=len(rows), lines_matching_independent_amount=sum(1 for x in rows if x["match"]), engine=dict((k, (str(v) if v is not None else None)) for k, v in t.items()), state=est.state, blockers=[str(b)[:120] for b in est.blockers][:8],
             independent=dict(direct_cost=str(direct), contingency_5pct=str(cont), total_cost_before_markup=str(total_cost), direct_by_section={k: str(v) for k, v in sorted(by_sec.items())}),
             direct_cost_agrees=Decimal(str(t["direct_cost"])) == direct, identities=ident, pack_dir=pack["out_dir"], pack_classification=pack["classification"], pack_production_ready=pack["production_ready"],
             d05_status=d05["status"], verification_file="priced_run_verification.csv",
             note="These amounts are arithmetic on placeholder rates. They are NOT an estimate of what the building costs and must never be quoted. Swap in approved, sourced rates through the normal rate workflow to get a real estimate.")


# ------------------------------------------------------------------------------------------------ main run
def run(scratch: Path, inp: Path, out: Path) -> Ev:
    from tests.closure import scenario as S                    # bootstrap/actors only; none of the synthetic data is used
    from app.core.errors import AppError
    from app.database import Database
    ev = Ev()
    out.mkdir(parents=True, exist_ok=True)
    inv = inventory(inp)
    pdfs = [r for r in inv if r["format"] == "pdf"]
    ev.stage("A0_inventory", "PASS" if inv else "FAIL", files=inv, folders_expected=["drawings", "BOQ", "specifications", "tender documents"],
             note="The input folder contains ONLY the files listed here. No drawing, specification, contract, addendum, spreadsheet or BOQ file exists in it.")
    pre_sha = {r["filename"]: r["sha256"] for r in inv}
    db, settings = S.bootstrap(scratch)
    A = S.actors()
    from app.imports import boq as bi
    from app.services import (assumptions, audit, estimates, projects, project_index, tender, workspaces)
    from app.estimators.estimate import compute_estimate
    # ---- project + workspace + original file preserved + index
    pid = projects.create_project(db, A["est"], name="PRACTICE TEST - Sample residential building (third-party sample BOQ)", client="NONE - practice exercise", location="not stated in the document (document uses INR and IS 1200: India)",
                                  project_type="residential building (G+1 house)", design_stage="PRACTICE TEST", is_demo=True, tax_category="VAT-STD", id=PID, tender_ref="PRACTICE-TEST-NOT-A-TENDER",
                                  trades=["civil", "structural", "architectural"], notes=BANNER)
    root = workspaces.resolve_dir(pid, db)
    dest_dir = root / "1. Tender Documents"
    copied = []
    for r in inv:
        d = dest_dir / r["filename"]
        shutil.copy2(inp / r["filename"], d)
        copied.append(dict(file=r["filename"], sha256_original=r["sha256"], sha256_copy=sha256(d), identical=sha256(d) == r["sha256"]))
    idx = project_index.index_project(db, A["est"], pid)
    docs = project_index.list_documents(db, pid)
    pdoc = next((d for d in docs if d["rel_path"].endswith(".pdf")), None)
    ex_txt = ""
    if pdoc:
        for p in (root / "2. AI Context" / "extracts").glob("*"):
            ex_txt += p.read_text(encoding="utf-8", errors="ignore")
    import re as _re
    _nos = {x[0] for x in T.R}
    _dec = [x for x in T.R if "." in x[3] and x[3] not in _nos]
    q_in_extract = sum(1 for x in _dec if _re.search(r"(?<![\d.,])" + _re.escape(x[3]) + r"(?![\d])", ex_txt))
    ev.stage("A1_workspace_index", "PASS" if all(c["identical"] for c in copied) and pdoc else "FAIL", workspace=str(root), originals_copied=copied, index_stats=idx,
             indexed=[dict(rel_path=d["rel_path"], category=d.get("category"), extraction_status=d.get("extraction_status"), text_chars=d.get("text_chars"), review_status=d.get("review_status"), sha256=d.get("sha256")) for d in docs],
             decimal_quantities_present_in_application_text_extract=q_in_extract, decimal_quantities_checked=len(_dec), extract_chars=len(ex_txt),
             finding="The indexer extracted the PDF text layer; the quantity column is not in it. The application's own text index therefore cannot see any quantity. They exist only in the rendered page images.")
    # ---- document register (registered, not interpreted); referenced-but-absent documents are registered as Missing
    tender.register_document(db, A["est"], pid, doc_ref="BOQ-SAMPLE-SITESETU", doc_type="boq", title=T.SOURCE, revision="published 2026-10-01; quantities delivered 2026-09-06", source="uploaded file (practice-test input folder)",
                             received_date="2026-10-14", applicability="BOQ quantities only (structure, walls, openings); rates blank; not a tender document")
    MISSING = [("DWG-ARCH-SET", "drawing", "architectural", "Architect's drawing set - 'a 16-sheet drawing set' (p.1): ground-floor plan, first-floor plan, roof plan, sections, elevations (referenced pp.1-3, 5; NOT provided)"),
               ("DWG-STR-FOOTING", "drawing", "structural", "Structural footing layout (basis of item 2.1; NOT provided)"), ("DWG-STR-COLUMN", "drawing", "structural", "Structural column keys and column details (items 2.2-2.4; NOT provided)"),
               ("DWG-STR-SLABBEAM", "drawing", "structural", "Structural slab/beam sheets and beam details (items 2.5-2.9; NOT provided)"), ("DWG-STR-STAIR", "drawing", "structural", "Structural stair sheet - the source says it was 'quarantined' (item 2.10; NOT provided)"),
               ("DWG-SITE-LEVELS", "survey", "civil", "Site survey / natural ground level (item 1.1 assumption; NOT provided)"), ("SPEC-STRUCT", "specification", "structural", "Structural / concrete / masonry specification (grades, cover, mix; NOT provided)"),
               ("SPEC-ARCH", "specification", "architectural", "Architectural specification: plaster, door and window schedules, railings (NOT provided)"),
               ("DWG-MECH", "drawing", "mechanical", "Mechanical / HVAC drawings (NOT provided; not in scope of the source BOQ)"), ("DWG-PLUMB", "drawing", "plumbing", "Plumbing and drainage drawings (NOT provided; not in scope of the source BOQ)"),
               ("DWG-ELEC", "drawing", "electrical", "Electrical drawings (NOT provided; not in scope of the source BOQ)"), ("DWG-FIRE", "drawing", "fire", "Fire protection drawings (NOT provided; not in scope of the source BOQ)"),
               ("BBS-REINF", "other", "structural", "Reinforcement bar bending schedule - the source says it is excluded (p.7; NOT provided)"), ("ITT-CONTRACT", "contract", "commercial", "Invitation to tender, conditions of contract, BOQ preamble / method of measurement (NOT provided)")]
    for ref, typ, disc, title in MISSING:
        tender.register_document(db, A["est"], pid, doc_ref=ref, doc_type=typ, title=title, revision="n/a", source="referenced in BOQ-SAMPLE-SITESETU but not supplied", status="Missing", discipline=disc)
    rep = tender.documents_report(db, pid)
    ev.stage("B1_document_register", "PASS", current=[(d["doc_ref"], d["revision"], d["content_status"]) for d in rep["current"]], missing=[(d["doc_ref"], d["title"][:70]) for d in rep["missing"]], superseded=[d["doc_ref"] for d in rep["superseded"]],
             revision_conflicts=rep["revision_conflicts"], not_interpreted=rep["not_interpreted"])
    # ---- C: BOQ import through the application workflow (the importer reads CSV/XLSX only: a PDF cannot be imported -> transcription is a documented manual pre-step)
    derived = out / "derived"
    derived.mkdir(exist_ok=True)
    csv_path = derived / "BOQ_TRANSCRIBED_FROM_PDF_UNVERIFIED.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Item No", "Description", "Section", "Unit", "Quantity", "Drawing Ref", "Remarks"])
        last = None
        for no, desc, unit, qty, basis, page, note in T.R:
            sec = no.split(".")[0]
            if sec != last:
                w.writerow([sec, T.SECTIONS[sec][0], T.SECTIONS[sec][1], "", "", "", ""])
                last = sec
            w.writerow([no, desc, T.SECTIONS[sec][1], unit, qty, basis, f"source PDF p.{page}; TRANSCRIBED FROM RENDERED PAGE - NOT VERIFIED" + (f"; {note}" if note else "")])
    DERIVED = dict(source_file=inv[0]["filename"] if inv else "", source_sha256=inv[0]["sha256"] if inv else "", method="read by eye from the rendered PDF pages (pdftoppm 80 dpi, pp.3-5) by one reader; text layer has no quantity column",
                   note="TRANSCRIBED - NOT VERIFIED by a second person")
    imp = guarded(ev, "C1_boq_import", bi.import_boq, db, A["est"], pid, csv_path, derived_from=DERIVED)
    rows = db.all("SELECT * FROM boq_items WHERE project_id=? ORDER BY id", (pid,))
    items = [r for r in rows if r["item_type"] == "item"]
    heads = [r for r in rows if r["item_type"] == "heading"]
    tr = {x[0]: x for x in T.R}
    qty_ok = [r["item_key"] for r in items if D(r["quantity_original"]) == D(tr[r["item_key"]][3])]
    desc_ok = [r["item_key"] for r in items if r["description"] == tr[r["item_key"]][1]]
    conv = [dict(item=r["item_key"], unit_original=r["unit_original"], unit_canonical=r["unit"], unit_status=r["unit_status"]) for r in items]
    conv_summary = {}
    for c in conv:
        conv_summary.setdefault((c["unit_original"], c["unit_canonical"], c["unit_status"]), 0)
        conv_summary[(c["unit_original"], c["unit_canonical"], c["unit_status"])] += 1
    issues = [(r["item_key"], r["validation_status"], r["issues_json"]) for r in items if r["validation_status"] != "OK"]
    rej = db.all("SELECT * FROM boq_rejected_rows WHERE project_id=?", (pid,)) if db.one("SELECT name FROM sqlite_master WHERE name='boq_rejected_rows'") else []
    ev.stage("C1_boq_import", "PASS" if imp and len(items) == 48 and len(qty_ok) == 48 and len(desc_ok) == 48 else "FAIL", import_result={k: v for k, v in (imp or {}).items() if not isinstance(v, (list, dict))}, items=len(items), headings=len(heads),
             rejected_rows=len(rej), quantities_identical_to_transcription=len(qty_ok), descriptions_identical=len(desc_ok), unit_conversions={f"{a} -> {b} [{c}]": n for (a, b, c), n in conv_summary.items()},
             items_needing_review=issues[:60], source_file_sha256=sha256(csv_path),
             limitation="The importer accepts only CSV/XLSX. The PDF was NOT imported by the application: its quantities were transcribed by hand into the CSV above (labelled unverified).")
    # ---- D: quantity verification and traceability
    from decimal import Decimal as Dc
    q = {r["item_key"]: D(r["quantity_original"]) for r in items}
    glance = []
    for name, (stated, keys) in T.GLANCE.items():
        calc = sum(q[k] for k in keys)
        glance.append(dict(group=name, printed_total=stated, sum_of_lines=str(calc), difference=str(calc - D(stated)), agrees=calc == D(stated)))
    backfill = dict(excavation=str(q["1.1"]), footings=str(q["2.1"]), blinding=str(q["1.2"]), printed_backfill=str(q["1.3"]), calculated_per_printed_basis=str(q["1.1"] - q["2.1"] - q["1.2"]), difference=str(q["1.3"] - (q["1.1"] - q["2.1"] - q["1.2"])))
    trace = [dict(item=k, pdf_page=tr[k][5], measurement_basis_printed=tr[k][4], source_drawing_in_input_folder=False) for k in tr]
    with open(out / "drawing_to_boq_traceability.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(trace[0]))
        w.writeheader()
        w.writerows(trace)
    ev.stage("D1_quantity_verification", "PASS (findings raised)", totals_cross_check=glance, backfill_arithmetic=backfill,
             traceability=dict(items=48, traceable_to_pdf_page_and_printed_basis=48, traceable_to_a_drawing_supplied_in_the_input_folder=0, verified_against_drawing=0),
             conclusion="No quantity can be verified: the drawings and the 3D model the quantities came from were not supplied. The cross-checks show the page-2 totals differ by 0.01 in three groups and item 1.3 differs from its own printed formula by 0.27.")
    # takeoff-required tasks (open actions). Nothing is measured here.
    TK = [("Obtain and register the 16-sheet architectural + structural drawing set; then a person verifies every BOQ quantity against it (0 of 48 lines are verifiable today)", "BOQ items 1.1-7.1", "all drawings (not provided)"),
          ("MANUAL TAKEOFF REQUIRED: reinforcement steel (kg) and bar bending schedule - excluded from the source BOQ", "new BOQ lines needed - structural", "structural drawings: footing layout, column keys, slab/beam sheets (not provided); all floors"),
          ("MANUAL TAKEOFF REQUIRED: plaster net area after deducting openings per the method of measurement the customer names", "item 4.4 (gross 1,345.20 m2)", "architectural plans/elevations, all floors (not provided); door/window schedule items 5.1-5.25"),
          ("MANUAL TAKEOFF REQUIRED: flooring, wall/ceiling finishes, waterproofing, painting, joinery", "not in BOQ", "architectural finishes schedule and plans, ground/first/roof (not provided)"),
          ("MANUAL TAKEOFF REQUIRED: plumbing, drainage, electrical, HVAC, fire and ELV quantities", "not in BOQ", "MEP drawings (not provided; none exist in the input folder)"),
          ("MANUAL TAKEOFF REQUIRED: external works, boundary wall, gate, site drainage, utilities connections", "not in BOQ", "site plan (not provided)"),
          ("MANUAL TAKEOFF REQUIRED: structural stair - source says the structural stair sheet was quarantined; stair concrete (4.13 m3) was taken from architectural plans", "item 2.10", "architectural plans/section; structural stair sheet (not provided)"),
          ("Confirm natural ground level; re-measure excavation 1.1, blinding 1.2, backfill 1.3 together if it changes", "items 1.1-1.3", "site survey / levels (not provided); footing layout"),
          ("MANUAL TAKEOFF REQUIRED: roof and canopy member sections/material/weights (only a run length is given)", "item 7.1 (48.85 m)", "roof plan, elevations, structural roof sheet (not provided)"),
          ("MANUAL TAKEOFF REQUIRED: railing type/height/material and fixings (only a run length is given)", "item 6.1 (43.68 m)", "architectural plans/elevations (not provided)")]
    acts = [tender.add_action(db, A["est"], pid, d, owner="UNASSIGNED (estimator to assign)", source_ref=f"{ref} | drawing/location: {loc}") for d, ref, loc in TK]
    # ---- E: queries (draft only) - detectors + evidence-based manual drafts
    before = len(tender.list_queries(db, pid))
    det = tender.generate_draft_queries(db, "system:detector", pid)
    mq = [
        ("boq_discrepancy", "Item 1.3 'Backfill around footings' (240.58 m3) is printed as 'excavation - footing - blinding'. 314.04 - 55.40 - 18.33 = 240.31 m3, a difference of 0.27 m3. Which quantity is correct and which volumes (e.g. foundation columns 1.90 m3) were deducted?", "Printed quantity does not follow its own printed formula.", "civil", ["1.1", "1.2", "1.3", "2.1"]),
        ("boq_discrepancy", "Page-2 totals differ from the sum of the item lines: RCC 129.42 vs 129.43, formwork 1,746.67 vs 1,746.68, masonry 111.38 vs 111.39. Please confirm the line quantities are the contractual figures (rounding vs error).", "Summary does not reconcile to its lines by 0.01.", "structural", ["2.1", "3.1", "4.1"]),
        ("missing_input", "Natural ground level is 'not printed - assumed at project +/-0.00'. Please supply the site survey / levels. Items 1.1, 1.2, 1.3 change together if it moves.", "Stated assumption in the source that the drawings did not settle.", "civil", ["1.1", "1.2", "1.3"]),
        ("missing_input", "The BOQ was measured from a '16-sheet drawing set' (and a 3D model of 434 elements). None of the sheets or the model were supplied. Please issue the complete set with revision identifiers so every quantity can be traced.", "0 of 48 lines can be traced to a supplied drawing.", "architectural", ["1.1-7.1"]),
        ("technical", "Item 2.10 RC stairs (4.13 m3): the structural stair sheet is stated as 'quarantined' and the quantity was taken from architectural plans and section. Please issue the structural stair design (reinforcement, thickness, landing support).", "Quantity based on non-structural drawings.", "structural", ["2.10"]),
        ("scope_exclusion", "Reinforcement steel and its bar bending schedule are excluded from the BOQ. Is steel to be priced by the contractor from the drawings, and which weight basis (BBS or % of concrete volume) governs?", "No reinforcement quantity exists for 129.42 m3 of RCC.", "structural", ["2.1-2.10"]),
        ("scope_exclusion", "Plaster (item 4.4) is measured gross, openings not deducted. Which method of measurement applies to the tender (the document cites IS 1200), and are deductions to be made by the contractor?", "Gross quantity overstates plaster area; basis of measurement unclear.", "architectural", ["4.4"]),
        ("scope_exclusion", "Flooring, finishes, plumbing, electrical and other services are not in the BOQ ('those come with a full BOQ'). Please confirm whether they are in scope of this tender and issue their drawings and quantities.", "Large parts of a G+1 house are unmeasured; MEP interfaces (sleeves, chases) cannot be assessed.", "mep", ["not in BOQ"]),
        ("technical", "Openings with unusual sizes: Door 6467x3140, Window 387x3140, Window 368x3140, Window 600x2950, Window 4274x2000. Please confirm these are real openings (e.g. shopfront, curtain wall, slot) and give their type, material and glazing.", "Sizes look like modelling artefacts or special openings; pricing per size needs a specification.", "architectural", ["5.4", "5.12", "5.13", "5.15", "5.21"]),
        ("boq_discrepancy", "Door 900x2400 (7 nos), 800x2400 (4), 802x2400 (1), 736x2400 (1): 802 and 736 look like duplicates/variants of 800. Please confirm the schedule sizes.", "Near-duplicate sizes split the count and the priced size.", "architectural", ["5.2", "5.3", "5.6"]),
        ("missing_input", "No specification is supplied: concrete grade, cover and mix, masonry unit type and mortar, plaster thickness/mix, door and window materials, railing material. Items carry no grade or material.", "Cannot select an assembly or rate without a specification.", "structural", ["2.1-2.10", "4.1-4.4", "5.1-5.25", "6.1"]),
        ("technical", "The source uses IS 1200 and INR. Which measurement standard, currency, region, tax and contractual basis apply to this enquiry? The suite's defaults are Saudi (VAT, KSA calendar); none is assumed.", "Region/standard mismatch with the estimating basis.", "commercial", ["all"]),
        ("design_interface", "Item 7.1 'Roof and canopy members' (48.85 m) gives only a running length. Material (steel/RCC/timber), section, finish and relation to roof beams (2.6) and slab (2.9) are not stated.", "Unit and description insufficient to price or sequence.", "structural", ["7.1", "2.6", "2.9"]),
        ("boq_discrepancy", "The document says quantities were delivered 6 September 2026 and the page was published 1 October 2026; no revision identifier exists. Which issue is current?", "Revision cannot be established.", "all", ["all"]),
        ("commercial", "Rates, amounts and the abstract of cost are blank by design. Which rate basis (DSR, SOR, market) and currency is to be used, and what are the payment, retention and bond terms?", "No commercial terms exist in the supplied documents.", "commercial", ["all"])]
    qids = []
    for reg, qq, why, disc, rel in mq:
        qids.append(tender.add_query(db, A["est"], pid, register=reg, question=qq, why=why, discipline=disc, responsible_party="Customer / design team", related=dict(boq_items=rel, source="BOQ-SAMPLE-SITESETU"), generated_by="user (practice-test operator)"))
    allq = tender.list_queries(db, pid)
    tender.skeleton_registers(db, A["est"], pid)
    ev.stage("E1_queries", "PASS" if allq and all(x["status"] == "Draft" for x in allq) else "FAIL", detectors_created=det.get("created") if isinstance(det, dict) else det, manual_drafts=len(qids), total=len(allq), statuses={s: sum(1 for x in allq if x["status"] == s) for s in {x["status"] for x in allq}},
             by_register={r: sum(1 for x in allq if x["register"] == r) for r in {x["register"] for x in allq}}, takeoff_required_tasks=acts, queries_not_issued=True,
             query_ids=[(x["id"], x["register"], x["generated_by"]) for x in allq])
    # ---- F: assumptions register (nothing approved)
    AS = [("ASMP-PT-001", "B", "Quantities used exactly as printed in the source PDF (transcribed; not re-measured)", "import", "Quantities and measurement", "Imported from a hand transcription of rendered pages; no drawing verification possible", "Low", "Every priced quantity would be unverified"),
          ("ASMP-PT-002", "G", "Natural ground level assumed at project +/-0.00 (assumption printed in the source for item 1.1)", "import", "Scope and design", "Source states the drawings did not settle it: 'confirm'", "Low", "Excavation/backfill quantities may change"),
          ("ASMP-PT-003", "A", "Scope limited to what the BOQ lists (structure, walls, openings, railings, roof); finishes, MEP, external works, reinforcement not included", "manual", "Exclusions, interfaces and responsibilities", "Operator assumption; page 7 'What this sample leaves out'", "Medium", "Estimate would understate scope"),
          ("ASMP-PT-004", "B", "Derived totals: sum of RCC lines 129.43 m3, formwork 1,746.68 m2, masonry 111.39 m3 (system arithmetic, not measurements)", "calculated", "Quantities and measurement", "Deterministic sums of the transcribed lines", "Medium", "n/a - arithmetic"),
          ("ASMP-PT-005", "I", "Region, currency and measurement standard of the project are NOT established (document is INR / IS 1200)", "manual", "Commercial terms and payment", "Operator note: no KSA basis can be claimed for this document", "Low", "Rates, tax, calendar cannot be selected")]
    for aid, fam, name, org, cat, why, conf, cons in AS:
        assumptions.create_assumption(db, A["est"], id=aid, family=fam, name=name, description=name, value_type="text", default_value=name, origin=org, category=cat, reason=why, confidence=conf, consequence_if_missing=cons,
                                      source="BOQ-SAMPLE-SITESETU (practice-test input)", evidence="see source PDF page references in drawing_to_boq_traceability.csv")
    ai_try = code_of(assumptions.create_assumption, db, A["est"], id="ASMP-PT-AI", family="A", name="AI proposal attempt", origin="ai", value_type="text")
    ai_actor = code_of(assumptions.create_assumption, db, __import__("app.models.actor", fromlist=["Actor"]).Actor("ai-assistant", "AI Assistant", "AI"), id="ASMP-PT-AI2", family="A", name="AI actor attempt", value_type="text")
    assumptions.adopt_mandatory(db, A["est"], pid)
    er = assumptions.evidence_report(db, pid)
    reg_rows = [dict(id=a[0], origin=a[3], classification=assumptions.data_class(assumptions.get_latest(db, a[0])), status=assumptions.get_latest(db, a[0])["status"]) for a in AS]
    syn = db.scalar("SELECT COUNT(*) FROM assumptions WHERE is_synthetic=1 AND id LIKE 'ASMP-PT-%'") or 0
    ev.stage("F1_assumptions_register", "PASS" if not er["fully_verified"] and ai_try != "NOT REFUSED" and ai_actor != "NOT REFUSED" else "FAIL", practice_test_rows=reg_rows, ai_proposals_in_register=0, ai_row_attempt=ai_try, ai_actor_attempt=ai_actor,
             synthetic_rows=syn, project_evidence_by_class=er["by_class"], mandatory_or_adopted_total=len(er["rows"]), problems_sample=er["problems"][:12], fully_verified=er["fully_verified"],
             source_backed_facts="none can be classed 'Verified source data': that class needs approval by a person; nothing was approved")
    # ---- G: estimate + programme to the extent supported
    est = compute_estimate(db, pid)
    unpriced = [l for l in est.lines if getattr(l, "amount", None) is None] if hasattr(est, "lines") else []
    ev.stage("G1_estimate", "PASS (INCOMPLETE as expected)" if est.state != "Complete" else "FAIL", state=est.state, totals={k: str(v) for k, v in est.totals().items()}, priced_lines=sum(1 for r in items if r["pricing_amount"]),
             boq_items=len(items), mapped=sum(1 for r in items if r["mapping_status"] != "Unmapped"), unpriced_lines=len(items), blockers=[str(b)[:140] for b in (getattr(est, "blockers", []) or [])][:20],
             completeness=getattr(est, "completeness", None) if not callable(getattr(est, "completeness", None)) else None,
             note="No assembly mapping and no approved rate exist. Per rule 4, no mapping was made or approved by the test; per rule 3, no price was invented. The estimate total is therefore not a number.")
    from app.reporting import registry
    from app.api.serializers import ser
    prog = {}
    for name in ("productivity_programme", "schedule", "long_lead", "cashflow", "plant_hire"):
        try:
            prog[name] = ser(registry.run_report(db, name, pid, {}))
        except AppError as e:
            prog[name] = dict(refused=e.code, message=str(e)[:200])
    from app.services import workforce as wf
    try:
        wf.build_programme(db, pid, "NO-PROFILE")
        pcode = "NOT REFUSED"
    except AppError as e:
        pcode = e.code
    missing = dict(rates="all 48 lines (no rate exists in the library; 'the library ships empty')", productivity_norms=db.scalar("SELECT COUNT(*) FROM productivity_norms") or 0, workforce_profiles=db.scalar("SELECT COUNT(*) FROM workforce_profiles") or 0,
                   work_activities=db.scalar("SELECT COUNT(*) FROM work_activities WHERE project_id=?", (pid,)) or 0, calendar="none approved", lead_times="none recorded", cost_allocations="none")
    ev.stage("G2_programme_to_extent_supported", "PASS (refused/empty as expected)" if pcode != "NOT REFUSED" else "FAIL", build_programme_code=pcode, reports={k: (v if "refused" in v else {kk: (vv if not isinstance(vv, (list, dict)) else f"<{type(vv).__name__} {len(vv)}>") for kk, vv in list(v.items())[:8]}) for k, v in prog.items()},
             missing_inputs=missing, note="No programme or duration is produced: no norm, crew, calendar, activity or lead time exists in the documents. A duration here would be invented.")
    # ---- completeness matrix (application report) + discipline matrix from the register
    from app.reporting import completeness
    comp = completeness.project_completeness(db, pid)
    from app.api.serializers import ser as _ser
    disc = _ser(registry.run_report(db, "discipline_completeness", pid, {}))
    ev.stage("B2_registers", "PASS", discipline_matrix=disc, application_completeness_report=comp, drawing_register="EMPTY: no drawing was supplied; 6 drawing/survey documents referenced by the BOQ are registered as Missing",
             revision_register="1 current document; no superseded document; no revision identifier in the source (only two dates)", note="The discipline matrix is the application's own report (discipline_completeness), built from the document register and the BOQ trades.")
    # ---- H: generate drafts (freeze first - the pack generator needs a frozen version)
    from app.tender import packs
    vid = estimates.freeze_version(db, A["est"], pid, "practice-v1", "PRACTICE TEST: frozen INCOMPLETE estimate, only so draft documents can be generated")
    pack = packs.generate_pack(db, A["est"], pid, out_root=out / "generated", issue_date="2026-10-14", version_id=vid)
    v = packs.validate_pack(db, pack["pack_pk"])
    by = {d["code"]: d for d in pack["documents"]}
    stat = {}
    for d in pack["documents"]:
        stat.setdefault(d["status"], []).append(d["code"])
    wanted = {"Basis of estimate": "D07", "BOQ import and mapping report": "D34", "Document completeness and revision report": "D33", "Technical query / RFI register": "D25", "BOQ discrepancy and scope-gap report": "D34 + D25",
              "Assumptions and exclusions register": "D08 + D09", "Technical compliance matrix": "D23", "Procurement and missing-rate report": "D36", "Workforce and programme report": "D19/D20/D37", "Preliminary technical proposal": "D16",
              "Execution methodology": "D18", "Commercial estimate and reconciliation report": "D35", "Document applicability matrix": "applicability_matrix.json", "Open actions and handover checklist": "D42 + D43"}
    ev.stage("H1_documents_generated", "PASS" if pack["classification"] != "production" and not pack["production_ready"] else "FAIL", out_dir=pack["out_dir"], classification=pack["classification"], production_ready=pack["production_ready"], banner=pack["banner"], counts=pack["counts"],
             statuses={k: v for k, v in stat.items()}, blocked_reasons={c: by[c]["blocked_reason"] for c in by if by[c]["status"] == "BLOCKED"}, files=sum(len(d["files"]) for d in pack["documents"]), requested_outputs=wanted,
             validator=dict(ok=v["ok"], errors=v["errors"][:20], warnings=v["warnings"][:10], blocked_documents=v["blocked_documents"], files_checked=v["files_checked"]))
    # ---- I: gates / negative tests
    from app.config import get_settings
    from app.models.actor import Actor
    from app.services import auth, readiness
    s = get_settings()
    r_test = readiness.evaluate(db, pid, vid, None)
    s.environment = "production"
    try:
        r_prod = readiness.evaluate(db, pid, vid, None)
    finally:
        s.environment = "test"
    neg = {}
    assumptions.submit_assumption(db, A["est"], "ASMP-PT-001")          # submission for review is allowed; approval is not
    neg["author_approves_own_assumption"] = code_of(assumptions.approve_assumption, db, A["est"], "ASMP-PT-001", comments="x")
    neg["viewer_creates_assumption"] = code_of(assumptions.create_assumption, db, A["view"], id="ASMP-PT-V", family="A", name="viewer attempt", value_type="text")
    neg["freeze_then_export_without_approval"] = code_of(estimates.export_submission, db, A["est"], pid, vid, 999)
    estimates.submit_version(db, A["est"], vid)
    neg["approve_version_incomplete_estimate_by_test_actor"] = code_of(estimates.approve_version, db, A["com"], vid)
    neg["approve_document_D16_blocked_doc_by_test_actor"] = code_of(packs.approve_document, db, A["com"], pid, f"{pid}-D16")
    neg["approve_document_D07_by_test_actor_in_demo_project"] = code_of(packs.approve_document, db, A["com"], pid, f"{pid}-D07")
    # a real (non-demo) project with registered HUMAN users in a production environment: can missing inputs + unapproved assumptions give a submission-ready export?
    auth.create_user(db, "pt-human-estimator", "Practice human estimator (scratch)", "Estimator", "scratch-only-pw", actor_type="human")
    auth.create_user(db, "pt-human-commercial", "Practice human commercial (scratch)", "Commercial Approver", "scratch-only-pw", actor_type="human")
    he, hc = Actor("pt-human-estimator", "Estimator", "Practice human estimator"), Actor("pt-human-commercial", "Commercial Approver", "Practice human commercial")
    s.environment = "production"
    hn = {}
    try:
        np_ = projects.create_project(db, he, name="Negative control: same BOQ as a real (non-demo) project", client="NONE - practice exercise", id=NEG, is_demo=False, tax_category="VAT-STD", notes=BANNER)
        bi.import_boq(db, he, np_, csv_path)
        assumptions.adopt_mandatory(db, he, np_)
        nv = estimates.freeze_version(db, he, np_, "negative-control")
        estimates.submit_version(db, he, nv)
        hn["approve_version_by_human_commercial"] = code_of(estimates.approve_version, db, hc, nv)
        hn["approve_tender_export_by_human_commercial"] = code_of(estimates.approve_tender_export, db, hc, np_, nv)
        hn["export_submission_by_human_estimator"] = code_of(estimates.export_submission, db, he, np_, nv, 1)
        npk = packs.generate_pack(db, he, np_, out_root=scratch / "neg_pack", issue_date="2026-10-14", version_id=nv)
        hn["negative_control_pack"] = dict(classification=npk["classification"], production_ready=npk["production_ready"], blocked=sum(1 for d in npk["documents"] if d["status"] == "BLOCKED"))
        hn["approve_document_D16_(blocked)_by_human_commercial"] = code_of(packs.approve_document, db, hc, np_, f"{np_}-D16")
        hn["approve_document_D07_by_human_commercial"] = code_of(packs.approve_document, db, hc, np_, f"{np_}-D07")
        npk2 = packs.generate_pack(db, he, np_, out_root=scratch / "neg_pack", issue_date="2026-10-14", version_id=nv)
        d07 = next(d for d in npk2["documents"] if d["code"] == "D07")
        hn["D07_status_after_a_human_approved_it_in_a_not_ready_pack"] = dict(status=d07["status"], pack_classification=npk2["classification"], pack_production_ready=npk2["production_ready"])
        from app.reconciliation import engine as recon
        run_ = recon.run_reconciliation(db, he, np_)
        fnd = recon.get_run(db, run_["run_id"])["findings"]
        hn["reconciliation"] = dict(total=len(fnd), by_severity={sv: sum(1 for x in fnd if x["severity"] == sv) for sv in sorted({x["severity"] for x in fnd})},
                                    top_rules={rc: sum(1 for x in fnd if x["rule_code"] == rc) for rc in sorted({x["rule_code"] for x in fnd})})
        crit = [x for x in fnd if x["severity"] == "Critical" and x["status"] == "Open"]
        hn["accept_exception_on_a_Critical_finding"] = code_of(recon.accept_exception, db, hc, crit[0]["id"], "attempt to waive a Critical finding") if crit else "no Critical finding in this run"
        hn["final_gate_blocked"] = recon.final_gate(db, hc, np_)["blocked"]
        r_h = readiness.evaluate(db, np_, nv, None)
        hn["readiness"] = dict(classification=r_h["classification"], production_ready=r_h["production_ready"], reasons=r_h["reasons"][:12])
    finally:
        s.environment = "test"
    sub_ready = db.scalar("SELECT COUNT(*) FROM exports WHERE submission_ready=1") or 0
    neg["approve_document_D07_by_test_actor_in_demo_project"] = neg.get("approve_document_D07_by_test_actor_in_demo_project")
    ok = (not r_test["production_ready"] and not r_prod["production_ready"] and sub_ready == 0 and not hn.get("readiness", {}).get("production_ready", True)
          and all(v != "NOT REFUSED" for k, v in {**neg, **{k: v for k, v in hn.items() if isinstance(v, str) and k not in ("final_gate_blocked", "approve_document_D07_by_human_commercial")}}.items() if k != "approve_document_D07_by_test_actor_in_demo_project") and hn.get("final_gate_blocked") is True and hn.get("D07_status_after_a_human_approved_it_in_a_not_ready_pack", {}).get("status") != "Approved for Submission")
    ev.stage("I1_gates_and_negative_tests", "PASS" if ok else "FAIL", readiness_test_env=dict(classification=r_test["classification"], production_ready=r_test["production_ready"], reasons=r_test["reasons"][:14]),
             readiness_if_production_env=dict(classification=r_prod["classification"], production_ready=r_prod["production_ready"], structural=r_prod.get("structural"), reasons=r_prod["reasons"][:14]), negative_service_calls=neg,
             real_project_with_registered_human_users_in_production_env=hn, exports_marked_submission_ready=sub_ready, pack_validator_blocks_production_label=(pack["classification"] != "production"))
    priced_run(db, ev, A, out, csv_path, DERIVED, scratch)
    # ---- originals unchanged
    post = {r["filename"]: sha256(inp / r["filename"]) for r in inv}
    post_copy = {c["file"]: sha256(dest_dir / c["file"]) for c in copied}
    ev.stage("A2_originals_unchanged", "PASS" if post == pre_sha == post_copy else "FAIL", before=pre_sha, after_input_folder=post, after_workspace_copy=post_copy)
    # ---- audit chain
    try:
        ac = audit.verify_chain(db)
    except Exception as e:                       # noqa: BLE001
        ac = f"{type(e).__name__}: {e}"
    ev.stage("I2_audit_chain", "PASS" if (isinstance(ac, dict) and ac.get("ok")) or ac is True else "CHECK", result=ac if not isinstance(ac, dict) else {k: v for k, v in ac.items() if not isinstance(v, (list, dict))})
    queries = tender.list_queries(db, pid)
    (out / "queries.json").write_text(json.dumps([{k: x[k] for k in ("id", "register", "discipline", "status", "question", "why", "generated_by", "related_json")} for x in queries], indent=1, default=str), encoding="utf-8")
    (out / "inventory.json").write_text(json.dumps(inv, indent=1), encoding="utf-8")
    ev["_meta"] = dict(project=pid, scratch=str(scratch), settings_environment="test", banner=BANNER)
    return ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scratch")
    ap.add_argument("--input", default=str(ROOT / "practice_test" / "input"))
    ap.add_argument("--out", default=str(ROOT / "practice_test" / "real_document"))
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    ev = run(Path(a.scratch), Path(a.input), out)
    (out / "results.json").write_text(json.dumps(ev, indent=1, default=str), encoding="utf-8")
    for k, v in ev.items():
        if k != "_meta":
            print(f"{k:42s} {v['verdict']}" + (f"  {v.get('error', '')}" if v["verdict"] == "ERROR" else ""))


if __name__ == "__main__":
    main()
