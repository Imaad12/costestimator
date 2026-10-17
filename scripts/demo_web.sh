#!/usr/bin/env bash
# Start the web app on ready-made data so every page has something to show.
#   scripts/demo_web.sh                 # the SYNTHETIC end-to-end tender (project PRJ-9101) - builds it on first run (~1 min)
#   scripts/demo_web.sh practice        # the real-document practice test (needs the PDF in practice_test/input/)
#   scripts/demo_web.sh empty           # a fresh empty database + the small SYNTHETIC demo project (python -m app.cli demo)
# Environment: PORT (default 8000), HOST (default 127.0.0.1 - keep it local; see docs/SECURITY.md), KSA_DEMO_DIR (default /tmp/ksa_demo).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -e ".[dev]"
MODE="${1:-synthetic}"; DIR="${KSA_DEMO_DIR:-/tmp/ksa_demo}/$MODE"; PORT="${PORT:-8000}"; HOST="${HOST:-127.0.0.1}"
export KSA_DB_PATH="$DIR/app.db" KSA_WORKSPACES_DIR="$DIR/workspaces" KSA_SECRET_KEY="demo-only-not-a-secret" KSA_ENVIRONMENT=test
case "$MODE" in
  synthetic)
    if [ ! -f "$DIR/scratch_closure.db" ]; then python scripts/run_closure_scenario.py "$DIR" --out "$DIR-out" > /dev/null; fi
    export KSA_DB_PATH="$DIR/scratch_closure.db"
    echo "SYNTHETIC tender 'Dammam Industrial Utilities' (PRJ-9101). Sign in as test-estimator, test-procurement, test-commercial, test-admin or test-viewer - password: synthetic-only-pw"
    echo "Open: /  then  Projects > PRJ-9101 > Control tower"
    ;;
  practice)
    if [ ! -f "$DIR/scratch_closure.db" ]; then python scripts/run_real_document_practice_test.py "$DIR" > /dev/null; fi
    export KSA_DB_PATH="$DIR/scratch_closure.db"
    echo "Practice test data (PRJ-9201 no rates, PRJ-9203 placeholder rates). Sign in as test-estimator or test-commercial - password: synthetic-only-pw"
    ;;
  empty)
    mkdir -p "$DIR"
    if [ ! -f "$KSA_DB_PATH" ]; then python -m app.cli init --demo-users; python -m app.cli demo > /dev/null; fi
    echo "Sign in as estimator / procurement / commercial - password: demo-only-change-me (or admin with the password printed by init)"
    ;;
  *) echo "unknown mode '$MODE'"; exit 2 ;;
esac
echo "Serving on http://$HOST:$PORT  (Ctrl-C to stop)"
exec python -m app.cli run --host "$HOST" --port "$PORT"
