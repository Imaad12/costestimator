"""Rate candidates: the review queue between "found a price somewhere" and "an approved global rate".

Lifecycle   Pending Review -> (Needs Verification) -> Approved for Publication -> Published (a *Pending Review* global rate version)
            -> [separate human rate approval via services.rates.approve_rate] -> Approved.   Rejected is terminal.
* The original price/currency/unit are immutable once stored; edits are limited to matching/basis fields and are audited.
* A candidate never touches `resource_rates` until a human has approved it for publication AND a human then publishes it;
  even then the new rate version is only *Pending Review* - it is not eligible for a submission-ready estimate until approved.
* Published rates are VAT-exclusive: tax-inclusive prices are published only in their normalised (approved-tax) form.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from ..approvals import engine as approvals
from ..core.errors import Conflict, NotFound, ValidationFailed
from ..core.money import D_opt
from ..core.timeutil import now_iso, parse_date, today_iso
from ..core.units import registry
from ..database import Database, jload, rows_to_dicts
from ..models.actor import Actor
from ..models.enums import RATE_TYPE_VALUES, Entity, RateType
from ..services import audit, rates
from . import normalise as norm

SOURCE_TYPES = ["Manual dataset", "Supplier website", "Manufacturer website", "Official statistics", "Public tender award",
                "Quotation", "Historical project"]
RATE_TYPE_FOR_SOURCE = {
    "Manual dataset": RateType.PUBLISHED_MARKET_PRICE.value, "Supplier website": RateType.PUBLISHED_MARKET_PRICE.value,
    "Manufacturer website": RateType.PUBLISHED_MARKET_PRICE.value, "Quotation": RateType.VERIFIED_SUPPLIER_QUOTE.value,
    "Historical project": RateType.HISTORICAL_ACTUAL.value, "Public tender award": RateType.HISTORICAL_ACTUAL.value,
}
TERMINAL = ("Rejected", "Published")
VERIFY_FLAGS = {"VAT_UNKNOWN", "VAT_STATEMENT_CONFLICT", "GEOGRAPHY_UNKNOWN", "UNIT_UNKNOWN", "CURRENCY_UNKNOWN", "NO_PRICE", "STALE",
                "STALE_EXPIRED", "TEXT_PATTERN_ONLY", "LOW_CONFIDENCE_EXTRACTION", "PROMOTIONAL", "PRICE_RANGE", "AWARD_NOT_MARKET_QUOTE",
                "FOREIGN_CURRENCY", "RESOURCE_UNMATCHED", "NORMALISATION_INCOMPLETE", "DELIVERY_UNKNOWN", "CONTRADICTORY"}
EDITABLE = {"resource_id", "unit", "tax_basis", "delivery_basis", "installation_included", "geography", "specification", "description",
            "valid_until", "effective_date", "confidence", "price_kind"}


def _flags(row: dict) -> list[str]:
    return jload(row.get("flags_json"), []) or []


def _tokens(s: str | None) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]{3,}", (s or "").lower())}


def suggest_resource(db: Database, text: str, limit: int = 3) -> list[dict]:
    """Deterministic token-overlap suggestion (no AI). A suggestion is never applied automatically."""
    toks = _tokens(text)
    if not toks:
        return []
    scored = []
    for r in db.all("SELECT id, description, unit, resource_type FROM resources WHERE is_active=1"):
        common = toks & _tokens(r["description"])
        if len(common) >= 2:
            scored.append((len(common) / max(len(toks | _tokens(r["description"])), 1), dict(r)))
    scored.sort(key=lambda x: -x[0])
    return [{**r, "score": round(s, 2)} for s, r in scored[:limit]]


# ------------------------------------------------------------------------------------------------ validation
def validate(db: Database, d: dict) -> tuple[list[str], list[str]]:
    """-> (errors, flags). Errors reject the row; flags send it to the queue with a reason."""
    errs: list[str] = []
    flags = list(d.get("flags") or [])
    if not (d.get("source_url") or d.get("source_ref")):
        errs.append("exact source URL or uploaded-file reference is required")
    if d.get("source_type") not in SOURCE_TYPES:
        errs.append(f"source_type must be one of {SOURCE_TYPES}")
    if not d.get("retrieved_at"):
        errs.append("retrieval date is required")
    elif not parse_date(str(d["retrieved_at"])[:10]):
        errs.append(f"retrieval date '{d['retrieved_at']}' is not a valid date")
    price = D_opt(d.get("original_price"))
    if d.get("original_price") not in (None, "") and price is None:
        errs.append(f"price '{d.get('original_price')}' is not numeric")
    elif price is not None and price <= 0:
        errs.append("price must be greater than zero")
    if price is None and d.get("price_kind") not in ("Specification only", "Quote required"):
        errs.append("a price is required unless the item is 'Specification only' or 'Quote required'")
    if price is not None:
        if not d.get("currency"):
            errs.append("currency is required with a price")
        elif not re.fullmatch(r"[A-Za-z]{3}", d["currency"]):
            errs.append(f"currency '{d['currency']}' is not a 3-letter code")
        if not d.get("unit") and "UNIT_UNKNOWN" not in flags:
            flags.append("UNIT_UNKNOWN")
        elif d.get("unit") and registry(db).resolve(d["unit"]).status != "ok":
            flags.append("UNIT_UNKNOWN")
    for k in ("effective_date", "valid_until", "source_published_at"):
        if d.get(k) and not parse_date(str(d[k])[:10]):
            errs.append(f"{k} '{d[k]}' is not a valid date")
    if d.get("resource_id") and not db.one("SELECT 1 FROM resources WHERE id=?", (d["resource_id"],)):
        errs.append(f"resource '{d['resource_id']}' does not exist (create it first; resources are never auto-created)")
    if d.get("source_type") == "Official statistics":
        errs.append("official statistics/indices are not unit prices and cannot be rate candidates (use the index importer)")
    return errs, flags


def _row_hash(d: dict) -> str:
    import hashlib
    key = "|".join(str(d.get(k) or "") for k in ("source_url", "source_ref", "description", "original_price", "original_currency", "original_unit",
                                                  "effective_date", "tax_basis"))
    return hashlib.sha256(key.encode()).hexdigest()[:24]


def create_candidate(db: Database, actor: Actor | str, d: dict, *, manifest_id: int | None = None) -> int:
    """Validate + store one candidate (raises ValidationFailed listing every error). Computes normalisation, flags and queue."""
    if isinstance(actor, Actor):
        approvals.require_author(actor)
    d = dict(d)
    if d.get("unit"):
        ur = registry(db).resolve(str(d["unit"]))
        if ur.status == "ok":
            d["unit"] = ur.code                      # canonical code; unresolvable text is kept as-is and flagged UNIT_UNKNOWN
    d.setdefault("original_currency", d.get("currency"))
    d.setdefault("original_unit", d.get("unit"))
    d["currency"] = (d.get("currency") or "").upper() or None
    d["original_currency"] = d["currency"]
    errs, flags = validate(db, d)
    if errs:
        raise ValidationFailed("Candidate rejected: " + "; ".join(errs), code="CANDIDATE_INVALID", details=errs)
    if not d.get("resource_id"):
        text = f"{d.get('description') or ''} {d.get('specification') or ''}"
        sug = suggest_resource(db, text)
        d["suggested_resource_id"] = sug[0]["id"] if sug else None
        flags.append("RESOURCE_UNMATCHED")
    rh = _row_hash(d)
    dup = db.one("SELECT candidate_ref FROM rate_candidates WHERE row_hash=? AND status<>'Rejected'", (rh,))
    if dup:
        raise Conflict(f"Duplicate of {dup['candidate_ref']} (same source, item, price, date and basis).", code="DUPLICATE_CANDIDATE")
    uid = f"TMP-{rh}-{now_iso()}"
    cid = db.insert("rate_candidates", dict(
        candidate_ref=uid, resource_id=d.get("resource_id"), suggested_resource_id=d.get("suggested_resource_id"), description=d.get("description"),
        specification=d.get("specification"), source_type=d["source_type"], source_name=d.get("source_name"), source_id=d.get("source_id"),
        source_url=d.get("source_url") or d.get("source_ref"), retrieved_at=d["retrieved_at"], source_published_at=d.get("source_published_at"),
        effective_date=d.get("effective_date") or str(d["retrieved_at"])[:10], valid_until=d.get("valid_until"),
        geography=d.get("geography") or "Unknown", currency=d.get("currency"), unit=d.get("unit"),
        original_price=None if D_opt(d.get("original_price")) is None else str(d["original_price"]).strip(), original_currency=d.get("currency"),
        original_unit=d.get("unit"), tax_basis=d.get("tax_basis") or "Unknown", delivery_basis=d.get("delivery_basis") or "Unknown",
        installation_included=d.get("installation_included") or "Unknown", price_kind=d.get("price_kind") or "Unknown",
        confidence=d.get("confidence") or "Unverified", extraction_method=d.get("extraction_method") or "Manual entry",
        evidence_snippet=(d.get("evidence_snippet") or "")[:1000] or None, flags_json=sorted(set(flags)), manifest_id=manifest_id,
        row_hash=rh, created_by=getattr(actor, "username", str(actor)), created_at=now_iso()))
    db.update("rate_candidates", {"candidate_ref": f"RC-{cid:06d}"}, "id=?", (cid,))
    recompute(db, cid)
    audit.log(db, actor, "rate_candidate", f"RC-{cid:06d}", "create", after={"resource": d.get("resource_id"), "source": d.get("source_name"),
                                                                           "price": d.get("original_price")})
    return cid


def get(db: Database, cid: int) -> dict:
    r = db.one("SELECT * FROM rate_candidates WHERE id=? OR candidate_ref=?", (cid if str(cid).isdigit() else -1, str(cid)))
    if not r:
        raise NotFound(f"Rate candidate {cid} not found.")
    d = dict(r)
    d["flags"] = _flags(d)
    d["normalisation"] = jload(d.get("normalisation_json"), None)
    return d


def recompute(db: Database, cid: int) -> dict:
    """Refresh normalisation, derived flags and queue. Original price fields are never touched."""
    c = get(db, cid)
    flags = {f for f in c["flags"] if f not in ("NORMALISATION_INCOMPLETE", "RESOURCE_UNMATCHED", "STALE_EXPIRED", "VAT_UNKNOWN", "DELIVERY_UNKNOWN")}
    if D_opt(c["original_price"]) is not None:
        if (c["tax_basis"] or "Unknown") not in ("Included", "Excluded"):
            flags.add("VAT_UNKNOWN")
        if (c["delivery_basis"] or "Unknown") == "Unknown":
            flags.add("DELIVERY_UNKNOWN")
    res = db.one("SELECT unit FROM resources WHERE id=?", (c["resource_id"],)) if c["resource_id"] else None
    if not c["resource_id"]:
        flags.add("RESOURCE_UNMATCHED")
    upd: dict[str, Any] = {}
    if c["original_price"] is not None:
        n = norm.normalise(db, price=c["original_price"], currency=c["original_currency"], unit=c["original_unit"],
                           target_unit=res["unit"] if res else c["original_unit"], tax_basis=c["tax_basis"], price_date=c["effective_date"])
        upd.update(normalised_price=None if n.price is None else str(n.price), normalisation_method=n.method, normalisation_json=n.as_json())
        if not n.complete:
            flags.add("NORMALISATION_INCOMPLETE")
    if c["valid_until"] and parse_date(c["valid_until"]) and parse_date(c["valid_until"]) < parse_date(today_iso()):
        flags.add("STALE_EXPIRED")
    upd["flags_json"] = sorted(flags)
    c.update(upd)
    c["flags"] = sorted(flags)
    upd["queue"] = classify_queue(db, c)
    db.update("rate_candidates", upd, "id=?", (c["id"],))
    return get(db, c["id"])


def classify_queue(db: Database, c: dict) -> str:
    flags = set(c["flags"])
    rid = c.get("resource_id") or c.get("suggested_resource_id")
    conflicting = False
    if rid and D_opt(c.get("original_price")) is not None:
        others = db.all("SELECT id, original_price, original_currency, original_unit FROM rate_candidates WHERE id<>? AND status NOT IN ('Rejected','Published') "
                        "AND COALESCE(resource_id, suggested_resource_id)=?", (c["id"], rid))
        for o in others:
            if (o["original_currency"], o["original_unit"]) == (c["original_currency"], c["original_unit"]) and D_opt(o["original_price"]) is not None \
                    and D_opt(o["original_price"]) != D_opt(c["original_price"]):
                conflicting = True
    if conflicting or "CONTRADICTORY" in flags:
        return "Conflicting"
    if "STALE_EXPIRED" in flags:
        return "Expired"
    if c.get("resource_id"):
        cur = db.one("SELECT unit_price, valid_until, status FROM resource_rates WHERE resource_id=? AND status IN ('Approved','Expired') "
                     "AND project_id IS NULL AND unit_price IS NOT NULL ORDER BY version DESC LIMIT 1", (c["resource_id"],))
        if cur and cur["status"] == "Expired":
            return "Expired"
    if (flags & VERIFY_FLAGS) - {"CONTRADICTORY"}:
        return "Requires Verification"
    if c.get("resource_id"):
        cur = db.one("SELECT unit_price FROM resource_rates WHERE resource_id=? AND status='Approved' AND project_id IS NULL AND unit_price IS NOT NULL "
                     "ORDER BY version DESC LIMIT 1", (c["resource_id"],))
        if cur:
            return "Updated"
    return "New"


def edit(db: Database, actor: Actor, cid: int, **changes) -> dict:
    approvals.require_author(actor)
    c = get(db, cid)
    if c["status"] in TERMINAL:
        raise Conflict(f"{c['candidate_ref']} is {c['status']}; it can no longer be edited.", code="CANDIDATE_FINAL")
    bad = set(changes) - EDITABLE
    if bad:
        raise ValidationFailed(f"Not editable: {sorted(bad)}. The original price, currency, source and retrieval details are immutable.",
                               code="IMMUTABLE_FIELDS")
    if "resource_id" in changes and changes["resource_id"] and not db.one("SELECT 1 FROM resources WHERE id=?", (changes["resource_id"],)):
        raise ValidationFailed(f"Resource {changes['resource_id']} does not exist.")
    db.update("rate_candidates", {**changes, "status": "Pending Review" if c["status"] == "Approved for Publication" else c["status"]}, "id=?", (c["id"],))
    audit.log(db, actor, "rate_candidate", c["candidate_ref"], "edit", before={k: c.get(k) for k in changes}, after=changes)
    return recompute(db, c["id"])


def publishable_price(db: Database, c: dict) -> tuple[Decimal | None, str, list[str]]:
    """(price in the form that may be published, text describing it, blocking reasons).  Published rates are VAT-exclusive."""
    reasons: list[str] = []
    if D_opt(c["original_price"]) is None:
        return None, "", [f"{c['price_kind']} item has no price - it can inform an RFQ but cannot become a rate"]
    if not c.get("resource_id"):
        reasons.append("no resource matched (a human must choose the resource)")
    if c["tax_basis"] not in ("Included", "Excluded"):
        reasons.append("VAT treatment must be confirmed as Included or Excluded")
    if c["price_kind"] in ("Promotional", "Unknown"):
        reasons.append(f"price kind is '{c['price_kind']}' - confirm it is the normal (non-promotional) price")
    if c["price_kind"] in ("Quote required", "Specification only"):
        reasons.append(f"price kind is '{c['price_kind']}'")
    if "STALE_EXPIRED" in c["flags"]:
        reasons.append("the source's own validity date has passed")
    if c["tax_basis"] == "Excluded" and c["original_currency"] == "SAR" and c["original_unit"] == (db.scalar("SELECT unit FROM resources WHERE id=?", (c["resource_id"],)) if c["resource_id"] else None):
        return D_opt(c["original_price"]), "original price (SAR, resource unit, VAT-exclusive)", reasons
    n = c.get("normalisation") or {}
    if not n.get("complete"):
        reasons += [f"normalisation incomplete: {u}" for u in n.get("unresolved", ["not computed"])]
        return None, "", reasons
    return D_opt(n["price"]), f"normalised: {c['normalisation_method']}", reasons


def review(db: Database, actor: Actor, cid: int, decision: str, comments: str = "") -> dict:
    """decision: approve (= approved for publication), reject, needs_verification.  Human only; never automatic."""
    c = get(db, cid)
    if c["status"] in TERMINAL:
        raise Conflict(f"{c['candidate_ref']} is already {c['status']}.", code="CANDIDATE_FINAL")
    if decision not in ("approve", "reject", "needs_verification"):
        raise ValidationFailed("decision must be approve, reject or needs_verification.")
    if decision == "needs_verification":
        approvals.authorize(actor, Entity.RATE_CANDIDATE.value, "request_changes")
    else:
        approvals.authorize(actor, Entity.RATE_CANDIDATE.value, decision, created_by=c["created_by"])
    if decision != "approve" and not comments.strip():
        raise ValidationFailed("A comment is required to reject or request verification.", code="COMMENT_REQUIRED")
    if decision == "approve":
        price, how, reasons = publishable_price(db, c)
        if price is None or reasons:
            raise ValidationFailed("Cannot approve for publication: " + "; ".join(reasons or ["no usable price"]), code="NOT_PUBLISHABLE", details=reasons)
        status = "Approved for Publication"
    else:
        status = "Rejected" if decision == "reject" else "Needs Verification"
    db.update("rate_candidates", {"status": status, "reviewer": actor.username, "reviewed_at": now_iso(), "review_comments": comments or None}, "id=?", (c["id"],))
    approvals.record(db, actor, Entity.RATE_CANDIDATE.value, c["candidate_ref"], decision, previous_value=c["status"],
                     approved_value={"status": status, "original": f"{c['original_price']} {c['original_currency']}/{c['original_unit']}"},
                     evidence=c["source_url"], comments=comments or None)
    return get(db, c["id"])


def publish(db: Database, actor: Actor, cid: int) -> int:
    """Create the new global rate VERSION (status Pending Review) from an Approved-for-Publication candidate. Old versions stay."""
    approvals.require_author(actor)
    c = get(db, cid)
    if c["status"] != "Approved for Publication":
        raise Conflict(f"{c['candidate_ref']} is '{c['status']}'; only 'Approved for Publication' candidates can be published.", code="NOT_APPROVED_FOR_PUBLICATION")
    price, how, reasons = publishable_price(db, c)
    if price is None or reasons:
        raise ValidationFailed("Cannot publish: " + "; ".join(reasons or ["no usable price"]), code="NOT_PUBLISHABLE", details=reasons)
    res = db.one("SELECT unit FROM resources WHERE id=?", (c["resource_id"],))
    unit = res["unit"] if how.startswith("normalised") else c["original_unit"]
    currency = "SAR" if how.startswith("normalised") else c["original_currency"]
    evidence = (f"Candidate {c['candidate_ref']} [{c['source_type']}] {c['source_name'] or ''} {c['source_url']} retrieved {c['retrieved_at'][:10]}; "
                f"original {c['original_price']} {c['original_currency']}/{c['original_unit']} ({c['price_kind']}; VAT {c['tax_basis']}; {c['delivery_basis']}); "
                f"published as {price} {currency}/{unit} - {how}. Reviewer {c['reviewer']}: {c['review_comments'] or 'approved for publication'}")
    rid = rates.propose_rate(
        db, actor, c["resource_id"], unit_price=price, rate_type=RATE_TYPE_FOR_SOURCE.get(c["source_type"], RateType.PUBLISHED_MARKET_PRICE.value),
        currency=currency, unit=unit, region="KSA-ALL", source_id=c["source_id"], evidence=evidence, price_date=c["effective_date"],
        valid_until=c["valid_until"], tax_basis="Excluded", delivery_basis=c["delivery_basis"], installation_included=c["installation_included"],
        confidence=c["confidence"] if c["confidence"] in ("High", "Medium", "Low", "Unverified") else "Unverified", submit=True)
    db.update("rate_candidates", {"status": "Published", "published_rate_id": rid, "published_by": actor.username, "published_at": now_iso()}, "id=?", (c["id"],))
    audit.log(db, actor, "rate_candidate", c["candidate_ref"], "publish", after={"rate_id": rid, "price": str(price), "note": "Pending Review - needs rate approval"})
    return rid


# ------------------------------------------------------------------------------------------------ queue views
def list_queue(db: Database, *, queue: str | None = None, status: str | None = None, open_only: bool = True, limit: int = 500) -> list[dict]:
    sql, params = "SELECT * FROM rate_candidates WHERE 1=1", []
    if queue:
        sql += " AND queue=?"; params.append(queue)
    if status:
        sql += " AND status=?"; params.append(status)
    elif open_only:
        sql += " AND status NOT IN ('Rejected','Published')"
    rows = rows_to_dicts(db.all(sql + " ORDER BY id DESC LIMIT ?", params + [limit]))
    for r in rows:
        r["flags"] = _flags(r)
    return rows


def queue_counts(db: Database) -> dict:
    out = {"by_queue": {}, "by_status": {}}
    for r in db.all("SELECT queue, COUNT(*) n FROM rate_candidates WHERE status NOT IN ('Rejected','Published') GROUP BY queue"):
        out["by_queue"][r["queue"]] = r["n"]
    for r in db.all("SELECT status, COUNT(*) n FROM rate_candidates GROUP BY status"):
        out["by_status"][r["status"]] = r["n"]
    out["expired_rates"] = db.scalar("SELECT COUNT(*) FROM resource_rates WHERE status='Expired'") or 0
    out["rates_pending_approval"] = db.scalar("SELECT COUNT(*) FROM resource_rates WHERE status='Pending Review' AND project_id IS NULL AND unit_price IS NOT NULL") or 0
    return out
