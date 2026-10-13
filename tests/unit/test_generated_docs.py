"""Generated reference docs must list everything that exists (run `python scripts/gen_docs.py` after adding a kind, report or template)."""
from __future__ import annotations

import json
from pathlib import Path

from app.estimators.param_kinds import EXAMPLES, KINDS
from app.reporting.registry import REPORTS

ROOT = Path(__file__).resolve().parent.parent.parent


def test_governed_parameter_doc_lists_every_kind_and_every_kind_has_a_skeleton():
    doc = (ROOT / "docs" / "GOVERNED_PARAMETERS.md").read_text(encoding="utf-8")
    for k in KINDS:
        assert f"`{k}`" in doc, k
        assert k in EXAMPLES, f"{k} has no input-form skeleton in param_kinds.EXAMPLES"
    assert "ships no value" in doc


def test_report_doc_lists_every_report():
    doc = (ROOT / "docs" / "ANALYSIS_REPORTS.md").read_text(encoding="utf-8")
    for name in REPORTS:
        assert f"`{name}`" in doc, name


def test_template_doc_lists_every_template_and_skeletons_hold_no_numbers():
    doc = (ROOT / "docs" / "MTO_TEMPLATES.md").read_text(encoding="utf-8")
    for t in json.loads((ROOT / "data" / "mto" / "templates.json").read_text(encoding="utf-8"))["templates"]:
        assert f"`{t['code']}`" in doc, t["code"]
    def numeric(o):
        if isinstance(o, dict):
            return any(numeric(v) for v in o.values())
        if isinstance(o, list):
            return any(numeric(v) for v in o)
        return isinstance(o, (int, float)) and not isinstance(o, bool)
    assert not [k for k, v in EXAMPLES.items() if numeric(v)]                       # field skeletons never suggest a value
