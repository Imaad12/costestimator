"""UI flows for the numbered workspace, completeness report and the public-source rate-update screens."""
from __future__ import annotations

import io
from pathlib import Path

from app.database import get_db
from tests.integration.test_api_ui import client, login  # noqa: F401  (shared fixture)


def _login(c, user):
    c.cookies.clear()
    assert c.post("/login", data={"username": user, "password": "pw-" + user}, follow_redirects=False).status_code == 303


def test_first_run_dashboard_and_global_library_notice(client):
    _login(client, "est")
    html = client.get("/").text
    assert "Getting started" in html and "No approved real rates yet" in html and "1. Tender Documents" in html
    assert "0 approved real rates" in client.get("/rates/updates").text


def test_create_project_shows_workspace_path_next_action_and_numbered_folders(client):
    _login(client, "est")
    r = client.post("/ui/do/create_project", data={"name": "Office Fitout", "client": "ACME", "project_type": "Fit-out", "trades": "HVAC, Electrical",
                                                   "drawing_revision": "Rev B", "_next": "/projects/{result}/workspace"}, follow_redirects=False)
    assert r.headers["location"].startswith("/projects/PRJ-0001/workspace")
    page = client.get("/projects/PRJ-0001/workspace").text
    assert "PRJ-0001-office-fitout" in page and "Next action" in page and "copy the tender documents" in page
    for n in ("1. Tender Documents", "2. AI Context", "3. BOQ &amp; Takeoff", "10. Exports &amp; Archive"):
        assert n in page
    assert "HVAC, Electrical" in page and "Rev B" in page
    root = next(Path(__import__("app.config", fromlist=["x"]).get_settings().workspaces_dir).glob("PRJ-0001-*"))
    assert (root / "CLAUDE.md").exists() and (root / "project.json").exists() and (root / "5. Estimate & Cost Build-Up").is_dir()
    # upload a tender document twice: both kept, original never overwritten
    for _ in range(2):
        r = client.post("/projects/PRJ-0001/workspace/upload", data={"area": "tender"}, files={"file": ("Spec_RevA.txt", io.BytesIO(b"Concrete C30"), "text/plain")},
                        follow_redirects=False)
        assert r.status_code == 303 and "ok=" in r.headers["location"]
    names = sorted(p.name for p in (root / "1. Tender Documents").iterdir())
    assert len(names) == 2 and "Spec_RevA.txt" in names
    bad = client.post("/projects/PRJ-0001/workspace/upload", data={"area": "ai_context"}, files={"file": ("x.txt", io.BytesIO(b"x"), "text/plain")}, follow_redirects=False)
    assert "err=" in bad.headers["location"]
    r = client.post("/ui/do/index_project_documents", data={"project_id": "PRJ-0001", "_next": "/projects/PRJ-0001/workspace"}, follow_redirects=False)
    assert "ok=" in r.headers["location"]
    page = client.get("/projects/PRJ-0001/workspace").text
    assert "Spec_RevA.txt" in page and "Extracted" in page
    comp = client.get("/projects/PRJ-0001/completeness").text
    assert "No BOQ items" in comp and "0 approved real rates" in comp and "Blocked" in comp
    # viewer cannot upload or index
    _login(client, "view")
    r = client.post("/ui/do/index_project_documents", data={"project_id": "PRJ-0001", "_next": "/x"}, follow_redirects=False)
    assert "PERMISSION_DENIED" in r.headers["location"] or "read-only" in r.headers["location"]


def test_rate_update_screens_import_review_publish_and_approval_separation(client):
    db = get_db()
    _login(client, "est")
    r = client.post("/ui/do/create_resource", data={"resource_type": "material", "description": "Ready-mix concrete C30 supply", "unit": "m3", "cost_code": "C.01",
                                                    "_next": "/libraries"}, follow_redirects=False)
    rid = db.scalar("SELECT id FROM resources WHERE description='Ready-mix concrete C30 supply'")
    csv = (f"Resource ID,Description,Unit,Unit Price,Currency,Price Date,VAT,Delivery,Source URL\n{rid},Ready-mix C30,m3,310.50,SAR,2026-09-15,Excluded,Delivered,"
           f"https://example.invalid/list\n{rid},bad,m3,x,SAR,2026-09-15,Excluded,Delivered,https://example.invalid/list\n")
    r = client.post("/rates/updates/import", data={"source_name": "Test list", "source_type": "Manual dataset", "dry_run": "1"},
                    files={"file": ("list.csv", io.BytesIO(csv.encode()), "text/csv")}, follow_redirects=False)
    assert "DRY+RUN" in r.headers["location"] or "DRY%20RUN" in r.headers["location"]
    assert db.scalar("SELECT COUNT(*) FROM rate_candidates") == 0
    r = client.post("/rates/updates/import", data={"source_name": "Test list", "source_type": "Manual dataset"},
                    files={"file": ("list.csv", io.BytesIO(csv.encode()), "text/csv")}, follow_redirects=False)
    assert "ok=" in r.headers["location"] and db.scalar("SELECT COUNT(*) FROM rate_candidates") == 1
    ref = db.scalar("SELECT candidate_ref FROM rate_candidates")
    page = client.get("/rates/updates").text
    assert ref in page and "Test list" in page and "kapsarc-gastat-cci" in page and "manual-only" in page
    d = client.get(f"/rates/updates/{ref}").text
    assert "310.50" in d and "https://example.invalid/list" in d and "Original price (immutable)" in d
    # the estimator cannot approve; nothing reaches the library
    r = client.post("/ui/do/review_rate_candidate", data={"candidate": ref, "decision": "approve", "_next": "/rates/updates"}, follow_redirects=False)
    assert "PERMISSION_DENIED" in r.headers["location"]
    _login(client, "view")
    r = client.post("/ui/do/review_rate_candidate", data={"candidate": ref, "decision": "approve", "_next": "/rates/updates"}, follow_redirects=False)
    assert "PERMISSION_DENIED" in r.headers["location"]
    _login(client, "proc")
    assert ref in client.get("/approvals").text                                               # appears in the human approval queue
    r = client.post("/ui/do/review_rate_candidate", data={"candidate": ref, "decision": "approve", "comment": "checked", "_next": "/rates/updates"}, follow_redirects=False)
    assert "ok=" in r.headers["location"] and db.scalar("SELECT COUNT(*) FROM resource_rates WHERE unit_price IS NOT NULL") == 0
    _login(client, "est")
    r = client.post("/ui/do/publish_rate_candidate", data={"candidate": ref, "_next": "/rates/updates"}, follow_redirects=False)
    assert "ok=" in r.headers["location"]
    assert db.scalar("SELECT status FROM resource_rates WHERE resource_id=? AND unit_price IS NOT NULL", (rid,)) == "Pending Review"
    r = client.post("/ui/do/approve_rate", data={"rate_id": db.scalar("SELECT id FROM resource_rates WHERE resource_id=? AND unit_price IS NOT NULL", (rid,)), "_next": "/approvals"},
                    follow_redirects=False)
    assert "PERMISSION_DENIED" in r.headers["location"]                                        # publishing does not approve; estimator cannot
    # dry-run source refresh from the UI needs no network
    _login(client, "proc")
    r = client.post("/ui/do/refresh_sources", data={"_next": "/rates/updates"}, follow_redirects=False)
    assert "DRY+RUN" in r.headers["location"] or "DRY%20RUN" in r.headers["location"]
    # official index file
    cci = Path(__import__("app.config", fromlist=["x"]).BASE_DIR) / "data/public_data/gastat_cci/kapsarc_cci_2026-04.records.json"
    r = client.post("/rates/updates/index", data={"dataset": "gastat-cci", "source_id": "SRC-002", "dry_run": ""}, files={"file": (cci.name, cci.read_bytes(), "application/json")},
                    follow_redirects=False)
    assert "ok=" in r.headers["location"] and db.scalar("SELECT COUNT(*) FROM index_observations") == 39
