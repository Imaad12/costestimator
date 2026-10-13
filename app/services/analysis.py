"""Stored analysis outputs (loading histograms, simulations, cash-flow forecasts ...). Immutable, never an approved record: each run keeps its
parameters and an input hash so that it can be re-run and compared. Nothing here changes an estimate."""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

from ..approvals import engine as approvals
from ..core.errors import NotFound
from ..core.timeutil import now_iso
from ..database import Database, rows_to_dicts
from ..models.actor import Actor
from . import audit


def jsonable(o: Any) -> Any:
    if isinstance(o, Decimal):
        return format(o, "f")
    if isinstance(o, dict):
        return {str(k) if not isinstance(k, tuple) else "|".join(map(str, k)): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [jsonable(v) for v in o]
    if hasattr(o, "isoformat"):
        return o.isoformat()
    if hasattr(o, "__dict__") and not isinstance(o, type):
        return jsonable(vars(o))
    return o


def digest(o: Any) -> str:
    return hashlib.sha256(json.dumps(jsonable(o), sort_keys=True, default=str).encode()).hexdigest()


def save_run(db: Database, actor: Actor, project_id: str, kind: str, params: dict, result: dict, *, inputs_hash: str | None = None, notes: str | None = None) -> int:
    approvals.require_author(actor)
    rid = db.insert("analysis_runs", dict(project_id=project_id, kind=kind, params_json=json.dumps(jsonable(params), sort_keys=True),
                                          inputs_hash=inputs_hash, result_json=json.dumps(jsonable(result), default=str), notes=notes,
                                          created_by=actor.username, created_at=now_iso()))
    audit.log(db, actor, "analysis_run", rid, "create", after={"kind": kind, "inputs_hash": (inputs_hash or "")[:12]}, project_id=project_id)
    return rid


def list_runs(db: Database, project_id: str, kind: str | None = None) -> list[dict]:
    q, a = "SELECT id, project_id, kind, params_json, inputs_hash, notes, created_by, created_at FROM analysis_runs WHERE project_id=?", [project_id]
    if kind:
        q += " AND kind=?"; a.append(kind)
    return rows_to_dicts(db.all(q + " ORDER BY id DESC", tuple(a)))


def get_run(db: Database, run_id: int) -> dict:
    r = db.one("SELECT * FROM analysis_runs WHERE id=?", (run_id,))
    if not r:
        raise NotFound(f"Analysis run {run_id} not found.")
    d = dict(r)
    d["result"] = json.loads(d["result_json"])
    d["params"] = json.loads(d["params_json"] or "{}")
    return d
