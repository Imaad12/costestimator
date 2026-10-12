from __future__ import annotations

from fastapi import Request

from ..core.errors import AuthRequired
from ..database import Database, get_db
from ..models.actor import Actor
from ..services import auth

COOKIE = "ksa_token"


def database() -> Database:
    return get_db()


def token_from(request: Request) -> str | None:
    h = request.headers.get("authorization", "")
    if h.lower().startswith("bearer "):
        return h[7:].strip()
    return request.cookies.get(COOKIE)


def current_actor(request: Request) -> Actor:
    t = token_from(request)
    if not t:
        raise AuthRequired("Sign in required.")
    username = auth.read_token(t)
    actor = auth.get_actor(get_db(), username)
    if actor.is_ai:
        raise AuthRequired("AI principals cannot sign in.")
    return actor
