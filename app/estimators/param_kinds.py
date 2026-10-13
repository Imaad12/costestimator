"""Kinds of governed parameters: user-supplied numeric inputs that must be validated, versioned and human-approved before use.

Pure module (no DB). A validator receives the raw dict and returns a normalised dict of JSON-safe values (Decimals as exact text) or raises
ValidationFailed. NO kind has default values - the library ships empty; every number comes from a person and an approval.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Callable

from ..core.errors import ValidationFailed
from ..models.enums import Role

E, P, C, A = Role.ESTIMATOR.value, Role.PROCUREMENT.value, Role.COMMERCIAL.value, Role.ADMIN.value


def dec(data: dict, key: str, *, required: bool = True, gt: str | None = None, ge: str | None = None, le: str | None = None) -> str | None:
    """Exact-decimal field as normalised text; None when optional and absent."""
    v = data.get(key)
    if v in (None, ""):
        if required:
            raise ValidationFailed(f"'{key}' is required.", code="PARAM_FIELD")
        return None
    try:
        d = Decimal(str(v).strip())
    except InvalidOperation:
        raise ValidationFailed(f"'{key}' must be a number (got {v!r}).", code="PARAM_FIELD")
    if not d.is_finite():
        raise ValidationFailed(f"'{key}' must be finite.", code="PARAM_FIELD")
    if gt is not None and not d > Decimal(gt):
        raise ValidationFailed(f"'{key}' must be > {gt}.", code="PARAM_FIELD")
    if ge is not None and not d >= Decimal(ge):
        raise ValidationFailed(f"'{key}' must be >= {ge}.", code="PARAM_FIELD")
    if le is not None and not d <= Decimal(le):
        raise ValidationFailed(f"'{key}' must be <= {le}.", code="PARAM_FIELD")
    return format(d.normalize(), "f") if d != 0 else "0"


def text(data: dict, key: str, *, required: bool = True, choices: tuple | None = None) -> str | None:
    v = data.get(key)
    if v in (None, ""):
        if required:
            raise ValidationFailed(f"'{key}' is required.", code="PARAM_FIELD")
        return None
    v = str(v).strip()
    if choices and v not in choices:
        raise ValidationFailed(f"'{key}' must be one of {list(choices)} (got {v!r}).", code="PARAM_FIELD")
    return v


def _no_extra(data: dict, allowed: set[str], kind: str) -> None:
    extra = set(data) - allowed
    if extra:
        raise ValidationFailed(f"Unknown field(s) for {kind}: {sorted(extra)}. Allowed: {sorted(allowed)}.", code="PARAM_FIELD")


@dataclass(frozen=True)
class ParamKind:
    name: str
    label: str
    validate: Callable[[dict], dict]
    approvers: frozenset[str]
    description: str = ""


KINDS: dict[str, ParamKind] = {}


def kind(name: str, label: str, approvers: set[str], description: str = ""):
    def deco(fn):
        KINDS[name] = ParamKind(name, label, fn, frozenset(approvers), description)
        return fn
    return deco


PRODUCTIVITY_CATEGORIES = ("height", "congestion", "climate_heat", "shift_pattern", "remote_site", "learning_curve", "access_restriction",
                           "permit_to_work", "weather", "other")


@kind("productivity_factor", "Productivity adjustment factor", {E, C, A},
      "Multiplier on labour hours for conditions such as work at height, congestion, heat, shift pattern, remote site or learning curve. "
      "Value and basis come from the company's own records or an approved source - none is supplied.")
def _productivity(d: dict) -> dict:
    _no_extra(d, {"category", "factor", "scope_cost_prefix", "scope_wbs", "applies_to"}, "productivity_factor")
    out = {"category": text(d, "category", choices=PRODUCTIVITY_CATEGORIES), "factor": dec(d, "factor", gt="0"),
           "scope_cost_prefix": text(d, "scope_cost_prefix", required=False), "scope_wbs": text(d, "scope_wbs", required=False),
           "applies_to": text(d, "applies_to", required=False, choices=("labour",)) or "labour"}
    return out


@kind("plant_hire_terms", "Plant minimum-hire / standby terms", {P, C, A},
      "Per plant resource: minimum chargeable quantity (in the resource's rate unit) over the project and a standby quantity charged at a "
      "percentage of the approved rate. Values come from the hire contract or quotation.")
def _plant_terms(d: dict) -> dict:
    _no_extra(d, {"resource_id", "min_hire_qty", "standby_qty", "standby_pct_of_rate"}, "plant_hire_terms")
    out = {"resource_id": text(d, "resource_id"), "min_hire_qty": dec(d, "min_hire_qty", required=False, ge="0") or "0",
           "standby_qty": dec(d, "standby_qty", required=False, ge="0") or "0",
           "standby_pct_of_rate": dec(d, "standby_pct_of_rate", required=False, ge="0", le="100")}
    if Decimal(out["standby_qty"]) > 0 and out["standby_pct_of_rate"] is None:
        raise ValidationFailed("standby_qty > 0 requires standby_pct_of_rate (from the hire terms).", code="PARAM_FIELD")
    return out


@kind("calendar", "Project calendar", {E, C, A},
      "Start date, working weekdays (0=Mon..6=Sun) and non-working dates. Working weekdays and holidays are entered by the estimator from the "
      "contract / client calendar - none are assumed.")
def _calendar(d: dict) -> dict:
    _no_extra(d, {"start_date", "work_weekdays", "holidays", "hours_per_day"}, "calendar")
    sd = text(d, "start_date")
    try:
        date.fromisoformat(sd)
    except ValueError:
        raise ValidationFailed("start_date must be YYYY-MM-DD.", code="PARAM_FIELD")
    wd = d.get("work_weekdays")
    if isinstance(wd, str):
        wd = [x for x in re.split(r"[,\s]+", wd) if x != ""]
    try:
        wd = sorted({int(x) for x in (wd or [])})
    except (TypeError, ValueError):
        raise ValidationFailed("work_weekdays must be integers 0..6.", code="PARAM_FIELD")
    if not wd or any(x < 0 or x > 6 for x in wd):
        raise ValidationFailed("work_weekdays must list at least one weekday 0..6 (0=Monday).", code="PARAM_FIELD")
    hol = d.get("holidays") or []
    if isinstance(hol, str):
        hol = [x for x in re.split(r"[,\s]+", hol) if x]
    for h in hol:
        try:
            date.fromisoformat(str(h))
        except ValueError:
            raise ValidationFailed(f"holiday {h!r} must be YYYY-MM-DD.", code="PARAM_FIELD")
    return {"start_date": sd, "work_weekdays": wd, "holidays": sorted({str(h) for h in hol}),
            "hours_per_day": dec(d, "hours_per_day", required=False, gt="0")}


@kind("mto_factor", "Take-off derivation factor", {E, C, A},
      "Quantity of one resource per unit of a human-measured driver (e.g. welder hours per joint, paint litres per m2) for one slot of a take-off "
      "template. The factor, any waste allowance and the resource come from company records; none are supplied.")
def _mto_factor(d: dict) -> dict:
    _no_extra(d, {"template", "slot", "resource_id", "factor", "waste_pct", "basis"}, "mto_factor")
    return {"template": text(d, "template"), "slot": text(d, "slot"), "resource_id": text(d, "resource_id"), "factor": dec(d, "factor", ge="0"),
            "waste_pct": dec(d, "waste_pct", required=False, ge="0"), "basis": text(d, "basis", required=False)}


@kind("classification_scheme", "Estimate classification scheme", {C, A},
      "Classes with definition-maturity bands and expected accuracy ranges taken from the scheme the company or client works to (e.g. an AACE-type scheme "
      "or a client's own). The software holds no scheme; the numbers and the source document are entered here and approved.")
def _classification_scheme(d: dict) -> dict:
    _no_extra(d, {"name", "source_document", "classes"}, "classification_scheme")
    classes = d.get("classes")
    if not isinstance(classes, list) or not classes:
        raise ValidationFailed("classes must be a non-empty list.", code="PARAM_FIELD")
    out, seen = [], set()
    for c in classes:
        _no_extra(c, {"class_id", "name", "min_definition_pct", "max_definition_pct", "low_pct", "high_pct", "criteria"}, "class")
        cid = text(c, "class_id")
        if cid in seen:
            raise ValidationFailed(f"Duplicate class_id {cid}.", code="PARAM_FIELD")
        seen.add(cid)
        row = {"class_id": cid, "name": text(c, "name", required=False), "min_definition_pct": dec(c, "min_definition_pct", ge="0", le="100"),
               "max_definition_pct": dec(c, "max_definition_pct", ge="0", le="100"), "low_pct": dec(c, "low_pct"), "high_pct": dec(c, "high_pct"),
               "criteria": text(c, "criteria", required=False)}
        if Decimal(row["min_definition_pct"]) >= Decimal(row["max_definition_pct"]):
            raise ValidationFailed(f"Class {cid}: min_definition_pct must be below max_definition_pct.", code="PARAM_FIELD")
        if Decimal(row["low_pct"]) > Decimal(row["high_pct"]):
            raise ValidationFailed(f"Class {cid}: low_pct must not exceed high_pct.", code="PARAM_FIELD")
        out.append(row)
    srt = sorted(out, key=lambda r: Decimal(r["min_definition_pct"]))
    for a, b in zip(srt, srt[1:]):
        if Decimal(a["max_definition_pct"]) > Decimal(b["min_definition_pct"]):
            raise ValidationFailed(f"Classes {a['class_id']} and {b['class_id']} overlap in definition bands.", code="PARAM_FIELD")
    return {"name": text(d, "name"), "source_document": text(d, "source_document"), "classes": out}


@kind("maturity_input", "Design maturity input", {E, C, A},
      "The estimator's statement of project definition maturity (percent of project definition and deliverable status) with its basis. Measured facts are "
      "reported separately; this value is a human judgement and is shown as such.")
def _maturity(d: dict) -> dict:
    _no_extra(d, {"definition_pct", "basis", "deliverables_status"}, "maturity_input")
    return {"definition_pct": dec(d, "definition_pct", ge="0", le="100"), "basis": text(d, "basis"), "deliverables_status": text(d, "deliverables_status", required=False)}


@kind("landed_cost_terms", "Landed-cost / logistics terms", {P, C, A},
      "Ordered components (freight, insurance, duty, clearance, port charges, haulage ...) that turn a supplier base price into a delivered cost, with the "
      "percentages and amounts taken from quotations, tariffs and forwarder terms. None are supplied.")
def _landed_terms(d: dict) -> dict:
    from .landed_cost import validate_components
    _no_extra(d, {"name", "incoterm", "output_currency", "components", "units_per_shipment", "note"}, "landed_cost_terms")
    return {"name": text(d, "name"), "incoterm": text(d, "incoterm", required=False), "output_currency": text(d, "output_currency"),
            "components": validate_components(d.get("components")), "units_per_shipment": dec(d, "units_per_shipment", required=False, gt="0"), "note": text(d, "note", required=False)}


@kind("labour_statutory", "Employer statutory / mobilisation labour cost rule", {C, A},
      "One labour on-cost rule (levy, social insurance, end-of-service accrual, visa/iqama, medical ...) with its basis and value from the applicable regulation or "
      "policy. The software holds no rule values.")
def _labour_statutory(d: dict) -> dict:
    from .labour_costs import BASES
    _no_extra(d, {"name", "basis", "value", "applies_to", "authority_ref"}, "labour_statutory")
    return {"name": text(d, "name"), "basis": text(d, "basis", choices=BASES), "value": dec(d, "value", ge="0"),
            "applies_to": text(d, "applies_to", required=False, choices=("all", "saudi", "expat")) or "all", "authority_ref": text(d, "authority_ref", required=False)}


@kind("national_workforce_target", "National-workforce share target", {C, A},
      "Required share (percent) of nationals in the workforce under the applicable programme or contract, with the source. The software holds no targets.")
def _nw_target(d: dict) -> dict:
    _no_extra(d, {"name", "required_pct", "authority_ref"}, "national_workforce_target")
    return {"name": text(d, "name"), "required_pct": dec(d, "required_pct", ge="0", le="100"), "authority_ref": text(d, "authority_ref")}


@kind("hedge_cover", "Currency hedge cover", {C, A},
      "Share of the exposure in one currency that is covered by a hedge (forward, natural hedge, price-in-SAR clause), with the instrument and its source.")
def _hedge(d: dict) -> dict:
    _no_extra(d, {"currency", "cover_pct", "instrument"}, "hedge_cover")
    return {"currency": text(d, "currency"), "cover_pct": dec(d, "cover_pct", ge="0", le="100"), "instrument": text(d, "instrument")}


@kind("escalation_profile", "Escalation profile", {C, A},
      "Annual escalation percentage applied from a base date to a scope (cost kind or cost-code prefix), with the basis for the figure. The percentage is a "
      "decision of the company; official indices are shown beside it as information only.")
def _escalation(d: dict) -> dict:
    _no_extra(d, {"name", "annual_pct", "base_date", "scope_kind", "scope_cost_prefix", "basis"}, "escalation_profile")
    bd = text(d, "base_date")
    try:
        date.fromisoformat(bd)
    except ValueError:
        raise ValidationFailed("base_date must be YYYY-MM-DD.", code="PARAM_FIELD")
    return {"name": text(d, "name"), "annual_pct": dec(d, "annual_pct"), "base_date": bd,
            "scope_kind": text(d, "scope_kind", required=False, choices=("labour", "material", "plant", "equipment", "subcontract", "allowance", "all")) or "all",
            "scope_cost_prefix": text(d, "scope_cost_prefix", required=False), "basis": text(d, "basis")}


@kind("range_item", "Cost uncertainty range", {E, C, A},
      "Three-point range (low / most likely / high, in project currency) for an element of the base estimate whose cost is uncertain, with its basis. "
      "'Most likely' is assumed to be the value already in the estimate; the simulation adds the deviation from it.")
def _range_item(d: dict) -> dict:
    _no_extra(d, {"name", "low", "likely", "high", "basis"}, "range_item")
    out = {"name": text(d, "name"), "low": dec(d, "low", ge="0"), "likely": dec(d, "likely", ge="0"), "high": dec(d, "high", ge="0"), "basis": text(d, "basis")}
    if not (Decimal(out["low"]) <= Decimal(out["likely"]) <= Decimal(out["high"])):
        raise ValidationFailed("Need low <= most likely <= high.", code="PARAM_FIELD")
    return out


@kind("payment_terms", "Contract payment, bond and financing terms", {C, A},
      "Advance, retention, release, certification/payment lags, supplier credit, performance-bond and financing terms from the contract, bank and supplier "
      "terms. Every field is required (zero is allowed) so that nothing is silently assumed.")
def _payment_terms(d: dict) -> dict:
    from .cashflow import TERM_KEYS
    _no_extra(d, set(TERM_KEYS) | {"name"}, "payment_terms")
    out = {"name": text(d, "name")}
    for k in TERM_KEYS:
        if k.endswith("_months"):
            v = dec(d, k, ge="0", le="120")
            if Decimal(v) != Decimal(v).to_integral_value():
                raise ValidationFailed(f"'{k}' must be a whole number of months.", code="PARAM_FIELD")
            out[k] = v
        else:
            out[k] = dec(d, k, ge="0", le="100")
    return out


@kind("evaluation_criteria", "Bid evaluation criteria", {P, C, A},
      "Criteria, weights (summing to 100 with the price weight), pass/fail gates and the scoring scale for evaluating bids or prequalifying vendors. "
      "Taken from the tender evaluation plan; none are supplied by the software.")
def _eval_criteria(d: dict) -> dict:
    from .bid_eval import validate_criteria
    _no_extra(d, {"name", "stage", "scale_max", "criteria", "price_weight"}, "evaluation_criteria")
    v = validate_criteria(d)
    return {"name": text(d, "name"), "stage": text(d, "stage", choices=("prequalification", "bid")), "scale_max": dec(d, "scale_max", gt="0"), **v}


@kind("variation_markup", "Variation pricing markup", {C, A},
      "Overhead and profit percentages applied to the direct cost of a priced variation, from the contract's variation clause or company policy.")
def _var_markup(d: dict) -> dict:
    _no_extra(d, {"overhead_pct", "profit_pct", "contract_clause"}, "variation_markup")
    return {"overhead_pct": dec(d, "overhead_pct", ge="0"), "profit_pct": dec(d, "profit_pct", ge="0"), "contract_clause": text(d, "contract_clause")}


@kind("contract_baseline", "Awarded contract baseline", {C, A},
      "The contract sum as awarded (not the estimate): amount, currency, award date and contract reference. Variations are measured against it.")
def _baseline(d: dict) -> dict:
    _no_extra(d, {"contract_sum", "currency", "award_date", "reference"}, "contract_baseline")
    ad = text(d, "award_date")
    try:
        date.fromisoformat(ad)
    except ValueError:
        raise ValidationFailed("award_date must be YYYY-MM-DD.", code="PARAM_FIELD")
    return {"contract_sum": dec(d, "contract_sum", gt="0"), "currency": text(d, "currency"), "award_date": ad, "reference": text(d, "reference")}


@kind("benchmark_range", "Reasonableness benchmark range", {E, C, A},
      "A historical or published range used only to flag outliers: unit cost per BOQ unit for a cost-code prefix, share of direct cost by cost kind, or hours per "
      "unit. The range, its currency/unit and its source come from the company's records; none are supplied.")
def _benchmark(d: dict) -> dict:
    _no_extra(d, {"name", "metric", "cost_prefix", "unit", "kind", "low", "high", "currency", "source_note"}, "benchmark_range")
    m = text(d, "metric", choices=("item_unit_cost", "share_of_direct", "hours_per_unit"))
    out = {"name": text(d, "name"), "metric": m, "cost_prefix": text(d, "cost_prefix", required=False), "unit": text(d, "unit", required=False),
           "kind": text(d, "kind", required=False, choices=("labour", "material", "plant", "equipment", "subcontract", "allowance")),
           "low": dec(d, "low", ge="0"), "high": dec(d, "high", ge="0"), "currency": text(d, "currency", required=False), "source_note": text(d, "source_note")}
    if Decimal(out["low"]) > Decimal(out["high"]):
        raise ValidationFailed("low must not exceed high.", code="PARAM_FIELD")
    if m in ("item_unit_cost", "hours_per_unit") and not (out["cost_prefix"] and out["unit"]):
        raise ValidationFailed(f"{m} needs cost_prefix and unit.", code="PARAM_FIELD")
    if m == "item_unit_cost" and not out["currency"]:
        raise ValidationFailed("item_unit_cost needs the currency of the range.", code="PARAM_FIELD")
    if m == "share_of_direct":
        if not out["kind"]:
            raise ValidationFailed("share_of_direct needs kind (labour / material / plant / ...).", code="PARAM_FIELD")
        if Decimal(out["high"]) > 100:
            raise ValidationFailed("a share is a percentage between 0 and 100.", code="PARAM_FIELD")
    return out


@kind("reserve_rule", "Reserve / provision rule", {C, A},
      "A percentage of a stated base kept as a provision (warranty / defects liability, commissioning reserve, temporary works ...), with the basis. "
      "The percentage comes from company policy or contract terms; none is supplied.")
def _reserve(d: dict) -> dict:
    _no_extra(d, {"name", "base", "pct", "category", "basis"}, "reserve_rule")
    return {"name": text(d, "name"), "base": text(d, "base", choices=("direct", "direct_indirect", "selling_price")), "pct": dec(d, "pct", ge="0", le="100"),
            "category": text(d, "category"), "basis": text(d, "basis")}


@kind("engineering_basis", "Engineering / design effort basis", {E, C, A},
      "Deliverables or work packages per discipline with hours each and the labour resource they are charged at. Hours per deliverable come from company records "
      "or the engineering contractor's proposal; none are supplied.")
def _eng_basis(d: dict) -> dict:
    _no_extra(d, {"discipline", "deliverable", "count", "hours_each", "resource_id", "basis"}, "engineering_basis")
    return {"discipline": text(d, "discipline"), "deliverable": text(d, "deliverable"), "count": dec(d, "count", ge="0"), "hours_each": dec(d, "hours_each", ge="0"),
            "resource_id": text(d, "resource_id"), "basis": text(d, "basis")}


@kind("overhead_pool", "Home-office / overhead pool", {C, A},
      "An annual company cost pool and the annual base it is recovered over (e.g. annual turnover or annual labour hours), so a project share can be computed "
      "from the project's own base and duration. Both figures come from the company's accounts.")
def _pool(d: dict) -> dict:
    _no_extra(d, {"name", "annual_cost", "annual_base", "base_kind", "basis"}, "overhead_pool")
    return {"name": text(d, "name"), "annual_cost": dec(d, "annual_cost", ge="0"), "annual_base": dec(d, "annual_base", gt="0"),
            "base_kind": text(d, "base_kind", choices=("direct_cost", "labour_hours", "selling_price")), "basis": text(d, "basis")}
