"""The iteration-4 pages and endpoints render for the demonstration project and enforce the same server-side rules as every other route."""
from __future__ import annotations

import json

import pytest

from app.database import get_db
from tests.integration.test_api_ui import client, login  # noqa: F401


def _ui_login(c, user):
    assert c.post("/login", data={"username": user, "password": "pw-" + user}, follow_redirects=False).status_code == 303


@pytest.fixture()
def demo(client):
    from app.demo.build import seed_demo
    r = seed_demo(get_db())
    return get_db().scalar("SELECT id FROM projects ORDER BY id LIMIT 1")


def test_every_registered_report_renders_or_explains_why_not(client, demo):
    _ui_login(client, "est")
    idx = client.get(f"/projects/{demo}/analysis")
    assert idx.status_code == 200 and "Analysis" in idx.text and "never change an estimate" in idx.text
    from app.reporting.registry import REPORTS
    for name in REPORTS:
        r = client.get(f"/projects/{demo}/analysis/{name}")
        assert r.status_code == 200, (name, r.text[:300])
        assert "Traceback" not in r.text and ("banner warn" in r.text or "card" in r.text), name        # a result card, or a clear explanation (missing input)


def test_report_api_and_listing(client, demo):
    tok = login(client, "est")
    client.cookies.clear()
    names = {r["name"] for r in client.get("/api/reports", headers=tok).json()}
    assert {"rollup", "schedule", "loading", "manhours", "risk", "cashflow", "earned_value", "boe", "compliance"} <= names
    ok = client.get(f"/api/projects/{demo}/report/rollup", headers=tok)
    assert ok.status_code == 200 and ok.json()["tie_out"]["cbs"] is True and "rows" in ok.json()["matrix"]
    miss = client.get(f"/api/projects/{demo}/report/risk", headers=tok)                              # no quantified risks: a clear 422, not a 500
    assert miss.status_code == 422 and miss.json()["error"] == "RISK_NONE"
    assert client.get(f"/api/projects/{demo}/report/nope", headers=tok).status_code == 422
    assert client.get(f"/api/projects/{demo}/report/rollup?bogus=1", headers=tok).status_code == 422


def test_inputs_page_propose_submit_approve_through_the_ui_with_roles(client, demo):
    _ui_login(client, "est")
    page = client.get(f"/projects/{demo}/inputs")
    assert page.status_code == 200 and "productivity_factor" in page.text and "ships <b>none</b>" in page.text
    data = json.dumps({"category": "height", "factor": "1.2"})
    r = client.post("/ui/do/propose_param", data={"kind": "productivity_factor", "code": "UI-HT", "project_id": demo, "source": "Site study S-1 (test)", "data": data, "submit": "1",
                                                  "_next": f"/projects/{demo}/inputs"}, follow_redirects=False)
    assert r.status_code == 303 and "ok=" in r.headers["location"], r.headers["location"]
    pid = get_db().scalar("SELECT id FROM governed_params WHERE code='UI-HT'")
    # the estimator may approve a productivity factor (policy), a viewer may not
    _ui_login(client, "view")
    bad = client.post("/ui/do/approve_param", data={"param_id": pid, "_next": "/x"}, follow_redirects=False)
    assert "err=" in bad.headers["location"] and get_db().scalar("SELECT status FROM governed_params WHERE id=?", (pid,)) == "Pending Review"
    _ui_login(client, "com")
    ok = client.post("/ui/do/approve_param", data={"param_id": pid, "comments": "ok", "_next": "/x"}, follow_redirects=False)
    assert "ok=" in ok.headers["location"] and get_db().scalar("SELECT status FROM governed_params WHERE id=?", (pid,)) == "Approved"
    assert "UI-HT" in client.get(f"/projects/{demo}/inputs").text
    # bad data is refused with the validator's message, nothing stored
    r = client.post("/ui/do/propose_param", data={"kind": "productivity_factor", "code": "UI-BAD", "project_id": demo, "source": "s", "data": '{"category": "height", "factor": "-3"}',
                                                  "_next": "/x"}, follow_redirects=False)
    assert "err=" in r.headers["location"] and get_db().scalar("SELECT COUNT(*) FROM governed_params WHERE code='UI-BAD'") == 0


def test_save_analysis_creates_immutable_run_visible_in_ui(client, demo):
    _ui_login(client, "est")
    r = client.post("/ui/do/save_analysis", data={"project_id": demo, "report": "manhours", "params": "{}", "_next": f"/projects/{demo}/analysis"}, follow_redirects=False)
    assert "ok=" in r.headers["location"]
    rid = get_db().scalar("SELECT id FROM analysis_runs ORDER BY id DESC LIMIT 1")
    html = client.get(f"/projects/{demo}/analysis-run/{rid}").text
    assert "Saved analysis run" in html and "Own-labour hours" in html


def test_structure_page_forms_drive_wbs_tasks_and_roles(client, demo):
    _ui_login(client, "est")
    assert client.get(f"/projects/{demo}/structure").status_code == 200
    n = client.post("/ui/do/add_wbs_node", data={"project_id": demo, "code": "A1", "name": "Area 1", "_next": "/x"}, follow_redirects=False)
    assert "ok=" in n.headers["location"] and get_db().scalar("SELECT COUNT(*) FROM wbs_nodes WHERE project_id=?", (demo,)) == 1
    t = client.post("/ui/do/set_schedule_tasks", data={"project_id": demo, "_next": "/x", "tasks": json.dumps([{"task_code": "T1", "name": "One", "duration_days": "5", "wbs_code": "A1"},
                                                                                                                {"task_code": "T2", "name": "Two", "duration_days": "3", "predecessors": "T1-SS+2"}])},
                    follow_redirects=False)
    assert "ok=" in t.headers["location"]
    html = client.get(f"/projects/{demo}/structure").text
    assert "T1-SS+2" in html and "Area 1" in html and "piping.valve_install" in html
    rep = client.get(f"/projects/{demo}/analysis/schedule").text
    assert "project_working_days" in rep and "critical_path" in rep
    _ui_login(client, "view")
    bad = client.post("/ui/do/add_wbs_node", data={"project_id": demo, "code": "A2", "name": "x", "_next": "/x"}, follow_redirects=False)
    assert "err=" in bad.headers["location"] and get_db().scalar("SELECT COUNT(*) FROM wbs_nodes WHERE project_id=?", (demo,)) == 1
