"""GOV-05: a frozen estimate version can be re-computed IN FULL (direct cost, indirects, commercial policy, schedule, tax) from its snapshot alone,
after the live library, policy, tax, assumptions and indirects have all moved on."""
from __future__ import annotations

import json
from decimal import Decimal as D

import pytest

from app.estimators.estimate import compute_estimate, compute_estimate_from
from app.services import assumptions, commercial, estimates, governed, indirects, rates, snapshots
from tests.conftest import COMMERCIAL, ESTIMATOR, PROCUREMENT
from tests.helpers import build_mini


def test_replay_reproduces_frozen_totals_after_everything_changes(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    vid = estimates.freeze_version(seeded, ESTIMATOR, pid, "v1")
    frozen = estimates.get_version(seeded, vid)
    assert frozen["totals"]["selling_price_pre_tax"] is not None
    # --- the world moves on: new rate, new productivity factor, new indirect version, new policy, changed tax rate, new assumption value
    old = seeded.scalar("SELECT id FROM resource_rates WHERE resource_id='DEMO-MAT-001' AND status='Approved'")
    nr = rates.propose_rate(seeded, ESTIMATOR, "DEMO-MAT-001", unit_price="999", rate_type="Synthetic Demonstration Rate", price_date="2026-09-02", is_synthetic=True, submit=True)
    rates.approve_rate(seeded, PROCUREMENT, nr)
    f = governed.propose(seeded, ESTIMATOR, "productivity_factor", "X", {"category": "height", "factor": "3"}, source="s", submit=True)
    governed.approve(seeded, COMMERCIAL, f)
    indirects.revise_indirect(seeded, ESTIMATOR, pid, "IND-1", amount="99999")
    indirects.submit_indirect(seeded, ESTIMATOR, pid, "IND-1")
    indirects.approve_indirect(seeded, COMMERCIAL, pid, "IND-1")
    seeded.execute("UPDATE tax_categories SET rate_pct='99' WHERE code='VAT-STD'")
    live = compute_estimate(seeded, pid)
    assert live.totals()["selling_price_pre_tax"] != D(frozen["totals"]["selling_price_pre_tax"]) and live.fingerprint != frozen["inputs_hash"]
    # --- full replay still reproduces the frozen version exactly
    rp = snapshots.replay_estimate(seeded, vid)
    assert rp["ok"], rp["differences"]
    assert rp["fingerprint"] == frozen["inputs_hash"] and rp["state"] == frozen["state"] and rp["legacy_snapshot"] is False
    assert rp["replayed"] == rp["frozen"] and snapshots.verify_snapshot(seeded, vid)["ok"] and snapshots.replay_direct_cost(seeded, vid)["ok"]
    assert estimates.get_version(seeded, vid)["totals"] == frozen["totals"]                      # the frozen version itself was never rewritten


def test_replay_detects_a_tampered_snapshot_and_changed_engine_inputs(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    vid = estimates.freeze_version(seeded, ESTIMATOR, pid, "v1")
    snap = snapshots.get_snapshot(seeded, vid)
    # an edit to the stored JSON breaks the integrity hash
    row = seeded.one("SELECT id, snapshot_json FROM estimate_snapshots WHERE estimate_version_id=?", (vid,))
    seeded.update("estimate_snapshots", {"snapshot_json": row["snapshot_json"] + " "}, "id=?", (row["id"],))
    with pytest.raises(ValueError):
        snapshots.replay_estimate(seeded, vid)
    # an honest replay engine run on altered inputs shows the difference (what replay is for)
    seeded.update("estimate_snapshots", {"snapshot_json": row["snapshot_json"]}, "id=?", (row["id"],))
    inp = snapshots.inputs_from_snapshot(seeded, snap)
    ex = snapshots.extras_from_snapshot(snap)
    inp.takeoff = {}
    inp.items = [dict(i, quantity="11") if i["item_type"] == "item" else i for i in inp.items]
    changed = compute_estimate_from(inp, ex)
    assert changed.fingerprint != snap["expected"]["fingerprint"]


def test_legacy_snapshot_without_extras_still_replays(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    vid = estimates.freeze_version(seeded, ESTIMATOR, pid, "v1")
    row = seeded.one("SELECT id, snapshot_json FROM estimate_snapshots WHERE estimate_version_id=?", (vid,))
    snap = json.loads(row["snapshot_json"])
    snap.pop("extras")                                                                          # as written before this capability existed
    text = json.dumps(snap, indent=1, default=str, ensure_ascii=False)
    import hashlib
    seeded.update("estimate_snapshots", {"snapshot_json": text, "sha256": hashlib.sha256(text.encode()).hexdigest()}, "id=?", (row["id"],))
    rp = snapshots.replay_estimate(seeded, vid)
    assert rp["ok"] and rp["legacy_snapshot"] is True


def test_no_snapshot_reports_cleanly(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    vid = estimates.freeze_version(seeded, ESTIMATOR, pid, "v1")
    seeded.execute("DELETE FROM estimate_snapshots WHERE estimate_version_id=?", (vid,))
    rp = snapshots.replay_estimate(seeded, vid)
    assert rp["ok"] is False and "No snapshot" in rp["problems"][0]
