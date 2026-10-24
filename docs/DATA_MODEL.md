# Data model and source-of-truth rules

SQLite (`var/ksa_estimator.db`), schema = numbered SQL files in `app/migrations/` (0001 core … 0015 end-to-end closure, 0016 project basis flag, 0017 document discipline, 0018 unit spellings). Decimals are stored as exact TEXT.
Everything below is **implemented** unless marked otherwise.

## The eleven data classes and where each lives
| # | Class | Source of truth | Tables / files | Sync rule |
|---|---|---|---|---|
| 1 | Global taxonomy & code mappings | seed CSV → DB | `data/taxonomy/cost_codes.csv`, `data/units`, `data/regions` → `cost_codes`, `units`, `regions` | **insert-only** load (`refdata`); the DB is authoritative at runtime; admin additions live in the DB only |
| 2 | Global resource catalogues | seed CSV → DB | `data/{materials,labour,plant,equipment,subcontractors}/*.csv` → `resources` | insert-only; catalogues carry **no prices** (each new resource gets a *Missing Rate* placeholder) |
| 3 | Global rates & rate history | **DB only** | `resource_rates` (versioned, immutable once approved), `approvals`, `audit_log` | no JSON/CSV mirror; exports are views. Published candidates become new versions here |
| 4 | Global assumptions & productivity benchmarks | seed CSV → DB | `data/assumptions/assumptions_register.csv` → `assumptions` (versioned); `data/productivity/` = schema only | insert-only; values only via approved versions |
| 5 | Global assembly templates | seed CSV → DB | `data/assemblies/standard_assemblies.csv` → `assemblies`, `assembly_lines` | insert-only; structure without factors until a human supplies them |
| 6 | Public-source datasets & manifests | **files + DB** | originals + `*.manifest-N.json` in `var/imports/`; `import_manifests`, `index_observations`, `rate_candidates`, `source_access_log`; Source Register `data/sources/source_register.csv` → `sources` | originals are content-addressed (`<sha10>_name`) and never rewritten; DB rows are the queryable record; the register CSV is repo-owned and **refreshes** the `sources` descriptive fields |
| 7 | Project BOQ & quantities | DB (+ original upload) | `boq_imports`, `boq_items`, `boq_rejected_rows`, `takeoff_resource_lines`, `change_requests`; original file in workspace `3. BOQ & Takeoff/` | the file is evidence; the DB is what is calculated. Re-import → *pending change requests*, never silent overwrite |
| 8 | Project assumptions & overrides | DB | `project_assumptions` (versioned, needs reason + approval), `projects.*` | an override never changes the global assumption row |
| 9 | Project supplier quotations | DB (+ original) | `quotations`, `quotation_lines`, `quote_adjustments`, `quote_selections`, `rfqs`, `procurement_*`; originals in `6. Procurement & Quotations/` | attached to `project_id`; approved quotes may *publish* a global rate (new version) |
| 10 | Project estimate versions | DB | `estimate_versions` (frozen results, fingerprint), **`estimate_snapshots`** (frozen inputs) | frozen rows are append-only; a copy of the snapshot JSON is written to `5. …/versions/` |
| 11 | Approved submission snapshots | DB + files | `exports` (kind, sha256, `estimate_version_id`, `approval_ref`), `approvals`, `offers`; files in `8. Commercial Submission/` / `10. Exports & Archive/` | released only via the gated `export_submission`; the hash is stored |

Generated, never trusted as input: `projects/<id>/project.json`, `projects/<id>/CLAUDE.md`, `2. AI Context/*`, workbooks (re-validated on import), `docs/TRADE_TAXONOMY.md` and the Excel data dictionary (`scripts/gen_docs.py`).
Rule of thumb: **if a number or an approval matters, it is a row in the database; a file is evidence or a view.** Do not add a second authoritative copy of anything.

## Table groups
* Identity/audit: `users`, `settings`, `audit_log` (hash chain), `approvals`, `change_requests`.
* Reference: `cost_codes`, `units`, `regions`, `tax_categories`, `fx_rates`, `sources`, `commercial_policies`.
* Libraries: `suppliers`, `resources`, `resource_rates`, `assumptions`, `project_assumptions`, `assemblies`, `assembly_lines`.
* Projects: `projects` (+ `workspace_path`, `workspace_slug`, `project_type`, `trades`, `drawing_revision`, `spec_revision`), `boq_*`, `takeoff_resource_lines`, `project_durations`, `schedule_tasks`, `indirect_items`, `estimate_versions`, `estimate_snapshots`, `offers`, `clarifications`, `scope_register`, `risks`, `exports`, `recon_*`, `actual_costs`, `ai_suggestions`.
* Documents: `project_documents` (indexer).
* Procurement: `procurement_packages/items`, `rfqs`, `rfq_items`, `quotations/lines`, `quote_adjustments`, `quote_selections`.
* Structure, parameters, analysis (0008): `wbs_nodes`, `boq_wbs`, `code_crosswalk`, **`governed_params`** (versioned, human-approved company/project numbers of ~20 kinds - see [GOVERNED_PARAMETERS.md](GOVERNED_PARAMETERS.md)), `analysis_runs` (immutable saved analyses, *not* approved data); `schedule_tasks.{wbs_code,snet,fnlt}`; quantified `risks.*`.
* Take-off derivation (0009): `mto_applications`, `takeoff_resource_lines.{origin,origin_ref}` (derived lines are marked and need a pricing decision).
* Client profiles (0010): `client_profiles`, `profile_requirements`, `project_profiles`, `profile_assessments`.
* Bids and scope (0011): `bid_scores`, `long_lead_items`, `package_scope`. Post-award (0012): `variations`, `variation_lines`, `task_progress`. Security (0013): `login_attempts`.
* Public sources (0007): `import_manifests`, `rate_candidates`, `index_observations`, `source_access_log`; legacy flow: `dataset_imports`, `rate_staging`.

## Stable references (what an estimate points at)
| From | To | Stable? |
|---|---|---|
| BOQ item | `assembly_code` (+ approved version at calculation) or `pricing_resource_id` | ids; version resolved from approved state and frozen in the snapshot |
| Assembly line | `resource_id`, assumption ids (`@ASMP-…`, `waste_ref`, …) | ids |
| Cost line (calculated) | `rate_id` (a `resource_rates.id`: resource+version), assembly code+version, assumption ids | row ids; rows are immutable once approved |
| Estimate version | `inputs_hash` (fingerprint), snapshot sha256 | hashes |
| Rate candidate | `resource_id`, `manifest_id`, `source_id`, source URL, `published_rate_id` | ids |
| Published rate | evidence text embeds candidate ref, URL, retrieval date, original price, normalisation method, reviewer | text + FK-free link in audit |

## Reproducing a historical estimate
1. `estimate_versions.result_json` / `totals_json` — the frozen output (never recomputed).
2. `estimate_snapshots` — the frozen input records, integrity-checked by SHA-256. `snapshots.verify_snapshot` / `replay_direct_cost` (CLI `project verify-snapshot <version_id>`).
**Limit:** replay re-runs the *direct-cost* engine from the snapshot. Indirects/commercial/tax are stored in the snapshot for audit but are not replayed (they are re-computable by hand from the stored policy and indirect rows; a full replay engine is planned — NEXT_STEPS #13).
Snapshots do not exist for versions frozen before migration 0007 (reported as such).

## Rate lifecycle across the tables
`import / discovery` → `rate_candidates` (Pending Review) → human *Approved for Publication* (`approvals` entity `rate_candidate`) → `resource_rates` new version **Pending Review** → human `approve_rate`
(supersedes the previous approved version for the same resource+region; old row kept) → eligible for estimates. Index series never leave `index_observations`.

## Governed parameters (iteration 4)
Numbers that a company decides (productivity factors, hire terms, calendar, escalation, payment terms, benchmark ranges, statutory rules, take-off factors, evaluation criteria ...) live in **one table**, `governed_params`, with a `kind`, `code`, `version`, `status`, validated `data_json`, a **required source**, and the approval trail in `approvals` (entity `param:<kind>`). Approved rows are immutable; a change is a new version and the approved one stays in force until the new one is approved (`governed.effective`). Project-scoped rows override company-wide rows of the same code. Direct-cost inputs of this kind are frozen into every estimate snapshot (`params`, `item_wbs`, `wbs_parent`) so replays do not depend on later changes. The library ships **empty**.

## Replay and frozen estimates (iteration 4)
`estimate_snapshots` now also store `extras` (duration rows, indirect rows, resolved commercial policy and the assumptions it used, tax categories). `compute_estimate_from(inputs, extras)` is pure, so `replay_estimate(version)` recomputes the whole estimate (direct, indirects, commercial, schedule, tax) from the snapshot alone and compares the fingerprint and every total; snapshots written before `extras` existed are rebuilt from their older keys.

## Migration rules
Forward-only numbered SQL (`app/migrations`), applied once, recorded in `schema_migrations`. Restructuring of *files* goes through `migrate-workspaces` (dry-run, backup, report, copy-only).

## End-to-end closure tables (migration 0015)
* Assumption governance: new columns on `assumptions` (`category`, `origin`, `reason`, `business_impact`, `uncertainty`, `consequence_if_missing`, `affects`, `reviewed_by/at`, `supersedes_version`) and **triggers** that refuse changes/deletes of Approved/Superseded rows of `assumptions`, `project_assumptions`, `productivity_norms`, `workforce_profiles` (a guard, not tamper-proofing).
* Programme: `productivity_norms` (versioned, 7 states, origin, evidence status), `workforce_profiles` (archetype, roles, shifts, attendance, fronts, role costs), `work_activities` (project activities; quantity read from `boq_items`), `programme_baselines` (saved results + fingerprint + approval).
* Tender: `tender_enquiries`, `tender_documents` (received documents, revisions, content status), `tender_queries` (8 registers, draft-only workflow), `tender_register_items` (compliance, ITP, method statement, HSE, permit, submittal, testing, NCR structure, bid/no-bid, context ...), `open_actions`.
* Output: `tender_packs` (kind tender/handover, revision, classification, manifest hash), `generated_documents` (doc id, template id/version, status, applicability + reason, checksum, facts printed, references). `standards_register` holds source references.

## Unit spellings (migration 0018)
Reference data only: adds the spellings `psc` (number) and `lot` (lump sum) to existing unit synonyms so real BOQs resolve; no unit is added or redefined. Existing databases get it by migration, new ones from `data/units/units.csv`.

## Project basis flag (migration 0016)
`projects.basis_defaulted` = 1 when a project was created without an explicit region and currency (KSA-ALL / SAR were applied as defaults). It blocks production readiness and prints a banner until `projects.confirm_basis` (action `confirm_project_basis`) is called by a person.
