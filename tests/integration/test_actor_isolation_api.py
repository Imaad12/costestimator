"""The production gate is enforced server-side: the same refusals come back through the REST API (and therefore the UI and CLI, which call the same services)."""
from __future__ import annotations

from app.database import get_db
from app.services import auth, estimates
from tests.approvals.test_actor_isolation import finish, mk_users, real_project
from tests.integration.test_api_ui import client, login  # noqa: F401


def test_api_refuses_test_principal_and_unready_exports(client, tmp_path):
    db = get_db()
    U = {k: v for k, v in mk_users(db).items()}
    pid = real_project(db, tmp_path, U)
    auth.create_user(db, "t-com2", "Test Commercial", "Commercial Approver", "pw-t-com2", actor_type="test")
    vid = estimates.freeze_version(db, U["h-est"], pid, "v1")
    estimates.submit_version(db, U["h-est"], vid)
    tok = {"Authorization": "Bearer " + client.post("/api/auth/login", json={"username": "t-com2", "password": "pw-t-com2"}).json()["token"]}
    client.cookies.clear()
    r = client.post("/api/actions/approve_tender_export", json={"project_id": pid, "version_id": vid}, headers=tok)
    assert r.status_code in (403, 409, 422) and r.json()["error"] == "NON_HUMAN_ACTOR"
    r = client.post("/api/actions/approve_version", json={"version_id": vid}, headers=tok)
    assert r.json()["error"] == "NON_HUMAN_ACTOR"
    r = client.post("/api/actions/export_submission", json={"project_id": pid, "version_id": vid, "approval_id": 999999}, headers=tok)
    assert r.json()["error"] in ("NON_HUMAN_ACTOR", "EXPORT_NOT_APPROVED") and not db.scalar("SELECT COUNT(*) FROM exports WHERE submission_ready=1")
    # the registered human chain through the API reaches readiness; the same API cannot be used by a viewer
    vid2, ap = finish(db, tmp_path, U, pid)
    ex = client.post("/api/actions/export_submission", json={"project_id": pid, "version_id": vid2, "approval_id": ap}, headers=tok)
    assert ex.json()["error"] == "NON_HUMAN_ACTOR"                                                  # a test principal cannot even produce the package
    from app.services import auth as _a
    _a.create_user(db, "h-api", "Human API", "Estimator", "pw-h-api")
    hh = {"Authorization": "Bearer " + client.post("/api/auth/login", json={"username": "h-api", "password": "pw-h-api"}).json()["token"]}
    client.cookies.clear()
    ex = client.post("/api/actions/export_submission", json={"project_id": pid, "version_id": vid2, "approval_id": ap}, headers=hh)
    assert ex.status_code == 200 and db.scalar("SELECT COUNT(*) FROM exports WHERE submission_ready=1 AND readiness='production'") == 4
