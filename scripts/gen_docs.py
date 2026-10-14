"""Regenerates the data-derived documentation: docs/TRADE_TAXONOMY.md, docs/KSA_DATA_SOURCES.md (table), docs/EXCEL_DATA_DICTIONARY.md.
Run: python scripts/gen_docs.py"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def taxonomy() -> None:
    rows = list(csv.DictReader(open(ROOT / "data/taxonomy/cost_codes.csv", encoding="utf-8-sig")))
    out = ["# Trade taxonomy and cost codes", "",
           "Generated from `data/taxonomy/cost_codes.csv` by `scripts/gen_docs.py`. The taxonomy is **data, not code**: add a trade, sub-trade or",
           "cost code in *Settings -> Add cost code* (Administrator) or by adding rows to the CSV (loaded idempotently by `refdata.load_taxonomy`).",
           "No calculation-engine change is needed. Codes are stable identifiers used in resources, assemblies, BOQ items, workbooks and reports.", "",
           "Level 1 = division (A-L); level 2 = sub-trade; level 3+ = user-added cost codes (e.g. `D.07.01`).",
           "A project records its applicable trades (project settings / `project.json`); the cost-code tree itself is global and shared by resources, assemblies, BOQ items and reports.", ""]
    for d in [r for r in rows if r["level"] == "1"]:
        out.append(f"## {d['code']} - {d['name']}")
        out.append("")
        out.append("| Code | Sub-trade |")
        out.append("|---|---|")
        for r in rows:
            if r["parent_code"] == d["code"]:
                out.append(f"| `{r['code']}` | {r['name']} |")
        out.append("")
    (ROOT / "docs/TRADE_TAXONOMY.md").write_text("\n".join(out), encoding="utf-8")


def sources_table() -> str:
    rows = list(csv.DictReader(open(ROOT / "data/sources/source_register.csv", encoding="utf-8-sig")))
    out = ["| ID | Source | Organisation | Access status | Accessed | Licence / reuse (as observed) | Data collected |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        f = lambda k: (r[k] or "").replace("|", "/").replace("\n", " ")[:160]  # noqa: E731
        out.append(f"| {r['source_id']} | {f('name')} | {f('organisation')} | {f('access_status')} | {f('date_accessed') or '-'} | {f('licence_reuse_conditions')} | {f('data_collected') or 'none'} |")
    return "\n".join(out)


def governed_parameters() -> None:
    from app.estimators.param_kinds import EXAMPLES, KINDS
    import json
    out = ["# Governed parameters (company-supplied, human-approved inputs)", "",
           "Generated from `app/estimators/param_kinds.py` by `scripts/gen_docs.py`. **The software ships no value for any of these kinds.** Every number comes from a person's records, carries a stated source,",
           "is validated, goes *Draft -> Pending Review -> Approved* (role per kind below, enforced server-side by `approvals.engine.authorize`; AI cannot approve) and is never edited once approved - a change is a new version.",
           "Only *Approved* values affect a strict estimate; the preliminary (what-if) view may show newer Draft/Pending ones, flagged. Scope: company-wide (`project_id` empty) or one project (project value overrides a company-wide value of the same code).",
           "Propose with the UI (*Inputs & parameters*), `python -m app.cli param propose KIND CODE '<json>' --source '...' [--project PRJ-..]`, or the `propose_param` action. Field skeletons below show **names and shapes only**.", "",
           "| Kind | Label | Approvers | What it is | Fields (skeleton, no values) |", "|---|---|---|---|---|"]
    for k in KINDS.values():
        out.append(f"| `{k.name}` | {k.label} | {', '.join(sorted(k.approvers))} | {k.description} | `{json.dumps(EXAMPLES.get(k.name, {}), ensure_ascii=False)}` |")
    (ROOT / "docs/GOVERNED_PARAMETERS.md").write_text("\n".join(out) + "\n", encoding="utf-8")


def reports_doc() -> None:
    from app.reporting.registry import REPORTS
    out = ["# Analysis reports (read-only)", "",
           "Generated from `app/reporting/registry.py` by `scripts/gen_docs.py`. Every report is available identically from the web UI (*Analysis & controls*), the REST API",
           "(`GET /api/projects/{id}/report/{name}?param=value`), and the CLI (`python -m app.cli report PRJ-.. NAME --param k=v [--save]`). A report **never changes an estimate and never approves anything**;",
           "*Save* stores an immutable `analysis_runs` record (parameters, input hash, result) that is explicitly not an approved record. A report that lacks an approved input says so instead of guessing.", "",
           "| Report | Group | What it shows | Parameters |", "|---|---|---|---|"]
    for r in REPORTS.values():
        out.append(f"| `{r.name}` | {r.group} | **{r.label}** - {r.description} | {', '.join(f'`{n}`={d or chr(34)*2}' for n, d, h in r.params) or '-'} |")
    (ROOT / "docs/ANALYSIS_REPORTS.md").write_text("\n".join(out) + "\n", encoding="utf-8")


def mto_doc() -> None:
    import json
    d = json.loads((ROOT / "data/mto/templates.json").read_text(encoding="utf-8"))
    out = ["# Take-off derivation templates (structure only)", "",
           "Generated from `data/mto/templates.json` (written by `scripts/gen_mto_templates.py`). A template names a **driver** (the quantity *you* measured: inch-diameter, joints, tonnes, m2 ...) and the **resource slots**",
           "that follow from it. It contains **no factor, rate, productivity or standard**: each slot needs an approved governed `mto_factor` (code `template/slot`) naming the catalogue resource and the quantity per driver unit.",
           "`python -m app.cli mto preview|apply PRJ-.. ITEM TEMPLATE [--driver-qty N --driver-source '...']`: the result is written as take-off lines marked `origin=mto` and the item becomes a *Pending Review* pricing decision - nothing is priced until a person approves it.",
           "A slot without an approved factor blocks the application (or must be skipped explicitly and is recorded). Derived labour hours receive the governed productivity factors in scope.", "",
           f"{len(d['templates'])} templates, {sum(len(t['slots']) for t in d['templates'])} slots.", "",
           "| Template | Discipline | Driver | Slots (resource type, unit dimension) | Capability records |", "|---|---|---|---|---|"]
    for t in sorted(d["templates"], key=lambda t: t["code"]):
        out.append(f"| `{t['code']}` | {t['discipline']} | {t['driver_unit']} - {t['driver_description']} | " + "; ".join(f"`{s['slot']}` ({s['resource_type']}, {s['unit_dim']})" for s in t["slots"]) + f" | {t.get('capability') or '-'} |")
    (ROOT / "docs/MTO_TEMPLATES.md").write_text("\n".join(out) + "\n", encoding="utf-8")


def excel_dictionary() -> None:
    from app.excel.master import REQUIRED_SHEETS
    from app.excel.spec import S
    out = ["# Excel data dictionary", "", "Generated from `app/excel/spec.py` (the single source of truth for all workbooks). Row 5 = headers, hidden row 4 = machine keys, data from row 6.", ""]
    cls = {"input": "Input (yellow)", "calc": "Formula (grey, locked)", "ro": "Read-only (blue)"}
    for name in REQUIRED_SHEETS:
        sp = S.get(name)
        if not sp:
            continue
        out += [f"## {name}", "", sp.instructions, "", "| Header | Key | Class | Format / list |", "|---|---|---|---|"]
        for c in sp.cols:
            out.append(f"| {c.header} | `{c.key}` | {cls[c.kind]} | {(c.fmt or '')}{(' / list ' + c.dv) if c.dv else ''}{(' / `' + c.formula + '`') if c.formula else ''} |".replace("|  /", "| "))
        out.append("")
    (ROOT / "docs/EXCEL_DATA_DICTIONARY.md").write_text("\n".join(out), encoding="utf-8")


def standards_doc() -> None:
    import json
    d = json.loads((ROOT / "data/standards/standards_register.json").read_text(encoding="utf-8"))
    f = lambda x, n=700: (str(x) if x is not None else "-").replace("|", "/").replace("\n", " ")[:n]  # noqa: E731
    out = ["# Standards and evidence register", "",
           "Generated from `data/standards/standards_register.json` by `scripts/gen_docs.py` (loaded into the table `standards_register`; CLI `python -m app.cli standards list|acquire|import`).",
           "It records **where a rule or a basis comes from and what was actually read** - concise references and paraphrases only. It never reproduces copyrighted standards, never stores a price or a productivity value,",
           "and **no row is a statement that a project complies** with anything. " + d.get("review_required", ""), "",
           f"Source of these rows: {d.get('generated_by', '')}. Access date {d.get('access_date', '')}.", "",
           "| ID | Topic | Title | Publisher | Edition / date | Clause / page | Status | Link or file |", "|---|---|---|---|---|---|---|---|"]
    for s_ in d["sources"]:
        out.append(f"| {s_['id']} | {f(s_.get('topic'), 80)} | {f(s_['title'], 160)} | {f(s_.get('publisher'), 80)} | {f(s_.get('edition_or_publication_date'), 120)} | {f(s_.get('clause_or_page'), 120)} | **{s_['verification_status']}** | {f(s_.get('url'), 120)} |")
    out += ["", "## What each row says and where it stops", ""]
    for s_ in d["sources"]:
        out += [f"### {s_['id']} - {f(s_['title'], 120)}", "", f"* **Scope:** {f(s_.get('scope'))}", f"* **Paraphrase (not a quotation):** {f(s_.get('paraphrase'))}",
                f"* **Limitations:** {f(s_.get('limitations'), 900)}", f"* **Notes:** {f(s_.get('notes'), 900)}", ""]
    out += ["## Sources a person must still acquire", "", "Every row whose status is not *Verified - primary source read* needs a person to obtain the document, record the edition and clause, and re-import the row. "
            "Until then the product treats it as **unverified** and states so in every document that cites it. Productivity references (RSMeans, Spon's, CIOB publications, manufacturer instructions, company actuals) "
            "are listed by **name only**; no number from them is stored anywhere in the product.", ""]
    (ROOT / "docs/STANDARDS_AND_EVIDENCE_REGISTER.md").write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    (ROOT / "docs").mkdir(exist_ok=True)
    standards_doc()
    taxonomy()
    excel_dictionary()
    governed_parameters()
    reports_doc()
    mto_doc()
    tbl = sources_table()
    (ROOT / "docs/_sources_table.md").write_text(tbl, encoding="utf-8")
    ks = ROOT / "docs/KSA_DATA_SOURCES.md"
    txt = ks.read_text(encoding="utf-8")
    b, e = "<!-- SOURCES_TABLE_BEGIN -->", "<!-- SOURCES_TABLE_END -->"
    if b in txt and e in txt:
        ks.write_text(txt[:txt.index(b) + len(b)] + "\n## Register (generated)\n" + tbl + "\n" + txt[txt.index(e):], encoding="utf-8")
    print("docs generated")
