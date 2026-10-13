"""The Claude Code instruction system must stay real: skills are well-formed and every file they tell Claude to read exists."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS = ["project-initializer", "project-indexer", "boq-import-review", "requirements-extraction", "assembly-management", "estimating-workflow",
          "rate-source-research", "rate-update-review", "subcontractor-quote-analysis", "procurement-rfq", "gantt-duration-estimation",
          "reconciliation-check", "excel-validation", "architecture-maintenance"]
SECTIONS = ["Purpose", "When to use", "Required context and inputs", "Read first", "Steps", "Outputs and schemas", "Validation checks",
            "Approval requirements", "Failure handling", "Explicitly prohibited"]
DOCS = ["ARCHITECTURE", "DATA_MODEL", "ESTIMATING_METHODOLOGY", "ASSUMPTIONS_POLICY", "APPROVAL_WORKFLOW", "EXCEL_WORKBOOK_GUIDE", "PROJECT_WORKSPACES",
        "KSA_DATA_SOURCES", "RATE_PROVENANCE", "RATE_UPDATE_WORKFLOW", "TRADE_TAXONOMY", "DEVELOPMENT_AUDIT", "NEXT_STEPS"]


def _paths(text: str):
    for m in re.finditer(r"`((?:docs|app|data|config|templates|tests|scripts)/[A-Za-z0-9_./-]+)", text):
        p = m.group(1).rstrip(".,)")
        if "<" in p or "*" in p or "…" in p:
            continue
        yield p


def test_required_documents_exist():
    for d in DOCS:
        assert (ROOT / "docs" / f"{d}.md").is_file(), d
    assert (ROOT / "CLAUDE.md").is_file()


def test_every_skill_is_well_formed_and_states_all_required_sections():
    for name in SKILLS:
        f = ROOT / ".claude" / "skills" / name / "SKILL.md"
        assert f.is_file(), name
        t = f.read_text(encoding="utf-8")
        m = re.match(r"---\n(.*?)\n---\n", t, re.S)
        assert m, name
        fm = dict(line.split(": ", 1) for line in m.group(1).splitlines())
        assert fm["name"] == name and len(fm["description"]) > 40 and fm["allowed-tools"]
        for s in SECTIONS:
            assert f"## {s}" in t, (name, s)
        assert "Quantities" in t or "quantities" in t                              # the human-measured-quantities prohibition is present
        assert "approv" in t.lower()


def test_paths_named_in_skills_and_claude_md_exist():
    missing = []
    files = [ROOT / "CLAUDE.md", *(ROOT / ".claude" / "skills" / n / "SKILL.md" for n in SKILLS)]
    for f in files:
        for p in _paths(f.read_text(encoding="utf-8")):
            if not (ROOT / p).exists() and not any((ROOT / p.rsplit("/", 1)[0]).glob(p.rsplit("/", 1)[1] + "*")):
                missing.append(f"{f.relative_to(ROOT)} -> {p}")
    assert not missing, missing


def test_folder_names_in_project_claude_md_template_match_workspace_constants():
    from app.services import workspaces
    t = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for n in workspaces.AREA_NAMES:
        assert n in t, n
