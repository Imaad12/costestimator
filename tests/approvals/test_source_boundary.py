"""Structural guard: automated source access can only CREATE proposals. It must never reach review / publish / approve code."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent / "app"
FORBIDDEN = {"review", "publish", "approve_rate", "approve_rate_provisional", "approve_assumption", "approve_version", "approve_tender_export",
             "authorize", "record", "decide", "decide_rows", "publish_dataset", "approve_fx", "approve_tax_category", "reject_rate", "accept"}
MODULES = [*sorted((ROOT / "sources").glob("*.py")), ROOT / "rate_updates" / "refresh.py", ROOT / "rate_updates" / "importer.py",
           ROOT / "rate_updates" / "index_import.py", ROOT / "rate_updates" / "normalise.py", ROOT / "rate_updates" / "manifest.py"]


def test_automated_source_code_never_references_approval_or_publication_functions():
    offenders = []
    for f in MODULES:
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            name = n.attr if isinstance(n, ast.Attribute) else n.id if isinstance(n, ast.Name) else None
            if name in FORBIDDEN:
                offenders.append(f"{f.relative_to(ROOT)}:{n.lineno} -> {name}")
            if isinstance(n, ast.ImportFrom) and n.module and n.module.endswith("approvals.engine"):
                offenders.append(f"{f.relative_to(ROOT)}:{n.lineno} imports approvals.engine")
    assert not offenders, offenders


def test_refresh_and_providers_only_create_proposals_in_the_database():
    """Behavioural twin: after a full (mocked) refresh nothing is Approved/Published and no approval row exists."""
    import json
    from app.database import Database
    from app.rate_updates import refresh
    from app.sources import providers
    from app.sources.base import FetchResult
    from tests.conftest import ESTIMATOR
    db = Database(":memory:")
    db.migrate()
    from app.services import refdata
    refdata.seed_reference(db)

    class F:
        def fetch(self, url, policy):
            return FetchResult(url, "OK", 200, json.dumps({"total_count": 1, "results": [{"time_period": "2026-04", "measure": "Index",
                                                           "section_and_group": "Labor Costs", "index": 104.9}]}).encode(), "application/json")

    before_ap = db.scalar("SELECT COUNT(*) FROM approvals")
    rep = refresh.refresh_sources(db, ESTIMATOR, dry_run=False, fetcher=F())
    assert rep["summary"]["successful"] >= 1
    assert db.scalar("SELECT COUNT(*) FROM approvals") == before_ap
    assert db.scalar("SELECT COUNT(*) FROM resource_rates WHERE status IN ('Approved','Pending Review') AND unit_price IS NOT NULL") == 0
