"""Pilot CSV templates load as Drafts only; placeholders never become approved or priced data."""
from __future__ import annotations

import csv
import json

from app.services import governed
from tests.conftest import ESTIMATOR


def _write(p, rows):
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["kind", "code", "source", "basis_note", "project_id", "is_synthetic", "data_json"])
        w.writeheader()
        w.writerows(rows)
    return p


def test_governed_csv_import_creates_drafts_only_and_reports_bad_rows(seeded, tmp_path):
    f = _write(tmp_path / "p.csv", [
        dict(kind="productivity_factor", code="T1", source="synthetic test", basis_note="", project_id="", is_synthetic="yes",
             data_json=json.dumps({"category": "climate_heat", "factor": "1.10"})),
        dict(kind="productivity_factor", code="T2", source="", basis_note="", project_id="", is_synthetic="",
             data_json=json.dumps({"category": "climate_heat", "factor": "1.10"})),          # no source -> refused
        dict(kind="nope", code="T3", source="x", basis_note="", project_id="", is_synthetic="", data_json="{}"),
    ])
    res = governed.import_csv(seeded, ESTIMATOR, f)
    assert len(res["created_ids"]) == 1 and len(res["errors"]) == 2 and res["status"] == "Draft"
    assert seeded.one("SELECT status FROM governed_params WHERE id=?", (res["created_ids"][0],))["status"] == "Draft"
    assert governed.effective(seeded, "none", "productivity_factor") == []
    assert seeded.one("SELECT COUNT(*) n FROM approvals WHERE entity_type LIKE 'param:%'")["n"] == 0


def test_template_placeholders_are_rejected_not_loaded(seeded):
    from pathlib import Path
    res = governed.import_csv(seeded, ESTIMATOR, Path("templates/pilot/governed_parameters_template.csv"))
    assert res["created_ids"] == [] and res["errors"]
