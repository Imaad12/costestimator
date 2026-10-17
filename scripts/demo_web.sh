#!/usr/bin/env bash
# Start the web app on ready-made data so every page has something to show.
#   scripts/demo_web.sh                 # the SYNTHETIC end-to-end tender (project PRJ-9101) - builds it on first run (~1 min)
#   scripts/demo_web.sh practice        # the real-document practice test (needs the PDF in practice_test/input/)
#   scripts/demo_web.sh empty           # a fresh empty database + the small SYNTHETIC demo project (python -m app.cli demo)
#   scripts/demo_web.sh dev             # YOUR working database (var/dev, kept between runs) and one 'superuser' login (password shown once, or KSA_SUPERUSER_PASSWORD)
#                                       # add KSA_ALLOW_SELF_APPROVAL=true in front if you want that one login to approve its own work while tuning (off by default)
# Environment: PORT (first port to try, default 8731 - a rarely used one), HOST (default 127.0.0.1 - keep it local; see docs/SECURITY.md), KSA_DEMO_DIR (default /tmp/ksa_demo).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -e ".[dev]"
MODE="${1:-synthetic}"; DIR="${KSA_DEMO_DIR:-/tmp/ksa_demo}/$MODE"; PORT="${PORT:-8731}"; HOST="${HOST:-127.0.0.1}"
export KSA_DB_PATH="$DIR/app.db" KSA_WORKSPACES_DIR="$DIR/workspaces" KSA_SECRET_KEY="demo-only-not-a-secret" KSA_ENVIRONMENT=test
case "$MODE" in
  synthetic)
    if [ ! -f "$DIR/scratch_closure.db" ]; then python scripts/run_closure_scenario.py "$DIR" --out "$DIR-out" > /dev/null; fi
    export KSA_DB_PATH="$DIR/scratch_closure.db"
    echo "SYNTHETIC tender 'Dammam Industrial Utilities' (PRJ-9101). Sign in as test-estimator, test-procurement, test-commercial, test-admin or test-viewer - password: synthetic-only-pw"
    echo "Open the printed URL, then Projects > PRJ-9101 > Control tower"
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
  dev)
    # Development mode: persistent data and one superuser. A 'test' principal in a 'test' environment, so every export stays DEMONSTRATION. Self-approval is whatever you set in the environment.
    DIR="${KSA_DEV_DIR:-$PWD/var/dev}"
    mkdir -p "$DIR"
    export KSA_DB_PATH="$DIR/app.db" KSA_WORKSPACES_DIR="$DIR/workspaces"
    [ -f "$DIR/secret" ] || python -c "import secrets;print(secrets.token_hex(24))" > "$DIR/secret"
    export KSA_SECRET_KEY="$(cat "$DIR/secret")"
    if [ ! -f "$KSA_DB_PATH" ]; then python -m app.cli init > /dev/null; fi
    python -m app.cli superuser
    echo "DEVELOPMENT MODE - data lives in $DIR - self-approval is ${KSA_ALLOW_SELF_APPROVAL:-false}"
    ;;
  *) echo "unknown mode '$MODE'"; exit 2 ;;
esac
# Pick a port nobody uses. "Free" is judged conservatively: nothing may answer on it AND it must be bindable on IPv4 and IPv6, on loopback and on the wildcard
# address - another program (a Docker/WSL/Windows service, an IPv6-only listener, a dashboard bound to 0.0.0.0) can own a port that a plain IPv4 connect test cannot see.
PORT=$(python - "$PORT" <<'PY'
import socket, sys
def busy(port):
    for fam, addr in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET, "0.0.0.0"), (socket.AF_INET6, "::1"), (socket.AF_INET6, "::")):
        try:
            probe = socket.socket(fam, socket.SOCK_STREAM)
        except OSError:
            continue                                   # this address family is not available here
        with probe:
            probe.settimeout(0.3)
            if addr not in ("0.0.0.0", "::") and probe.connect_ex((addr, port)) == 0:
                return f"something answers on {addr}"
        with socket.socket(fam, socket.SOCK_STREAM) as b:
            try:
                b.bind((addr, port))
            except OSError:
                return f"cannot bind {addr}"
    return None
start = int(sys.argv[1])
for port in range(start, start + 100):
    why = busy(port)
    if why is None:
        print(port); break
    print(f"port {port} skipped: {why}", file=sys.stderr)
else:
    sys.exit("no free port found")
PY
)
python -m app.cli run --host "$HOST" --port "$PORT" &
SRV=$!
trap 'kill $SRV 2>/dev/null || true' EXIT INT TERM
python - "$HOST" "$PORT" <<'PY'
import re, sys, time, urllib.request
url = f"http://{sys.argv[1]}:{sys.argv[2]}/login"
for _ in range(60):
    try:
        html = urllib.request.urlopen(url, timeout=2).read().decode("utf-8", "replace"); break
    except Exception:
        time.sleep(0.5)
else:
    sys.exit("The web app did not start - see the messages above.")
title = (re.search(r"<title>([^<]*)", html) or [None, ""])[1]
if "KSA Construction Estimating Suite" not in title:
    sys.exit(f"ANOTHER application answered at {url} (title: '{title}'). Stop it or set PORT=<free port> and run again.")
print(f"Verified: '{title}' is answering.")
PY
echo "Open  http://$HOST:$PORT   (Ctrl-C to stop)"
wait $SRV
