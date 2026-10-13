# KSA Construction Estimating Suite

A **local-first, Excel-first estimating and procurement-support system** for construction contractors in the Kingdom of Saudi Arabia.
Estimators measure quantities themselves; the application imports them, prices them deterministically from approved resources,
assemblies and assumptions, drives procurement (missing rates -> RFQs -> quotations -> levelling), applies indirects and a
configurable commercial policy, reconciles everything, and only releases a "submission-ready" export after explicit human approval.

> **Human-in-the-loop by design.** AI (optional) only *proposes*. Nothing becomes verified, approved or exportable without a named,
> authorised human decision recorded in the approval log. Missing rates are shown as missing - never zero, never invented.
> **All demonstration data is SYNTHETIC / DEMO / NOT A MARKET QUOTE.** No Saudi market rate library is shipped
> (see [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) for measured coverage).

## Quick start

```bash
python3 -m venv .venv && . .venv/bin/activate          # Python 3.11+ (developed on 3.13)
pip install -e ".[dev]"                                 # add ".[ai]" for the optional Claude integration
python -m app.cli init --demo-users                     # database + reference data + users (admin password is printed once)
python -m app.cli demo                                  # optional: the clearly-labelled SYNTHETIC demonstration project
python -m app.cli run                                   # http://127.0.0.1:8000  (use --port to change)
```

Sign in as `admin` (password printed by `init`) or, if you used `--demo-users`, as `estimator`, `procurement` or `commercial`
(password `demo-only-change-me` - local demo only). Then follow [docs/USER_GUIDE.md](docs/USER_GUIDE.md).

Helper scripts: `scripts/setup.sh` (venv + install + init), `scripts/run.sh`, `scripts/test.sh`.

## What is in the box

| Area | Where |
|---|---|
| Deterministic engines (Decimal): direct cost, indirects, duration/CPM, commercial, pricing schedule | `app/estimators/` |
| Approval policy and server-side authorisation, hash-chained audit trail | `app/approvals/`, `app/services/audit.py` |
| Resources, versioned rates, assumptions, assemblies, BOQ import, projects | `app/services/`, `app/imports/` |
| Procurement: needs detection, RFQs (EN/AR), quotations, levelling, selection, rate publication | `app/procurement/` |
| Reconciliation (configurable rules, exceptions, audit report) | `app/reconciliation/`, `config/reconciliation_rules.json` |
| Excel: 27-sheet master workbook, 11 standalone templates, round-trip import, LibreOffice verification | `app/excel/`, `templates/` |
| Documents: client pricing schedule, offer letter, estimate report (.docx/.xlsx) | `app/exports/`, `app/services/offers.py` |
| Optional AI (review-only, schema-validated) and rule-based suggesters | `app/ai/` |
| Local web UI (16 sections) + REST API | `app/web/`, `app/api/` |
| Backup / restore / project packages, CLI | `app/services/backup.py`, `app/cli.py` |
| Numbered project workspaces (`projects/PRJ-nnnn-slug/` with 10 fixed folders, generated project `CLAUDE.md`), document indexer, frozen estimate input snapshots | `app/services/workspaces.py`, `project_index.py`, `snapshots.py` |
| Public-source rate updates: provider interface, KAPSARC/GASTAT CCI index import, manual price-list import, web evidence extraction, rate-candidate review queue, normalisation, publication as Pending Review | `app/sources/`, `app/rate_updates/` |
| Claude Code instructions: root `CLAUDE.md`, 16 task skills | `CLAUDE.md`, `.claude/skills/` |
| Data: 152-node taxonomy, 927 catalogue resources (no prices), 322 assumptions (no invented values), 27 sources, synthetic demo | `data/` |
| **Iteration 4:** governed parameters, WBS/CBS roll-ups, programme v2 + loading + man-hours, take-off templates, landed cost/currency, statutory labour, risk/Monte Carlo/escalation, cash flow, bids/long-lead/interfaces, variations/EVM, benchmarks, Basis of Estimate, classification, client profiles, method alternatives, client-form export, full replay, security hardening | `app/estimators/`, `app/services/`, `app/reporting/registry.py`, [docs](docs/ESTIMATING_CAPABILITY_MATRIX.md) |
| Tests (pytest) | `tests/` |

## Commands

```
python -m app.cli init [--admin-password P] [--demo-users]    python -m app.cli demo
python -m app.cli run [--host H --port N]                       python -m app.cli templates [--out DIR]
python -m app.cli backup | validate-backup F | restore F --yes  python -m app.cli export-workbook PRJ-0001 --out wb.xlsx
python -m app.cli verify-workbook wb.xlsx [--project PRJ-0001]  python -m app.cli coverage | audit-verify | export-project PRJ-0001
python -m app.cli project create --name "…" --trades "HVAC,Electrical" | list | index PRJ-0001 | search PRJ-0001 "text" | import-boq PRJ-0001 FILE
python -m app.cli sources list | status | refresh --dry-run         python -m app.cli rates import|validate FILE … | pending | review RC-… approve | publish RC-…
python -m app.cli index import FILE --dataset gastat-cci --source SRC-002 [--dry-run]       python -m app.cli migrate-workspaces --dry-run
python -m app.cli pack list|load industrial   python -m app.cli report PRJ-0001 rollup|manhours|loading|risk|cashflow|earned_value … [--param k=v] [--save]
python -m app.cli param kinds|list|propose|import|submit|approve|reject …    python -m app.cli wbs PRJ-0001 FILE.csv     python -m app.cli mto templates|preview|apply …
Pilot readiness (what real data a pilot needs, preliminary vs approved): docs/PILOT_READINESS.md
python -m app.cli profile create|submit|approve|link|attest …         python -m app.cli unlock-user NAME --user admin     python -m app.cli run --ssl-certfile C --ssl-keyfile K
pytest                                                          # full automated suite (see docs/TESTING.md)
# state-changing commands authenticate: --user NAME (or KSA_CLI_USER) and KSA_CLI_PASSWORD (or a prompt)
```

## Configuration

`config/settings.toml` (defaults) overridden by `.env` / `KSA_*` environment variables (see `.env.example`). Notable: `KSA_DB_PATH`,
`KSA_ALLOW_SELF_APPROVAL`, `KSA_AI_ENABLED` + `ANTHROPIC_API_KEY`, approval thresholds, reconciliation tolerance, company details.
Secrets are never committed (`.env`, `var/` are git-ignored).

## Documentation

[Architecture](docs/ARCHITECTURE.md) · [User guide](docs/USER_GUIDE.md) · [Estimating methodology](docs/ESTIMATING_METHODOLOGY.md) ·
[Assumptions policy](docs/ASSUMPTIONS_POLICY.md) · [KSA data sources](docs/KSA_DATA_SOURCES.md) · [Rate provenance](docs/RATE_PROVENANCE.md) ·
[Approval workflow](docs/APPROVAL_WORKFLOW.md) · [Procurement guide](docs/PROCUREMENT_GUIDE.md) · [Excel workbook guide](docs/EXCEL_WORKBOOK_GUIDE.md) ·
[Trade taxonomy](docs/TRADE_TAXONOMY.md) · [Import/export formats](docs/IMPORT_EXPORT_FORMATS.md) · [Backup/restore](docs/BACKUP_RESTORE.md) ·
[Project workspaces](docs/PROJECT_WORKSPACES.md) · [Data model](docs/DATA_MODEL.md) · [Rate update workflow](docs/RATE_UPDATE_WORKFLOW.md) · [Development audit](docs/DEVELOPMENT_AUDIT.md) · [Next steps](docs/NEXT_STEPS.md) ·
[Extending without code changes](docs/EXTENDING.md) · [Known limitations](docs/KNOWN_LIMITATIONS.md) · [Testing](docs/TESTING.md) ·
[Capability matrix](docs/ESTIMATING_CAPABILITY_MATRIX.md) · [Gap roadmap](docs/ESTIMATING_GAP_ROADMAP.md) · [Governed parameters](docs/GOVERNED_PARAMETERS.md) · [Analysis reports](docs/ANALYSIS_REPORTS.md) · [Take-off templates](docs/MTO_TEMPLATES.md) · [Security](docs/SECURITY.md)

## Licence

MIT (see `LICENSE`). Commercial and contractual outputs (offer letters, schedules) are drafts for human review and are not legal advice.
