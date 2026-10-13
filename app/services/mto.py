"""Material-take-off derivation service. A human supplies the measured driver quantity (or confirms the BOQ quantity is the driver); company-approved
factors turn it into resource quantities; the result is written as takeoff lines marked origin='mto' and the item goes to 'Pending Review' so a person
approves the pricing before it counts. Nothing is measured from drawings and no factor is ever supplied by the software."""
from __future__ import annotations

import json
from decimal import Decimal

from ..approvals import engine as approvals
from ..config import get_settings
from ..core.errors import Conflict, NotFound, ValidationFailed
from ..core.money import D_opt
from ..core.timeutil import now_iso
from ..core.units import registry
from ..database import Database, rows_to_dicts
from ..estimators import mto as engine
from ..models.actor import Actor
from ..models.enums import Status
from . import audit, governed, projects


# slot `unit_dim` may name a group of dimensions (see scripts/gen_mto_templates.py)
DIM_GROUPS = {"time": {"time_hr", "time_day", "time_wk", "time_mo"}, "count*": {"count", "item", "joint", "spool", "loop", "tag", "set", "pair"}}


def templates() -> dict[str, dict]:
    return engine.load_templates(get_settings().data_dir)


def get_template(code: str) -> dict:
    t = templates().get(code)
    if not t:
        raise NotFound(f"Unknown take-off template '{code}'. Known: {sorted(templates())}")
    return t


def check_factor(db: Database, code: str, clean: dict) -> None:
    t = get_template(clean["template"])
    slot = next((s for s in t["slots"] if s["slot"] == clean["slot"]), None)
    if slot is None:
        raise ValidationFailed(f"Template {t['code']} has no slot '{clean['slot']}'. Slots: {[s['slot'] for s in t['slots']]}", code="MTO_SLOT")
    if code != f"{clean['template']}/{clean['slot']}":
        raise ValidationFailed(f"The parameter code must be '{clean['template']}/{clean['slot']}'.", code="MTO_CODE")
    res = db.one("SELECT r.resource_type, r.unit, u.dimension FROM resources r LEFT JOIN units u ON u.code=r.unit WHERE r.id=?", (clean["resource_id"],))
    if not res:
        raise ValidationFailed(f"resource_id {clean['resource_id']} not found.", code="PARAM_FIELD")
    if res["resource_type"] != slot["resource_type"]:
        raise ValidationFailed(f"Slot {slot['slot']} expects a {slot['resource_type']} resource; {clean['resource_id']} is {res['resource_type']}.", code="MTO_RESOURCE")
    allowed = DIM_GROUPS.get(slot["unit_dim"], {slot["unit_dim"]})
    if res["dimension"] not in allowed:
        raise ValidationFailed(f"Slot {slot['slot']} expects a unit of kind '{slot['unit_dim']}' ({', '.join(sorted(allowed))}); {clean['resource_id']} is in '{res['unit']}' ({res['dimension']}).", code="MTO_UNIT")


def _factors(db: Database, project_id: str, template: str, include_unapproved: bool = False) -> dict[str, dict]:
    out = {}
    for p in governed.effective(db, project_id, "mto_factor", include_unapproved=include_unapproved):
        d = p["data"]
        if d["template"] == template:
            out[d["slot"]] = dict(resource_id=d["resource_id"], factor=d["factor"], waste_pct=d.get("waste_pct"), ref=dict(param_id=p["id"], code=p["code"], version=p["version"]))
    return out


def _driver(db: Database, project_id: str, item: dict, t: dict, driver_qty, driver_source) -> tuple[Decimal, str]:
    if driver_qty not in (None, ""):
        q = D_opt(driver_qty)
        if q is None or q < 0:
            raise ValidationFailed("driver_qty must be a non-negative number.", code="MTO_DRIVER")
        if not (driver_source or "").strip():
            raise ValidationFailed("A measured driver quantity needs its source (MTO / drawing / register reference).", code="MTO_DRIVER_SOURCE")
        return q, driver_source.strip()
    iq = D_opt(item.get("quantity"))
    if iq is None:
        raise ValidationFailed(f"BOQ item {item['item_key']} has no quantity; give the measured driver quantity and its source.", code="MTO_DRIVER")
    reg = registry(db)
    if item.get("unit") and reg.can_convert(item["unit"], t["driver_unit"]):
        return iq * reg.factor(item["unit"], t["driver_unit"]), f"BOQ item {item['item_key']} quantity ({item['quantity']} {item['unit']})"
    raise ValidationFailed(f"Item unit '{item.get('unit')}' is not the template driver unit '{t['driver_unit']}': give driver_qty and driver_source.", code="MTO_DRIVER_UNIT")


def preview(db: Database, project_id: str, item_key: str, template: str, driver_qty=None, driver_source=None, skip_slots: list[str] | None = None) -> dict:
    t = get_template(template)
    item = db.one("SELECT * FROM boq_items WHERE project_id=? AND item_key=? AND item_type='item'", (project_id, item_key))
    if not item:
        raise NotFound(f"BOQ item {item_key} not found.")
    q, src = _driver(db, project_id, dict(item), t, driver_qty, driver_source)
    res = engine.derive(t, q, _factors(db, project_id, template), set(skip_slots or []))
    res["driver_source"] = src
    res["item_key"] = item_key
    return res


def apply(db: Database, actor: Actor, project_id: str, item_key: str, template: str, driver_qty=None, driver_source=None, skip_slots: list[str] | None = None) -> dict:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    item = dict(db.one("SELECT * FROM boq_items WHERE project_id=? AND item_key=? AND item_type='item'", (project_id, item_key)) or {})
    if not item:
        raise NotFound(f"BOQ item {item_key} not found.")
    if item["pricing_method"] not in ("unpriced", "takeoff_resources"):
        raise Conflict(f"Item {item_key} is priced by '{item['pricing_method']}'. Clear that first - an item may not be priced twice.", code="MTO_ITEM_PRICED")
    other = db.one("SELECT 1 FROM takeoff_resource_lines WHERE project_id=? AND item_key=? AND COALESCE(origin,'')<>'mto'", (project_id, item_key))
    if other:
        raise Conflict(f"Item {item_key} already has imported take-off lines; MTO derivation would double count.", code="MTO_ITEM_PRICED")
    pv = preview(db, project_id, item_key, template, driver_qty, driver_source, skip_slots)
    if pv["missing"]:
        raise ValidationFailed(f"No approved factor for slot(s) {pv['missing']} of template {template}. Approve the factors first, or skip the slot explicitly "
                               f"(skip_slots) if that cost is covered elsewhere.", code="MTO_FACTORS_MISSING")
    with db.tx():
        db.execute("DELETE FROM takeoff_resource_lines WHERE project_id=? AND item_key=? AND origin='mto' AND origin_ref=?", (project_id, item_key, template))
        for l in pv["lines"]:
            r = db.one("SELECT unit FROM resources WHERE id=?", (l["resource_id"],))
            db.insert("takeoff_resource_lines", dict(project_id=project_id, item_key=item_key, resource_id=l["resource_id"], description=f"{template}/{l['slot']}: {l['description']}",
                                                     quantity=str(l["qty"]), unit=r["unit"], source_file=f"mto:{template}", origin="mto", origin_ref=template, notes=l["basis"]))
        db.update("boq_items", {"pricing_method": "takeoff_resources", "pricing_status": Status.PENDING.value,
                                "pricing_note": f"Derived by take-off template {template} from driver {pv['driver_qty']} {pv['driver_unit']} ({pv['driver_source']}); review required"},
                  "project_id=? AND item_key=?", (project_id, item_key))
        refs = [dict(slot=l["slot"], **l["ref"], factor=str(l["factor"]), resource_id=l["resource_id"]) for l in pv["lines"]]
        aid = db.insert("mto_applications", dict(project_id=project_id, item_key=item_key, template=template, driver_qty=str(pv["driver_qty"]), driver_unit=pv["driver_unit"],
                                                 driver_source=pv["driver_source"], factor_refs_json=json.dumps(refs), skipped_json=json.dumps(pv["skipped"]),
                                                 lines_json=json.dumps([{k: str(v) if isinstance(v, Decimal) else v for k, v in l.items() if k != "ref"} for l in pv["lines"]]),
                                                 applied_by=actor.username, applied_at=now_iso()))
        audit.log(db, actor, "mto_application", f"{project_id}/{item_key}/{template}", "apply", after={"driver": str(pv["driver_qty"]), "lines": len(pv["lines"]), "skipped": pv["skipped"]},
                  project_id=project_id)
    pv["application_id"] = aid
    return pv


def status_report(db: Database, project_id: str) -> dict:
    """Latest application per (item, template): is it still current? Stale = the BOQ quantity (when it was the driver) or an approved factor changed since."""
    rows = rows_to_dicts(db.all("SELECT * FROM mto_applications WHERE project_id=? ORDER BY id", (project_id,)))
    latest: dict[tuple, dict] = {}
    for r in rows:
        latest[(r["item_key"], r["template"])] = r
    out = []
    cur_factors: dict[str, dict] = {}
    for (ik, tc), r in latest.items():
        cur_factors.setdefault(tc, _factors(db, project_id, tc))
        item = db.one("SELECT quantity, pricing_status, unit FROM boq_items WHERE project_id=? AND item_key=?", (project_id, ik))
        used = {x["slot"]: (x["code"], x["version"]) for x in json.loads(r["factor_refs_json"])}
        now = {s: (f["ref"]["code"], f["ref"]["version"]) for s, f in cur_factors[tc].items()}
        changed = sorted(s for s, v in used.items() if now.get(s) != v)
        stale_driver = bool(item and r["driver_source"] and r["driver_source"].startswith("BOQ item") and D_opt(item["quantity"]) is not None
                            and f"({item['quantity']} " not in r["driver_source"])
        flags = (["FACTORS_CHANGED"] if changed else []) + (["DRIVER_CHANGED"] if stale_driver else [])
        out.append(dict(item_key=ik, template=tc, driver_qty=r["driver_qty"], driver_unit=r["driver_unit"], applied_by=r["applied_by"], applied_at=r["applied_at"],
                        pricing_status=item["pricing_status"] if item else None, skipped=json.loads(r["skipped_json"] or "[]"), changed_slots=changed,
                        current=not flags, flags=flags))
    return dict(project_id=project_id, applications=out, stale=[a for a in out if not a["current"]], pending_review=[a for a in out if a["pricing_status"] == "Pending Review"])
