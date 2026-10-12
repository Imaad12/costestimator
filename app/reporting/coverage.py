"""Measured coverage of the rate library. Counts records only - this is NOT a claim of market completeness."""
from __future__ import annotations

from ..database import Database, rows_to_dicts


def library_coverage(db: Database) -> dict:
    by_type = rows_to_dicts(db.all(
        "SELECT r.resource_type AS type, COUNT(*) AS resources, "
        "SUM(CASE WHEN EXISTS (SELECT 1 FROM resource_rates x WHERE x.resource_id=r.id AND x.status='Approved' AND x.unit_price IS NOT NULL AND x.is_synthetic=0) THEN 1 ELSE 0 END) AS real_approved_rate, "
        "SUM(CASE WHEN EXISTS (SELECT 1 FROM resource_rates x WHERE x.resource_id=r.id AND x.status='Approved' AND x.unit_price IS NOT NULL AND x.is_synthetic=1) THEN 1 ELSE 0 END) AS synthetic_approved_rate, "
        "SUM(CASE WHEN NOT EXISTS (SELECT 1 FROM resource_rates x WHERE x.resource_id=r.id AND x.status IN ('Approved','Provisional — Approved for This Estimate') AND x.unit_price IS NOT NULL) THEN 1 ELSE 0 END) AS missing "
        "FROM resources r WHERE r.is_active=1 GROUP BY r.resource_type ORDER BY r.resource_type"))
    by_rt = rows_to_dicts(db.all("SELECT rate_type, status, is_synthetic, COUNT(*) AS n FROM resource_rates GROUP BY rate_type, status, is_synthetic ORDER BY rate_type"))
    by_div = rows_to_dicts(db.all(
        "SELECT substr(r.cost_code,1,1) AS division, COUNT(*) AS resources, "
        "SUM(CASE WHEN EXISTS (SELECT 1 FROM resource_rates x WHERE x.resource_id=r.id AND x.status='Approved' AND x.unit_price IS NOT NULL AND x.is_synthetic=0) THEN 1 ELSE 0 END) AS real_approved "
        "FROM resources r WHERE r.is_active=1 GROUP BY division ORDER BY division"))
    tot = {k: sum(r[k] for r in by_type) for k in ("resources", "real_approved_rate", "synthetic_approved_rate", "missing")}
    tot["pct_with_real_approved_rate"] = None if not tot["resources"] else round(100 * tot["real_approved_rate"] / tot["resources"], 1)
    return dict(totals=tot, by_type=by_type, by_rate_type=by_rt, by_division=by_div,
                assemblies=rows_to_dicts(db.all("SELECT status, is_synthetic, COUNT(*) AS n FROM (SELECT status, is_synthetic FROM assemblies) GROUP BY status, is_synthetic")),
                assumptions=rows_to_dicts(db.all("SELECT status, COUNT(*) AS n, SUM(CASE WHEN default_value IS NOT NULL THEN 1 ELSE 0 END) AS with_value FROM assumptions GROUP BY status")),
                sources=rows_to_dicts(db.all("SELECT access_status, COUNT(*) AS n FROM sources GROUP BY access_status")))
