"""Quote leveling: like-for-like comparison. Quoted prices and normalised comparison values are always shown separately.

Normalised value (SAR, pre-tax) per line = required qty x unit rate x (1 - discount) x FX / tax divisor,
plus APPROVED normalisation adjustments only. Pending adjustments are listed but never applied.
The engine never selects a supplier: `suggested_lowest_like_for_like` is advisory and requires human approval.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..approvals import engine as approvals
from ..core.errors import NotFound, ValidationFailed
from ..core.money import ONE, ZERO, D, D_opt, pct, quantize, to_text
from ..core.timeutil import now_iso, parse_date, today
from ..core.units import registry
from ..database import Database, rows_to_dicts
from ..models.actor import Actor
from ..services import audit
from ..ai.service import spec_diff
from .quotes import get_quotation, validity


def _fx(db: Database, ccy: str, to_ccy: str, as_of: date) -> Decimal | None:
    if ccy == to_ccy:
        return ONE
    best = None
    for f in db.all("SELECT * FROM fx_rates WHERE from_ccy=? AND to_ccy=? AND status='Approved'", (ccy, to_ccy)):
        rd, vu = parse_date(f["rate_date"]), parse_date(f["valid_until"])
        if rd and rd <= as_of and (not vu or vu >= as_of) and (best is None or rd > parse_date(best["rate_date"])):
            best = f
    return D(best["rate"]) if best else None


def add_adjustment(db: Database, actor: Actor, quotation_id: str, adj_type: str, amount, basis: str, description: str = "") -> int:
    """Propose a normalisation adjustment (e.g. add missing delivery). Applied only after approval."""
    approvals.require_author(actor)
    q = get_quotation(db, quotation_id)
    if D_opt(amount) is None:
        raise ValidationFailed("Adjustment amount must be numeric (SAR, pre-tax).")
    if not basis or not basis.strip():
        raise ValidationFailed("An adjustment needs an explicit basis.", code="BASIS_REQUIRED")
    aid = db.insert("quote_adjustments", dict(quotation_id=quotation_id, package_id=q["package_id"], adj_type=adj_type,
                                              description=description, amount=to_text(D(amount)), basis=basis,
                                              status="Pending Review", created_by=actor.username, created_at=now_iso()))
    audit.log(db, actor, "quote_adjustment", aid, "propose", after={"quotation": quotation_id, "amount": amount, "basis": basis})
    return aid


def approve_adjustment(db: Database, actor: Actor, adj_id: int, comments: str | None = None) -> None:
    approvals.authorize(actor, "quotation", "approve")
    r = db.one("SELECT * FROM quote_adjustments WHERE id=?", (adj_id,))
    if not r:
        raise NotFound("Adjustment not found.")
    db.update("quote_adjustments", {"status": "Approved", "approved_by": actor.username, "approved_at": now_iso()}, "id=?", (adj_id,))
    approvals.record(db, actor, "quotation", f"adj:{adj_id}", "approve", approved_value={"amount": r["amount"], "basis": r["basis"]},
                     comments=comments)


def level_package(db: Database, package_id: str, *, as_of: date | None = None, target_ccy: str = "SAR") -> dict:
    as_of = as_of or today()
    pkg = db.one("SELECT * FROM procurement_packages WHERE id=?", (package_id,))
    if not pkg:
        raise NotFound(f"Package {package_id} not found.")
    reg = registry(db)
    items = rows_to_dicts(db.all("SELECT * FROM procurement_items WHERE package_id=? ORDER BY id", (package_id,)))
    quotes = [q for q in rows_to_dicts(db.all("SELECT * FROM quotations WHERE package_id=? AND status NOT IN ('Rejected','Superseded') ORDER BY id",
                                              (package_id,)))]
    out_q = []
    for q in quotes:
        full = get_quotation(db, q["id"])
        lines_by_item = {}
        for ln in full["lines"]:
            if ln["procurement_item_id"]:
                lines_by_item.setdefault(ln["procurement_item_id"], ln)
        fx = _fx(db, q["currency"], target_ccy, as_of)
        tax_div, tax_note = ONE, None
        if q["tax_treatment"] == "incl":
            tr = D_opt(q["tax_rate_pct"])
            if tr is None:
                tax_div, tax_note = None, "Quote prices include tax but the tax rate is not stated."
            else:
                tax_div = ONE + pct(tr)
        elif q["tax_treatment"] is None:
            tax_div, tax_note = None, "Tax treatment not stated on the quotation."
        notes: list[str] = []
        if fx is None:
            notes.append(f"No approved FX rate {q['currency']}->{target_ccy}; normalised value unavailable.")
        if tax_note:
            notes.append(tax_note)
        v = validity(full, as_of)
        if v != "Valid":
            notes.append(f"Quotation validity: {v}.")
        rows, quoted_total, norm_total = [], ZERO, ZERO
        missing, qty_diff, unit_issues, non_compliant, excl_delivery = [], [], [], [], []
        resolvable = fx is not None and tax_div is not None
        for it in items:
            ln = lines_by_item.get(it["id"])
            if not ln:
                missing.append(it["id"])
                rows.append(dict(item_id=it["id"], status="Not quoted"))
                continue
            rate = D_opt(ln["unit_rate"])
            qty_req = D_opt(it["quantity"])
            qq = D_opt(ln["quantity"]) or qty_req
            disc = pct(ln["discount_pct"]) if D_opt(ln["discount_pct"]) else ZERO
            unit_factor, uflag = ONE, None
            if ln["unit"] and it["unit"] and ln["unit"] != it["unit"]:
                try:
                    unit_factor = reg.factor(ln["unit"], it["unit"])
                except ValidationFailed:
                    uflag = f"unit {ln['unit']} vs required {it['unit']} not convertible"
                    unit_issues.append(it["id"])
            if qq is not None and qty_req is not None and qq != qty_req:
                qty_diff.append(dict(item=it["id"], required=qty_req, quoted=qq))
            if ln["compliance"] == "Non-compliant":
                non_compliant.append(it["id"])
            if ln["delivery_included"] == "No" or ln["unloading_included"] == "No":
                excl_delivery.append(it["id"])
            quoted_ext = (qq or ZERO) * (rate or ZERO) * (ONE - disc)
            quoted_total += quoted_ext
            norm = None
            if resolvable and rate is not None and qty_req is not None and uflag is None:
                norm = qty_req * (rate / unit_factor) * (ONE - disc) * fx / tax_div
                norm_total += norm
            rows.append(dict(item_id=it["id"], status="Quoted", unit_rate=rate, discount=ln["discount_pct"], qty_quoted=qq,
                             qty_required=qty_req, unit=ln["unit"], quoted_extended=quantize(quoted_ext, 2),
                             normalised=None if norm is None else quantize(norm, 2), unit_flag=uflag, compliance=ln["compliance"],
                             lead_time_days=ln["lead_time_days"], delivery_included=ln["delivery_included"],
                             unloading_included=ln["unloading_included"], comments=ln["comments"],
                             spec_differences=spec_diff(it.get("specification") or "", ln.get("specification") or "") if (it.get("specification") and ln.get("specification")) else []))
        adjs = rows_to_dicts(db.all("SELECT * FROM quote_adjustments WHERE quotation_id=?", (q["id"],)))
        approved_adj = sum((D(a["amount"]) for a in adjs if a["status"] == "Approved"), ZERO)
        pending_adj = [a for a in adjs if a["status"] != "Approved"]
        like = (not missing and not unit_issues and resolvable and not non_compliant and v == "Valid")
        out_q.append(dict(
            quotation_id=q["id"], supplier_id=q["supplier_id"], reference=q["reference"], status=q["status"], currency=q["currency"],
            validity=v, valid_until=q["valid_until"], payment_terms=q["payment_terms"], lead_time_days=q["lead_time_days"],
            tax_treatment=q["tax_treatment"], exclusions=q["exclusions"], deviations=q["deviations"], quoted_total=quantize(quoted_total, 2),
            normalised_total=quantize(norm_total + approved_adj, 2) if resolvable else None, approved_adjustments=approved_adj,
            pending_adjustments=pending_adj, coverage=f"{len(items) - len(missing)}/{len(items)}", missing_items=missing,
            quantity_differences=qty_diff, unit_issues=unit_issues, non_compliant_items=non_compliant,
            delivery_or_unloading_excluded=excl_delivery, notes=notes, like_for_like=like, lines=rows,
            is_synthetic=bool(q["is_synthetic"])))
    comparable = sorted([x for x in out_q if x["like_for_like"] and x["normalised_total"] is not None], key=lambda x: x["normalised_total"])
    return dict(package_id=package_id, package_name=pkg["name"], as_of=as_of.isoformat(), items=items, quotations=out_q,
                suggested_lowest_like_for_like=comparable[0]["quotation_id"] if comparable else None,
                advisory="Advisory only: the cheapest quotation is not automatically awarded. A human must select and approve.",
                synthetic=any(x["is_synthetic"] for x in out_q))
