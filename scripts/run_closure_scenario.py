"""Run the SYNTHETIC end-to-end tender closure scenario (tests/closure/scenario.py) in a fresh scratch directory.

Usage: python scripts/run_closure_scenario.py [WORKDIR] [--out DIR]
  WORKDIR  fresh scratch directory (default: a new temporary directory); the scratch database and workspaces live there
  --out    where the generated tender pack, handover pack, MANIFEST.json and acceptance_results.json are written (default: WORKDIR/demo_output)
Everything is SYNTHETIC: fictional customer, quantities, rates, norms and quotations; every actor is a registered TEST ACTOR; the packs are DEMONSTRATION packs that can never be submission-ready.
Exit code 0 only if every stage is PASS."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.closure import scenario  # noqa: E402


def main(argv: list[str]) -> int:
    out = None
    args = list(argv)
    if "--out" in args:
        i = args.index("--out")
        out = Path(args[i + 1])
        del args[i:i + 2]
    work = Path(args[0]) if args else Path(tempfile.mkdtemp(prefix="ksa_closure_"))
    ev = scenario.run(work, out)
    root = Path(ev.get("_summary", {}).get("out_root", work / "demo_output"))
    root.mkdir(parents=True, exist_ok=True)
    v = scenario.verdicts(ev)
    results = dict(scenario="Dammam Industrial Utilities - Synthetic Tender Closure", synthetic=True, banner=scenario.Dt.BANNER, verdicts=v, all_pass=all(x == "PASS" for x in v.values()),
                   stages={k: x for k, x in ev.items() if not k.startswith("_")})
    (root / "acceptance_results.json").write_text(json.dumps(results, indent=1, default=str, sort_keys=False), encoding="utf-8")
    print(json.dumps(v, indent=1))
    print("results:", root / "acceptance_results.json")
    return 0 if results["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
