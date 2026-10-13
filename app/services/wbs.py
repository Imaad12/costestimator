"""Work breakdown structure (area / unit / system / phase) kept separate from the cost-code tree (CBS), plus a cross-walk to a client's coding system
and roll-up reports. Structure only: nothing here changes a price. Quantities are never touched."""
from __future__ import annotations

import csv
import re
from decimal import Decimal
from pathlib import Path

from ..approvals import engine as approvals
from ..core.errors import Conflict, NotFound, ValidationFailed
from ..core.money import to_text
from ..core.timeutil import now_iso
from ..database import Database, rows_to_dicts
from ..estimators import rollup
from ..models.actor import Actor
from . import audit, projects

_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-/]{0,39}$")
KINDS = ("area", "unit", "system", "phase", "package", "other")


def add_node(db: Database, actor: Actor, project_id: str, code: str, name: str, parent_code: str | None = None, kind: str = "area") -> int:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    code, name = (code or "").strip(), (name or "").strip()
    if not _CODE.match(code):
        raise ValidationFailed("WBS code: letters/digits/._-/ only, up to 40 characters.", code="BAD_WBS_CODE")
    if not name:
        raise ValidationFailed("WBS node name is required.")
    if kind not in KINDS:
        raise ValidationFailed(f"kind must be one of {KINDS}")
    if db.one("SELECT 1 FROM wbs_nodes WHERE project_id=? AND code=?", (project_id, code)):
        raise Conflict(f"WBS code {code} already exists.", code="WBS_EXISTS")
    if parent_code and not db.one("SELECT 1 FROM wbs_nodes WHERE project_id=? AND code=?", (project_id, parent_code)):
        raise ValidationFailed(f"Parent WBS {parent_code} not found (create parents first).", code="WBS_PARENT")
    nid = db.insert("wbs_nodes", dict(project_id=project_id, code=code, parent_code=parent_code or None, name=name, kind=kind,
                                      created_by=actor.username, created_at=now_iso()))
    audit.log(db, actor, "wbs_node", f"{project_id}/{code}", "create", after={"name": name, "parent": parent_code}, project_id=project_id)
    return nid


def delete_node(db: Database, actor: Actor, project_id: str, code: str) -> None:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    if db.one("SELECT 1 FROM wbs_nodes WHERE project_id=? AND parent_code=?", (project_id, code)):
        raise Conflict("WBS node has children; remove them first.", code="WBS_HAS_CHILDREN")
    if db.one("SELECT 1 FROM boq_wbs WHERE project_id=? AND wbs_code=?", (project_id, code)):
        raise Conflict("WBS node has BOQ items assigned; reassign them first.", code="WBS_IN_USE")
    if not db.one("SELECT 1 FROM wbs_nodes WHERE project_id=? AND code=?", (project_id, code)):
        raise NotFound(f"WBS {code} not found.")
    db.execute("DELETE FROM wbs_nodes WHERE project_id=? AND code=?", (project_id, code))
    audit.log(db, actor, "wbs_node", f"{project_id}/{code}", "delete", project_id=project_id)


def assign_items(db: Database, actor: Actor, project_id: str, mapping: dict[str, str]) -> dict:
    """item_key -> wbs_code. Unknown items/codes are refused individually and reported; an item has at most one WBS node."""
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    ok, errors = 0, []
    with db.tx():
        for ik, wc in mapping.items():
            if not db.one("SELECT 1 FROM boq_items WHERE project_id=? AND item_key=? AND item_type='item'", (project_id, ik)):
                errors.append(f"{ik}: BOQ item not found"); continue
            if not db.one("SELECT 1 FROM wbs_nodes WHERE project_id=? AND code=?", (project_id, wc)):
                errors.append(f"{ik}: WBS {wc} not found"); continue
            db.execute("INSERT INTO boq_wbs(project_id,item_key,wbs_code,assigned_by,assigned_at) VALUES (?,?,?,?,?) "
                       "ON CONFLICT(project_id,item_key) DO UPDATE SET wbs_code=excluded.wbs_code, assigned_by=excluded.assigned_by, assigned_at=excluded.assigned_at",
                       (project_id, ik, wc, actor.username, now_iso()))
            ok += 1
        audit.log(db, actor, "wbs_assignment", project_id, "assign", after={"assigned": ok, "errors": len(errors)}, project_id=project_id)
    return {"assigned": ok, "errors": errors}


def import_rows(db: Database, actor: Actor, project_id: str, nodes: list[dict] | None = None, assignments: list[dict] | None = None) -> dict:
    created = 0
    for r in sorted(nodes or [], key=lambda r: (str(r.get("parent_code") or "").count("."), str(r.get("code")))):
        if db.one("SELECT 1 FROM wbs_nodes WHERE project_id=? AND code=?", (project_id, str(r["code"]).strip())):
            continue
        add_node(db, actor, project_id, str(r["code"]), r.get("name") or r["code"], (r.get("parent_code") or None), r.get("kind") or "area")
        created += 1
    res = assign_items(db, actor, project_id, {str(r["item_key"]).strip(): str(r["wbs_code"]).strip() for r in (assignments or [])}) if assignments else {"assigned": 0, "errors": []}
    return {"nodes_created": created, **res}


def import_csv(db: Database, actor: Actor, project_id: str, path: Path) -> dict:
    """CSV with columns [code,parent_code,name,kind] (nodes) and/or [item_key,wbs_code] (assignments); a file may carry either set."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValidationFailed("Empty WBS file.")
    cols = set(rows[0])
    if {"item_key", "wbs_code"} <= cols:
        return import_rows(db, actor, project_id, assignments=rows)
    if "code" in cols:
        return import_rows(db, actor, project_id, nodes=rows)
    raise ValidationFailed("WBS file needs columns code[,parent_code,name,kind] or item_key,wbs_code.", code="WBS_FILE")


def add_crosswalk(db: Database, actor: Actor, project_id: str, system: str, client_code: str, cost_code: str, client_name: str | None = None) -> int:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    if not (system and client_code and cost_code):
        raise ValidationFailed("system, client_code and cost_code are required.")
    if not db.one("SELECT 1 FROM cost_codes WHERE code=? OR code LIKE ?", (cost_code, cost_code + "%")):
        raise ValidationFailed(f"Cost code (or prefix) {cost_code} matches nothing in the taxonomy.", code="CROSSWALK_COST_CODE")
    if db.one("SELECT 1 FROM code_crosswalk WHERE project_id=? AND system=? AND client_code=? AND cost_code=?", (project_id, system, client_code, cost_code)):
        raise Conflict("Cross-walk row exists.")
    cid = db.insert("code_crosswalk", dict(project_id=project_id, system=system, client_code=client_code, client_name=client_name, cost_code=cost_code,
                                           created_by=actor.username, created_at=now_iso()))
    audit.log(db, actor, "code_crosswalk", cid, "create", after={"system": system, "client_code": client_code, "cost_code": cost_code}, project_id=project_id)
    return cid


def import_crosswalk(db: Database, actor: Actor, project_id: str, system: str, rows: list[dict]) -> dict:
    added, errors = 0, []
    for r in rows:
        try:
            add_crosswalk(db, actor, project_id, system, str(r["client_code"]).strip(), str(r["cost_code"]).strip(), r.get("client_name"))
            added += 1
        except (ValidationFailed, Conflict, KeyError) as e:
            errors.append(f"{r}: {getattr(e, 'message', e)}")
    return {"added": added, "errors": errors}


def list_nodes(db: Database, project_id: str) -> list[dict]:
    return rows_to_dicts(db.all("SELECT * FROM wbs_nodes WHERE project_id=? ORDER BY code", (project_id,)))


# ---------------------------------------------------------------------------------------------------- reports
def _matrix_rows(m: dict) -> dict:
    """Cross-tab as plain rows (JSON-friendly) next to the keyed cells used by callers and tests."""
    return {"cells": m["cells"], "row_totals": m["row_totals"], "col_totals": m["col_totals"], "grand_total": m["grand_total"],
            "rows": [{"wbs": r, "division": c, "amount": a} for (r, c), a in sorted(m["cells"].items())]}


def rollup_report(db: Database, project_id: str, *, est=None, include_unapproved: bool = False) -> dict:
    """Direct cost rolled up by cost-code tree (CBS), by WBS, as a WBS x CBS-division matrix and through each client cross-walk.
    Ties out to the estimate's direct total; items without a cost code / WBS appear in an explicit '(unassigned)' bucket."""
    from ..estimators.estimate import compute_estimate
    est = est or compute_estimate(db, project_id, include_unapproved=include_unapproved)
    items = est.direct.items
    inp = est.inputs
    cost_parent = {r["code"]: r["parent_code"] for r in db.all("SELECT code, parent_code FROM cost_codes")}
    cost_name = {r["code"]: r["name"] for r in db.all("SELECT code, name FROM cost_codes")}
    by_cc: dict[str, Decimal] = {}
    for l in est.direct.lines:                                  # line-level code: item's own, else the assembly's (same rule the engine uses)
        if l.amount is not None:
            by_cc[l.cost_code or ""] = by_cc.get(l.cost_code or "", Decimal(0)) + l.amount
    cbs = rollup.tree_rollup({k or "(none)": v for k, v in by_cc.items()}, cost_parent)
    wbs_nodes = list_nodes(db, project_id)
    wbs_parent = {n["code"]: n["parent_code"] for n in wbs_nodes}
    by_wbs: dict[str, Decimal] = {}
    for k, ic in items.items():
        w = inp.item_wbs.get(k) or "(none)"
        by_wbs[w] = by_wbs.get(w, Decimal(0)) + ic.direct_cost
    wbs = rollup.tree_rollup(by_wbs, wbs_parent)
    cells: dict[tuple[str, str], Decimal] = {}
    for l in est.direct.lines:
        if l.amount is None:
            continue
        key = (inp.item_wbs.get(l.item_key) or "(unassigned)", (l.cost_code or "(none)").split(".")[0])
        cells[key] = cells.get(key, Decimal(0)) + l.amount
    cw_rows = rows_to_dicts(db.all("SELECT * FROM code_crosswalk WHERE project_id=? ORDER BY system, client_code", (project_id,)))
    systems: dict[str, dict] = {}
    for s in sorted({r["system"] for r in cw_rows}):
        rows = [r for r in cw_rows if r["system"] == s]
        res = rollup.crosswalk(by_cc, [(r["client_code"], r["cost_code"]) for r in rows])
        res["client_names"] = {r["client_code"]: r["client_name"] for r in rows}
        systems[s] = res
    total = est.direct.direct_cost_total
    return {
        "project_id": project_id, "state": est.state, "direct_cost_total": total, "currency": est.direct.currency,
        "cbs": {"nodes": [dict(code=c, name=cost_name.get(c, ""), level=cbs["nodes"][c].level, own=cbs["nodes"][c].own, total=cbs["nodes"][c].total)
                          for c in cbs["order"] if cbs["nodes"][c].total != 0 or cbs["nodes"][c].own != 0],
                "unassigned": cbs["unassigned"], "grand_total": cbs["grand_total"]},
        "wbs": {"nodes": [dict(code=c, name=next((n["name"] for n in wbs_nodes if n["code"] == c), ""), level=wbs["nodes"][c].level,
                               own=wbs["nodes"][c].own, total=wbs["nodes"][c].total) for c in wbs["order"]],
                "unassigned": wbs["unassigned"], "grand_total": wbs["grand_total"]},
        "matrix": _matrix_rows(rollup.matrix(cells)), "crosswalks": systems,
        "tie_out": {"cbs": cbs["grand_total"] == total, "wbs": wbs["grand_total"] == total,
                    "crosswalk": {s: r["grand_total"] == total for s, r in systems.items()}},
    }
