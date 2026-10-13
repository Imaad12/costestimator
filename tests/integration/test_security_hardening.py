"""GOV-12 hardening: same-origin check for cookie-authenticated writes, security headers, sign-in lockout and unlock, TLS refusal on open networks."""
from __future__ import annotations

import subprocess
import sys
import time

import pytest

import app.config as cfg
from app.core.errors import AccountLocked, AuthRequired, PermissionDenied
from app.database import get_db
from app.services import auth
from tests.integration.test_api_ui import client, login  # noqa: F401


def test_cookie_authenticated_write_needs_same_origin(client):
    client.cookies.clear()
    r = client.post("/login", data={"username": "est", "password": "pw-est"}, follow_redirects=False)          # no cookie yet: sign-in itself is allowed
    assert r.status_code == 303 and "ksa_token" in r.headers.get("set-cookie", "")
    hdr = client.headers.pop("Origin")                                                                          # a request with the session cookie but no Origin/Referer
    try:
        bad = client.post("/ui/do/create_project", data={"name": "Forged", "_next": "/projects"}, follow_redirects=False)
        assert bad.status_code == 403 and bad.json()["error"] == "CSRF_BLOCKED"
        cross = client.post("/ui/do/create_project", data={"name": "Forged", "_next": "/projects"}, headers={"Origin": "https://evil.example"}, follow_redirects=False)
        assert cross.status_code == 403
        ref = client.post("/ui/do/create_project", data={"name": "Via referer", "_next": "/projects"}, headers={"Referer": "http://testserver/projects"}, follow_redirects=False)
        assert ref.status_code == 303 and "ok=" in ref.headers["location"]
        same = client.post("/ui/do/create_project", data={"name": "Same origin", "_next": "/projects"}, headers={"Origin": "http://testserver"}, follow_redirects=False)
        assert same.status_code == 303
    finally:
        client.headers["Origin"] = hdr
    tok = login(client, "est")
    client.cookies.clear()
    client.headers.pop("Origin")                                                                                                          # a script with a Bearer token and no Origin
    api = client.post("/api/actions/create_project", json={"name": "Bearer client"}, headers=tok)       # token clients are not subject to the origin check
    client.headers["Origin"] = hdr
    assert api.status_code == 200
    client.cookies.clear()
    assert get_db().all("SELECT name FROM projects WHERE name='Forged'") == []
    assert client.get("/api/projects", headers=tok).status_code == 200                                                                  # reads are never blocked


def test_security_headers_present_and_pages_not_cached(client):
    r = client.get("/login")
    h = {k.lower(): v for k, v in r.headers.items()}
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY" and h["referrer-policy"] == "same-origin"
    assert "frame-ancestors 'none'" in h["content-security-policy"] and "script-src 'self'" in h["content-security-policy"] and h["cache-control"] == "no-store"
    assert "strict-transport-security" not in h                                                                 # plain HTTP: no HSTS
    assert "strict-transport-security" in {k.lower() for k in client.get("/login", headers={"X-Forwarded-Proto": "https"}).headers}
    assert "cache-control" not in {k.lower() for k in client.get("/static/app.css").headers} or client.get("/static/app.css").headers["cache-control"] != "no-store"
    assert "onsubmit" not in client.get("/rates/updates", headers=login(client, "est")).text                    # no inline event handlers (CSP forbids inline scripts)


def test_lockout_after_repeated_failures_even_for_unknown_names_and_admin_unlock(client):
    db = get_db()
    s = cfg.get_settings()
    s.login_max_failures, s.login_lock_minutes = 3, 15
    for _ in range(3):
        with pytest.raises(AuthRequired):
            auth.authenticate(db, "est", "wrong")
    with pytest.raises(AccountLocked) as e:
        auth.authenticate(db, "est", "pw-est")                                                                  # correct password is refused while locked
    assert e.value.status_code == 429 and "administrator" in e.value.message
    auth.authenticate(db, "proc", "pw-proc")                                                                    # other accounts unaffected
    for _ in range(3):
        with pytest.raises(AuthRequired):
            auth.authenticate(db, "nobody", "x")
    with pytest.raises(AccountLocked):
        auth.authenticate(db, "nobody", "x")                                                                    # unknown names throttle too: no user enumeration
    assert db.one("SELECT 1 FROM audit_log WHERE action='lockout' AND entity_id='est'")
    r = client.post("/api/auth/login", json={"username": "est", "password": "pw-est"})
    assert r.status_code == 429
    with pytest.raises(PermissionDenied):
        auth.unlock_user(db, auth.get_actor(db, "est"), "est")
    assert auth.unlock_user(db, auth.get_actor(db, "admin"), "est") == 3
    assert auth.authenticate(db, "est", "pw-est").username == "est"
    # the window expires on its own
    for _ in range(3):
        with pytest.raises(AuthRequired):
            auth.authenticate(db, "view", "wrong")
    db.execute("UPDATE login_attempts SET ts=ts-? WHERE username='view'", (16 * 60,))
    assert auth.authenticate(db, "view", "pw-view").username == "view"


def test_cli_refuses_open_network_without_tls():
    r = subprocess.run([sys.executable, "-m", "app.cli", "run", "--host", "0.0.0.0", "--port", "8123"], capture_output=True, text=True, timeout=60, cwd=str(cfg.BASE_DIR))
    assert r.returncode == 2 and "without TLS" in r.stderr
    r2 = subprocess.run([sys.executable, "-m", "app.cli", "run", "--ssl-certfile", "x.pem"], capture_output=True, text=True, timeout=60, cwd=str(cfg.BASE_DIR))
    assert r2.returncode == 2 and "together" in r2.stderr
