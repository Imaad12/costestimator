---
name: architecture-maintenance
description: Keep code, schema, tests and documentation consistent when changing the application: migrations, new modules/trades/sources, doc updates, instruction files. Use for any non-trivial code change or when the documentation may be out of date.
allowed-tools: Read, Glob, Grep, Edit, Write, Bash(python -m pytest *), Bash(python -m app.cli *), Bash(python scripts/gen_docs.py), Bash(git status *), Bash(git diff *), Bash(git log *)
argument-hint: <change description>
---

# architecture-maintenance

## Purpose
Prevent drift: the root `CLAUDE.md`, `docs/*`, tests and migrations must describe and cover what the code really does; approval boundaries stay intact.

## When to use
Before and after implementing a feature, migration, provider, importer or trade; when asked to audit or update documentation.

## Required context and inputs
The change request; `git status` (never overwrite uncommitted user changes); the branch you were told to use.

## Read first (exact modules, data files, docs)
- `CLAUDE.md`
- `docs/ARCHITECTURE.md` (status table)
- `docs/DATA_MODEL.md`
- `docs/TESTING.md`
- `docs/EXTENDING.md`
- `docs/DEVELOPMENT_AUDIT.md`
- `docs/NEXT_STEPS.md`
- `app/migrations/` (latest file)

## Steps
1. `git status`, `git log -3`, run `python -m pytest -o addopts="" -q` for a baseline; note failures before editing.
2. Locate the owning layer (estimators pure / services DB / api actions / web / cli). Keep calculation pure, approvals in services via `authorize`, exposure through `api/actions.py`.
3. Schema change → new numbered SQL file in `app/migrations/` (never edit an applied one); update `docs/DATA_MODEL.md` and any backup/export code that lists tables.
4. Add tests first or alongside (independent expected values for money; fake fetchers for network; `tmp_path` for files; nothing may write into the repo).
5. Update the capability record in `docs/capability_matrix.json` (status only changes with its acceptance test automated), then `python scripts/gen_capability_matrix.py`; `tests/unit/test_capability_matrix.py` must stay green.
6. Update docs: the specific doc, the status table in `docs/ARCHITECTURE.md` (implemented / partial / planned), `docs/NEXT_STEPS.md`, `docs/KNOWN_LIMITATIONS.md`, root `CLAUDE.md` if commands/structure/rules changed; run `python scripts/gen_docs.py`.
7. Run the full suite; commit on the designated branch with a clear message; push with `git push -u origin <branch>`; report the real outcome. Do not open a PR unless asked; never touch `main`.

## Outputs and schemas
Code + migration + tests + docs in one commit series; an updated `docs/DEVELOPMENT_AUDIT.md` entry for anything that deviated from earlier claims.

## Validation checks
- Full suite green; new behaviour has tests; `git diff --stat` shows docs changed with code.
- `tests/approvals` pass (AI boundary, source boundary); no new path writes approvals/status outside services.
- Docs distinguish implemented / partial / planned honestly (no 'complete' for a stub).

## Approval requirements
Changes that touch roles, gates, severities or approval records require explicit user instruction; otherwise do not alter them.

## Failure handling
- Failing baseline → record it in the audit doc; do not mask it.
- Migration needed for existing data → provide a dry-run script, backup, report (see `workspace_migration.py`).
- Push failure → retry only on network errors with backoff; report the final state truthfully.

## Explicitly prohibited
- Measuring, inferring or generating quantities, or editing a quantity without an approved change request.
- Inventing prices, wages, productivity, wastage, suppliers, FX/tax values or benchmarks; filling a missing value with a default or a guess.
- Calling an approve/reject/publish function as, or on behalf of, a human; writing `approvals`, status or `audit_log` rows directly; weakening `app/approvals/policy.py` or a reconciliation rule.
- Editing or overwriting original files in `1. Tender Documents/` or any supplier-supplied original.
- Treating AI output, an extract, a summary or an index as authoritative over the original document.
- Force-push, reset, history rewrite, merging into `main`, deleting project data.
- Committing `projects/*`, `var/`, `.env`, client documents or secrets; putting model identifiers in repository artifacts.

_Skills orchestrate application functions; they never bypass validation or server-side approvals. AI output remains a suggestion until an authorised human accepts it._
