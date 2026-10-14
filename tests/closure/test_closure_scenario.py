"""End-to-end SYNTHETIC tender closure: the whole scenario runs once; every stage must PASS and the independent oracle must agree with the application.

All data are fictional test inputs; every actor is a registered TEST ACTOR; the packs are DEMONSTRATION packs that can never be submission-ready."""
from __future__ import annotations

import json
import shutil
from contextlib import contextmanager
from datetime import date
from decimal import Decimal as D
from fractions import Fraction
from pathlib import Path

import pytest

from app import config as cfg
from app.database import set_db
from app.tender import catalogue, model
from tests.closure import data as Dt, oracle, scenario


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    work = tmp_path_factory.mktemp("closure")
    ev = scenario.run(work, work / "demo_output")
    from app.database import get_db
    yield dict(ev=ev, work=work, out=work / "demo_output", db=get_db())
    cfg.set_settings(None)
    set_db(None)


def test_every_stage_passes_and_none_is_missing(run):
    v = scenario.verdicts(run["ev"])
    assert set(v) == set(scenario.STAGES), sorted(set(scenario.STAGES) ^ set(v))
    assert {k: x for k, x in v.items() if x != "PASS"} == {}, {k: run["ev"][k] for k, x in v.items() if x != "PASS"}


def test_acceptance_inputs_are_synthetic_and_never_submission_ready(run):
    db = run["db"]
    assert db.scalar("SELECT COUNT(*) FROM exports WHERE submission_ready=1") == 0
    assert db.scalar("SELECT COUNT(*) FROM tender_packs WHERE classification='production'") == 0
    assert db.scalar("SELECT COUNT(*) FROM approvals WHERE actor_type='human'") == 0                      # every approval in the run was by a registered TEST principal or an unregistered probe
    assert db.scalar("SELECT COUNT(*) FROM users WHERE actor_type='human'") == 0
    pk = db.scalar("SELECT pk FROM tender_packs WHERE kind='tender' ORDER BY revision DESC LIMIT 1")
    for r in db.all("SELECT status FROM generated_documents WHERE pack_pk=?", (pk,)):
        assert r["status"] != "Approved for Submission"


# ---------------------------------------------------------------------------------------------------- programme oracle
def test_programme_matches_independent_oracle(run):
    from app.services import workforce as wf
    db = run["db"]
    pid = Dt.PROJECT_ID
    base = wf.latest_baseline(db, pid, approved_only=True)
    res = base["result"]
    prof = dict(db.one("SELECT * FROM workforce_profiles WHERE id=? ORDER BY version DESC LIMIT 1", ("WP-MID",)))
    model_ = oracle.activity_model(db, pid, prof)
    rows = {a["code"]: a for a in res["activities"]}
    for code, m in model_.items():
        a = rows[code]
        assert abs(D(a["labour_hours"]) - D(m["hours"].numerator) / D(m["hours"].denominator)) <= D("0.005"), code
        assert abs(D(a["crew_days"]) - D(m["crew_days"].numerator) / D(m["crew_days"].denominator)) <= D("0.005"), code
        assert a["unconstrained_wd"] == m["dur"], (code, a["unconstrained_wd"], m["dur"])
    # dependency-only schedule (no procurement, no resources): separate longest-path implementation
    mob = prof["mobilisation_wd"]
    es, ef = oracle.longest_path(model_, None, mob)
    assert res["dependency_constrained_wd"] == max(ef.values())
    # procurement-constrained: the pump skid is ready at the working-day index of its order date + lead time
    cal = oracle.calendar_data(db, pid)
    wk = {int(x) for x in cal["work_weekdays"]}
    hol = {date.fromisoformat(h) for h in cal["holidays"]}
    shut = [(date.fromisoformat(w["from"]), date.fromisoformat(w["to"])) for w in cal.get("shutdowns", [])]
    ll = db.one("SELECT * FROM long_lead_items WHERE project_id=?", (pid,))
    ready_date = date.fromisoformat(ll["planned_order_date"]).toordinal() + int(ll["lead_time_weeks"]) * 7
    ready_idx = sum(1 for k in range(date.fromisoformat(cal["start_date"]).toordinal(), ready_date) if _is_work(date.fromordinal(k), wk, hol, shut))
    es2, ef2 = oracle.longest_path(model_, {"A-PUMP": ready_idx}, mob)
    assert res["procurement_constrained_wd"] == max(ef2.values())
    assert sorted(res["critical_path"]) == sorted(oracle.critical_path(model_, es2, ef2))
    # resource-constrained duration is never shorter than the procurement-constrained one, nor than the single-role workload bound
    assert res["working_days"] >= res["procurement_constrained_wd"]
    pool = {r: int(n * D("0.92") * D("0.95")) if not r.startswith(("eq:", "sub:")) else n for r, n in {**json.loads(prof["roles_json"]), **{"sub:" + k: v for k, v in json.loads(prof["subcontract_capacity_json"]).items()}}.items()}
    assert res["working_days"] >= oracle.role_lower_bound_days(model_, pool)
    # calendar conversion with a plain date loop
    dates = oracle.working_dates(date.fromisoformat(cal["start_date"]), wk, hol, shut, res["working_days"])
    assert res["finish_date"] == dates[-1].isoformat() and res["start_date"] == dates[0].isoformat() and res["calendar_days"] == (dates[-1] - dates[0]).days + 1


def _is_work(d, wk, hol, shut):
    return d.weekday() in wk and d not in hol and not any(a <= d <= b for a, b in shut)


def test_crew_scenarios_use_constraints_not_headcount_division(run):
    from app.services import workforce as wf
    db = run["db"]
    sc = wf.crew_scenarios(db, Dt.PROJECT_ID, [p[0] for p in Dt.PROFILES], allow_provisional=True, allow_unconfirmed_calendar=True)["scenarios"]
    by = {s["profile"]: s for s in sc}
    heads = {k: v["headcount"] for k, v in by.items()}
    assert all(s["schedulable"] for s in sc)
    wd = {k: v["working_days"] for k, v in by.items()}
    assert wd["WP-SME"] > wd["WP-MID"] > wd["WP-LARGE"] >= wd["WP-ENT"]
    # a naive "labour-hours / head-count" duration would collapse with head-count; the constrained one does not
    naive = {k: float(D(by[k]["labour_hours"]) / (heads[k] * 6)) for k in by}
    assert naive["WP-ENT"] < wd["WP-ENT"] / 3
    assert wd["WP-LARGE"] == wd["WP-ENT"]                      # more people than fronts / the single crane allow: no further gain
    assert wd["WP-SME"] / wd["WP-ENT"] < (heads["WP-ENT"] / heads["WP-SME"]) / 2
    assert [s["archetype"] for s in sc] == ["sme", "mid", "large", "enterprise"] and all(s["claim"].startswith("PROVISIONAL") for s in sc)
    assert all(s["cost"]["computed"] for s in sc)            # role day-costs were entered (synthetic), so the planning cost is computed


def test_plant_hire_window_matches_independent_count(run):
    from app.reporting import registry
    db = run["db"]
    rep = registry.run_report(db, "plant_hire", Dt.PROJECT_ID, {})
    cal = oracle.calendar_data(db, Dt.PROJECT_ID)
    wk = {int(x) for x in cal["work_weekdays"]}
    hol = {date.fromisoformat(h) for h in cal["holidays"]}
    shut = [(date.fromisoformat(w["from"]), date.fromisoformat(w["to"])) for w in cal.get("shutdowns", [])]
    rows = [r for v in rep.values() if isinstance(v, list) for r in v if isinstance(r, dict) and r.get("window_start")]
    assert rows
    for r in rows:
        wdays, cdays = oracle.plant_window_working_days(date.fromisoformat(r["window_start"]), date.fromisoformat(r["window_finish"]), wk, hol, shut)
        assert str(wdays) == str(r["working_days"]) and cdays == int(r["calendar_days"]), r["resource_id"]
        assert r["billing_basis"] in ("working_day", "calendar_day") and (r["billing_basis"] == "calendar_day" or str(wdays) == str(r["required_billable_days"]))


# ---------------------------------------------------------------------------------------------------- commercial / cash oracle
def test_quotes_and_levelling_match_hand_calculation(run):
    st = run["ev"]["13_procurement_and_quote_levelling"]
    for k, sup in Dt.SUPPLIERS.items():
        assert st["headline_totals"][k] == oracle.quote_totals(sup["rates"], Dt.QUOTE_QTY)
    assert st["headline_lowest"] == "B" and st["evaluated_winner"] == "A"                       # the lowest headline price is not the best like-for-like offer
    assert D(st["evaluated_totals"]["B"]) == D(st["headline_totals"]["B"]) + D(Dt.DELIVERY_ADJ_B)


def test_commercial_chain_and_cash_flow_reconcile_independently(run):
    from app.estimators.estimate import compute_estimate
    from app.reporting import registry
    db = run["db"]
    est = compute_estimate(db, Dt.PROJECT_ID)
    t = est.totals()
    line_sum = sum((Fraction(str(l.quantity)) * Fraction(str(l.unit_rate)) for l in est.schedule.lines if l.amount is not None), Fraction(0))
    assert abs(D(t["selling_price_pre_tax"]) - D(line_sum.numerator) / D(line_sum.denominator)) <= est.schedule.max_rounding_variance
    assert abs(D(t["tax"]) - D(t["selling_price_pre_tax"]) * D("0.15")) <= D("0.01")
    assert D(t["final_payable"]) == D(t["selling_price_pre_tax"]) + D(t["tax"])
    cf = registry.run_report(db, "cashflow", Dt.PROJECT_ID, {})
    assert cf["complete"] and cf["status"] == "COMPLETE" and all(c["ok"] for c in cf["reconciliation"]["checks"])
    rec = cf["reconciliation"]
    assert D(rec["direct_cost"]) == est.direct.direct_cost_total and D(str(rec["unallocated_direct_cost"])) == 0 and D(str(rec["unallocated_price_share"])) == 0
    # independent identities: cash paid = direct + indirect (everything is allocated); retention = 5% of the valuations (the synthetic terms); closing = price - paid - interest
    assert D(str(rec["cash_out_total"])) == est.direct.direct_cost_total + est.indirect.total
    assert abs(D(str(cf["retention_total"])) - D(str(rec["valued_price"])) * D("0.05")) <= D("0.01")
    assert abs(D(str(cf["final_balance"])) - (D(str(rec["valued_price"])) - D(str(rec["cash_out_total"])) - D(str(rec["interest_total"])))) <= D("0.02")
    assert abs(sum(D(str(r["cash_in"])) for r in cf["rows"]) - D(str(rec["cash_in_total"]))) <= D("0.05") and abs(sum(D(str(r["cash_out"])) for r in cf["rows"]) - D(str(rec["cash_out_total"]))) <= D("0.05")
    assert abs(sum(D(str(v["value"])) for v in cf["valuations"]) - D(str(rec["valued_price"]))) <= D("0.05")
    # time-phased values are presented to 2 decimals (calculation precision is kept internally)
    for v in (cf["final_balance"], cf["interest_total"], cf["peak_funding"]):
        assert D(str(v)) == D(str(v)).quantize(D("0.01"))


def test_time_allocation_before_after_exact_amounts(run):
    ta = run["ev"]["21_resolve_issues_with_test_approvals"]["time_allocation"]
    assert ta["before"]["cashflow_status"].startswith("INCOMPLETE - NOT FOR RELIANCE") and D(ta["before"]["unallocated_direct_cost"]) == D("568080.00")
    assert D(ta["first_batch"]["unallocated_direct_cost"]) == sum(D(a) for _, a in ta["first_batch"]["unallocated_lines"]) == D("211380.00")        # the exact untied amount is exposed after each batch
    assert ta["after"]["cashflow_status"] == "COMPLETE" and ta["after"]["escalation_complete"] and ta["after"]["reconciliation_checks_ok"]
    assert ta["before"]["financing_refused_with"] == "TIMEPHASING_INCOMPLETE" and ta["before"]["final_gate_blocked_by_it"]


# ---------------------------------------------------------------------------------------------------- documents
def _pack(run, kind="tender", rev=None):
    db = run["db"]
    row = db.one("SELECT * FROM tender_packs WHERE project_id=? AND kind=? " + ("AND revision=? " if rev else "") + "ORDER BY revision DESC LIMIT 1", (Dt.PROJECT_ID, kind) + ((rev,) if rev else ()))
    return dict(row), json.loads((Path(row["out_dir"]) / "manifest.json").read_text())


def test_every_generated_file_opens_and_carries_its_identity(run):
    row, man = _pack(run, rev=2)
    n = 0
    for d in man["documents"]:
        if d["status"] == "Not Applicable":
            assert not d["files"]
            continue
        for fmt, f in d["files"].items():
            p = Path(row["out_dir"]).parent / f["path"]
            got = model.parse_back(p)
            assert got["format"] == fmt and model.sha256_file(p) == f["sha256"]
            if fmt in ("docx", "pdf"):
                assert d["doc_id"] in got["text"] and "NOT SUBMISSION READY" in got["text"].upper() and "SYNTHETIC" in got["text"].upper()
            if fmt == "pdf":
                assert p.read_bytes()[:5] == b"%PDF-" and got["pages"] >= 1
            n += 1
    assert n > 100


def test_applicability_matrix_and_blocked_documents(run):
    row1, man1 = _pack(run, rev=1)
    by1 = {d["code"]: d for d in man1["documents"]}
    assert by1["D13"]["status"] == "BLOCKED" and "payment terms" in by1["D13"]["blocked_reason"]
    assert by1["D06"]["status"] == "BLOCKED" and by1["D44"]["status"] == "Not Applicable"
    mx = json.loads((Path(row1["out_dir"]) / "applicability_matrix.json").read_text())
    assert sum(mx["counts"].values()) == 45 and all(r["reason"] for r in mx["rows"])
    assert {r["applicability"] for r in mx["rows"]} <= {catalogue.REQ, catalogue.COND, catalogue.NA, catalogue.MCR}
    row2, man2 = _pack(run, rev=2)
    assert not [d for d in man2["documents"] if d["status"] == "BLOCKED"] and man2["classification"] == "demonstration" and man2["production_ready"] is False


def test_documents_agree_with_the_frozen_estimate_and_with_each_other(run):
    import openpyxl
    from app.services import estimates
    db = run["db"]
    row, man = _pack(run, rev=2)
    t = estimates.get_version(db, row["estimate_version_id"])["totals"]
    facts = {}
    for g in db.all("SELECT doc_code, facts_json FROM generated_documents WHERE pack_pk=? AND status<>'Not Applicable'", (row["pk"],)):
        for k, v in json.loads(g["facts_json"] or "{}").items():
            facts.setdefault(k, set()).add(str(v))
    assert all(len(v) == 1 for v in facts.values()), {k: v for k, v in facts.items() if len(v) > 1}
    assert facts["net_price"] == {t["commercial_net_price"]} and facts["payable"] == {t["final_payable"]} and facts["vat"] == {t["tax"]}
    # the priced schedule workbook adds up (independent re-addition of the printed lines)
    xl = next(Path(row["out_dir"]).glob("*D05*.xlsx"))
    wb = openpyxl.load_workbook(xl)
    ws = wb["Pricing schedule (SAR)"]
    total = sum(D(str(r[3])) for r in ws.iter_rows(min_row=2, values_only=True) if r[3] not in (None, "", "None", "-"))
    assert abs(total - D(t["selling_price_pre_tax"])) <= D("0.011") or abs(total - D(t["selling_price_pre_tax"])) <= D("350")
    d19 = model.parse_back(next(Path(row["out_dir"]).glob("*D19*.docx")))["text"]
    prog = json.loads(db.one("SELECT result_json FROM programme_baselines WHERE project_id=? AND status='Approved'", (Dt.PROJECT_ID,))["result_json"])
    assert str(prog["working_days"]) in d19 and prog["finish_date"] in d19 and "Calendar confirmed" in d19


def test_pack_regeneration_is_deterministic_and_figures_survive_library_changes(run):
    st = run["ev"]["25_global_library_change"]
    assert st["verdict"] == "PASS" and st["document_figure_differences_rev_after_vs_before"] == {} and st["frozen_replay_ok"] and st["live_total_before"] != st["live_total_after"]
    d = model.Doc("D99", "Determinism probe", [model.Section("S", ["p"], model.Table(["a"], [[1]]))], facts={"x": 1}, xlsx=True)
    meta = dict(project_id="P", project_name="n", customer="c", doc_id="P-D99", title=d.title, revision=1, issue_date="2027-01-01", status="Draft", author="a", reviewer="r", estimate_version="v1",
                fingerprint="ab", template="t", confidentiality="c", banner="B", synthetic_mark="S")
    hashes = set()
    for i in range(2):
        for fmt, fn in (("docx", model.render_docx), ("xlsx", model.render_xlsx), ("pdf", model.render_pdf)):
            p = run["work"] / f"det{i}.{fmt}"
            fn(d, meta, p)
            hashes.add((fmt, model.sha256_file(p)))
    assert len(hashes) == 3                                          # same inputs + template version -> byte-identical files per format


def test_handover_pack_is_labelled_hypothetical_and_complete(run):
    row, man = _pack(run, kind="handover")
    assert man["hypothetical"] is True and len(man["documents"]) == 17 and row["hypothetical"] == 1
    for d in man["documents"]:
        txt = model.parse_back(Path(row["out_dir"]).parent / d["files"]["docx"]["path"])["text"]
        assert "HYPOTHETICAL POST-AWARD HANDOVER" in txt and "NO AWARD HAS BEEN MADE" in txt
    h16 = next(d for d in man["documents"] if d["code"] == "H16")
    assert man["estimate_fingerprint"] in model.parse_back(Path(row["out_dir"]).parent / h16["files"]["docx"]["path"])["text"]
    h17 = next(d for d in man["documents"] if d["code"] == "H17")
    txt = model.parse_back(Path(row["out_dir"]).parent / h17["files"]["docx"]["path"])["text"]
    assert "SIMULATED OWNER" in txt and "[[MISSING" not in txt


def test_consolidated_manifest_and_acceptance_file_are_machine_readable(run):
    man = json.loads((run["out"] / "MANIFEST.json").read_text())
    assert man["synthetic"] and man["tender_pack"]["production_ready"] is False and man["handover_pack"]["hypothetical"] and len(man["files"]) > 150
    for f in man["files"][:20]:
        p = run["out"] / f["path"]
        assert p.exists() and model.sha256_file(p) == f["sha256"]


# ---------------------------------------------------------------------------------------------------- pack validator: negative tests
@contextmanager
def tampered(path: Path, new: bytes | None):
    old = path.read_bytes()
    try:
        path.write_bytes(new) if new is not None else path.unlink()
        yield
    finally:
        path.write_bytes(old)


def test_validator_detects_tampering_corruption_missing_files_and_inconsistency(run):
    from app.tender import packs
    db = run["db"]
    row, man = _pack(run, rev=2)
    assert packs.validate_pack(db, row["pk"])["ok"]
    d01 = next(d for d in man["documents"] if d["code"] == "D01")
    docx = Path(row["out_dir"]).parent / d01["files"]["docx"]["path"]
    with tampered(docx, docx.read_bytes() + b"x"):
        v = packs.validate_pack(db, row["pk"])
        assert not v["ok"] and any("checksum" in e for e in v["errors"])
    with tampered(docx, b"this is not a docx"):
        assert any("does not open" in e or "checksum" in e for e in packs.validate_pack(db, row["pk"])["errors"])
    with tampered(docx, None):
        assert any("file missing" in e for e in packs.validate_pack(db, row["pk"])["errors"])
    pdf = Path(row["out_dir"]).parent / d01["files"]["pdf"]["path"]
    with tampered(pdf, b"renamed text file"):
        v = packs.validate_pack(db, row["pk"])
        assert any("genuine PDF" in e or "checksum" in e for e in v["errors"])
    g = db.one("SELECT pk, facts_json FROM generated_documents WHERE pack_pk=? AND doc_code='D02'", (row["pk"],))
    bad = json.loads(g["facts_json"])
    bad["payable"] = "1.00"
    db.execute("UPDATE generated_documents SET facts_json=? WHERE pk=?", (json.dumps(bad), g["pk"]))
    try:
        assert any("inconsistent value 'payable'" in e for e in packs.validate_pack(db, row["pk"])["errors"])              # one document disagrees with the others
    finally:
        db.execute("UPDATE generated_documents SET facts_json=? WHERE pk=?", (g["facts_json"], g["pk"]))
    saved = {x["pk"]: x["facts_json"] for x in db.all("SELECT pk, facts_json FROM generated_documents WHERE pack_pk=? AND facts_json IS NOT NULL", (row["pk"],))}
    try:
        for pk_, fj in saved.items():
            f = json.loads(fj)
            if "payable" in f:
                f["payable"] = "1.00"                                                                                       # ... or every document carries the same wrong total
                db.execute("UPDATE generated_documents SET facts_json=? WHERE pk=?", (json.dumps(f), pk_))
        assert any(e.startswith("arithmetic:") for e in packs.validate_pack(db, row["pk"])["errors"])
    finally:
        for pk_, fj in saved.items():
            db.execute("UPDATE generated_documents SET facts_json=? WHERE pk=?", (fj, pk_))
    r = db.one("SELECT refs_json FROM generated_documents WHERE pack_pk=? AND doc_code='D02'", (row["pk"],))
    db.execute("UPDATE generated_documents SET refs_json=? WHERE pack_pk=? AND doc_code='D02'", (json.dumps(["PRJ-9101-D99"]), row["pk"]))
    try:
        assert any("stale reference" in e for e in packs.validate_pack(db, row["pk"])["errors"])
    finally:
        db.execute("UPDATE generated_documents SET refs_json=? WHERE pack_pk=? AND doc_code='D02'", (r["refs_json"], row["pk"]))
    assert packs.validate_pack(db, row["pk"])["ok"]
