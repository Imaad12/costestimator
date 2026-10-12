"""Load an immutable EstimateInputs snapshot from the database (the only place estimating reads SQL)."""
from __future__ import annotations

from datetime import date

from ..core.timeutil import parse_date, today
from ..core.units import registry
from ..database import Database, jload, rows_to_dicts
from ..services import assemblies as asm_service
from ..services import assumptions as assumption_service
from .types import AssemblyDef, AssumptionValue, EstimateInputs

ASSUMPTION_REF_FIELDS = ("waste_ref", "utilisation_ref", "shift_hours_ref", "productive_hours_ref")


def _load_assembly(db: Database, code: str, project_id: str, include_unapproved: bool) -> dict | None:
    a = asm_service.get_approved(db, code, project_id)
    if a is None and include_unapproved:
        try:
            a = asm_service.get(db, code)
        except Exception:
            a = None
    return a


def load_inputs(db: Database, project_id: str, *, include_unapproved: bool = False, as_of: date | None = None,
                assumption_overrides: dict[str, str] | None = None) -> EstimateInputs:
    project = dict(db.one("SELECT * FROM projects WHERE id=?", (project_id,)))
    as_of = as_of or parse_date(project.get("rate_as_of_date")) or today()
    items = rows_to_dicts(db.all("SELECT * FROM boq_items WHERE project_id=? ORDER BY id", (project_id,)))

    # ---- assemblies (recursive closure of nested assemblies)
    asm_defs: dict[str, AssemblyDef] = {}
    pending = [i["assembly_code"] for i in items if i.get("assembly_code") and i["item_type"] == "item"]
    seen: set[str] = set()
    resource_ids: set[str] = set()
    assumption_ids: set[str] = set()
    while pending:
        code = pending.pop()
        if code in seen:
            continue
        seen.add(code)
        a = _load_assembly(db, code, project_id, include_unapproved)
        if a is None:
            continue
        ls = asm_service.lines(db, a["pk"])
        asm_defs[code] = AssemblyDef(code, a["version"], a["unit"], a["description"], a["status"], bool(a["is_synthetic"]),
                                     ls, a["cost_code"])
        for l in ls:
            if l["line_type"] == "assembly" and l["child_assembly_code"]:
                pending.append(l["child_assembly_code"])
            if l.get("resource_id"):
                resource_ids.add(l["resource_id"])
            for c in l.get("crew") or []:
                resource_ids.add(c["resource_id"])
            for f in ASSUMPTION_REF_FIELDS:
                if l.get(f):
                    assumption_ids.add(l[f])

    # ---- takeoff + direct pricing resources
    takeoff: dict[str, list[dict]] = {}
    for t in rows_to_dicts(db.all("SELECT * FROM takeoff_resource_lines WHERE project_id=?", (project_id,))):
        takeoff.setdefault(t["item_key"], []).append(t)
        if t.get("resource_id"):
            resource_ids.add(t["resource_id"])
    for i in items:
        if i.get("pricing_resource_id"):
            resource_ids.add(i["pricing_resource_id"])

    resources: dict[str, dict] = {}
    rates: dict[str, list[dict]] = {}
    for rid in resource_ids:
        r = db.one("SELECT * FROM resources WHERE id=?", (rid,))
        if r:
            resources[rid] = dict(r)
            rates[rid] = rows_to_dicts(db.all("SELECT * FROM resource_rates WHERE resource_id=?", (rid,)))

    # ---- assumptions
    engine_keys: dict[str, AssumptionValue] = {}
    for row in db.all("SELECT DISTINCT id, engine_key FROM assumptions WHERE engine_key IS NOT NULL"):
        ra = assumption_service.resolve(db, project_id, row["id"], as_of.isoformat())
        engine_keys[row["engine_key"]] = AssumptionValue(ra.id, ra.value, ra.status, ra.origin, ra.name, ra.unit, row["engine_key"])
    assumptions: dict[str, AssumptionValue] = {}
    for aid in assumption_ids:
        ra = assumption_service.resolve(db, project_id, aid, as_of.isoformat())
        assumptions[aid] = AssumptionValue(aid, ra.value, ra.status, ra.origin, ra.name, ra.unit, ra.engine_key)
    if assumption_overrides:
        for k, v in assumption_overrides.items():
            for store in (assumptions, engine_keys):
                for key, av in store.items():
                    if k in (av.id, av.engine_key):
                        store[key] = AssumptionValue(av.id, str(v), "Approved", "what_if", av.name, av.unit, av.engine_key)
            if k not in assumptions and not any(k == av.engine_key for av in engine_keys.values()):
                ra = assumption_service.resolve(db, project_id, k, as_of.isoformat())
                assumptions[k] = AssumptionValue(k, str(v), "Approved", "what_if", ra.name, ra.unit, ra.engine_key)

    fx = rows_to_dicts(db.all("SELECT * FROM fx_rates"))
    parents = {r["code"]: r["parent_code"] for r in db.all("SELECT code, parent_code FROM regions")}
    return EstimateInputs(project=project, as_of=as_of, items=items, assemblies=asm_defs, resources=resources, rates=rates,
                          assumptions=assumptions, engine_keys=engine_keys, takeoff=takeoff, fx=fx,
                          units=registry(db), region_parents=parents, include_unapproved=include_unapproved)
