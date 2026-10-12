"""Hash-chained audit trail.

This is tamper-EVIDENT only: each row hashes its content plus the previous row's hash, so accidental or naive
edits are detectable via `verify_chain`. Anyone with write access to the SQLite file can rebuild the chain, so
this is NOT a tamper-proof or enterprise-grade audit log.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from ..core.timeutil import now_iso
from ..database import Database
from ..models.actor import Actor


def _canon(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _hash(prev: str, ts, actor, role, project_id, etype, eid, action, before, after, comment) -> str:
    payload = json.dumps([prev, ts, actor, role, project_id, etype, eid, action, before, after, comment],
                         ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def log(db: Database, actor: Actor | str, entity_type: str, entity_id: Any, action: str, *,
        before: Any = None, after: Any = None, comment: str | None = None, project_id: str | None = None) -> int:
    actor_name = actor if isinstance(actor, str) else actor.username
    actor_role = None if isinstance(actor, str) else actor.role
    ts = now_iso()
    last = db.one("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1")
    prev = last["hash"] if last else ""
    b, a = _canon(before), _canon(after)
    eid = str(entity_id)
    h = _hash(prev, ts, actor_name, actor_role, project_id, entity_type, eid, action, b, a, comment)
    return db.insert("audit_log", dict(ts=ts, actor=actor_name, actor_role=actor_role, project_id=project_id,
                                       entity_type=entity_type, entity_id=eid, action=action, before_json=b,
                                       after_json=a, comment=comment, prev_hash=prev, hash=h))


def verify_chain(db: Database) -> dict:
    prev = ""
    count = 0
    for r in db.all("SELECT * FROM audit_log ORDER BY id"):
        expect = _hash(prev, r["ts"], r["actor"], r["actor_role"], r["project_id"], r["entity_type"], r["entity_id"],
                       r["action"], r["before_json"], r["after_json"], r["comment"])
        if r["prev_hash"] != prev or r["hash"] != expect:
            return {"ok": False, "first_bad_id": r["id"], "checked": count}
        prev = r["hash"]
        count += 1
    return {"ok": True, "checked": count}


def history(db: Database, entity_type: str, entity_id: Any) -> list[dict]:
    return [dict(r) for r in db.all(
        "SELECT * FROM audit_log WHERE entity_type=? AND entity_id=? ORDER BY id", (entity_type, str(entity_id)))]
