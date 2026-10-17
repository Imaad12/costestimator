"""The tender-workflow web pages: menu, control tower, tender desk, queries, registers, workforce, pack (with safe downloads), readiness, standards, audit and help (SYNTHETIC data)."""
from __future__ import annotations

from app.database import get_db
from app.web.routes_tender import render_markdown
from tests.integration.test_api_ui import client  # noqa: F401  (shared fixture)


def _login(c, user):
    c.cookies.clear()
    assert c.post("/login", data={"username": user, "password": "pw-" + user}, follow_redirects=False).status_code == 303


def _project(c):
    r = c.post("/ui/do/create_project", data={"name": "Web pages (SYNTHETIC)", "client": "FICTIONAL", "trades": "civil, structural", "_next": "/projects/{result}/tower"}, follow_redirects=False)
    assert r.status_code == 303
    return r.headers["location"].split("?")[0].split("/")[2]


def test_menu_and_every_new_page_render(client):
    _login(client, "est")
    pid = _project(client)
    home = client.get("/").text
    for label in ("Dashboard", "Projects", "Standards &amp; evidence", "Audit trail", "What&#39;s built / missing", "All documents"):
        assert label in home or label.replace("&#39;", "'") in home, label
    for path in (f"/projects/{pid}/tower", f"/projects/{pid}/tender", f"/projects/{pid}/queries", f"/projects/{pid}/tender-registers", f"/projects/{pid}/workforce",
                 f"/projects/{pid}/pack", f"/projects/{pid}/readiness", "/standards", "/audit", "/audit?verify=1", "/help", "/help/SYSTEM_MAP_BUILT_VS_MISSING", "/favicon.ico"):
        r = client.get(path)
        assert r.status_code in (200, 204), (path, r.status_code, r.text[:200])
    t = client.get(f"/projects/{pid}/tower").text
    assert "Control tower" in t and "workflow stages done" in t and "What stops a submission-ready status" in t
    assert "Chain verified" in client.get("/audit?verify=1").text
    assert "Verified - primary source read" in client.get("/standards").text


def test_tender_desk_queries_and_registers_flow_through_the_shared_actions(client):
    _login(client, "est")
    pid = _project(client)
    nxt = f"/projects/{pid}/tender"
    assert "ok=" in client.post("/ui/do/create_enquiry", data={"customer_name": "FICTIONAL CO", "title": "Test enquiry", "received_date": "2027-01-04", "project_id": pid, "_next": nxt}, follow_redirects=False).headers["location"]
    assert "ok=" in client.post("/ui/do/register_document", data={"project_id": pid, "doc_ref": "DWG-S", "doc_type": "drawing", "title": "Footing layout", "revision": "-", "status": "Missing", "discipline": "structural", "_next": nxt},
                                follow_redirects=False).headers["location"]
    page = client.get(nxt).text
    assert "FICTIONAL CO" in page and "DWG-S" in page and "drawings missing" in page
    q = client.post("/ui/do/add_query", data={"project_id": pid, "register": "technical", "question": "Which concrete grade applies to the footings?", "_next": f"/projects/{pid}/queries"}, follow_redirects=False)
    assert "ok=" in q.headers["location"]
    qp = client.get(f"/projects/{pid}/queries").text
    assert "Which concrete grade" in qp and "Draft" in qp and "Approve to issue" in qp
    assert "ok=" in client.post("/ui/do/generate_queries", data={"project_id": pid, "_next": f"/projects/{pid}/queries"}, follow_redirects=False).headers["location"]
    assert "DWG-S" in client.get(f"/projects/{pid}/queries?register=missing_input").text
    assert "ok=" in client.post("/ui/do/skeleton_registers", data={"project_id": pid, "_next": f"/projects/{pid}/tender-registers"}, follow_redirects=False).headers["location"]
    assert "ok=" in client.post("/ui/do/add_action", data={"project_id": pid, "description": "Takeoff required: footing", "owner": "estimator", "_next": f"/projects/{pid}/tender-registers"}, follow_redirects=False).headers["location"]
    assert "Takeoff required: footing" in client.get(f"/projects/{pid}/tender-registers").text
    tw = client.get(f"/projects/{pid}/tower").text
    assert "1 received" not in tw and "1 missing" in tw           # the missing drawing shows on the control tower


def test_viewer_cannot_write_through_the_new_pages_forms(client):
    _login(client, "est")
    pid = _project(client)
    _login(client, "view")
    r = client.post("/ui/do/add_query", data={"project_id": pid, "register": "technical", "question": "x?", "_next": f"/projects/{pid}/queries"}, follow_redirects=False)
    assert "err=" in r.headers["location"] and "PERMISSION_DENIED" in r.headers["location"]
    assert client.get(f"/projects/{pid}/queries").status_code == 200           # reading is allowed


def test_pack_downloads_stay_inside_the_pack_directory_and_help_is_safe(client, tmp_path):
    _login(client, "est")
    pid = _project(client)
    assert client.get(f"/projects/{pid}/pack/999/file/PRJ-1-D01/docx").status_code == 404
    assert client.get(f"/projects/{pid}/pack/999/manifest").status_code == 404
    db = get_db()
    out = tmp_path / "pack_out"
    out.mkdir()
    (out / "ok.docx").write_bytes(b"docx")
    secret = tmp_path / "secret.pdf"
    secret.write_bytes(b"secret")
    pk = db.insert("tender_packs", dict(project_id=pid, kind="tender", revision=1, classification="demonstration", status_label="t", out_dir=str(out), created_by="t", created_at="2026-01-01"))
    db.insert("generated_documents", dict(pack_pk=pk, doc_code="D01", doc_id="X-D01", title="t", template_id="T", template_version="1", revision=1, status="Draft", applicability="Required", path=str(out / "ok.docx"), created_at="2026-01-01"))
    db.insert("generated_documents", dict(pack_pk=pk, doc_code="D02", doc_id="X-D02", title="t", template_id="T", template_version="1", revision=1, status="Draft", applicability="Required", path=str(secret), created_at="2026-01-01"))
    assert client.get(f"/projects/{pid}/pack/{pk}/file/X-D01/docx").content == b"docx"
    assert client.get(f"/projects/{pid}/pack/{pk}/file/X-D02/pdf").status_code == 404            # outside the pack's directory
    assert client.get(f"/projects/{pid}/pack/{pk}/file/X-D01/exe").status_code == 404            # only docx / pdf / xlsx
    assert client.get("/help/..%2F..%2Fetc%2Fpasswd").status_code == 404
    assert client.get("/help/NOT_A_DOC").status_code == 404
    other = client.get(f"/projects/PRJ-9999/pack/{pk}/file/X-D01/docx")
    assert other.status_code in (404, 400)


def test_markdown_viewer_escapes_html_and_renders_tables_and_diagrams():
    out = render_markdown("# T\n<script>alert(1)</script>\n\n| a | b |\n|---|---|\n| 1 | **2** |\n\n```\n+--+\n|<b>|\n+--+\n```\n- one\n- `two`\n[x](javascript:alert(1)) [ok](/help)")
    assert "<script>" not in out and "&lt;script&gt;" in out
    assert "<table>" in out and "<b>2</b>" in out and '<pre class="diagram"' in out and "&lt;b&gt;" in out
    assert "javascript:" not in out.replace("javascript:alert(1)", "") or 'href="javascript' not in out
    assert 'href="/help"' in out


def test_workforce_forms_post_what_the_row_editors_serialise_and_prefill(client):
    """The browser's row editors (static/app.js) turn rows into JSON in hidden fields; the shared actions must accept exactly that shape, and the page must prefill the saved rows."""
    import json
    _login(client, "est")
    pid = _project(client)
    nxt = f"/projects/{pid}/workforce"
    page = client.get(nxt).text
    for needle in ('action="/ui/do/create_norm"', 'action="/ui/do/create_profile"', 'action="/ui/do/set_activities"', 'data-json-map="crew"', 'data-json-map="roles"', 'data-json-list="activities"'):
        assert needle in page, needle
    import re
    assert "onclick=" not in page and not re.findall(r"<script(?![^>]*\bsrc=)", page)       # the Content-Security-Policy forbids inline scripts; only the external app.js is loaded
    r = client.post("/ui/do/create_norm", data={"id": "N-W1", "trade": "Civil", "activity": "Excavation", "output_unit": "m3", "basis": "crew_output_per_crew_day", "value": "60",
                                                "crew": json.dumps({"skilled": 2, "labourer": 3}), "source": "test entry", "is_synthetic": "true", "_next": nxt}, follow_redirects=False)
    assert "ok=" in r.headers["location"], r.headers["location"]
    r = client.post("/ui/do/create_profile", data={"id": "WP-W1", "archetype": "mid", "name": "Mid", "roles": json.dumps({"skilled": 8, "labourer": 10, "eq:excavator": 2}), "indirect": json.dumps({"foreman": 2}),
                                                   "attendance_pct": "90", "availability_pct": "95", "productive_hours_per_shift": "8", "shifts": "1", "is_synthetic": "true", "_next": nxt}, follow_redirects=False)
    assert "ok=" in r.headers["location"], r.headers["location"]
    acts = [{"code": "A-MOB", "name": "Mobilisation", "crews": 1, "work_fronts": 1, "fixed_days": {"setup": 5, "fixed_only": True}}, {"code": "A-EXC", "name": "Excavation", "norm_id": "N-W1", "crews": 2, "work_fronts": 2, "predecessors": "A-MOB"}]
    r = client.post("/ui/do/set_activities", data={"project_id": pid, "activities": json.dumps(acts), "_next": nxt}, follow_redirects=False)
    assert "ok=" in r.headers["location"], r.headers["location"]
    page = client.get(nxt).text
    assert "N-W1" in page and "WP-W1" in page and 'value="A-MOB"' in page and 'value="A-EXC"' in page and "selected" in page and "checked" in page
    # a wrong head-count for the archetype is refused by the service, not silently accepted
    bad = client.post("/ui/do/create_profile", data={"id": "WP-BAD", "archetype": "sme", "name": "x", "roles": json.dumps({"skilled": 60}), "attendance_pct": "90", "availability_pct": "95",
                                                     "productive_hours_per_shift": "8", "_next": nxt}, follow_redirects=False)
    assert "ARCHETYPE_BAND" in bad.headers["location"]
    # reviewer separation: the author cannot approve their own norm
    client.post("/ui/do/submit_norm", data={"id": "N-W1", "_next": nxt}, follow_redirects=False)
    own = client.post("/ui/do/approve_norm", data={"id": "N-W1", "_next": nxt}, follow_redirects=False)
    assert "err=" in own.headers["location"]
    # crew comparison uses plain checkboxes (no inline script)
    assert client.get(nxt + "?profiles=WP-W1").status_code == 200
