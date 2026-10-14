"""Run the SYNTHETIC end-to-end pilot (tests/synthetic_pilot/pilot.py) in a scratch directory and write evidence.json there.

Usage: python scripts/run_synthetic_pilot.py [WORKDIR]      (default: a fresh temporary directory; nothing is written to the repository)
All data is SYNTHETIC / TEST ONLY / NOT A MARKET QUOTE; TEST ACTOR approvals validate software behaviour and are not real approvals."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.synthetic_pilot import pilot  # noqa: E402


def main() -> int:
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="ksa_synthetic_pilot_"))
    ev = pilot.run(work)
    (work / "evidence.json").write_text(json.dumps(ev, indent=1, default=str), encoding="utf-8")
    v = pilot.verdicts(ev)
    print(json.dumps(v, indent=1))
    print("evidence:", work / "evidence.json")
    return 0 if all(x == "PASS" for x in v.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
