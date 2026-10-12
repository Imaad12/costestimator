"""Detect procurement requirements from the (strict) estimate: missing / expired / unapproved / low-confidence rates."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from ..approvals import engine as approvals
from ..core.money import ZERO, to_text
from ..core.timeutil import now_iso
from ..database import Database, rows_to_dicts
from ..estimators.estimate import compute_estimate
from ..models.actor import Actor
from ..services import audit, projects

REASONS = {
    "MISSING_RATE": "Missing rate - no verified price on record",
    "EXPIRED_RATE": "Rate/quotation expired",
    "UNAPPROVED_RATE": "Rate exists but is not approved",
    "RATE_REGION_MISMATCH": "Rate is for a different region",
    "INDEX_ONLY_NO_PRICE": "Only an official index exists - a quotation is needed",
    "RATE_NOT_YET_EFFECTIVE": "Rate not yet effective",
    "RATE_WARNING": "Low-confidence or aged rate - re-confirm",
}


def ensure_package(db: Database, project_id: str, trade_code: str, actor: str) -> str:
    div = (trade_code or "X")[0]
    pkg = f"PKG-{project_id}-{div}"
    if not db.one("SELECT 1 FROM procurement_packages WHERE id=?", (pkg,)):
        name = db.scalar("SELECT name FROM cost_codes WHERE code=?", (div,)) or "General"
        db.insert("procurement_packages", dict(id=pkg, project_id=project_id, name=f"{name} package", trade=div,
                                               status="Open", created_by=actor, created_at=now_iso()))
    return pkg


def detect_needs(db: Database, actor: Actor, project_id: str) -> dict:
    """Create/refresh procurement items. Never invents prices; indicative exposure is shown only when an unapproved rate exists."""
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    est = compute_estimate(db, project_id)
    resources = est.inputs.resources
    agg: dict[tuple[str, str], dict] = {}
    lines_by_res: dict[str, list] = defaultdict(list)
    for l in est.direct.lines:
        if l.resource_id:
            lines_by_res[l.resource_id].append(l)
    for e in est.direct.exceptions:
        if e.code not in REASONS or not e.resource_id:
            continue
        key = (e.resource_id, e.code)
        a = agg.setdefault(key, dict(items=set(), exposure=ZERO, exposure_known=False))
        if e.item_key:
            a["items"].add(e.item_key)
    created = updated = 0
    seen_ids: list[str] = []
    for (rid, code), a in agg.items():
        res = resources.get(rid) or dict(db.one("SELECT * FROM resources WHERE id=?", (rid,)))
        lines = [l for l in lines_by_res.get(rid, []) if l.amount is None]
        qty = sum((l.quantity for l in lines if l.quantity is not None), ZERO)
        exposure = sum((l.indicative_amount for l in lines if l.indicative_amount is not None), ZERO)
        known = any(l.indicative_amount is not None for l in lines)
        cc = res.get("cost_code") or ""
        pkg = ensure_package(db, project_id, cc, actor.username)
        item_keys = sorted(a["items"])
        existing = db.one("SELECT * FROM procurement_items WHERE project_id=? AND resource_id=? AND reason_code=?",
                          (project_id, rid, code))
        vals = dict(package_id=pkg, trade=cc, item_id=rid, boq_item_key=",".join(item_keys)[:500], description=res["description"],
                    specification=res.get("specification"), quantity=to_text(qty), unit=res["unit"],
                    delivery_location=est.project.get("location"), reason=REASONS[code],
                    estimated_exposure=to_text(exposure) if known else None,
                    priority="High" if exposure and exposure > 100000 else ("Medium" if known else "Unknown exposure"))
        if existing:
            db.update("procurement_items", {**vals, "closed": 0}, "id=?", (existing["id"],))
            updated += 1
            seen_ids.append(existing["id"])
        else:
            n = (db.scalar("SELECT COUNT(*) FROM procurement_items WHERE project_id=?", (project_id,)) or 0) + 1
            pid = f"PRC-{project_id}-{n:04d}"
            db.insert("procurement_items", dict(id=pid, project_id=project_id, resource_id=rid, reason_code=code,
                                                created_by=actor.username, created_at=now_iso(), **vals))
            created += 1
            seen_ids.append(pid)
    # close items no longer needed (resolved by an approved rate)
    closed = 0
    for r in db.all("SELECT id FROM procurement_items WHERE project_id=? AND closed=0", (project_id,)):
        if r["id"] not in seen_ids:
            db.update("procurement_items", {"closed": 1}, "id=?", (r["id"],))
            closed += 1
    audit.log(db, actor, "procurement", project_id, "detect_needs", after=dict(created=created, updated=updated, closed=closed),
              project_id=project_id)
    return dict(created=created, updated=updated, closed=closed, open=len(seen_ids))


def register(db: Database, project_id: str, include_closed: bool = False) -> list[dict]:
    sql = "SELECT * FROM procurement_items WHERE project_id=?" + ("" if include_closed else " AND closed=0") + " ORDER BY package_id, id"
    return rows_to_dicts(db.all(sql, (project_id,)))


def update_item(db: Database, actor: Actor, item_id: str, **changes) -> None:
    approvals.require_author(actor)
    allowed = {"delivery_location", "required_date", "preferred_suppliers", "response_deadline", "specification", "quantity", "lead_time_days"}
    bad = set(changes) - allowed
    if bad:
        raise ValueError(f"Not editable: {sorted(bad)}")
    db.update("procurement_items", changes, "id=?", (item_id,))
    audit.log(db, actor, "procurement_item", item_id, "update", after=changes)
