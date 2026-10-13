"""HTTP hardening for the local web app: same-origin check for cookie-authenticated state changes (CSRF), security headers, no-store caching of dynamic pages.

Bearer-token API clients are not affected by CSRF (the token is not an ambient credential) and skip the origin check. For a deployment beyond a single
trusted workstation also serve over TLS and put the app behind a reverse proxy; see docs/SECURITY.md for what is and is not provided."""
from __future__ import annotations

from urllib.parse import urlsplit

from .api.deps import COOKIE
from .config import get_settings

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; form-action 'self'; frame-ancestors 'none'; base-uri 'self'; "
       "object-src 'none'")


def _hdr(scope, name: bytes) -> str | None:
    for k, v in scope.get("headers", []):
        if k == name:
            return v.decode("latin-1")
    return None


def same_origin_ok(scope) -> tuple[bool, str]:
    host = _hdr(scope, b"host")
    origin = _hdr(scope, b"origin")
    if origin and origin != "null":
        return (urlsplit(origin).netloc == host, f"Origin {origin} does not match host {host}")
    ref = _hdr(scope, b"referer")
    if ref:
        return (urlsplit(ref).netloc == host, f"Referer {ref} does not match host {host}")
    return False, "missing Origin/Referer on a state-changing request"


class Hardening:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        s = get_settings()
        method = scope["method"]
        cookie_auth = _hdr(scope, b"authorization") is None and f"{COOKIE}=" in (_hdr(scope, b"cookie") or "")
        if s.csrf_origin_check and method in UNSAFE and cookie_auth:
            ok, why = same_origin_ok(scope)
            if not ok:
                body = (b'{"error":"CSRF_BLOCKED","message":"Cross-origin state-changing request refused (' + why.encode()[:200].replace(b'"', b"'") + b')."}')
                await send({"type": "http.response.start", "status": 403, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
                await send({"type": "http.response.body", "body": body})
                return
        if not s.security_headers:
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        https = s.tls or scope.get("scheme") == "https" or (_hdr(scope, b"x-forwarded-proto") or "").lower() == "https"

        async def send_wrapped(msg):
            if msg["type"] == "http.response.start":
                h = list(msg.get("headers", []))
                names = {k for k, _ in h}
                add = [(b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"DENY"), (b"referrer-policy", b"same-origin"),
                       (b"permissions-policy", b"geolocation=(), microphone=(), camera=()"), (b"content-security-policy", CSP.encode())]
                if not path.startswith("/static/"):
                    add.append((b"cache-control", b"no-store"))
                if https:
                    add.append((b"strict-transport-security", b"max-age=31536000"))
                for k, v in add:
                    if k not in names:
                        h.append((k, v))
                msg = {**msg, "headers": h}
            await send(msg)
        await self.app(scope, receive, send_wrapped)
