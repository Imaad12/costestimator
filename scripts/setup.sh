#!/usr/bin/env bash
# One-shot local setup: virtualenv, dependencies, database, reference data. Usage: scripts/setup.sh [--demo]
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -e ".[dev]"
python -m app.cli init --demo-users
[ "${1:-}" = "--demo" ] && python -m app.cli demo
echo "Done. Start with: scripts/run.sh"
