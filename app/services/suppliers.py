"""Supplier directory. Contact details are accepted only with a traceable source - never invented."""
from __future__ import annotations

from ..approvals import engine as approvals
from ..core.errors import Conflict, NotFound, ValidationFailed
from ..core.timeutil import now_iso
from ..database import Database, rows_to_dicts
from ..models.actor import Actor
from ..models.enums import Entity, Status
from . import audit


def next_supplier_id(db: Database) -> str:
    n = db.scalar("SELECT COUNT(*) FROM suppliers") or 0
    while True:
        n += 1
        sid = f"SUP-{n:04d}"
        if not db.one("SELECT 1 FROM suppliers WHERE id=?", (sid,)):
            return sid


def create_supplier(db: Database, actor: Actor, *, name: str, supplier_type: str = "supplier", trades: str = "",
                    region: str = "KSA-ALL", contact_name: str | None = None, contact_email: str | None = None,
                    contact_phone: str | None = None, contact_source: str | None = None,
                    contact_permitted_use: str | None = None, is_synthetic: bool = False, notes: str | None = None,
                    id: str | None = None, name_ar: str | None = None) -> str:
    approvals.require_author(actor)
    has_contact = any([contact_name, contact_email, contact_phone])
    if has_contact and not (contact_source and contact_source.strip()):
        raise ValidationFailed("Contact details require a traceable contact_source (where they came from and that use is "
                               "permitted). Do not enter contacts you cannot source.", code="CONTACT_SOURCE_REQUIRED")
    sid = id or next_supplier_id(db)
    if db.one("SELECT 1 FROM suppliers WHERE id=?", (sid,)):
        raise Conflict(f"Supplier {sid} exists.")
    db.insert("suppliers", dict(id=sid, name=name, name_ar=name_ar, supplier_type=supplier_type, trades=trades, region=region,
                                contact_name=contact_name, contact_email=contact_email, contact_phone=contact_phone,
                                contact_source=contact_source, contact_permitted_use=contact_permitted_use,
                                qualification_status=Status.PENDING.value, is_synthetic=int(is_synthetic), notes=notes,
                                created_by=actor.username, created_at=now_iso()))
    audit.log(db, actor, "supplier", sid, "create", after={"name": name, "has_contact": has_contact})
    return sid


def get_supplier(db: Database, sid: str) -> dict:
    r = db.one("SELECT * FROM suppliers WHERE id=?", (sid,))
    if not r:
        raise NotFound(f"Supplier {sid} not found.")
    return dict(r)


def list_suppliers(db: Database, q: str | None = None) -> list[dict]:
    if q:
        return rows_to_dicts(db.all("SELECT * FROM suppliers WHERE name LIKE ? OR trades LIKE ? ORDER BY id", (f"%{q}%", f"%{q}%")))
    return rows_to_dicts(db.all("SELECT * FROM suppliers ORDER BY id"))


def qualify_supplier(db: Database, actor: Actor, sid: str, comments: str | None = None) -> None:
    s = get_supplier(db, sid)
    approvals.authorize(actor, Entity.SUPPLIER.value, "approve", created_by=s["created_by"])
    db.update("suppliers", {"qualification_status": Status.APPROVED.value, "approved_by": actor.username,
                            "approved_at": now_iso()}, "id=?", (sid,))
    approvals.record(db, actor, Entity.SUPPLIER.value, sid, "approve", comments=comments)
