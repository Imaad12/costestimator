"""Historical cost intelligence: actuals, estimate-vs-actual, rate change history. Ordinary SQL + pandas; no models, no fabricated data.

Compatible with DuckDB later: all queries are plain SQL over simple tables."""
from __future__ import annotations

from decimal import Decimal

import pandas as pd

from ..approvals import engine as approvals
from ..core.errors import ValidationFailed
from ..core.money import D, D_opt, to_text
from ..core.timeutil import now_iso
from ..database import Database, rows_to_dicts
from ..models.actor import Actor
from ..services import audit


def record_actual(db: Database, actor: Actor, project_id: str, *, source: str, cost_code: str | None = None, resource_id: str | None = None,
                  description: str | None = None, actual_amount=None, actual_quantity=None, actual_hours=None, unit: str | None = None,
                  cost_date: str | None = None, region: str | None = None) -> int:
    approvals.require_author(actor)
    if not source or not source.strip():
        raise ValidationFailed("An actual cost needs a source reference (ledger, invoice, timesheet...). Actuals are never estimated here.", code="SOURCE_REQUIRED")
    if actual_amount is None and actual_quantity is None and actual_hours is None:
        raise ValidationFailed("Provide an actual amount, quantity or hours.")
    for n, v in (("actual_amount", actual_amount), ("actual_quantity", actual_quantity), ("actual_hours", actual_hours)):
        if v is not None and D_opt(v) is None:
            raise ValidationFailed(f"{n} must be numeric.")
    aid = db.insert("actual_costs", dict(project_id=project_id, cost_code=cost_code, resource_id=resource_id, description=description,
                                         actual_amount=to_text(D_opt(actual_amount)), actual_quantity=to_text(D_opt(actual_quantity)),
                                         actual_hours=to_text(D_opt(actual_hours)), unit=unit, cost_date=cost_date, region=region, source=source,
                                         entered_by=actor.username, entered_at=now_iso()))
    audit.log(db, actor, "actual_cost", aid, "record", after={"project": project_id, "cost_code": cost_code, "source": source}, project_id=project_id)
    return aid


def estimate_vs_actual(db: Database, project_id: str, estimate: dict[str, Decimal] | None = None) -> pd.DataFrame:
    """By cost code: estimated direct cost (from the latest strict estimate) vs entered actuals. Only codes with data on either side appear."""
    if estimate is None:
        from ..estimators.estimate import compute_estimate
        estimate = compute_estimate(db, project_id).direct.by_cost_code()
    est = pd.DataFrame([{"cost_code": k, "estimated": float(v)} for k, v in estimate.items()])
    act = pd.DataFrame(rows_to_dicts(db.all("SELECT cost_code, actual_amount FROM actual_costs WHERE project_id=? AND actual_amount IS NOT NULL", (project_id,))))
    if act.empty:
        return est.assign(actual=None, variance=None, variance_pct=None) if not est.empty else est
    act["actual_amount"] = act["actual_amount"].astype(float)
    a = act.groupby("cost_code", dropna=False)["actual_amount"].sum().reset_index().rename(columns={"actual_amount": "actual"})
    df = est.merge(a, on="cost_code", how="outer")
    df["variance"] = df["actual"] - df["estimated"]
    df["variance_pct"] = (df["variance"] / df["estimated"]).where(df["estimated"].fillna(0) != 0) * 100
    return df.sort_values("cost_code")


def rate_changes(db: Database, resource_id: str | None = None) -> pd.DataFrame:
    sql = ("SELECT resource_id, version, rate_type, unit_price, currency, region, price_date, status FROM resource_rates "
           "WHERE unit_price IS NOT NULL" + (" AND resource_id=?" if resource_id else "") + " ORDER BY resource_id, price_date, version")
    df = pd.DataFrame(rows_to_dicts(db.all(sql, (resource_id,) if resource_id else ())))
    if df.empty:
        return df
    df["unit_price"] = df["unit_price"].astype(float)
    df["prev_price"] = df.groupby(["resource_id", "region"])["unit_price"].shift(1)
    df["change_pct"] = ((df["unit_price"] - df["prev_price"]) / df["prev_price"] * 100).where(df["prev_price"].notna())
    return df


def productivity_variance(db: Database, project_id: str) -> pd.DataFrame:
    """Estimated labour hours (strict estimate) vs actual hours entered, by resource."""
    from ..estimators.estimate import compute_estimate
    est = compute_estimate(db, project_id)
    e = {}
    for l in est.direct.lines:
        if l.kind == "labour" and l.hours is not None and l.resource_id:
            e[l.resource_id] = e.get(l.resource_id, Decimal(0)) + l.hours
    est_df = pd.DataFrame([{"resource_id": k, "estimated_hours": float(v)} for k, v in e.items()])
    act = pd.DataFrame(rows_to_dicts(db.all("SELECT resource_id, actual_hours FROM actual_costs WHERE project_id=? AND actual_hours IS NOT NULL AND resource_id IS NOT NULL",
                                            (project_id,))))
    if act.empty:
        return est_df.assign(actual_hours=None, variance_hours=None) if not est_df.empty else est_df
    act["actual_hours"] = act["actual_hours"].astype(float)
    a = act.groupby("resource_id")["actual_hours"].sum().reset_index()
    df = est_df.merge(a, on="resource_id", how="outer")
    df["variance_hours"] = df["actual_hours"] - df["estimated_hours"]
    return df
