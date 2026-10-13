"""Industrial acceptance chain (PRC-01 / SCO-04 / LIB-04 / EST-12 / DUR-04 / CTL-07): optional pack -> approved rates and factors -> a piping BOQ in 'joint' units ->
take-off derivation -> pricing approval -> estimate -> man-hours, programme loading, roll-up, risk and Basis of Estimate. All numbers SYNTHETIC and worked out by hand."""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.estimators.estimate import compute_estimate
from app.imports import boq as bi
from app.services import boe, boq, governed, indirects, mto, programme, projects, refdata, registers, risk, wbs
from tests.conftest import ADMIN, COMMERCIAL, ESTIMATOR
from tests.helpers import approve_vat, approved_rate, std_policy, write_boq


def test_piping_welds_from_pack_to_basis_of_estimate(seeded, tmp_path):
    db = seeded
    refdata.load_pack(db, ADMIN, "industrial")
    joint_subs = [r["id"] for r in db.all("SELECT id FROM resources WHERE created_by='pack:industrial' AND resource_type='subcontract' AND unit='joint' ORDER BY id")]
    assert len(joint_subs) >= 2
    welder, fitter, grinder, consumable, ndt, pwht = "PRC-LAB-002", "PRC-LAB-001", "PRC-LAB-003", "PRC-MAT-022", joint_subs[0], joint_subs[1]
    for rid, price in ((welder, "20"), (fitter, "20"), (grinder, "20"), (consumable, "15"), (ndt, "300"), (pwht, "400")):
        approved_rate(db, rid, price)                                                    # SYNTHETIC rates; the pack itself holds none

    T = "piping.weld_joint"
    for slot, rid, fac in (("welder_labour", welder, "1.5"), ("fitter_labour", fitter, "1.0"), ("consumables", consumable, "0.4"), ("ndt", ndt, "0.1"), ("pwht", pwht, "0.05"),
                           ("grinding_labour", grinder, "0.25")):
        i = governed.propose(db, ESTIMATOR, "mto_factor", f"{T}/{slot}", {"template": T, "slot": slot, "resource_id": rid, "factor": fac}, source="Synthetic test norms (not real)", submit=True)
        governed.approve(db, COMMERCIAL, i)

    pid = projects.create_project(db, ESTIMATOR, name="Piping package (SYNTHETIC)", is_demo=True, tax_category="VAT-STD")
    r = bi.import_boq(db, ESTIMATOR, pid, write_boq(tmp_path / "pipe.csv", [("P-1", "Butt welds, CS pipe, field", "joint", "200", "", "")]))
    assert r["rejected"] == 0 and db.one("SELECT unit, unit_status FROM boq_items WHERE project_id=?", (pid,))["unit_status"] == "ok"        # SCO-04
    boq.set_cost_code(db, ESTIMATOR, pid, "P-1", "M.01")
    std_policy(db, pid)
    approve_vat(db)

    # take-off derivation: driver = the BOQ quantity (200 joints); per joint 30 + 20 + 6 + 30 + 20 + 5 = 111 -> 22,200
    pv = mto.preview(db, pid, "P-1", T)
    assert pv["driver_qty"] == 200 and not pv["missing"] and sum(l["qty"] for l in pv["lines"] if l["slot"] == "welder_labour") == D(300)
    mto.apply(db, ESTIMATOR, pid, "P-1", T)
    assert not compute_estimate(db, pid).direct.items["P-1"].complete                                   # not usable until a person approves the pricing
    boq.decide_pricing(db, COMMERCIAL, pid, "P-1", "approve", comment="Driver and norms checked (synthetic)")
    est = compute_estimate(db, pid)
    assert est.direct.items["P-1"].complete and est.direct.direct_cost_total == D("22200.00")

    # company productivity factor for work at height: labour 2.75 h/joint x 200 = 550 h -> 660 h ; labour cost 11,000 -> 13,200
    f = governed.propose(db, ESTIMATOR, "productivity_factor", "HEIGHT", {"category": "height", "factor": "1.2", "scope_cost_prefix": "M."}, source="Synthetic site study", submit=True)
    governed.approve(db, COMMERCIAL, f)
    est = compute_estimate(db, pid)
    assert est.direct.direct_cost_total == D("24400.00")

    # roll-up by cost-code tree and WBS; man-hours; programme loading
    wbs.add_node(db, ESTIMATOR, pid, "U1", "Unit 1"); wbs.assign_items(db, ESTIMATOR, pid, {"P-1": "U1"})
    c = governed.propose(db, ESTIMATOR, "calendar", "PROJECT", {"start_date": "2026-03-01", "work_weekdays": [6, 0, 1, 2, 3], "holidays": []}, project_id=pid, source="Contract programme (synthetic)", submit=True)
    governed.approve(db, COMMERCIAL, c)
    indirects.set_tasks(db, ESTIMATOR, pid, [{"task_code": "W1", "name": "Pipe welding", "duration_days": "10", "cost_code": "M.01", "wbs_code": "U1"}])
    est = compute_estimate(db, pid)                                                                     # re-read: the WBS assignment is an estimate input
    rep = wbs.rollup_report(db, pid, est=est)
    cb = {n["code"]: n["total"] for n in rep["cbs"]["nodes"]}
    assert cb["M.01"] == D("24400.00") and cb["M"] == D("24400.00") and rep["tie_out"]["cbs"] and rep["tie_out"]["wbs"]
    mh = programme.manhours_report(db, pid, est=est)
    assert mh["total_hours"] == D(660) and mh["by_resource"] == {welder: D(360), fitter: D(240), grinder: D(60)} and mh["by_wbs"] == {"U1": D(660)} and mh["by_division"] == {"M": D(660)}
    ld = programme.loading_report(db, pid, measure="labour_hours", period="week", est=est)
    assert ld["scheduled_total"] == D(660) and ld["unscheduled_total"] == 0 and ld["tie_out"]
    assert sum(ld["totals"].values()) == D(660)

    # risk analysis proposes a provision and changes nothing
    rk = registers.add_risk(db, ESTIMATOR, pid, "Weld repair rate above plan")
    registers.quantify_risk(db, ESTIMATOR, rk, prob_pct="30", cost_low="500", cost_likely="1500", cost_high="4000", basis="Last two piping jobs (synthetic)")
    before = compute_estimate(db, pid).fingerprint
    rr = risk.risk_report(db, pid, trials=2000, seed=11, target_pct=80, est=est)
    assert rr["expected_value"]["total"] == D("0.3") * (D(500) + D(1500) + D(4000)) / 3 and "PROPOSAL ONLY" in rr["note"]
    assert compute_estimate(db, pid).fingerprint == before

    # Basis of Estimate lists the derivation and leaves the judgement sections to the estimator
    out = boe.generate_boe(db, ESTIMATOR, pid)
    md = (__import__("pathlib").Path(out["directory"]) / out["files"][0]).read_text(encoding="utf-8")
    assert "piping.weld_joint" in md and "HEIGHT" in md and md.count(boe.PLACEHOLDER) == 6


def _compatible(db, slot):
    allowed = mto.DIM_GROUPS.get(slot["unit_dim"], {slot["unit_dim"]})
    return [r["id"] for r in db.all("SELECT r.id, u.dimension FROM resources r JOIN units u ON u.code=r.unit WHERE r.resource_type=? AND r.is_active=1 ORDER BY r.id", (slot["resource_type"],))
            if db.scalar("SELECT dimension FROM units WHERE code=(SELECT unit FROM resources WHERE id=?)", (r["id"],)) in allowed]


def test_every_template_slot_has_a_compatible_catalogue_resource_in_the_pack(seeded):
    """COMPATIBILITY only (type and unit kind). It does not say the resource is the right one for a given job - that is the company's choice in the factor."""
    refdata.load_pack(seeded, ADMIN, "industrial")
    missing = [(t["code"], s["slot"]) for t in mto.templates().values() for s in t["slots"] if not _compatible(seeded, s)]
    assert missing == []


def test_every_template_can_be_derived_and_priced_mechanically_with_synthetic_inputs(seeded, tmp_path):
    """Mechanics only: all 23 templates run through factor approval -> apply -> pricing approval -> estimate with SYNTHETIC unit factors of 1 and SYNTHETIC rates of 10.
    It proves the generic engine accepts every template; it proves nothing about real norms, which the repository does not contain."""
    db = seeded
    refdata.load_pack(db, ADMIN, "industrial")
    pid = projects.create_project(db, ESTIMATOR, name="All templates (SYNTHETIC)", is_demo=True, tax_category="VAT-STD")
    tpls = sorted(mto.templates().values(), key=lambda t: t["code"])
    rows = [(f"T{i}", t["name"], "nr", "2", "", "") for i, t in enumerate(tpls)]
    bi.import_boq(db, ESTIMATOR, pid, write_boq(tmp_path / "all.csv", rows))
    rated = set()
    for i, t in enumerate(tpls):
        for s in t["slots"]:
            rid = _compatible(db, s)[0]
            if rid not in rated:
                approved_rate(db, rid, "10")
                rated.add(rid)
            f = governed.propose(db, ESTIMATOR, "mto_factor", f"{t['code']}/{s['slot']}", {"template": t["code"], "slot": s["slot"], "resource_id": rid, "factor": "1"},
                                 source="SYNTHETIC mechanical test", submit=True)
            governed.approve(db, COMMERCIAL, f)
        mto.apply(db, ESTIMATOR, pid, f"T{i}", t["code"], driver_qty="2", driver_source="SYNTHETIC test driver")
        boq.decide_pricing(db, COMMERCIAL, pid, f"T{i}", "approve", comment="synthetic mechanical test")
    std_policy(db, pid)
    est = compute_estimate(db, pid)
    done = [k for k, ic in est.direct.items.items() if ic.complete]
    assert len(done) == len(tpls) == 23
    # per item: driver 2 x factor 1 x SYNTHETIC rate 10 = 20 per slot (unit conversions to the rate unit are identity here)
    for i, t in enumerate(tpls):
        assert est.direct.items[f"T{i}"].direct_cost == D(20) * len(t["slots"]), t["code"]
