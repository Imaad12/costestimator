# Backup and restore

## What is backed up
A consistent snapshot of the SQLite database (SQLite online-backup API - safe while the app runs), plus every file under `data/projects/` (original uploads) and `data/outputs/` (generated files), with `manifest.json`
(app version, creation time, applied migrations, key-table row counts, **SHA-256 of every file**). Backups go to `var/backups/` by default. The signing secret (`var/secret.key`) and `.env` are **not** included.

## Commands
```
python -m app.cli backup [--label before-tender]        # creates + validates; refuses to overwrite an existing backup file
python -m app.cli validate-backup var/backups/FILE.zip  # read-only: zip test, manifest hashes, PRAGMA integrity_check, audit hash chain
python -m app.cli restore var/backups/FILE.zip --yes    # DESTRUCTIVE to the current database (see below)
python -m app.cli export-project PRJ-0001               # self-contained project package (JSON + files) for hand-over/archive
```
Settings -> *Create backup now* (Administrator) is the UI equivalent of `backup`; restore is deliberately command-line only.

## Restore safety
1. Without `--yes` the command prints a warning and exits (code 2) - nothing changes.
2. The backup is **validated first**; an invalid, corrupt, truncated or hash-mismatched backup is refused (`BACKUP_INVALID`).
3. A **safety backup of the current state** (`*-pre-restore.zip`) is created before the database is replaced.
4. Project files are **never silently overwritten**: where a file with the same path but different content already exists, the backup copy is written beside it as `<name>.restored` and the conflict is reported (use `--overwrite-files` to replace).
5. Imports never move or modify user-provided files; originals are kept separately from generated outputs.

## Archiving a project
*Archive* (Commercial Approver/Administrator, with a reason) makes the project read-only (all writing services call `require_active`); `export-project` produces the package. Unarchive requires the same role.

## Schema upgrades
Pending `app/migrations/*.sql` files are applied automatically at startup (recorded in `schema_migrations`). Take a backup before upgrading the code.
