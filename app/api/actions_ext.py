"""Actions added in iteration 4 (governed parameters, WBS/CBS, programme, analyses, controls ...). Registered into the same registry as actions.py;
every action calls a service that enforces roles and approval rules on the server."""
from __future__ import annotations

import json
from typing import Any

from ..core.errors import ValidationFailed
from .actions import action, opt, req


def jdict(p: dict, key: str, required: bool = True) -> Any:
    """A dict/list given as a real object (REST) or JSON text (HTML form)."""
    raw = p.get(key)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        if required:
            raise ValidationFailed(f"'{key}' is required.", code="FIELD_REQUIRED")
        return None
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValidationFailed(f"'{key}' is not valid JSON: {e}", code="BAD_JSON")
    return raw


# ---------------------------------------------------------------- governed parameters
@action("propose_param")
def _(db, a, p):
    from ..services import governed
    return governed.propose(db, a, req(p, "kind")[0], req(p, "code")[0], jdict(p, "data"), project_id=opt(p, "project_id"), source=opt(p, "source"),
                            basis_note=opt(p, "basis_note"), is_synthetic=str(p.get("is_synthetic", "")).lower() in ("1", "true", "on", "yes"),
                            submit=str(p.get("submit", "")).lower() in ("1", "true", "on", "yes"))


@action("submit_param")
def _(db, a, p):
    from ..services import governed
    governed.submit(db, a, int(req(p, "param_id")[0]))


@action("approve_param")
def _(db, a, p):
    from ..services import governed
    governed.approve(db, a, int(req(p, "param_id")[0]), comments=opt(p, "comments"))


@action("reject_param")
def _(db, a, p):
    from ..services import governed
    governed.reject(db, a, int(req(p, "param_id")[0]), comments=req(p, "comments")[0])


# ---------------------------------------------------------------- WBS / cross-walk
@action("add_wbs_node")
def _(db, a, p):
    from ..services import wbs
    return wbs.add_node(db, a, req(p, "project_id")[0], req(p, "code")[0], req(p, "name")[0], opt(p, "parent_code"), opt(p, "kind") or "area")


@action("delete_wbs_node")
def _(db, a, p):
    from ..services import wbs
    wbs.delete_node(db, a, req(p, "project_id")[0], req(p, "code")[0])


@action("assign_wbs")
def _(db, a, p):
    """`mapping`: {item_key: wbs_code} (JSON), or single `item_key` + `wbs_code`."""
    from ..services import wbs
    pid = req(p, "project_id")[0]
    mapping = jdict(p, "mapping", required=False) or {req(p, "item_key")[0]: req(p, "wbs_code")[0]}
    return wbs.assign_items(db, a, pid, mapping)


@action("add_crosswalk")
def _(db, a, p):
    from ..services import wbs
    return wbs.add_crosswalk(db, a, req(p, "project_id")[0], req(p, "system")[0], req(p, "client_code")[0], req(p, "cost_code")[0], opt(p, "client_name"))


# ---------------------------------------------------------------- analysis runs
@action("save_analysis")
def _(db, a, p):
    """Run a registered report and store its result as an immutable analysis run (not an approved record)."""
    from ..reporting.registry import run_report
    from ..services import analysis
    pid, name = req(p, "project_id", "report")
    params = jdict(p, "params", required=False) or {}
    res = run_report(db, name, pid, params)
    return analysis.save_run(db, a, pid, name, params, res, inputs_hash=analysis.digest(res), notes=opt(p, "notes"))
