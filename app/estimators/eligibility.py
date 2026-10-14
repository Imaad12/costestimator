"""Explicit eligibility of direct cost for a percentage-based adder (percentage indirects, contingency, risk and escalation percentages). Pure Decimal.

A spec is  {"default": "include" | "exclude", "rules": [{"cost_prefix"?, "item_key"?, "kind"?, "eligible_pct": 0..100, "note"?}, ...]}.
The FIRST rule whose every stated key matches a direct cost line decides that line's eligible share; a line that matches no rule takes the default and is reported as
UNCLASSIFIED (so nothing is silently in or out). With no spec at all the legacy behaviour applies: every direct line is fully eligible, and the breakdown says it was not specified.
`kind` is the cost line kind (material, labour, plant, equipment, subcontract, plant_standby, ...). The breakdown is returned for audit by cost code, BOQ line and kind."""
from __future__ import annotations

from decimal import Decimal

from ..core.errors import ValidationFailed
from ..core.money import ZERO, D

HUNDRED = Decimal(100)
RULE_KEYS = {"cost_prefix", "item_key", "kind", "eligible_pct", "note"}


def validate_spec(spec) -> dict | None:
    if spec in (None, "", {}):
        return None
    if not isinstance(spec, dict):
        raise ValidationFailed("eligibility must be an object {default, rules}.", code="ELIGIBILITY")
    extra = set(spec) - {"default", "rules"}
    if extra:
        raise ValidationFailed(f"Unknown eligibility field(s) {sorted(extra)}.", code="ELIGIBILITY")
    default = spec.get("default")
    if default not in ("include", "exclude"):
        raise ValidationFailed("eligibility.default must be 'include' or 'exclude' (what happens to lines that no rule names).", code="ELIGIBILITY")
    rules = []
    for i, r in enumerate(spec.get("rules") or [], 1):
        if not isinstance(r, dict) or set(r) - RULE_KEYS:
            raise ValidationFailed(f"eligibility rule {i}: allowed keys {sorted(RULE_KEYS)}.", code="ELIGIBILITY")
        if not (r.get("cost_prefix") or r.get("item_key") or r.get("kind")):
            raise ValidationFailed(f"eligibility rule {i} needs at least one of cost_prefix, item_key, kind.", code="ELIGIBILITY")
        try:
            p = D(str(r.get("eligible_pct")))
        except Exception:
            raise ValidationFailed(f"eligibility rule {i}: eligible_pct must be a number 0-100.", code="ELIGIBILITY")
        if p < 0 or p > 100:
            raise ValidationFailed(f"eligibility rule {i}: eligible_pct {p} is outside 0-100 (an adder cannot apply to more than the underlying cost).", code="ELIGIBILITY")
        rules.append({**{k: r[k] for k in ("cost_prefix", "item_key", "kind", "note") if r.get(k)}, "eligible_pct": str(p)})
    return {"default": default, "rules": rules}


def _match(rule: dict, line: dict) -> bool:
    if rule.get("cost_prefix") and not (line.get("cost_code") or "").startswith(rule["cost_prefix"]):
        return False
    if rule.get("item_key") and rule["item_key"] != line.get("item_key"):
        return False
    if rule.get("kind") and rule["kind"] != line.get("kind"):
        return False
    return True


def eligible_base(lines: list[dict], spec: dict | None) -> dict:
    """lines: [{item_key, cost_code, kind, amount}]. Returns {specified, total, eligible, excluded, unclassified, by_cost_code, by_item, by_kind, rows}."""
    total = eligible = unclassified = ZERO
    by_cc: dict[str, dict] = {}
    by_item: dict[str, dict] = {}
    by_kind: dict[str, dict] = {}
    rows = []
    for l in lines:
        a = l.get("amount")
        if a is None:
            continue
        a = D(a)
        if spec is None:
            pct, how, unc = HUNDRED, "not specified: whole direct cost", False
        else:
            hit = next((r for r in spec["rules"] if _match(r, l)), None)
            if hit:
                pct, how, unc = D(hit["eligible_pct"]), "rule " + ", ".join(f"{k}={v}" for k, v in hit.items() if k in ("cost_prefix", "item_key", "kind")), False
            else:
                pct, how, unc = (HUNDRED if spec["default"] == "include" else ZERO), f"default {spec['default']} (unclassified)", True
        e = a * pct / HUNDRED
        total += a
        eligible += e
        if unc:
            unclassified += a
        for key, bucket in (((l.get("cost_code") or "(none)"), by_cc), (l.get("item_key") or "(none)", by_item), (l.get("kind") or "(none)", by_kind)):
            b = bucket.setdefault(key, dict(total=ZERO, eligible=ZERO))
            b["total"] += a
            b["eligible"] += e
        rows.append(dict(item_key=l.get("item_key"), cost_code=l.get("cost_code"), kind=l.get("kind"), amount=a, eligible_pct=pct, eligible_amount=e, decided_by=how))
    return dict(specified=spec is not None, spec=spec, total=total, eligible=eligible, excluded=total - eligible, unclassified=unclassified,
                by_cost_code=by_cc, by_item=by_item, by_kind=by_kind, rows=rows)
