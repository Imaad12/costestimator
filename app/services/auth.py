"""Local users, password hashing, and signed session tokens (HMAC). Single-user / small-team MVP only."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from ..config import get_settings
from ..core.errors import AuthRequired, ValidationFailed
from ..core.timeutil import now_iso
from ..database import Database
from ..models.actor import Actor
from ..models.enums import ROLE_VALUES, Role
from . import audit

_ITER = 240_000


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITER)
    return f"pbkdf2${_ITER}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, it, salt_b64, dk_b64 = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), base64.b64decode(salt_b64), int(it))
        return hmac.compare_digest(dk, base64.b64decode(dk_b64))
    except Exception:
        return False


def create_user(db: Database, username: str, display_name: str, role: str, password: str | None,
                *, creator: Actor | str = "system", is_ai: bool = False) -> int:
    if role not in ROLE_VALUES:
        raise ValidationFailed(f"Unknown role '{role}'. Valid: {ROLE_VALUES}")
    if is_ai or role == Role.AI.value:
        is_ai, role, password = True, Role.AI.value, None  # AI principals never get a password / login
    uid = db.insert("users", dict(username=username, display_name=display_name, role=role,
                                  password_hash=hash_password(password) if password else None,
                                  is_active=1, is_ai=int(is_ai), created_at=now_iso()))
    audit.log(db, creator, "user", username, "create", after={"role": role, "is_ai": is_ai})
    return uid


def authenticate(db: Database, username: str, password: str) -> Actor:
    r = db.one("SELECT * FROM users WHERE username=? AND is_active=1", (username,))
    if not r or r["is_ai"] or not verify_password(password, r["password_hash"]):
        raise AuthRequired("Invalid username or password.")
    return Actor(r["username"], r["role"], r["display_name"], False)


def get_actor(db: Database, username: str) -> Actor:
    r = db.one("SELECT * FROM users WHERE username=? AND is_active=1", (username,))
    if not r:
        raise AuthRequired("Unknown or inactive user.")
    return Actor(r["username"], r["role"], r["display_name"], bool(r["is_ai"]))


def make_token(username: str, ttl_hours: int | None = None) -> str:
    s = get_settings()
    exp = int(time.time() + 3600 * (ttl_hours or s.token_ttl_hours))
    payload = base64.urlsafe_b64encode(json.dumps({"u": username, "exp": exp}).encode()).decode().rstrip("=")
    sig = hmac.new(s.get_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def read_token(token: str) -> str:
    try:
        payload, sig = token.rsplit(".", 1)
        expect = hmac.new(get_settings().get_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expect):
            raise ValueError
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if data["exp"] < time.time():
            raise ValueError
        return data["u"]
    except Exception:
        raise AuthRequired("Session expired or invalid. Please sign in again.")
