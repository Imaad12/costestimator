"""Deterministic direct-cost engine.

Pure function of `EstimateInputs` (no DB, no AI, no clock). Every cost line carries its own calculation `basis`
text, the rate record used, the assumptions applied, and flags. Nothing unresolved is ever priced as zero:
unpriced lines have amount=None and an exception, and are excluded from totals (with exposure reported separately).

Formulas (all explicit; see docs/ESTIMATING_METHODOLOGY.md):
  assembly qty            Qa = BOQ qty x convert(BOQ unit -> assembly unit)
  material/equipment/etc  Q  = Qa x factor ; gross = Q x (1 + waste%/100) only if waste_basis != none
  labour paid_hours_per_unit        H = Qa x factor
  labour productive_hours_per_unit  H = Qa x factor x shift_hours / productive_hours_per_shift
  labour output_per_crew_shift      shifts = Qa / output ; H_i = shifts x count_i x shift_hours
  plant                             charged = Qa x factor / (utilisation%/100)  (if utilisation basis set)
  amount = round(gross_qty_in_rate_unit x rate x fx, money_dp)
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from ..core.errors import ValidationFailed
from ..core.money import ONE, ZERO, D, D_opt, pct, quantize
from ..core.units import UnitRegistry
from ..database import jload
from ..models.enums import Status
from . import rate_build
from .rate_resolution import ELIGIBLE, PROVISIONAL, resolve_rate
from .types import (AssemblyDef, AssumptionValue, CostLine, DirectCostResult, EngineException, EstimateInputs, ItemCost)


class _Ctx:
    def __init__(self, inp: EstimateInputs):
        self.inp = inp
        self.exceptions: list[EngineException] = []
        self.lines: list[CostLine] = []
        self.used_assumptions: set[str] = set()
        self.used_rates: set[int] = set()
        k = inp.engine_keys
        self.money_dp = int(D(k["money.rounding_dp"].value)) if _ok(k.get("money.rounding_dp")) else 2
        self.qty_dp = int(D(k["qty.rounding_dp"].value)) if _ok(k.get("qty.rounding_dp")) else 3
        self.age_warn = int(D(k["rates.age_warning_days"].value)) if _ok(k.get("rates.age_warning_days"), True) else None
        self.currency = inp.project.get("currency") or "SAR"

    def exc(self, code, severity, msg, **kw):
        self.exceptions.append(EngineException(code, severity, msg, **kw))


def _ok(av: AssumptionValue | None, allow_unapproved: bool = False) -> bool:
    return bool(av and av.has_value and (av.approved or allow_unapproved))


# ----------------------------------------------------------------------------- assumptions
def _assumption(ctx: _Ctx, aid: str | None = None, key: str | None = None) -> tuple[Decimal | None, str | None]:
    """Return (numeric value, problem-code). Unapproved values are used only in include_unapproved mode (flagged)."""
    av = ctx.inp.engine_keys.get(key) if key else ctx.inp.assumptions.get(aid or "")
    label = key or aid
    if av is None or not av.has_value:
        return None, "ASSUMPTION_MISSING"
    if av.id:
        ctx.used_assumptions.add(av.id)
    if not av.approved:
        if not ctx.inp.include_unapproved:
            return None, "ASSUMPTION_NOT_APPROVED"
    v = D_opt(av.value)
    if v is None:
        return None, "ASSUMPTION_NOT_NUMERIC"
    return v, None


# ----------------------------------------------------------------------------- rates
def _fx(ctx: _Ctx, ccy: str) -> tuple[Decimal | None, str | None]:
    if ccy == ctx.currency:
        return ONE, None
    best = None
    for f in ctx.inp.fx:
        if f["from_ccy"] == ccy and f["to_ccy"] == ctx.currency and f["status"] == Status.APPROVED.value:
            from ..core.timeutil import parse_date
            rd, vu = parse_date(f["rate_date"]), parse_date(f.get("valid_until"))
            if rd and rd <= ctx.inp.as_of and (not vu or vu >= ctx.inp.as_of):
                if best is None or rd > parse_date(best["rate_date"]):
                    best = f
    if not best:
        return None, f"No approved FX rate {ccy}->{ctx.currency} valid on {ctx.inp.as_of}."
    return D(best["rate"]), None


def _price_line(ctx: _Ctx, line: CostLine, resource_id: str, qty_res_unit: Decimal, res_unit: str,
                *, charged_qty: Decimal | None = None) -> None:
    """Resolve the rate for `resource_id` and compute line.amount (or leave unpriced with exception)."""
    inp = ctx.inp
    res = inp.resources.get(resource_id)
    rr = resolve_rate(inp.rates.get(resource_id, []), project_id=inp.project["id"],
                      project_region=inp.project.get("region") or "KSA-ALL", as_of=inp.as_of,
                      region_parents=inp.region_parents, age_warning_days=ctx.age_warn)
    line.eligibility = rr.eligibility
    rate = rr.rate
    if not rr.usable and inp.include_unapproved and rr.indicative_rate and rr.eligibility in ("UNAPPROVED",):
        # preliminary view: price with the unapproved rate but flag loudly
        rate = rr.indicative_rate
        line.flags.append("UNAPPROVED_RATE_USED_PRELIMINARY")
    elif not rr.usable:
        line.flags.append(f"{rr.eligibility}_RATE" if rr.eligibility != "MISSING" else "MISSING_RATE")
        code = {"MISSING": "MISSING_RATE", "EXPIRED": "EXPIRED_RATE", "UNAPPROVED": "UNAPPROVED_RATE",
                "REGION": "RATE_REGION_MISMATCH", "FUTURE": "RATE_NOT_YET_EFFECTIVE",
                "NON_PRICE": "INDEX_ONLY_NO_PRICE"}.get(rr.eligibility, "MISSING_RATE")
        ind = rr.indicative_rate
        if ind is not None:
            ip = D_opt(ind.get("unit_price"))
            if ip is not None:
                ifx, _ = _fx(ctx, ind["currency"])
                if ifx is not None:
                    try:
                        line.indicative_amount = quantize(
                            qty_res_unit * ip * ifx / inp.units.factor(ind["unit"], res_unit), ctx.money_dp)
                    except ValidationFailed:
                        pass
        ctx.exc(code, "High" if code in ("EXPIRED_RATE", "UNAPPROVED_RATE") else "High",
                f"{resource_id} '{(res or {}).get('description', '')[:60]}': {rr.message}",
                item_key=line.item_key, resource_id=resource_id, exposure=line.indicative_amount,
                rate_id=(ind or {}).get("id"))
        return
    ctx.used_rates.add(rate["id"])
    line.rate_id, line.rate_type, line.rate_status = rate["id"], rate["rate_type"], rate["status"]
    line.rate_currency = rate["currency"]
    line.is_synthetic = bool(rate.get("is_synthetic"))
    line.is_provisional = rate["status"] == Status.PROVISIONAL.value
    for w in (rr.warnings if rr.usable else []):
        if w.startswith("SYNTHETIC"):
            line.flags.append("SYNTHETIC_RATE")
        else:
            line.flags.append("RATE_WARNING")
            ctx.exc("RATE_WARNING", "Low", f"{resource_id}: {w}", item_key=line.item_key, resource_id=resource_id,
                    rate_id=rate["id"])
    if line.is_provisional:
        line.flags.append("PROVISIONAL_RATE")
    fxv, fxerr = _fx(ctx, rate["currency"])
    if fxv is None:
        line.flags.append("FX_MISSING")
        ctx.exc("FX_MISSING", "High", fxerr, item_key=line.item_key, resource_id=resource_id)
        return
    try:
        unit_factor = inp.units.factor(rate["unit"], res_unit)   # 1 rate-unit = f resource-units
    except ValidationFailed as e:
        line.flags.append("UNIT_CONVERSION")
        ctx.exc("UNIT_CONVERSION", "High", f"{resource_id}: rate unit {rate['unit']} vs resource unit {res_unit}: {e.message}",
                item_key=line.item_key, resource_id=resource_id)
        return
    price = D(rate["unit_price"])
    rate_per_res_unit = price * fxv / unit_factor
    line.rate = rate_per_res_unit
    line.fx_rate = fxv if fxv != ONE else None
    billed = charged_qty if charged_qty is not None else qty_res_unit
    # plant with component build-up: fuel only on productive hours
    comps = jload(rate.get("components_json"), None) if res and res["resource_type"] == "plant" else None
    if comps and charged_qty is not None and "hire_rate" in comps:
        try:
            pb = rate_build.build_plant(comps)
            amount = (billed * pb.hourly_cost_charged + qty_res_unit * pb.fuel_per_hour) * fxv
            line.basis += (f" | plant build-up: charged hrs {billed} x (hire+operator+maintenance {pb.hourly_cost_charged}) "
                           f"+ productive hrs {qty_res_unit} x fuel {pb.fuel_per_hour}")
            line.amount = quantize(amount, ctx.money_dp)
            return
        except ValidationFailed as e:
            ctx.exc("PLANT_BUILD_INVALID", "High", e.message, item_key=line.item_key, resource_id=resource_id)
            line.flags.append("PLANT_BUILD_INVALID")
            return
    line.amount = quantize(billed * rate_per_res_unit, ctx.money_dp)


# ----------------------------------------------------------------------------- assembly expansion
def _need_factor(ctx: _Ctx, item_key: str, al: dict, ref: str) -> Decimal | None:
    f = D_opt(al.get("factor"))
    if f is None:
        ctx.exc("FACTOR_MISSING", "High", f"{ref}: consumption/productivity factor missing (estimator input required).",
                item_key=item_key, resource_id=al.get("resource_id"))
    return f


def _expand(ctx: _Ctx, item: dict, asm: AssemblyDef, qty: Decimal, path: str, stack: tuple[str, ...], depth: int) -> None:
    inp = ctx.inp
    ik = item["item_key"]
    if asm.code in stack:
        ctx.exc("CIRCULAR_ASSEMBLY", "Critical", f"Circular assembly reference: {' > '.join(stack + (asm.code,))}", item_key=ik)
        return
    if depth > inp.max_depth:
        ctx.exc("ASSEMBLY_TOO_DEEP", "High", f"Assembly nesting deeper than {inp.max_depth} at {path}", item_key=ik)
        return
    stack = stack + (asm.code,)
    # run-time double-count guard (also enforced when the assembly is approved)
    sub_inc = {"labour": False, "material": False, "plant": False}
    for al in asm.lines:
        if al["line_type"] == "subcontract":
            sub_inc["labour"] |= bool(al.get("includes_labour"))
            sub_inc["material"] |= bool(al.get("includes_material"))
            sub_inc["plant"] |= bool(al.get("includes_plant"))
    for al in asm.lines:
        ref = f"{path}#{al['line_no']}"
        lt = al["line_type"]
        if lt in sub_inc and sub_inc[lt] and not al.get("explicitly_separate"):
            ctx.exc("DOUBLE_COUNT_SUBCONTRACT", "Critical",
                    f"{ref}: {lt} line duplicates a subcontract line that already includes {lt}; line not priced.",
                    item_key=ik, resource_id=al.get("resource_id"))
            continue
        factor = _need_factor(ctx, ik, al, ref) if lt != "other" else D_opt(al.get("factor"))
        if factor is None:
            continue
        if lt == "assembly":
            child = inp.assemblies.get(al["child_assembly_code"])
            if child is None:
                ctx.exc("CHILD_ASSEMBLY_UNAVAILABLE", "High",
                        f"{ref}: nested assembly {al['child_assembly_code']} is not approved/available.", item_key=ik)
                continue
            cq = qty * factor
            if al.get("factor_unit") and al["factor_unit"] != child.unit:
                try:
                    cq = cq * inp.units.factor(al["factor_unit"], child.unit)
                except ValidationFailed as e:
                    ctx.exc("UNIT_CONVERSION", "High", f"{ref}: {e.message}", item_key=ik)
                    continue
            _expand(ctx, item, child, cq, f"{path}>{child.code}", stack, depth + 1)
            continue
        rid = al.get("resource_id")
        res = inp.resources.get(rid) if rid else None
        if lt == "other" or rid is None:
            ctx.exc("UNSUPPORTED_LINE", "Medium", f"{ref}: 'other' line without a resource cannot be priced.", item_key=ik)
            continue
        if res is None:
            ctx.exc("UNKNOWN_RESOURCE", "High", f"{ref}: resource {rid} not found.", item_key=ik, resource_id=rid)
            continue
        line = CostLine(item_key=ik, assembly_code=asm.code, assembly_version=asm.version, path=path, line_ref=ref,
                        kind=lt, resource_id=rid, description=res["description"], quantity=None, unit=res["unit"],
                        cost_code=item.get("cost_code") or asm.cost_code)
        ctx.lines.append(line)
        if lt == "labour":
            _labour(ctx, item, asm, al, line, qty, factor, ref)
        elif lt == "plant":
            _plant(ctx, item, al, line, qty, factor, ref)
        else:
            _material_like(ctx, item, al, line, qty, factor, ref, res)
        if lt == "subcontract":
            line.subcontract_includes = {"labour": bool(al.get("includes_labour")),
                                         "material": bool(al.get("includes_material")),
                                         "plant": bool(al.get("includes_plant"))}


def _convert_factor_unit(ctx: _Ctx, line: CostLine, al: dict, res_unit: str, qty: Decimal) -> Decimal | None:
    fu = al.get("factor_unit") or res_unit
    if fu == res_unit:
        return qty
    try:
        return qty * ctx.inp.units.factor(fu, res_unit)
    except ValidationFailed as e:
        line.flags.append("UNIT_CONVERSION")
        ctx.exc("UNIT_CONVERSION", "High", f"{line.line_ref}: {e.message}", item_key=line.item_key, resource_id=line.resource_id)
        return None


def _material_like(ctx: _Ctx, item, al, line: CostLine, qty: Decimal, factor: Decimal, ref: str, res: dict) -> None:
    base = qty * factor
    basis = f"qty {qty} x factor {factor} = {base} {al.get('factor_unit') or res['unit']}"
    base_res = _convert_factor_unit(ctx, line, al, res["unit"], base)
    if base_res is None:
        return
    line.base_quantity = base_res
    gross = base_res
    wb = al.get("waste_basis") or "none"
    if wb == "fixed_pct":
        w = D_opt(al.get("waste_value"))
        if w is None:
            ctx.exc("WASTE_INVALID", "High", f"{ref}: waste value invalid.", item_key=line.item_key)
            return
        gross = base_res * (ONE + pct(w))
        basis += f" | waste fixed {w}% => x{ONE + pct(w)}"
    elif wb == "assumption":
        w, prob = _assumption(ctx, aid=al.get("waste_ref"))
        line.assumptions.append(al.get("waste_ref") or "")
        if w is None:
            line.flags.append(prob)
            ctx.exc(prob, "High", f"{ref}: waste assumption {al.get('waste_ref')} unavailable ({prob}).",
                    item_key=line.item_key, assumption_id=al.get("waste_ref"))
            return
        gross = base_res * (ONE + pct(w))
        basis += f" | waste per assumption {al.get('waste_ref')} = {w}% => x{ONE + pct(w)}"
    elif al.get("factor_includes_waste"):
        basis += " | factor already includes waste (no further waste applied)"
    line.quantity = gross
    line.basis = basis
    _price_line(ctx, line, line.resource_id, gross, res["unit"])
    line.basis += f" | rate {line.rate} / {res['unit']} => {line.amount}" if line.amount is not None else " | UNPRICED"


def _hours_params(ctx: _Ctx, al: dict, need_productive: bool) -> tuple[Decimal | None, Decimal | None, str | None]:
    sh, prob = _assumption(ctx, aid=al.get("shift_hours_ref")) if al.get("shift_hours_ref") else _assumption(ctx, key="labour.shift_hours")
    if sh is None:
        return None, None, prob
    ph = None
    if need_productive:
        ph, prob = (_assumption(ctx, aid=al.get("productive_hours_ref")) if al.get("productive_hours_ref")
                    else _assumption(ctx, key="labour.productive_hours_per_shift"))
        if ph is None:
            return sh, None, prob
        if ph <= 0 or ph > sh:
            return sh, None, "PRODUCTIVE_HOURS_INVALID"
    if sh <= 0:
        return None, None, "SHIFT_HOURS_INVALID"
    return sh, ph, None


def _labour(ctx: _Ctx, item, asm, al, line: CostLine, qty: Decimal, factor: Decimal, ref: str) -> None:
    pb = al.get("productivity_basis")
    ik = item["item_key"]
    if pb is None:
        line.flags.append("NO_PRODUCTIVITY_BASIS")
        ctx.exc("NO_PRODUCTIVITY_BASIS", "High", f"{ref}: labour line has no explicit productivity basis.", item_key=ik,
                resource_id=line.resource_id)
        return
    ot = al.get("overtime_share_pct")
    if pb == "paid_hours_per_unit":
        hours = qty * factor
        line.basis = f"paid hours: qty {qty} x {factor} h/unit = {hours} h"
        _labour_price(ctx, line, al, hours, ot, ref)
        return
    if pb == "productive_hours_per_unit":
        sh, ph, prob = _hours_params(ctx, al, True)
        if prob:
            _unresolved_assumption(ctx, line, ref, prob)
            return
        hours = qty * factor * sh / ph
        line.assumptions += ["labour.shift_hours", "labour.productive_hours_per_shift"]
        line.basis = f"productive hrs/unit {factor} x qty {qty} x shift {sh} / productive {ph} = {hours} paid h"
        _labour_price(ctx, line, al, hours, ot, ref)
        return
    if pb == "output_per_crew_shift":
        crew = jload(al.get("crew_json"), []) if not al.get("crew") else al["crew"]
        sh, _, prob = _hours_params(ctx, al, False)
        if prob:
            _unresolved_assumption(ctx, line, ref, prob)
            return
        if factor <= 0:
            ctx.exc("OUTPUT_INVALID", "High", f"{ref}: output per crew-shift must be > 0.", item_key=ik)
            return
        shifts = qty / factor
        # first crew member uses the already-created line; the rest get new lines
        ctx.lines.remove(line)
        for idx, member in enumerate(crew, 1):
            rid = member["resource_id"]
            cnt = D(member.get("count", 1))
            res = ctx.inp.resources.get(rid)
            if res is None:
                ctx.exc("UNKNOWN_RESOURCE", "High", f"{ref}: crew resource {rid} not found.", item_key=ik, resource_id=rid)
                continue
            ln = CostLine(item_key=ik, assembly_code=line.assembly_code, assembly_version=line.assembly_version,
                          path=line.path, line_ref=f"{ref}.{idx}", kind="labour", resource_id=rid,
                          description=res["description"], quantity=None, unit=res["unit"], cost_code=line.cost_code)
            ctx.lines.append(ln)
            hours = shifts * cnt * sh
            ln.assumptions.append("labour.shift_hours")
            ln.basis = f"crew-shift: qty {qty} / output {factor} = {shifts} shifts x {cnt} x {sh} h = {hours} h"
            _labour_price(ctx, ln, al, hours, ot, ref)
        return
    ctx.exc("PRODUCTIVITY_BASIS_UNKNOWN", "High", f"{ref}: unknown productivity basis {pb}", item_key=ik)


def _unresolved_assumption(ctx: _Ctx, line: CostLine, ref: str, prob: str) -> None:
    line.flags.append(prob)
    ctx.exc(prob, "High", f"{ref}: required labour calendar assumption unavailable ({prob}).",
            item_key=line.item_key, resource_id=line.resource_id)


def _wbs_chain(inp: EstimateInputs, item_key: str) -> set[str]:
    """The item's WBS code and all its ancestors (a factor scoped to an area applies to everything beneath it)."""
    out, cur, guard = set(), inp.item_wbs.get(item_key), 0
    while cur and guard < 50:
        out.add(cur)
        cur, guard = inp.wbs_parent.get(cur), guard + 1
    return out


def productivity_factors_for(inp: EstimateInputs, item_key: str, cost_code: str | None) -> list[dict]:
    """Governed productivity factors (labour) whose scope matches the item. Deterministic order (by code)."""
    chain = _wbs_chain(inp, item_key)
    out = []
    for p in sorted(inp.params.get("productivity_factor", []), key=lambda p: p["code"]):
        d = p["data"]
        if d.get("applies_to", "labour") != "labour":
            continue
        pre, wbs = d.get("scope_cost_prefix"), d.get("scope_wbs")
        if pre and not (cost_code or "").startswith(pre):
            continue
        if wbs and wbs not in chain:
            continue
        out.append(p)
    return out


def _adjust_hours(ctx: _Ctx, line: CostLine, hours: Decimal, ref: str) -> Decimal:
    """Apply the governed productivity factors in scope to labour hours (multiplicative; recorded on the line)."""
    facs = productivity_factors_for(ctx.inp, line.item_key, line.cost_code)
    if facs:
        combined = ONE
        for p in facs:
            combined *= D(p["data"]["factor"])
            if p.get("unapproved"):
                line.flags.append("UNAPPROVED_PRODUCTIVITY_FACTOR")
                ctx.exc("UNAPPROVED_PRODUCTIVITY_FACTOR", "High", f"{ref}: productivity factor {p['code']} v{p['version']} is '{p['status']}'.",
                        item_key=line.item_key)
        base = hours
        hours = hours * combined
        line.flags.append("PRODUCTIVITY_ADJUSTED")
        line.basis += (f" | productivity factors {[p['code'] for p in facs]} (multiplicative) x {combined}: {base} h => {hours} h")
    return hours


def _labour_price(ctx: _Ctx, line: CostLine, al: dict, hours: Decimal, ot_share, ref: str) -> None:
    hours = _adjust_hours(ctx, line, hours, ref)
    line.hours = hours
    line.quantity = hours
    line.unit = "hr"
    res_unit = ctx.inp.resources[line.resource_id]["unit"]
    if res_unit != "hr":
        ctx.exc("LABOUR_UNIT", "High", f"{ref}: labour resource unit must be hr (is {res_unit}).", item_key=line.item_key)
        return
    _price_line(ctx, line, line.resource_id, hours, "hr")
    if line.amount is not None and ot_share not in (None, "") and D_opt(ot_share) not in (None, ZERO):
        # overtime premium on base wage portion, from the rate's labour build-up
        rate = next((r for r in ctx.inp.rates.get(line.resource_id, []) if r["id"] == line.rate_id), None)
        comps = jload((rate or {}).get("components_json"), None)
        if not comps:
            line.amount = None
            line.flags.append("OT_NEEDS_BUILDUP")
            ctx.exc("OT_NEEDS_BUILDUP", "High", f"{ref}: overtime share requires a labour rate build-up (components).",
                    item_key=line.item_key, resource_id=line.resource_id)
            return
        try:
            blended = rate_build.blended_labour_rate(comps, ot_share)
        except ValidationFailed as e:
            line.amount = None
            ctx.exc("OT_INVALID", "High", f"{ref}: {e.message}", item_key=line.item_key)
            return
        straight = rate_build.build_labour(comps).hourly_cost
        line.rate = line.rate * (blended / straight) if straight else line.rate
        line.amount = quantize(hours * line.rate, ctx.money_dp)
        line.basis += f" | overtime share {ot_share}% (premium on base wage only)"
    if line.amount is not None:
        line.basis += f" | rate {line.rate}/h => {line.amount}"


def _plant(ctx: _Ctx, item, al, line: CostLine, qty: Decimal, factor: Decimal, ref: str) -> None:
    hours = qty * factor
    line.hours = hours
    line.basis = f"plant hours: qty {qty} x {factor} h/unit = {hours} h"
    charged = hours
    ub = al.get("utilisation_basis") or "none"
    if ub != "none":
        if ub == "fixed_pct":
            u = D_opt(al.get("utilisation_value"))
            prob = None if u is not None else "ASSUMPTION_NOT_NUMERIC"
        else:
            u, prob = (_assumption(ctx, aid=al.get("utilisation_ref")) if al.get("utilisation_ref")
                       else _assumption(ctx, key="plant.utilisation_pct"))
            line.assumptions.append(al.get("utilisation_ref") or "plant.utilisation_pct")
        if u is None or u <= 0 or u > 100:
            line.flags.append(prob or "UTILISATION_INVALID")
            ctx.exc(prob or "UTILISATION_INVALID", "High", f"{ref}: plant utilisation unavailable/invalid.",
                    item_key=line.item_key, resource_id=line.resource_id, assumption_id=al.get("utilisation_ref"))
            return
        charged = hours / pct(u)
        line.basis += f" | utilisation {u}% => charged {charged} h"
    line.quantity = charged
    line.unit = ctx.inp.resources[line.resource_id]["unit"]
    if line.unit != "hr":
        ctx.exc("PLANT_UNIT", "Medium", f"{ref}: plant resource unit is {line.unit}; hours-based factor assumed to be in that unit.",
                item_key=line.item_key, resource_id=line.resource_id)
    _price_line(ctx, line, line.resource_id, hours, line.unit, charged_qty=charged)
    if line.amount is not None:
        line.basis += f" => {line.amount}"


# ----------------------------------------------------------------------------- items
def _item_qty_ok(ctx: _Ctx, item: dict) -> Decimal | None:
    q = D_opt(item.get("quantity"))
    if q is None:
        ctx.exc("QUANTITY_MISSING", "High", f"BOQ {item['item_key']}: quantity missing.", item_key=item["item_key"])
    return q


def _price_allowance(ctx: _Ctx, item: dict, ic: ItemCost) -> None:
    ik = item["item_key"]
    amt = D_opt(item.get("pricing_amount"))
    st = item.get("pricing_status")
    line = CostLine(item_key=ik, assembly_code=None, assembly_version=None, path=ik, line_ref=f"{ik}#SUM", kind="allowance",
                    resource_id=None, description=item.get("description") or "", quantity=ONE, unit="ls",
                    cost_code=item.get("cost_code"))
    ctx.lines.append(line)
    if amt is None:
        line.flags.append("AMOUNT_MISSING")
        ctx.exc("ALLOWANCE_AMOUNT_MISSING", "High", f"{ik}: {item['pricing_method']} has no amount.", item_key=ik)
        return
    usable = st in (Status.APPROVED.value, Status.PROVISIONAL.value) or (ctx.inp.include_unapproved and st == Status.PENDING.value)
    if not usable:
        line.flags.append("ALLOWANCE_NOT_APPROVED")
        ctx.exc("ALLOWANCE_NOT_APPROVED", "High", f"{ik}: {item['pricing_method'].replace('_', ' ')} is '{st}', not approved.",
                item_key=ik, exposure=amt)
        line.indicative_amount = amt
        return
    fx, err = _fx(ctx, item.get("pricing_currency") or ctx.currency)
    if fx is None:
        ctx.exc("FX_MISSING", "High", err, item_key=ik)
        return
    line.amount = quantize(amt * fx, ctx.money_dp)
    line.eligibility = PROVISIONAL if st == Status.PROVISIONAL.value else ELIGIBLE
    line.is_provisional = st == Status.PROVISIONAL.value or st == Status.PENDING.value
    line.rate_type = "Estimator-Entered Allowance"
    line.rate_status = st
    line.basis = f"{item['pricing_method'].replace('_', ' ')} lump sum {amt} {item.get('pricing_currency') or ctx.currency} ({item.get('pricing_note') or ''})"
    if line.is_provisional:
        line.flags.append("PROVISIONAL_ALLOWANCE")


def compute_direct_cost(inp: EstimateInputs) -> DirectCostResult:
    ctx = _Ctx(inp)
    items: dict[str, ItemCost] = {}
    for item in inp.items:
        if item.get("item_type", "item") != "item":
            continue
        if item.get("status_in_revision") not in (None, "Current"):
            ctx.exc("ITEM_MISSING_IN_REVISION", "Medium", f"{item['item_key']} absent from latest BOQ revision; still priced.",
                    item_key=item["item_key"])
        ik = item["item_key"]
        qty = D_opt(item.get("quantity"))
        ic = ItemCost(ik, item.get("item_code"), item.get("description"), item.get("unit"), qty, item.get("cost_code"),
                      item.get("pricing_method") or "unpriced")
        items[ik] = ic
        start = len(ctx.lines)
        method = ic.pricing_method
        if method == "unpriced":
            ctx.exc("UNPRICED_ITEM", "High", f"BOQ {ik} has no pricing method/assembly mapping.", item_key=ik)
        elif method == "excluded":
            ic.complete = True
        elif method == "assembly":
            _price_assembly_item(ctx, item, ic, qty)
        elif method == "subcontract_lump":
            _price_subcontract_item(ctx, item, ic, qty)
        elif method == "takeoff_resources":
            _price_takeoff_item(ctx, item, ic)
        elif method in ("provisional_sum", "prime_cost_sum", "allowance"):
            _price_allowance(ctx, item, ic)
        new = ctx.lines[start:]
        ic.lines = len(new)
        ic.direct_cost = sum((l.amount for l in new if l.amount is not None), ZERO)
        ic.unpriced_lines = sum(1 for l in new if l.amount is None)
        ic.indicative_exposure = sum((l.indicative_amount for l in new if l.amount is None and l.indicative_amount is not None), ZERO)
        ic.unknown_exposure_lines = sum(1 for l in new if l.amount is None and l.indicative_amount is None)
        ic.provisional = any(l.is_provisional for l in new)
        ic.synthetic = any(l.is_synthetic for l in new)
        if method not in ("unpriced", "excluded"):
            ic.complete = bool(new) and ic.unpriced_lines == 0 and not any(
                e.item_key == ik and e.code in _BLOCKING for e in ctx.exceptions)
    _plant_mobilisation(ctx, items)
    _plant_hire_terms(ctx, items)
    total = sum((l.amount for l in ctx.lines if l.amount is not None), ZERO)
    return DirectCostResult(
        lines=ctx.lines, items=items, exceptions=ctx.exceptions, direct_cost_total=total,
        used_assumptions=ctx.used_assumptions, used_rates=ctx.used_rates,
        provisional_used=any(l.is_provisional for l in ctx.lines), synthetic_used=any(l.is_synthetic for l in ctx.lines),
        money_dp=ctx.money_dp, qty_dp=ctx.qty_dp, currency=ctx.currency, include_unapproved=inp.include_unapproved)


_BLOCKING = {"FACTOR_MISSING", "ASSUMPTION_MISSING", "ASSUMPTION_NOT_APPROVED", "UNIT_CONVERSION", "UNKNOWN_RESOURCE",
             "CHILD_ASSEMBLY_UNAVAILABLE", "CIRCULAR_ASSEMBLY", "DOUBLE_COUNT_SUBCONTRACT", "NO_PRODUCTIVITY_BASIS",
             "ASSEMBLY_UNAVAILABLE", "QUANTITY_MISSING", "UNIT_MISSING", "MAPPING_NOT_APPROVED", "UNSUPPORTED_LINE",
             "ALLOWANCE_NOT_APPROVED", "ALLOWANCE_AMOUNT_MISSING", "ITEM_UNIT_INCOMPATIBLE", "WASTE_INVALID",
             "ASSUMPTION_NOT_NUMERIC", "OT_NEEDS_BUILDUP", "OT_INVALID", "OUTPUT_INVALID", "PLANT_BUILD_INVALID",
             "PRODUCTIVE_HOURS_INVALID", "SHIFT_HOURS_INVALID", "UTILISATION_INVALID", "LABOUR_UNIT", "TAKEOFF_NOT_APPROVED"}


def _price_assembly_item(ctx: _Ctx, item: dict, ic: ItemCost, qty: Decimal | None) -> None:
    inp, ik = ctx.inp, item["item_key"]
    code = item.get("assembly_code")
    if not code:
        ctx.exc("UNPRICED_ITEM", "High", f"BOQ {ik}: pricing method is assembly but none is mapped.", item_key=ik)
        return
    ms = item.get("mapping_status")
    if ms != Status.APPROVED.value and not (inp.include_unapproved and ms in ("Suggested", Status.PENDING.value)):
        ctx.exc("MAPPING_NOT_APPROVED", "High", f"BOQ {ik}: assembly mapping is '{ms}', not approved.", item_key=ik)
        return
    asm = inp.assemblies.get(code)
    if asm is None:
        ctx.exc("ASSEMBLY_UNAVAILABLE", "High", f"BOQ {ik}: assembly {code} has no approved version.", item_key=ik)
        return
    if qty is None:
        ctx.exc("QUANTITY_MISSING", "High", f"BOQ {ik}: quantity missing.", item_key=ik)
        return
    if not item.get("unit"):
        ctx.exc("UNIT_MISSING", "High", f"BOQ {ik}: unit is missing/ambiguous; correct it (approved change) before pricing.",
                item_key=ik)
        return
    try:
        qa = qty * inp.units.factor(item["unit"], asm.unit)
    except ValidationFailed as e:
        ctx.exc("ITEM_UNIT_INCOMPATIBLE", "High", f"BOQ {ik}: unit {item['unit']} vs assembly unit {asm.unit}: {e.message}", item_key=ik)
        return
    if asm.is_synthetic:
        pass
    _expand(ctx, item, asm, qa, asm.code, (), 0)


def _price_subcontract_item(ctx: _Ctx, item: dict, ic: ItemCost, qty: Decimal | None) -> None:
    ik = item["item_key"]
    rid = item.get("pricing_resource_id")
    res = ctx.inp.resources.get(rid) if rid else None
    if res is None or qty is None:
        ctx.exc("UNPRICED_ITEM", "High", f"BOQ {ik}: subcontract resource/quantity missing.", item_key=ik)
        return
    unit = item.get("unit")
    q = qty
    if unit and unit != res["unit"]:
        try:
            q = qty * ctx.inp.units.factor(unit, res["unit"])
        except ValidationFailed as e:
            ctx.exc("ITEM_UNIT_INCOMPATIBLE", "High", f"BOQ {ik}: {e.message}", item_key=ik)
            return
    line = CostLine(item_key=ik, assembly_code=None, assembly_version=None, path=ik, line_ref=f"{ik}#SUBCON",
                    kind="subcontract", resource_id=rid, description=res["description"], quantity=q, unit=res["unit"],
                    cost_code=item.get("cost_code"), subcontract_includes={"labour": True, "material": True, "plant": True})
    ctx.lines.append(line)
    line.basis = f"subcontract: qty {q} {res['unit']} x approved subcontract rate"
    _price_line(ctx, line, rid, q, res["unit"])
    if line.amount is not None:
        line.basis += f" {line.rate} => {line.amount}"


def _price_takeoff_item(ctx: _Ctx, item: dict, ic: ItemCost) -> None:
    ik = item["item_key"]
    tl = ctx.inp.takeoff.get(ik, [])
    if not tl:
        ctx.exc("UNPRICED_ITEM", "High", f"BOQ {ik}: takeoff resource lines missing.", item_key=ik)
        return
    st = item.get("pricing_status")
    if any(t.get("origin") == "mto" for t in tl) and not (st in (Status.APPROVED.value, Status.PROVISIONAL.value)
                                                          or (ctx.inp.include_unapproved and st == Status.PENDING.value)):
        ctx.exc("TAKEOFF_NOT_APPROVED", "High", f"BOQ {ik}: quantities derived by a take-off template are '{st}' - a person must approve the pricing decision.", item_key=ik)
        return
    for i, t in enumerate(tl, 1):
        res = ctx.inp.resources.get(t["resource_id"])
        if res is None:
            ctx.exc("UNKNOWN_RESOURCE", "High", f"{ik}: resource {t['resource_id']} unknown.", item_key=ik)
            continue
        q = D(t["quantity"])
        if t.get("unit") and t["unit"] != res["unit"]:
            try:
                q = q * ctx.inp.units.factor(t["unit"], res["unit"])
            except ValidationFailed as e:
                ctx.exc("UNIT_CONVERSION", "High", f"{ik}: {e.message}", item_key=ik, resource_id=res["id"])
                continue
        line = CostLine(item_key=ik, assembly_code=None, assembly_version=None, path=ik, line_ref=f"{ik}#T{i}",
                        kind=res["resource_type"], resource_id=res["id"], description=res["description"], quantity=q,
                        unit=res["unit"], cost_code=item.get("cost_code"))
        line.basis = (f"take-off template quantity {q} {res['unit']} ({t.get('notes')})" if t.get("origin") == "mto"
                      else f"takeoff-supplied resource quantity {q} {res['unit']} (source row {t.get('source_row')})")
        ctx.lines.append(line)
        if res["resource_type"] == "labour" and res["unit"] == "hr":
            line.hours = q
            if t.get("origin") == "mto":                                      # derived labour norms are adjusted like assembly labour
                q = _adjust_hours(ctx, line, q, f"{ik}#T{i}")
                line.hours = line.quantity = q
        _price_line(ctx, line, res["id"], q, res["unit"])
        if line.amount is not None:
            line.basis += f" x rate {line.rate} => {line.amount}"


def _plant_mobilisation(ctx: _Ctx, items: dict[str, ItemCost]) -> None:
    """Once per distinct plant resource used: mobilisation + demobilisation lumps from its approved rate build-up."""
    seen: set[str] = set()
    for l in list(ctx.lines):
        if l.kind != "plant" or l.amount is None or l.resource_id in seen or l.rate_id is None:
            continue
        seen.add(l.resource_id)
        rate = next((r for r in ctx.inp.rates.get(l.resource_id, []) if r["id"] == l.rate_id), None)
        comps = jload((rate or {}).get("components_json"), None)
        if not comps:
            continue
        mob = (D_opt(comps.get("mobilisation_lump")) or ZERO) + (D_opt(comps.get("demobilisation_lump")) or ZERO)
        if mob > 0:
            fxv, _ = _fx(ctx, rate["currency"])
            if fxv is None:
                continue
            ml = CostLine(item_key=l.item_key, assembly_code=l.assembly_code, assembly_version=l.assembly_version,
                          path=l.path, line_ref=f"MOB:{l.resource_id}", kind="plant_mobilisation", resource_id=l.resource_id,
                          description=f"Mobilisation/demobilisation: {l.description}", quantity=ONE, unit="ls",
                          rate=mob * fxv, rate_id=rate["id"], eligibility=l.eligibility, rate_type=rate["rate_type"],
                          rate_status=rate["status"], is_provisional=l.is_provisional, is_synthetic=l.is_synthetic,
                          cost_code=l.cost_code,
                          basis="mobilisation + demobilisation lump sums from the plant rate build-up, once per plant item")
            ml.amount = quantize(mob * fxv, ctx.money_dp)
            ctx.lines.append(ml)
            ic = items.get(l.item_key)
            if ic:
                ic.direct_cost += ml.amount
                ic.lines += 1


def _plant_hire_terms(ctx: _Ctx, items: dict[str, ItemCost]) -> None:
    """Governed minimum-hire top-up and standby for plant resources actually used, priced at that resource's approved rate.
    top-up = max(0, min_hire_qty - sum(charged plant qty)) ; standby = standby_qty x rate x standby_pct/100. Only user-supplied terms apply."""
    for p in sorted(ctx.inp.params.get("plant_hire_terms", []), key=lambda p: p["code"]):
        d = p["data"]
        rid = d["resource_id"]
        used = [l for l in ctx.lines if l.kind == "plant" and l.resource_id == rid and l.amount is not None]
        if not used:
            continue
        ref_line = used[0]
        total_qty = sum((l.quantity or ZERO for l in used), ZERO)
        rate = ref_line.rate
        add: list[tuple[str, Decimal, Decimal, str]] = []
        shortfall = max(ZERO, D(d.get("min_hire_qty") or "0") - total_qty)
        if shortfall > 0:
            add.append(("plant_min_hire_top_up", shortfall, ONE,
                        f"minimum hire {d['min_hire_qty']} {ref_line.unit} (terms {p['code']} v{p['version']}) - charged {total_qty} => top-up {shortfall}"))
        sq = D(d.get("standby_qty") or "0")
        if sq > 0:
            add.append(("plant_standby", sq, D(d["standby_pct_of_rate"]) / 100,
                        f"standby {sq} {ref_line.unit} at {d['standby_pct_of_rate']}% of rate (terms {p['code']} v{p['version']})"))
        for kind, qty, share, why in add:
            ln = CostLine(item_key=ref_line.item_key, assembly_code=ref_line.assembly_code, assembly_version=ref_line.assembly_version,
                          path=ref_line.path, line_ref=f"{kind.upper()}:{rid}", kind=kind, resource_id=rid,
                          description=f"{'Minimum-hire top-up' if kind == 'plant_min_hire_top_up' else 'Standby'}: {ref_line.description}",
                          quantity=qty, unit=ref_line.unit, rate=rate * share, rate_id=ref_line.rate_id, eligibility=ref_line.eligibility,
                          rate_type=ref_line.rate_type, rate_status=ref_line.rate_status, rate_currency=ref_line.rate_currency,
                          is_provisional=ref_line.is_provisional, is_synthetic=ref_line.is_synthetic or bool(p.get("is_synthetic")),
                          cost_code=ref_line.cost_code, basis=why)
            ln.amount = quantize(qty * rate * share, ctx.money_dp)
            ln.basis += f" => {ln.amount}"
            if p.get("unapproved"):
                ln.flags.append("UNAPPROVED_PLANT_TERMS")
                ctx.exc("UNAPPROVED_PLANT_TERMS", "High", f"Plant hire terms {p['code']} v{p['version']} are '{p['status']}'.", item_key=ln.item_key,
                        resource_id=rid)
            ctx.lines.append(ln)
            ic = items.get(ln.item_key)
            if ic:
                ic.direct_cost += ln.amount
                ic.lines += 1
