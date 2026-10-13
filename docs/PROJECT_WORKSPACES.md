# Project workspaces

Status: **implemented** (`app/services/workspaces.py`, `project_index.py`, `snapshots.py`, `workspace_migration.py`; UI tab *Workspace & documents*;
CLI `project …`, `migrate-workspaces`). Tests: `tests/workspaces/`, `tests/integration/test_workspace_ui.py`.

## What a workspace is (and is not)
Every project has one folder of **files**: tender documents, extracts, uploaded BOQs, supplier quotation originals, generated deliverables.
The **database remains the source of truth for every number and every approval**. A workspace is never read back as input by the
estimating engines, and `project.json` / the project `CLAUDE.md` are *generated views* of the database (they are regenerated, not parsed).

| Global (shared, reusable, versioned, in the DB) | Project-specific (isolated) |
|---|---|
| taxonomy / cost codes, units, regions | BOQ items, quantities (human-measured), BOQ imports |
| resources and their rate history | project assumption overrides (`project_assumptions`) |
| assumptions register (defaults), assembly templates | project-scoped provisional rates / allowances |
| commercial policy templates, tax categories, FX | supplier quotations, RFQs, procurement needs |
| Source Register, index observations, import manifests | indirects, duration, clarifications, offers |
| rate candidates (review queue) | estimate versions + their **input snapshots**, exports, reconciliation runs |

A project override never edits the global default (tested: `test_project_assumption_override_does_not_change_global_default`).
A supplier quotation always carries a `project_id` (or is explicitly general) and its original file lives in that project's folder `6. Procurement & Quotations`.

## Location and naming
`<workspaces_dir>/<PROJECT-ID>-<slug>/` — default `<repo>/projects/` (git-ignored; override with `KSA_WORKSPACES_DIR` or `workspaces_dir` in
`config/settings.toml`). Example: `projects/PRJ-0002-office-fitout/`.

* The **project ID** is the identity (`projects.id` is the primary key; creation with an existing ID raises `Conflict`). The slug is cosmetic
  (ASCII, lower-case, ≤40 chars; non-ASCII names fall back to `project`). IDs must match `[A-Za-z0-9][A-Za-z0-9_-]{1,40}` (no path traversal).
* The folder belongs to a project only if its `project.json` says so (`find_existing` matches by manifest `project_id`, not by name prefix).
  A folder that claims another project is refused (`WORKSPACE_CONFLICT`); a pre-existing folder named exactly `<PROJECT-ID>` or restored
  with a matching manifest is **adopted with its files intact**.
* `projects.workspace_path` / `workspace_slug` record the folder (migration `0007`).

## Folder structure (a product requirement — names and numbers are fixed)
```
1. Tender Documents/              originals as received (read-only by convention; the indexer only reads them)
2. AI Context/                    GENERATED: project_index.json, project_summary.md, extracts/docNNNNN_vN.txt (versioned)
3. BOQ & Takeoff/                 BOQ / takeoff uploads (original kept; imports copy as <sha10>_<name>)
4. Clarifications & Assumptions/
5. Estimate & Cost Build-Up/      master workbook exports; versions/<PRJ>_vN_inputs_snapshot.json
6. Procurement & Quotations/      RFQs issued, supplier quotation originals
7. Programme & Indirects/
8. Commercial Submission/         pricing schedule, offer letter, estimate report (PRELIMINARY until released)
9. Reconciliation & Approvals/    reconciliation reports
10. Exports & Archive/            released submission exports, project packages, archives
CLAUDE.md                          project-specific instructions (generated block + preserved human notes)
project.json                       generated manifest
```
Where the application writes: BOQ/takeoff uploads → 3; quotation uploads → 6; master workbook / round-trip uploads → 5; pricing schedule, estimate
report, offer letter → 8; reconciliation report → 9; RFQ files → 6; version snapshots → 5/versions. (`projects.output_dir(pid, area)`.)

## Creation, idempotency and repair
`projects.create_project` → inserts the row, adopts mandatory assumptions, then `workspaces.ensure_workspace`. `ensure_workspace` can be run any
number of times: it creates only what is missing, never deletes or overwrites a file, rewrites `project.json` (generated) and regenerates only the
**generated block** of `CLAUDE.md`. A `CLAUDE.md` without markers (hand-written) is kept intact and the block is appended. UI: *Workspace & documents → Repair folders / regenerate*;
CLI: `python -m app.cli project refresh PRJ-0002`. Legacy projects get a workspace on first use.

## Project `CLAUDE.md`
Generated block (between `<!-- BEGIN GENERATED … -->` and `<!-- END GENERATED -->`): project ID/name, client, tender reference, location/region, type,
trades, currency, design stage, recorded drawing/specification revisions, **library versions** (resource/rate counts, approved real vs synthetic rates,
highest rate id, schema migration), project assumptions by status, commercial policy and status, estimate versions, workspace map, source-file
conventions, human-approval rules, outstanding issues computed from the database (unmapped items, estimate state and blockers) and how to refresh it. No secrets.
Everything under `## Human notes (preserved on refresh)` is yours. Drawing/specification revisions are **recorded by a human** (UI form, `update_project`); the
indexer's file-name revision guesses never populate them.

## Project indexer (`python -m app.cli project index PRJ-0002`, UI *Index documents*)
Read-only scan of the workspace (excluding `2. AI Context/`, hidden files, `CLAUDE.md`, `project.json`). For every file it records path, name, type, size,
modified time, SHA-256, area, category/trade hint/revision **from the file name only**, extraction status/error, extract version and review status in
`project_documents`; writes `project_index.json`, `project_summary.md` (counts and lists only, labelled non-authoritative) and versioned text extracts.

* Text extraction: txt/md/csv/json/xml/html, PDF (pypdf; encrypted or image-only PDFs are reported, **no OCR**), DOCX (python-docx), XLSX (openpyxl, first 5,000 rows/sheet). DWG/DXF/RVT/IFC and everything else → *Not text-extracted* with the reason. Parser failures → *Extraction error* with the message. Nothing is invented.
* Change handling: unchanged hash → untouched. Changed hash → a **new** `docNNNNN_v(n+1).txt` (old extracts kept), `review_status = Source changed - review` until a human presses *Mark reviewed*. Deleted files → `Missing`, never dropped.
* Search: `project search PRJ-0002 "text"` returns snippets from the current extracts.
* The indexer never modifies originals (tested).

## Isolation, versioning and reproducibility
* Estimates reference rate **ids and versions**, never free text: every cost line records `rate_id`, assembly code+version and assumption ids.
* `estimates.freeze_version` also stores an **input snapshot** (`estimate_snapshots`, SHA-256-guarded, plus a copy in `5. …/versions/`): BOQ rows, assembly definitions,
  every rate row of every involved resource *with its status at freeze time*, resolved assumptions, takeoff, FX, policy, tax categories, indirects, duration, library versions, expected results.
  `snapshots.verify_snapshot` proves the pinned rate rows are still stored unchanged and lists newer approved rates; `snapshots.replay_direct_cost` re-runs the direct-cost engine from
  the snapshot alone and must equal the frozen result — after a newer rate has been approved (tested). The commercial tail (indirects/policy/tax) is stored for audit but not re-run (see DATA_MODEL.md).
* Approving a new global rate supersedes the older version for *new* calculations; frozen estimate versions are never rewritten (tested).
* Archive (`archive_project`) makes the project read-only; the workspace stays on disk. Backups include `workspaces/`, `imports/` and `outputs/`; restore never overwrites a differing file
  without `--overwrite-files` (it writes `<name>.restored` beside it). `export-project` packages the workspace under `workspace/`.

## Migration of pre-0007 layouts
`python -m app.cli migrate-workspaces --dry-run` lists what would be copied from `data/projects/<PRJ>/uploads/` and `data/outputs/<PRJ>/` into the numbered folders (no folder is created in a dry run).
A real run first takes and **validates a database backup**, then **copies** (never moves) files, skips identical ones, writes different ones beside an existing target as
`<name>.legacy-<sha8>`, and writes `var/migration_reports/workspaces-<timestamp>.json`. Legacy originals stay; database rows holding legacy absolute paths keep working. Safe to repeat.
The old staging flow's dataset store (`data/projects/_datasets`) is not migrated (it is the store for `rate_staging` datasets only).

## Not implemented
OCR, CAD/BIM text extraction, automatic revision detection from drawing title blocks, automatic folder watchers (indexing is an explicit command), Windows long-path handling beyond the slug limit, access control per workspace folder (single local user model).
