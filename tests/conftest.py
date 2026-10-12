from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config as cfg  # noqa: E402
from app.database import Database, set_db  # noqa: E402
from app.models.actor import Actor  # noqa: E402
from app.services import refdata  # noqa: E402


@pytest.fixture()
def settings(tmp_path, monkeypatch):
    s = cfg.load_settings(env={})
    s.db_path = tmp_path / "var" / "test.db"
    s.data_dir = Path(cfg.BASE_DIR / "data")           # read-only reference data
    s.secret_key = "test-secret"
    s.allow_self_approval = True
    # runtime dirs under tmp so tests never write into the repo
    from dataclasses import replace
    s.__class__.projects_dir = property(lambda self: tmp_path / "projects")
    s.workspaces_override = tmp_path / "workspaces"
    s.__class__.outputs_dir = property(lambda self: tmp_path / "outputs")
    s.__class__.backups_dir = property(lambda self: tmp_path / "backups")
    cfg.set_settings(s)
    yield s
    cfg.set_settings(None)


@pytest.fixture()
def db(settings):
    d = Database(":memory:")
    d.migrate()
    set_db(d)
    yield d
    set_db(None)


@pytest.fixture()
def seeded(db):
    refdata.seed_reference(db)
    return db


ESTIMATOR = Actor("est", "Estimator", "Test Estimator")
PROCUREMENT = Actor("proc", "Procurement Reviewer", "Test Procurement")
COMMERCIAL = Actor("com", "Commercial Approver", "Test Commercial")
ADMIN = Actor("admin", "Administrator", "Test Admin")
VIEWER = Actor("view", "Viewer", "Test Viewer")
AI = Actor("ai-bot", "AI Assistant", "AI", is_ai=True)


@pytest.fixture()
def est():
    return ESTIMATOR


@pytest.fixture()
def proc():
    return PROCUREMENT


@pytest.fixture()
def com():
    return COMMERCIAL


@pytest.fixture()
def admin():
    return ADMIN


@pytest.fixture()
def viewer():
    return VIEWER


@pytest.fixture()
def ai():
    return AI
