---
name: project-initializer
description: Create a new construction project with its numbered workspace, project CLAUDE.md and manifest, then walk the human through recording context and the first documents. Use when the user asks to start/set up a new project or tender.
allowed-tools: Read, Glob, Grep, Bash(python -m app.cli *), Bash(ls *)
argument-hint: <project name> [client] [location]
disable-model-invocation: true
---

# project-initializer

## Purpose
Start a project correctly: a unique project ID, the ten numbered folders, a generated project `CLAUDE.md` and `project.json`, and a checklist of what a human must still record. Never confuses the project workspace with the global libraries.

## When to use
A new tender/job must be set up; a legacy project lacks a workspace (use `project refresh`); the workspace folders were damaged or deleted.

## Required context and inputs
Project name (required); client, tender reference, location/region, project type, applicable trades, design stage (optional, human-supplied); an authenticated user with an author role (`KSA_CLI_USER`, `KSA_CLI_PASSWORD`). Do not guess missing facts — leave them blank.

## Read first (exact modules, data files, docs)
- `CLAUDE.md` (root)
- `docs/PROJECT_WORKSPACES.md`
- `docs/DATA_MODEL.md`
- `app/services/projects.py`
- `app/services/workspaces.py`
- `data/regions/regions.csv` (valid region codes)

## Steps
1. Check the database is initialised: `python -m app.cli coverage` must show resources > 0 (otherwise run `python -m app.cli init --demo-users` first).
2. List existing projects with `python -m app.cli project list` so the user does not create a duplicate by mistake (project IDs are generated and unique).
3. Create: `python -m app.cli project create --name "…" --client "…" --location "…" --project-type "…" --trades "Architectural,HVAC,…" [--tender-ref …] [--design-stage …] [--demo]` (add `--demo` only for SYNTHETIC test projects).
4. Verify the tree: `ls projects/<PRJ-…>/` shows the ten numbered folders plus `CLAUDE.md` and `project.json` (names and numbers are fixed).
5. Open `projects/<id>/CLAUDE.md`: confirm facts match what the user said and the 'No BOQ imported yet' issue is listed. Do not edit the generated block; put notes under *Human notes*.
6. Tell the human the next actions: copy tender documents into `1. Tender Documents/`, run the project-indexer skill, import the BOQ (boq-import-review skill), record approved drawing/specification revisions (web UI *Workspace & documents* → `update_project`; **only a human states these**).
7. Optionally write `projects/<id>/4. Clarifications & Assumptions/setup_checklist.md` using the schema below.

## Outputs and schemas
`projects/<PRJ-ID>-<slug>/` (10 folders, `CLAUDE.md`, `project.json`) and DB rows `projects`, adopted `project_assumptions`, audit entry. Optional `setup_checklist.md`: sections `## Recorded facts`, `## Missing facts (human to supply)`, `## Next actions`, each a bullet list; no invented values.

## Validation checks
- Exactly one folder matches `<PRJ-ID>-*`; `project.json.project_id` equals the DB id.
- Re-running `project refresh <id>` changes no file contents except generated files (idempotent).
- `python -m pytest tests/workspaces -q` still passes if you touched workspace code.

## Approval requirements
Creating a project needs an author role (Estimator, Procurement Reviewer, Commercial Approver, Administrator). Nothing is approved by this skill. Drawing/specification revisions, trades and policy assignment are human decisions.

## Failure handling
- `Conflict: Project … already exists` → do not retry with force; pick another ID or open the existing project.
- `WORKSPACE_CONFLICT` → a folder belongs to another project; stop and ask the user; never delete or rename it.
- Auth error → ask the user for credentials; never read or print passwords from files.
- Folder permissions/disk errors → report them verbatim.

## Explicitly prohibited
- Measuring, inferring or generating quantities, or editing a quantity without an approved change request.
- Inventing prices, wages, productivity, wastage, suppliers, FX/tax values or benchmarks; filling a missing value with a default or a guess.
- Calling an approve/reject/publish function as, or on behalf of, a human; writing `approvals`, status or `audit_log` rows directly; weakening `app/approvals/policy.py` or a reconciliation rule.
- Editing or overwriting original files in `1. Tender Documents/` or any supplier-supplied original.
- Treating AI output, an extract, a summary or an index as authoritative over the original document.
- Hard-coding project details into the root `CLAUDE.md`.
- Creating folders by hand with different names/numbers.

_Skills orchestrate application functions; they never bypass validation or server-side approvals. AI output remains a suggestion until an authorised human accepts it._
