"""Reproducible input snapshots for frozen estimate versions.

Every `freeze_version` stores, next to the frozen results, a snapshot of the exact records the engine read:
BOQ items, assembly definitions (code+version), the resources and *all* rate rows of those resources (id+version+status at freeze time),
resolved assumption values, takeoff lines, FX rows, commercial policy, tax categories, indirect items and duration.

Why: rate and assumption rows are append-only/immutable once approved, but their *status* changes (Approved -> Superseded) when a
newer version is published.  The snapshot freezes the status as seen at freeze time, so
  * `verify_snapshot` proves the stored records still exist unchanged (immutability check, reports newer rates available), and
  * `replay_direct_cost` re-runs the deterministic direct-cost engine on the snapshot alone and must reproduce the frozen result,
    even after the live library has moved on.
The commercial tail (indirects/policy/tax) is stored for audit; it is not re-computed by `replay` (see docs/DATA_MODEL.md).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from ..core.money import to_text
from ..core.timeutil import now_iso, parse_date
from ..core.units import registry
from ..database import Database, jload, rows_to_dicts
from ..estimators.types import AssemblyDef, AssumptionValue, EstimateInputs
from . import audit, workspaces

SNAPSHOT_SCHEMA = "ksa-estimator/estimate-snapshot/1"
IMMUTABLE_RATE_FIELDS = ("resource_id", "version", "rate_type", "unit_price", "currency", "unit", "region", "price_date", "valid_until",
                         "supplier_id", "source_id", "project_id", "is_synthetic", "tax_basis", "delivery_basis")


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False, separators=(",", ":"))


def build_snapshot(db: Database, est) -> dict:
    """Serialise the inputs of an EstimateResult (`est.inputs`) plus the non-engine inputs read by compute_estimate."""
    inp: EstimateInputs = est.inputs
    pid = inp.project["id"]
    used_rate_ids = sorted(est.direct.used_rates)
    snap = {
        "schema": SNAPSHOT_SCHEMA,
        "project": {k: inp.project.get(k) for k in ("id", "name", "region", "currency", "tax_category", "commercial_policy_id",
                                                     "rate_as_of_date", "design_stage", "drawing_revision", "spec_revision", "is_demo")},
        "as_of": inp.as_of.isoformat(),
        "include_unapproved": inp.include_unapproved,
        "items": inp.items,
        "takeoff": inp.takeoff,
        "assemblies": {code: asdict(a) for code, a in inp.assemblies.items()},
        "resources": inp.resources,
        "rates": inp.rates,                                   # every rate row of every involved resource, with status AT FREEZE TIME
        "used_rate_ids": used_rate_ids,
        "assumptions": {k: asdict(v) for k, v in inp.assumptions.items()},
        "engine_keys": {k: asdict(v) for k, v in inp.engine_keys.items()},
        "fx": inp.fx,
        "region_parents": inp.region_parents,
        "params": inp.params, "item_wbs": inp.item_wbs, "wbs_parent": inp.wbs_parent,
        "policy": {"row": _policy_row(db, inp.project), "resolved": est.policy},
        "tax": {"status": {k: {"rate": to_text(v.get("rate")), "status": v.get("status"), "note": v.get("note")} for k, v in est.tax_status.items()},
                "categories": rows_to_dicts(db.all("SELECT * FROM tax_categories"))},
        "indirect_items": rows_to_dicts(db.all("SELECT * FROM indirect_items WHERE project_id=? ORDER BY code, version", (pid,))),
        "duration": rows_to_dicts(db.all("SELECT * FROM project_durations WHERE project_id=? ORDER BY id", (pid,))),
        "extras": _extras_dict(est),
        "libraries": workspaces.library_versions(db),
        "expected": {
            "state": est.state, "fingerprint": est.fingerprint,
            "direct_cost_total": to_text(est.direct.direct_cost_total),
            "item_direct_cost": {k: to_text(i.direct_cost) for k, i in est.direct.items.items()},
            "totals": {k: to_text(v) for k, v in est.totals().items()},
        },
    }
    snap["inputs_sha256"] = hashlib.sha256(_canon({k: v for k, v in snap.items() if k != "expected"}).encode()).hexdigest()
    return snap


def _extras_dict(est) -> dict | None:
    ex = est.extras
    if ex is None:
        return None
    return {"duration_rows": ex.duration_rows, "indirect_rows": ex.indirect_rows, "policy_row": ex.policy_row, "policy_resolved": ex.policy_resolved,
            "policy_used": [list(x) for x in ex.policy_used], "policy_unresolved": ex.policy_unresolved, "tax_rows": ex.tax_rows}


def _policy_row(db: Database, project: dict) -> dict | None:
    if not project.get("commercial_policy_id"):
        return None
    r = db.one("SELECT * FROM commercial_policies WHERE id=?", (project["commercial_policy_id"],))
    return dict(r) if r else None


def store_snapshot(db: Database, actor, version_id: int, est) -> int:
    v = db.one("SELECT project_id, version_no FROM estimate_versions WHERE id=?", (version_id,))
    snap = build_snapshot(db, est)
    text = json.dumps(snap, indent=1, default=str, ensure_ascii=False)
    sha = hashlib.sha256(text.encode()).hexdigest()
    path = None
    try:
        d = workspaces.area_dir(v["project_id"], "estimate", db) / "versions"
        d.mkdir(exist_ok=True)
        f = d / f"{v['project_id']}_v{v['version_no']}_inputs_snapshot.json"
        if not f.exists():                                # never overwrite a prior snapshot file
            f.write_text(text, encoding="utf-8")
        path = str(f.relative_to(workspaces.resolve_dir(v["project_id"], db)).as_posix())
    except Exception:  # workspace issues must not block freezing; the DB copy is authoritative
        path = None
    sid = db.insert("estimate_snapshots", dict(estimate_version_id=version_id, project_id=v["project_id"], snapshot_json=text, sha256=sha,
                                               file_path=path, created_by=getattr(actor, "username", str(actor)), created_at=now_iso()))
    audit.log(db, actor, "estimate_snapshot", sid, "create", after={"version": version_id, "sha256": sha[:12]}, project_id=v["project_id"])
    return sid


def get_snapshot(db: Database, version_id: int) -> dict | None:
    r = db.one("SELECT * FROM estimate_snapshots WHERE estimate_version_id=?", (version_id,))
    if not r:
        return None
    if hashlib.sha256(r["snapshot_json"].encode()).hexdigest() != r["sha256"]:
        raise ValueError("Stored snapshot failed its integrity hash.")
    return json.loads(r["snapshot_json"])


def verify_snapshot(db: Database, version_id: int) -> dict:
    """Integrity + drift report. `ok` means: the snapshot is intact and every rate row it pinned is still stored unchanged."""
    snap = get_snapshot(db, version_id)
    if snap is None:
        return {"ok": False, "problems": ["No snapshot stored for this estimate version (frozen before snapshots existed)."]}
    problems: list[str] = []
    newer: list[dict] = []
    for rid, rows in snap["rates"].items():
        for r in rows:
            live = db.one("SELECT * FROM resource_rates WHERE id=?", (r["id"],))
            if not live:
                problems.append(f"rate {r['id']} ({rid}) no longer exists")
                continue
            for f in IMMUTABLE_RATE_FIELDS:
                if str(live[f]) != str(r[f]):
                    problems.append(f"rate {r['id']} field {f} changed: {r[f]!r} -> {live[f]!r}")
        used = [r for r in rows if r["id"] in snap["used_rate_ids"]]
        for u in used:
            later = db.all("SELECT id, version, status, unit_price FROM resource_rates WHERE resource_id=? AND region=? AND version>? "
                           "AND status IN ('Approved','Provisional — Approved for This Estimate')", (rid, u["region"], u["version"]))
            for l in later:
                newer.append({"resource_id": rid, "used_rate_id": u["id"], "used_price": u["unit_price"], "newer_rate_id": l["id"],
                              "newer_price": l["unit_price"]})
    for a in snap["assemblies"].values():
        live = db.one("SELECT 1 FROM assemblies WHERE code=? AND version=?", (a["code"], a["version"]))
        if not live:
            problems.append(f"assembly {a['code']} v{a['version']} no longer exists")
    return {"ok": not problems, "problems": problems, "newer_rates_available": newer, "inputs_sha256": snap["inputs_sha256"]}


def inputs_from_snapshot(db: Database, snap: dict) -> EstimateInputs:
    return EstimateInputs(
        project=snap["project"], as_of=date.fromisoformat(snap["as_of"]), items=snap["items"],
        assemblies={c: AssemblyDef(**a) for c, a in snap["assemblies"].items()}, resources=snap["resources"], rates=snap["rates"],
        assumptions={k: AssumptionValue(**v) for k, v in snap["assumptions"].items()},
        engine_keys={k: AssumptionValue(**v) for k, v in snap["engine_keys"].items()}, takeoff=snap["takeoff"], fx=snap["fx"],
        units=registry(db), region_parents=snap["region_parents"], include_unapproved=snap["include_unapproved"],
        params=snap.get("params", {}), item_wbs=snap.get("item_wbs", {}), wbs_parent=snap.get("wbs_parent", {}))


def extras_from_snapshot(snap: dict):
    """EstimateExtras from a snapshot (snapshots frozen before `extras` existed are rebuilt from their older keys)."""
    from ..estimators.estimate import EstimateExtras
    ex = snap.get("extras")
    if ex:
        return EstimateExtras(ex["duration_rows"], ex["indirect_rows"], ex["policy_row"], ex["policy_resolved"], [tuple(x) for x in ex["policy_used"]],
                              ex["policy_unresolved"], ex["tax_rows"])
    pol = snap.get("policy") or {}
    return EstimateExtras(snap.get("duration", []), [r for r in snap.get("indirect_items", []) if r["status"] != "Superseded"], pol.get("row"), pol.get("resolved"), [], [],
                          (snap.get("tax") or {}).get("categories", []))


def replay_estimate(db: Database, version_id: int) -> dict:
    """Re-run the WHOLE deterministic estimate (direct cost, indirects, commercial policy, pricing schedule, tax) on the stored snapshot only - no live
    rates, assumptions, policy or tax rows are read - and compare state, fingerprint and every total with what was frozen."""
    from ..estimators.estimate import compute_estimate_from
    snap = get_snapshot(db, version_id)
    if snap is None:
        return {"ok": False, "problems": ["No snapshot stored for this estimate version."]}
    inp = inputs_from_snapshot(db, snap)
    res = compute_estimate_from(inp, extras_from_snapshot(snap))
    exp = snap["expected"]
    diffs = []
    if res.fingerprint != exp["fingerprint"]:
        diffs.append(f"fingerprint {res.fingerprint[:12]} != frozen {exp['fingerprint'][:12]}")
    if res.state != exp["state"]:
        diffs.append(f"state {res.state} != frozen {exp['state']}")
    now = {k: to_text(v) for k, v in res.totals().items()}
    for k, v in exp["totals"].items():
        if now.get(k) != v:
            diffs.append(f"total {k}: {now.get(k)} != frozen {v}")
    for k, ic in res.direct.items.items():
        if to_text(ic.direct_cost) != exp["item_direct_cost"].get(k):
            diffs.append(f"item {k}: {to_text(ic.direct_cost)} != frozen {exp['item_direct_cost'].get(k)}")
    return {"ok": not diffs, "differences": diffs, "replayed": now, "frozen": exp["totals"], "fingerprint": res.fingerprint, "state": res.state,
            "legacy_snapshot": not snap.get("extras")}


def replay_direct_cost(db: Database, version_id: int) -> dict:
    """Re-run the direct-cost engine on the snapshot only and compare with the frozen result."""
    from ..estimators.direct_cost import compute_direct_cost
    snap = get_snapshot(db, version_id)
    if snap is None:
        return {"ok": False, "problems": ["No snapshot stored for this estimate version."]}
    inp = inputs_from_snapshot(db, snap)
    res = compute_direct_cost(inp)
    exp = snap["expected"]
    diffs = []
    if to_text(res.direct_cost_total) != exp["direct_cost_total"]:
        diffs.append(f"direct total {to_text(res.direct_cost_total)} != frozen {exp['direct_cost_total']}")
    for k, ic in res.items.items():
        if to_text(ic.direct_cost) != exp["item_direct_cost"].get(k):
            diffs.append(f"item {k}: {to_text(ic.direct_cost)} != frozen {exp['item_direct_cost'].get(k)}")
    return {"ok": not diffs, "differences": diffs, "replayed_direct_cost": to_text(res.direct_cost_total), "frozen_direct_cost": exp["direct_cost_total"]}
