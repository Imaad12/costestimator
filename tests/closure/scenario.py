"""Self-running SYNTHETIC end-to-end tender closure: 'Dammam Industrial Utilities - Synthetic Tender Closure'.

Drives the REAL services / actions / CLI against a scratch database and writes a tender pack, a hypothetical post-award handover pack, a machine-readable manifest and acceptance results
into a separate output directory. Every actor is a registered TEST ACTOR; nothing here is a real approval, quotation, customer or market rate. The run can never be submission-ready.
"""
from __future__ import annotations

import json
import shutil
import traceback
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from . import data as Dt

D = Decimal
STAGES = ["01_enquiry", "02_bid_no_bid", "03_project_and_documents", "04_boq_import", "05_validate_and_map", "06_assumptions_and_missing_data", "07_direct_cost_and_missing_rates",
          "08_productivity_and_crew_scenarios", "09_resource_constrained_programme", "10_queries_and_clarifications", "11_customer_responses", "12_recalculate_impacts",
          "13_procurement_and_quote_levelling", "14_indirects_tax_risk_escalation_cashflow", "15_methodology_and_compliance", "16_applicability_matrix", "17_generate_document_pack",
          "18_validate_document_pack", "19_production_readiness_blocked", "20_assumption_bypass_blocked", "21_resolve_issues_with_test_approvals", "22_final_demonstration_pack",
          "23_hypothetical_handover_pack", "24_freeze_estimate_and_manifest", "25_global_library_change", "26_snapshot_replay", "27_ui_api_cli_agreement"]


def r2(x) -> Decimal:
    return D(x).quantize(D("0.01"), rounding=ROUND_HALF_UP)


class Evidence(dict):
    def stage(self, key: str, verdict: str, **facts):
        self[key] = {"verdict": verdict, **facts}


def bootstrap(workdir: Path):
    from app import config as cfg
    from app.database import Database, set_db
    from app.services import auth, refdata
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    s = cfg.load_settings(env={"KSA_DB_PATH": str(workdir / "scratch_closure.db"), "KSA_WORKSPACES_DIR": str(workdir / "workspaces"), "KSA_SECRET_KEY": "synthetic-closure",
                               "KSA_ALLOW_SELF_APPROVAL": "false", "KSA_ENVIRONMENT": "test"})
    cfg.set_settings(s)
    if Path(s.db_path).exists():
        raise RuntimeError(f"{s.db_path} already exists: the scenario needs a fresh scratch directory")
    db = Database(s.db_path)
    db.migrate()
    set_db(db)
    refdata.seed_reference(db)
    for u, role in (("test-estimator", "Estimator"), ("test-procurement", "Procurement Reviewer"), ("test-commercial", "Commercial Approver"), ("test-admin", "Administrator"),
                    ("test-viewer", "Viewer")):
        auth.create_user(db, u, f"TEST ACTOR {role}", role, "synthetic-only-pw", actor_type="test")
    return db, s


def actors():
    from app.models.actor import Actor
    return dict(est=Actor("test-estimator", "Estimator", "TEST ACTOR Estimator"), proc=Actor("test-procurement", "Procurement Reviewer", "TEST ACTOR Procurement"),
                com=Actor("test-commercial", "Commercial Approver", "TEST ACTOR Commercial"), admin=Actor("test-admin", "Administrator", "TEST ACTOR Admin"),
                view=Actor("test-viewer", "Viewer", "TEST ACTOR Viewer"))


def _try(fn, *a, **k):
    from app.core.errors import AppError
    try:
        fn(*a, **k)
        return "NOT REFUSED"
    except AppError as e:
        return e.code
    except Exception as e:                       # noqa: BLE001 - sqlite3 trigger refusals etc.
        return f"{type(e).__name__}: {str(e)[:90]}"


# ================================================================================================ stages 1-3
def stage_enquiry_project_docs(db, ev, A, workdir):
    from app.services import projects, tender, workspaces
    eid = tender.create_enquiry(db, A["est"], customer_name=Dt.CUSTOMER, title="Dammam Industrial Utilities - process piping, pipe-rack and E&I package", received_date="2027-01-04",
                                tender_deadline="2027-03-01", customer_is_synthetic=True,
                                submission_instructions="SYNTHETIC: sealed copy to the (fictional) customer procurement office; this scenario never submits anything.",
                                brief="SYNTHETIC enquiry: supply, fabricate and install utility process piping, pipe-rack foundations and steel, two transfer pump skids, E&I and CCTV for a fictional Dammam industrial site.",
                                scope_summary="Trench and foundation works, pipe-rack steel, carbon-steel process piping with welding/NDT/hydrotest, pump skid setting, LV power, fibre and CCTV, fire-water tie-ins (interface), testing and commissioning.")
    ack = dict(enquiry=eid, acknowledgement="SYNTHETIC acknowledgement draft: enquiry received 2027-01-04; clarifications will follow through the query register.")
    pid = projects.create_project(db, A["est"], name="Dammam Industrial Utilities - Synthetic Tender Closure", client=Dt.CUSTOMER, location="Dammam industrial area, Saudi Arabia (fictional site)",
                                  project_type="industrial utilities", design_stage="SYNTHETIC TEST", is_demo=True, tax_category="VAT-STD", id=Dt.PROJECT_ID, tender_ref="SYN-TENDER-9101",
                                  trades=["civil", "structural", "piping", "mechanical", "electrical", "elv", "fire"], notes=Dt.BANNER)
    tender.link_enquiry(db, A["est"], eid, pid)
    root = workspaces.resolve_dir(pid, db)
    (root / "1. Tender Documents" / "SYNTHETIC_enquiry_note_TEST_ONLY.txt").write_text(Dt.BANNER + "\n" + db.one("SELECT brief FROM tender_enquiries WHERE id=?", (eid,))["brief"] + "\n", encoding="utf-8")
    ev.stage("01_enquiry", "PASS", enquiry=eid, customer=Dt.CUSTOMER, acknowledgement=ack["acknowledgement"], synthetic_customer=True)
    # bid / no-bid (judgement recorded by a person; the system does not decide)
    for k, (crit, assess, evid) in {"capacity": ("Resource capacity", "Bid: mid-sized crew can cover the programme (see crew scenarios)", "SYNTHETIC workforce scenarios"),
                                    "margin": ("Commercial attractiveness", "Bid, subject to resolving open queries and the missing-rate package", "SYNTHETIC estimate"),
                                    "risk": ("Technical / contractual risk", "Moderate: ambiguous scope items and an interface with existing fire ring main", "SYNTHETIC queries")}.items():
        tender.upsert_item(db, A["est"], pid, "bid_no_bid", k, dict(criterion=crit, assessment=assess, evidence=evid), source_ref="SYNTHETIC bid review", is_synthetic=True)
        tender.submit_item(db, A["est"], pid, "bid_no_bid", k)
        tender.approve_item(db, A["com"], pid, "bid_no_bid", k, comments="TEST ACTOR: SYNTHETIC")
    for k, (inp, need, note) in {"drawings": ("Complete drawing set with all revisions", "quantities and methodology", "DWG-EL-010 missing at enquiry"), "payment": ("Payment, retention and bond terms", "cash-flow basis and financing", "not stated in the ITT"),
                                  "quality": ("Customer quality-plan requirement", "documents D27, D28, D30", "conflicting statements"), "site": ("Site access and working-hour rules", "calendar and programme", "to be confirmed")}.items():
        tender.upsert_item(db, A["est"], pid, "required_input", k, dict(input=inp, needed_for=need, status_note=note), source_ref="enquiry review (SYNTHETIC)", is_synthetic=True)
    for k, (role, resp, who) in {"estimating": ("Estimating lead", "BOQ mapping, pricing, queries", "SIMULATED OWNER - Lead Estimator (test)"), "commercial": ("Commercial approver", "commercial policy, offer, final gate", "SIMULATED OWNER - Commercial Manager (test)"),
                                  "procurement": ("Procurement lead", "RFQs, quote levelling, long-lead items", "SIMULATED OWNER - Procurement Manager (test)")}.items():
        tender.upsert_item(db, A["est"], pid, "responsibility", k, dict(role=role, responsibility=resp, assigned_to=who), source_ref="project setup (SYNTHETIC)", is_synthetic=True)
    ev.stage("02_bid_no_bid", "PASS", items=[i["item_key"] for i in tender.list_items(db, pid, "bid_no_bid")], statuses=[i["status"] for i in tender.list_items(db, pid, "bid_no_bid")])
    # context + customer requirements (one deliberately conflicting, one deliberately unstated)
    tender.upsert_item(db, A["est"], pid, "tender_context", "context", dict(contract_type="lump sum (FICTIONAL)", delivery_model="construct-only (FICTIONAL)", award_scenario="",
                                                                          customer_requires={"technical_proposal": "yes"}), source_ref="ITT-001 (FICTIONAL)", is_synthetic=True)
    tender.upsert_item(db, A["est"], pid, "customer_requirement", "ITT-001-4.2", dict(requirement="quality plan required", stated="no", source="ITT-001 section 4.2"), is_synthetic=True)
    tender.upsert_item(db, A["est"], pid, "customer_requirement", "SPEC-PIPE-001-1.5", dict(requirement="quality plan required", stated="yes", source="SPEC-PIPE-001 section 1.5"), is_synthetic=True)
    # document register: revisions and a missing document
    for ref, typ, title, rev, st in Dt.DOCS:
        tender.register_document(db, A["est"], pid, doc_ref=ref, doc_type=typ, title=title, revision=rev, source="SYNTHETIC customer issue", received_date="2027-01-04", status=st, is_synthetic=True)
    tender.register_document(db, A["est"], pid, doc_ref="DWG-PR-001", doc_type="drawing", title="Process piping layout (FICTIONAL)", revision="C", source="SYNTHETIC addendum 1", received_date="2027-02-02",
                             applicability="supersedes revision B by addendum", is_synthetic=True)
    tender.register_document(db, A["est"], pid, doc_ref="ADD-001", doc_type="addendum", title="Addendum 1 (FICTIONAL): revised piping layout", revision="0", received_date="2027-02-02", is_synthetic=True)
    rep = tender.documents_report(db, pid)
    ev.stage("03_project_and_documents", "PASS" if rep["superseded"] and rep["missing"] and rep["not_interpreted"] else "FAIL", project=pid, workspace=str(root),
             current=len(rep["current"]), superseded=[(d["doc_ref"], d["revision"]) for d in rep["superseded"]], missing=[d["doc_ref"] for d in rep["missing"]],
             not_interpreted=len(rep["not_interpreted"]), note="documents are registered, not interpreted")
    return pid


# ================================================================================================ stages 4-7
def stage_boq(db, ev, A, pid):
    from app.imports import boq as bi
    from app.services import boq
    src = Dt.FIX / "boq_SYNTHETIC_TEST_ONLY.csv"
    imp = bi.import_boq(db, A["est"], pid, src)
    rows = db.all("SELECT item_key, unit, unit_status, validation_status, issues_json, quantity FROM boq_items WHERE project_id=? AND item_type='item' ORDER BY id", (pid,))
    dups = [r["item_key"] for r in rows if "#" in r["item_key"]]
    bad_units = [r["item_key"] for r in rows if r["unit_status"] != "ok"]
    ev.stage("04_boq_import", "PASS" if imp["items_new"] == 44 and dups == ["C-071#2"] and not bad_units else "FAIL",
             items=imp["items_new"], rejected=imp["rejected"], change_requests=imp["change_requests"], duplicates=dups, units_not_ok=bad_units,
             sum_of_quantities_by_item=None)
    return rows


def stage_map(db, ev, A, pid):
    from app.services import assemblies, boq, rates
    L = Dt.lines()
    seen = set()
    rtype_of = {}
    for b in L:
        if b["item"] in seen:
            continue
        seen.add(b["item"])
        rtype_of[b["item"]] = b
        rid, acode = f"SYN-{b['item']}", f"SYNA-{b['item']}"
        rates.create_resource(db, A["est"], resource_type=b["rtype"], description=f"SYNTHETIC installed baseline: {b['description']}", unit=b["unit"], cost_code=b["cost_code"], id=rid, is_synthetic=True)
        ln = dict(line_type=b["rtype"], resource_id=rid, factor="1")
        if b["rtype"] == "material":
            ln["factor_includes_waste"] = 1
        if b["rtype"] == "plant":
            ln["factor_unit"] = b["unit"]
        if b["rtype"] == "labour":
            ln["productivity_basis"] = "paid_hours_per_unit"
        assemblies.create_assembly(db, A["est"], code=acode, description=f"SYNTHETIC installed-rate assembly {b['item']}", unit=b["unit"], cost_code=b["cost_code"], is_synthetic=True,
                                   source="SYNTHETIC test assembly - one installed-rate line", lines_=[ln])
        assemblies.submit_assembly(db, A["est"], acode)
        assemblies.approve_assembly(db, A["com"], acode, comments="TEST ACTOR: SYNTHETIC")
        if b["rate"] is not None:
            r = rates.propose_rate(db, A["est"], rid, unit_price=str(b["rate"]), rate_type="Synthetic Demonstration Rate", unit=b["unit"], price_date="2026-10-01", confidence="Medium",
                                   is_synthetic=True, evidence="SYNTHETIC / DEMO / NOT A MARKET QUOTE", submit=True)
            rates.approve_rate(db, A["proc"], r, comments="TEST ACTOR: SYNTHETIC rate approval (not a real procurement approval)")
    n = 0
    for row in db.all("SELECT item_key FROM boq_items WHERE project_id=? AND item_type='item' ORDER BY id", (pid,)):
        key = row["item_key"]
        base = key.split("#")[0]
        if "#" in key:
            continue                                 # the duplicate stays unmapped: it is a BOQ discrepancy for the customer to resolve
        boq.map_to_assembly(db, A["est"], pid, key, f"SYNA-{base}")
        boq.set_cost_code(db, A["est"], pid, key, rtype_of[base]["cost_code"])
        n += 1
    unmapped = [r["item_key"] for r in db.all("SELECT item_key FROM boq_items WHERE project_id=? AND item_type='item' AND mapping_status='Unmapped'", (pid,))]
    no_rate = sorted({f"SYN-{b['item']}" for b in L if b["rate"] is None})
    ev.stage("05_validate_and_map", "PASS" if unmapped == ["C-071#2"] and n == 43 else "FAIL", mapped=n, unmapped=unmapped, resources_without_rate=no_rate,
             note="every BOQ quantity is the human-measured fixture value; the duplicate code is left unmapped and unpriced until the customer clarifies")
    return rtype_of


def stage_assumptions(db, ev, A, pid):
    from app.reporting import registry
    from app.services import assumptions
    new = [("ASMP-Z-001", "A", "Scope and design", "Design stage of the tender documents", "text", "IFC for tender (SYNTHETIC)", None),
           ("ASMP-Z-002", "D", "Productivity and workforce", "Productive hours per worker per shift", "number", "6", "hr"),
           ("ASMP-Z-003", "F", "Logistics, transport and landed cost", "Delivery to site is by the supplier unless the quotation states otherwise", "text", "supplier delivers (SYNTHETIC)", None),
           ("ASMP-Z-004", "I", "Commercial terms and payment", "Offer validity period (days)", "number", "30", "day"),
           ("ASMP-Z-005", "K", "Commissioning, testing and handover", "Hydrotest pressure basis is per the piping specification", "text", "per SPEC-PIPE-001 (not yet read by a person)", None),
           ("ASMP-Z-006", "L", "Risk and contingency", "Contingency allowance basis", "text", "", None)]
    for aid, fam, cat, name, vt, val, unit in new:
        assumptions.create_assumption(db, A["est"], id=aid, family=fam, name=name, category=cat, value_type=vt, default_value=val or None, unit=unit, source="SYNTHETIC test assumption",
                                      evidence="SYNTHETIC", confidence="Low", mandatory_for_projects=False, is_synthetic=True, reason="needed by the closure scenario",
                                      business_impact="drives the tender basis", consequence_if_missing="document D08 shows the assumption as missing", affects="programme, commercial terms")
        assumptions.adopt(db, A["est"], pid, aid)
    # lifecycle: Z-001/2/4 approved by a different person, Z-003 pending, Z-005 draft, Z-006 has no value (missing)
    for aid in ("ASMP-Z-001", "ASMP-Z-002", "ASMP-Z-004", "ASMP-Z-003"):
        assumptions.submit_assumption(db, A["est"], aid)
    for aid in ("ASMP-Z-001", "ASMP-Z-002", "ASMP-Z-004"):
        assumptions.approve_assumption(db, A["com"], aid, comments="TEST ACTOR: SYNTHETIC")
    rep = registry.run_report(db, "assumption_evidence", pid, {})
    z = {r["id"]: r["data_class"] for r in rep["rows"] if r["id"].startswith("ASMP-Z")}
    ok = z.get("ASMP-Z-001") == "Explicitly synthetic test data" and z.get("ASMP-Z-003") == "Explicitly synthetic test data" and not rep["fully_verified"]
    ev.stage("06_assumptions_and_missing_data", "PASS" if ok else "FAIL", classes_of_new_assumptions=z, fully_verified=rep["fully_verified"], counts=rep["by_class"],
             problems_sample=rep["problems"][:8], note="a synthetic assumption can never read as verified, even after approval; a missing value stays 'Missing data'")
    return rep


def stage_direct(db, ev, A, pid):
    from app.estimators.estimate import compute_estimate
    est = compute_estimate(db, pid)
    L = Dt.lines()
    seen, ext = set(), D(0)
    rows = []
    for b in L:
        if b["item"] in seen or b["rate"] is None:
            continue
        seen.add(b["item"])
        amt = r2(D(str(b["qty"])) * D(str(b["rate"])))
        ext += amt
        rows.append((b["item"], amt))
    app_total = est.direct.direct_cost_total
    unpriced = sorted({e.resource_id for e in est.direct.exceptions if e.code == "MISSING_RATE"})
    # item-level independent check (priced lines only)
    diffs = {k: (str(est.direct.items[k].direct_cost), str(a)) for k, a in rows if r2(est.direct.items[k].direct_cost) != a}
    ev.stage("07_direct_cost_and_missing_rates", "PASS" if not diffs and r2(app_total) == ext and est.state != "Complete" and len(unpriced) == 3 else "FAIL",
             application_direct_cost=str(app_total), independent_direct_cost_priced_lines=str(ext), line_differences=diffs, state=est.state, unpriced_resources=unpriced,
             note="the three unpriced items stay unpriced (amount None, never zero); the estimate is not complete")
    return est


# ================================================================================================ stages 8-9
def _calendar(db, A, pid, *, confirmed: bool):
    from app.services import governed
    data = {"start_date": Dt.START_DATE, "work_weekdays": [6, 0, 1, 2, 3], "holidays": ["2027-03-30"], "hours_per_day": "8",
            "reduced_hours": [{"from": "2027-04-04", "to": "2027-04-29", "hours": "6", "reason": "SYNTHETIC reduced-hours window for testing (not an actual Ramadan date)"}],
            "shutdowns": [{"from": "2027-05-16", "to": "2027-05-18", "reason": "SYNTHETIC client shutdown (test)"}],
            "calendar_source": "SYNTHETIC default Saudi-style profile (test)", "requires_confirmation": not confirmed}
    i = governed.propose(db, A["est"], "calendar", "PROJECT", data, project_id=pid, source="SYNTHETIC TEST DATA - calendar default profile" + ("" if not confirmed else " confirmed by a TEST ACTOR for the project"),
                         is_synthetic=True, submit=True)
    governed.approve(db, A["com"], i, comments="TEST ACTOR: SYNTHETIC")
    return i


def _norms(db, A, ids=None):
    from app.services import workforce as wf
    out = {}
    for nid, trade, act, unit, basis, val, crew in Dt.NORMS:
        wf.create_norm(db, A["est"], id=nid, trade=trade, activity=act, output_unit=unit, basis=basis, value=val, crew=crew, source=Dt.SYN, evidence="SYNTHETIC fixture value",
                       effective_from="2027-01-01", review_by="2027-12-31", confidence="Low", is_synthetic=True, applicability={"region": "KSA (SYNTHETIC)", "project_type": "industrial utilities"},
                       exclusions="SYNTHETIC: no site-specific factors included")
        wf.submit_norm(db, A["est"], nid)
        wf.approve_norm(db, A["com"], nid, comments="TEST ACTOR: SYNTHETIC norm approved to exercise the workflow (NOT a benchmark)")
        out[nid] = wf.get_norm(db, nid)["status"]
    return out


def stage_productivity(db, ev, A, pid):
    from app.services import bids, workforce as wf
    _calendar(db, A, pid, confirmed=False)
    norm_status = _norms(db, A)
    # states a norm can be in (none of these becomes 'Approved' without a different person's decision)
    wf.create_norm(db, A["est"], id="N-DRAFT", trade="Piping", activity="Draft example", output_unit="m", basis="crew_output_per_crew_day", value="10", crew={"skilled": 1}, source=Dt.SYN, is_synthetic=True)
    wf.create_norm(db, A["est"], id="N-PROPOSED", trade="Piping", activity="Proposed example", output_unit="m", basis="crew_output_per_crew_day", value="10", crew={"skilled": 1}, source=Dt.SYN, is_synthetic=True)
    wf.propose_norm(db, A["est"], "N-PROPOSED")
    wf.create_norm(db, A["est"], id="N-IMPORTED", trade="Piping", activity="Imported example", output_unit="m", basis="crew_output_per_crew_day", value="10", crew={"skilled": 1}, source=Dt.SYN, origin="import")
    wf.create_norm(db, A["est"], id="N-REJECT", trade="Piping", activity="Rejected example", output_unit="m", basis="crew_output_per_crew_day", value="99", crew={"skilled": 1}, source=Dt.SYN, effective_from="2027-01-01", is_synthetic=True)
    wf.submit_norm(db, A["est"], "N-REJECT")
    wf.reject_norm(db, A["com"], "N-REJECT", "TEST ACTOR: SYNTHETIC rejection - value not supported by the cited source")
    wf.create_norm(db, A["est"], id="N-SYSTEM", trade="Piping", activity="System-proposed example", output_unit="m", basis="crew_output_per_crew_day", value="10", crew={"skilled": 1}, source=Dt.SYN, is_synthetic=True)
    state_demo = {n["id"]: n["status"] for n in wf.list_norms(db) if n["id"] in ("N-DRAFT", "N-PROPOSED", "N-IMPORTED", "N-SYSTEM", "N-REJECT")}
    for prof in Dt.PROFILES:
        pid_, arch, name, roles, indirect, shifts, nt, att, av, ph, fronts, sub = prof
        wf.create_profile(db, A["est"], id=pid_, archetype=arch, name=name, roles=roles, indirect=indirect, shifts=shifts, night_shift_efficiency_pct=nt, attendance_pct=att, availability_pct=av,
                          productive_hours_per_shift=ph, work_fronts=fronts, subcontract_capacity=sub, role_day_cost=Dt.ROLE_DAY_COST, source=Dt.SYN, is_synthetic=True,
                          notes="Configurable company planning assumption (SYNTHETIC): not an industry-standard category")
        wf.submit_profile(db, A["est"], pid_)
        wf.approve_profile(db, A["com"], pid_, comments="TEST ACTOR: SYNTHETIC")
    ll = bids.add_long_lead(db, A["est"], pid, "Transfer pump skids (SYNTHETIC)", 20, "2027-07-15", planned_order_date="2027-03-14", notes="SYNTHETIC lead time; not a supplier confirmation")
    acts = []
    for code, name, boq, norm, crews, fronts, fixed, preds, cc in Dt.ACTIVITIES:
        acts.append(dict(code=code, name=name, boq_item_key=boq, norm_id=norm, crews=crews, work_fronts=fronts, fixed_days=fixed, predecessors=preds, cost_code=cc,
                         long_lead_id=ll if code == "A-PUMP" else None))
    wf.set_activities(db, A["est"], pid, acts)
    sc = wf.crew_scenarios(db, pid, [p[0] for p in Dt.PROFILES], allow_provisional=True, allow_unconfirmed_calendar=True)
    base = {s["profile"]: s for s in sc["scenarios"]}
    wds = {k: v["working_days"] for k, v in base.items()}
    ok = (all(not v["complete"] for v in base.values()) and all(v["claim"].startswith("PROVISIONAL") for v in base.values())
          and wds["WP-SME"] >= wds["WP-MID"] >= wds["WP-LARGE"] >= wds["WP-ENT"]
          and D(wds["WP-SME"]) / wds["WP-ENT"] < D(base["WP-ENT"]["headcount"]) / base["WP-SME"]["headcount"] / 2 and wds["WP-LARGE"] == wds["WP-ENT"] and all(v["schedulable"] for v in base.values()))
    ev.stage("08_productivity_and_crew_scenarios", "PASS" if ok else "FAIL", norm_states_after_workflow=dict(sorted(norm_status.items())[:4]) | {"...": f"{len(norm_status)} norms Approved by TEST ACTOR"},
             norm_state_examples=state_demo, long_lead=ll,
             scenarios=[{k: s[k] for k in ("profile", "archetype", "headcount", "subcontract_capacity", "working_days", "calendar_days", "start", "finish", "peak_workers", "labour_hours", "resource_limited", "critical_path", "claim", "gaps")} |
                        {"cost": s["cost"]} for s in sc["scenarios"]], calendar=sc["calendar"], note=sc["note"])
    return sc


def stage_programme(db, ev, A, pid, sc):
    from app.services import workforce as wf
    r = wf.build_programme(db, pid, "WP-MID", allow_provisional=True, allow_unconfirmed_calendar=True)
    v = wf.save_baseline(db, A["est"], pid, "WP-MID", allow_provisional=True, allow_unconfirmed_calendar=True)
    by = {a["code"]: a for a in r["activities"]}
    gaps = [(g["code"], g["kind"]) for g in r["gaps"]]
    ok = (any(k == "MISSING_NORM" and c == "A-NDT" for c, k in gaps) and any(k == "CALENDAR_UNCONFIRMED" for _, k in gaps) and r["critical_path"]
          and r["procurement_constrained_wd"] >= r["dependency_constrained_wd"] and r["working_days"] >= r["procurement_constrained_wd"])
    ev.stage("09_resource_constrained_programme", "PASS" if ok else "FAIL", baseline_version=v, profile="WP-MID", working_days=r["working_days"], calendar_days=r["calendar_days"], start=r["start_date"], finish=r["finish_date"],
             unconstrained_activity_max_wd=r["unconstrained_project_wd"], dependency_constrained_wd=r["dependency_constrained_wd"], procurement_constrained_wd=r["procurement_constrained_wd"],
             resource_constrained_wd=r["resource_constrained_wd"], critical_path=r["critical_path"], resource_limited=r["resource_limited"], peak_workers=r["peak_workers"], labour_hours=r["labour_hours"],
             gaps=gaps, claim=r["claims"], complete=r["complete"], provisional=r["provisional"],
             activity_rows=[dict(code=a["code"], status=a["status"], hours=a["labour_hours"], crew_days=a["crew_days"], unconstrained=a["unconstrained_wd"], start=a["resource_start"], finish=a["resource_finish"],
                                 delay=a["resource_delay_wd"], float=a["total_float_wd"], critical=a["critical"]) for a in r["activities"]])
    return r


# ================================================================================================ stages 10-12
def stage_queries(db, ev, A, pid):
    from app.services import tender
    r = tender.generate_draft_queries(db, "system:detector", pid, response_due="2027-02-22")
    tender.add_query(db, A["est"], pid, register="commercial", question="Please confirm the advance payment, retention percentage and retention release terms applicable to this contract.",
                     why="Payment terms drive the cash-flow basis (document D13) and financing cost.", responsible_party="Customer (commercial)", response_due="2027-02-22",
                     impact={"assessed": False, "note": "payment terms not stated in the (fictional) ITT"}, blocks_submission=True)
    tender.add_query(db, A["est"], pid, register="design_interface", question="Who supplies and fixes the fire-water tie-in flanges at the existing ring main, and who isolates the main during tie-in?",
                     why="Interface between this package and the existing fire-water system.", responsible_party="Customer / existing-system owner", response_due="2027-02-22")
    qs = tender.list_queries(db, pid)
    by_reg = {}
    for q in qs:
        by_reg.setdefault(q["register"], []).append(q["id"])
    keys = {q["detector_key"] for q in qs if q["detector_key"]}
    need = {"AMBIG:C-013", "AMBIG:C-055", "MISSDOC:DWG-EL-010", "CONFLICT:quality plan required", "RATE:SYN-C-045", "RATE:SYN-C-046", "RATE:SYN-C-047"}
    ok = need <= keys and all(q["status"] == "Draft" for q in qs) and any(k.startswith("REV:") for k in keys) and any(k.startswith("ISSUE:") for k in keys) and any(k.startswith("LL:") for k in keys)
    # nothing can be issued while it is a draft; releasing is a person's approval and a response cannot be entered before issue
    first = qs[0]["id"]
    refused = {"issue_draft": _try(tender.mark_issued, db, A["est"], first), "response_before_issue": _try(tender.record_response, db, A["est"], first, response_text="x", response_by="y", response_date="2027-02-10")}
    ev.stage("10_queries_and_clarifications", "PASS" if ok and refused["issue_draft"] == "NOT_RELEASED" and refused["response_before_issue"] == "NOT_ISSUED" else "FAIL", created=r["created"], by_register={k: len(v) for k, v in by_reg.items()},
             detector_keys=sorted(keys), all_draft=True, refused=refused, open_material_queries=len(tender.open_material_queries(db, pid)))
    return qs


def stage_responses(db, ev, A, pid):
    from app.services import tender
    qs = {q["detector_key"]: q for q in tender.list_queries(db, pid) if q["detector_key"]}
    out = {}
    for key, (text, _) in ((k, (v, None)) for k, v in Dt.SYN_RESPONSES.items()):
        q = qs[key]
        tender.approve_to_issue(db, A["com"], q["id"], comments="TEST ACTOR: SYNTHETIC release (nothing is sent by the application)")
        tender.mark_issued(db, A["est"], q["id"])
        tender.record_response(db, A["est"], q["id"], response_text=text, response_by="SYNTHETIC customer representative (FICTIONAL)", response_date="2027-02-12", is_synthetic=True)
        out[key] = q["id"]
    # revision conflict + duplicate answered too
    rev = next(q for k, q in qs.items() if k.startswith("REV:"))
    dup = next(q for k, q in qs.items() if k.startswith("ISSUE:"))
    for q, text in ((rev, "SYNTHETIC CUSTOMER RESPONSE: revision C of DWG-PR-001 governs; it changes no BOQ quantity."),
                    (dup, "SYNTHETIC CUSTOMER RESPONSE: the second C-071 line is a BOQ error; the correct total is 14 CCTV cameras on one line.")):
        tender.approve_to_issue(db, A["com"], q["id"], comments="TEST ACTOR: SYNTHETIC release")
        tender.mark_issued(db, A["est"], q["id"])
        tender.record_response(db, A["est"], q["id"], response_text=text, response_by="SYNTHETIC customer representative (FICTIONAL)", response_date="2027-02-12", is_synthetic=True)
        out[q["detector_key"]] = q["id"]
    rows = tender.list_queries(db, pid, status="Answered")
    ev.stage("11_customer_responses", "PASS" if len(rows) == 6 and all(r["response_is_synthetic"] for r in rows) else "FAIL", answered=[(r["id"], r["detector_key"], r["response_text"][:70]) for r in rows],
             note="responses are labelled synthetic test inputs entered by a TEST ACTOR; none was generated by the application")
    return out


def stage_recalculate(db, ev, A, pid, answered):
    from app.estimators.estimate import compute_estimate
    from app.services import boq, tender
    before = compute_estimate(db, pid)
    b0 = before.direct.direct_cost_total
    ch = boq.request_quantity_change(db, A["est"], pid, "C-055", "3", "SYNTHETIC customer response: three tie-in assemblies, not two")
    boq.decide_change(db, A["com"], ch, True, comment="TEST ACTOR: SYNTHETIC")
    ch2 = boq.request_quantity_change(db, A["est"], pid, "C-071", "14", "SYNTHETIC customer response: correct total is 14 cameras on one line")
    boq.decide_change(db, A["com"], ch2, True, comment="TEST ACTOR: SYNTHETIC")
    boq.set_pricing(db, A["est"], pid, "C-071#2", "excluded", note="duplicate of C-071 per SYNTHETIC customer response; not priced twice")
    tender.register_document(db, A["est"], pid, doc_ref="DWG-EL-010", doc_type="drawing", title="Earthing layout (FICTIONAL)", revision="A", source="SYNTHETIC customer response", received_date="2027-02-12", is_synthetic=True)
    ctx = tender.context(db, pid)
    ctx["customer_requires"] = {**ctx["customer_requires"], "quality_plan": "yes"}
    tender.upsert_item(db, A["est"], pid, "tender_context", "context", ctx, source_ref="SYNTHETIC customer response to the quality-plan query", is_synthetic=True)
    after = compute_estimate(db, pid)
    delta = after.direct.direct_cost_total - b0
    expected = D(1) * D(14500) + D(2) * D(3600)                              # +1 tie-in at 14,500; +2 cameras at 3,600 (independent of the application)
    tender.set_impact(db, A["est"], answered["AMBIG:C-055"], cost_impact=str(D(14500)), time_impact_days="0", basis="recalculated estimate: +1 tie-in assembly at the synthetic installed rate")
    dupq = next(v for k, v in answered.items() if k.startswith("ISSUE:"))
    tender.set_impact(db, A["est"], dupq, cost_impact=str(D(7200)), time_impact_days="0", basis="recalculated estimate: +2 cameras on C-071; duplicate C-071#2 excluded (not priced twice)")
    for qid in answered.values():
        tender.close_query(db, A["est"], qid, "Closed after the estimate was recalculated (SYNTHETIC)")
    docs = tender.documents_report(db, pid)
    ev.stage("12_recalculate_impacts", "PASS" if delta == expected and not docs["missing"] else "FAIL", direct_before=str(b0), direct_after=str(after.direct.direct_cost_total), delta_application=str(delta),
             delta_independent=str(expected), missing_documents_after=[d["doc_ref"] for d in docs["missing"]], customer_requires=tender.context(db, pid)["customer_requires"],
             open_material_queries_remaining=[q["id"] for q in tender.open_material_queries(db, pid)])
    return after


# ================================================================================================ stage 13
def stage_procurement(db, ev, A, pid):
    from datetime import date, timedelta
    from app.core.errors import ApprovalBlocked, ValidationFailed
    from app.estimators.estimate import compute_estimate
    from app.procurement import leveling, needs, quotes, rfq, selection
    from app.services import rates, suppliers
    n = needs.detect_needs(db, A["est"], pid)
    reg = needs.register(db, pid)
    by_res = {r["resource_id"]: r for r in reg if r["reason_code"] == "MISSING_RATE"}
    pkgs = sorted({r["package_id"] for r in by_res.values()})
    assert len(pkgs) == 1, pkgs
    pkg = pkgs[0]
    sup = {k: suppliers.create_supplier(db, A["est"], name=v["name"], supplier_type="supplier", trades="E", is_synthetic=True, notes="SYNTHETIC / NOT A REAL SUPPLIER") for k, v in Dt.SUPPLIERS.items()}
    rf = rfq.create_rfq(db, A["est"], pid, pkg)
    today = date.today()
    qids = {}
    for k, v in Dt.SUPPLIERS.items():
        lines = [dict(procurement_item_id=by_res[rid]["id"], description=by_res[rid]["description"] + " (SYNTHETIC)", unit=by_res[rid]["unit"], quantity=str(Dt.QUOTE_QTY[rid]), unit_rate=rate,
                      delivery_included=v["delivery_included"], unloading_included="Unknown", installation_included="No", tax_included="Unknown", compliance="Compliant") for rid, rate in v["rates"].items()]
        qids[k] = quotes.create_quotation(db, A["est"], supplier_id=sup[k], project_id=pid, package_id=pkg, reference=f"SYNTHETIC-{k}-001", quote_date=today.isoformat(),
                                          valid_until=(today + timedelta(days=v["valid_days"])).isoformat(), tax_treatment="excl", payment_terms="SYNTHETIC / NOT A REAL QUOTE",
                                          deviations="SYNTHETIC: tax treatment NOT verified", is_synthetic=True, lines=lines)
        quotes.submit_quotation(db, A["est"], qids[k])
        quotes.approve_quotation(db, A["proc"], qids[k], evidence="TEST ACTOR: synthetic fixture entered as stated; SYNTHETIC / NOT A REAL QUOTE")
    adj = leveling.add_adjustment(db, A["est"], qids["B"], "delivery", Dt.DELIVERY_ADJ_B, "SYNTHETIC delivery charge excluded from B's quotation, applied once at package level")
    leveling.approve_adjustment(db, A["proc"], adj, comments="TEST ACTOR: SYNTHETIC")
    lv = leveling.level_package(db, pkg)
    lv10 = leveling.level_package(db, pkg, as_of=today + timedelta(days=10))
    by_q = {next(k for k, v in qids.items() if v == q["quotation_id"]): q for q in lv["quotations"]}
    headline = {k: str(D(q["quoted_total"]).quantize(D("1"))) for k, q in by_q.items()}
    evaluated = {k: str(D(q["normalised_total"]).quantize(D("1"))) for k, q in by_q.items()}
    rec = lv["suggested_lowest_like_for_like"]
    winner = next(k for k, v in qids.items() if v == rec)
    sid = selection.propose_selection(db, A["est"], pkg, rec, "SYNTHETIC: lowest like-for-like evaluated total after the delivery adjustment")
    blocked_publish = _try(selection.publish_rates, db, A["est"], sid)
    selection.decide_selection(db, A["proc"], sid, True, "TEST ACTOR: SYNTHETIC selection approval (not a real procurement approval)")
    new_rates = selection.publish_rates(db, A["est"], sid)
    status_after_publish = [rates.get_rate(db, r)["status"] for r in new_rates]
    for r in new_rates:
        rates.approve_rate(db, A["proc"], r, comments="TEST ACTOR: SYNTHETIC")
    est = compute_estimate(db, pid)
    exp_headline = {k: str(v) for k, v in Dt.EXPECTED_QUOTE_TOTALS.items()}
    ok = (headline == exp_headline and evaluated == Dt.EXPECTED_EVALUATED and winner == "A" and min(headline, key=lambda k: int(headline[k])) == "B"
          and blocked_publish != "NOT REFUSED" and not any(e.code == "MISSING_RATE" for e in est.direct.exceptions) and est.direct.direct_cost_total == D("3407410"))
    ev.stage("13_procurement_and_quote_levelling", "PASS" if ok else "FAIL", needs=n, package=pkg, headline_totals=headline, expected_headline=exp_headline, evaluated_totals=evaluated,
             expected_evaluated=Dt.EXPECTED_EVALUATED, headline_lowest=min(headline, key=lambda k: int(headline[k])), evaluated_winner=winner,
             validity_as_of_plus_10=[(q["quotation_id"], q["validity"]) for q in lv10["quotations"]], publish_before_approval_blocked_with=blocked_publish,
             rates_status_on_publish=status_after_publish, estimate_state_after=est.state, direct_cost_after=str(est.direct.direct_cost_total))
    return est


# ================================================================================================ stage 14
def stage_commercial(db, ev, A, pid):
    from app.estimators.estimate import compute_estimate
    from app.reconciliation import engine as recon
    from app.reporting import registry
    from app.services import commercial, governed, indirects, registers, workforce as wf
    for code, cat, desc, amt in (("IND-SITE", "Site indirects", "SYNTHETIC site indirects, 6% of direct cost (eligibility base NOT yet stated)", "6"),
                                 ("IND-HO", "Home-office overhead", "SYNTHETIC home-office overhead, 3% of direct cost (eligibility base NOT yet stated)", "3")):
        indirects.add_indirect(db, A["est"], pid, code=code, category=cat, description=desc, method="percent_of_direct", amount=amt, is_synthetic=True, source="SYNTHETIC TEST ASSUMPTION - NOT COMPANY DATA")
        indirects.submit_indirect(db, A["est"], pid, code)
        indirects.approve_indirect(db, A["com"], pid, code, comments="TEST ACTOR: SYNTHETIC")
    indirects.add_indirect(db, A["est"], pid, code="IND-INS", category="Insurance", description="SYNTHETIC contract works insurance allowance (fixed)", method="fixed", amount="25000", is_synthetic=True,
                           source="SYNTHETIC TEST ASSUMPTION - NOT COMPANY DATA")
    indirects.submit_indirect(db, A["est"], pid, "IND-INS")
    indirects.approve_indirect(db, A["com"], pid, "IND-INS", comments="TEST ACTOR: SYNTHETIC")
    cfg = {"method": "markup", "markup_pct": "8", "default_tax_category": "VAT-STD", "contingency": {"pct": "4", "base": "direct_indirect"}, "risk_items": [], "rounding": {"dp": 2}}
    pol = commercial.create_policy(db, A["est"], code="POL-CLOSURE", name="SYNTHETIC policy: markup 8% on total cost, contingency 4% of direct+indirect", config=cfg, is_synthetic=True)
    commercial.submit_policy(db, A["est"], pol)
    commercial.approve_policy(db, A["com"], pol, comments="TEST ACTOR: SYNTHETIC")
    commercial.assign_policy(db, A["est"], pid, pol)
    tid = db.scalar("SELECT id FROM tax_categories WHERE code='VAT-STD'")
    commercial.approve_tax_category(db, A["com"], tid, evidence="TEST ONLY: the seeded rate is used solely as a synthetic calculation parameter - NOT a verified tax determination")
    # governed parameters: escalation, plant hire terms (crane + telehandler) - payment terms are deliberately NOT supplied yet (customer query open)
    def gp(kind, code, data, note):
        i = governed.propose(db, A["est"], kind, code, data, project_id=pid, source=Dt.SYN, basis_note=note, is_synthetic=True, submit=True)
        governed.approve(db, A["com"], i, comments="TEST ACTOR: SYNTHETIC")
    gp("escalation_profile", "ESC-35", {"name": "SYNTHETIC annual escalation", "annual_pct": "3.5", "base_date": "2027-01-01", "scope_kind": "all", "scope_cost_prefix": "", "basis": "SYNTHETIC test assumption"}, "SYNTHETIC")
    gp("plant_hire_terms", "CRANE-TERMS", {"resource_id": "SYN-C-050", "min_hire_qty": "2", "standby_qty": "1", "standby_pct_of_rate": "50", "billing_basis": "working_day", "programme_tasks": ["A-STEEL", "A-PUMP"],
                                         "mobilisation_qty": "1", "demobilisation_qty": "1"}, "SYNTHETIC hire terms (test)")
    gp("plant_hire_terms", "TELEHANDLER-TERMS", {"resource_id": "SYN-C-051", "min_hire_qty": "1", "billing_basis": "working_day", "programme_tasks": ["A-PIPE100", "A-PIPE50"]}, "SYNTHETIC hire terms (test)")
    for title, desc, p_, lo, ml, hi in (("Ground conditions in hard material", "Rock quantity may exceed the BOQ", "30", "20000", "60000", "150000"),
                                         ("Pump skid delivery delay", "Long-lead item arrives after required-on-site", "25", "0", "45000", "120000"),
                                         ("Interface with existing fire ring main", "Isolation windows not available", "20", "10000", "30000", "90000")):
        rid = registers.add_risk(db, A["est"], pid, title, description=desc, owner="Estimator (test)", mitigation="SYNTHETIC mitigation placeholder")
        registers.quantify_risk(db, A["est"], rid, prob_pct=p_, cost_low=lo, cost_likely=ml, cost_high=hi, category="Technical", basis="SYNTHETIC three-point range (test)")
    # programme -> schedule tasks (so cost can be time-phased); the baseline is still provisional
    base = wf.latest_baseline(db, pid)
    n_tasks = wf.baseline_to_schedule_tasks(db, A["est"], pid, base["version_no"])
    est = compute_estimate(db, pid)
    es = registry.run_report(db, "escalation", pid, {})
    ib = registry.run_report(db, "indirect_base", pid, {})
    ph = registry.run_report(db, "plant_hire", pid, {})
    try:
        cf = registry.run_report(db, "cashflow", pid, {})
        cf_state = cf.get("status")
    except Exception as e:                       # noqa: BLE001
        cf_state = f"{getattr(e, 'code', type(e).__name__)}: {str(e)[:120]}"
    run = recon.run_reconciliation(db, A["est"], pid)
    f = recon.get_run(db, run["run_id"])["findings"]
    codes = sorted({(x["severity"], x["rule_code"]) for x in f})
    t = est.totals()
    # independent commercial chain (separate formulas). Tax is charged on the TENDERED pricing schedule (sum of the printed line amounts), not on the commercial net price.
    Dd = est.direct.direct_cost_total
    ind = est.indirect.total
    cont = r2((Dd + ind) * D("0.04"))
    total_cost = Dd + ind + cont
    net = r2(total_cost * D("1.08"))
    sched_total = sum((D(str(l.amount)) for l in est.schedule.lines if l.amount is not None), D(0)) + sum((D(str(x["amount"])) for x in est.schedule.separate_lines if x.get("amount") is not None), D(0))
    lines_ok = all(abs(l.amount - l.quantity * l.unit_rate) <= D("0.01") * max(D(1), l.quantity) for l in est.schedule.lines if l.amount is not None and l.unit_rate is not None)
    vat = r2(sched_total * D("0.15"))
    variance = sched_total - net
    markup_on_cost = (net - total_cost) / total_cost
    margin_on_price = (net - total_cost) / net                                          # markup and margin are different numbers: 8 % on cost is 7.41 % on price
    chain_ok = (abs(markup_on_cost - D("0.08")) < D("0.0000001") and abs(margin_on_price - D("0.08") / D("1.08")) < D("0.0000001") and r2(t["total_cost"]) == r2(total_cost) and r2(t["commercial_net_price"]) == net and r2(t["selling_price_pre_tax"]) == r2(sched_total) and r2(t["tax"]) == vat
                and r2(t["final_payable"]) == r2(sched_total) + vat and abs(variance) <= est.schedule.max_rounding_variance + D("0.01"))
    # independent percent-indirect: 9% of the whole direct cost (nothing excluded: base unspecified) + 25,000 fixed
    ind_expected = r2(Dd * D("0.09")) + D(25000)
    need = {"INDIRECT_ELIGIBILITY_UNSPECIFIED", "PLANT_HIRE_DAYS"}
    have = {c for _, c in codes}
    ev.stage("14_indirects_tax_risk_escalation_cashflow", "PASS" if need <= have and chain_ok and lines_ok and abs(ind - ind_expected) <= D("0.05") else "FAIL",
             totals={k: str(v) for k, v in t.items()}, independent=dict(indirect=str(ind_expected), contingency=str(cont), total_cost=str(total_cost), net=str(net), schedule_total=str(r2(sched_total)), vat=str(vat), payable=str(r2(sched_total) + vat),
                              schedule_vs_net_variance=str(r2(variance)), markup_on_cost=str(markup_on_cost.quantize(D('0.000001'))), margin_on_price=str(margin_on_price.quantize(D('0.000001'))), max_rounding_variance_allowed=str(est.schedule.max_rounding_variance)),
             indirect_application=str(ind), findings=codes, schedule_tasks=n_tasks, escalation_status=es.get("status"), escalation_complete=es.get("complete"),
             unescalated_cost=es.get("unescalated_eligible_cost"), indirect_base=dict(ib) if isinstance(ib, dict) else None, plant_hire_findings=[x for x in f if x["rule_code"] == "PLANT_HIRE_DAYS"][:3],
             cashflow=cf_state, estimate_state=est.state)
    return est, f


# ================================================================================================ stages 15-18
def stage_methodology(db, ev, A, pid):
    from app.services import tender, workforce as wf
    acts = wf.list_activities(db, pid)
    prog = wf.latest_baseline(db, pid)["result"]
    topics = {
        "wbs": f"Work breakdown: {len(acts)} activities grouped by BOQ trade (civil, structural, piping, mechanical, electrical, ELV, commissioning).",
        "sequence": "Execution sequence follows the programme dependencies: mobilisation, excavation, pipe-rack foundations, steel, support fabrication, piping, welding, NDT, hydrotest, backfill/coating, E&I, commissioning, demobilisation.",
        "work_fronts": f"Work fronts per activity are limited to the values entered on the activities (maximum {max(a['work_fronts'] for a in acts)}).",
        "plant": "One mobile crane serves steel erection and pump-skid setting; a telehandler serves pipe installation (hire terms in the plant exposure report).",
        "workforce": f"Selected profile {prog['profile']['name']}: peak direct manpower {prog['peak_workers']}.",
        "procurement": "Pump skids are a long-lead item; procurement-constrained dates are shown in the programme.",
        "inspection": "Hold points follow the ITP register; NDT sample size is subject to the compliance deviation D-1.",
        "interfaces": "The fire-water tie-in is an interface with the existing ring main owned by the customer.",
        "risks": "Programme risks: hard-material excavation, pump skid delay, tie-in isolation windows (see the risk register).",
        "temporary_works": "Temporary works: trench shoring (BOQ C-012) and scaffolding access hire (BOQ C-052); design of temporary works is by a competent engineer (not generated here).",
        "access": "Access and working windows follow the project calendar (shutdown and reduced-hour windows are shown in D19); the customer's site access rules are a recorded required input.",
        "testing_commissioning": "Hydrotest and flushing are a fixed 8-day activity, commissioning a fixed 10-day activity after coating, cable and fibre completion.",
        "hse_interfaces": "HSE interfaces: hot-work and excavation permits (permit register), tie-in isolation with the existing ring main (interface register).",
        "constraints": "Constraints and exclusions: see D09; unverified norms and the synthetic basis are listed in D37."}
    for k, v in topics.items():
        tender.upsert_item(db, A["est"], pid, "execution_review", k, dict(topic=k.replace("_", " ").title(), content=v), source_ref="programme baseline / registers", is_synthetic=True)
    for k, t in {"scope": "Scope and objectives", "org": "Organisation and responsibilities", "ncr": "Nonconformance handling", "records": "Records and documentation control"}.items():
        tender.upsert_item(db, A["est"], pid, "quality_plan", k, dict(topic=t, content=tender.TODO), source_ref="customer quality requirement (conflict resolved by response)", is_synthetic=True)
    for k, row in {"fire-tie-in": dict(interface="Fire-water tie-in to existing ring main", parties="Contractor / customer / existing-system owner", responsibility="Customer provides tie-in flanges; contractor supplies and installs three tie-in assemblies (per synthetic response)"),
                   "power": dict(interface="LV supply point for the new distribution boards", parties="Contractor / customer", responsibility="Customer provides the incomer; contractor terminates")}.items():
        tender.upsert_item(db, A["est"], pid, "interface", k, row, source_ref="synthetic customer response", is_synthetic=True)
    tender.upsert_item(db, A["est"], pid, "permit", "hot-work", dict(permit="Hot-work permit", authority="Customer HSE (fictional)", needed_before="Start of welding"), is_synthetic=True)
    tender.upsert_item(db, A["est"], pid, "permit", "excavation", dict(permit="Excavation permit", authority="Customer HSE (fictional)", needed_before="Start of trench excavation"), is_synthetic=True)
    tender.upsert_item(db, A["est"], pid, "handover_obligation", "oam", dict(obligation="O&M manuals and as-built records at completion", source="COND-001 (FICTIONAL)", owner="Project manager (to be named)"), is_synthetic=True)
    tender.upsert_item(db, A["est"], pid, "procurement_strategy", "pump", dict(package="Pump skids (E.08)", approach="Supply-only purchase order with early order date", rationale="Long-lead item"), is_synthetic=True)
    tender.upsert_item(db, A["est"], pid, "supplier_qualification", "A", dict(supplier="SYNTHETIC Supplier A (fictional)", status="Not qualified (test)", basis="No qualification evidence supplied"), is_synthetic=True)
    sk = tender.skeleton_registers(db, A["est"], pid)
    tender.upsert_item(db, A["est"], pid, "deviation", "D-1", dict(requirement_ref="SPEC-PIPE-001", deviation="Radiography is priced on a 130-joint sample (about 20% of 640 joints), not 100%",
                                                                  justification="SYNTHETIC: sample basis assumed pending clarification; 100% would add cost and time"), source_ref="SPEC-PIPE-001", is_synthetic=True)
    for k in ("SPEC-PIPE-001", "SPEC-ST-001", "SPEC-EL-001"):
        row = next(i for i in tender.list_items(db, pid, "compliance") if i["item_key"] == k)
        if k == "SPEC-PIPE-001":
            tender.upsert_item(db, A["est"], pid, "compliance", k, {**row["data"], "response": "Complies except radiography extent (deviation D-1)", "evidence": "SYNTHETIC statement - not read against the clauses by a person"}, source_ref=k, is_synthetic=True)
    items = tender.list_items(db, pid)
    reg = {}
    for i in items:
        reg[i["register"]] = reg.get(i["register"], 0) + 1
    todo = sum(1 for i in items if tender.TODO in json.dumps(i["data"]))
    ev.stage("15_methodology_and_compliance", "PASS" if reg.get("compliance", 0) >= 3 and reg.get("itp") == len(acts) and todo > 0 else "FAIL", skeleton=sk, register_counts=reg, rows_with_placeholders=todo,
             note="skeleton rows carry 'TO BE COMPLETED BY A COMPETENT PERSON' placeholders: the system does not write inspection criteria, HSE controls or compliance statements")


def stage_matrix(db, ev, A, pid):
    from app.tender import catalogue
    m = catalogue.matrix(db, pid)
    by = {r["code"]: r for r in m["rows"]}
    ok = (by["D13"]["applicability"] == catalogue.MCR and by["D44"]["applicability"] == catalogue.NA and by["D27"]["applicability"] == catalogue.REQ and by["D16"]["applicability"] == catalogue.REQ
          and m["counts"][catalogue.MCR] >= 1 and sum(m["counts"].values()) == 45)
    ev.stage("16_applicability_matrix", "PASS" if ok else "FAIL", counts=m["counts"], inputs=m["inputs"], not_required=[(r["code"], r["reason"]) for r in m["rows"] if r["applicability"] == catalogue.NA],
             missing_customer_requirement=[(r["code"], r["reason"]) for r in m["rows"] if r["applicability"] == catalogue.MCR], conditional=[r["code"] for r in m["rows"] if r["applicability"] == catalogue.COND])
    return m


def stage_pack1(db, ev, A, pid, out_root):
    from app.services import estimates
    from app.tender import packs
    vid = estimates.freeze_version(db, A["est"], pid, "closure-v1", "SYNTHETIC: frozen before the open items are resolved")
    r = packs.generate_pack(db, A["est"], pid, out_root=out_root, issue_date=Dt.ISSUE_DATE, version_id=vid)
    by = {d["code"]: d for d in r["documents"]}
    ev["_vid1"], ev["_pack1"] = vid, r
    ok = (r["classification"] == "demonstration" and not r["production_ready"] and by["D13"]["status"] == "BLOCKED" and all(d["status"] != "Approved for Submission" for d in r["documents"]))
    ev.stage("17_generate_document_pack", "PASS" if ok else "FAIL", pack_revision=r["revision"], out_dir=r["out_dir"], classification=r["classification"], banner=r["banner"], counts=r["counts"],
             statuses={k: sum(1 for d in r["documents"] if d["status"] == k) for k in sorted({d["status"] for d in r["documents"]})}, blocked={d["code"]: d["blocked_reason"] for d in r["documents"] if d["status"] == "BLOCKED"},
             files=sum(len(d["files"]) for d in r["documents"]))
    return r


def stage_validate1(db, ev, A, pid, r1):
    from app.tender import packs
    v = packs.validate_pack(db, r1["pack_pk"])
    ev.stage("18_validate_document_pack", "PASS" if v["ok"] and v["files_checked"] > 60 else "FAIL", ok=v["ok"], errors=v["errors"][:12], warnings=v["warnings"][:6], blocked_documents=v["blocked_documents"],
             documents=v["documents"], files_checked=v["files_checked"], facts_checked=v["facts_checked"])
    return v


# ================================================================================================ stage 19-20 (negative controls)
def stage_production_blocked(db, ev, A, pid, out_root):
    from app.approvals import engine as ap
    from app.config import get_settings
    from app.core.errors import AppError, ApprovalBlocked
    from app.models.actor import Actor
    from app.services import estimates, projects, readiness
    vid = ev["_vid1"]
    r = readiness.evaluate(db, pid, vid, None)
    s = get_settings()
    s.environment = "production"
    try:
        prod = readiness.evaluate(db, pid, vid, None)
    finally:
        s.environment = "test"
    # a REAL (non-demonstration) project: test actors cannot approve or export in a production environment
    rp = projects.create_project(db, A["est"], name="Real-project negative control (SYNTHETIC content)", client="SYNTHETIC CLIENT", id="PRJ-9102", is_demo=False, tax_category="VAT-STD")
    rv = estimates.freeze_version(db, A["est"], rp, "negative control")
    estimates.submit_version(db, A["est"], rv)
    s.environment = "production"
    try:
        attempts = {}
        for label, fn in (("approve_version", lambda: estimates.approve_version(db, A["com"], rv)), ("approve_tender_export", lambda: estimates.approve_tender_export(db, A["com"], rp, rv)),
                          ("export_submission", lambda: estimates.export_submission(db, A["est"], rp, rv, 1))):
            try:
                fn()
                attempts[label] = "NOT REFUSED (defect)"
            except AppError as e:
                attempts[label] = e.code
        from app.tender import packs
        try:
            packs.approve_document(db, A["com"], rp, f"{rp}-D16")
            attempts["approve_document"] = "NOT REFUSED (defect)"
        except AppError as e:
            attempts["approve_document"] = e.code
    finally:
        s.environment = "test"
    kinds = dict(forged_display_name=ap.resolve_actor_type(db, Actor("forged-human", "Commercial Approver", "Real Human Commercial Approver (identity verified)")),
                 role_mismatch=ap.resolve_actor_type(db, Actor("test-estimator", "Commercial Approver", "claims another role")), registered_test_actor=ap.resolve_actor_type(db, A["com"]),
                 unregistered=ap.resolve_actor_type(db, Actor("nobody", "Estimator")))
    attempts["export_submission_without_export_approval (demo project)"] = _try(estimates.export_submission, db, A["est"], pid, vid, 999)
    exp = None
    sub_ready = db.scalar("SELECT COUNT(*) FROM exports WHERE submission_ready=1")
    ok = (not r["production_ready"] and not prod["production_ready"] and r["classification"] == "demonstration" and all(v != "human" for v in kinds.values())
          and all(v in ("NON_HUMAN_ACTOR", "EXPORT_NOT_APPROVED", "NOT_PRODUCTION_READY") for v in attempts.values()) and sub_ready == 0)
    ev.stage("19_production_readiness_blocked", "PASS" if ok else "FAIL", classification_in_test_environment=r["classification"], reasons=r["reasons"][:14], classification_if_production_environment=prod["classification"],
             structural_reasons=prod["structural"], real_project_attempts_in_production_env=attempts, resolved_actor_types=kinds,              exports_marked_submission_ready=sub_ready, pack_classification=ev["17_generate_document_pack"]["classification"])


def stage_assumption_bypass(db, ev, A, pid, workdir):
    import sqlite3
    from fastapi.testclient import TestClient
    from app.core.errors import AppError
    from app.main import app
    from app.models.actor import Actor
    from app.services import assumptions, auth
    res = {}
    assumptions.create_assumption(db, A["est"], id="ASMP-Z-090", family="I", name="Bypass probe: validity days", value_type="number", default_value="45", unit="day", source="SYNTHETIC", category="Commercial terms and payment",
                                  is_synthetic=True, reason="negative test")
    assumptions.submit_assumption(db, A["est"], "ASMP-Z-090")
    res["author_self_approval"] = _try(assumptions.approve_assumption, db, A["est"], "ASMP-Z-090")
    admin_probe = Actor("test-admin", "Administrator", "TEST ACTOR Admin")
    assumptions.create_assumption(db, admin_probe, id="ASMP-Z-091", family="I", name="Bypass probe 2", value_type="number", default_value="9", source="SYNTHETIC", is_synthetic=True)
    assumptions.submit_assumption(db, admin_probe, "ASMP-Z-091")
    res["administrator_self_approval"] = _try(assumptions.approve_assumption, db, admin_probe, "ASMP-Z-091")
    res["viewer_approval"] = _try(assumptions.approve_assumption, db, A["view"], "ASMP-Z-090")
    res["ai_approval"] = _try(assumptions.approve_assumption, db, Actor("ai-assistant", "AI Assistant", "AI", is_ai=True), "ASMP-Z-090")
    res["ai_creates_register_row"] = _try(assumptions.create_assumption, db, Actor("ai-assistant", "AI Assistant", "AI", is_ai=True), id="ASMP-Z-092", family="I", name="x")
    res["manual_entry_is_not_approval"] = db.scalar("SELECT status FROM assumptions WHERE id='ASMP-Z-090'")
    assumptions.approve_assumption(db, A["com"], "ASMP-Z-090", comments="TEST ACTOR: SYNTHETIC")
    res["approved_by_a_second_person"] = db.scalar("SELECT approved_by FROM assumptions WHERE id='ASMP-Z-090'")
    res["service_revision_creates_new_version"] = assumptions.revise_assumption(db, A["est"], "ASMP-Z-090", default_value="60")
    res["v1_after_revision"] = [db.scalar("SELECT default_value FROM assumptions WHERE id='ASMP-Z-090' AND version=1"), db.scalar("SELECT status FROM assumptions WHERE id='ASMP-Z-090' AND version=1")]
    res["sql_update_of_approved_value"] = _try(db.execute, "UPDATE assumptions SET default_value='1' WHERE id='ASMP-Z-090' AND version=1")
    res["sql_delete_of_approved"] = _try(db.execute, "DELETE FROM assumptions WHERE id='ASMP-Z-090' AND version=1")
    res["sql_replace_provenance"] = _try(db.execute, "UPDATE assumptions SET approved_by='someone-else', source='forged' WHERE id='ASMP-Z-090' AND version=1")
    res["sql_make_synthetic_look_real"] = _try(db.execute, "UPDATE assumptions SET is_synthetic=0 WHERE id='ASMP-Z-090' AND version=1")
    forged = Actor("forged-commercial", "Commercial Approver", "Real Commercial Approver")
    assumptions.submit_assumption(db, A["est"], "ASMP-Z-090")
    assumptions.approve_assumption(db, forged, "ASMP-Z-090", comments="forged identity (nobody registered under this username)")
    ap = db.one("SELECT reviewer, actor_type, environment FROM approvals WHERE entity_type='assumption' AND entity_id='ASMP-Z-090' ORDER BY id DESC LIMIT 1")
    res["forged_identity_recorded_as"] = dict(ap)
    from app.services import readiness
    row = db.one("SELECT * FROM approvals WHERE entity_type='assumption' AND entity_id='ASMP-Z-090' ORDER BY id DESC LIMIT 1")
    probs, _ = readiness.check_approval(db, row, "assumption", entity_type="assumption", entity_id="ASMP-Z-090")
    res["forged_approval_counts_for_production"] = not probs
    # REST API and CLI: identity comes from the authenticated user, never from a field in the request
    for u, role in (("api-est", "Estimator"), ("api-view", "Viewer"), ("api-com", "Commercial Approver")):
        if not db.one("SELECT 1 FROM users WHERE username=?", (u,)):
            auth.create_user(db, u, f"TEST ACTOR {u}", role, "pw-" + u, actor_type="test")
    api = {}
    with TestClient(app, headers={"Origin": "http://testserver"}) as c:
        def tok(u):
            r = c.post("/api/auth/login", json={"username": u, "password": "pw-" + u})
            c.cookies.clear()
            return {"Authorization": "Bearer " + r.json()["token"]}
        he = tok("api-est")
        r = c.post("/api/actions/create_assumption", json={"id": "ASMP-Z-093", "family": "I", "name": "API probe", "value_type": "number", "default_value": "5", "is_synthetic": True, "category": "Commercial terms and payment"}, headers=he)
        api["create"] = r.status_code
        c.post("/api/actions/submit_assumption", json={"id": "ASMP-Z-093"}, headers=he)
        r = c.post("/api/actions/approve_assumption", json={"id": "ASMP-Z-093"}, headers=he)
        api["estimator_cannot_approve"] = (r.status_code, r.json().get("error"))
        r = c.post("/api/actions/approve_assumption", json={"id": "ASMP-Z-093", "reviewer": "test-commercial", "actor": "test-commercial"}, headers=he)
        api["body_field_cannot_forge_identity"] = (r.status_code, r.json().get("error"))
        r = c.post("/api/actions/approve_assumption", json={"id": "ASMP-Z-093"}, headers=tok("api-view"))
        api["viewer_cannot_approve"] = (r.status_code, r.json().get("error"))
        r = c.post("/api/actions/create_assumption", json={"id": "ASMP-Z-094", "family": "I", "name": "x"}, headers=tok("api-view"))
        api["viewer_cannot_create"] = (r.status_code, r.json().get("error"))
        r = c.post("/api/actions/approve_assumption", json={"id": "ASMP-Z-093"}, headers=tok("api-com"))
        api["commercial_approves"] = r.status_code
        r = c.post("/api/actions/approve_assumption", json={"id": "ASMP-Z-093"})
        api["no_token"] = r.status_code
    res["api"] = api
    cli = [_cli(workdir, "action", "approve_assumption", json.dumps({"id": "ASMP-Z-090"}), user="api-view"), _cli(workdir, "action", "approve_assumption", json.dumps({"id": "ASMP-Z-090"}), user="ghost")]
    res["cli"] = [dict(cmd=x["cmd"], exit=x["exit"], err=(x["stderr"] or x["full"])[-160:]) for x in cli]
    refused = [v for k, v in res.items() if k in ("author_self_approval", "administrator_self_approval", "viewer_approval", "ai_approval", "ai_creates_register_row")]
    ok = (all(v not in ("NOT REFUSED",) for v in refused) and res["author_self_approval"] == "SELF_APPROVAL_BLOCKED" and res["administrator_self_approval"] == "SELF_APPROVAL_BLOCKED"
          and res["manual_entry_is_not_approval"] == "Pending Review" and res["v1_after_revision"] == ["45", "Approved"]
          and all("IMMUTABLE_RECORD" in res[k] for k in ("sql_update_of_approved_value", "sql_delete_of_approved", "sql_replace_provenance", "sql_make_synthetic_look_real"))
          and res["forged_identity_recorded_as"]["actor_type"] == "unregistered" and res["forged_approval_counts_for_production"] is False
          and api["estimator_cannot_approve"][0] in (403, 409) and api["body_field_cannot_forge_identity"][0] in (403, 409) and api["viewer_cannot_approve"][0] == 403
          and api["viewer_cannot_create"][0] == 403 and api["commercial_approves"] == 200 and api["no_token"] in (401, 403) and all(x["exit"] != 0 for x in cli))
    ev.stage("20_assumption_bypass_blocked", "PASS" if ok else "FAIL", **res)


def _cli(workdir: Path, *args: str, user: str | None = None, timeout: int = 300) -> dict:
    import os
    import subprocess
    import sys
    env = {**os.environ, "KSA_DB_PATH": str(Path(workdir) / "scratch_closure.db"), "KSA_WORKSPACES_DIR": str(Path(workdir) / "workspaces"), "KSA_SECRET_KEY": "synthetic-closure",
           "KSA_ENVIRONMENT": "test", "KSA_ALLOW_SELF_APPROVAL": "false"}
    if user:
        env.update(KSA_CLI_USER=user, KSA_CLI_PASSWORD="pw-" + user)
    cp = subprocess.run([sys.executable, "-m", "app.cli", *args], cwd=Path(__file__).resolve().parents[2], env=env, capture_output=True, text=True, timeout=timeout)
    return dict(cmd="python -m app.cli " + " ".join(args)[:140], exit=cp.returncode, stdout=cp.stdout[-1500:], stderr=cp.stderr[-600:], full=cp.stdout)


# ================================================================================================ stage 21
def stage_resolve(db, ev, A, pid, out_root):
    from app.estimators.estimate import compute_estimate
    from app.reconciliation import engine as recon
    from app.reporting import registry
    from app.services import bids, boq, estimates, governed, indirects, offers, registers, tender, workforce as wf
    from app.api.serializers import ser
    facts = {}
    # --- remaining queries: commercial + interface answered; supplier/long-lead queries closed by the actions that resolved them
    for q in tender.list_queries(db, pid):
        if q["status"] != "Draft":
            continue
        if q["register"] in ("commercial", "design_interface"):
            tender.approve_to_issue(db, A["com"], q["id"], comments="TEST ACTOR: SYNTHETIC release")
            tender.mark_issued(db, A["est"], q["id"])
            text = ("SYNTHETIC CUSTOMER RESPONSE: advance 10%, retention 5% (50% released at completion, balance after a 12-month defects period), payment 1 month after certification; performance bond 10%." if q["register"] == "commercial"
                    else "SYNTHETIC CUSTOMER RESPONSE: the customer supplies the tie-in flanges and isolates the ring main; the contractor supplies and installs the tie-in assemblies.")
            tender.record_response(db, A["est"], q["id"], response_text=text, response_by="SYNTHETIC customer representative (FICTIONAL)", response_date="2027-02-14", is_synthetic=True)
            tender.close_query(db, A["est"], q["id"], "Closed after the response was applied (SYNTHETIC)")
        else:
            tender.close_query(db, A["est"], q["id"], "Withdrawn: resolved inside the estimating workflow (quotation levelling / long-lead update / norm approval)", withdraw=True)
    facts["open_material_queries"] = [q["id"] for q in tender.open_material_queries(db, pid)]
    # --- payment terms from the customer's answer
    gp = lambda kind, code, data, note: governed.approve(db, A["com"], governed.propose(db, A["est"], kind, code, data, project_id=pid, source=Dt.SYN, basis_note=note, is_synthetic=True, submit=True), comments="TEST ACTOR: SYNTHETIC")   # noqa: E731
    gp("payment_terms", "PAY-CLOSURE", {"name": "SYNTHETIC payment terms (from the synthetic customer response)", "advance_pct": "10", "retention_pct": "5", "retention_release_at_completion_pct": "50", "defects_months": "12",
                                        "certification_lag_months": "1", "payment_lag_months": "1", "supplier_payment_lag_months": "1", "financing_rate_annual_pct": "9", "performance_bond_pct": "10",
                                        "performance_bond_fee_annual_pct": "1.5"}, "SYNTHETIC")
    # --- cost with no time allocation: INCOMPLETE and blocking BEFORE the rules, reconciled AFTER (supervision, temporary facilities, HSE, plant, scaffolding)
    def snap():
        cf = ser(registry.run_report(db, "cashflow", pid, {}))
        es = ser(registry.run_report(db, "escalation", pid, {}))
        return cf, es
    cf0, es0 = snap()
    gate0 = recon.final_gate(db, A["com"], pid)
    from app.core.errors import ValidationFailed
    from app.services import cashflow
    refused = _try(cashflow.propose_financing_indirects, db, A["est"], pid)
    rules = [("TA-SUP", {"name": "Site management over the whole programme", "scope_cost_prefix": "A.02", "tasks": ["ALL"], "basis": "SYNTHETIC: supervision runs for the whole programme"}),
             ("TA-TEMP", {"name": "Temporary facilities over the whole programme", "scope_cost_prefix": "A.03", "tasks": ["ALL"], "basis": "SYNTHETIC: temporary facilities are on site throughout"}),
             ("TA-HSE", {"name": "HSE provisions over the whole programme", "scope_cost_prefix": "A.04", "tasks": ["ALL"], "basis": "SYNTHETIC: HSE provisions run throughout"}),
             ("TA-PLANT", {"name": "Crane, telehandler and scaffolding on erection and piping", "scope_cost_prefix": "A.05", "tasks": ["A-STEEL", "A-PUMP", "A-PIPE100", "A-PIPE50", "A-WELD"],
                           "shares": {"A-STEEL": "30", "A-PUMP": "10", "A-PIPE100": "30", "A-PIPE50": "15", "A-WELD": "15"}, "basis": "SYNTHETIC: plant is used on these activities in these shares"})]
    for code, data in rules:
        gp("time_allocation", code, data, "SYNTHETIC")
    cf1, es1 = snap()
    first_batch = dict(cashflow_status=cf1["status"], unallocated_lines=[(u["item_key"], u["amount"]) for u in cf1["unallocated_lines"]], unallocated_direct_cost=cf1["unscheduled_cost"])
    # the report names exactly what is still untied: the person adds explicit rules (or ties an activity to the cost code) for it - nothing is spread silently
    for code, data in [("TA-ANCHOR", {"name": "Anchor bolts and base plates with steel erection", "scope_cost_prefix": "C.05", "tasks": ["A-STEEL"], "basis": "SYNTHETIC: installed with the steel"}),
                       ("TA-BACKFILL", {"name": "Backfill after hydrotest", "scope_cost_prefix": "B.03", "tasks": ["A-BACK"], "basis": "SYNTHETIC: backfill happens in the backfill activity"}),
                       ("TA-FIRE", {"name": "Fire-water tie-ins and hydrants during hydrotest and commissioning", "scope_cost_prefix": "G", "tasks": ["A-HYDRO", "A-COMM"], "shares": {"A-HYDRO": "50", "A-COMM": "50"}, "basis": "SYNTHETIC"}),
                       ("TA-ELV", {"name": "CCTV and access control during fibre works and commissioning", "scope_cost_prefix": "I", "tasks": ["A-ELV", "A-COMM"], "basis": "SYNTHETIC: weighted by duration"})]:
        gp("time_allocation", code, data, "SYNTHETIC")
        rules.append((code, data))
    cf1, es1 = snap()
    facts["time_allocation"] = dict(first_batch=first_batch, before=dict(cashflow_status=cf0["status"], unallocated_direct_cost=cf0["unscheduled_cost"], escalation_status=es0["status"], unescalated_cost=es0["unescalated_eligible_cost"],
                                                financing_refused_with=refused, final_gate_blocked_by_it=any(b["rule_code"] == "TIMEPHASING_INCOMPLETE" for b in gate0["blockers"]), closing_balance=cf0["final_balance"]),
                                    after=dict(cashflow_status=cf1["status"], complete=cf1["complete"], reconciliation_checks_ok=all(c["ok"] for c in cf1["reconciliation"]["checks"]),
                                               escalation_complete=es1["complete"], escalation_total=es1["escalation_total"], closing_balance=cf1["final_balance"], peak_funding=cf1.get("peak_funding")))
    # --- programme: confirmed calendar, the missing NDT norm, an earlier order date, re-baseline
    _calendar(db, A, pid, confirmed=True)
    wf.create_norm(db, A["est"], id=Dt.NDT_NORM[0], trade=Dt.NDT_NORM[1], activity=Dt.NDT_NORM[2], output_unit=Dt.NDT_NORM[3], basis=Dt.NDT_NORM[4], value=Dt.NDT_NORM[5], crew=Dt.NDT_NORM[6], source=Dt.SYN, evidence="SYNTHETIC fixture value",
                   effective_from="2027-01-01", is_synthetic=True)
    wf.submit_norm(db, A["est"], Dt.NDT_NORM[0])
    wf.approve_norm(db, A["com"], Dt.NDT_NORM[0], comments="TEST ACTOR: SYNTHETIC")
    ll = db.one("SELECT id FROM long_lead_items WHERE project_id=?", (pid,))["id"]
    bids.update_long_lead(db, A["est"], ll, planned_order_date="2027-02-21")
    acts = [dict(code=c, name=n, boq_item_key=b, norm_id=(Dt.NDT_NORM[0] if c == "A-NDT" else nm), crews=cr, work_fronts=fr, fixed_days=fx, predecessors=pr, cost_code=cc, long_lead_id=ll if c == "A-PUMP" else None)
            for c, n, b, nm, cr, fr, fx, pr, cc in Dt.ACTIVITIES]
    wf.set_activities(db, A["est"], pid, acts)
    v2 = wf.save_baseline(db, A["est"], pid, "WP-MID")
    wf.approve_baseline(db, A["com"], pid, v2, comments="TEST ACTOR: SYNTHETIC programme baseline approval")
    wf.baseline_to_schedule_tasks(db, A["est"], pid, v2)
    prog = wf.latest_baseline(db, pid, approved_only=True)["result"]
    facts["programme"] = dict(version=v2, working_days=prog["working_days"], calendar_days=prog["calendar_days"], finish=prog["finish_date"], gaps=[(g["code"], g["kind"]) for g in prog["gaps"] if g["kind"] != "NORM_EVIDENCE_SYNTHETIC"],
                              claim=prog["claims"], synthetic=prog["synthetic"], complete=prog["complete"])
    # --- plant: the telehandler is re-priced to the programme window (change request), the crane exception is accepted by the Commercial Approver, scaffolding gets hire terms
    ph = registry.run_report(db, "plant_hire", pid, {})
    for row in ph["plant"] if "plant" in ph else ph.get("terms", []):
        pass
    rows = [r for k, v in ph.items() if isinstance(v, list) for r in v if isinstance(r, dict) and r.get("resource_id")]
    need = {r["resource_id"]: r for r in rows}
    ch = boq.request_quantity_change(db, A["est"], pid, "C-051", str(need["SYN-C-051"]["required_billable_days"]), "SYNTHETIC: re-priced to the programme hire window read from the approved baseline")
    boq.decide_change(db, A["com"], ch, True, comment="TEST ACTOR: SYNTHETIC")
    gp("plant_hire_terms", "SCAFFOLD-TERMS", {"resource_id": "SYN-C-052", "min_hire_qty": "1", "billing_basis": "calendar_day", "programme_tasks": ["A-STEEL", "A-PIPE100", "A-PIPE50", "A-WELD"]}, "SYNTHETIC hire terms (test)")
    # --- BOQ discrepancy, exclusion, indirect eligibility
    boq.acknowledge_issues(db, A["com"], pid, "C-071#2", "SYNTHETIC: duplicate line identified; excluded from pricing per the customer response")
    sid = registers.add_scope_entry(db, A["est"], pid, "exclusion", "BOQ line C-071#2 (duplicate of C-071) is not priced", boq_item_key="C-071#2", rationale="SYNTHETIC customer response: duplicate BOQ line")
    registers.approve_scope_entry(db, A["com"], sid, comments="TEST ACTOR: SYNTHETIC")
    for code in ("IND-SITE", "IND-HO"):
        indirects.revise_indirect(db, A["est"], pid, code, eligibility=Dt.INDIRECT_ELIGIBILITY, description=f"SYNTHETIC {code}: eligibility base now stated (division A and plant excluded; B,C,E,G,H,I included)")
        indirects.submit_indirect(db, A["est"], pid, code)
        indirects.approve_indirect(db, A["com"], pid, code, comments="TEST ACTOR: SYNTHETIC")
    # --- remaining register content + the letter of offer
    tender.upsert_item(db, A["est"], pid, "submittal_shop", "SH-1", dict(item="Pipe-rack steel shop drawings", drawing_ref="DWG-ST-002", required_by="Before fabrication"), is_synthetic=True)
    o = offers.generate_offer(db, A["est"], pid, payment_terms="SYNTHETIC terms per the synthetic customer response")
    offers.approve_offer(db, A["com"], pid, o["version_no"])
    from app.procurement import needs as _needs
    _needs.detect_needs(db, A["est"], pid)   # re-detect so needs satisfied by the approved quotations close
    # --- reconciliation: remaining High findings are accepted as recorded exceptions by the Commercial Approver (test actor); Critical ones must be resolved
    run = recon.run_reconciliation(db, A["est"], pid)
    fnd = recon.get_run(db, run["run_id"])["findings"]
    crit = [(x["rule_code"], x["entity_id"]) for x in fnd if x["severity"] == "Critical" and x["status"] == "Open"]
    accepted = []
    for x in fnd:
        if x["status"] == "Open" and x["severity"] == "High" and x["rule_code"] not in ("TIMEPHASING_INCOMPLETE", "INDIRECT_BASE_OVERLAP"):
            recon.accept_exception(db, A["com"], x["id"], f"SYNTHETIC / TEST ACTOR exception: {x['rule_code']} on {x['entity_id']} accepted to complete the demonstration workflow")
            accepted.append((x["rule_code"], x["entity_id"]))
    gate = recon.final_gate(db, A["com"], pid)
    est = compute_estimate(db, pid)
    facts.update(critical_open=crit, exceptions_accepted=accepted, gate_blocked=gate["blocked"], blockers=[(b["rule_code"], b["entity_id"]) for b in gate["blockers"]], estimate_state=est.state, totals={k: str(v) for k, v in est.totals().items()},
                 plant_hire_after=[(r["resource_id"], r["status"]) for r in registry.run_report(db, "plant_hire", pid, {}).get("terms", [])] if False else None)
    ok = (not crit and not gate["blocked"] and not facts["open_material_queries"] and cf1["complete"] and es1["complete"] and facts["time_allocation"]["after"]["reconciliation_checks_ok"]
          and facts["time_allocation"]["before"]["financing_refused_with"] == "TIMEPHASING_INCOMPLETE" and facts["time_allocation"]["before"]["final_gate_blocked_by_it"] and cf0["complete"] is False and not facts["programme"]["gaps"][:0])
    ev.stage("21_resolve_issues_with_test_approvals", "PASS" if ok else "FAIL", **facts)
    return est


# ================================================================================================ stages 22-26
def stage_final_pack(db, ev, A, pid, out_root):
    from app.services import estimates
    from app.tender import packs
    vid = estimates.freeze_version(db, A["est"], pid, "closure-v2", "SYNTHETIC: frozen after the open items were resolved")
    estimates.submit_version(db, A["est"], vid)
    estimates.approve_version(db, A["com"], vid, "TEST ACTOR: SYNTHETIC estimate approval (not a real approval)")
    ap = estimates.approve_tender_export(db, A["com"], pid, vid, "TEST ACTOR: SYNTHETIC tender-export approval (not a real approval)")
    files = estimates.export_submission(db, A["est"], pid, vid, ap)
    exp = [dict(r) for r in db.all("SELECT readiness, submission_ready, COUNT(*) n FROM exports GROUP BY readiness, submission_ready")]
    r = packs.generate_pack(db, A["est"], pid, out_root=out_root, issue_date=Dt.ISSUE_DATE, version_id=vid)
    for code in ("D16", "D06"):
        packs.approve_document(db, A["com"], pid, f"{pid}-{code}")
    v = packs.validate_pack(db, r["pack_pk"])
    by = {d["code"]: d for d in r["documents"]}
    ev["_vid2"], ev["_ap2"] = vid, ap
    first_blocked = sorted(d["code"] for d in ev["_pack1"]["documents"] if d["status"] == "BLOCKED")
    now_blocked = sorted(d["code"] for d in r["documents"] if d["status"] == "BLOCKED")
    ok = (v["ok"] and r["classification"] == "demonstration" and not r["production_ready"] and "D13" not in now_blocked and "D13" in first_blocked
          and all(d["status"] not in ("Approved for Submission",) for d in r["documents"]) and all(x["submission_ready"] == 0 for x in exp)
          and any("DEMONSTRATION" in Path(p).name for p in files.values()))
    ev.stage("22_final_demonstration_pack", "PASS" if ok else "FAIL", pack_revision=r["revision"], out_dir=r["out_dir"], classification=r["classification"], banner=r["banner"], blocked_in_rev1=first_blocked, blocked_now=now_blocked,
             blocked_reasons={d["code"]: d["blocked_reason"] for d in r["documents"] if d["status"] == "BLOCKED"}, validation=dict(ok=v["ok"], errors=v["errors"], warnings=v["warnings"], files=v["files_checked"]),
             statuses={k: sum(1 for d in r["documents"] if d["status"] == k) for k in sorted({d["status"] for d in r["documents"]})}, exports=exp, export_files=sorted(Path(p).name for p in files.values()),
             readiness_reasons_still_present=r.get("reasons"), documents_approved_by_test_actor=["D16", "D06"], note="approved by TEST ACTORs on a demonstration project: the pack stays DEMONSTRATION and is never submission-ready")
    return r


def stage_handover(db, ev, A, pid, out_root):
    from app.services import tender
    from app.tender import packs
    refused = _try(packs.generate_handover_pack, db, A["est"], pid, out_root=out_root, issue_date=Dt.ISSUE_DATE)
    ctx = tender.context(db, pid)
    ctx["award_scenario"] = "hypothetical"
    tender.upsert_item(db, A["est"], pid, "tender_context", "context", ctx, source_ref="simulation selected by the scenario author", is_synthetic=True)
    for d, o, due in (("Place the pump skid purchase order (order date per the long-lead item)", "SIMULATED OWNER - Procurement Manager (test)", "2027-02-21"), ("Submit the baseline programme to the customer", "SIMULATED OWNER - Planning Engineer (test)", "2027-03-21"),
                      ("Issue method statements and ITPs for hot work and excavation", "SIMULATED OWNER - Project Manager (test)", "2027-03-28")):
        tender.add_action(db, A["est"], pid, d, owner=o, due=due, source_ref="simulated handover")
    r = packs.generate_handover_pack(db, A["est"], pid, out_root=out_root, issue_date=Dt.ISSUE_DATE, version_id=ev["_vid2"])
    v = packs.validate_pack(db, r["pack_pk"])
    ok = (refused == "AWARD_NOT_SELECTED" and v["ok"] and len(r["documents"]) == 17 and "HYPOTHETICAL" in r["banner"] and all("SIMULATED" in d["status"] or d["status"] == "BLOCKED" for d in r["documents"]))
    ev.stage("23_hypothetical_handover_pack", "PASS" if ok else "FAIL", refused_before_award_scenario=refused, pack_revision=r["revision"], out_dir=r["out_dir"], banner=r["banner"], documents=[(d["code"], d["title"], d["status"]) for d in r["documents"]],
             validation=dict(ok=v["ok"], errors=v["errors"], warnings=v["warnings"], files=v["files_checked"]), note="no award has been made; the scenario is a labelled simulation")
    return r


def stage_freeze_manifest(db, ev, A, pid, out_root, final, hand):
    from app.services import snapshots
    import hashlib
    v = snapshots.verify_snapshot(db, ev["_vid2"])
    man = json.loads((Path(final["out_dir"]) / "manifest.json").read_text())
    hman = json.loads((Path(hand["out_dir"]) / "manifest.json").read_text())
    files = []
    for m in (man, hman):
        for d in m["documents"]:
            for fmt, f in d.get("files", {}).items():
                files.append(dict(pack=m["kind"], revision=m["revision"], code=d["code"], doc_id=d["doc_id"], format=fmt, path=f["path"], sha256=f["sha256"], bytes=f["bytes"], status=d["status"], template=d["template"]))
    consolidated = dict(project=pid, scenario="Dammam Industrial Utilities - Synthetic Tender Closure", synthetic=True, banner=Dt.BANNER, estimate_version=man["estimate_version"], estimate_fingerprint=man["estimate_fingerprint"],
                        tender_pack=dict(revision=man["revision"], classification=man["classification"], production_ready=man["production_ready"], manifest_sha256=hashlib.sha256((Path(final["out_dir"]) / "manifest.json").read_bytes()).hexdigest()),
                        handover_pack=dict(revision=hman["revision"], hypothetical=True, manifest_sha256=hashlib.sha256((Path(hand["out_dir"]) / "manifest.json").read_bytes()).hexdigest()), files=files)
    Path(out_root).mkdir(parents=True, exist_ok=True)
    (Path(out_root) / "MANIFEST.json").write_text(json.dumps(consolidated, indent=1, sort_keys=True), encoding="utf-8")
    ev.stage("24_freeze_estimate_and_manifest", "PASS" if v.get("ok") and files and all(x["sha256"] for x in files) else "FAIL", snapshot_verified=v.get("ok"), files_in_manifest=len(files), tender_manifest_sha256=consolidated["tender_pack"]["manifest_sha256"],
             handover_manifest_sha256=consolidated["handover_pack"]["manifest_sha256"], estimate_fingerprint=man["estimate_fingerprint"], consolidated_manifest=str(Path(out_root) / "MANIFEST.json"))


def stage_library_change(db, ev, A, pid, out_root, final):
    from app.estimators.estimate import compute_estimate
    from app.services import assumptions, estimates, rates, snapshots
    from app.tender import packs
    vid = ev["_vid2"]
    frozen = estimates.get_version(db, vid)["totals"]
    live_before = {k: str(v) for k, v in compute_estimate(db, pid).totals().items()}
    # a NEW global rate version for a resource the estimate uses, and a revised + approved global assumption
    old = db.one("SELECT unit_price FROM resource_rates WHERE resource_id='SYN-C-030' AND status='Approved' ORDER BY id DESC LIMIT 1")["unit_price"]
    new_price = str(D(old) * D("1.25"))
    nr = rates.propose_rate(db, A["est"], "SYN-C-030", unit_price=new_price, rate_type="Synthetic Demonstration Rate", unit="m", price_date="2026-10-02", confidence="Medium", is_synthetic=True,
                            evidence="SYNTHETIC / DEMO / NOT A MARKET QUOTE", submit=True)
    rates.approve_rate(db, A["proc"], nr, comments="TEST ACTOR: SYNTHETIC global library change after the freeze")
    assumptions.revise_assumption(db, A["est"], "ASMP-Z-002", default_value="5")
    assumptions.submit_assumption(db, A["est"], "ASMP-Z-002")
    assumptions.approve_assumption(db, A["com"], "ASMP-Z-002", comments="TEST ACTOR: SYNTHETIC global change")
    live_after = {k: str(v) for k, v in compute_estimate(db, pid).totals().items()}
    rp = snapshots.replay_estimate(db, vid)
    r3 = packs.generate_pack(db, A["est"], pid, out_root=out_root, issue_date=Dt.ISSUE_DATE, version_id=vid)
    f2 = {d["code"]: json.loads(db.one("SELECT facts_json FROM generated_documents g JOIN tender_packs p ON p.pk=g.pack_pk WHERE p.project_id=? AND p.revision=? AND p.kind='tender' AND g.doc_code=?", (pid, final["revision"], d["code"]))["facts_json"] or "{}")
          for d in final["documents"] if d["status"] != "Not Applicable"}
    f3 = {d["code"]: json.loads(db.one("SELECT facts_json FROM generated_documents WHERE pack_pk=? AND doc_code=?", (r3["pack_pk"], d["code"]))["facts_json"] or "{}") for d in r3["documents"] if d["status"] != "Not Applicable"}
    est_keys = ("net_price", "vat", "payable", "schedule_total", "direct_cost", "indirect_cost", "total_cost", "estimate_version", "fingerprint")
    diff = {c: {k: (f2[c].get(k), f3[c].get(k)) for k in est_keys if f2[c].get(k) != f3[c].get(k)} for c in f2 if any(f2[c].get(k) != f3[c].get(k) for k in est_keys)}
    ok = (live_before != live_after and rp["ok"] and not diff and estimates.get_version(db, vid)["totals"] == frozen)
    ev.stage("25_global_library_change", "PASS" if ok else "FAIL", live_estimate_changed=live_before != live_after, live_total_before=live_before["final_payable"], live_total_after=live_after["final_payable"], frozen_total=frozen["final_payable"],
             frozen_replay_ok=rp["ok"], replay_differences=rp.get("differences"), document_figure_differences_rev_after_vs_before=diff, new_pack_revision=r3["revision"],
             global_changes=dict(rate="SYN-C-030 +25% (new approved version)", assumption="ASMP-Z-002 revised to v2 (approved)"))
    return r3


def stage_replay(db, ev, A, pid, final):
    from app.services import snapshots
    vid = ev["_vid2"]
    rp = snapshots.replay_estimate(db, vid)
    dc = snapshots.replay_direct_cost(db, vid)
    from app.services import estimates
    t = estimates.get_version(db, vid)["totals"]
    docfacts = json.loads(db.one("SELECT facts_json FROM generated_documents g JOIN tender_packs p ON p.pk=g.pack_pk WHERE p.project_id=? AND p.revision=? AND p.kind='tender' AND g.doc_code='D06'", (pid, final["revision"]))["facts_json"])
    agree = (docfacts["net_price"] == t["commercial_net_price"] and docfacts["payable"] == t["final_payable"] and docfacts["vat"] == t["tax"] and rp["replayed"]["final_payable"] == t["final_payable"])
    ev.stage("26_snapshot_replay", "PASS" if rp["ok"] and dc["ok"] and agree else "FAIL", replay_ok=rp["ok"], replay_fingerprint=rp["fingerprint"][:16], direct_cost_replay_ok=dc["ok"], documents_agree_with_frozen_totals=agree,
             frozen_totals=t, replayed_totals=rp["replayed"], document_facts={k: docfacts[k] for k in ("net_price", "vat", "payable", "schedule_total")})


# ================================================================================================ stage 27
def stage_interfaces(db, ev, A, pid, workdir):
    """The same functionality through the service, the REST API, the web UI and the CLI must give the same numbers."""
    from fastapi.testclient import TestClient
    from app.api.serializers import ser
    from app.main import app
    from app.reporting import registry
    from app.services import estimates
    profiles = ",".join(p[0] for p in Dt.PROFILES)
    svc = {"crew": ser(registry.run_report(db, "crew_scenarios", pid, {"profiles": profiles, "provisional": "true"})), "applic": ser(registry.run_report(db, "applicability", pid, {})),
           "queries": ser(registry.run_report(db, "tender_queries", pid, {})), "evidence": ser(registry.run_report(db, "assumption_evidence", pid, {}))}
    cli = {"crew": _cli(workdir, "report", pid, "crew_scenarios", "--param", f"profiles={profiles}", "--param", "provisional=true"), "applic": _cli(workdir, "report", pid, "applicability"),
           "queries": _cli(workdir, "report", pid, "tender_queries"), "evidence": _cli(workdir, "report", pid, "assumption_evidence")}
    api, ui = {}, {}
    with TestClient(app, headers={"Origin": "http://testserver"}) as c:
        r = c.post("/api/auth/login", json={"username": "api-est", "password": "pw-api-est"})
        h = {"Authorization": "Bearer " + r.json()["token"]}
        c.cookies.clear()
        for k, name, q in (("crew", "crew_scenarios", f"?profiles={profiles}&provisional=true"), ("applic", "applicability", ""), ("queries", "tender_queries", ""), ("evidence", "assumption_evidence", "")):
            rr = c.get(f"/api/projects/{pid}/report/{name}{q}", headers=h)
            api[k] = (rr.status_code, rr.json() if rr.status_code == 200 else rr.text[:200])
        e = c.get(f"/api/projects/{pid}/estimate", headers=h)
        api["estimate_totals"] = e.json().get("totals") if e.status_code == 200 else e.status_code
        assert c.post("/login", data={"username": "api-est", "password": "pw-api-est"}, follow_redirects=False).status_code == 303
        for path in (f"/projects/{pid}/", f"/projects/{pid}/estimate", f"/projects/{pid}/boq", f"/projects/{pid}/reconciliation", f"/projects/{pid}/analysis", f"/projects/{pid}/analysis/crew_scenarios",
                     f"/projects/{pid}/analysis/applicability", f"/projects/{pid}/analysis/tender_queries", f"/projects/{pid}/analysis/assumption_evidence", f"/projects/{pid}/analysis/productivity_programme", f"/projects/{pid}/workspace"):
            rr = c.get(path)
            ui[path] = dict(status=rr.status_code, traceback="Traceback" in rr.text, mentions_synthetic="SYNTHETIC" in rr.text.upper())
    cj = {k: json.loads(v["full"]) for k, v in cli.items() if v["exit"] == 0}
    agree = {}
    agree["crew_working_days"] = ([s["working_days"] for s in svc["crew"]["scenarios"]] == [s["working_days"] for s in cj["crew"]["scenarios"]] == [s["working_days"] for s in api["crew"][1]["scenarios"]])
    agree["applicability_counts"] = svc["applic"]["counts"] == cj["applic"]["counts"] == api["applic"][1]["counts"]
    agree["query_status_counts"] = svc["queries"]["by_status"] == cj["queries"]["by_status"] == api["queries"][1]["by_status"]
    agree["assumption_classes"] = svc["evidence"]["by_class"] == cj["evidence"]["by_class"] == api["evidence"][1]["by_class"]
    live = {k: str(v) for k, v in __import__("app.estimators.estimate", fromlist=["x"]).compute_estimate(db, pid).totals().items()}
    agree["estimate_totals_api_vs_engine"] = all(str(api["estimate_totals"].get(k)) == v or D(str(api["estimate_totals"].get(k))) == D(v) for k, v in live.items())
    ui_ok = all(v["status"] == 200 and not v["traceback"] for v in ui.values())
    ev.stage("27_ui_api_cli_agreement", "PASS" if all(agree.values()) and ui_ok and all(v["exit"] == 0 for v in cli.values()) else "FAIL", agreement=agree, ui=ui, cli_exit={k: v["exit"] for k, v in cli.items()},
             crew_working_days={s["profile"]: s["working_days"] for s in svc["crew"]["scenarios"]}, applicability_counts=svc["applic"]["counts"], query_status_counts=svc["queries"]["by_status"])


# ================================================================================================ orchestration
def verdicts(ev: Evidence) -> dict:
    return {k: v["verdict"] for k, v in ev.items() if not k.startswith("_")}


def run(workdir: Path, out_root: Path | None = None) -> Evidence:
    workdir = Path(workdir)
    out_root = Path(out_root) if out_root else workdir / "demo_output"
    ev = Evidence()
    db, s = bootstrap(workdir)
    A = actors()
    done = {}

    def step(key, fn, *a):
        try:
            done[key] = fn(*a)
        except Exception as e:                                        # noqa: BLE001 - a stage that raises is a FAIL, never a silent skip
            ev.stage(key, "FAIL", error=f"{type(e).__name__}: {e}", traceback=traceback.format_exc()[-1800:])
            done[key] = None
        return done[key]
    pid = step("03", stage_enquiry_project_docs, db, ev, A, workdir)
    if pid is None:
        return ev
    step("04", stage_boq, db, ev, A, pid)
    step("05", stage_map, db, ev, A, pid)
    step("06", stage_assumptions, db, ev, A, pid)
    step("07", stage_direct, db, ev, A, pid)
    sc = step("08", stage_productivity, db, ev, A, pid)
    step("09", stage_programme, db, ev, A, pid, sc)
    step("10", stage_queries, db, ev, A, pid)
    ans = step("11", stage_responses, db, ev, A, pid)
    step("12", stage_recalculate, db, ev, A, pid, ans)
    step("13", stage_procurement, db, ev, A, pid)
    step("14", stage_commercial, db, ev, A, pid)
    step("15", stage_methodology, db, ev, A, pid)
    step("16", stage_matrix, db, ev, A, pid)
    r1 = step("17", stage_pack1, db, ev, A, pid, out_root)
    step("18", stage_validate1, db, ev, A, pid, r1)
    step("19", stage_production_blocked, db, ev, A, pid, out_root)
    step("20", stage_assumption_bypass, db, ev, A, pid, workdir)
    step("21", stage_resolve, db, ev, A, pid, out_root)
    fin = step("22", stage_final_pack, db, ev, A, pid, out_root)
    hand = step("23", stage_handover, db, ev, A, pid, out_root)
    if fin and hand:
        step("24", stage_freeze_manifest, db, ev, A, pid, out_root, fin, hand)
        step("25", stage_library_change, db, ev, A, pid, out_root, fin)
        step("26", stage_replay, db, ev, A, pid, fin)
    step("27", stage_interfaces, db, ev, A, pid, workdir)
    for k in STAGES:                      # a stage that never ran is reported as NOT TESTED, never omitted
        ev.setdefault(k, {"verdict": "NOT TESTED"}) if not any(x.startswith(k[:2]) for x in ev) else None
    ev["_summary"] = dict(project=pid, out_root=str(out_root), database=str(workdir / "scratch_closure.db"))
    return ev
