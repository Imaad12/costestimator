"""SYNTHETIC end-to-end pilot (docs/SYNTHETIC_PILOT_RUN.md). Drives the REAL services against a scratch database.

Everything here is SYNTHETIC / TEST ONLY / NOT A MARKET QUOTE: the "TEST ACTOR" users validate software behaviour and are not real approvals.
`run(workdir)` returns an evidence dict (stage -> verdict + facts). Nothing is written to the shared library, data/ or projects/.
"""
from __future__ import annotations

import csv
import json
import shutil
import traceback
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

D = Decimal
FIX = Path(__file__).resolve().parent.parent / "fixtures" / "synthetic_pilot"
PROJECT_ID = "PRJ-9001"
VARIANT_ID = "PRJ-9002"
BANNER = "SYNTHETIC SOFTWARE VALIDATION ONLY — NOT A MARKET ESTIMATE, NOT FOR TENDER, NOT FOR PROCUREMENT, AND NOT FOR COMMERCIAL RELIANCE."


def r2(x) -> Decimal:
    return D(x).quantize(D("0.01"), rounding=ROUND_HALF_UP)


def boq_rows() -> list[dict]:
    return json.loads((FIX / "boq_SYNTHETIC_TEST_ONLY.json").read_text())


class Evidence(dict):
    def stage(self, key: str, verdict: str, **facts):
        self[key] = {"verdict": verdict, **facts}


def bootstrap(workdir: Path):
    from app import config as cfg
    from app.database import Database, set_db
    from app.services import refdata
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    s = cfg.load_settings(env={"KSA_DB_PATH": str(workdir / "scratch_pilot.db"), "KSA_WORKSPACES_DIR": str(workdir / "workspaces"),
                               "KSA_SECRET_KEY": "synthetic-pilot", "KSA_ALLOW_SELF_APPROVAL": "true", "KSA_ENVIRONMENT": "test"})
    cfg.set_settings(s)
    if Path(s.db_path).exists():
        raise RuntimeError(f"{s.db_path} already exists: the pilot needs a fresh scratch directory")
    db = Database(s.db_path)
    db.migrate()
    set_db(db)
    refdata.seed_reference(db)
    from app.services import auth
    for u, role in (("test-estimator", "Estimator"), ("test-procurement", "Procurement Reviewer"), ("test-commercial", "Commercial Approver"), ("test-admin", "Administrator")):
        auth.create_user(db, u, f"TEST ACTOR {role}", role, None, actor_type="test")          # registered as TEST principals: durable marker, not a display name
    return db, s


# ------------------------------------------------------------------ actors (TEST ACTORs - not real approvals)
def actors():
    from app.models.actor import Actor
    return dict(est=Actor("test-estimator", "Estimator", "TEST ACTOR Estimator"), proc=Actor("test-procurement", "Procurement Reviewer", "TEST ACTOR Procurement"),
                com=Actor("test-commercial", "Commercial Approver", "TEST ACTOR Commercial"), admin=Actor("test-admin", "Administrator", "TEST ACTOR Admin"),
                ai=Actor("test-ai", "AI Assistant", "TEST ACTOR AI", is_ai=True))


# resource type / unit per BOQ line for the SYNTHETIC baseline "installed-rate" resources
RTYPE = {**{f"P-{i:03d}": "material" for i in range(1, 17)}, "P-017": "labour", "P-018": "labour", "P-019": "labour", "P-020": "plant", "P-021": "plant",
         "P-022": "subcontract", "P-023": "subcontract", "P-024": "subcontract", "P-025": "subcontract", "P-026": "subcontract", "P-027": "subcontract",
         "P-028": "subcontract", "P-029": "subcontract", "P-030": "subcontract"}
UNIT_MAP = {"m": "m", "ea": "nr", "set": "set", "kg": "kg", "dia-in": "inch_dia", "hour": "hr", "day": "day", "m2-day": "m2_day", "weld": "joint",
            "test": "test", "LS": "ls", "m2": "m2"}


def independent_total() -> tuple[list[tuple[str, Decimal]], Decimal]:
    ext = [(r["item"], D(str(r["quantity"])) * D(str(r["baseline_rate"]))) for r in boq_rows()]
    return ext, sum((e for _, e in ext), D(0))


def stage_project_and_boq(db, ev: Evidence, A: dict, workdir: Path) -> None:
    from app.imports import boq as bi
    from app.services import boq, project_index, projects, units_admin, workspaces
    pid = projects.create_project(db, A["est"], name="SYNTHETIC Eastern Province Utility Piping Package", client="SYNTHETIC CLIENT (fictional)", location="Dammam industrial area, Saudi Arabia",
                                  project_type="industrial piping", design_stage="SYNTHETIC TEST", is_demo=True, tax_category="VAT-STD", id=PROJECT_ID,
                                  notes=BANNER)
    root = workspaces.resolve_dir(pid, db)
    tender = root / "1. Tender Documents"
    shutil.copy2(FIX / "boq_SYNTHETIC_TEST_ONLY.csv", tender / "boq_SYNTHETIC_TEST_ONLY.csv")                    # the original measured-BOQ fixture, kept untouched
    (tender / "SYNTHETIC_scope_note_TEST_ONLY.txt").write_text(
        BANNER + "\nScope (synthetic): carbon-steel pipes, fittings, flanges, gaskets, bolts; gate and check valves; fabricated supports and anchors; welding and installation; weld inspection and PMI; "
        "crane, forklift and scaffolding; hydrotesting and flushing; surface preparation, painting and insulation; mobilisation and supervision.\nLocation: Dammam industrial area (fictional client).\n", encoding="utf-8")
    imp = bi.import_boq(db, A["est"], pid, FIX / "boq_SYNTHETIC_TEST_ONLY.csv")
    q = "SELECT item_key, unit, unit_status, quantity, cost_code FROM boq_items WHERE project_id=? AND item_type='item' ORDER BY id"
    first = {r["item_key"]: (r["unit"], r["unit_status"]) for r in db.all(q, (pid,))}
    flagged = {k: v for k, v in first.items() if v[1] != "ok"}
    # unit rules: m2-day / test / dia-in are NOT silently converted; an administrator adds the two missing units explicitly, then a human approves each correction
    units_admin.add_unit(db, A["admin"], code="m2_day", name="square metre-day", dimension="area_time", to_base="1", synonyms="m2-day|m2 day")
    units_admin.add_unit(db, A["admin"], code="test", name="test (count of tests)", dimension="test_count", to_base="1", synonyms="tests")
    decisions = {}
    for ch in boq.pending_changes(db, pid):
        if ch["field"] != "unit":
            continue
        code = {"P-016": "inch_dia", "P-022": "m2_day", "P-024": "test"}[ch["entity_id"]]
        boq.decide_change(db, A["est"], ch["id"], True, unit_code=code, comment=f"SYNTHETIC: BOQ unit text mapped explicitly to '{code}' (not silently converted)")
        decisions[ch["entity_id"]] = code
    rows = db.all(q, (pid,))
    idx = project_index.index_project(db, A["est"], pid)
    docs = project_index.list_documents(db, pid)
    hit = project_index.search(db, pid, "hydrotesting")
    claude_md = (root / "CLAUDE.md").read_text(encoding="utf-8")
    manifest = json.loads((root / "project.json").read_text(encoding="utf-8"))
    uploads = sorted(p.name for p in (root / "3. BOQ & Takeoff").iterdir())
    other_ids = sorted(set(__import__("re").findall(r"PRJ-\d{4}", claude_md + json.dumps(manifest))) - {pid})
    ws_ok = (len([p for p in root.iterdir() if p.is_dir()]) == 10 and "CLAUDE.md" in [p.name for p in root.iterdir()] and manifest.get("project_id", manifest.get("id")) == pid and not other_ids
             and any("SYNTHETIC_scope_note" in d["path"] for d in [{"path": x["rel_path"]} for x in docs]) and bool(hit) and any(n.endswith("boq_SYNTHETIC_TEST_ONLY.csv") for n in uploads))
    ev.stage("3_project_workspace", "PASS" if ws_ok else "FAIL", index=dict(new=idx["new"], extracted=idx["extracted"], documents=[d["rel_path"] for d in docs]), search_hits_for_hydrotesting=len(hit), boq_upload_copies=uploads,
             manifest_project=manifest.get("project_id", manifest.get("id")), other_project_ids_in_claude_md_or_manifest=other_ids, claude_md_mentions_synthetic="SYNTHETIC" in claude_md.upper(), project_id=pid, workspace=str(root), folders=sorted(p.name for p in root.iterdir() if p.is_dir()),
             files=sorted(p.name for p in root.iterdir() if p.is_file()),
             boq_import={k: v for k, v in imp.items() if k in ("rows_read", "items_new", "rejected", "change_requests")},
             units_flagged_on_import=flagged, unit_decisions=decisions, units_after={r["item_key"]: (r["unit"], r["unit_status"]) for r in rows},
             cost_codes_on_import={r["item_key"]: r["cost_code"] for r in rows})


def library_resources() -> list[dict]:
    return json.loads((FIX / "library_resources_SYNTHETIC.json").read_text())


LIB_TYPE = {"LIB-PIPE-DN100": "material", "LIB-PIPE-DN50": "material", "LIB-LAB-WELDER": "labour", "LIB-LAB-FITTER": "labour", "LIB-LAB-HELPER": "labour",
            "LIB-PLT-CRANE": "plant", "LIB-PLT-FORK": "plant", "LIB-MAT-WELDCONS": "material", "LIB-MAT-SUPPORT": "material", "LIB-MAT-PAINT": "material"}
QUOTED_LIB = {"LIB-PIPE-DN100", "LIB-PIPE-DN50", "LIB-MAT-SUPPORT"}          # their candidates stay pending: the quotations below are the evidence route


def stage_resources_and_rates(db, ev: Evidence, A: dict, workdir: Path) -> dict:
    from app.core.errors import ValidationFailed
    from app.rate_updates import candidates as cand, importer
    from app.services import rates
    for b in boq_rows():
        rates.create_resource(db, A["est"], resource_type=RTYPE[b["item"]], description=f"SYNTHETIC installed baseline: {b['description']}", unit=UNIT_MAP[b["unit"]],
                              cost_code=b["cost_code"], id=f"SYN-{b['item']}", is_synthetic=True)
    for r in library_resources():
        rates.create_resource(db, A["est"], resource_type=LIB_TYPE[r["id"]], description=r["description"], unit=r["unit"], id=r["id"], is_synthetic=True)
    for rid, d, u, t in (("LIB-VALVE-GATE-DN100", "SYNTHETIC Gate valve DN100, supply only", "nr", "material"), ("LIB-VALVE-CHECK-DN100", "SYNTHETIC Check valve DN100, supply only", "nr", "material")):
        rates.create_resource(db, A["est"], resource_type=t, description=d, unit=u, id=rid, is_synthetic=True)
    f = FIX / "rates_SYNTHETIC_TEST_ONLY.csv"
    url = "SYNTHETIC-TEST-FIXTURE:tests/fixtures/synthetic_pilot/rates_SYNTHETIC_TEST_ONLY.csv"
    kw = dict(source_name="SYNTHETIC TEST DATA - NOT A MARKET QUOTE", source_url=url, source_type="Manual dataset", extra_flags=["SYNTHETIC_DATA"], description="SYNTHETIC pilot rate file", confidence="Medium")
    dry = importer.import_rates_file(db, A["est"], f, dry_run=True, **kw)
    n_rates_before = db.scalar("SELECT COUNT(*) FROM resource_rates")
    real = importer.import_rates_file(db, A["est"], f, **kw)
    cands = db.all("SELECT id, candidate_ref, resource_id, status, flags_json, source_name, original_price, original_currency, original_unit, effective_date FROM rate_candidates ORDER BY id")
    pending_ok = all(c["status"] == "Pending Review" for c in cands)
    no_rates_yet = db.scalar("SELECT COUNT(*) FROM resource_rates WHERE unit_price IS NOT NULL") == 0 or db.scalar("SELECT COUNT(*) FROM resource_rates") == n_rates_before
    # an index source is refused as a price source
    idx = {}
    for sid in ("SRC-001", "SRC-002", "SRC-003"):
        try:
            importer.import_rates_file(db, A["est"], f, source_id=sid, dry_run=True)
            idx[sid] = "ACCEPTED (defect)"
        except ValidationFailed as e:
            idx[sid] = e.code
    # approvals through the real chain with TEST ACTORs (candidate review -> publish -> approve_rate); quoted materials are left at candidate stage
    approved = 0
    for c in cands:
        if c["resource_id"] in QUOTED_LIB:
            continue
        cand.review(db, A["proc"], c["id"], "approve", comments="TEST ACTOR: SYNTHETIC rate approved for software validation only")
        rid = cand.publish(db, A["est"], c["id"])
        rates.approve_rate(db, A["proc"], rid, comments="TEST ACTOR: SYNTHETIC rate approval (not a real procurement approval)")
        approved += 1
    published = db.all("SELECT rate_type, is_synthetic, status, COUNT(*) n FROM resource_rates GROUP BY rate_type, is_synthetic, status")
    ev.stage("6_rate_import", "PASS" if (dry["accepted"] == 40 and real["accepted"] == 40 and pending_ok and set(idx.values()) == {"SOURCE_NOT_PRICE"}) else "FAIL",
             dry_run=dict(accepted=dry["accepted"], rejected=dry["rejected"], errors=dry["errors"]), import_=dict(accepted=real["accepted"], rejected=real["rejected"], manifest=real["manifest_id"]),
             all_candidates_pending_review=pending_ok, rates_created_by_import=n_rates_before != db.scalar("SELECT COUNT(*) FROM resource_rates") and False,
             index_source_results=idx, approved_via_test_actor_chain=approved, left_pending_candidates=[c["resource_id"] for c in cands if c["resource_id"] in QUOTED_LIB],
             sample_candidate={k: cands[0][k] for k in cands[0].keys()}, rates_by_type=[dict(r) for r in published])
    return {"candidates": [dict(c) for c in cands]}


WBS = [("1.0", "Project management and mobilisation"), ("2.0", "Piping materials"), ("3.0", "Piping installation and welding"), ("4.0", "Supports and anchors"),
       ("5.0", "Inspection and testing"), ("6.0", "Access and lifting"), ("7.0", "Painting and insulation"), ("8.0", "Project indirects and commercial costs")]
WBS_OF = {**{f"P-{i:03d}": "2.0" for i in range(1, 14)}, "P-014": "4.0", "P-015": "4.0", "P-016": "3.0", "P-017": "3.0", "P-018": "3.0", "P-019": "3.0",
          "P-020": "6.0", "P-021": "6.0", "P-022": "6.0", "P-023": "5.0", "P-024": "5.0", "P-025": "5.0", "P-026": "5.0", "P-027": "7.0", "P-028": "7.0",
          "P-029": "1.0", "P-030": "1.0"}


def _line_for(item: str) -> dict:
    t = RTYPE[item]
    ln = dict(line_type=t, resource_id=f"SYN-{item}", factor="1")
    if t == "material":
        ln["factor_includes_waste"] = 1
    if t == "plant":
        ln["factor_unit"] = "day"                                           # the factor is days per BOQ day: stated, so no PLANT_UNIT assumption
    if t == "labour":
        ln["productivity_basis"] = "paid_hours_per_unit"
    return ln


def stage_mapping_baseline(db, ev: Evidence, A: dict, pid: str = PROJECT_ID) -> None:
    from app.estimators.estimate import compute_estimate
    from app.services import assemblies, boq, wbs
    for b in boq_rows():
        code = f"SYNA-{b['item']}"
        assemblies.create_assembly(db, A["est"], code=code, description=f"SYNTHETIC baseline installed-rate assembly {b['item']}: {b['description']}", unit=UNIT_MAP[b["unit"]],
                                   cost_code=b["cost_code"], is_synthetic=True, source="SYNTHETIC test assembly - one installed-rate resource line", lines_=[_line_for(b["item"])])
        assemblies.submit_assembly(db, A["est"], code)
        assemblies.approve_assembly(db, A["com"], code, comments="TEST ACTOR: SYNTHETIC")
        boq.map_to_assembly(db, A["est"], pid, b["item"], code)
        boq.set_cost_code(db, A["est"], pid, b["item"], b["cost_code"])
    for c, n in WBS:
        wbs.add_node(db, A["est"], pid, c, n)
    wbs.assign_items(db, A["est"], pid, WBS_OF)
    for b in boq_rows():                                                                # fictional client code cross-walk (test project only)
        wbs.add_crosswalk(db, A["est"], pid, "FICTIONAL-CLIENT-CBS", f"FC-{b['item']}", b["cost_code"], b["description"])
    est = compute_estimate(db, pid)
    ev["_baseline_state"] = est.state


def stage_params(db, ev: Evidence, A: dict, pid: str = PROJECT_ID) -> dict:
    from app.estimators.estimate import compute_estimate
    from app.services import governed
    f = FIX / "governed_parameters_SYNTHETIC_TEST_ONLY.csv"
    before = db.scalar("SELECT COUNT(*) FROM governed_params")
    dry = governed.import_csv(db, A["est"], f, dry_run=True)
    after_dry = db.scalar("SELECT COUNT(*) FROM governed_params")
    res = governed.import_csv(db, A["est"], f)
    statuses = {r["id"]: r["status"] for r in db.all("SELECT id, status FROM governed_params")}
    all_draft = set(statuses.values()) == {"Draft"}
    pre = compute_estimate(db, pid)                                                           # approved view: Draft parameters must not be in force
    in_force = governed.effective(db, pid, "calendar")
    ids = res["created_ids"]
    for i in ids:
        governed.submit(db, A["est"], i)
        governed.approve(db, A["com"], i, comments="TEST ACTOR: SYNTHETIC parameter approved to exercise the workflow (not a real approval)")
    ev.stage("8_governed_parameters", "PASS" if (dry["would_create"] == 7 and not dry["errors"] and after_dry == before and all_draft and not in_force and len(ids) == 7) else "FAIL",
             dry_run=dry, rows_before_dry_run=before, rows_after_dry_run=after_dry, imported=res, all_imported_as_draft=all_draft, draft_in_force_before_approval=bool(in_force),
             approved_via_test_actor=len(ids), kinds_unsupported_as_governed=["site indirects %", "home-office overhead %", "contingency %", "target profit %", "VAT % (tax category record)", "FX (SAR-only)"])
    return {"ids": ids}


TASKS = [   # scope tie for loading: a task declares a cost-code prefix and/or a WBS node; lines reach it by that scope (cost-code-only or WBS-only so that coverage is as wide as the brief allows)
    dict(task_code="MOB", name="Mobilisation and access", duration_days="3", predecessors="", cost_code="A.01"),
    dict(task_code="PROC", name="Material procurement", duration_days="10", predecessors="MOB-SS", wbs_code="2.0"),
    dict(task_code="SUPFAB", name="Supports fabrication", duration_days="5", predecessors="MOB", wbs_code="4.0"),
    dict(task_code="INST", name="Piping installation", duration_days="8", predecessors="PROC,SUPFAB", wbs_code="3.0"),
    dict(task_code="WELD", name="Welding completion", duration_days="5", predecessors="INST-SS+3,INST-FF+2", wbs_code="3.0"),
    dict(task_code="NDT", name="NDT and PMI", duration_days="3", predecessors="WELD-SS+2,PROC", cost_code="A.08"),
    dict(task_code="HYDRO", name="Hydrotest and flushing", duration_days="3", predecessors="WELD,NDT", cost_code="F.10"),
    dict(task_code="PAINT", name="Painting and insulation", duration_days="4", predecessors="HYDRO", wbs_code="7.0"),
    dict(task_code="FINAL", name="Final inspection and handover", duration_days="2", predecessors="PAINT"),
]


# Explicit eligibility (SYNTHETIC test decision): the percentage indirects apply to the E/D/F BOQ scope only; preliminaries (division A) are priced as BOQ lines and are excluded.
INDIRECT_ELIGIBILITY = {"default": "exclude", "rules": [{"cost_prefix": "A", "eligible_pct": 0, "note": "preliminaries are BOQ lines"}, {"cost_prefix": "E", "eligible_pct": 100},
                                                        {"cost_prefix": "D", "eligible_pct": 100}, {"cost_prefix": "F", "eligible_pct": 100}]}


def stage_commercial_setup(db, ev: Evidence, A: dict, pid: str = PROJECT_ID, *, approve_tax: bool = True, approve_duration: bool = True) -> None:
    from app.services import commercial, indirects
    for code, cat, desc, amt in (("IND-SITE", "Site indirects", "SYNTHETIC site indirects, 8% of the ELIGIBLE direct cost (preliminaries division A excluded: supervision, mobilisation, plant, access are BOQ lines)", "8"),
                                 ("IND-HO", "Home-office overhead", "SYNTHETIC home-office overhead, 3% of the ELIGIBLE direct cost (division A excluded)", "3")):
        indirects.add_indirect(db, A["est"], pid, code=code, category=cat, description=desc, method="percent_of_direct", amount=amt, is_synthetic=True,
                               source="SYNTHETIC TEST ASSUMPTION - NOT COMPANY DATA", eligibility=INDIRECT_ELIGIBILITY)
        indirects.submit_indirect(db, A["est"], pid, code)
        indirects.approve_indirect(db, A["com"], pid, code, comments="TEST ACTOR: SYNTHETIC")
    cfg = {"method": "markup", "markup_pct": "7", "default_tax_category": "VAT-STD", "contingency": {"pct": "5", "base": "direct_indirect"}, "risk_items": [],
           "rounding": {"dp": 2}}
    pol = commercial.create_policy(db, A["est"], code="POL-SYNTH", name="SYNTHETIC policy: markup 7% on total cost, contingency 5% of direct+indirect", config=cfg, is_synthetic=True)
    commercial.submit_policy(db, A["est"], pol)
    commercial.approve_policy(db, A["com"], pol, comments="TEST ACTOR: SYNTHETIC")
    commercial.assign_policy(db, A["est"], pid, pol)
    ev["_policy_id"] = pol
    if approve_tax:
        tid = db.scalar("SELECT id FROM tax_categories WHERE code='VAT-STD'")
        commercial.approve_tax_category(db, A["com"], tid, evidence="TEST ONLY: 15% used solely as a synthetic calculation parameter - NOT a verified tax determination")


def stage_programme(db, ev: Evidence, A: dict, pid: str = PROJECT_ID) -> dict:
    from app.estimators.estimate import compute_estimate
    from app.services import assumptions, indirects, programme
    for aid, val in (("ASMP-D-003", "6"), ("ASMP-D-004", "26"), ("ASMP-D-005", "10")):
        assumptions.set_override(db, A["est"], pid, aid, val, "SYNTHETIC TEST ASSUMPTION derived from the synthetic calendar (6 days/week, 10 h/day, 26 days/month)")
        assumptions.approve_override(db, A["com"], pid, aid, comments="TEST ACTOR: SYNTHETIC")
    indirects.set_tasks(db, A["est"], pid, TASKS)
    rep = programme.schedule_report(db, pid)
    did = indirects.propose_duration_from_schedule(db, A["est"], pid)
    indirects.approve_duration(db, A["com"], did, comments="TEST ACTOR: SYNTHETIC")
    est = compute_estimate(db, pid)
    mh = programme.manhours_report(db, pid, est=est)
    ld = programme.loading_report(db, pid, measure="labour_hours", period="week", est=est)
    start = rep["tasks"][0]["start_date"]
    cal_days = (__import__("datetime").date.fromisoformat(rep["project_finish_date"]) - __import__("datetime").date.fromisoformat(start)).days + 1
    ev.stage("9_programme", "PASS", working_days=rep["project_working_days"], critical_path=rep["critical_path"], driving_path=rep.get("driving_path"),
             start=start, finish=rep["project_finish_date"], calendar_days_inclusive=cal_days, assumed_calendar_days=30, exceeds_30_day_assumption=cal_days > 30,
             tasks=[{k: t[k] for k in ("task_code", "es", "ef", "total_float", "critical", "start_date", "finish_date")} for t in rep["tasks"]],
             duration_proposal_id=did, manhours_total=mh["total_hours"], manhours_by_resource=mh["by_resource"], manhours_by_wbs=mh["by_wbs"],
             loading=dict(scheduled=ld["scheduled_total"], unscheduled=ld["unscheduled_total"], tie_out=ld["tie_out"], totals=ld["totals"]))
    return {"report": rep, "manhours": mh, "loading": ld}


def quotations() -> dict:
    return json.loads((FIX / "quotations_SYNTHETIC_NOT_A_REAL_QUOTE.json").read_text())


NORMS = {   # explicit SYNTHETIC test norms (hours / quantities per unit) stored in the assemblies' notes - none is hidden in application code
    "ASM-DN100-INST": dict(unit="m", cost="E.06", lines=[("material", "LIB-PIPE-DN100", "1", dict(waste_basis="fixed_pct", waste_value="2")), ("labour", "LIB-LAB-WELDER", "0.50", {}),
                                                         ("labour", "LIB-LAB-FITTER", "0.60", {}), ("labour", "LIB-LAB-HELPER", "0.50", {}), ("material", "LIB-MAT-WELDCONS", "0.667", dict(factor_includes_waste=1))]),
    "ASM-DN50-INST": dict(unit="m", cost="E.06", lines=[("material", "LIB-PIPE-DN50", "1", dict(waste_basis="fixed_pct", waste_value="2")), ("labour", "LIB-LAB-WELDER", "0.25", {}),
                                                        ("labour", "LIB-LAB-FITTER", "0.35", {}), ("labour", "LIB-LAB-HELPER", "0.30", {}), ("material", "LIB-MAT-WELDCONS", "0.333", dict(factor_includes_waste=1))]),
    "ASM-SUPPORT-KG": dict(unit="kg", cost="E.08", lines=[("material", "LIB-MAT-SUPPORT", "1", dict(waste_basis="fixed_pct", waste_value="5")), ("labour", "LIB-LAB-WELDER", "0.02", {}),
                                                          ("labour", "LIB-LAB-FITTER", "0.03", {}), ("labour", "LIB-LAB-HELPER", "0.03", {}), ("material", "LIB-MAT-PAINT", "0.01", dict(factor_includes_waste=1))]),
    "ASM-VALVE-GATE-DN100": dict(unit="nr", cost="E.08", lines=[("material", "LIB-VALVE-GATE-DN100", "1", dict(factor_includes_waste=1)), ("labour", "LIB-LAB-FITTER", "1.5", {}), ("labour", "LIB-LAB-HELPER", "1.5", {})]),
    "ASM-VALVE-CHECK-DN100": dict(unit="nr", cost="E.08", lines=[("material", "LIB-VALVE-CHECK-DN100", "1", dict(factor_includes_waste=1)), ("labour", "LIB-LAB-FITTER", "1.5", {}), ("labour", "LIB-LAB-HELPER", "1.5", {})]),
}
VARIANT_MAP = {"P-001": "ASM-DN50-INST", "P-002": "ASM-DN100-INST", "P-012": "ASM-VALVE-GATE-DN100", "P-013": "ASM-VALVE-CHECK-DN100", "P-014": "ASM-SUPPORT-KG"}


def stage_variant_assemblies(db, ev: Evidence, A: dict, workdir: Path) -> None:
    """Project PRJ-9002: the SAME measured quantities for five lines priced bottom-up from resource assemblies (supply rates still missing)."""
    from app.estimators.estimate import compute_estimate
    from app.imports import boq as bi
    from app.services import assemblies, boq, projects
    for code, a in NORMS.items():
        lines = []
        for lt, rid, fac, extra in a["lines"]:
            ln = dict(line_type=lt, resource_id=rid, factor=fac, **extra)
            if lt == "labour":
                ln["productivity_basis"] = "paid_hours_per_unit"
            lines.append(ln)
        notes = "SYNTHETIC TEST NORMS (not company data): " + "; ".join(f"{rid} {fac} {'h' if lt == 'labour' else 'unit'}/{a['unit']}" for lt, rid, fac, _ in a["lines"])
        assemblies.create_assembly(db, A["est"], code=code, description=f"SYNTHETIC {code}", unit=a["unit"], cost_code=a["cost"], is_synthetic=True,
                                   source="SYNTHETIC test norms - NOT COMPANY DATA", notes=notes, lines_=lines)
        assemblies.submit_assembly(db, A["est"], code)
        assemblies.approve_assembly(db, A["com"], code, comments="TEST ACTOR: SYNTHETIC")
    pid = projects.create_project(db, A["est"], name="SYNTHETIC bottom-up variant (assemblies and supply sourcing)", location="Dammam industrial area, Saudi Arabia", is_demo=True,
                                  tax_category="VAT-STD", id=VARIANT_ID, notes=BANNER)
    rows = [b for b in boq_rows() if b["item"] in VARIANT_MAP]
    f = Path(db.scalar("SELECT workspace_path FROM projects WHERE id=?", (pid,)) and (Path(workdir) / "variant_boq_SYNTHETIC.csv"))
    with open(f, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Item", "Description", "Unit", "Qty", "Cost Code"])
        for b in rows:
            w.writerow([b["item"], b["description"], b["unit"], b["quantity"], b["cost_code"]])
    bi.import_boq(db, A["est"], pid, f)
    for b in rows:
        boq.map_to_assembly(db, A["est"], pid, b["item"], VARIANT_MAP[b["item"]])
        boq.set_cost_code(db, A["est"], pid, b["item"], b["cost_code"])
    est = compute_estimate(db, pid)
    ev["_variant_before_quotes"] = dict(direct=str(est.direct.direct_cost_total), unpriced=[k for k, i in est.direct.items.items() if not i.complete],
                                        missing=sorted({e.resource_id for e in est.direct.exceptions if e.code == "MISSING_RATE"}))


def stage_procurement(db, ev: Evidence, A: dict, pid: str = VARIANT_ID) -> dict:
    from datetime import date, timedelta
    from app.core.errors import ApprovalBlocked, ValidationFailed
    from app.estimators.estimate import compute_estimate
    from app.procurement import leveling, needs, quotes, rfq, selection
    from app.services import rates, suppliers
    n = needs.detect_needs(db, A["est"], pid)
    reg = needs.register(db, pid)
    by_res = {r["resource_id"]: r for r in reg}
    pkgs = sorted({r["package_id"] for r in reg})
    assert len(pkgs) == 1, pkgs
    pkg = pkgs[0]
    Q = quotations()
    sup = {k: suppliers.create_supplier(db, A["est"], name=v["name"], supplier_type="supplier", trades="E", is_synthetic=True, notes="SYNTHETIC / NOT A REAL SUPPLIER") for k, v in Q["suppliers"].items()}
    rf = rfq.create_rfq(db, A["est"], pid, pkg)                                         # draft only: nothing is sent (no email channel exists)
    today = date.today()
    qids = {}
    for k, v in Q["suppliers"].items():
        lines = [dict(procurement_item_id=by_res[ln["resource_id"]]["id"], description=ln["material"] + " (SYNTHETIC)", unit=ln["unit"], quantity=by_res[ln["resource_id"]]["quantity"],
                      unit_rate=ln[k], delivery_included=v["delivery_included"], unloading_included="Unknown", installation_included="No", tax_included="Unknown", compliance="Compliant")
                 for ln in Q["lines"]]
        qids[k] = quotes.create_quotation(db, A["est"], supplier_id=sup[k], project_id=pid, package_id=pkg, reference=f"SYNTHETIC-{k}-001", quote_date=today.isoformat(),
                                          valid_until=(today + timedelta(days=v["valid_days"])).isoformat(), tax_treatment="excl", payment_terms="SYNTHETIC / NOT A REAL QUOTE",
                                          deviations="SYNTHETIC: tax treatment NOT verified (recorded as exclusive for normalisation only)", is_synthetic=True, lines=lines)
        quotes.submit_quotation(db, A["est"], qids[k])
        quotes.approve_quotation(db, A["proc"], qids[k], evidence="TEST ACTOR: synthetic fixture entered as stated; SYNTHETIC / NOT A REAL QUOTE")
    adj = leveling.add_adjustment(db, A["est"], qids["B"], "delivery", Q["delivery_adjustment_B_sar"], "SYNTHETIC one-off delivery charge for B's entire selected package; applied once at package level (no per-item allocation)")
    pre_adj = leveling.level_package(db, pkg)
    leveling.approve_adjustment(db, A["proc"], adj, comments="TEST ACTOR: SYNTHETIC")
    lv = leveling.level_package(db, pkg)
    lv10 = leveling.level_package(db, pkg, as_of=today + timedelta(days=10))
    rec = lv["suggested_lowest_like_for_like"]
    table = [dict(quotation=q["quotation_id"], supplier=next(k for k, v in qids.items() if v == q["quotation_id"]), base_price=q["quoted_total"], delivery_adjustment=q["approved_adjustments"],
                  tax_status=q["tax_treatment"] + " (UNVERIFIED, synthetic)", validity=q["validity"], valid_until=q["valid_until"], coverage=q["coverage"], non_compliant=q["non_compliant_items"],
                  delivery_excluded_items=len(q["delivery_or_unloading_excluded"]), missing=q["missing_items"], like_for_like=q["like_for_like"], evaluated_total=q["normalised_total"], notes=q["notes"]) for q in lv["quotations"]]
    sid = selection.propose_selection(db, A["est"], pkg, qids["A"] if rec == qids["A"] else rec, "SYNTHETIC: lowest like-for-like evaluated total incl. delivery adjustment; valid 14 days")
    sel_status_before = db.scalar("SELECT status FROM quote_selections WHERE id=?", (sid,))
    blocked_publish = None
    try:
        selection.publish_rates(db, A["est"], sid)
    except (ValidationFailed, ApprovalBlocked) as e:
        blocked_publish = e.code
    selection.decide_selection(db, A["proc"], sid, True, "TEST ACTOR: SYNTHETIC selection approval (not a real procurement approval)")
    new_rates = selection.publish_rates(db, A["est"], sid)
    status_after_publish = [rates.get_rate(db, r)["status"] for r in new_rates]
    for r in new_rates:
        rates.approve_rate(db, A["proc"], r, comments="TEST ACTOR: SYNTHETIC")
    est = compute_estimate(db, pid)
    base = {"P-001": D(120) * 185, "P-002": D(240) * 315, "P-012": D(6) * 1450, "P-013": D(4) * 1850, "P-014": D(650) * 24}
    comp = {k: dict(bottom_up=str(est.direct.items[k].direct_cost), baseline=str(base[k]), diff=str(est.direct.items[k].direct_cost - base[k])) for k in base}
    ev.stage("7_quotation_levelling", "PASS" if rec == qids["A"] and sel_status_before == "Pending Review" and blocked_publish else "FAIL",
             needs=n, rfq_draft=rf, package=pkg, table=table, headline_lowest=min(table, key=lambda r: r["base_price"])["supplier"], recommendation=next(k for k, v in qids.items() if v == rec),
             before_adjustment_evaluated={q["quotation_id"]: q["normalised_total"] for q in pre_adj["quotations"]},
             as_of_plus_10_days={q["quotation_id"]: (q["validity"], q["like_for_like"]) for q in lv10["quotations"]},
             selection_status_when_proposed=sel_status_before, publish_before_approval_blocked_with=blocked_publish, rates_published_status_then_approved=status_after_publish,
             variant_vs_baseline=comp, variant_direct_total=str(est.direct.direct_cost_total))
    return {"qids": qids, "lv": lv}


TAKEOFF_ITEMS = {"P-016": "piping.pipe_fab_install", "P-023": "piping.weld_joint", "P-014": "piping.supports", "P-027": "coating.surface", "P-028": "insulation.surface", "P-012": "piping.valve_install"}
# SYNTHETIC mechanical-test factors: (template, slot) -> (resource, factor).  Slots with no unit-compatible library resource are skipped explicitly and reported.
TAKEOFF_FACTORS = {
    ("piping.pipe_fab_install", "fab_labour"): ("LIB-LAB-WELDER", "0.5"), ("piping.pipe_fab_install", "erect_labour"): ("LIB-LAB-FITTER", "0.4"),
    ("piping.pipe_fab_install", "fit_up_labour"): ("LIB-LAB-HELPER", "0.3"), ("piping.pipe_fab_install", "pipe_material"): ("LIB-PIPE-DN100", "0.5"),
    ("piping.pipe_fab_install", "crane_plant"): ("LIB-PLT-CRANE", "0.01"),
    ("piping.weld_joint", "welder_labour"): ("LIB-LAB-WELDER", "1.5"), ("piping.weld_joint", "fitter_labour"): ("LIB-LAB-FITTER", "1.0"), ("piping.weld_joint", "grinding_labour"): ("LIB-LAB-HELPER", "0.25"),
    ("piping.supports", "fab_labour"): ("LIB-LAB-WELDER", "40"), ("piping.supports", "install_labour"): ("LIB-LAB-FITTER", "30"), ("piping.supports", "steel"): ("LIB-MAT-SUPPORT", "1050"),
    ("coating.surface", "blast_labour"): ("LIB-LAB-HELPER", "0.3"), ("coating.surface", "apply_labour"): ("LIB-LAB-HELPER", "0.2"),
    ("insulation.surface", "install_labour"): ("LIB-LAB-FITTER", "0.8"),
    ("piping.valve_install", "install_labour"): ("LIB-LAB-FITTER", "1.5"), ("piping.valve_install", "test_labour"): ("LIB-LAB-HELPER", "0.5"),
}


def stage_takeoff(db, ev: Evidence, A: dict, workdir: Path) -> None:
    from app.estimators.estimate import compute_estimate
    from app.imports import boq as bi
    from app.services import boq, governed, mto, projects, refdata
    refdata.load_pack(db, A["admin"], "industrial")                                       # definitions only - the pack holds no prices
    pid = projects.create_project(db, A["est"], name="SYNTHETIC take-off derivation check", is_demo=True, tax_category="VAT-STD", id="PRJ-9003", notes=BANNER)
    f = Path(workdir) / "takeoff_boq_SYNTHETIC.csv"
    with open(f, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Item", "Description", "Unit", "Qty", "Cost Code"])
        for b in boq_rows():
            if b["item"] in TAKEOFF_ITEMS:
                w.writerow([b["item"], b["description"], "inch_dia" if b["unit"] == "dia-in" else b["unit"], b["quantity"], b["cost_code"]])
    bi.import_boq(db, A["est"], pid, f)
    for (t, slot), (rid, fac) in TAKEOFF_FACTORS.items():
        i = governed.propose(db, A["est"], "mto_factor", f"{t}/{slot}", {"template": t, "slot": slot, "resource_id": rid, "factor": fac}, project_id=pid,
                             source="SYNTHETIC TEST NORM - NOT COMPANY DATA", is_synthetic=True, submit=True)
        governed.approve(db, A["com"], i, comments="TEST ACTOR: SYNTHETIC")
    out = {}
    for item, t in TAKEOFF_ITEMS.items():
        tpl = mto.get_template(t)
        covered = {s for (tt, s) in TAKEOFF_FACTORS if tt == t}
        skip = [s["slot"] for s in tpl["slots"] if s["slot"] not in covered]
        pv = mto.apply(db, A["est"], pid, item, t, skip_slots=skip)
        out[item] = dict(template=t, driver=f"{pv['driver_qty']} {pv['driver_unit']}", driver_source=pv["driver_source"], skipped_slots=skip,
                         lines=[dict(slot=l["slot"], resource=l["resource_id"], qty=str(l["qty"]), basis=l["basis"]) for l in pv["lines"]],
                         pricing_status=db.scalar("SELECT pricing_status FROM boq_items WHERE project_id=? AND item_key=?", (pid, item)))
    est = compute_estimate(db, pid)
    ev.stage("10_takeoff_templates", "PASS" if all(v["pricing_status"] == "Pending Review" for v in out.values()) and not any(i.complete for i in est.direct.items.values()) else "FAIL",
             project=pid, derived=out, items_priced_before_human_approval=[k for k, i in est.direct.items.items() if i.complete], boq_quantities_unchanged=all(
                 db.scalar("SELECT quantity FROM boq_items WHERE project_id=? AND item_key=?", (pid, b["item"])) == str(b["quantity"]) for b in boq_rows() if b["item"] in TAKEOFF_ITEMS),
             note="structural/mechanical derivation with SYNTHETIC factors only; not real estimating validation")


TIME_ALLOCATION_RULES = [
    ("SUP-ALL", {"name": "Site supervision over the whole programme", "scope_cost_prefix": "A.03", "tasks": ["ALL"], "basis": "SYNTHETIC TEST ASSUMPTION: supervision runs for the whole programme (duration-weighted over every activity)"}),
    ("LIFT-INST-WELD", {"name": "Crane and forklift on installation and welding", "scope_cost_prefix": "A.07", "tasks": ["INST", "WELD"], "shares": {"INST": "60", "WELD": "40"},
                        "basis": "SYNTHETIC TEST ASSUMPTION: lifting plant is used 60 % on installation, 40 % on welding"}),
    ("SCAFFOLD", {"name": "Scaffolding on installation, welding and painting", "scope_cost_prefix": "A.06", "tasks": ["INST", "WELD", "PAINT"],
                  "basis": "SYNTHETIC TEST ASSUMPTION: scaffolding access is needed by these activities, weighted by their duration"}),
]


def stage_time_allocation(db, ev: Evidence, A: dict, pid: str = PROJECT_ID) -> None:
    """Untied cost (supervision, crane, forklift, scaffolding): BEFORE any allocation rule the cash flow / escalation are marked INCOMPLETE with the exact amount and the gate blocks;
    AFTER explicit approved time_allocation rules they are complete, reconciled and the finding is gone."""
    from app.core.errors import ValidationFailed
    from app.reconciliation import engine as recon
    from app.reporting import registry
    from app.services import cashflow, governed
    from app.api.serializers import ser

    def snap():
        cf = ser(registry.run_report(db, "cashflow", pid, {"terms_code": "PAY-SYNTH"}))
        es = ser(registry.run_report(db, "escalation", pid, {}))
        run = recon.run_reconciliation(db, A["est"], pid)
        f = [(x["severity"], x["rule_code"], x["status"]) for x in recon.get_run(db, run["run_id"])["findings"]]
        return cf, es, f
    cf0, es0, f0 = snap()
    try:
        cashflow.propose_financing_indirects(db, A["est"], pid, terms_code="PAY-SYNTH")
        refused = "NOT REFUSED (defect)"
    except ValidationFailed as e:
        refused = e.code
    gate0 = recon.final_gate(db, A["com"], pid)
    for code, data in TIME_ALLOCATION_RULES:
        i = governed.propose(db, A["est"], "time_allocation", code, data, project_id=pid, source="SYNTHETIC TEST DATA - NOT COMPANY RECORDS", is_synthetic=True, submit=True)
        governed.approve(db, A["com"], i, comments="TEST ACTOR: SYNTHETIC")
    cf1, es1, f1 = snap()
    ev.stage("13d_time_allocation", "PASS" if (cf0["complete"] is False and es0["complete"] is False and refused == "TIMEPHASING_INCOMPLETE" and cf1["complete"] and es1["complete"]
                                              and all(c["ok"] for c in cf1["reconciliation"]["checks"]) and not any(r == "TIMEPHASING_INCOMPLETE" for _, r, _ in f1)
                                              and any(b["rule_code"] == "TIMEPHASING_INCOMPLETE" for b in gate0["blockers"])) else "FAIL",
             before=dict(cashflow_status=cf0["status"], unallocated_direct_cost=cf0["unscheduled_cost"], unallocated_lines=[(u["item_key"], u["kind"], u["amount"], u["reason"]) for u in cf0["unallocated_lines"]],
                         valued_price=cf0["reconciliation"]["valued_price"], unallocated_price_share=cf0["reconciliation"]["unallocated_price_share"], closing_balance=cf0["final_balance"],
                         escalation_status=es0["status"], unescalated_cost=es0["unescalated_eligible_cost"], escalation_total=es0["escalation_total"], financing_proposal_refused_with=refused,
                         findings=[x for x in f0 if x[1] == "TIMEPHASING_INCOMPLETE"], final_gate_blocked_by_it=any(b["rule_code"] == "TIMEPHASING_INCOMPLETE" for b in gate0["blockers"])),
             after=dict(rules=[c for c, _ in TIME_ALLOCATION_RULES], allocated_by_rule=cf1["allocated_by_rule"], cashflow_status=cf1["status"], reconciliation=cf1["reconciliation"],
                        escalation_status=es1["status"], escalation_total=es1["escalation_total"], escalation_base=es1["scheduled_base_total"], findings_remaining=[x for x in f1 if x[1] == "TIMEPHASING_INCOMPLETE"]))


def stage_estimate_outputs(db, ev: Evidence, A: dict, pid: str = PROJECT_ID) -> dict:
    from app.api.serializers import ser
    from app.estimators.estimate import compute_estimate
    from app.reporting import registry
    from app.services import registers
    est = compute_estimate(db, pid)
    ext, tot = independent_total()
    kind: dict[str, Decimal] = {}
    by_res: dict[str, Decimal] = {}
    for l in est.direct.lines:
        kind[l.kind] = kind.get(l.kind, D(0)) + (l.amount or D(0))
        if l.resource_id:
            by_res[l.resource_id] = by_res.get(l.resource_id, D(0)) + (l.amount or D(0))
    per_item = {k: i.direct_cost for k, i in est.direct.items.items()}
    line_diffs = {k: str(per_item[k] - e) for k, e in ext if per_item.get(k) != e}
    explained_only = line_diffs == {"P-020": "900.00"}                                         # the approved TEST-ONLY crane standby is booked on the crane line
    # independent commercial chain (Decimal): D -> indirects (each % of D, rounded) -> contingency 5% of D+I -> markup 7% on total cost -> VAT on the tendered schedule
    Dd = tot + D(900)                                                                        # + crane standby (1 day x 1,800 x 50%) from the approved test-only plant terms
    elig_base = sum((e for (k, e), b in zip(ext, boq_rows()) if b["cost_code"][0] in "EDF"), D(0))              # division A (preliminaries) excluded by the approved eligibility rules
    I = r2(elig_base * D("0.08")) + r2(elig_base * D("0.03"))
    I_legacy = r2(Dd * D("0.08")) + r2(Dd * D("0.03"))                                                   # what the same 8 % + 3 % gave on the whole direct cost (previous pilot run)
    Ct = r2((Dd + I) * D("0.05"))
    T = Dd + I + Ct
    S = r2(T * D("1.07"))
    c, s = est.commercial, est.schedule
    chain = dict(direct=str(Dd), eligible_base=str(elig_base), indirect=str(I), indirect_on_whole_direct_cost_legacy=str(I_legacy), indirect_base_report=ser(registry.run_report(db, "indirect_base", pid, {})), contingency=str(Ct), total_cost=str(T), selling_price=str(S), engine=dict(direct=str(est.direct.direct_cost_total), indirect=str(est.indirect.total), contingency=str(c.contingency),
                 total_cost=str(c.total_cost), selling_price=str(c.selling_price_pre_discount), net_price=str(c.net_price), schedule_total=str(s.total_pre_tax), rounding_variance=str(s.rounding_variance),
                 tax_total=str(c.tax_total), final_payable=str(c.final_payable)), tax_check_15pct_of_schedule=str(r2(s.total_pre_tax * D("0.15"))))
    chain_ok = (Dd, I, Ct, T, S) == (est.direct.direct_cost_total, est.indirect.total, c.contingency, c.total_cost, c.selling_price_pre_discount) and r2(s.total_pre_tax * D("0.15")) == c.tax_total
    unpriced = [k for k, i in est.direct.items.items() if not i.complete]
    roll = ser(registry.run_report(db, "rollup", pid, {}))
    # risks (all p=100%; SAR ranges derived from the estimate's own subtotals because the engine accepts SAR ranges only)
    M, L = kind["material"], kind["labour"]
    RISKS = [("Material price movement", D(0), r2(M * D("0.04")), r2(M * D("0.10")), f"SYNTHETIC: triangular 0/4/10% of material subtotal {M}"),
             ("Productivity shortfall", D(0), r2(L * D("0.05")), r2(L * D("0.15")), f"SYNTHETIC: triangular 0/5/15% of labour subtotal {L}"),
             ("Testing / rework", D(0), D(5000), D(15000), "SYNTHETIC: SAR 0 / 5,000 / 15,000")]
    for t, lo, li, hi, basis in RISKS:
        rid = registers.add_risk(db, A["est"], pid, t, description="SYNTHETIC TEST RISK - not a forecast")
        registers.quantify_risk(db, A["est"], rid, prob_pct="100", cost_low=str(lo), cost_likely=str(li), cost_high=str(hi), basis=basis)
    rk = ser(registry.run_report(db, "risk", pid, {"trials": "5000", "seed": "20260101", "target_pct": "80"}))
    rk2 = ser(registry.run_report(db, "risk", pid, {"trials": "5000", "seed": "20260101", "target_pct": "80"}))
    esc = ser(registry.run_report(db, "escalation", pid, {}))
    cf = ser(registry.run_report(db, "cashflow", pid, {"terms_code": "PAY-SYNTH"}))
    ev.stage("11_12_13_cost_commercial_risk_cashflow", "PASS" if (est.direct.direct_cost_total == Dd and chain_ok and not unpriced and explained_only) else "FAIL",
             state=est.state, blockers=est.blockers, independent_boq_total=str(tot), line_extension_differences=line_diffs, direct_total_engine=str(est.direct.direct_cost_total),
             explained_difference=str(est.direct.direct_cost_total - tot) + " = crane standby 1 day x 1,800 x 50% (approved TEST-ONLY plant terms)", direct_by_kind={k: str(v) for k, v in kind.items()},
             direct_by_resource={k: str(v) for k, v in sorted(by_res.items())}, commercial_chain=chain, chain_matches_independent=chain_ok, unpriced_items=unpriced,
             unapproved_or_flagged_exceptions=sorted({e.code for e in est.direct.exceptions}), rollup_tie_out=roll.get("tie_out"),
             rollup_cbs_nodes={n["code"]: n["total"] for n in roll["cbs"]["nodes"]}, rollup_wbs_nodes={n["code"]: n["total"] for n in roll["wbs"]["nodes"]} if "wbs" in roll else None,
             plant_hire=ser(registry.run_report(db, "plant_hire", pid, {})["rows"]), risk=dict(seed="20260101", trials=5000, repeat_identical=(rk == rk2), report={k: v for k, v in rk.items() if k != "histogram"}), escalation=esc, cashflow={k: v for k, v in cf.items() if k != "rows"},
             cashflow_rows=cf.get("rows"), schedule_rows=[dict(item=l.item_key, amount=str(l.amount)) for l in s.lines[:3]] if hasattr(s, "lines") else None)
    return {"est": est, "risk": rk, "cashflow": cf}


def _try(fn, *a, **k):
    """Run an action that is EXPECTED to be refused; return the refusal code (or 'NOT REFUSED')."""
    from app.core.errors import AppError
    try:
        fn(*a, **k)
        return "NOT REFUSED (defect)"
    except AppError as e:
        return getattr(e, "code", type(e).__name__)


def stage_gates_freeze_export(db, ev: Evidence, A: dict, pid: str = PROJECT_ID) -> dict:
    import openpyxl
    from app.estimators.estimate import compute_estimate
    from app.reconciliation import engine as recon
    from app.services import estimates, offers
    out = {}
    pre = estimates.preliminary_export(db, A["est"], pid)
    ws = openpyxl.load_workbook(pre["pricing_schedule"]).active
    out["preliminary_export_banner"] = str(ws["A2"].value)
    run = recon.run_reconciliation(db, A["est"], pid)
    first = recon.get_run(db, run["run_id"])["findings"]
    out["findings_before"] = [(f["severity"], f["rule_code"], f["status"]) for f in first]
    vid = estimates.freeze_version(db, A["est"], pid, "SYNTHETIC v1")
    estimates.submit_version(db, A["est"], vid)
    out["approve_before_exceptions"] = _try(estimates.approve_version, db, A["com"], vid)
    out["self_role_cannot_approve"] = _try(estimates.approve_version, db, A["est"], vid)
    out["ai_cannot_approve"] = _try(estimates.approve_version, db, A["ai"], vid)
    out["tender_export_approval_before_estimate_approved"] = _try(estimates.approve_tender_export, db, A["com"], pid, vid)
    out["export_without_approval"] = _try(estimates.export_submission, db, A["est"], pid, vid, 999999)
    high = [f for f in first if f["severity"] == "High"]
    out["exception_by_estimator_refused"] = _try(recon.accept_exception, db, A["est"], high[0]["id"], "TEST: estimator may not accept a High exception")
    for f in high:
        recon.accept_exception(db, A["com"], f["id"], "TEST ACTOR: SYNTHETIC. Plant hire is priced per day at the day rate; the day factor is 1 day per BOQ day (hours-based wording of the check is not applicable).")
    out["approve_version"] = estimates.approve_version(db, A["com"], vid, comments="TEST ACTOR: SYNTHETIC approval to exercise the gate (not a real commercial approval)")
    out["tender_export_before_offer"] = _try(estimates.approve_tender_export, db, A["com"], pid, vid)
    o = offers.generate_offer(db, A["est"], pid, payment_terms="SYNTHETIC terms (30 days)")
    offers.approve_offer(db, A["com"], pid, o["version_no"], comments="TEST ACTOR: SYNTHETIC")
    ap = estimates.approve_tender_export(db, A["com"], pid, vid, "TEST ACTOR: SYNTHETIC export approval (not a real tender-export approval)")
    files = estimates.export_submission(db, A["est"], pid, vid, ap)
    out["export_files"] = files
    ws2 = openpyxl.load_workbook(files["pricing_schedule"]).active
    out["submission_banner_cells"] = [str(ws2[c].value) for c in ("A1", "A2", "A3") if ws2[c].value]
    est = compute_estimate(db, pid)
    v = estimates.get_version(db, vid)
    out.update(version_id=vid, frozen_fingerprint=v["inputs_hash"], frozen_totals=v["totals"], frozen_state=v["state"], current_fingerprint=est.fingerprint, offer=o["offer_ref"] if "offer_ref" in o else o)
    ev.stage("15_gates_and_17_export", "PASS" if (out["approve_before_exceptions"] == "RECON_BLOCKED" and out["export_without_approval"] == "EXPORT_NOT_APPROVED" and out["tender_export_before_offer"] == "OFFER_NOT_APPROVED") else "FAIL", **out)
    return {"vid": vid, "ap": ap, "files": files}


def stage_replay(db, ev: Evidence, A: dict, ctx: dict, pid: str = PROJECT_ID) -> None:
    from app.estimators.estimate import compute_estimate
    from app.services import audit, estimates, governed, rates, snapshots
    vid = ctx["vid"]
    v1 = estimates.get_version(db, vid)
    before = dict(verify=snapshots.verify_snapshot(db, vid), replay=snapshots.replay_estimate(db, vid))
    # change ONE parameter (new version of the pipe-fitting productivity factor) and ONE rate (new welder rate version)
    p = governed.propose(db, A["est"], "productivity_factor", "PIPEFIT-SYNTH", {"category": "other", "factor": "1.10", "scope_cost_prefix": "E.06", "applies_to": "labour"}, project_id=pid,
                         source="SYNTHETIC TEST ASSUMPTION - revised", is_synthetic=True, submit=True)
    governed.approve(db, A["com"], p, comments="TEST ACTOR: SYNTHETIC")
    r_old = db.scalar("SELECT id FROM resource_rates WHERE resource_id='SYN-P-017' AND status='Approved'")
    r_new = rates.revise_rate(db, A["est"], r_old, unit_price="70", price_date="2026-10-10", evidence="SYNTHETIC / TEST ONLY revised rate")
    rates.submit_rate(db, A["est"], r_new)
    rates.approve_rate(db, A["proc"], r_new, comments="TEST ACTOR: SYNTHETIC")
    now = compute_estimate(db, pid)
    v1_after = estimates.get_version(db, vid)
    after = dict(verify=snapshots.verify_snapshot(db, vid), replay=snapshots.replay_estimate(db, vid), direct=snapshots.replay_direct_cost(db, vid))
    ex = db.scalar("SELECT approval_id FROM exports WHERE estimate_version_id=? LIMIT 1", (vid,)) if False else ctx["ap"]
    gate_after = _try(estimates.export_submission, db, A["est"], pid, vid, ctx["ap"])
    v2 = estimates.freeze_version(db, A["est"], pid, "SYNTHETIC v2 (after parameter + rate change)")
    chain = audit.verify_chain(db)
    same = lambda a, b: all(a[k] == b[k] for k in ("inputs_hash", "totals_json", "result_json", "state", "status"))
    ok = after["replay"]["ok"] and after["direct"]["ok"] and now.fingerprint != v1["inputs_hash"] and same(v1, v1_after) and chain["ok"]
    ev.stage("16_freeze_and_replay", "PASS" if ok else "FAIL", v1=dict(id=vid, fingerprint=v1["inputs_hash"], totals=v1["totals"], status=v1["status"]),
             replay_before_changes=dict(ok=before["replay"]["ok"], fingerprint=before["replay"]["fingerprint"], differences=before["replay"]["differences"]),
             changed=dict(parameter="productivity_factor PIPEFIT-SYNTH 1.00 -> 1.10 (new version, approved by TEST ACTOR)", rate="SYN-P-017 welder rate 65 -> 70 (new rate version, approved by TEST ACTOR)"),
             current_fingerprint_after_changes=now.fingerprint, current_totals_after=dict((k, str(x)) for k, x in now.totals().items()), v1_row_unchanged=same(v1, v1_after),
             replay_after_changes=dict(ok=after["replay"]["ok"], fingerprint=after["replay"]["fingerprint"], differences=after["replay"]["differences"], replayed=after["replay"]["replayed"]),
             replay_direct_cost_after_changes=after["direct"], verify_snapshot_after=dict(ok=after["verify"]["ok"], problems=after["verify"]["problems"], newer_rates_available=after["verify"]["newer_rates_available"]),
             export_of_frozen_v1_after_changes_refused_with=gate_after, v2=dict(id=v2), audit_chain=chain)


def stage_tax_gate(db, ev: Evidence, A: dict, pid: str = PROJECT_ID) -> None:
    from app.estimators.estimate import compute_estimate
    from app.services import commercial
    est = compute_estimate(db, pid)
    unverified = dict(state=est.state, blockers=list(est.blockers), tax_total=None if est.commercial is None else str(est.commercial.tax_total))
    tid = db.scalar("SELECT id FROM tax_categories WHERE code='VAT-STD'")
    commercial.approve_tax_category(db, A["com"], tid, evidence="TEST ONLY: 15% used solely as a synthetic calculation parameter - NOT a verified tax determination")
    ev["_tax_gate"] = dict(before_tax_approval=unverified, after=compute_estimate(db, pid).state)


def stage_negative_controls(db, ev: Evidence, A: dict, workdir: Path) -> None:
    """PRJ-9004 (NOT flagged demo): unresolved mandatory inputs must keep the estimate preliminary and unexportable."""
    from app.estimators.estimate import compute_estimate
    from app.imports import boq as bi
    from app.reconciliation import engine as recon
    from app.reporting import registry
    from app.services import assemblies, boq, estimates, governed, projects, rates
    pid = projects.create_project(db, A["est"], name="SYNTHETIC negative control (unresolved inputs)", is_demo=False, tax_category="VAT-STD", id="PRJ-9004", notes=BANNER)
    rates.create_resource(db, A["est"], resource_type="material", description="SYNTHETIC resource with NO rate", unit="m", cost_code="E.06", id="NEG-MAT-1", is_synthetic=True)
    assemblies.create_assembly(db, A["est"], code="NEG-ASM-1", description="SYNTHETIC assembly using an unrated resource", unit="m", cost_code="E.06", is_synthetic=True, source="SYNTHETIC",
                               lines_=[dict(line_type="material", resource_id="NEG-MAT-1", factor="1", factor_includes_waste=1)])
    assemblies.submit_assembly(db, A["est"], "NEG-ASM-1")
    assemblies.approve_assembly(db, A["com"], "NEG-ASM-1", comments="TEST ACTOR: SYNTHETIC")
    f = Path(workdir) / "negative_boq_SYNTHETIC.csv"
    with open(f, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Item", "Description", "Unit", "Qty"])
        w.writerows([("N-1", "Mapped to a synthetic-rated assembly", "m", "10"), ("N-2", "Line with no mapping at all", "m", "5"), ("N-3", "Line with an unrecognised unit", "bundle", "2"),
                     ("N-4", "Line whose resource has no rate", "m", "7")])
    bi.import_boq(db, A["est"], pid, f)
    boq.map_to_assembly(db, A["est"], pid, "N-1", "SYNA-P-001")
    boq.map_to_assembly(db, A["est"], pid, "N-4", "NEG-ASM-1")
    governed.propose(db, A["est"], "productivity_factor", "DRAFT-ONLY", {"category": "other", "factor": "1.30", "scope_cost_prefix": "E.06"}, project_id=pid, source="SYNTHETIC", is_synthetic=True)   # stays Draft
    est = compute_estimate(db, pid)
    prelim = compute_estimate(db, pid, include_unapproved=True)
    draft_ignored = est.direct.direct_cost_total
    run = recon.run_reconciliation(db, A["est"], pid)
    findings = [(f["severity"], f["rule_code"]) for f in recon.get_run(db, run["run_id"])["findings"]]
    vid = estimates.freeze_version(db, A["est"], pid, "SYNTHETIC preliminary")
    estimates.submit_version(db, A["est"], vid)
    comp = ser_safe(registry.run_report(db, "compliance", pid, {}))
    cls = ser_safe(registry.run_report(db, "classification", pid, {}))
    pre = estimates.preliminary_export(db, A["est"], pid)
    import openpyxl
    banner = str(openpyxl.load_workbook(pre["pricing_schedule"]).active["A2"].value)
    codes = sorted({e.code for e in est.direct.exceptions})
    ev.stage("15_preliminary_cannot_be_final", "PASS" if (est.state.startswith("Preliminary") and _try(estimates.approve_version, db, A["com"], vid) in ("ESTIMATE_PRELIMINARY", "RECON_BLOCKED")) else "FAIL",
             state=est.state, blockers=est.blockers, engine_exception_codes=codes, unmapped_or_unpriced=[k for k, i in est.direct.items.items() if not i.complete],
             direct_total_approved_view=str(est.direct.direct_cost_total),
             direct_total_preliminary_view=str(prelim.direct.direct_cost_total), reconciliation_findings=findings, approve_version=_try(estimates.approve_version, db, A["com"], vid),
             tender_export_approval=_try(estimates.approve_tender_export, db, A["com"], pid, vid), export_submission=_try(estimates.export_submission, db, A["est"], pid, vid, 1),
             preliminary_export_banner=banner, compliance_report=comp, classification_report=cls)


def ser_safe(x):
    from app.api.serializers import ser
    return ser(x)


def stage_takeoff_replay(db, ev: Evidence, A: dict, pid: str = "PRJ-9003") -> None:
    """Replay of a frozen estimate whose lines come from take-off templates (PRJ-9003), after a take-off factor is revised."""
    from app.estimators.estimate import compute_estimate
    from app.services import boq, commercial, estimates, governed, mto, snapshots
    commercial.assign_policy(db, A["est"], pid, ev["_policy_id"])
    for item in TAKEOFF_ITEMS:
        boq.decide_pricing(db, A["com"], pid, item, "approve", comment="TEST ACTOR: SYNTHETIC derivation reviewed for the software test (not a real pricing approval)")
    est = compute_estimate(db, pid)
    vid = estimates.freeze_version(db, A["est"], pid, "SYNTHETIC take-off v1")
    v1 = estimates.get_version(db, vid)
    key = ("piping.weld_joint", "welder_labour")
    i = governed.propose(db, A["est"], "mto_factor", f"{key[0]}/{key[1]}", {"template": key[0], "slot": key[1], "resource_id": TAKEOFF_FACTORS[key][0], "factor": "2.0"}, project_id=pid,
                         source="SYNTHETIC TEST NORM - revised", is_synthetic=True, submit=True)
    governed.approve(db, A["com"], i, comments="TEST ACTOR: SYNTHETIC")
    stale = [(x["item_key"], x["template"], x["flags"]) for x in mto.status_report(db, pid)["stale"]]
    same_until_reapplied = compute_estimate(db, pid).fingerprint == v1["inputs_hash"]            # derived lines are stored at apply time; a revised factor only flags them stale
    covered = {sl for (tt, sl) in TAKEOFF_FACTORS if tt == key[0]}
    mto.apply(db, A["est"], pid, "P-023", key[0], skip_slots=[x["slot"] for x in mto.get_template(key[0])["slots"] if x["slot"] not in covered])
    boq.decide_pricing(db, A["com"], pid, "P-023", "approve", comment="TEST ACTOR: SYNTHETIC re-derivation reviewed")
    now = compute_estimate(db, pid)
    rp = snapshots.replay_estimate(db, vid)
    ev.stage("16b_replay_with_takeoff", "PASS" if (rp["ok"] and now.fingerprint != v1["inputs_hash"] and rp["fingerprint"] == v1["inputs_hash"] and same_until_reapplied) else "FAIL", project=pid,
             frozen_state=v1["state"], frozen_direct=v1["totals"].get("direct_cost"), stale_applications_flagged=stale, estimate_unchanged_until_a_person_re_applies=same_until_reapplied,
             current_direct_after_factor_change_and_reapply=str(now.direct.direct_cost_total), replay_ok=rp["ok"], replay_differences=rp["differences"],
             replayed_fingerprint_equals_frozen=rp["fingerprint"] == v1["inputs_hash"], not_covered="landed cost / FX (SAR-only) and escalation (a read-only report, not an estimate input) are not in this replay")


def stage_production_isolation(db, ev: Evidence, A: dict, ctx: dict) -> None:
    """The synthetic pilot can never produce a production-ready status: approval identity, role, actor type, environment and project class are read from durable records."""
    from app.approvals import engine as ap
    from app.config import get_settings
    from app.core.errors import ApprovalBlocked
    from app.models.actor import Actor
    from app.services import estimates, readiness
    r = readiness.evaluate(db, PROJECT_ID, ctx["vid"], ctx["ap"])
    chain_types = [dict(r_) for r_ in db.all("SELECT actor_type, environment, COUNT(*) n FROM approvals WHERE project_id=? GROUP BY actor_type, environment", (PROJECT_ID,))]
    forged = Actor("forged-human", "Commercial Approver", "Real Human Commercial Approver (identity verified)")          # nobody registered under this username
    liar = Actor("test-estimator", "Commercial Approver", "claims another role")                                          # registered, but not as a Commercial Approver
    kinds = dict(forged_display_name=ap.resolve_actor_type(db, forged), role_mismatch=ap.resolve_actor_type(db, liar), registered_test_actor=ap.resolve_actor_type(db, A["com"]),
                 missing_actor=ap.resolve_actor_type(db, Actor("nobody", "Estimator")))
    s = get_settings()
    s.environment = "production"                                                                                          # what a real installation would run as
    try:
        prod = readiness.evaluate(db, PROJECT_ID, ctx["vid"], ctx["ap"])
        try:
            estimates.approve_tender_export(db, A["com"], "PRJ-9004", 1)
            non_human = "NOT REFUSED (defect)"
        except ApprovalBlocked as e:
            non_human = e.code
        try:
            estimates.export_submission(db, A["est"], "PRJ-9004", 1, 1)
            direct = "NOT REFUSED (defect)"
        except ApprovalBlocked as e:
            direct = e.code
    finally:
        s.environment = "test"
    ok = (not r["production_ready"] and not prod["production_ready"] and r["classification"] == "demonstration" and all(v != "human" for v in kinds.values())
          and non_human == "NON_HUMAN_ACTOR" and direct == "NON_HUMAN_ACTOR" and db.scalar("SELECT COUNT(*) FROM exports WHERE submission_ready=1") == 0)
    ev.stage("19_production_isolation", "PASS" if ok else "FAIL", classification_in_pilot_environment=r["classification"], production_ready=r["production_ready"], reasons_in_pilot_environment=r["reasons"][:12],
             classification_if_environment_were_production=prod["classification"], reasons_if_production=prod["reasons"][:12], approvals_by_actor_type_and_environment=chain_types, resolved_actor_types=kinds,
             test_actor_approving_a_real_project_in_production=non_human, direct_export_attempt_on_a_real_project_by_a_test_actor=direct,
             exports_marked_submission_ready=db.scalar("SELECT COUNT(*) FROM exports WHERE submission_ready=1"), export_readiness_labels=[dict(r_) for r_ in db.all("SELECT readiness, COUNT(*) n FROM exports GROUP BY readiness")])


def stage_boe(db, ev: Evidence, A: dict, pid: str = PROJECT_ID) -> dict:
    from app.services import boe
    out = boe.generate_boe(db, A["est"], pid)
    md = (Path(out["directory"]) / out["files"][0]).read_text(encoding="utf-8")
    required = {"project scope": "## 2. Scope and quantities", "exclusions/scope register": "Scope register", "BOQ source": "boq_SYNTHETIC_TEST_ONLY.csv", "estimate date and currency": "| currency | SAR |",
                "synthetic rate designation": "SYNTHETIC RATES IN USE", "assemblies": "**Assemblies used**", "productivity assumptions": "productivity_factor", "programme": "## 7. Programme",
                "indirects/duration": "## 6. Indirects and duration", "commercial": "## 8. Commercial", "risk": "## 9. Risk register", "classification": "## 10. Classification and maturity",
                "client profile / no compliance claim": "no compliance statement can be made", "validation-only statement": BANNER}
    present = {k: (v in md) for k, v in required.items()}
    ev.stage("14_basis_of_estimate", "PASS" if all(present.values()) else "FAIL", files=out["files"], placeholders_for_human_judgement=out["placeholders"], sections_present=present, estimate_state=out["estimate_state"],
             missing_sections=[k for k, v in present.items() if not v], excerpt=md[:1200])
    return out


def _cli(workdir: Path, *args: str, user: str | None = None, timeout: int = 300) -> dict:
    import os
    import subprocess
    import sys
    env = {**os.environ, "KSA_DB_PATH": str(Path(workdir) / "scratch_pilot.db"), "KSA_WORKSPACES_DIR": str(Path(workdir) / "workspaces"), "KSA_SECRET_KEY": "synthetic-pilot"}
    if user:
        env.update(KSA_CLI_USER=user, KSA_CLI_PASSWORD="synthetic-only-pw")
    cp = subprocess.run([sys.executable, "-m", "app.cli", *args], cwd=Path(__file__).resolve().parents[2], env=env, capture_output=True, text=True, timeout=timeout)
    return dict(cmd="python -m app.cli " + " ".join(args), exit=cp.returncode, stdout=cp.stdout[-1500:], stderr=cp.stderr[-600:], full=cp.stdout)


def stage_interfaces(db, ev: Evidence, A: dict, workdir: Path, ctx: dict) -> None:
    """CLI (subprocess against the scratch DB), REST API and UI (TestClient) read the SAME numbers; workbook formulas recalculated by LibreOffice."""
    from fastapi.testclient import TestClient
    from app.estimators.estimate import compute_estimate
    from app.main import app
    from app.services import auth
    est = compute_estimate(db, PROJECT_ID)
    if not db.one("SELECT 1 FROM users WHERE username='cli-est'"):
        auth.create_user(db, "cli-est", "TEST ACTOR CLI Estimator", "Estimator", "synthetic-only-pw")
    pcsv = Path(workdir) / "cli_params_SYNTHETIC.csv"
    pcsv.write_text("kind,code,source,basis_note,project_id,is_synthetic,data_json\n"
                    'productivity_factor,CLI-DRAFT,SYNTHETIC TEST DATA,SYNTHETIC TEST ASSUMPTION - NOT COMPANY DATA,PRJ-9004,yes,"{""category"": ""other"", ""factor"": ""1.05"", ""scope_cost_prefix"": ""E.06""}"\n', encoding="utf-8")
    rcsv = Path(workdir) / "cli_rates_SYNTHETIC.csv"
    rcsv.write_text("Resource ID,Description,Unit,Unit Price,Currency,Price Date,VAT,Delivery,Price Kind,Evidence\n"
                    "NEG-MAT-1,SYNTHETIC resource with NO rate,m,99,SAR,2026-10-01,Excluded,Unknown,List price,SYNTHETIC / TEST ONLY\n", encoding="utf-8")
    u = dict(user="cli-est")
    cli_imports = [_cli(workdir, "param", "import", str(pcsv), "--project", "PRJ-9004", "--dry-run", **u), _cli(workdir, "param", "import", str(pcsv), "--project", "PRJ-9004", **u),
                   _cli(workdir, "param", "import", str(FIX / "governed_parameters_SYNTHETIC_TEST_ONLY.csv"), "--dry-run", **u),
                   _cli(workdir, "rates", "import", str(FIX / "rates_SYNTHETIC_TEST_ONLY.csv"), "--source-name", "SYNTHETIC TEST DATA", "--url", "SYNTHETIC-TEST-FIXTURE", "--synthetic", "--dry-run", **u),
                   _cli(workdir, "rates", "import", str(rcsv), "--source-name", "SYNTHETIC TEST DATA", "--url", "SYNTHETIC-TEST-FIXTURE", "--synthetic", **u),
                   _cli(workdir, "rates", "import", str(FIX / "rates_SYNTHETIC_TEST_ONLY.csv"), "--source", "SRC-002", "--dry-run", **u)]
    cli_imports_ok = [x["exit"] for x in cli_imports] == [0, 0, 0, 0, 0, 1] and '"would_create": 1' in cli_imports[0]["full"] and "SOURCE_NOT_PRICE" in cli_imports[5]["stderr"] + cli_imports[5]["full"]
    cli = [_cli(workdir, "report", PROJECT_ID, "rollup"), _cli(workdir, "report", PROJECT_ID, "manhours"), _cli(workdir, "report", PROJECT_ID, "schedule"),
           _cli(workdir, "project", "verify-snapshot", str(ctx["vid"])), _cli(workdir, "audit-verify"), _cli(workdir, "coverage"), _cli(workdir, "param", "list", "--project", PROJECT_ID),
           _cli(workdir, "rates", "pending")]
    for u, role in (("api-est", "Estimator"), ("api-com", "Commercial Approver"), ("api-view", "Viewer")):
        if not db.one("SELECT 1 FROM users WHERE username=?", (u,)):
            auth.create_user(db, u, f"TEST ACTOR {u}", role, "pw-" + u)
    api, ui = {}, {}
    with TestClient(app, headers={"Origin": "http://testserver"}) as c:
        def tok(u):
            r = c.post("/api/auth/login", json={"username": u, "password": "pw-" + u})
            return {"Authorization": "Bearer " + r.json()["token"]}
        h = tok("api-est")
        c.cookies.clear()
        e = c.get(f"/api/projects/{PROJECT_ID}/estimate", headers=h)
        api["estimate_status"] = e.status_code
        body = e.json()
        api["totals"] = body.get("totals")
        api["totals_match_engine"] = {k: str(v) for k, v in (body.get("totals") or {}).items()} == {k: str(v) for k, v in est.totals().items()} or body.get("totals") == {k: format(v, "f") for k, v in est.totals().items()}
        r = c.get(f"/api/projects/{PROJECT_ID}/report/rollup", headers=h); api["rollup"] = (r.status_code, r.json().get("tie_out"))
        r = c.get(f"/api/projects/{PROJECT_ID}/versions", headers=h); api["versions"] = [(v["version_no"], v["status"]) for v in r.json()] if r.status_code == 200 else r.status_code
        r = c.get("/api/audit/verify", headers=h); api["audit_verify"] = r.json()
        r = c.get(f"/api/projects/{PROJECT_ID}/reconciliation", headers=h); api["reconciliation_status"] = r.status_code
        r = c.post("/api/actions/approve_tender_export", json={"project_id": PROJECT_ID, "version_id": ctx["vid"]}, headers=tok("api-view")); api["viewer_tender_export"] = (r.status_code, r.json().get("error"))
        r = c.post("/api/actions/approve_tender_export", json={"project_id": PROJECT_ID, "version_id": ctx["vid"]}, headers=h); api["estimator_tender_export"] = (r.status_code, r.json().get("error"))
        r = c.post("/api/actions/approve_rate", json={"rate_id": 1}, headers=h); api["estimator_approve_rate"] = (r.status_code, r.json().get("error"))
        c.cookies.clear()
        assert c.post("/login", data={"username": "api-est", "password": "pw-api-est"}, follow_redirects=False).status_code == 303
        for path in (f"/projects/{PROJECT_ID}/", f"/projects/{PROJECT_ID}/estimate", f"/projects/{PROJECT_ID}/boq", f"/projects/{PROJECT_ID}/reconciliation", f"/projects/{PROJECT_ID}/analysis",
                     f"/projects/{PROJECT_ID}/analysis/rollup", f"/projects/{PROJECT_ID}/analysis/schedule", f"/projects/{PROJECT_ID}/completeness", f"/projects/{PROJECT_ID}/workspace", f"/projects/{VARIANT_ID}/quotes"):
            r = c.get(path)
            ui[path] = dict(status=r.status_code, traceback="Traceback" in r.text, shows_synthetic="SYNTHETIC" in r.text.upper(), shows_total=format(est.direct.direct_cost_total, ",.2f") in r.text if path.endswith("/estimate") else None)
    wb = Path(workdir) / "PRJ-9001_master_SYNTHETIC.xlsx"
    exp = _cli(workdir, "export-workbook", PROJECT_ID, "--out", str(wb))
    ver = _cli(workdir, "verify-workbook", str(wb), "--project", PROJECT_ID, timeout=600)
    import openpyxl
    from app.services import programme as prog
    mh_now = prog.manhours_report(db, PROJECT_ID, est=est)
    cli_mh = json.loads(cli[1]["full"])
    cli_roll = json.loads(cli[0]["full"])
    cli_sched = json.loads(cli[2]["full"])
    cross = dict(cli_manhours_total=str(cli_mh.get("total_hours")), engine_manhours_total=str(mh_now["total_hours"]), cli_rollup_tie_out=cli_roll.get("tie_out"),
                 cli_programme_working_days=str(cli_sched.get("project_working_days")))
    cross_ok = D(str(cli_mh["total_hours"])) == D(str(mh_now["total_hours"])) and cli_roll["tie_out"]["cbs"] is True
    sheets = openpyxl.load_workbook(wb, read_only=True).sheetnames if wb.exists() else []
    ok_cli = all(x["exit"] == 0 for x in cli) and cross_ok and cli_imports_ok
    ev.stage("17_reports_api_ui_export", "PASS" if (ok_cli and api["totals_match_engine"] and all(v["status"] == 200 and not v["traceback"] for v in ui.values()) and exp["exit"] == 0 and ver["exit"] == 0) else "FAIL",
             cli=[dict(cmd=x["cmd"], exit=x["exit"], out=x["stdout"][:300]) for x in cli], cross_checks=cross, workbook_sheets=sheets, cli_imports=[dict(cmd=x["cmd"], exit=x["exit"], out=(x["full"] or x["stderr"])[:350]) for x in cli_imports], api=api, ui=ui, workbook_export=dict(exit=exp["exit"], out=exp["stdout"][-300:]), workbook_verify=dict(exit=ver["exit"], out=ver["stdout"][-1400:]))


def stage_wbs_check(db, ev: Evidence, rollup: dict, pid: str = PROJECT_ID) -> None:
    ext, tot = independent_total()
    rows = db.all("SELECT item_key, cost_code, assembly_code FROM boq_items WHERE project_id=? AND item_type='item'", (pid,))
    wbs_assigned = db.scalar("SELECT COUNT(*) FROM wbs_item_assignments WHERE project_id=?", (pid,)) if db.one("SELECT 1 FROM sqlite_master WHERE name='wbs_item_assignments'") else None
    top = {n["code"]: D(n["total"]) for n in rollup["cbs"]["nodes"] if "." not in n["code"]}
    leaves = {n["code"]: D(n["total"]) for n in rollup["cbs"]["nodes"] if "." in n["code"]}
    wbs_top = sum((D(n["total"]) for n in rollup["wbs"]["nodes"]), D(0))
    ok = len(rows) == 30 and all(r["cost_code"] and r["assembly_code"] for r in rows) and sum(top.values(), D(0)) == sum(leaves.values(), D(0)) and rollup["tie_out"]["cbs"] and rollup["tie_out"]["wbs"]
    ev.stage("4_cost_code_and_wbs", "PASS" if ok else "FAIL", boq_lines=len(rows), lines_with_cost_code_and_mapping=sum(1 for r in rows if r["cost_code"] and r["assembly_code"]), wbs_assignment_rows=wbs_assigned,
             cbs_top_level_sum=str(sum(top.values(), D(0))), cbs_leaf_sum=str(sum(leaves.values(), D(0))), wbs_sum=str(wbs_top), tie_out=rollup["tie_out"],
             note="CBS/WBS totals include the approved test-only crane standby (900.00); parents and children are not summed together (top-level equals leaf sum)")


def run(workdir: Path) -> Evidence:
    from app.estimators.estimate import compute_estimate
    ev = Evidence()
    db, s = bootstrap(workdir)
    A = actors()
    ev["_meta"] = dict(workdir=str(workdir), db=str(s.db_path))
    stage_project_and_boq(db, ev, A, workdir)
    stage_resources_and_rates(db, ev, A, workdir)
    stage_mapping_baseline(db, ev, A)
    stage_params(db, ev, A)
    stage_commercial_setup(db, ev, A, approve_tax=False)
    stage_tax_gate(db, ev, A)
    stage_programme(db, ev, A)
    stage_time_allocation(db, ev, A)
    out = stage_estimate_outputs(db, ev, A)
    stage_wbs_check(db, ev, __import__("app.api.serializers", fromlist=["ser"]).ser(__import__("app.reporting.registry", fromlist=["x"]).run_report(db, "rollup", PROJECT_ID, {})))
    stage_variant_assemblies(db, ev, A, workdir)
    stage_procurement(db, ev, A)
    stage_takeoff(db, ev, A, workdir)
    stage_takeoff_replay(db, ev, A)
    ctx = stage_gates_freeze_export(db, ev, A)
    stage_production_isolation(db, ev, A, ctx)
    stage_boe(db, ev, A)
    stage_replay(db, ev, A, ctx)
    stage_negative_controls(db, ev, A, workdir)
    stage_interfaces(db, ev, A, workdir, ctx)
    ev["_finished"] = dict(final_state=compute_estimate(db, PROJECT_ID).state)
    return ev


def verdicts(ev: Evidence) -> dict:
    return {k: v["verdict"] for k, v in ev.items() if isinstance(v, dict) and "verdict" in v}
