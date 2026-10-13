"""Renders docs/ESTIMATING_CAPABILITY_MATRIX.md (tables between markers) from docs/capability_matrix.json.
The JSON is the maintained source; tests/unit/test_capability_matrix.py checks every reference in it against the repository.
Run: python scripts/gen_capability_matrix.py"""
from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "capability_matrix.json"
DOC = ROOT / "docs" / "ESTIMATING_CAPABILITY_MATRIX.md"
IT, IU, PA, MI, NA = "Implemented and tested", "Implemented but unverified", "Partial", "Missing", "Not Applicable"
SHORT = {IT: "IT", IU: "IU", PA: "PA", MI: "MI", NA: "NA"}


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def required_for(records: list[dict], level: int) -> list[dict]:
    """A capability with required_from=N is needed at level N and at every more demanding level (numerically lower)."""
    return [r for r in records if r["required_from"] >= level]


def verdict(recs: list[dict]) -> str:
    st = Counter(r["status"] for r in recs)
    if st[MI]:
        return "NOT SUPPORTED (missing capabilities)"
    if st[PA] or st[IU]:
        return "CONDITIONALLY SUPPORTED (partial / unverified items)"
    return "SUPPORTED (all required engine capabilities implemented and tested)"


def rollup(d: dict) -> str:
    recs = d["records"]
    out = ["| Level | Name | Required capabilities (engine) | IT | IU | PA | MI | Verdict (engine) |", "|---|---|---|---|---|---|---|---|"]
    for lv in ("5", "4", "3", "2", "1"):
        eng = [r for r in required_for(recs, int(lv)) if r["kind"] == "engine"]
        c = Counter(r["status"] for r in eng)
        out.append(f"| {lv} | {d['levels'][lv]['name']} | {len(eng)} | {c[IT]} | {c[IU]} | {c[PA]} | {c[MI]} | **{verdict(eng)}** |")
    data = [r for r in recs if r["kind"] == "data"]
    out += ["", "Data readiness (applies to every level): " + "; ".join(f"{r['id']} {r['capability'].split(':', 1)[-1].strip()} - **{r['status']}**" for r in data) + "."]
    tot = Counter(r["status"] for r in recs)
    out += ["", f"All {len(recs)} capability records: " + ", ".join(f"{s} {tot[s]}" for s in (IT, IU, PA, MI, NA)) + "."]
    return "\n".join(out)


def by_area(d: dict) -> "OrderedDict[str, list[dict]]":
    g: "OrderedDict[str, list[dict]]" = OrderedDict()
    for r in d["records"]:
        g.setdefault(r["area"], []).append(r)
    return g


def area_summary(d: dict) -> str:
    out = ["| Area | Records | IT | IU | PA | MI |", "|---|---|---|---|---|---|"]
    for a, rs in by_area(d).items():
        c = Counter(r["status"] for r in rs)
        out.append(f"| {a} | {len(rs)} | {c[IT]} | {c[IU]} | {c[PA]} | {c[MI]} |")
    return "\n".join(out)


def detail(d: dict) -> str:
    L: list[str] = []
    for a, rs in by_area(d).items():
        L += [f"### {a}", "", "| ID | Capability | Status | Needed from level |", "|---|---|---|---|"]
        L += [f"| {r['id']} | {r['capability']} | {SHORT[r['status']]} {r['status']} | {r['required_from']}{' (data)' if r['kind'] == 'data' else ''} |" for r in rs]
        L.append("")
        for r in rs:
            L.append(f"**{r['id']} - {r['capability']}**  ")
            L.append(f"*Status:* {r['status']} · *needed from level:* {r['required_from']} · *kind:* {r['kind']}")
            L.append(f"- *Code:* " + ("; ".join(f"`{c}`" for c in r["code"]) if r["code"] else "none (nothing implements this)"))
            if r["tests"]:
                L.append("- *Tests:* " + "; ".join(f"`{t['ref'].split('/', 1)[1] if t['ref'].startswith('tests/') else t['ref']}` [{t['verdict']}]" + (f" ({t['note']})" if t["note"] else "") for t in r["tests"]))
            else:
                L.append("- *Tests:* none")
            L.append(f"- *Workflow / output:* {r['output']}")
            L.append(f"- *Limitations / dependencies:* {r['limits']}" + (f" Depends on: {', '.join(r['depends'])}." if r["depends"] else ""))
            L.append(f"- *Acceptance test to mark complete:* {r['acceptance']}")
            L.append("")
    return "\n".join(L)


def splice(text: str, name: str, body: str) -> str:
    b, e = f"<!-- {name}_BEGIN -->", f"<!-- {name}_END -->"
    if b not in text or e not in text:
        raise SystemExit(f"markers {name} missing in {DOC}")
    return text[: text.index(b) + len(b)] + "\n" + body + "\n" + text[text.index(e):]


def render(text: str, d: dict) -> str:
    text = splice(text, "ROLLUP", rollup(d))
    text = splice(text, "AREAS", area_summary(d))
    return splice(text, "DETAIL", detail(d))


if __name__ == "__main__":
    d = load()
    DOC.write_text(render(DOC.read_text(encoding="utf-8"), d), encoding="utf-8")
    print("rendered", len(d["records"]), "records")
