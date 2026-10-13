"""Saudi-style labour on-cost build-up from user-supplied, approved rules, and workforce-mix checks against a user-supplied national-workforce target.
The software holds no wage, levy, insurance or accrual value."""
from __future__ import annotations

from ..approvals import engine as approvals
from ..core.errors import ValidationFailed
from ..core.money import D, D_opt, to_text
from ..database import Database
from ..estimators import labour_costs, rate_build
from ..models.actor import Actor
from . import audit, governed, rates


def _rules(db: Database, project_id: str | None) -> list[dict]:
    return [dict(code=r["code"], version=r["version"], **r["data"]) for r in governed.effective(db, project_id or "", "labour_statutory")]


def build(db: Database, *, monthly_base_wage, group: str, contract_months=None, normal_hours_per_month, project_id: str | None = None, **components) -> dict:
    if group not in ("saudi", "expat"):
        raise ValidationFailed("group must be 'saudi' or 'expat'.", code="LABOUR_GROUP")
    rules = _rules(db, project_id)
    st = labour_costs.statutory_monthly(D(monthly_base_wage), rules, group, D_opt(contract_months))
    comps = {"monthly_base_wage": str(monthly_base_wage), "normal_hours_per_month": str(normal_hours_per_month),
             "employer_costs_monthly": to_text(st["monthly_total"]), "statutory_breakdown": [{**r, "monthly": to_text(r["monthly"])} for r in st["rows"]],
             "workforce_group": group, "contract_months": None if contract_months in (None, "") else str(contract_months)}
    comps.update({k: str(v) for k, v in components.items() if v not in (None, "")})
    b = rate_build.build_labour(comps)
    return dict(components=comps, hourly_cost=b.hourly_cost, monthly_total=b.monthly_total, statutory=st, rules_applied=[r["code"] for r in rules])


def propose_labour_rate(db: Database, actor: Actor, resource_id: str, *, monthly_base_wage, group: str, normal_hours_per_month, contract_months=None,
                        project_id: str | None = None, rate_type: str = "Estimator-Entered Allowance", source_id: str | None = None, evidence: str,
                        price_date: str | None = None, submit: bool = False, **components) -> dict:
    approvals.require_author(actor)
    if not (evidence or "").strip():
        raise ValidationFailed("Evidence for the wage figures is required.", code="EVIDENCE_REQUIRED")
    res = build(db, monthly_base_wage=monthly_base_wage, group=group, contract_months=contract_months, normal_hours_per_month=normal_hours_per_month,
                project_id=project_id, **components)
    rid = rates.propose_rate(db, actor, resource_id, unit_price=res["hourly_cost"], rate_type=rate_type, components=res["components"], source_id=source_id, evidence=evidence,
                             price_date=price_date, project_id=project_id, confidence="Unverified", submit=submit,
                             notes=f"Labour build-up incl. statutory rules {res['rules_applied']} (user-supplied, approved)")
    audit.log(db, actor, "rate", rid, "propose_labour_buildup", after={"hourly": to_text(res["hourly_cost"]), "group": group, "rules": res["rules_applied"]}, project_id=project_id)
    return dict(rate_id=rid, hourly_cost=res["hourly_cost"], statutory_monthly=res["statutory"]["monthly_total"], rules_applied=res["rules_applied"])


def workforce_report(db: Database, groups: list[dict], project_id: str | None = None, target_code: str | None = None) -> dict:
    """groups: [{name, headcount, hourly_cost, saudi}] entered by the user. Blends the cost and checks the national share against an approved target."""
    out = labour_costs.blend(groups)
    tg = [r for r in governed.effective(db, project_id or "", "national_workforce_target") if (target_code is None or r["code"] == target_code)]
    if tg:
        t = tg[0]
        out["target"] = dict(code=t["code"], authority_ref=t["data"]["authority_ref"], **labour_costs.national_target_check(out["saudi_pct"], D(t["data"]["required_pct"])))
    else:
        out["target"] = None
        out["note"] = "No approved national-workforce target on record: no compliance check was made."
    return out
