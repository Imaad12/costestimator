# Architecture

## Principles
1. **Deterministic core.** All money/quantity arithmetic is ordinary Python `Decimal` code in `app/estimators/` - pure functions of an
   input snapshot, no database, no AI, no clock. They are unit-tested against independently computed values.
2. **Human approval gates data, not the UI.** `app/approvals/policy.py` is the role matrix; `approvals.engine.authorize` is called by every
   service that approves, rejects or publishes. The REST API and web UI only authenticate; they cannot bypass a service.
3. **No silent change.** Approved records are immutable; edits create new versions or pending revisions; every change is written to a
   hash-chained audit log (tamper-*evident* only - see Known Limitations).
4. **Excel-first, local-first.** SQLite file + ordinary folders. The master workbook is an editable *view*; the Python engine is authoritative
   and workbooks are re-validated on import.
5. **AI is optional and boxed in.** `app/ai` can only insert review-pending rows (`ai_suggestions`); a structural test asserts it imports no
   approval or mutation code.

## Layers
```
app/
  config.py, database.py      settings (toml/.env/env), SQLite wrapper + SQL migrations (app/migrations/*.sql, applied in order)
  core/                       errors, Decimal helpers, unit registry (explicit conversions), time helpers
  models/                     enums (statuses, rate types, roles, pricing methods), Actor
  estimators/                 PURE engines: direct_cost, rate_build, rate_resolution, indirect, duration (CPM), commercial,
                              pricing_schedule, estimate (orchestrator + fingerprint), context (the only SQL reader)
  services/                   DB-backed domain services: rates, assumptions, assemblies, boq, projects, indirects, commercial (policy/tax/FX),
                              registers, offers, estimates (versions, gated export), suppliers, suggestions, backup, audit, auth, refdata
  imports/                    readers (CSV/XLSX), BOQ + takeoff importer, dataset ingestion (stage -> validate -> publish)
  procurement/                needs detection, RFQ drafting/export, quotations, levelling, selection + rate publication
  reconciliation/             rule table (config/reconciliation_rules.json), findings engine, exceptions, final gate
  excel/                      spec (single source of truth for columns), builder, master (27 sheets), templates, roundtrip, recalc (LibreOffice)
  exports/                    client pricing schedule, estimate report, offer templates (docx)
  ai/                         provider (Null/Claude/Mock), strict schemas, proposal service; deterministic suggesters
  api/                        REST routes, action registry (shared by UI and API), serializers
  web/                        Jinja2 templates + CSS (no external assets)
  reporting/                  dashboard, coverage, historical analytics (pandas)
  integrations/               documented integration points (adapters are honest about what is NOT implemented)
  cli.py, main.py             command line, FastAPI factory
```

## Data model (SQLite; decimals stored as exact TEXT)
Identity/audit: `users`, `audit_log` (hash chain), `approvals`, `change_requests`. Reference: `cost_codes`, `units`, `regions`, `tax_categories`,
`fx_rates`, `sources`. Libraries: `resources`, `resource_rates` (versioned), `assumptions` (versioned), `project_assumptions`, `assemblies` +
`assembly_lines`. Projects: `projects`, `boq_imports`, `boq_items`, `boq_rejected_rows`, `takeoff_resource_lines`, `indirect_items`,
`project_durations`, `schedule_tasks`, `commercial_policies`, `estimate_versions`, `offers`. Procurement: `procurement_packages/items`, `rfqs`,
`quotations/lines`, `quote_adjustments`, `quote_selections`. Registers: `clarifications`, `scope_register`, `risks`. Control: `recon_runs/findings/
exceptions`, `exports`. History/ingestion: `actual_costs`, `dataset_imports`, `rate_staging`, `ai_suggestions`.

## Request flow for a priced estimate
`context.load_inputs` (SQL -> immutable `EstimateInputs`) -> `direct_cost.compute_direct_cost` -> `indirect.compute_indirects` ->
`commercial.compute_commercial` -> `pricing_schedule.build_schedule` -> tax recomputed on the tendered schedule -> state, blockers,
completeness and a SHA-256 *fingerprint* of the result. Reconciliation, versions, workbooks and exports are all keyed to that fingerprint,
so any later change to inputs makes an approval, offer or export visibly stale.

## Concurrency and deployment
A single SQLite connection with explicit nested transactions; the ASGI app serialises requests (one at a time) - appropriate for a local
single-user/small-team tool. Not designed for multi-node or internet exposure (bind to 127.0.0.1; see Known Limitations).

## Design decisions
* **Own SQL migration runner** instead of Alembic/SQLAlchemy: plain numbered `.sql` files, fewer dependencies, easy to audit. A `schema_migrations` table records applied versions.
* **Stdlib `sqlite3`** with TEXT decimals: exact money, simple backup (online-backup API), DuckDB-compatible plain SQL for analytics.
* **HMAC-signed tokens** (PBKDF2 passwords) rather than a user framework: sufficient for the stated MVP; documented as not enterprise security.
* **Python 3.13 / pandas 3 / pydantic 2** were used for development; `requires-python >= 3.11`.
