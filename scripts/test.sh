#!/usr/bin/env bash
# Repeatable test command. LibreOffice-based workbook recalculation tests are skipped automatically if `soffice` is absent.
set -euo pipefail
cd "$(dirname "$0")/.."
. .venv/bin/activate
exec python -m pytest "$@"
