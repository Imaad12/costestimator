"""WBS / cost-code roll-ups and client cross-walk: hand-calculated, tie-out invariants, structure-only (SYNTHETIC figures)."""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.core.errors import Conflict, PermissionDenied, ValidationFailed
from app.estimators import rollup
from app.services import wbs
from tests.conftest import ESTIMATOR, VIEWER


# ------------------------------------------------------------------ pure engine
def test_tree_rollup_hand_calculated_and_ties_out():
    parent = {"C": None, "C.01": "C", "C.02": "C", "C.01.1": "C.01", "D": None, "D.01": "D"}
    vals = {"C.01.1": D("100"), "C.01": D("10"), "C.02": D("5"), "D.01": D("7"), "ZZ": D("3"), None: D("1")}
    r = rollup.tree_rollup(vals, parent)
    n = r["nodes"]
    assert n["C.01"].total == D("110") and n["C"].total == D("115") and n["D"].total == D("7")
    assert r["unassigned"] == D("4")                                                  # unknown code + None are explicit, not lost
    assert r["grand_total"] == D("126") == sum(vals.values())
    assert n["C.01.1"].level == 3 and n["C"].level == 1


def test_crosswalk_longest_prefix_unmapped_and_ambiguous():
    vals = {"C.01.1": D("100"), "C.02": D("40"), "D.01": D("7"), "E.05": D("9"), "H.01": D("11")}
    maps = [("2000", "C"), ("2010", "C.01"), ("3000", "D"), ("9001", "H"), ("9002", "H")]      # H maps to two client codes: ambiguous
    r = rollup.crosswalk(vals, maps)
    assert r["by_client"] == {"2010": D("100"), "2000": D("40"), "3000": D("7")}
    assert r["unmapped"] == {"E.05": D("9")} and r["ambiguous"] == {"H.01": ["9001", "9002"]}
    assert r["grand_total"] == D("167") == sum(vals.values())


def test_matrix_totals():
    m = rollup.matrix({("A1", "C"): D("10"), ("A1", "D"): D("5"), ("A2", "C"): D("1")})
    assert m["row_totals"] == {"A1": D("15"), "A2": D("1")} and m["col_totals"] == {"C": D("11"), "D": D("5")} and m["grand_total"] == D("16")


# ------------------------------------------------------------------ service
@pytest.fixture()
def proj(seeded, tmp_path):
    from tests.helpers import build_mini
    return build_mini(seeded, tmp_path)


def test_wbs_structure_rules(seeded, proj):
    wbs.add_node(seeded, ESTIMATOR, proj, "A1", "Area 1")
    wbs.add_node(seeded, ESTIMATOR, proj, "A1.1", "Unit 1", "A1", "unit")
    with pytest.raises(Conflict):
        wbs.add_node(seeded, ESTIMATOR, proj, "A1", "dup")
    with pytest.raises(ValidationFailed):
        wbs.add_node(seeded, ESTIMATOR, proj, "B", "no parent", "NOPE")
    with pytest.raises(ValidationFailed):
        wbs.add_node(seeded, ESTIMATOR, proj, "bad code!", "x")
    with pytest.raises(PermissionDenied):
        wbs.add_node(seeded, VIEWER, proj, "Z", "z")
    r = wbs.assign_items(seeded, ESTIMATOR, proj, {"1.1": "A1.1", "9.9": "A1.1", "1.2": "NOPE"})
    assert r["assigned"] == 1 and len(r["errors"]) == 2
    with pytest.raises(Conflict):
        wbs.delete_node(seeded, ESTIMATOR, proj, "A1")                                # has children
    with pytest.raises(Conflict):
        wbs.delete_node(seeded, ESTIMATOR, proj, "A1.1")                              # has an item
    assert seeded.one("SELECT COUNT(*) n FROM audit_log WHERE entity_type IN ('wbs_node','wbs_assignment')")["n"] >= 3


def test_rollup_report_ties_to_estimate_and_wbs_scoped_by_item(seeded, proj):
    from app.estimators.estimate import compute_estimate
    wbs.add_node(seeded, ESTIMATOR, proj, "A1", "Area 1")
    wbs.add_node(seeded, ESTIMATOR, proj, "A2", "Area 2")
    wbs.assign_items(seeded, ESTIMATOR, proj, {"1.1": "A1"})                          # 1.2 left unassigned on purpose
    cid = seeded.one("SELECT code FROM cost_codes WHERE code='C.01'")["code"]
    wbs.add_crosswalk(seeded, ESTIMATOR, proj, "ClientX", "7100", "C")
    est = compute_estimate(seeded, proj)
    rep = wbs.rollup_report(seeded, proj, est=est)
    i11, i12 = est.direct.items["1.1"].direct_cost, est.direct.items["1.2"].direct_cost
    assert i11 > 0 and i12 > 0
    wb = {n["code"]: n["total"] for n in rep["wbs"]["nodes"]}
    assert wb["A1"] == i11 and wb["A2"] == D(0) and rep["wbs"]["unassigned"] == i12
    assert rep["direct_cost_total"] == i11 + i12 and all(rep["tie_out"][k] for k in ("cbs", "wbs")) and rep["tie_out"]["crosswalk"]["ClientX"]
    assert rep["crosswalks"]["ClientX"]["by_client"] == {"7100": i11 + i12}           # both items are cost code C.01 -> client 7100
    cb = {n["code"]: n["total"] for n in rep["cbs"]["nodes"]}
    assert cb[cid] == i11 + i12 and cb["C"] == i11 + i12                              # parent includes child
    assert rep["matrix"]["cells"][("A1", "C")] == i11 and rep["matrix"]["cells"][("(unassigned)", "C")] == i12


def test_wbs_scoped_productivity_factor_changes_only_that_area(seeded, proj):
    from app.estimators.estimate import compute_estimate
    from app.services import governed
    from tests.conftest import COMMERCIAL
    wbs.add_node(seeded, ESTIMATOR, proj, "A1", "Area 1"); wbs.add_node(seeded, ESTIMATOR, proj, "A1.1", "Unit", "A1")
    wbs.assign_items(seeded, ESTIMATOR, proj, {"1.1": "A1.1"})
    base = compute_estimate(seeded, proj)
    f = governed.propose(seeded, ESTIMATOR, "productivity_factor", "H", {"category": "height", "factor": "2", "scope_wbs": "A1"}, source="test record", submit=True)
    governed.approve(seeded, COMMERCIAL, f)
    after = compute_estimate(seeded, proj)
    lab = lambda e, k: sum(l.amount for l in e.direct.lines if l.kind == "labour" and l.item_key == k)
    assert lab(after, "1.1") == lab(base, "1.1") * 2 and lab(after, "1.2") == lab(base, "1.2")


def test_import_csv_and_crosswalk_rejects_unknown_cost_code(seeded, proj, tmp_path):
    f = tmp_path / "wbs.csv"
    f.write_text("code,parent_code,name,kind\nP1,,Plant 1,unit\nP1.A,P1,Block A,area\n", encoding="utf-8")
    assert wbs.import_csv(seeded, ESTIMATOR, proj, f)["nodes_created"] == 2
    g = tmp_path / "asg.csv"
    g.write_text("item_key,wbs_code\n1.1,P1.A\n", encoding="utf-8")
    assert wbs.import_csv(seeded, ESTIMATOR, proj, g)["assigned"] == 1
    with pytest.raises(ValidationFailed):
        wbs.add_crosswalk(seeded, ESTIMATOR, proj, "ClientX", "1", "ZZZ")
    r = wbs.import_crosswalk(seeded, ESTIMATOR, proj, "ClientX", [{"client_code": "1", "cost_code": "C"}, {"client_code": "2", "cost_code": "QQQ"}])
    assert r["added"] == 1 and len(r["errors"]) == 1
