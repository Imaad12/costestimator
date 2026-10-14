"""END-TO-END (SYNTHETIC): nine packages - civil, structural, architectural, HVAC, plumbing, electrical, fire, ELV, specialist/subcontract.

BOQ import -> mapping -> cost build-up -> procurement needs -> RFQs -> quotations -> levelling -> selection -> approved rates -> commercial
-> reconciliation -> final approval -> offer -> approved, gated export. Every approval is performed by an explicit human-role actor.
All figures are SYNTHETIC / DEMO / NOT A MARKET QUOTE; expected values below are computed independently of the engine.
"""
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import openpyxl
import pytest

from app.core.errors import ApprovalBlocked, PermissionDenied
from app.demo.build import seed_demo
from app.estimators.estimate import compute_estimate
from app.procurement import leveling, needs, quotes, rfq, selection
from app.reconciliation import engine as recon
from app.services import (assumptions, boq, commercial, estimates, offers, projects, rates, registers)

from tests.conftest import ADMIN, COMMERCIAL, ESTIMATOR, PROCUREMENT

D = Decimal


def r2(x):
    return D(x).quantize(D("0.01"), rounding=ROUND_HALF_UP)


LAB1 = D(2900) / D(208)                      # labourer build-up: (1800+400+300+150+250)/208
LAB2 = D(4950) / D(208)                      # foreman: (3500+600+300+150+400)/208


@pytest.fixture()
def demo(seeded, tmp_path):
    db = seeded
    pid = seed_demo(db)["project_id"]
    return db, pid, tmp_path


def line_total(est, item_key):
    return est.direct.items[item_key].direct_cost


def test_initial_state_matches_independent_hand_calculations(demo):
    db, pid, _ = demo
    est = compute_estimate(db, pid)
    assert est.state == "Preliminary — Incomplete" and not est.completeness["pct_items_complete"] == 100
    # --- 1.1 excavation 2,500 m3: excavator 0.05 h/m3 at 80% utilisation; tipper 0.08 h/m3; labour 0.03 h/m3; + mobilisation/demob once
    prod_h = D(2500) * D("0.05")                                         # 125 h
    charged = prod_h / D("0.8")                                          # 156.25 h
    exc = r2(charged * (D(75) + D(25) + D("3.75"))) + r2(prod_h * D(24))       # hire+operator+maintenance on charged h, fuel on productive h
    tip = r2(D(2500) * D("0.08") * D(120))
    lab = r2(D(2500) * D("0.03") * LAB1)
    mob = D(1600)
    assert line_total(est, "1.1") == exc + tip + lab + mob == D("45856.61") or line_total(est, "1.1") == exc + tip + lab + mob
    assert exc == D("19210.94") and tip == D("24000.00") and lab == D("1045.67")
    # --- 1.3 kerb 400 m: 2% fixed waste, labour 0.2 h/m
    assert line_total(est, "1.3") == r2(D(400) * D("1.02") * D(45)) + r2(D(400) * D("0.2") * LAB1) == D("19475.38")
    # --- 2.1 RC 850 m3: 3% wastage (project-approved override), crew-shift output 12 m3 (3 labourers + foreman, 8 h shift)
    shifts = D(850) / D(12)
    rc = r2(D(850) * D("1.03") * D(320)) + r2(shifts * 3 * 8 * LAB1) + r2(shifts * 1 * 8 * LAB2)
    assert line_total(est, "2.1") == rc == D("317347.50")
    # --- 3.1 blockwork 2,100 m2: block 12.5/m2 + 5%, mortar 0.02 m3/m2 + 5%, mason 0.5 h, labourer 0.3 h
    blk = r2(D(2100) * D("12.5") * D("1.05") * D("3.5")) + r2(D(2100) * D("0.02") * D("1.05") * D(250)) + r2(D(2100) * D("0.5") * D(17)) + r2(D(2100) * D("0.3") * LAB1)
    assert line_total(est, "3.1") == blk == D("134127.40")
    # --- 4.1 ductwork 950 m2 priced as an all-in subcontract rate: no separate labour/material/plant lines (no double count)
    assert line_total(est, "4.1") == D(950) * D(150)
    assert {l.kind for l in est.direct.lines if l.item_key == "4.1"} == {"subcontract"}
    # --- unit conversion in a rate: reinforcement priced per tonne, consumed in kg (blocked until 'ton' is confirmed)
    assert not est.direct.items["2.2"].complete
    # the open issues the walkthrough promises are all really there
    unpriced = {k for k, i in est.direct.items.items() if not i.complete and i.pricing_method != "excluded"}
    assert unpriced == {"2.2", "3.3", "4.2", "6.2", "7.2", "8.2", "9.1", "9.2", "9.3", "9.5"}
    assert est.direct.items["9.4"].pricing_method == "excluded"
    assert est.flags["synthetic"] is True and est.commercial is not None and est.schedule.complete is False
    codes = {e.code for e in est.direct.exceptions}
    assert {"MISSING_RATE", "UNAPPROVED_RATE", "EXPIRED_RATE", "ALLOWANCE_NOT_APPROVED", "UNPRICED_ITEM", "UNIT_MISSING"} <= codes
    # missing mandatory rates are never replaced by zero or defaults
    assert all(l.amount is None for l in est.direct.lines if l.resource_id in ("DEMO-MAT-016", "DEMO-EQP-001", "DEMO-EQP-003", "DEMO-SUB-002"))
    assert est.completeness["unknown_exposure_lines"] >= 4 and est.completeness["indicative_exposure"] > 0
    # the final gate is blocked by Critical findings
    gate = recon.final_gate(db, ESTIMATOR, pid)
    assert gate["blocked"] and any(b["severity"] == "Critical" for b in gate["blockers"])
    # and the preliminary export is watermarked, never submission-ready
    files = estimates.preliminary_export(db, ESTIMATOR, pid)
    ws = openpyxl.load_workbook(files["pricing_schedule"]).active
    assert "PRELIMINARY - NOT FOR SUBMISSION" in ws["A2"].value and "SYNTHETIC DATA" in ws["A2"].value
    assert db.scalar("SELECT COUNT(*) FROM exports WHERE submission_ready=1") == 0


def make_quote(db, pid, supplier, pkg, ref, lines, *, tax="excl", rate_tax=None, **kw):
    qid = quotes.create_quotation(db, ESTIMATOR, supplier_id=supplier, project_id=pid, package_id=pkg, reference=ref, quote_date=date.today().isoformat(),
                                  valid_until=(date.today() + timedelta(days=45)).isoformat(), tax_treatment=tax, tax_rate_pct=rate_tax,
                                  payment_terms="30 days (SYNTHETIC)", is_synthetic=True, lines=lines, **kw)
    quotes.submit_quotation(db, ESTIMATOR, qid)
    quotes.approve_quotation(db, PROCUREMENT, qid, evidence=f"checked against synthetic document {ref}")
    return qid


def award(db, pkg, qid, why, not_lowest=None, approver=PROCUREMENT):
    sid = selection.propose_selection(db, ESTIMATOR, pkg, qid, why, not_lowest_reason=not_lowest)
    selection.decide_selection(db, approver, sid, True, "approved (synthetic test)")
    for rid in selection.publish_rates(db, ESTIMATOR, sid):
        rates.approve_rate(db, PROCUREMENT, rid, comments="published from approved quotation")
    return sid


def test_complete_workflow_to_gated_submission_export(demo):
    db, pid, tmp = demo
    sups = {r["name"][:15]: r["id"] for r in db.all("SELECT id, name FROM suppliers")}
    A, B, C = sups["DEMO Supplier A"], sups["DEMO Supplier B"], sups["DEMO Supplier C"]

    # ---------------- BOQ hygiene (human decisions) ----------------
    ch = next(c for c in boq.pending_changes(db, pid) if c["entity_id"] == "2.2")
    boq.decide_change(db, ESTIMATOR, ch["id"], True, unit_code="t", comment="metric tonne per specification clause 03 20 00 (synthetic)")
    boq.acknowledge_issues(db, ESTIMATOR, pid, "6.1#2", "Second cable size is a distinct client item (confirmed by drawing E-102, synthetic)")
    assert boq.get_item(db, pid, "6.1#2")["description"].endswith("(duplicate item code in client file)")
    assert compute_estimate(db, pid).direct.items["2.2"].complete
    # reinforcement: 95 t x (1000 kg x 1.03 x 3.4 SAR/kg + 14 h x 15)
    assert line_total(compute_estimate(db, pid), "2.2") == r2(D(95) * D(1000) * D("1.03") * D("3.4")) + r2(D(95) * D(14) * D(15)) == D("352640.00")

    # ---------------- pending / expired rates ----------------
    tile = db.scalar("SELECT id FROM resource_rates WHERE resource_id='DEMO-MAT-009' AND status='Pending Review'")
    with pytest.raises(PermissionDenied):
        rates.approve_rate(db, ESTIMATOR, tile)                                    # estimators cannot verify rates
    rates.approve_rate(db, PROCUREMENT, tile, comments="synthetic catalogue price accepted")
    old_tray = db.scalar("SELECT id FROM resource_rates WHERE resource_id='DEMO-MAT-014'")
    assert rates.get_rate(db, old_tray)["status"] == "Expired"
    new_tray = rates.revise_rate(db, ESTIMATOR, old_tray, unit_price="57", price_date="2026-10-01", valid_until="2027-03-31", evidence="SYNTHETIC re-quote")
    rates.submit_rate(db, ESTIMATOR, new_tray)
    rates.approve_rate(db, PROCUREMENT, new_tray)
    assert rates.get_rate(db, old_tray)["unit_price"] == "55"                        # history preserved

    # ---------------- procurement: needs -> RFQs ----------------
    r = needs.detect_needs(db, ESTIMATOR, pid)
    reg = {i["resource_id"]: i for i in needs.register(db, pid)}
    assert {"DEMO-MAT-016", "DEMO-EQP-001", "DEMO-EQP-003", "DEMO-SUB-002"} <= set(reg)
    assert reg["DEMO-MAT-016"]["quantity"] == "760" and reg["DEMO-SUB-002"]["unit"] == "set" and reg["DEMO-SUB-002"]["quantity"] == "2"
    assert reg["DEMO-SUB-002"]["estimated_exposure"] is None                          # unknown exposure is stated as unknown, not zero
    pk = {k: v["package_id"] for k, v in reg.items()}
    rfqs = {k: rfq.create_rfq(db, ESTIMATOR, pid, v, supplier_id=A, response_deadline="2026-11-30") for k, v in
            {"DEMO-SUB-002": pk["DEMO-SUB-002"], "DEMO-EQP-001": pk["DEMO-EQP-001"]}.items()}
    body = rfq.get_rfq(db, rfqs["DEMO-SUB-002"])["body"]
    assert "Passenger lift 8 stops" in body and "2 set" in body and "SYNTHETIC SITE" in body
    xl = rfq.export_xlsx(db, rfqs["DEMO-SUB-002"], tmp / "rfq_lift.xlsx")
    assert openpyxl.load_workbook(xl)["RFQ"]["E6"].value == "set"

    # ---------------- quotations, levelling, selection, rate publication ----------------
    # J: lifts. A = 520,000/set excl. tax. B = 480,000/set INCLUDING 15% tax (=417,391.30 pre-tax) -> B is the lowest like-for-like.
    it_lift = reg["DEMO-SUB-002"]["id"]
    qa = make_quote(db, pid, A, pk["DEMO-SUB-002"], "A-LIFT", [dict(procurement_item_id=it_lift, description="Lift", quantity="2", unit="set", unit_rate="520000",
                                                             delivery_included="Yes", compliance="Compliant", lead_time_days="26")])
    qb = make_quote(db, pid, B, pk["DEMO-SUB-002"], "B-LIFT", [dict(procurement_item_id=it_lift, description="Lift", quantity="2", unit="set", unit_rate="480000",
                                                             delivery_included="Yes", compliance="Compliant", lead_time_days="40")], tax="incl", rate_tax="15")
    lv = leveling.level_package(db, pk["DEMO-SUB-002"])
    by = {q["quotation_id"]: q for q in lv["quotations"]}
    assert by[qa]["quoted_total"] == D("1040000.00") and by[qa]["normalised_total"] == D("1040000.00")
    assert by[qb]["quoted_total"] == D("960000.00") and by[qb]["normalised_total"] == r2(D(960000) / D("1.15")) == D("834782.61")
    assert lv["suggested_lowest_like_for_like"] == qb and "Advisory" in lv["advisory"]
    with pytest.raises(Exception) as e:
        selection.propose_selection(db, ESTIMATOR, pk["DEMO-SUB-002"], qa, "A is our usual lift supplier")
    assert getattr(e.value, "code", "") == "NOT_LOWEST_REASON_REQUIRED"               # the cheapest bid is never silently overridden
    sel = selection.propose_selection(db, ESTIMATOR, pk["DEMO-SUB-002"], qa, "Shorter lead time and local service", not_lowest_reason="A delivers in 26 weeks vs 40 weeks (programme critical)")
    with pytest.raises(PermissionDenied):
        selection.decide_selection(db, ESTIMATOR, sel, True)                           # value >= SAR 1,000,000 needs a Commercial Approver
    with pytest.raises(PermissionDenied) as e:
        selection.decide_selection(db, PROCUREMENT, sel, True)
    assert e.value.code == "THRESHOLD_ROLE_REQUIRED"
    selection.decide_selection(db, COMMERCIAL, sel, True, "approved on programme grounds")
    for rid in selection.publish_rates(db, ESTIMATOR, sel):
        rates.approve_rate(db, PROCUREMENT, rid)
    est = compute_estimate(db, pid)
    assert line_total(est, "9.1") == D("1040000.00")
    # E: AHU (A only). G: heads (B and C; C cheaper but partial). I: CCTV (A).
    q_ahu = make_quote(db, pid, A, pk["DEMO-EQP-001"], "A-AHU", [dict(procurement_item_id=reg["DEMO-EQP-001"]["id"], description="AHU", quantity="6", unit="nr", unit_rate="48000", compliance="Compliant")])
    award(db, pk["DEMO-EQP-001"], q_ahu, "only bidder")
    q_head_b = make_quote(db, pid, B, pk["DEMO-MAT-016"], "B-HEAD", [dict(procurement_item_id=reg["DEMO-MAT-016"]["id"], description="Head", quantity="760", unit="nr", unit_rate="38.5", compliance="Compliant", delivery_included="No")])
    q_head_c = make_quote(db, pid, C, pk["DEMO-MAT-016"], "C-HEAD", [dict(procurement_item_id=reg["DEMO-MAT-016"]["id"], description="Head", quantity="760", unit="nr", unit_rate="36", compliance="Deviation")])
    lv = leveling.level_package(db, pk["DEMO-MAT-016"])
    qq = {q["quotation_id"]: q for q in lv["quotations"]}
    assert qq[q_head_b]["delivery_or_unloading_excluded"]                              # surfaced for like-for-like review
    adj = leveling.add_adjustment(db, ESTIMATOR, q_head_b, "delivery", "1500", "Delivery to site quoted separately by supplier on call (SYNTHETIC)")
    leveling.approve_adjustment(db, PROCUREMENT, adj)
    assert {q["quotation_id"]: q["normalised_total"] for q in leveling.level_package(db, pk["DEMO-MAT-016"])["quotations"]}[q_head_b] == D("30760.00")   # 760 x 38.5 + 1,500
    award(db, pk["DEMO-MAT-016"], q_head_b, "compliant bid; the cheaper bid carries a technical deviation", not_lowest="C has a spec deviation on K-factor")
    q_cctv = make_quote(db, pid, A, pk["DEMO-EQP-003"], "A-CCTV", [dict(procurement_item_id=reg["DEMO-EQP-003"]["id"], description="Camera", quantity="48", unit="nr", unit_rate="1250", compliance="Compliant")])
    award(db, pk["DEMO-EQP-003"], q_cctv, "only bidder")
    est = compute_estimate(db, pid)
    after = needs.detect_needs(db, ESTIMATOR, pid)
    assert after["open"] == 0 and after["closed"] == 4 and needs.register(db, pid) == []        # all four procurement requirements closed by approved rates
    for k in ("4.2", "7.2", "8.2", "9.1"):
        assert est.direct.items[k].complete and est.direct.items[k].synthetic
    assert line_total(est, "4.2") == r2(D(6) * D(48000)) + r2(D(6) * D(16) * D(18)) == D("289728.00")
    assert est.direct.lines and all(l.rate_id for l in est.direct.lines if l.amount is not None)         # every priced line traces to a rate record

    # ---------------- allowances, exclusion, remaining item ----------------
    boq.decide_pricing(db, ESTIMATOR, pid, "9.2", "approve_provisional", comment="Client-stated provisional sum; included at stated value (synthetic)")
    boq.decide_pricing(db, COMMERCIAL, pid, "9.3", "approve", comment="PC sum per client BOQ")
    boq.set_pricing(db, ESTIMATOR, pid, "9.5", "allowance", amount="25000", note="Allowance pending authority confirmation (SYNTHETIC)")
    boq.decide_pricing(db, ESTIMATOR, pid, "9.5", "approve_provisional", comment="Allowance for temporary power; clarification open")
    for e in registers.list_scope(db, pid):
        registers.approve_scope_entry(db, ESTIMATOR, e["id"], "reviewed")
    est = compute_estimate(db, pid, )
    assert est.flags["provisional"] and est.direct.items["9.2"].provisional and est.direct.items["9.5"].provisional
    # tax category is still Pending Review -> final payable cannot be resolved
    assert est.commercial.tax_by_category["VAT-STD"]["tax"] is None
    assert any("Tax" in b for b in est.blockers)
    tid = db.scalar("SELECT id FROM tax_categories WHERE code='VAT-STD'")
    with pytest.raises(PermissionDenied):
        commercial.approve_tax_category(db, ESTIMATOR, tid, evidence="x")
    commercial.approve_tax_category(db, COMMERCIAL, tid, evidence="SYNTHETIC TEST: pretend verification record against official guidance")
    est = compute_estimate(db, pid)
    assert est.state.startswith("Complete with Provisional Inputs"), (est.state, est.blockers)

    # ---------------- commercial chain, independent re-derivation ----------------
    c, sch = est.commercial, est.schedule
    Dtot = est.direct.direct_cost_total
    assert Dtot == sum((l.amount for l in est.direct.lines if l.amount is not None), D(0)) == sum((i.direct_cost for i in est.direct.items.values()), D(0))
    ind = {l.code: l.amount for l in est.indirect.lines}
    assert ind["IND-01"] == D("600000.00") and ind["IND-02"] == D("720000.00") and ind["IND-03"] == D("90000.00") and ind["IND-05"] == D("250000.00")
    assert ind["IND-04"] == r2(Dtot * D("0.004")) and ind["IND-06"] == D("0") and ind["IND-07"] == D("120000.00")        # security excluded: inside a subcontract
    I = sum(ind.values(), D(0))
    ct = r2((Dtot + I) * D("0.03"))
    risk = r2(Dtot * D("0.01"))
    esc = r2((Dtot + I + ct + risk) * D("0.02"))
    T = Dtot + I + ct + risk + esc
    S = r2(T * D("1.08"))
    N = (S / D(1)).quantize(D(1), rounding=ROUND_HALF_UP)                              # rounding step 1 SAR
    assert (c.pre_contingency_cost, c.contingency, c.risk, c.escalation, c.total_cost, c.selling_price_pre_discount, c.net_price) == (Dtot + I, ct, risk, esc, T, S, N)
    assert abs(sch.total_pre_tax - N) <= sch.max_rounding_variance                      # schedule reconciles to the internal estimate within unit-rate rounding
    assert sch.rounding_variance == sch.total_pre_tax - N
    assert c.tax_total == r2(sch.total_pre_tax * D("0.15")) and c.final_payable == sch.total_pre_tax + c.tax_total
    assert len(sch.separate_lines) == 2 and {s["code"] for s in sch.separate_lines} == {"IND-05", "IND-07"}
    alloc = {a["code"]: a for a in sch.indirect_allocation}
    assert alloc["IND-01"]["allocation"] == "pro_rata_direct" and alloc["IND-05"]["allocation"] == "separate_line" and alloc["IND-06"]["note"].startswith("Included in subcontract")
    assert sum((l.allocated_indirect for l in sch.lines), D(0)) == I - D("250000.00") - D("120000.00")                   # original indirect total fully accounted for

    # ---------------- reconciliation ----------------
    run = recon.run_reconciliation(db, ESTIMATOR, pid)
    fs = recon.get_run(db, run["run_id"])["findings"]
    open_ = [f for f in fs if f["status"] == "Open"]
    by_rule = {}
    for f in open_:
        by_rule.setdefault(f["rule_code"], []).append(f)
    assert not [f for f in open_ if f["severity"] == "Critical"], [(f["rule_code"], f["detail"]) for f in open_ if f["severity"] == "Critical"]
    assert {"CLARIFICATION_OPEN", "BOQ_ROWS_REJECTED", "UNAPPROVED_ADOPTED_ASSUMPTION", "PROVISIONAL_INPUTS", "OFFER_MISSING"} <= set(by_rule)
    gate = recon.final_gate(db, ESTIMATOR, pid)
    assert gate["blocked"]                                                              # High findings (open clarifications) still block
    # freeze + approve is refused while blocking findings exist
    vid = estimates.freeze_version(db, ESTIMATOR, pid, "tender v1")
    estimates.submit_version(db, ESTIMATOR, vid)
    with pytest.raises(ApprovalBlocked) as e:
        estimates.approve_version(db, COMMERCIAL, vid)
    assert e.value.code == "RECON_BLOCKED"
    # human resolution of the open items
    for cl in registers.list_clarifications(db, pid):
        registers.resolve_clarification(db, ESTIMATOR, cl["id"], "Confirmed by client: lift 1000 kg / 1.6 m/s; temp power by main contractor (synthetic)", "Addendum 02, ref SYN-ADD-02")
    for f in by_rule["UNAPPROVED_ADOPTED_ASSUMPTION"]:                           # O-2: High now - only a Commercial Approver may accept it, never an Estimator
        with pytest.raises(PermissionDenied):
            recon.accept_exception(db, ESTIMATOR, f["id"], "Documented: remaining assumptions are not used by this synthetic estimate")
        recon.accept_exception(db, COMMERCIAL, f["id"], "Documented: remaining assumptions are not used by this synthetic estimate")
    for f in by_rule["BOQ_ROWS_REJECTED"] + by_rule["PROVISIONAL_INPUTS"]:
        recon.accept_exception(db, ESTIMATOR, f["id"], "Documented: row 'TBA' is a client placeholder; remaining assumptions are not used by this synthetic estimate; provisional inputs are as per client")
    for f in by_rule.get("INDIRECT_BASE_OVERLAP", []):                           # a High finding: only a Commercial Approver may accept it
        recon.accept_exception(db, COMMERCIAL, f["id"], "Documented: the percentage indirect is intentionally applied to the whole direct cost incl. one preliminaries line (synthetic)")
    gate = recon.final_gate(db, ESTIMATOR, pid)
    assert not gate["blocked"] and any(f["rule_code"] == "OFFER_MISSING" for f in recon.get_run(db, gate["run_id"])["findings"])
    # offer
    o = offers.generate_offer(db, ESTIMATOR, pid, validity_days=30, payment_terms="Per client conditions (SYNTHETIC)")
    assert "DEMONSTRATION PROJECT" in o["banner"] and o["total_pre_tax"] == sch.total_pre_tax
    from docx import Document
    text = "\n".join(p.text for p in Document(o["file"]).paragraphs)
    assert f"{sch.total_pre_tax:,.2f}" in text and "Landscaping and irrigation" in text and "INC-" in text and "EXC-" in text
    with pytest.raises(PermissionDenied):
        offers.approve_offer(db, ESTIMATOR, pid, o["version_no"])
    offers.approve_offer(db, COMMERCIAL, pid, o["version_no"], "ok")

    # ---------------- final approval ----------------
    # v1 was submitted while blocking findings existed (and refused); the numeric inputs are unchanged, the findings are now resolved
    with pytest.raises(PermissionDenied):
        estimates.approve_version(db, ESTIMATOR, vid)
    with pytest.raises(PermissionDenied):
        estimates.approve_version(db, PROCUREMENT, vid)
    res = estimates.approve_version(db, COMMERCIAL, vid, "final review complete (synthetic)")
    assert res["approved"]
    vid2 = vid
    # an export needs its own explicit approval; nothing leaves without it
    with pytest.raises(ApprovalBlocked):
        estimates.export_submission(db, COMMERCIAL, pid, vid2, 999999)
    with pytest.raises(PermissionDenied):
        estimates.approve_tender_export(db, ESTIMATOR, pid, vid2)
    ap = estimates.approve_tender_export(db, COMMERCIAL, pid, vid2, "release (synthetic)")
    files = estimates.export_submission(db, ESTIMATOR, pid, vid2, ap)
    assert set(files) == {"pricing_schedule", "estimate_report", "letter_of_offer", "reconciliation_report"} and all(Path(f).exists() for f in files.values())
    ws = openpyxl.load_workbook(files["pricing_schedule"]).active
    assert ws["A2"].value.startswith("DEMONSTRATION EXPORT - NOT SUBMISSION READY") and "unregistered" in ws["A2"].value and "NOT A MARKET QUOTE" in ws["A2"].value and "PROVISIONAL" in ws["A2"].value
    amounts = [ws.cell(r, 6).value for r in range(6, 6 + len(sch.lines) + len(sch.separate_lines)) if ws.cell(r, 6).value]
    assert abs(D(str(sum(amounts))) - sch.total_pre_tax) < D("0.01")                   # client file adds up to the offer total
    # client-facing file carries no internal cost information
    flat = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None).lower()
    assert "markup" not in flat and "contingency" not in flat and "direct cost" not in flat
    assert db.scalar("SELECT COUNT(*) FROM exports WHERE submission_ready=1") == 0 and db.scalar("SELECT COUNT(*) FROM exports WHERE readiness='demonstration'") == 4      # demo project + unregistered approvers: never submission-ready
    # ---- client-supplied tender form (OUT-05): matched on item code, only mapped cells written, formulas untouched, gated like every submission-ready file
    from openpyxl import Workbook, load_workbook
    tpl = Path(files["pricing_schedule"]).parent / "client_template_test.xlsx"
    twb = Workbook(); tws = twb.active; tws.title = "Schedule of Rates"
    tws["A1"] = "CLIENT TENDER FORM"
    priced = [l for l in sch.lines if l.status in ("Priced", "Provisional") and l.amount is not None]
    for i, l in enumerate(priced):
        tws.cell(8 + i, 1, l.item_code or l.item_key)
        tws.cell(8 + i, 2, "client wording " + str(i))
    tws.cell(8 + len(priced), 1, "ZZ.9")                                                # client row the schedule knows nothing about
    tws.cell(8, 5, "=B8&\"\"")                                                           # a client formula in a mapped column of a matched row
    twb.save(tpl)
    mapping = {"sheet": "Schedule of Rates", "first_row": 8, "key_column": "A", "columns": {"quantity": "D", "unit_rate": "E", "amount": "F"},
               "totals": {"total_pre_tax": "F90"}, "banner_cell": "A1"}
    from app.core.errors import ValidationFailed as VF
    with pytest.raises(ApprovalBlocked):
        estimates.export_client_form(db, ESTIMATOR, pid, tpl, mapping, version_id=vid2, approval_id=424242)                    # no valid approval -> refused
    pre = estimates.export_client_form(db, ESTIMATOR, pid, tpl, mapping)                                                     # preliminary copy needs no approval but is labelled
    assert pre["submission_ready"] is False and pre["file"].endswith("_PRELIMINARY.xlsx")
    assert load_workbook(pre["file"])["Schedule of Rates"]["A1"].value.startswith("PRELIMINARY - NOT FOR SUBMISSION")
    rep = estimates.export_client_form(db, ESTIMATOR, pid, tpl, mapping, version_id=vid2, approval_id=ap)
    assert rep["submission_ready"] is False and rep["rows_filled"] == len(priced) and rep["template_rows_without_schedule_item"] == [dict(row=8 + len(priced), key="ZZ.9")]
    out_ws = load_workbook(rep["file"])["Schedule of Rates"]
    assert out_ws["A1"].value.startswith("DEMONSTRATION EXPORT - NOT SUBMISSION READY") and out_ws.cell(8, 5).value == '=B8&""'          # banner states the real status; client formula untouched
    assert any("formula" in x["reason"] for x in rep["skipped"]) and rep["ties_out"] is False
    assert abs(D(str(sum(out_ws.cell(8 + i, 6).value for i in range(len(priced))))) - rep["filled_amount_total"]) < D("0.01")
    assert abs(D(str(out_ws["F90"].value)) - sch.total_pre_tax) < D("0.01") and out_ws.cell(8, 2).value == "client wording 0"     # totals cell written; client wording preserved
    with pytest.raises(VF) as e:                                                                                         # templates outside the workspace are refused
        estimates.export_client_form(db, ESTIMATOR, pid, "/etc/hostname", mapping)
    assert e.value.code == "FORM_PATH"
    with pytest.raises(VF):
        estimates.export_client_form(db, ESTIMATOR, pid, tpl, {"sheet": "Nope", "first_row": 8, "key_column": "A", "columns": {"amount": "F"}})
    with pytest.raises(VF):
        estimates.export_client_form(db, ESTIMATOR, pid, tpl, mapping, version_id=vid2)
    # changing any input after approval re-blocks the export path and the approved version stays frozen
    db.execute("UPDATE boq_items SET quantity='999' WHERE project_id=? AND item_key='1.2'", (pid,))
    with pytest.raises(ApprovalBlocked):
        estimates.export_submission(db, ESTIMATOR, pid, vid2, ap)
    assert estimates.get_version(db, vid2)["status"] == "Approved"
    # the audit trail is intact and records the human decisions
    from app.services import audit
    assert audit.verify_chain(db)["ok"]
    log = db.all("SELECT DISTINCT reviewer FROM approvals WHERE project_id=?", (pid,))
    assert {"demo-seed", "est", "proc", "com"} <= {r["reviewer"] for r in log}
    assert db.scalar("SELECT COUNT(*) FROM approvals WHERE reviewer LIKE 'ai%'") == 0
