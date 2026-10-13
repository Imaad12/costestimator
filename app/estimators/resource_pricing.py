"""Price one unit of a resource from its strictly eligible approved rate (used by services that cost hours outside the BOQ engine). Returns None if no eligible rate."""
from __future__ import annotations

from decimal import Decimal

from ..core.money import D
from ..core.timeutil import parse_date, today
from ..database import Database, rows_to_dicts
from .rate_resolution import resolve_rate


def price_resource_hours(db: Database, project_id: str, resource_id: str) -> Decimal | None:
    proj = db.one("SELECT region, currency, rate_as_of_date FROM projects WHERE id=?", (project_id,))
    as_of = parse_date(proj["rate_as_of_date"]) or today()
    parents = {r["code"]: r["parent_code"] for r in db.all("SELECT code, parent_code FROM regions")}
    rr = resolve_rate(rows_to_dicts(db.all("SELECT * FROM resource_rates WHERE resource_id=? ORDER BY version", (resource_id,))), project_id=project_id,
                      project_region=proj["region"] or "KSA-ALL", as_of=as_of, region_parents=parents)
    if not rr.usable:
        return None
    rate = rr.rate
    if rate["unit"] != "hr":
        return None
    if rate["currency"] != proj["currency"]:
        from ..services.landed import fx_lookup
        f = fx_lookup(db, as_of, proj["currency"])(rate["currency"])
        if f is None:
            return None
        return D(rate["unit_price"]) * f
    return D(rate["unit_price"])
