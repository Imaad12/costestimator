"""Approvals inbox, Rates workbook (template, check, import) and the Settings hub (users, audit, integrity, standards, documents). SYNTHETIC data."""
from __future__ import annotations

import re
from pathlib import Path

import openpyxl

from app.database import get_db
from app.models.actor import Actor
from app.services import auth, rates
from tests.integration.test_api_ui import client  # noqa: F401  (shared fixture)
from tests.integration.test_web_tender_pages import _login

PROC = Actor("proc", "Procurement Reviewer", "proc")


def _pending_rate(db):
    rid = rates.create_resource(db, PROC, resource_type="material", description="Inbox test grout (SYNTHETIC)", unit="kg", cost_code="C.07")
    r = rates.propose_rate(db, PROC, rid, unit_price="12.50", rate_type="Synthetic Demonstration Rate", price_date="2026-10-01", is_synthetic=True, evidence="SYNTHETIC test")
    rates.submit_rate(db, PROC, r)
    return rid, r


def test_inbox_shows_buttons_only_to_roles_that_may_decide_and_never_on_own_work(client):
    db = get_db()
    rid, r = _pending_rate(db)
    _login(client, "proc")
    own = client.get("/approvals").text
    assert "You raised this" in own and 'action="/ui/do/approve_rate"' not in own          # four-eyes: the author sees no approve button
    _login(client, "view")
    v = client.get("/approvals").text
    assert 'action="/ui/do/approve_rate"' not in v and "cannot decide this" in v
    _login(client, "com")
    page = client.get("/approvals").text
    assert 'action="/ui/do/approve_rate"' in page and f'name="rate_id" value="{r}"' in page and 'action="/ui/do/reject_rate"' in page
    assert client.get("/approvals?group=rates").status_code == 200
    ok = client.post("/ui/do/approve_rate", data={"rate_id": r, "comments": "checked", "_next": "/approvals"}, follow_redirects=False)
    assert "ok=" in ok.headers["location"], ok.headers["location"]
    assert db.scalar("SELECT status FROM resource_rates WHERE id=?", (r,)) == "Approved"
    assert 'action="/ui/do/approve_rate"' not in client.get("/approvals").text
    assert "approve" in client.get("/approvals?log=1").text.lower()


def test_rates_workbook_template_check_and_import(client):
    db = get_db()
    rid = rates.create_resource(db, PROC, resource_type="material", description="Workbook test cement (SYNTHETIC)", unit="kg", cost_code="C.07")
    n_rates = db.scalar("SELECT COUNT(*) FROM resource_rates")
    _login(client, "proc")
    assert "Rates workbook" in client.get("/rates/workbook").text
    t = client.get("/rates/workbook/template.xlsx")
    assert t.status_code == 200 and t.headers["content-type"].startswith("application/vnd.openxmlformats")
    import io
    wb = openpyxl.load_workbook(io.BytesIO(t.content))
    assert "Rate Dataset" in wb.sheetnames and "Resource List" in wb.sheetnames
    assert any(row[0].value == rid for row in wb["Resource List"].iter_rows(min_row=2))
    ws = wb["Rate Dataset"]
    hdr = {str(c.value): c.column for c in ws[5] if c.value}
    for col, v in (("Resource ID", rid), ("Unit", "kg"), ("Unit price", 9.75), ("Currency", "SAR"), ("Price date", "2026-10-01"), ("Evidence / reference", "SYNTHETIC test quote")):
        ws.cell(row=6, column=hdr[col], value=v)
    ws.cell(row=7, column=hdr["Resource ID"], value="NO-SUCH-RES"); ws.cell(row=7, column=hdr["Unit price"], value=5); ws.cell(row=7, column=hdr["Currency"], value="SAR")
    buf = io.BytesIO(); wb.save(buf)
    files = {"file": ("filled.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    no_src = client.post("/rates/workbook/preview", files=files, data={"source_type": "Quotation"}, follow_redirects=False)
    assert "err=" in no_src.headers["location"]                                          # a source is mandatory
    pv = client.post("/rates/workbook/preview", files=files, data={"source_name": "SYNTHETIC supplier list", "source_type": "Quotation"})
    assert pv.status_code == 200 and "Rejected rows" in pv.text and "does not exist" in pv.text
    assert db.scalar("SELECT COUNT(*) FROM rate_candidates") == 0                       # preview stores nothing
    stored = re.search(r'name="stored" value="([^"]+)"', pv.text).group(1)
    imp = client.post("/rates/workbook/import", data={"stored": stored, "source_name": "SYNTHETIC supplier list", "source_type": "Quotation"}, follow_redirects=False)
    assert "ok=" in imp.headers["location"] and "group=candidates" in imp.headers["location"], imp.headers["location"]
    row = db.one("SELECT status, original_price, source_name FROM rate_candidates")
    assert row["status"] == "Pending Review" and str(row["original_price"]) in ("9.75", "9.750000") and row["source_name"] == "SYNTHETIC supplier list"
    assert db.scalar("SELECT COUNT(*) FROM resource_rates") == n_rates                        # an import never creates a rate
    again = client.post("/rates/workbook/import", data={"stored": stored, "source_name": "SYNTHETIC supplier list", "source_type": "Quotation"}, follow_redirects=False)
    assert "err=" in again.headers["location"]                                          # the identical file is refused
    _login(client, "com")
    assert "review_rate_candidate" in client.get("/approvals?group=candidates").text


def test_settings_hub_tabs_render_and_user_admin_rules(client):
    _login(client, "admin")
    for tab in ("general", "users", "audit", "integrity", "standards", "documents", "sources", "reference"):
        r = client.get(f"/settings?tab={tab}")
        assert r.status_code == 200 and "Settings" in r.text, tab
    import html
    assert "Don't approve your own work" in html.unescape(client.get("/settings?tab=documents").text)
    assert "Recompute and compare" in client.get("/settings?tab=integrity").text and client.get("/settings?tab=integrity&verify=1").status_code == 200
    assert "Verify hash chain" in client.get("/settings?tab=audit").text and "Chain verified" in client.get("/settings?tab=audit&verify=1").text
    mk = client.post("/ui/do/create_user", data={"username": "newbie", "display_name": "New B", "role": "Estimator", "password": "longenough1", "_next": "/settings?tab=users"}, follow_redirects=False)
    assert "ok=" in mk.headers["location"]
    assert "newbie" in client.get("/settings?tab=users").text
    short = client.post("/ui/do/reset_user_password", data={"username": "newbie", "password": "short", "_next": "/settings?tab=users"}, follow_redirects=False)
    assert "err=" in short.headers["location"]
    ok = client.post("/ui/do/reset_user_password", data={"username": "newbie", "password": "another-long-pw", "_next": "/settings?tab=users"}, follow_redirects=False)
    assert "ok=" in ok.headers["location"]
    client.cookies.clear()
    assert client.post("/login", data={"username": "newbie", "password": "another-long-pw"}, follow_redirects=False).status_code == 303
    assert client.post("/login", data={"username": "newbie", "password": "longenough1"}, follow_redirects=False).status_code != 303      # old password no longer works
    _login(client, "admin")
    me = client.post("/ui/do/set_user_active", data={"username": "admin", "active": "0", "_next": "/settings?tab=users"}, follow_redirects=False)
    assert "err=" in me.headers["location"]                                                                                              # cannot lock yourself out
    demote = client.post("/ui/do/set_user_role", data={"username": "admin", "role": "Viewer", "_next": "/settings?tab=users"}, follow_redirects=False)
    assert "LAST_ADMIN" in demote.headers["location"]
    off = client.post("/ui/do/set_user_active", data={"username": "newbie", "active": "0", "_next": "/settings?tab=users"}, follow_redirects=False)
    assert "ok=" in off.headers["location"]
    client.cookies.clear()
    assert client.post("/login", data={"username": "newbie", "password": "another-long-pw"}, follow_redirects=False).status_code != 303   # deactivated
    assert get_db().one("SELECT 1 FROM audit_log WHERE entity_type='user' AND entity_id='newbie' AND action='password_reset'")
    _login(client, "est")
    deny = client.post("/ui/do/set_user_role", data={"username": "view", "role": "Administrator", "_next": "/settings?tab=users"}, follow_redirects=False)
    assert "err=" in deny.headers["location"]
    assert "/ui/do/reset_user_password" not in client.get("/settings?tab=users").text                                    # no management controls for non-admins


def test_integrity_tab_detects_a_tampered_evidence_file(client, tmp_path, monkeypatch):
    import app.web.routes_ops as ops
    ev = tmp_path / "ev"; ev.mkdir()
    (ev / "a.pdf").write_bytes(b"original")
    import hashlib, json
    (ev / "evidence_manifest.json").write_text(json.dumps({"files": [{"file": "a.pdf", "sha256": hashlib.sha256(b"original").hexdigest(), "register_row": "STD-X"}]}))
    monkeypatch.setattr(ops, "ROOT", tmp_path / "root")
    (tmp_path / "root" / "data" / "standards").mkdir(parents=True); (tmp_path / "root" / "data" / "standards" / "evidence").symlink_to(ev)
    _login(client, "admin")
    assert "MATCH" in client.get("/settings?tab=integrity&verify=1").text
    (ev / "a.pdf").write_bytes(b"tampered")
    assert "MISMATCH" in client.get("/settings?tab=integrity&verify=1").text


def test_placeholders_are_capitalised_in_templates():
    bad = []
    for f in Path("app/web/templates").glob("*.html"):
        for m in re.finditer(r'placeholder="([a-z][^"]{0,30})', f.read_text(encoding="utf-8")):
            bad.append((f.name, m.group(1)))
    assert not bad, bad[:5]
