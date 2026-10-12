"""Assembly library: versioned resource build-ups per unit of completed work."""
from __future__ import annotations

import json
from typing import Any

from ..approvals import engine as approvals
from ..core.errors import Conflict, ImmutableRecord, NotFound, ValidationFailed
from ..core.money import D_opt
from ..core.timeutil import now_iso
from ..database import Database, jload, rows_to_dicts
from ..models.actor import Actor
from ..models.enums import Entity, Status
from . import audit

LINE_TYPES = ("material", "labour", "plant", "equipment", "subcontract", "assembly", "other")
LINE_FIELDS = {"line_type", "resource_id", "child_assembly_code", "child_assembly_version", "description", "factor",
               "factor_unit", "factor_includes_waste", "waste_basis", "waste_value", "waste_ref", "productivity_basis",
               "crew_json", "shift_hours_ref", "productive_hours_ref", "overtime_share_pct", "utilisation_basis",
               "utilisation_value", "utilisation_ref", "includes_labour", "includes_material", "includes_plant",
               "explicitly_separate", "notes"}


def get(db: Database, code: str, version: int | None = None) -> dict:
    if version is None:
        r = db.one("SELECT * FROM assemblies WHERE code=? ORDER BY version DESC LIMIT 1", (code,))
    else:
        r = db.one("SELECT * FROM assemblies WHERE code=? AND version=?", (code, version))
    if not r:
        raise NotFound(f"Assembly {code} not found.")
    return dict(r)


def get_approved(db: Database, code: str, project_id: str | None = None) -> dict | None:
    """Latest Approved version; a project-specific approved customisation (same code) wins."""
    if project_id:
        r = db.one("SELECT * FROM assemblies WHERE code=? AND status='Approved' AND project_id=? "
                   "ORDER BY version DESC LIMIT 1", (code, project_id))
        if r:
            return dict(r)
    r = db.one("SELECT * FROM assemblies WHERE code=? AND status='Approved' AND project_id IS NULL "
               "ORDER BY version DESC LIMIT 1", (code,))
    return dict(r) if r else None


def lines(db: Database, assembly_pk: int) -> list[dict]:
    out = rows_to_dicts(db.all("SELECT * FROM assembly_lines WHERE assembly_pk=? ORDER BY line_no", (assembly_pk,)))
    for l in out:
        l["crew"] = jload(l.get("crew_json"), [])
    return out


def list_assemblies(db: Database, cost_code: str | None = None, q: str | None = None, project_id: str | None = None
                    ) -> list[dict]:
    sql = "SELECT a.* FROM assemblies a WHERE a.version=(SELECT MAX(version) FROM assemblies WHERE code=a.code)"
    params: list[Any] = []
    if cost_code:
        sql += " AND a.cost_code LIKE ?"; params.append(cost_code + "%")
    if q:
        sql += " AND (a.code LIKE ? OR a.description LIKE ?)"; params += [f"%{q}%"] * 2
    if project_id:
        sql += " AND (a.project_id IS NULL OR a.project_id=?)"; params.append(project_id)
    return rows_to_dicts(db.all(sql + " ORDER BY a.code", params))


def create_assembly(db: Database, actor: Actor, *, code: str, description: str, unit: str, cost_code: str | None = None,
                    specification: str | None = None, applicability: str | None = None, source: str | None = None,
                    confidence: str = "Unverified", project_id: str | None = None, is_synthetic: bool = False,
                    notes: str | None = None, lines_: list[dict] | None = None) -> int:
    approvals.require_author(actor)
    if db.one("SELECT 1 FROM assemblies WHERE code=?", (code,)):
        raise Conflict(f"Assembly {code} exists; use new_version().")
    if not db.one("SELECT 1 FROM units WHERE code=?", (unit,)):
        raise ValidationFailed(f"Unknown unit '{unit}'.")
    if cost_code and not db.one("SELECT 1 FROM cost_codes WHERE code=?", (cost_code,)):
        raise ValidationFailed(f"Unknown cost code '{cost_code}'.")
    with db.tx():
        pk = db.insert("assemblies", dict(code=code, version=1, cost_code=cost_code, description=description, unit=unit,
                                          specification=specification, applicability=applicability, source=source,
                                          confidence=confidence, status=Status.DRAFT.value, project_id=project_id,
                                          is_synthetic=int(is_synthetic), notes=notes, created_by=actor.username,
                                          created_at=now_iso()))
        for l in lines_ or []:
            add_line(db, actor, pk, **l)
    audit.log(db, actor, "assembly", code, "create", after={"unit": unit, "cost_code": cost_code}, project_id=project_id)
    return pk


def _assembly_by_pk(db: Database, pk: int) -> dict:
    r = db.one("SELECT * FROM assemblies WHERE pk=?", (pk,))
    if not r:
        raise NotFound(f"Assembly pk {pk} not found.")
    return dict(r)


def _require_editable(a: dict) -> None:
    if a["status"] not in (Status.DRAFT.value, Status.REJECTED.value, Status.PENDING.value):
        raise ImmutableRecord(f"Assembly {a['code']} v{a['version']} is {a['status']} and immutable. "
                              "Create a new version to change it.")


def add_line(db: Database, actor: Actor, assembly_pk: int, **line) -> int:
    approvals.require_author(actor)
    a = _assembly_by_pk(db, assembly_pk)
    _require_editable(a)
    if a["status"] == Status.PENDING.value:
        db.update("assemblies", {"status": Status.DRAFT.value}, "pk=?", (assembly_pk,))
    bad = set(line) - LINE_FIELDS
    if bad:
        raise ValidationFailed(f"Unknown assembly line fields: {sorted(bad)}")
    lt = line.get("line_type")
    if lt not in LINE_TYPES:
        raise ValidationFailed(f"line_type must be one of {LINE_TYPES}")
    if lt == "assembly":
        if not line.get("child_assembly_code"):
            raise ValidationFailed("Nested assembly line needs child_assembly_code.")
        if line["child_assembly_code"] == a["code"]:
            raise ValidationFailed("An assembly cannot contain itself.", code="CIRCULAR_ASSEMBLY")
        if would_create_cycle(db, a["code"], line["child_assembly_code"]):
            raise ValidationFailed(f"Adding {line['child_assembly_code']} to {a['code']} creates a circular reference.",
                                   code="CIRCULAR_ASSEMBLY")
    else:
        rid = line.get("resource_id")
        if lt != "other" and not rid:
            raise ValidationFailed(f"{lt} line requires resource_id.")
        if rid and not db.one("SELECT 1 FROM resources WHERE id=?", (rid,)):
            raise ValidationFailed(f"Unknown resource {rid}.")
    if line.get("factor") not in (None, "") and D_opt(line["factor"]) is None:
        raise ValidationFailed("factor must be numeric.")
    if line.get("crew") is not None:
        line["crew_json"] = json.dumps(line.pop("crew"))
    _check_line_rules(line)
    n = (db.scalar("SELECT MAX(line_no) FROM assembly_lines WHERE assembly_pk=?", (assembly_pk,)) or 0) + 1
    lid = db.insert("assembly_lines", {**line, "assembly_pk": assembly_pk, "line_no": n})
    audit.log(db, actor, "assembly", a["code"], "add_line", after={k: line.get(k) for k in ("line_type", "resource_id", "factor")})
    return lid


def _check_line_rules(line: dict) -> None:
    """Explicit calculation basis: never apply waste twice, never mix bases."""
    wb = line.get("waste_basis") or "none"
    if line.get("factor_includes_waste") and wb != "none":
        raise ValidationFailed("Waste would be applied twice: factor_includes_waste is set AND a waste basis is given.",
                               code="DOUBLE_WASTE")
    if wb == "fixed_pct" and D_opt(line.get("waste_value")) is None:
        raise ValidationFailed("waste_basis=fixed_pct needs waste_value (percent points).")
    if wb == "assumption" and not line.get("waste_ref"):
        raise ValidationFailed("waste_basis=assumption needs waste_ref (assumption id).")
    ub = line.get("utilisation_basis") or "none"
    if ub == "fixed_pct" and D_opt(line.get("utilisation_value")) is None:
        raise ValidationFailed("utilisation_basis=fixed_pct needs utilisation_value.")
    if ub == "assumption" and not line.get("utilisation_ref"):
        raise ValidationFailed("utilisation_basis=assumption needs utilisation_ref.")
    pb = line.get("productivity_basis")
    if pb == "output_per_crew_shift":
        crew = jload(line.get("crew_json"), None)
        if not crew:
            raise ValidationFailed("output_per_crew_shift requires a crew composition (crew).")


def update_line(db: Database, actor: Actor, assembly_pk: int, line_no: int, **changes) -> None:
    approvals.require_author(actor)
    a = _assembly_by_pk(db, assembly_pk)
    _require_editable(a)
    cur = db.one("SELECT * FROM assembly_lines WHERE assembly_pk=? AND line_no=?", (assembly_pk, line_no))
    if not cur:
        raise NotFound("Assembly line not found.")
    if "crew" in changes:
        changes["crew_json"] = json.dumps(changes.pop("crew"))
    bad = set(changes) - LINE_FIELDS
    if bad:
        raise ValidationFailed(f"Unknown fields: {sorted(bad)}")
    merged = {**dict(cur), **changes}
    _check_line_rules(merged)
    db.update("assembly_lines", changes, "assembly_pk=? AND line_no=?", (assembly_pk, line_no))
    db.update("assemblies", {"status": Status.DRAFT.value}, "pk=?", (assembly_pk,))
    audit.log(db, actor, "assembly", a["code"], "update_line", before={k: cur[k] for k in changes}, after=changes)


def remove_line(db: Database, actor: Actor, assembly_pk: int, line_no: int) -> None:
    approvals.require_author(actor)
    a = _assembly_by_pk(db, assembly_pk)
    _require_editable(a)
    db.execute("DELETE FROM assembly_lines WHERE assembly_pk=? AND line_no=?", (assembly_pk, line_no))
    audit.log(db, actor, "assembly", a["code"], "remove_line", before={"line_no": line_no})


def children_of(db: Database, code: str) -> set[str]:
    """Nested assembly codes referenced by ANY version of `code`."""
    rows = db.all("SELECT DISTINCT l.child_assembly_code c FROM assembly_lines l JOIN assemblies a ON a.pk=l.assembly_pk "
                  "WHERE a.code=? AND l.line_type='assembly'", (code,))
    return {r["c"] for r in rows if r["c"]}


def would_create_cycle(db: Database, parent: str, child: str) -> bool:
    seen, stack = set(), [child]
    while stack:
        cur = stack.pop()
        if cur == parent:
            return True
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(children_of(db, cur))
    return False


def new_version(db: Database, actor: Actor, code: str, *, revision_note: str | None = None, project_id: str | None = None
                ) -> int:
    """Clone the latest version as a new Draft (pending revision). The old version is untouched."""
    approvals.require_author(actor)
    cur = get(db, code)
    if cur["status"] in (Status.DRAFT.value,) and not project_id:
        raise Conflict(f"{code} v{cur['version']} is already a Draft; edit it directly.")
    with db.tx():
        pk = db.insert("assemblies", dict(
            code=code, version=cur["version"] + 1, cost_code=cur["cost_code"], description=cur["description"],
            unit=cur["unit"], specification=cur["specification"], applicability=cur["applicability"],
            source=cur["source"], confidence=cur["confidence"], status=Status.DRAFT.value,
            project_id=project_id if project_id is not None else cur["project_id"], cloned_from=f"{code}@{cur['version']}",
            is_synthetic=cur["is_synthetic"], notes=cur["notes"], revision_note=revision_note,
            created_by=actor.username, created_at=now_iso()))
        for l in lines(db, cur["pk"]):
            d = {k: l[k] for k in LINE_FIELDS | {"line_no"}}
            db.insert("assembly_lines", {**d, "assembly_pk": pk})
    audit.log(db, actor, "assembly", code, "new_version", after={"version": cur["version"] + 1}, comment=revision_note)
    return pk


def clone(db: Database, actor: Actor, code: str, new_code: str, *, project_id: str | None = None,
          description: str | None = None) -> int:
    approvals.require_author(actor)
    src = get(db, code)
    if db.one("SELECT 1 FROM assemblies WHERE code=?", (new_code,)):
        raise Conflict(f"{new_code} already exists.")
    with db.tx():
        pk = db.insert("assemblies", dict(
            code=new_code, version=1, cost_code=src["cost_code"], description=description or src["description"],
            unit=src["unit"], specification=src["specification"], applicability=src["applicability"],
            source=src["source"], confidence="Unverified", status=Status.DRAFT.value, project_id=project_id,
            cloned_from=f"{code}@{src['version']}", is_synthetic=src["is_synthetic"], notes=src["notes"],
            created_by=actor.username, created_at=now_iso()))
        for l in lines(db, src["pk"]):
            d = {k: l[k] for k in LINE_FIELDS | {"line_no"}}
            db.insert("assembly_lines", {**d, "assembly_pk": pk})
    audit.log(db, actor, "assembly", new_code, "clone", after={"from": f"{code}@{src['version']}"}, project_id=project_id)
    return pk


def validate(db: Database, assembly_pk: int) -> list[str]:
    """Structural validation. Returns blocking problems (empty => approvable)."""
    a = _assembly_by_pk(db, assembly_pk)
    problems: list[str] = []
    ls = lines(db, assembly_pk)
    if not ls:
        problems.append("Assembly has no resource lines.")
    sub_flags = {"labour": False, "material": False, "plant": False}
    for l in ls:
        if l["line_type"] == "subcontract":
            sub_flags["labour"] |= bool(l["includes_labour"])
            sub_flags["material"] |= bool(l["includes_material"])
            sub_flags["plant"] |= bool(l["includes_plant"])
    for l in ls:
        tag = f"line {l['line_no']}"
        if l["line_type"] != "other" and D_opt(l["factor"]) is None and l["productivity_basis"] is None:
            problems.append(f"{tag}: consumption factor is missing (estimator input required).")
        if l["line_type"] == "assembly" and not db.one("SELECT 1 FROM assemblies WHERE code=?", (l["child_assembly_code"],)):
            problems.append(f"{tag}: nested assembly {l['child_assembly_code']} not found.")
        if l["line_type"] in ("labour", "material", "plant") and sub_flags.get(l["line_type"]) and not l["explicitly_separate"]:
            problems.append(f"{tag}: {l['line_type']} line duplicates a subcontract line that already includes "
                            f"{l['line_type']} (set explicitly_separate only if the scope requires separate charging).")
    return problems


def submit_assembly(db: Database, actor: Actor, code: str) -> None:
    approvals.require_author(actor)
    a = get(db, code)
    if a["status"] not in (Status.DRAFT.value, Status.REJECTED.value):
        raise Conflict(f"Only Draft/Rejected assemblies can be submitted (is {a['status']}).")
    db.update("assemblies", {"status": Status.PENDING.value}, "pk=?", (a["pk"],))
    audit.log(db, actor, "assembly", code, "submit", after={"version": a["version"]})


def approve_assembly(db: Database, actor: Actor, code: str, *, comments: str | None = None,
                     evidence: str | None = None, version: int | None = None) -> None:
    a = get(db, code, version)
    approvals.authorize(actor, Entity.ASSEMBLY.value, "approve", created_by=a["created_by"])
    if a["status"] != Status.PENDING.value:
        raise Conflict(f"Assembly must be Pending Review (is {a['status']}).", code="NOT_PENDING")
    problems = validate(db, a["pk"])
    if problems:
        raise ValidationFailed("Assembly cannot be approved: " + "; ".join(problems), code="ASSEMBLY_INVALID",
                               details=problems)
    with db.tx():
        for old in db.all("SELECT pk FROM assemblies WHERE code=? AND status='Approved' AND version<? AND "
                          "COALESCE(project_id,'')=COALESCE(?,'')", (code, a["version"], a["project_id"])):
            db.update("assemblies", {"status": Status.SUPERSEDED.value}, "pk=?", (old["pk"],))
        db.update("assemblies", {"status": Status.APPROVED.value, "approved_by": actor.username,
                                 "approved_at": now_iso()}, "pk=?", (a["pk"],))
        approvals.record(db, actor, Entity.ASSEMBLY.value, code, "approve", version=a["version"],
                         approved_value={"lines": len(lines(db, a["pk"]))}, evidence=evidence, comments=comments,
                         project_id=a["project_id"])


def reject_assembly(db: Database, actor: Actor, code: str, reason: str) -> None:
    a = get(db, code)
    approvals.authorize(actor, Entity.ASSEMBLY.value, "reject")
    if a["status"] in (Status.APPROVED.value, Status.SUPERSEDED.value):
        raise ImmutableRecord("Approved assemblies cannot be rejected; create a new version.")
    db.update("assemblies", {"status": Status.REJECTED.value}, "pk=?", (a["pk"],))
    approvals.record(db, actor, Entity.ASSEMBLY.value, code, "reject", version=a["version"], comments=reason)
