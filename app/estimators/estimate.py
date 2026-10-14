"""Estimate orchestration: direct -> indirect -> commercial -> pricing schedule, plus state & fingerprint."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from typing import Any

from ..core.errors import ValidationFailed
from ..core.money import ZERO, D_opt, quantize, to_text
from ..core.timeutil import parse_date
from ..database import Database, jload, rows_to_dicts
from ..models.enums import EstimateState, Status
from ..services import assumptions as assumption_service
from . import commercial as com
from .context import load_inputs
from .direct_cost import compute_direct_cost
from .indirect import IndirectResult, compute_indirects
from .pricing_schedule import PricingSchedule, build_schedule
from .types import DirectCostResult, EngineException, EstimateInputs


@dataclass
class EstimateResult:
    project: dict
    as_of: date
    inputs: EstimateInputs
    direct: DirectCostResult
    indirect: IndirectResult
    commercial: com.CommercialResult | None
    schedule: PricingSchedule | None
    policy: dict | None
    exceptions: list[dict]
    state: str
    blockers: list[str]
    completeness: dict
    flags: dict
    fingerprint: str
    tax_status: dict = field(default_factory=dict)
    extras: "EstimateExtras | None" = None

    def totals(self) -> dict:
        c = self.commercial
        return {
            # unknown is not zero: nothing priced -> None; no indirect item defined -> None
            "direct_cost": self.direct.direct_cost_total if any(i.complete for i in self.direct.items.values() if i.pricing_method != "excluded") or not self.direct.items else None,
            "indirect_cost": self.indirect.total if self.indirect.lines else None,
            "total_cost": c.total_cost if c else None, "selling_price_pre_tax": self.schedule.total_pre_tax if self.schedule else None,
            "commercial_net_price": c.net_price if c else None, "tax": c.tax_total if c else None,
            "final_payable": c.final_payable if c else None,
        }


def _resolve_refs(db: Database, project_id: str, obj: Any, used: list, unresolved: list) -> Any:
    """Replace '@ASMP-...' string values with the project's effective assumption value."""
    if isinstance(obj, dict):
        return {k: _resolve_refs(db, project_id, v, used, unresolved) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_refs(db, project_id, v, used, unresolved) for v in obj]
    if isinstance(obj, str) and obj.startswith("@ASMP-"):
        ra = assumption_service.resolve(db, project_id, obj[1:])
        used.append((ra.id, ra.status))
        if not ra.has_value:
            unresolved.append(f"{ra.id} has no value")
            return None
        return ra.value
    return obj


def _effective_indirects(items: list[dict], include_unapproved: bool) -> list[dict]:
    """One row per code: the latest APPROVED version stays in force while a newer draft/pending revision awaits approval
    (preliminary view uses the newer revision, flagged). Never both (no double count)."""
    by: dict[str, list[dict]] = {}
    for it in items:
        by.setdefault(it["code"], []).append(it)
    out = []
    for code, versions in by.items():
        versions.sort(key=lambda v: v["version"])
        approved = [v for v in versions if v["status"] == Status.APPROVED.value]
        newest = versions[-1]
        if approved and not (include_unapproved and newest["version"] > approved[-1]["version"]):
            out.append(approved[-1])
        else:
            out.append(newest)
    return out


def effective_duration(db: Database, project_id: str, include_unapproved: bool) -> tuple[Decimal | None, str | None, dict | None]:
    return duration_from_rows(rows_to_dicts(db.all("SELECT * FROM project_durations WHERE project_id=? ORDER BY id", (project_id,))), include_unapproved)


def duration_from_rows(rows: list[dict], include_unapproved: bool) -> tuple[Decimal | None, str | None, dict | None]:
    appr = [r for r in rows if r["status"] == "Approved"]
    r = appr[-1] if appr else None
    if r is None and include_unapproved:
        opn = [r for r in rows if r["status"] in ("Pending Review", "Draft")]
        r = opn[-1] if opn else None
    if r is None:
        return None, None, None
    return D_opt(r["months"]), r["status"], dict(r)


def tax_rate_for(db: Database, code: str, as_of: date, include_unapproved: bool) -> tuple[Decimal | None, str, str | None]:
    """(rate, status, note). Only Approved categories valid on `as_of` give a rate unless include_unapproved."""
    return tax_rate_from_rows(rows_to_dicts(db.all("SELECT * FROM tax_categories WHERE code=?", (code,))), code, as_of, include_unapproved)


def tax_rate_from_rows(all_rows: list[dict], code: str, as_of: date, include_unapproved: bool) -> tuple[Decimal | None, str, str | None]:
    rows = sorted((r for r in all_rows if r["code"] == code), key=lambda r: r["valid_from"] or "", reverse=True)
    for r in rows:
        vf, vt = parse_date(r["valid_from"]), parse_date(r["valid_to"])
        if vf and vf <= as_of and (not vt or vt >= as_of):
            if r["status"] == Status.APPROVED.value:
                return D_opt(r["rate_pct"]), r["status"], None
            if include_unapproved:
                return D_opt(r["rate_pct"]), r["status"], "Tax rate NOT verified/approved (preliminary)."
            return None, r["status"], f"Tax category {code} is '{r['status']}' - must be verified and approved."
    return None, "Missing", f"No tax category {code} valid on {as_of}."


@dataclass
class EstimateExtras:
    """Everything compute_estimate reads besides EstimateInputs - so that a frozen estimate can be replayed from its snapshot with no database."""
    duration_rows: list[dict]
    indirect_rows: list[dict]                 # non-superseded rows, all versions
    policy_row: dict | None
    policy_resolved: dict | None
    policy_used: list[tuple[str, str]]         # (assumption id, status) referenced by the policy
    policy_unresolved: list[str]
    tax_rows: list[dict]


def load_extras(db: Database, inp: EstimateInputs) -> EstimateExtras:
    project_id = inp.project["id"]
    policy_row, policy, used, unresolved = None, None, [], []
    if inp.project.get("commercial_policy_id"):
        r = db.one("SELECT * FROM commercial_policies WHERE id=?", (inp.project["commercial_policy_id"],))
        policy_row = dict(r) if r else None
        if policy_row:
            policy = _resolve_refs(db, project_id, jload(policy_row["config_json"], {}), used, unresolved)
    return EstimateExtras(
        duration_rows=rows_to_dicts(db.all("SELECT * FROM project_durations WHERE project_id=? ORDER BY id", (project_id,))),
        indirect_rows=rows_to_dicts(db.all("SELECT * FROM indirect_items WHERE project_id=? AND status<>'Superseded' ORDER BY code", (project_id,))),
        policy_row=policy_row, policy_resolved=policy, policy_used=[(a, b) for a, b in used], policy_unresolved=list(unresolved),
        tax_rows=rows_to_dicts(db.all("SELECT * FROM tax_categories")))


def compute_estimate(db: Database, project_id: str, *, include_unapproved: bool = False, as_of: date | None = None,
                     assumption_overrides: dict[str, str] | None = None, policy_override: dict | None = None
                     ) -> EstimateResult:
    inp = load_inputs(db, project_id, include_unapproved=include_unapproved, as_of=as_of,
                      assumption_overrides=assumption_overrides)
    return compute_estimate_from(inp, load_extras(db, inp), policy_override=policy_override)


_CACHE_MAX = 16


def compute_estimate_cached(db: Database, project_id: str, *, include_unapproved: bool = False, as_of: date | None = None, **kw) -> EstimateResult:
    """Read-only convenience for pages and reports that recompute the same estimate repeatedly. The cache is valid only while the database connection has seen
    NO row change by this connection (`total_changes`) or any other process (`PRAGMA data_version`), so any approval, import, edit or audit entry invalidates it;
    what-if overrides bypass it. Callers must not mutate the result."""
    if kw.get("assumption_overrides") or kw.get("policy_override") is not None:
        return compute_estimate(db, project_id, include_unapproved=include_unapproved, as_of=as_of, **kw)
    from ..core.timeutil import today
    cache = db.__dict__.setdefault("_estimate_cache", {"changes": -1, "items": {}})
    tc = (db.conn.total_changes, db.scalar("PRAGMA data_version"))
    if cache["changes"] != tc:
        cache["items"].clear()
        cache["changes"] = tc
    key = (project_id, bool(include_unapproved), as_of.isoformat() if as_of else None, today().isoformat())
    hit = cache["items"].get(key)
    if hit is not None:
        return hit
    res = compute_estimate(db, project_id, include_unapproved=include_unapproved, as_of=as_of)
    cache["changes"] = (db.conn.total_changes, db.scalar("PRAGMA data_version"))
    if len(cache["items"]) >= _CACHE_MAX:
        cache["items"].pop(next(iter(cache["items"])))
    cache["items"][key] = res
    return res


def compute_estimate_from(inp: EstimateInputs, ex: EstimateExtras, *, policy_override: dict | None = None) -> EstimateResult:
    """Pure: no database, no clock. Same inputs + extras -> same result and fingerprint."""
    project_id = inp.project["id"]
    include_unapproved = inp.include_unapproved
    direct = compute_direct_cost(inp)
    ek = inp.engine_keys

    def ek_num(key: str) -> Decimal | None:
        av = ek.get(key)
        if av and av.has_value and (av.approved or include_unapproved):
            return D_opt(av.value)
        return None

    dur_months, dur_status, dur_row = duration_from_rows(ex.duration_rows, include_unapproved)
    ind_items = list(ex.indirect_rows)
    wdpm, wdpw = ek_num("calendar.working_days_per_month"), ek_num("calendar.working_days_per_week")
    ind_items = _effective_indirects(ind_items, include_unapproved)
    indirect = compute_indirects(ind_items, direct_cost_total=direct.direct_cost_total, duration_months=dur_months,
                                 duration_status=dur_status, working_days_per_month=wdpm, working_days_per_week=wdpw,
                                 money_dp=direct.money_dp, include_unapproved=include_unapproved,
                                 direct_lines=[dict(item_key=l.item_key, cost_code=l.cost_code, kind=l.kind, amount=l.amount) for l in direct.lines if l.amount is not None])
    exceptions: list[dict] = []

    def add(e: EngineException, src: str):
        exceptions.append(dict(code=e.code, severity=e.severity, message=e.message, item_key=e.item_key,
                               resource_id=e.resource_id, exposure=e.exposure, assumption_id=e.assumption_id,
                               rate_id=e.rate_id, source=src))

    for e in direct.exceptions:
        add(e, "direct")
    for e in indirect.exceptions:
        add(e, "indirect")

    # ---- commercial policy
    policy_row = None
    policy = None
    if policy_override is not None:
        policy, policy_row = policy_override, {"id": None, "name": "override", "status": "Draft", "code": "OVERRIDE", "version": 0}
    elif ex.policy_row:
        policy_row = ex.policy_row
        policy = ex.policy_resolved
        for u in ex.policy_unresolved:
            exceptions.append(dict(code="POLICY_ASSUMPTION_UNRESOLVED", severity="High", message=u, source="commercial"))
        for aid, st in ex.policy_used:
            if st != Status.APPROVED.value:
                exceptions.append(dict(code="POLICY_ASSUMPTION_NOT_APPROVED", severity="High", assumption_id=aid,
                                       message=f"Commercial policy uses assumption {aid} in status '{st}'.", source="commercial"))
            direct.used_assumptions.add(aid)
    commercial = None
    schedule = None
    tax_status: dict = {}
    if policy is None:
        exceptions.append(dict(code="POLICY_MISSING", severity="Critical", source="commercial",
                               message="No commercial policy assigned to the project."))
    else:
        if policy_row and policy_row["status"] != Status.APPROVED.value:
            exceptions.append(dict(code="POLICY_NOT_APPROVED", severity="High", source="commercial",
                                   message=f"Commercial policy '{policy_row['name']}' is '{policy_row['status']}'."))
        probs = com.validate_policy(policy)
        if probs:
            exceptions.append(dict(code="POLICY_INVALID", severity="Critical", source="commercial", message=" ".join(probs)))
        else:
            default_tax = inp.project.get("tax_category") or policy.get("default_tax_category")
            cats = {default_tax or ""}
            for it in inp.items:
                if it.get("tax_category"):
                    cats.add(it["tax_category"])
            rates: dict[str, Decimal | None] = {}
            for c in cats:
                if not c:
                    rates[c] = None
                    exceptions.append(dict(code="TAX_CATEGORY_MISSING", severity="High", source="commercial",
                                           message="No tax category on the project / policy."))
                    continue
                r, st, note = tax_rate_from_rows(ex.tax_rows, c, inp.as_of, include_unapproved)
                rates[c] = r
                tax_status[c] = {"rate": r, "status": st, "note": note}
                if note:
                    exceptions.append(dict(code="TAX_RATE_UNVERIFIED" if r is not None else "TAX_RATE_UNRESOLVED",
                                           severity="High", source="commercial", message=note))
            # preliminary tax shares by direct-cost weight (final tax is recomputed from the schedule below)
            shares: dict[str, Decimal] = {}
            item_tax: dict[str, str | None] = {}                    # first row per item_key (O(n) lookup instead of a scan per item)
            for i in inp.items:
                item_tax.setdefault(i["item_key"], i.get("tax_category"))
            for k, ic in direct.items.items():
                if ic.complete and ic.pricing_method != "excluded":
                    tc = item_tax.get(k) or default_tax or ""
                    shares[tc] = shares.get(tc, ZERO) + ic.direct_cost
            commercial = com.compute_commercial(policy, direct_lines=[dict(item_key=l.item_key, cost_code=l.cost_code, kind=l.kind, amount=l.amount) for l in direct.lines if l.amount is not None],
                                                 direct=direct.direct_cost_total, indirect=indirect.total,
                                                money_dp=direct.money_dp, tax_shares=shares or {default_tax or "": Decimal(1)},
                                                tax_rates=rates, policy_name=policy_row["name"] if policy_row else "",
                                                policy_status=policy_row["status"] if policy_row else "")
            for e in commercial.exceptions:
                pass  # tax exceptions already added from tax_status
            adders = commercial.contingency + commercial.risk + commercial.escalation
            margin_incl = commercial.net_price + commercial.discount - commercial.total_cost
            items_meta = {i["item_key"]: i for i in inp.items}
            schedule = build_schedule(direct, indirect, policy,
                                      {"adders": adders, "margin": margin_incl, "discount": commercial.discount,
                                       "net": commercial.net_price}, items_meta, money_dp=direct.money_dp,
                                      rate_dp=int(policy.get("rate_dp", 2)), default_tax=default_tax)
            commercial = _tax_from_schedule(commercial, schedule, rates, direct.money_dp)

    # ---- unapproved flags & state
    for aid in sorted(direct.used_assumptions):
        pass
    blockers = _blockers(direct, indirect, commercial, schedule, exceptions, include_unapproved, dur_status, ind_items)
    items_all = [ic for ic in direct.items.values() if ic.pricing_method != "excluded"]
    completeness = {
        "items_total": len(items_all), "items_complete": sum(1 for i in items_all if i.complete),
        "items_unpriced": sum(1 for i in items_all if not i.complete),
        "pct_items_complete": (None if not items_all else quantize(Decimal(sum(1 for i in items_all if i.complete)) * 100 / len(items_all), 1)),
        "missing_rate_lines": sum(1 for l in direct.lines if l.amount is None),
        "indicative_exposure": sum((i.indicative_exposure for i in direct.items.values()), ZERO),
        "unknown_exposure_lines": sum(i.unknown_exposure_lines for i in direct.items.values()),
        "indirects_resolved": indirect.resolved,
    }
    complete = not blockers
    unapproved_used = include_unapproved and any("UNAPPROVED" in f or "PRELIMINARY" in f for l in direct.lines for f in l.flags)
    if not complete or include_unapproved:
        state = EstimateState.PRELIMINARY.value
    elif direct.provisional_used:
        state = EstimateState.PROVISIONAL.value
    else:
        state = EstimateState.COMPLETE.value
    flags = dict(synthetic=direct.synthetic_used, provisional=direct.provisional_used, include_unapproved=include_unapproved,
                 duration_status=dur_status)
    res = EstimateResult(inp.project, inp.as_of, inp, direct, indirect, commercial, schedule, policy, exceptions, state,
                         blockers, completeness, flags, "", tax_status, ex)
    res.fingerprint = fingerprint(res)
    return res


def _tax_from_schedule(c: com.CommercialResult, sch: PricingSchedule, rates: dict, dp: int) -> com.CommercialResult:
    """Final tax is computed on the TENDERED schedule amounts per tax category."""
    by: dict[str, dict] = {}
    total = ZERO
    unresolved = False
    for cat, base in sch.tax_shares.items():
        rate = rates.get(cat)
        if rate is None:
            by[cat] = {"base": base, "rate_pct": None, "tax": None}
            unresolved = True
            continue
        t = quantize(base * rate / 100, dp)
        by[cat] = {"base": base, "rate_pct": rate, "tax": t}
        total += t
    # an unresolved tax rate is shown as unresolved (None) - never as zero tax or a payable that silently omits tax
    return replace(c, tax_by_category=by, tax_total=None if unresolved else total,
                   final_payable=None if unresolved else sch.total_pre_tax + total)


_BLOCKING_SOURCES_SEV = ("Critical", "High")


def _blockers(direct, indirect, commercial, schedule, exceptions, include_unapproved, dur_status, ind_items) -> list[str]:
    b: list[str] = []
    if include_unapproved:
        b.append("Preliminary view includes unapproved inputs.")
    unpriced = [i for i in direct.items.values() if i.pricing_method != "excluded" and not i.complete]
    if unpriced:
        b.append(f"{len(unpriced)} BOQ item(s) are unpriced or incomplete.")
    if not indirect.resolved:
        b.append("Indirect costs have unresolved inputs.")
    if commercial is None:
        b.append("No computable commercial policy.")
    codes = {e["code"] for e in exceptions}
    for c, msg in (("POLICY_NOT_APPROVED", "Commercial policy not approved."),
                   ("TAX_RATE_UNRESOLVED", "Tax rate unresolved."), ("TAX_RATE_UNVERIFIED", "Tax rate unverified."),
                   ("POLICY_ASSUMPTION_NOT_APPROVED", "Policy depends on unapproved assumptions."),
                   ("DURATION_NOT_APPROVED", "Project duration not approved.")):
        if c in codes:
            b.append(msg)
    if ind_items and not any(i["status"] == "Approved" for i in ind_items):
        b.append("No indirect cost item is approved.")
    return b


def fingerprint(res: EstimateResult) -> str:
    c = res.commercial
    payload = {
        "lines": [(l.item_key, l.line_ref, to_text(l.amount), l.rate_id) for l in res.direct.lines],
        "indirect": [(l.code, to_text(l.amount)) for l in res.indirect.lines],
        "commercial": None if not c else [to_text(c.total_cost), to_text(c.net_price), to_text(c.tax_total)],
        "schedule": None if not res.schedule else [(l.item_key, to_text(l.amount), to_text(l.unit_rate)) for l in res.schedule.lines]
        + [(s["code"], to_text(s["price"])) for s in res.schedule.separate_lines],
        "policy": res.policy,
        "as_of": res.as_of.isoformat(),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
