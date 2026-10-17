"""Local users, password hashing, and signed session tokens (HMAC). Single-user / small-team MVP only."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from ..config import get_settings
from ..core.errors import AccountLocked, AuthRequired, ValidationFailed
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
                *, creator: Actor | str = "system", is_ai: bool = False, actor_type: str = "human") -> int:
    if actor_type not in ("human", "test", "ai"):
        raise ValidationFailed("actor_type must be 'human' (a real accountable person) or 'test' (software-validation principal).")
    if role not in ROLE_VALUES:
        raise ValidationFailed(f"Unknown role '{role}'. Valid: {ROLE_VALUES}")
    if is_ai or role == Role.AI.value:
        is_ai, role, password, actor_type = True, Role.AI.value, None, "ai"  # AI principals never get a password / login
    uid = db.insert("users", dict(username=username, display_name=display_name, role=role,
                                  password_hash=hash_password(password) if password else None,
                                  is_active=1, is_ai=int(is_ai), actor_type=actor_type, created_at=now_iso()))
    audit.log(db, creator, "user", username, "create", after={"role": role, "is_ai": is_ai, "actor_type": actor_type})
    return uid


def _failures_in_window(db: Database, username: str, now: float) -> tuple[int, float | None]:
    """(failed attempts since the last success within the lock window, time of the latest failure)."""
    window = get_settings().login_lock_minutes * 60
    last_ok = db.one("SELECT MAX(ts) t FROM login_attempts WHERE username=? AND success=1", (username,))["t"] or 0
    since = max(now - window, last_ok)
    rows = db.all("SELECT ts FROM login_attempts WHERE username=? AND success=0 AND ts>? ORDER BY ts", (username, since))
    return len(rows), (rows[-1]["ts"] if rows else None)


def authenticate(db: Database, username: str, password: str, client: str | None = None) -> Actor:
    """Verify credentials. After `login_max_failures` consecutive failures the name is locked for `login_lock_minutes` (even for unknown names, so existence is not
    revealed); a correct password during the lock is refused too. An administrator can unlock with `unlock_user`."""
    s = get_settings()
    now = time.time()
    n, last = _failures_in_window(db, username, now)
    if s.login_max_failures > 0 and n >= s.login_max_failures:
        wait = int((last + s.login_lock_minutes * 60 - now) / 60) + 1
        raise AccountLocked(f"Too many failed sign-in attempts. Try again in about {max(wait, 1)} minute(s), or ask an administrator to unlock the account.")
    r = db.one("SELECT * FROM users WHERE username=? AND is_active=1", (username,))
    ok = bool(r) and not r["is_ai"] and verify_password(password, r["password_hash"])
    db.insert("login_attempts", dict(username=username, ts=now, success=int(ok), client=client))
    if ok:
        db.execute("DELETE FROM login_attempts WHERE ts<?", (now - 30 * 86400,))              # keep a month of history only
    if not ok:
        if s.login_max_failures > 0 and n + 1 >= s.login_max_failures:
            audit.log(db, "system:auth", "user", username, "lockout", after={"failures": n + 1, "minutes": s.login_lock_minutes})
        raise AuthRequired("Invalid username or password.")
    return Actor(r["username"], r["role"], r["display_name"], False)


def unlock_user(db: Database, actor: Actor, username: str) -> int:
    from ..approvals import engine as approvals
    approvals.require_admin(actor, "unlocking an account")
    n = db.update("login_attempts", {"success": 1}, "username=? AND success=0", (username,))     # resolved failures no longer count
    audit.log(db, actor, "user", username, "unlock", after={"cleared": n})
    return n


def list_users(db: Database) -> list[dict]:
    rows = db.all("SELECT username, display_name, role, is_active, is_ai, actor_type, created_at FROM users ORDER BY is_active DESC, role, username")
    return [dict(r) for r in rows]


def _admin_count(db: Database) -> int:
    return int(db.scalar("SELECT COUNT(*) FROM users WHERE role=? AND is_active=1 AND is_ai=0", (Role.ADMIN.value,)) or 0)


def _human_user(db: Database, username: str):
    r = db.one("SELECT * FROM users WHERE username=?", (username,))
    if not r:
        raise ValidationFailed(f"Unknown user '{username}'.", code="USER_UNKNOWN")
    if r["is_ai"]:
        raise ValidationFailed("AI principals have no password and cannot be edited here.", code="USER_AI")
    return r


def reset_password(db: Database, actor: Actor, username: str, new_password: str) -> None:
    from ..approvals import engine as approvals
    approvals.require_admin(actor, "resetting a password")
    _human_user(db, username)
    if len(new_password or "") < 8:
        raise ValidationFailed("Password must be at least 8 characters.", code="PASSWORD_WEAK")
    db.update("users", {"password_hash": hash_password(new_password)}, "username=?", (username,))
    unlock_user(db, actor, username)
    audit.log(db, actor, "user", username, "password_reset")


def set_role(db: Database, actor: Actor, username: str, role: str) -> None:
    from ..approvals import engine as approvals
    approvals.require_admin(actor, "changing a role")
    r = _human_user(db, username)
    if role not in ROLE_VALUES or role == Role.AI.value:
        raise ValidationFailed(f"Unknown role '{role}'. Valid: {[x for x in ROLE_VALUES if x != Role.AI.value]}", code="ROLE_UNKNOWN")
    if r["role"] == Role.ADMIN.value and role != Role.ADMIN.value and r["is_active"] and _admin_count(db) <= 1:
        raise ValidationFailed("Cannot remove the last active Administrator.", code="LAST_ADMIN")
    db.update("users", {"role": role}, "username=?", (username,))
    audit.log(db, actor, "user", username, "set_role", before={"role": r["role"]}, after={"role": role})


def set_active(db: Database, actor: Actor, username: str, active: bool) -> None:
    from ..approvals import engine as approvals
    approvals.require_admin(actor, "activating or deactivating a user")
    r = _human_user(db, username)
    if not active and username == actor.username:
        raise ValidationFailed("You cannot deactivate your own account.", code="SELF_DEACTIVATE")
    if not active and r["role"] == Role.ADMIN.value and r["is_active"] and _admin_count(db) <= 1:
        raise ValidationFailed("Cannot deactivate the last active Administrator.", code="LAST_ADMIN")
    db.update("users", {"is_active": int(active)}, "username=?", (username,))
    audit.log(db, actor, "user", username, "activate" if active else "deactivate")


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
