"""Read-only estimate cache: identical results, invalidated by any write (own connection or another process), bypassed by what-if overrides."""
from __future__ import annotations

import sqlite3

import pytest

from app.database import Database
from app.estimators.estimate import compute_estimate, compute_estimate_cached
from app.services import indirects
from tests.conftest import ESTIMATOR
from tests.helpers import build_mini


def test_cache_hits_until_any_change(seeded, tmp_path):
    pid = build_mini(seeded, tmp_path)
    a = compute_estimate_cached(seeded, pid)
    assert compute_estimate_cached(seeded, pid) is a                                          # same object: nothing recomputed
    assert a.fingerprint == compute_estimate(seeded, pid).fingerprint                         # and identical to a fresh computation
    assert compute_estimate_cached(seeded, pid, include_unapproved=True) is not a             # different key
    indirects.add_indirect(seeded, ESTIMATOR, pid, code="IND-X", category="c", description="d", method="fixed", amount="1")
    b = compute_estimate_cached(seeded, pid)
    assert b is not a and b.fingerprint != a.fingerprint                                      # a write invalidated it
    over = compute_estimate_cached(seeded, pid, assumption_overrides={"labour.shift_hours": "10"})
    assert over is not compute_estimate_cached(seeded, pid, assumption_overrides={"labour.shift_hours": "10"})   # what-if never cached
    assert compute_estimate_cached(seeded, pid) is b


def test_cache_sees_writes_from_another_connection(tmp_path):
    from app.config import get_settings
    from app.services import refdata
    path = tmp_path / "shared.db"
    db = Database(path)
    db.migrate()
    refdata.seed_reference(db)
    pid = build_mini(db, tmp_path)
    a = compute_estimate_cached(db, pid)
    other = sqlite3.connect(str(path), isolation_level=None)                                   # e.g. a CLI process importing while the server runs
    other.execute("UPDATE indirect_items SET amount='123456' WHERE project_id=?", (pid,))
    other.close()
    b = compute_estimate_cached(db, pid)
    assert b is not a and b.fingerprint != a.fingerprint
