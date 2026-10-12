"""Numbered project workspaces, project CLAUDE.md, indexer, isolation, idempotency, snapshots (all figures SYNTHETIC)."""
from __future__ import annotations

import json

import pytest

from app.core.errors import Conflict, ValidationFailed
from app.services import estimates, project_index, projects, rates, snapshots, workspaces
from tests.conftest import COMMERCIAL, ESTIMATOR, PROCUREMENT
from tests.helpers import approved_rate, build_mini

EXPECTED = ["1. Tender Documents", "2. AI Context", "3. BOQ & Takeoff", "4. Clarifications & Assumptions", "5. Estimate & Cost Build-Up",
            "6. Procurement & Quotations", "7. Programme & Indirects", "8. Commercial Submission", "9. Reconciliation & Approvals",
            "10. Exports & Archive"]


def test_folder_names_and_numbering_are_the_product_requirement():
    assert workspaces.AREA_NAMES == EXPECTED
    assert [n.split(".")[0] for n in workspaces.AREA_NAMES] == [str(i) for i in range(1, 11)]


def test_new_project_creates_complete_workspace(seeded, settings):
    pid = projects.create_project(seeded, ESTIMATOR, name="Office Fit-out (SYNTHETIC)", client="Demo Client", location="Riyadh",
                                  project_type="Fit-out", trades=["Architectural", "HVAC", "Electrical"], is_demo=True,
                                  drawing_revision="A-101 RevB", spec_revision="Spec R2")
    root = settings.workspaces_dir / f"{pid}-office-fit-out-synthetic"
    assert root.is_dir()
    for n in EXPECTED:
        assert (root / n).is_dir(), n
    man = json.loads((root / "project.json").read_text(encoding="utf-8"))
    assert man["project_id"] == pid and man["trades"] == ["Architectural", "HVAC", "Electrical"] and man["areas"]["boq"] == "3. BOQ & Takeoff"
    md = (root / "CLAUDE.md").read_text(encoding="utf-8")
    for needle in (pid, "Demo Client", "Riyadh", "Fit-out", "HVAC", "SAR", "A-101 RevB", "Spec R2", "SYNTHETIC / DEMO / NOT A MARKET QUOTE",
                   "Workspace map", "Human-approval rules", "Outstanding issues", "Updating this context safely", "No BOQ imported yet"):
        assert needle in md, needle
    row = projects.get_project(seeded, pid)
    assert row["workspace_path"] == root.name and row["workspace_slug"] == "office-fit-out-synthetic"
    for secret in ("password", "api_key", "ANTHROPIC_API_KEY=", "sk-"):
        assert secret not in md.lower().replace("api keys", "")


def test_duplicate_project_id_is_refused_and_nothing_is_overwritten(seeded, settings):
    pid = projects.create_project(seeded, ESTIMATOR, name="First", id="PRJ-0100")
    root = workspaces.resolve_dir(pid, seeded)
    mark = root / "1. Tender Documents" / "orig.txt"
    mark.write_text("original")
    with pytest.raises(Conflict):
        projects.create_project(seeded, ESTIMATOR, name="Other name", id="PRJ-0100")
    assert mark.read_text() == "original"
    assert len(list(settings.workspaces_dir.iterdir())) == 1               # no second folder was created


def test_ensure_workspace_is_idempotent_repairs_missing_folders_and_keeps_files(seeded, settings):
    pid = projects.create_project(seeded, ESTIMATOR, name="Repeat")
    root = workspaces.resolve_dir(pid, seeded)
    keep = root / "3. BOQ & Takeoff" / "mine.csv"
    keep.write_text("a,b")
    (root / "6. Procurement & Quotations").rmdir()                         # folder went missing
    (root / "CLAUDE.md").write_text(workspaces.GEN_BEGIN + "\nold\n" + workspaces.GEN_END + "\n\n## Human notes (preserved on refresh)\n\nMY NOTE\n")
    r1 = workspaces.ensure_workspace(seeded, pid)
    r2 = workspaces.ensure_workspace(seeded, pid)
    assert r1 == r2 == root
    assert (root / "6. Procurement & Quotations").is_dir() and keep.read_text() == "a,b"
    md = (root / "CLAUDE.md").read_text(encoding="utf-8")
    assert "MY NOTE" in md and "\nold\n" not in md and md.count(workspaces.GEN_BEGIN) == 1       # block regenerated, human notes kept
    assert len(list(settings.workspaces_dir.iterdir())) == 1


def test_human_authored_claude_md_without_markers_is_never_clobbered(seeded, settings):
    pid = projects.create_project(seeded, ESTIMATOR, name="Hand")
    root = workspaces.resolve_dir(pid, seeded)
    (root / "CLAUDE.md").write_text("# My own instructions\nkeep me\n")
    workspaces.ensure_workspace(seeded, pid)
    t = (root / "CLAUDE.md").read_text(encoding="utf-8")
    assert t.startswith("# My own instructions\nkeep me") and workspaces.GEN_BEGIN in t


def test_workspace_adopts_existing_folder_after_db_loss_and_rejects_foreign_folder(seeded, settings):
    settings.workspaces_dir.mkdir(parents=True, exist_ok=True)
    pre = settings.workspaces_dir / "PRJ-0200-restored"
    (pre / "1. Tender Documents").mkdir(parents=True)
    (pre / "1. Tender Documents" / "spec.txt").write_text("kept")
    (pre / "project.json").write_text(json.dumps({"project_id": "PRJ-0200"}))
    pid = projects.create_project(seeded, ESTIMATOR, name="Restored", id="PRJ-0200")
    assert workspaces.resolve_dir(pid, seeded) == pre and (pre / "1. Tender Documents" / "spec.txt").read_text() == "kept"
    # a folder that claims another project id is never reused
    foreign = settings.workspaces_dir / "PRJ-0300-other"
    foreign.mkdir()
    (foreign / "project.json").write_text(json.dumps({"project_id": "PRJ-9999"}))
    assert workspaces.find_existing("PRJ-0300") is None
    with pytest.raises(ValidationFailed):
        workspaces.check_project_id("../escape")


def test_project_isolation_files_and_quotes_stay_in_their_own_workspace(seeded, settings):
    a = projects.create_project(seeded, ESTIMATOR, name="Alpha")
    b = projects.create_project(seeded, ESTIMATOR, name="Beta")
    (projects.project_dir(a, "uploads") / "a.csv").write_text("x")
    assert not list(projects.project_dir(b, "uploads").iterdir())
    assert workspaces.area_dir(a, "procurement") != workspaces.area_dir(b, "procurement")
    assert workspaces.resolve_dir(a, seeded).name.startswith(a) and workspaces.resolve_dir(b, seeded).name.startswith(b)


def test_project_assumption_override_does_not_change_global_default(seeded):
    pid = projects.create_project(seeded, ESTIMATOR, name="Assump iso")
    other = projects.create_project(seeded, ESTIMATOR, name="Assump other")
    row = seeded.one("SELECT id, default_value FROM assumptions WHERE default_value IS NOT NULL LIMIT 1")
    if row is None:
        pytest.skip("no assumption with a default value in the reference set")
    before = seeded.scalar("SELECT default_value FROM assumptions WHERE id=?", (row["id"],))
    from app.services import assumptions
    assumptions.set_override(seeded, ESTIMATOR, pid, row["id"], "123456", reason="test override")
    assert seeded.scalar("SELECT default_value FROM assumptions WHERE id=?", (row["id"],)) == before          # global default untouched
    assert assumptions.resolve(seeded, other, row["id"]).value == before                                     # other project untouched
    assert assumptions.resolve(seeded, pid, row["id"]).origin != "global_default"


def test_indexer_inventories_versions_and_flags_changes(seeded, settings):
    pid = projects.create_project(seeded, ESTIMATOR, name="Index me")
    root = workspaces.resolve_dir(pid, seeded)
    t = root / "1. Tender Documents"
    (t / "Spec_Section_03_Concrete_RevB.txt").write_text("Concrete shall be grade C30 with 50mm cover.")
    (t / "A-101_Plan_R2.dwg").write_bytes(b"\x00\x01binary")
    (t / "broken.pdf").write_bytes(b"not a pdf")
    (t / "site.xlsx").write_bytes(b"not an xlsx")
    rep = project_index.index_project(seeded, ESTIMATOR, pid)
    docs = {d["file_name"]: d for d in project_index.list_documents(seeded, pid)}
    assert rep["new"] == 4 and set(docs) == {"Spec_Section_03_Concrete_RevB.txt", "A-101_Plan_R2.dwg", "broken.pdf", "site.xlsx"}
    s = docs["Spec_Section_03_Concrete_RevB.txt"]
    assert s["extraction_status"] == "Extracted" and s["revision"] == "B" and s["category"] == "specification" and s["sha256"] and s["size_bytes"] > 0
    assert docs["A-101_Plan_R2.dwg"]["extraction_status"] == "Not text-extracted" and "CAD/BIM" in docs["A-101_Plan_R2.dwg"]["extraction_error"]
    assert docs["A-101_Plan_R2.dwg"]["revision"] == "2"
    assert docs["broken.pdf"]["extraction_status"] == "Extraction error" and docs["broken.pdf"]["extraction_error"]
    assert (root / "2. AI Context" / "project_index.json").exists() and (root / "2. AI Context" / "project_summary.md").exists()
    hits = project_index.search(seeded, pid, "grade c30")
    assert hits and hits[0]["file"].endswith("Concrete_RevB.txt")
    # unchanged re-run: nothing re-extracted
    assert project_index.index_project(seeded, ESTIMATOR, pid)["unchanged"] == 4
    # source changes -> new extract version, old kept, flagged for review, original untouched by the indexer
    (t / "Spec_Section_03_Concrete_RevB.txt").write_text("Concrete shall be grade C40.")
    rep = project_index.index_project(seeded, ESTIMATOR, pid)
    d = {x["file_name"]: x for x in project_index.list_documents(seeded, pid)}["Spec_Section_03_Concrete_RevB.txt"]
    assert rep["changed"] == 1 and d["extract_version"] == 2 and d["review_status"] == "Source changed - review"
    ex = sorted((root / "2. AI Context" / "extracts").glob("*.txt"))
    assert len(ex) == 2 and "C30" in ex[0].read_text() and "C40" in ex[1].read_text()
    assert (t / "Spec_Section_03_Concrete_RevB.txt").read_text() == "Concrete shall be grade C40."
    project_index.mark_reviewed(seeded, ESTIMATOR, pid, d["id"])
    # deleted file -> Missing, never silently dropped
    (t / "A-101_Plan_R2.dwg").unlink()
    assert project_index.index_project(seeded, ESTIMATOR, pid)["missing"] == 1
    assert {x["file_name"]: x for x in project_index.list_documents(seeded, pid)}["A-101_Plan_R2.dwg"]["extraction_status"] == "Missing"


def test_snapshot_keeps_frozen_estimate_reproducible_after_a_new_rate_is_approved(seeded, tmp_path):
    db = seeded
    pid = build_mini(db, tmp_path)
    vid = estimates.freeze_version(db, ESTIMATOR, pid, "v1")
    v1 = estimates.get_version(db, vid)
    snap = snapshots.get_snapshot(db, vid)
    assert snap and snap["used_rate_ids"] and snap["expected"]["direct_cost_total"] == v1["totals"]["direct_cost"]
    assert snapshots.verify_snapshot(db, vid)["ok"] and snapshots.replay_direct_cost(db, vid)["ok"]
    wf = workspaces.resolve_dir(pid, db) / "5. Estimate & Cost Build-Up" / "versions"
    assert any(wf.glob("*_inputs_snapshot.json"))
    # publish a NEW approved global rate for the same resource (doubles the price)
    approved_rate(db, "DEMO-MAT-001", "200")
    # the frozen version row is unchanged ...
    assert estimates.get_version(db, vid)["totals"] == v1["totals"] and estimates.get_version(db, vid)["inputs_hash"] == v1["inputs_hash"]
    # ... a fresh computation differs (live library moved on) ...
    from app.estimators.estimate import compute_estimate
    assert compute_estimate(db, pid).fingerprint != v1["inputs_hash"]
    # ... and the snapshot still reproduces the frozen direct cost, and reports the newer rate
    ver = snapshots.verify_snapshot(db, vid)
    assert ver["ok"] and ver["newer_rates_available"] and snapshots.replay_direct_cost(db, vid)["ok"]
    # tampering with an immutable field of a pinned rate is detected
    rid = snap["used_rate_ids"][0]
    db.execute("UPDATE resource_rates SET unit_price='999' WHERE id=?", (rid,))
    assert not snapshots.verify_snapshot(db, vid)["ok"]
