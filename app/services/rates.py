"""Resource & rate management with versioning and approval gating."""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from ..approvals import engine as approvals
from ..core.errors import Conflict, ImmutableRecord, NotFound, ValidationFailed
from ..core.money import D, D_opt, to_text
from ..core.timeutil import now_iso, parse_date, today_iso
from ..database import Database, jload, row_to_dict, rows_to_dicts
from ..estimators import rate_build
from ..models.actor import Actor
from ..models.enums import (NON_PRICE_RATE_TYPES, RATE_TYPE_VALUES, RESOURCE_TYPES, Entity, RateType, Status)
from . import audit

FINAL_STATES = (Status.APPROVED.value, Status.PROVISIONAL.value, Status.SUPERSEDED.value, Status.EXPIRED.value)


# ----------------------------------------------------------------------------- resources
def next_resource_id(db: Database, prefix: str) -> str:
    n = db.scalar("SELECT COUNT(*) FROM resources WHERE id LIKE ?", (prefix + "-%",)) or 0
    while True:
        n += 1
        rid = f"{prefix}-{n:03d}"
        if not db.one("SELECT 1 FROM resources WHERE id=?", (rid,)):
            return rid


def create_resource(db: Database, actor: Actor, *, resource_type: str, description: str, unit: str,
                    cost_code: str | None = None, category: str | None = None, id: str | None = None,
                    is_synthetic: bool = False, **extra) -> str:
    approvals.require_author(actor)
    if resource_type not in RESOURCE_TYPES:
        raise ValidationFailed(f"resource_type must be one of {RESOURCE_TYPES}")
    if not db.one("SELECT 1 FROM units WHERE code=?", (unit,)):
        raise ValidationFailed(f"Unknown unit '{unit}'. Use a canonical unit code.", code="UNKNOWN_UNIT")
    if cost_code and not db.one("SELECT 1 FROM cost_codes WHERE code=?", (cost_code,)):
        raise ValidationFailed(f"Unknown cost code '{cost_code}'.")
    rid = id or next_resource_id(db, {"material": "MAT", "labour": "LAB", "plant": "PLT", "equipment": "EQP",
                                      "subcontract": "SUB"}[resource_type] + (f"-{cost_code[0]}" if cost_code and resource_type in ("material", "equipment", "subcontract") else ""))
    if db.one("SELECT 1 FROM resources WHERE id=?", (rid,)):
        raise Conflict(f"Resource {rid} already exists.")
    allowed = {"description_ar", "aliases", "specification", "brand_requirements", "currency",
               "geographic_applicability", "installation_included", "freight_unloading_included", "tax_basis",
               "delivery_basis", "notes"}
    vals = {k: v for k, v in extra.items() if k in allowed}
    db.insert("resources", dict(id=rid, resource_type=resource_type, cost_code=cost_code, category=category,
                                description=description, unit=unit, is_synthetic=int(is_synthetic), is_active=1,
                                created_by=actor.username, created_at=now_iso(), updated_at=now_iso(), **vals))
    audit.log(db, actor, "resource", rid, "create", after={"description": description, "unit": unit})
    return rid


def update_resource(db: Database, actor: Actor, rid: str, **changes) -> None:
    """Edit descriptive master data. Prices are never edited here (rates are versioned records)."""
    approvals.require_author(actor)
    allowed = {"description", "description_ar", "aliases", "specification", "brand_requirements", "category",
               "cost_code", "geographic_applicability", "installation_included", "freight_unloading_included",
               "tax_basis", "delivery_basis", "notes", "is_active"}
    bad = set(changes) - allowed
    if bad:
        raise ValidationFailed(f"Fields not editable here: {sorted(bad)} (unit/type changes require a new resource).")
    before = row_to_dict(get_resource(db, rid))
    db.update("resources", {**changes, "updated_at": now_iso()}, "id=?", (rid,))
    audit.log(db, actor, "resource", rid, "update", before={k: before[k] for k in changes}, after=changes)


def get_resource(db: Database, rid: str):
    r = db.one("SELECT * FROM resources WHERE id=?", (rid,))
    if not r:
        raise NotFound(f"Resource {rid} not found.")
    return r


# ----------------------------------------------------------------------------- rates
def _next_version(db: Database, rid: str) -> int:
    return (db.scalar("SELECT MAX(version) FROM resource_rates WHERE resource_id=?", (rid,)) or 0) + 1


def create_missing_placeholder(db: Database, rid: str, *, unit: str, created_by: str = "system") -> int:
    return db.insert("resource_rates", dict(
        resource_id=rid, version=_next_version(db, rid), rate_type=RateType.MISSING.value, unit_price=None,
        currency="SAR", unit=unit, region="KSA-ALL", confidence="Unverified", status=Status.DRAFT.value,
        notes="No verified rate on record. Raise a procurement requirement / RFQ.", created_by=created_by,
        created_at=now_iso()))


def propose_rate(db: Database, actor: Actor, resource_id: str, *, unit_price: Decimal | str | None, rate_type: str,
                 currency: str = "SAR", unit: str | None = None, region: str = "KSA-ALL", supplier_id: str | None = None,
                 quotation_line_id: int | None = None, source_id: str | None = None, evidence: str | None = None,
                 price_date: str | None = None, valid_until: str | None = None, tax_basis: str | None = None,
                 delivery_basis: str | None = None, installation_included: str | None = None,
                 freight_included: str | None = None, confidence: str = "Unverified", project_id: str | None = None,
                 components: dict | None = None, notes: str | None = None, is_synthetic: bool = False,
                 submit: bool = False) -> int:
    """Create a new rate version in Draft (or Pending Review when submit=True). Never approves anything."""
    approvals.require_author(actor)
    res = get_resource(db, resource_id)
    if rate_type not in RATE_TYPE_VALUES:
        raise ValidationFailed(f"rate_type must be one of {RATE_TYPE_VALUES}")
    if rate_type == RateType.SYNTHETIC.value:
        is_synthetic = True
    if is_synthetic and rate_type not in (RateType.SYNTHETIC.value, RateType.MISSING.value):
        raise ValidationFailed("Synthetic data must use rate type 'Synthetic Demonstration Rate'.")
    if components and unit_price in (None, ""):
        unit_price = _price_from_components(res["resource_type"], components)
    price = D_opt(unit_price)
    if rate_type == RateType.MISSING.value:
        price = None
    elif price is None:
        raise ValidationFailed("unit_price is required (use rate type 'Missing Rate' to record an absent price).")
    elif price < 0:
        raise ValidationFailed("unit_price cannot be negative.")
    if not db.one("SELECT 1 FROM regions WHERE code=?", (region,)):
        raise ValidationFailed(f"Unknown region '{region}'.")
    u = unit or res["unit"]
    if u != res["unit"]:
        from ..core.units import registry
        if not registry(db).can_convert(u, res["unit"]):
            raise ValidationFailed(f"Rate unit '{u}' is not convertible to resource unit '{res['unit']}'.")
    v = _next_version(db, resource_id)
    rid = db.insert("resource_rates", dict(
        resource_id=resource_id, version=v, rate_type=rate_type, unit_price=price, currency=currency, unit=u,
        region=region, supplier_id=supplier_id, quotation_line_id=quotation_line_id, source_id=source_id,
        evidence=evidence, price_date=price_date, valid_until=valid_until, tax_basis=tax_basis,
        delivery_basis=delivery_basis, installation_included=installation_included, freight_included=freight_included,
        confidence=confidence, status=Status.PENDING.value if submit else Status.DRAFT.value, project_id=project_id,
        is_synthetic=int(is_synthetic), components_json=components, notes=notes, created_by=actor.username,
        created_at=now_iso()))
    audit.log(db, actor, "rate", rid, "propose", after={"resource": resource_id, "price": to_text(price),
                                                        "type": rate_type, "version": v}, project_id=project_id)
    return rid


def _price_from_components(resource_type: str, comps: dict) -> Decimal:
    if resource_type == "labour":
        return rate_build.build_labour(comps).hourly_cost
    if resource_type == "plant":
        return rate_build.build_plant(comps).hourly_cost_full
    raise ValidationFailed("Component build-ups are only supported for labour and plant resources.")


def get_rate(db: Database, rate_id: int) -> dict:
    r = db.one("SELECT * FROM resource_rates WHERE id=?", (rate_id,))
    if not r:
        raise NotFound(f"Rate {rate_id} not found.")
    return dict(r)


def update_draft_rate(db: Database, actor: Actor, rate_id: int, **changes) -> None:
    """Only Draft / Pending / Rejected rates are editable. Approved rates are immutable: use revise_rate()."""
    approvals.require_author(actor)
    r = get_rate(db, rate_id)
    if r["status"] in FINAL_STATES:
        raise ImmutableRecord(f"Rate {rate_id} is {r['status']} and immutable. Create a new version with revise_rate().")
    allowed = {"unit_price", "currency", "region", "supplier_id", "source_id", "evidence", "price_date", "valid_until",
               "tax_basis", "delivery_basis", "installation_included", "freight_included", "confidence", "notes",
               "quotation_line_id"}
    bad = set(changes) - allowed
    if bad:
        raise ValidationFailed(f"Fields not editable: {sorted(bad)}")
    if "unit_price" in changes and D_opt(changes["unit_price"]) is None:
        raise ValidationFailed("unit_price must be numeric.")
    db.update("resource_rates", {**changes, "status": Status.DRAFT.value}, "id=?", (rate_id,))
    audit.log(db, actor, "rate", rate_id, "edit_draft", before={k: r[k] for k in changes}, after=changes)


def submit_rate(db: Database, actor: Actor, rate_id: int) -> None:
    approvals.require_author(actor)
    r = get_rate(db, rate_id)
    if r["status"] not in (Status.DRAFT.value, Status.REJECTED.value):
        raise Conflict(f"Only Draft/Rejected rates can be submitted (current: {r['status']}).")
    if r["rate_type"] == RateType.MISSING.value:
        raise ValidationFailed("A 'Missing Rate' placeholder cannot be submitted; propose a real rate.")
    db.update("resource_rates", {"status": Status.PENDING.value}, "id=?", (rate_id,))
    audit.log(db, actor, "rate", rate_id, "submit", before=r["status"], after=Status.PENDING.value)


def revise_rate(db: Database, actor: Actor, rate_id: int, **changes) -> int:
    """Create a new Draft version copying an existing (possibly approved) rate. The original is untouched."""
    approvals.require_author(actor)
    r = get_rate(db, rate_id)
    base = {k: r[k] for k in ("rate_type", "unit_price", "currency", "unit", "region", "supplier_id", "source_id",
                              "evidence", "price_date", "valid_until", "tax_basis", "delivery_basis",
                              "installation_included", "freight_included", "confidence", "project_id", "notes")}
    base.update(changes)
    return propose_rate(db, actor, r["resource_id"], components=jload(r["components_json"]),
                        is_synthetic=bool(r["is_synthetic"]), **base)


def _validate_for_approval(r: dict) -> None:
    if r["rate_type"] == RateType.MISSING.value or D_opt(r["unit_price"]) is None:
        raise ValidationFailed("A rate without a price cannot be approved.", code="NO_PRICE")
    if r["rate_type"] in NON_PRICE_RATE_TYPES:
        raise ValidationFailed("Official indices/benchmarks cannot be approved as unit prices.", code="NON_PRICE_TYPE")
    if not r["price_date"] or not parse_date(r["price_date"]):
        raise ValidationFailed("A valid price_date is required before approval.", code="PRICE_DATE_REQUIRED")
    if r["valid_until"] and parse_date(r["valid_until"]) and parse_date(r["valid_until"]) < parse_date(r["price_date"]):
        raise ValidationFailed("valid_until precedes price_date.")
    if r["rate_type"] in (RateType.VERIFIED_SUPPLIER_QUOTE.value,) and not (r["quotation_line_id"] or r["evidence"]):
        raise ValidationFailed("Verified Supplier Quote requires the originating quotation line or evidence.",
                               code="EVIDENCE_REQUIRED")
    if r["rate_type"] in (RateType.PUBLISHED_MARKET_PRICE.value, RateType.HISTORICAL_ACTUAL.value,
                          RateType.APPROVED_INTERNAL_BENCHMARK.value) and not (r["source_id"] or r["evidence"]):
        raise ValidationFailed("Source or evidence is required before approval.", code="EVIDENCE_REQUIRED")


def approve_rate(db: Database, actor: Actor, rate_id: int, *, comments: str | None = None,
                 evidence: str | None = None) -> None:
    r = get_rate(db, rate_id)
    approvals.authorize(actor, Entity.RATE.value, "approve", created_by=r["created_by"])
    if r["status"] != Status.PENDING.value:
        raise Conflict(f"Rate must be 'Pending Review' to approve (current: {r['status']}).", code="NOT_PENDING")
    _validate_for_approval(r)
    if r["project_id"]:
        raise ValidationFailed("Project-scoped rates may only be approved provisionally (approve_provisional).")
    with db.tx():
        prev = db.all("SELECT id FROM resource_rates WHERE resource_id=? AND status='Approved' AND region=? "
                      "AND project_id IS NULL AND id<>?", (r["resource_id"], r["region"], rate_id))
        for p in prev:
            db.update("resource_rates", {"status": Status.SUPERSEDED.value, "superseded_by": rate_id}, "id=?", (p["id"],))
            audit.log(db, actor, "rate", p["id"], "superseded", after={"by": rate_id})
        db.update("resource_rates", {"status": Status.APPROVED.value, "approved_by": actor.username,
                                     "approved_at": now_iso()}, "id=?", (rate_id,))
        approvals.record(db, actor, Entity.RATE.value, rate_id, "approve", version=r["version"],
                         previous_value=[p["id"] for p in prev] or None,
                         approved_value={"unit_price": r["unit_price"], "currency": r["currency"], "unit": r["unit"]},
                         evidence=evidence or r["evidence"], comments=comments)


def approve_rate_provisional(db: Database, actor: Actor, rate_id: int, project_id: str, *, comments: str | None = None
                             ) -> None:
    """Project-scoped provisional approval: visible everywhere as 'Provisional — Approved for This Estimate'."""
    r = get_rate(db, rate_id)
    approvals.authorize(actor, Entity.RATE.value, "approve_provisional", created_by=r["created_by"])
    if not comments:
        raise ValidationFailed("A reason is required for provisional approval.", code="REASON_REQUIRED")
    if r["status"] not in (Status.PENDING.value, Status.DRAFT.value):
        raise Conflict(f"Cannot provisionally approve a rate in status {r['status']}.")
    if D_opt(r["unit_price"]) is None or r["rate_type"] in NON_PRICE_RATE_TYPES:
        raise ValidationFailed("Only priced, non-index rates may be provisionally approved.")
    if r["project_id"] not in (None, project_id):
        raise ValidationFailed("Rate belongs to a different project.")
    with db.tx():
        if r["project_id"] is None:
            # keep global rate untouched; create a project-scoped copy
            new_id = db.insert("resource_rates", {**{k: r[k] for k in (
                "resource_id", "rate_type", "unit_price", "currency", "unit", "region", "supplier_id", "quotation_line_id",
                "source_id", "evidence", "price_date", "valid_until", "tax_basis", "delivery_basis",
                "installation_included", "freight_included", "confidence", "is_synthetic", "components_json")},
                "version": _next_version(db, r["resource_id"]), "project_id": project_id,
                "status": Status.PROVISIONAL.value, "notes": f"Provisional copy of rate {rate_id}: {comments}",
                "created_by": actor.username, "created_at": now_iso(), "approved_by": actor.username,
                "approved_at": now_iso()})
            target = new_id
        else:
            db.update("resource_rates", {"status": Status.PROVISIONAL.value, "approved_by": actor.username,
                                         "approved_at": now_iso()}, "id=?", (rate_id,))
            target = rate_id
        approvals.record(db, actor, Entity.RATE.value, target, "approve_provisional", project_id=project_id,
                         version=r["version"], approved_value={"unit_price": r["unit_price"], "project": project_id},
                         comments=comments, override_reason=comments)


def reject_rate(db: Database, actor: Actor, rate_id: int, reason: str) -> None:
    r = get_rate(db, rate_id)
    approvals.authorize(actor, Entity.RATE.value, "reject")
    if r["status"] in FINAL_STATES:
        raise ImmutableRecord(f"Rate is {r['status']}; it cannot be rejected. Create a superseding version.")
    db.update("resource_rates", {"status": Status.REJECTED.value}, "id=?", (rate_id,))
    approvals.record(db, actor, Entity.RATE.value, rate_id, "reject", comments=reason, previous_value=r["status"])


def rates_for(db: Database, resource_id: str) -> list[dict]:
    return rows_to_dicts(db.all("SELECT * FROM resource_rates WHERE resource_id=? ORDER BY version", (resource_id,)))


def expire_stale_rates(db: Database, as_of: str | None = None, actor: Actor | str = "system") -> int:
    """Mark approved rates whose valid_until has passed as Expired (record kept; never deleted)."""
    as_of = as_of or today_iso()
    rows = db.all("SELECT id FROM resource_rates WHERE status='Approved' AND valid_until IS NOT NULL AND valid_until < ?",
                  (as_of,))
    for r in rows:
        db.update("resource_rates", {"status": Status.EXPIRED.value}, "id=?", (r["id"],))
        audit.log(db, actor, "rate", r["id"], "expired", after={"as_of": as_of})
    return len(rows)
