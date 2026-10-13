"""The capability matrix may not drift from the repository: every cited file, symbol and test must exist, and status claims
must be consistent with the evidence they cite (docs/ESTIMATING_CAPABILITY_MATRIX.md is rendered from docs/capability_matrix.json)."""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
D = json.loads((ROOT / "docs" / "capability_matrix.json").read_text(encoding="utf-8"))
REC = D["records"]
IT, IU, PA, MI, NA = D["statuses"]


def _gen():
    spec = importlib.util.spec_from_file_location("gen_capability_matrix", ROOT / "scripts" / "gen_capability_matrix.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_structure_ids_levels_kinds_dependencies():
    ids = [r["id"] for r in REC]
    assert len(ids) == len(set(ids))
    assert set(D["levels"]) == {"1", "2", "3", "4", "5"}
    for r in REC:
        assert r["status"] in D["statuses"], r["id"]
        assert r["required_from"] in (1, 2, 3, 4, 5) and r["kind"] in ("engine", "data"), r["id"]
        for k in ("capability", "output", "limits", "acceptance", "area"):
            assert str(r[k]).strip(), (r["id"], k)
        for dep in r["depends"]:
            assert dep in ids, (r["id"], dep)


def test_every_cited_code_path_symbol_and_test_exists():
    problems = []
    for r in REC:
        for c in r["code"]:
            path, _, sym = c.partition("::")
            f = ROOT / path
            if not f.exists():
                problems.append(f"{r['id']}: missing file {path}")
            elif sym and f.suffix == ".py" and sym not in f.read_text(encoding="utf-8"):
                problems.append(f"{r['id']}: symbol {sym} not in {path}")
        for t in r["tests"]:
            path, _, name = t["ref"].partition("::")
            f = ROOT / path
            if not f.exists() or not re.search(rf"def {re.escape(name)}\b", f.read_text(encoding="utf-8")):
                problems.append(f"{r['id']}: test not found {t['ref']}")
            assert t["verdict"] in ("yes", "partly", "no"), (r["id"], t)
    assert not problems, problems


def test_status_claims_are_consistent_with_their_evidence():
    problems = []
    for r in REC:
        yes = [t for t in r["tests"] if t["verdict"] == "yes"]
        if r["status"] == IT and not yes:
            problems.append(f"{r['id']}: Implemented and tested without a test that verifies the behaviour")
        if r["status"] == MI and (r["code"] or r["tests"]):
            problems.append(f"{r['id']}: Missing must not cite implementing code or tests (describe the closest existing code in 'limits')")
        if r["status"] in (PA, IU) and not r["code"]:
            problems.append(f"{r['id']}: {r['status']} must cite code")
        if r["status"] in (PA, IU, MI) and len(r["limits"]) < 25:
            problems.append(f"{r['id']}: limitations must be stated for {r['status']}")
        if r["status"] == IU and not any(w in r["limits"].lower() for w in ("never", "not ", "no ", "blocked", "unverified")):
            problems.append(f"{r['id']}: unverified status must say what is unverified")
    assert not problems, problems


def test_the_brief_s_mandatory_areas_have_records():
    text = " ".join(f"{r['id']} {r['capability']} {r['area']}".lower() for r in REC)
    for needle in ("boq", "unit", "mapping", "architectural", "structural", "civil", "infrastructure", "hvac", "plumbing", "fire", "electrical", "elv", "piping",
                   "process equipment", "instrumentation", "steel", "tank", "coating", "insulation", "specialist", "labour", "plant", "subcontract", "crew", "productivity",
                   "methodology", "engineering services", "temporary", "mobilisation", "home-office", "logistics", "customs", "preliminaries", "indirects", "duration",
                   "sequencing", "resource loading", "basis of estimate", "classification", "exclusions", "escalation", "contingency", "quantified risk", "quotation",
                   "levelling", "procurement", "wbs", "cbs", "benchmark", "cash flow", "forecast", "change order", "commissioning", "start-up", "handover", "close-out",
                   "client compliance profile", "aramco", "snapshot", "audit", "approval", "export"):
        assert needle in text or needle.replace("-", " ") in text, needle


def test_no_aramco_compliance_is_claimed():
    for r in REC:
        if "aramco" in (r["capability"] + r["output"] + r["limits"]).lower():
            assert r["status"] == MI and "no compliance is claimed" in (r["limits"] + r["output"]).lower(), r["id"]
    doc = (ROOT / "docs" / "ESTIMATING_CAPABILITY_MATRIX.md").read_text(encoding="utf-8")
    assert "not official Saudi Aramco levels" in doc and "No Saudi Aramco compliance is claimed" in doc


def test_rendered_document_is_current():
    g = _gen()
    doc = ROOT / "docs" / "ESTIMATING_CAPABILITY_MATRIX.md"
    assert g.render(doc.read_text(encoding="utf-8"), g.load()) == doc.read_text(encoding="utf-8"), "run: python scripts/gen_capability_matrix.py"


def test_rollup_is_computed_from_records_not_hand_written():
    g = _gen()
    eng = lambda lv: [r for r in g.required_for(REC, lv) if r["kind"] == "engine"]  # noqa: E731
    assert len(eng(1)) > len(eng(3)) > len(eng(5)) > 0
    assert all(r["kind"] == "data" for r in REC if r["id"] in ("LIB-07", "LIB-08"))
    assert g.verdict(eng(1)).startswith("NOT SUPPORTED") and g.verdict(eng(2)).startswith("NOT SUPPORTED")


def test_every_gap_in_the_matrix_is_covered_by_a_roadmap_work_package():
    road = (ROOT / "docs" / "ESTIMATING_GAP_ROADMAP.md").read_text(encoding="utf-8")
    covered = set(re.findall(r"\b([A-Z]{3}-\d{2})\b", road))
    open_ids = [r["id"] for r in REC if r["status"] in (IU, PA, MI)]
    assert not [i for i in open_ids if i not in covered], [i for i in open_ids if i not in covered]
    unknown = [i for i in covered if i not in {r["id"] for r in REC} and not i.startswith("WP-")]
    assert not unknown, unknown                                                             # roadmap cites no record that does not exist
    assert "no claim of Saudi Aramco" in road or "no claim of Saudi Aramco (or any client) compliance" in road
