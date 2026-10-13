"""Weighted bid evaluation. Pure Decimal. Criteria, weights, scale and pass/fail rules are supplied by the company (approved governed parameter); scores are
entered by evaluators with evidence. The ranking is advisory: selection and award remain human, approved decisions.

  criterion points = weight x score / scale_max            (scored criteria)
  pass/fail        score 1 = pass, 0 = fail -> a fail disqualifies the bid
  price points     weight x (lowest qualifying price / bid price)   (method 'lowest_over_bid')
  total = sum of points ; a bid with a missing score or no price is INCOMPLETE and is not ranked."""
from __future__ import annotations

from decimal import Decimal

from ..core.errors import ValidationFailed
from ..core.money import ZERO, D


def validate_criteria(d: dict) -> dict:
    crit = d.get("criteria")
    if not isinstance(crit, list) or not crit:
        raise ValidationFailed("criteria must be a non-empty list.", code="PARAM_FIELD")
    seen, total = set(), ZERO
    out = []
    for c in crit:
        if set(c) - {"id", "name", "type", "weight", "pass_fail", "min_score"}:
            raise ValidationFailed(f"Unknown criterion field(s): {sorted(set(c) - {'id', 'name', 'type', 'weight', 'pass_fail', 'min_score'})}", code="PARAM_FIELD")
        cid = str(c.get("id", "")).strip()
        if not cid or cid in seen or cid == "PRICE":
            raise ValidationFailed(f"Criterion id missing, duplicated or reserved: '{cid}'.", code="PARAM_FIELD")
        seen.add(cid)
        pf = bool(c.get("pass_fail"))
        try:
            w = Decimal(str(c.get("weight", 0)))
        except Exception:
            raise ValidationFailed(f"{cid}: weight must be a number.", code="PARAM_FIELD")
        if pf and w != 0:
            raise ValidationFailed(f"{cid}: a pass/fail criterion carries no weight (it disqualifies).", code="PARAM_FIELD")
        if not pf and w <= 0:
            raise ValidationFailed(f"{cid}: weight must be > 0.", code="PARAM_FIELD")
        ms = c.get("min_score")
        out.append({"id": cid, "name": str(c.get("name", cid)), "type": str(c.get("type", "technical")), "weight": format(w.normalize(), "f") if w else "0",
                    "pass_fail": pf, "min_score": None if ms in (None, "") else str(Decimal(str(ms)))})
        total += w
    pw = d.get("price_weight")
    pw = ZERO if pw in (None, "") else Decimal(str(pw))
    if pw < 0:
        raise ValidationFailed("price_weight cannot be negative.", code="PARAM_FIELD")
    if total + pw != 100:
        raise ValidationFailed(f"Weights must sum to 100 (criteria {total} + price {pw} = {total + pw}).", code="PARAM_FIELD")
    return {"criteria": out, "price_weight": format(pw.normalize(), "f") if pw else "0"}


def evaluate(crit_set: dict, scale_max: Decimal, scores: dict[str, dict[str, Decimal]], prices: dict[str, Decimal | None]) -> dict:
    crit = crit_set["criteria"]
    pw = D(crit_set["price_weight"])
    bids = {}
    for qid in sorted(set(scores) | set(prices)):
        s = scores.get(qid, {})
        pts, reasons, missing = {}, [], []
        for c in crit:
            v = s.get(c["id"])
            if v is None:
                missing.append(c["id"])
                continue
            if c["pass_fail"]:
                if v == 0:
                    reasons.append(f"failed pass/fail criterion {c['id']} ({c['name']})")
                pts[c["id"]] = ZERO
                continue
            if c["min_score"] is not None and v < D(c["min_score"]):
                reasons.append(f"score {v} below minimum {c['min_score']} on {c['id']} ({c['name']})")
            pts[c["id"]] = D(c["weight"]) * v / scale_max
        price = prices.get(qid)
        if pw > 0 and price is None:
            missing.append("PRICE")
        bids[qid] = {"points": pts, "disqualified": reasons, "missing": missing, "price": price}
    qualifying = [q for q, b in bids.items() if not b["disqualified"] and not b["missing"] and (pw == 0 or (b["price"] is not None and b["price"] > 0))]
    low = min((bids[q]["price"] for q in qualifying if bids[q]["price"] is not None), default=None)
    for q, b in bids.items():
        b["price_points"] = pw * low / b["price"] if (pw > 0 and q in qualifying and low is not None) else (ZERO if pw > 0 else None)
        b["total"] = (sum(b["points"].values(), ZERO) + (b["price_points"] or ZERO)) if q in qualifying else None
        b["status"] = "Disqualified" if b["disqualified"] else ("Incomplete" if b["missing"] else "Evaluated")
    ranking = sorted(qualifying, key=lambda q: (-bids[q]["total"], q))
    for i, q in enumerate(ranking, 1):
        bids[q]["rank"] = i
    return {"bids": bids, "ranking": ranking, "lowest_qualifying_price": low}
