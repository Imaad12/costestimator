"""Commercial calculation engine (deterministic, Decimal).

Order of operations (each adder is computed ONCE from an explicitly named base, and traced):
  D  direct cost                         I  indirect cost                    C0 = D + I   (pre-contingency cost)
  Ct contingency = pct x base(D | D+I)
  R  risk allowances = sum(pct x base, or fixed amounts)
  E  escalation = pct x base(D | D+I | C0+Ct+R)
  T  total cost = C0 + Ct + R + E
  S  selling price: markup  S = T x (1 + m)      |  margin  S = T / (1 - g)      (method is labelled in the output)
  Dis discount = pct x S (or fixed amount)       N = S - Dis    (net price before tax)
  N' = N rounded per policy rounding rule (round to `step`); the rounding delta is reported
  Tax = sum over tax categories of (N' share x rate)      Final payable = N' + Tax
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ..core.errors import ValidationFailed
from ..core.money import HUNDRED, ONE, ZERO, D, D_opt, pct, quantize
from . import eligibility as elig
from .types import EngineException

BASES = ("direct", "direct_indirect", "cost_before_escalation")


@dataclass
class TraceStep:
    name: str
    formula: str
    base_name: str | None
    base_value: Decimal | None
    rate: str | None
    amount: Decimal


@dataclass
class CommercialResult:
    method: str                           # 'markup' | 'margin'
    method_label: str
    direct: Decimal
    indirect: Decimal
    pre_contingency_cost: Decimal
    contingency: Decimal
    risk: Decimal
    escalation: Decimal
    total_cost: Decimal
    selling_price_pre_discount: Decimal
    margin_amount: Decimal
    effective_markup_pct: Decimal | None
    effective_margin_pct: Decimal | None
    discount: Decimal
    net_price_unrounded: Decimal
    net_price: Decimal                    # pre-tax, after commercial rounding
    rounding_delta: Decimal
    tax_by_category: dict[str, dict]
    tax_total: Decimal
    final_payable: Decimal
    trace: list[TraceStep]
    exceptions: list[EngineException]
    policy_name: str = ""
    policy_status: str = ""
    risk_detail: list[dict] = field(default_factory=list)


def _round_step(v: Decimal, rounding: dict, money_dp: int) -> Decimal:
    step = D_opt(rounding.get("step")) or ZERO
    mode = rounding.get("mode", "half_up")
    if step and step > 0:
        from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP
        q = (v / step).quantize(Decimal(1), rounding=ROUND_HALF_EVEN if mode == "half_even" else ROUND_HALF_UP)
        return quantize(q * step, money_dp)
    return quantize(v, int(rounding.get("dp", money_dp)), mode)


def _base(name: str, d: Decimal, i: Decimal, ct: Decimal = ZERO, r: Decimal = ZERO) -> Decimal:
    if name == "direct":
        return d
    if name == "direct_indirect":
        return d + i
    if name == "cost_before_escalation":
        return d + i + ct + r
    raise ValidationFailed(f"Unknown cost base '{name}'. Use one of {BASES}.", code="BAD_BASE")


def _need(policy: dict, key: str) -> Decimal:
    v = D_opt(policy.get(key))
    if v is None:
        raise ValidationFailed(f"Commercial policy field '{key}' is required (no default is assumed).", code="POLICY_INCOMPLETE")
    return v


def validate_policy(policy: dict) -> list[str]:
    """Returns problems; an empty list means the policy is computable."""
    probs: list[str] = []
    m = policy.get("method")
    if m not in ("markup", "margin"):
        probs.append("method must be 'markup' or 'margin' (explicit choice required).")
    elif m == "markup" and D_opt(policy.get("markup_pct")) is None:
        probs.append("markup_pct is required for the markup method.")
    elif m == "margin":
        g = D_opt(policy.get("margin_pct"))
        if g is None:
            probs.append("margin_pct is required for the gross-margin method.")
        elif not (ZERO <= g < HUNDRED):
            probs.append("margin_pct must be >= 0 and < 100.")
    def _check_elig(label: str, c: dict) -> None:
        if c.get("eligibility"):
            try:
                elig.validate_spec(c["eligibility"])
            except ValidationFailed as e:
                probs.append(f"{label}.eligibility: {e.message}")
            if c.get("base") == "cost_before_escalation":
                probs.append(f"{label}.eligibility cannot be combined with base 'cost_before_escalation' (use 'direct' or 'direct_indirect').")

    for k in ("contingency", "escalation"):
        c = policy.get(k)
        if c is None:
            continue
        _check_elig(k, c)
        if D_opt(c.get("pct")) is None:
            probs.append(f"{k}.pct is required when {k} is present (use pct 0 for none).")
        if c.get("base") not in (BASES if k == "escalation" else BASES[:2]):
            probs.append(f"{k}.base must be one of {BASES if k == 'escalation' else BASES[:2]} (explicit base required).")
    names = []
    for r in policy.get("risk_items", []) or []:
        n = (r.get("name") or "").strip().lower()
        if n in names:
            probs.append(f"Risk allowance '{r.get('name')}' is listed twice (possible double count).")
        names.append(n)
        if "contingency" in n and policy.get("contingency") and D_opt(policy["contingency"].get("pct")):
            probs.append(f"Risk item '{r.get('name')}' looks like contingency, which is already applied separately.")
        if D_opt(r.get("pct")) is None and D_opt(r.get("amount")) is None:
            probs.append(f"Risk item '{r.get('name')}' needs pct or amount.")
        if D_opt(r.get("pct")) is not None and r.get("base") not in BASES[:2]:
            probs.append(f"Risk item '{r.get('name')}' needs base 'direct' or 'direct_indirect'.")
        _check_elig(f"risk '{r.get('name')}'", r)
    dsc = policy.get("discount")
    if dsc and D_opt(dsc.get("pct")) is None and D_opt(dsc.get("amount")) is None:
        probs.append("discount needs pct or amount.")
    return probs


def compute_commercial(policy: dict, *, direct: Decimal, indirect: Decimal, money_dp: int,
                       tax_shares: dict[str, Decimal] | None, tax_rates: dict[str, Decimal | None],
                       policy_name: str = "", policy_status: str = "", direct_lines: list[dict] | None = None) -> CommercialResult:
    probs = validate_policy(policy)
    if probs:
        raise ValidationFailed("Commercial policy invalid: " + " ".join(probs), code="POLICY_INVALID", details=probs)
    exc: list[EngineException] = []
    trace: list[TraceStep] = []
    q = lambda v: quantize(v, money_dp)  # noqa: E731

    def eligible_direct(c: dict) -> tuple[Decimal, str]:
        """Direct cost that this adder's percentage applies to: the whole direct cost unless the adder states an eligibility spec (then the eligible part, with a note)."""
        spec = elig.validate_spec(c.get("eligibility")) if c.get("eligibility") else None
        if spec is None or direct_lines is None:
            return direct, ""
        bd = elig.eligible_base(direct_lines, spec)
        return bd["eligible"], f" [eligible direct {bd['eligible']} of {bd['total']}; excluded {bd['excluded']}; unclassified {bd['unclassified']}]"
    c0 = q(direct + indirect)
    trace.append(TraceStep("Pre-contingency cost (C0)", "Direct + Indirect", None, None, None, c0))

    ct = ZERO
    if policy.get("contingency"):
        c = policy["contingency"]
        ed, note = eligible_direct(c)
        b = _base(c["base"], ed, indirect)
        ct = q(b * pct(c["pct"]))
        trace.append(TraceStep("Contingency", f"{c['pct']}% x base[{c['base']}]{note}", c["base"], b, str(c["pct"]), ct))
    risk = ZERO
    risk_detail = []
    for r in policy.get("risk_items", []) or []:
        if D_opt(r.get("pct")) is not None:
            ed, note = eligible_direct(r)
            b = _base(r["base"], ed, indirect)
            amt = q(b * pct(r["pct"]))
            trace.append(TraceStep(f"Risk: {r['name']}", f"{r['pct']}% x base[{r['base']}]{note}", r["base"], b, str(r["pct"]), amt))
        else:
            amt = q(D(r["amount"]))
            trace.append(TraceStep(f"Risk: {r['name']}", "fixed amount", None, None, None, amt))
        risk += amt
        risk_detail.append({"name": r["name"], "amount": amt})
    esc = ZERO
    if policy.get("escalation"):
        e = policy["escalation"]
        ed, note = eligible_direct(e)
        b = _base(e["base"], ed, indirect, ct, risk)
        esc = q(b * pct(e["pct"]))
        trace.append(TraceStep("Escalation", f"{e['pct']}% x base[{e['base']}]{note}", e["base"], b, str(e["pct"]), esc))
    total_cost = q(c0 + ct + risk + esc)
    trace.append(TraceStep("Total cost (T)", "C0 + contingency + risk + escalation", None, None, None, total_cost))

    method = policy["method"]
    if method == "markup":
        m = D(policy["markup_pct"])
        sell = q(total_cost * (ONE + pct(m)))
        label = f"Selling price = Cost x (1 + Markup); markup = {m}% on total cost"
        trace.append(TraceStep("Selling price (markup)", f"T x (1 + {m}%)", "total_cost", total_cost, str(m), sell))
    else:
        g = D(policy["margin_pct"])
        sell = q(total_cost / (ONE - pct(g)))
        label = f"Selling price = Cost / (1 - Gross Margin); gross margin = {g}% of selling price"
        trace.append(TraceStep("Selling price (gross margin)", f"T / (1 - {g}%)", "total_cost", total_cost, str(g), sell))
    margin_amt = sell - total_cost
    eff_markup = (margin_amt / total_cost * HUNDRED) if total_cost else None
    eff_margin = (margin_amt / sell * HUNDRED) if sell else None

    disc = ZERO
    dsc = policy.get("discount")
    if dsc:
        if D_opt(dsc.get("pct")) is not None:
            disc = q(sell * pct(dsc["pct"]))
            trace.append(TraceStep("Discount", f"{dsc['pct']}% x selling price", "selling_price", sell, str(dsc["pct"]), -disc))
        else:
            disc = q(D(dsc["amount"]))
            trace.append(TraceStep("Discount", "fixed amount", None, None, None, -disc))
    net_unrounded = sell - disc
    rounding = policy.get("rounding") or {"dp": money_dp, "mode": "half_up"}
    net = _round_step(net_unrounded, rounding, money_dp)
    if net != net_unrounded:
        trace.append(TraceStep("Commercial rounding", f"round to {rounding}", None, None, None, net - net_unrounded))

    tax_by: dict[str, dict] = {}
    tax_total = ZERO
    shares = tax_shares or {}
    wsum = sum(shares.values(), ZERO)
    if not shares:
        shares = {policy.get("default_tax_category") or "": ONE}
        wsum = ONE
    allocated = ZERO
    cats = list(shares)
    for idx, cat in enumerate(cats):
        base_amt = net - allocated if idx == len(cats) - 1 else q(net * shares[cat] / wsum) if wsum else ZERO
        allocated += base_amt
        rate = tax_rates.get(cat)
        if rate is None:
            exc.append(EngineException("TAX_RATE_UNRESOLVED", "High",
                                       f"Tax category '{cat or '(none)'}' has no verified/valid rate for the estimate date."))
            tax_by[cat] = {"base": base_amt, "rate_pct": None, "tax": None}
            continue
        t = q(base_amt * pct(rate))
        tax_by[cat] = {"base": base_amt, "rate_pct": rate, "tax": t}
        tax_total += t
        trace.append(TraceStep(f"Tax {cat}", f"{rate}% x {base_amt}", "net_price", base_amt, str(rate), t))
    final = net + tax_total
    return CommercialResult(method, label, q(direct), q(indirect), c0, ct, risk, esc, total_cost, sell, margin_amt,
                            eff_markup, eff_margin, disc, net_unrounded, net, net - net_unrounded, tax_by, tax_total,
                            final, trace, exc, policy_name, policy_status, risk_detail)
