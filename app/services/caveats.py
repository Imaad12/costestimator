"""Reliance caveats of an estimate: things that make a numerically 'Complete' estimate unfit to rely on. Read-only; nothing here changes a number.

The engine's own state label already says SYNTHETIC when synthetic rates are used. The caveats below come from the database (checks only a service can make) and are shown in the completeness
report, the Basis of Estimate banner and the estimate API; the readiness gate turns the blocking ones into reasons.
"""
from __future__ import annotations

import json

from ..database import Database
from . import assumptions as asm


def estimate_caveats(db: Database, project_id: str, est) -> list[str]:
    out: list[str] = []
    if est.flags.get("synthetic"):
        out.append("synthetic (placeholder / demonstration) rates or data are in use - not market evidence")
    if est.flags.get("provisional"):
        out.append("provisional (project-scoped) inputs are in use")
    for imp in db.all("SELECT id, summary_json FROM boq_imports WHERE project_id=?", (project_id,)):
        sm = json.loads(imp["summary_json"] or "{}")
        if sm.get("unverified_transcription"):
            out.append(f"BOQ import #{imp['id']} is a transcription from '{(sm.get('derived_from') or {}).get('source_file')}' that no second person has checked - every quantity is unverified")
    p = db.one("SELECT region, currency, basis_defaulted FROM projects WHERE id=?", (project_id,))
    if p and p["basis_defaulted"]:
        out.append(f"region/currency ({p['region']} / {p['currency']}) are system defaults, not confirmed by a person")
    bad = []
    for aid in sorted(getattr(est.direct, "used_assumptions", set()) or set()):
        ra = asm.resolve(db, project_id, aid)
        if not ra.approved:
            bad.append(aid)
    if bad:
        out.append("assumption(s) feed the estimate without approval: " + ", ".join(bad[:8]))
    return out
