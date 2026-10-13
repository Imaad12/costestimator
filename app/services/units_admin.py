"""Administrator-managed unit definitions (audited; never silently overriding an existing unit or spelling).

Rules: a unit's `to_base` is an exact positive decimal; every dimension has exactly one base unit (to_base = 1); a dimension is
convertible automatically only if it is in `core.units.CONVERTIBLE` (physically exact definitions); spellings that already resolve to
another unit - or that are already declared ambiguous - are refused so that a BOQ cannot silently change meaning."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from ..approvals import engine as approvals
from ..core.errors import Conflict, ValidationFailed
from ..core.units import UnitRegistry, _norm
from ..database import Database
from ..models.actor import Actor
from . import audit

_CODE = re.compile(r"^[a-z][a-z0-9_]{0,23}$")


def add_unit(db: Database, actor: Actor, *, code: str, name: str, dimension: str, to_base: str = "1", synonyms: str = "", ambiguous_synonyms: str = "") -> str:
    approvals.require_admin(actor, "unit management")
    code = (code or "").strip()
    if not _CODE.match(code):
        raise ValidationFailed("Unit code must be lower-case letters/digits/underscore, starting with a letter (max 24).", code="BAD_UNIT_CODE")
    if db.one("SELECT 1 FROM units WHERE code=?", (code,)):
        raise Conflict(f"Unit '{code}' already exists. Units are never redefined; add a new code instead.", code="UNIT_EXISTS")
    if not name.strip() or not dimension.strip():
        raise ValidationFailed("name and dimension are required.")
    try:
        tb = Decimal(str(to_base))
    except InvalidOperation:
        raise ValidationFailed(f"to_base '{to_base}' is not a number.", code="BAD_UNIT_FACTOR")
    if tb <= 0:
        raise ValidationFailed("to_base must be > 0.", code="BAD_UNIT_FACTOR")
    existing = db.all("SELECT code, to_base FROM units WHERE dimension=?", (dimension,))
    if existing and tb != 1 and not any(Decimal(r["to_base"]) == 1 for r in existing):
        raise ValidationFailed(f"Dimension '{dimension}' has no base unit (to_base 1).", code="NO_BASE_UNIT")
    if not existing and tb != 1:
        raise ValidationFailed("The first unit of a new dimension must be its base unit (to_base = 1).", code="NO_BASE_UNIT")
    reg = UnitRegistry.from_db(db)
    syns = [s.strip() for s in synonyms.split("|") if s.strip()]
    ambs = [s.strip() for s in ambiguous_synonyms.split("|") if s.strip()]
    for s in [code, *syns]:
        r = reg.resolve(s)
        if r.status in ("ok", "ambiguous"):
            raise Conflict(f"Spelling '{s}' already means {r.code or r.candidates}; refusing to change how existing BOQs are read.", code="UNIT_SPELLING_CLASH")
    for s in ambs:
        if _norm(s) in {_norm(x) for x in syns}:
            raise ValidationFailed(f"'{s}' cannot be both a synonym and ambiguous.")
    db.insert("units", dict(code=code, name=name.strip(), dimension=dimension.strip(), to_base=str(tb), synonyms="|".join(syns) or None,
                            ambiguous_synonyms="|".join(ambs) or None, active=1))
    audit.log(db, actor, "unit", code, "create", after={"dimension": dimension, "to_base": str(tb), "synonyms": syns})
    return code
