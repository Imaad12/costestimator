"""HTTP-level tests: authentication, server-side authorisation (UI and API), uploads, and every UI page rendering."""
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.config as cfg
from app.database import Database, get_db, set_db
from app.services import auth, refdata


@pytest.fixture()
def client(tmp_path, monkeypatch):
    s = cfg.load_settings(env={})
    s.db_path = tmp_path / "var" / "app.db"
    s.data_dir = cfg.BASE_DIR / "data"
    s.secret_key = "test-secret-key"
    s.__class__.projects_dir = property(lambda self: tmp_path / "projects")
    s.__class__.outputs_dir = property(lambda self: tmp_path / "outputs")
    s.__class__.backups_dir = property(lambda self: tmp_path / "backups")
    cfg.set_settings(s)
    set_db(None)
    db = get_db()
    refdata.seed_reference(db)
    for u, role in (("admin", "Administrator"), ("est", "Estimator"), ("proc", "Procurement Reviewer"), ("com", "Commercial Approver"), ("view", "Viewer")):
        auth.create_user(db, u, u, role, "pw-" + u)
    auth.create_user(db, "ai-assistant", "AI", "AI Assistant", None, is_ai=True)
    from app.main import app
    with TestClient(app) as c:
        yield c
    set_db(None)
    cfg.set_settings(None)


def login(client, user):
    r = client.post("/api/auth/login", json={"username": user, "password": "pw-" + user})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_authentication_required_and_bad_tokens_rejected(client):
    assert client.get("/api/projects").status_code == 401
    assert client.get("/api/projects", headers={"Authorization": "Bearer garbage"}).status_code == 401
    good = login(client, "est")["Authorization"].split()[1]
    payload, sig = good.rsplit(".", 1)
    assert client.get("/api/projects", headers={"Authorization": f"Bearer {payload}.{'0' * len(sig)}"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "est", "password": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "ai-assistant", "password": ""}).status_code == 401      # AI principals cannot sign in
    client.cookies.clear()
    assert client.get("/", follow_redirects=False).status_code in (303, 307)                                         # UI redirects to /login
    assert client.get("/api/health").json() == {"status": "ok"}


def test_server_side_permissions_on_the_api(client):
    est, view, proc, com = (login(client, u) for u in ("est", "view", "proc", "com"))
    client.cookies.clear()          # authenticate strictly by Bearer header in this test
    r = client.post("/api/actions/create_project", json={"name": "Perm test"}, headers=view)
    assert r.status_code == 403 and r.json()["error"] == "PERMISSION_DENIED"
    r = client.post("/api/actions/create_project", json={"name": "Perm test"}, headers=est)
    assert r.status_code == 200
    # estimator proposes a rate; only procurement/commercial may approve; estimator may only approve provisionally
    r = client.post("/api/actions/propose_rate", json={"resource_id": "MAT-C-001", "unit_price": "10", "rate_type": "Published Market Price", "price_date": "2026-09-01",
                                                      "evidence": "catalogue p.3 (SYNTHETIC)", "source_id": "SRC-001", "submit": True}, headers=est)
    assert r.status_code == 200, r.text
    rid = r.json()["result"]
    assert client.post("/api/actions/approve_rate", json={"rate_id": rid}, headers=est).status_code == 403
    assert client.post("/api/actions/approve_rate", json={"rate_id": rid}, headers=view).status_code == 403
    assert client.post("/api/actions/approve_rate", json={"rate_id": rid}, headers=proc).status_code == 200
    assert client.post("/api/actions/approve_rate", json={"rate_id": rid}, headers=proc).status_code == 409              # no second approval
    # commercial-only actions
    assert client.post("/api/actions/approve_policy", json={"policy_id": 1}, headers=proc).status_code in (403, 404)
    assert client.post("/api/actions/nonexistent", json={}, headers=est).status_code == 422
    # admin-only
    assert client.post("/api/actions/create_backup", json={}, headers=est).status_code == 403
    assert client.post("/api/actions/create_backup", json={}, headers=login(client, "admin")).status_code == 200
    assert client.get("/api/audit/verify", headers=est).json()["ok"]


def test_ui_forms_enforce_permissions_server_side(client):
    c = client
    assert c.post("/login", data={"username": "view", "password": "pw-view"}, follow_redirects=False).status_code == 303
    r = c.post("/ui/do/create_project", data={"name": "x", "_next": "/projects"}, follow_redirects=False)
    assert r.status_code == 303 and "PERMISSION_DENIED" in r.headers["location"]
    c.get("/logout")
    c.post("/login", data={"username": "est", "password": "pw-est"})
    r = c.post("/ui/do/create_project", data={"name": "UI project", "_next": "/projects/{result}"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/projects/PRJ-0001")
    r = c.post("/ui/do/approve_tax_category", data={"tax_id": "1", "evidence": "x", "_next": "/projects"}, follow_redirects=False)
    assert "PERMISSION_DENIED" in r.headers["location"]                                                     # estimator cannot approve tax


def test_wrong_cookie_is_redirected(client):
    client.cookies.set("ksa_token", "tampered.value")
    assert client.get("/projects", follow_redirects=False).status_code == 303


def test_uploads_preview_import_and_downloads(client, tmp_path):
    h = login(client, "est")
    pid = client.post("/api/actions/create_project", json={"name": "Upload"}, headers=h).json()["result"]
    csvp = tmp_path / "b.csv"
    csvp.write_text("Item,Description,Unit,Qty\n1,Excavation,m3,100\n2,Blocks,sqm,50\n3,Bad,m,xx\n")
    with open(csvp, "rb") as f:
        pv = client.post(f"/api/projects/{pid}/boq/preview", files={"file": ("b.csv", f)}, headers=h).json()
    assert pv["header_row"] == 1 and pv["proposed_mapping"]["quantity"] == 3 and pv["missing_required"] == []
    with open(csvp, "rb") as f:
        r = client.post(f"/api/projects/{pid}/boq/import", files={"file": ("b.csv", f)}, data={"revision": "A"}, headers=h)
    assert r.status_code == 200 and r.json()["items_new"] == 2 and r.json()["rejected"] == 1
    # same filename again: stored under a new name, original upload untouched
    with open(csvp, "rb") as f:
        client.post(f"/api/projects/{pid}/boq/import", files={"file": ("b.csv", f)}, headers=h)
    ups = sorted(p.name for p in (tmp_path / "projects" / pid / "uploads").iterdir())
    assert len(ups) == 4 and any(n.startswith("b__") for n in ups)
    items = client.get(f"/api/projects/{pid}/boq", headers=h).json()
    assert {i["item_key"] for i in items if i["item_type"] == "item"} == {"1", "2"}
    # master workbook download
    r = client.get(f"/api/projects/{pid}/workbook", headers=h)
    assert r.status_code == 200 and r.content[:2] == b"PK"
    bad = client.post(f"/api/projects/{pid}/boq/import", files={"file": ("x.xlsx", b"not an excel file")}, headers=h)
    assert bad.status_code == 422 and bad.json()["error"] == "MALFORMED_FILE"
    # viewers cannot import
    assert client.post(f"/api/projects/{pid}/boq/import", files={"file": ("b.csv", b"Item,Description,Unit,Qty\n1,a,m,1")}, headers=login(client, "view")).status_code == 403


def test_every_ui_page_renders_for_the_demo_project(client):
    from app.demo.build import seed_demo
    pid = seed_demo(get_db())["project_id"]
    client.post("/login", data={"username": "admin", "password": "pw-admin"})
    pages = ["/", "/projects", f"/projects/{pid}/", f"/projects/{pid}/boq", f"/projects/{pid}/mapping", f"/projects/{pid}/estimate", f"/projects/{pid}/estimate?preliminary=1",
             f"/projects/{pid}/estimate?item=2.1", f"/projects/{pid}/assumptions", f"/projects/{pid}/assumptions/impact?aid=ASMP-C-003&value=6", f"/projects/{pid}/procurement",
             f"/projects/{pid}/quotes", f"/projects/{pid}/commercial", f"/projects/{pid}/registers", f"/projects/{pid}/reconciliation", f"/projects/{pid}/reports",
             "/libraries", "/libraries?q=pump&missing=1", "/libraries/DEMO-MAT-003", "/assumptions", "/assumptions?family=C", "/assemblies", "/assemblies?code=DEMO-A-RC",
             "/approvals", "/settings", f"/projects/{pid}/workbook"]
    for p in pages:
        r = client.get(p)
        assert r.status_code == 200, (p, r.status_code, r.text[:300])
    dash = client.get("/").text
    assert "DEMO / SYNTHETIC" in dash and "Preliminary" in dash
    est_page = client.get(f"/projects/{pid}/estimate").text
    assert "UNPRICED" in est_page and "Preliminary — Incomplete" in est_page
    # the approvals queue lists pending work
    assert "Rates" in client.get("/approvals").text


def test_ui_end_to_end_actions_for_the_demo_project(client):
    from app.demo.build import seed_demo
    pid = seed_demo(get_db())["project_id"]
    client.post("/login", data={"username": "proc", "password": "pw-proc"})
    r = client.post("/ui/do/detect_needs", data={"project_id": pid, "_next": f"/projects/{pid}/procurement"}, follow_redirects=False)
    assert "ok=" in r.headers["location"]
    page = client.get(f"/projects/{pid}/procurement").text
    for name in ("Sprinkler head", "Air handling unit", "CCTV IP camera", "Passenger lift"):
        assert name in page
    pkg = get_db().scalar("SELECT id FROM procurement_packages WHERE project_id=? AND trade='J'", (pid,))
    r = client.post("/ui/do/create_rfq", data={"project_id": pid, "package_id": pkg, "language": "en", "_next": f"/projects/{pid}/procurement"}, follow_redirects=False)
    assert "ok=" in r.headers["location"]
    rid = get_db().scalar("SELECT id FROM rfqs LIMIT 1")
    assert "Passenger lift" in client.get(f"/rfq/{rid}").text
    assert client.get(f"/rfq/{rid}/download/xlsx").content[:2] == b"PK"
    r = client.post("/ui/do/run_reconciliation", data={"project_id": pid, "_next": f"/projects/{pid}/reconciliation"}, follow_redirects=False)
    page = client.get(f"/projects/{pid}/reconciliation").text
    assert "UNPRICED_ITEM" in page and "MISSING_RATE" in page and "Critical" in page


def test_authoring_forms_create_resource_assembly_and_policy(client):
    c = client
    c.post("/login", data={"username": "est", "password": "pw-est"})
    r = c.post("/ui/do/create_resource", data={"resource_type": "material", "description": "Test grout", "unit": "kg", "cost_code": "C.07", "_next": "/libraries"}, follow_redirects=False)
    assert "ok=" in r.headers["location"]
    rid = get_db().scalar("SELECT id FROM resources WHERE description='Test grout'")
    assert rid.startswith("MAT-C-")
    r = c.post("/ui/do/create_assembly", data={"code": "UI-ASM", "description": "UI assembly", "unit": "m2", "cost_code": "C.07", "_next": "/assemblies"}, follow_redirects=False)
    assert "ok=" in r.headers["location"]
    r = c.post("/ui/do/add_assembly_line", data={"code": "UI-ASM", "line_type": "material", "resource_id": rid, "factor": "2", "factor_includes_waste": "1", "waste_basis": "fixed_pct", "waste_value": "5", "_next": "/assemblies"},
               follow_redirects=False)
    assert "DOUBLE_WASTE" in r.headers["location"]                                     # waste cannot be applied twice - rejected by the service
    r = c.post("/ui/do/add_assembly_line", data={"code": "UI-ASM", "line_type": "material", "resource_id": rid, "factor": "2", "waste_basis": "fixed_pct", "waste_value": "5", "_next": "/assemblies"}, follow_redirects=False)
    assert "ok=" in r.headers["location"]
    r = c.post("/ui/do/add_assembly_line", data={"code": "UI-ASM", "line_type": "labour", "resource_id": "LAB-028", "factor": "10", "productivity_basis": "output_per_crew_shift",
                                                  "crew": "LAB-028:2;LAB-014:1", "_next": "/assemblies"}, follow_redirects=False)
    assert "ok=" in r.headers["location"]
    assert "UI-ASM" in c.get("/assemblies?code=UI-ASM").text
    pol = '{"method":"markup","markup_pct":"7","contingency":{"pct":"2","base":"direct"}}'
    r = c.post("/ui/do/create_policy", data={"code": "UI-POL", "name": "UI policy", "config": pol, "_next": "/projects"}, follow_redirects=False)
    assert "ok=" in r.headers["location"]
    r = c.post("/ui/do/create_policy", data={"code": "UI-POL2", "name": "bad", "config": '{"method":"margin","margin_pct":"100"}', "_next": "/projects"}, follow_redirects=False)
    assert "POLICY_INVALID" in r.headers["location"]
    r = c.post("/ui/do/create_policy", data={"code": "UI-POL3", "name": "bad", "config": "not json", "_next": "/projects"}, follow_redirects=False)
    assert "valid JSON" in r.headers["location"] or "valid%20JSON" in r.headers["location"] or "JSON" in r.headers["location"]
