"""Configurable reconciliation rule table (severity, exception policy, blocking severities)."""
from __future__ import annotations

import json
from pathlib import Path

from ..config import BASE_DIR
from ..database import Database

DEFAULT_PATH = BASE_DIR / "config" / "reconciliation_rules.json"
OWNERS = {
    "UNPRICED_ITEM": "Estimator", "MISSING_RATE": "Procurement Reviewer", "EXPIRED_RATE": "Procurement Reviewer",
    "QUOTATION_EXPIRED": "Procurement Reviewer", "UNAPPROVED_ASSUMPTION": "Estimator", "UNAPPROVED_ADOPTED_ASSUMPTION": "Estimator",
    "DOUBLE_COUNT": "Estimator", "TAX_UNVERIFIED": "Commercial Approver", "POLICY_UNAPPROVED": "Commercial Approver",
    "DURATION_UNAPPROVED": "Estimator", "INDIRECT_UNAPPROVED": "Estimator", "OFFER_MISSING": "Commercial Approver",
    "OFFER_STALE": "Commercial Approver", "SCHEDULE_RECON": "Commercial Approver", "SCHEDULE_RECON_MAJOR": "Commercial Approver",
}


def load_rules(db: Database | None = None, path: Path | None = None) -> dict:
    data = json.loads((path or DEFAULT_PATH).read_text(encoding="utf-8"))
    if db is not None:
        row = db.one("SELECT value FROM settings WHERE key='recon_rules_override'")
        if row and row["value"]:
            ov = json.loads(row["value"])
            for k, v in (ov.get("rules") or {}).items():
                data["rules"].setdefault(k, {}).update(v)
            if ov.get("blocking_severities"):
                data["blocking_severities"] = ov["blocking_severities"]
    return data


def rule(rules: dict, code: str) -> dict:
    return rules["rules"].get(code) or {"severity": "High", "exception_allowed": True, "title": code}
