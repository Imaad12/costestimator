"""Source refresh + status reporting.  Refresh creates proposals (index observations, pending candidates); it never approves or publishes."""
from __future__ import annotations

from datetime import datetime, timezone

from ..core.timeutil import now_iso, parse_date, today
from ..database import Database, rows_to_dicts
from ..sources.base import Fetcher, HttpFetcher
from ..sources.providers import PROVIDERS
from . import candidates as cand

STALE_AFTER_DAYS = 45          # an official monthly series not refreshed for this long is reported stale


def list_sources(db: Database) -> list[dict]:
    out = []
    for p in PROVIDERS.values():
        i = p.info
        last = db.one("SELECT * FROM source_access_log WHERE provider=? ORDER BY id DESC LIMIT 1", (i.id,))
        last_ok = db.one("SELECT attempted_at FROM source_access_log WHERE provider=? AND outcome IN ('OK','NOT_MODIFIED') ORDER BY id DESC LIMIT 1", (i.id,))
        out.append({"id": i.id, "name": i.name, "register_id": i.source_id, "kind": i.kind, "status": i.status, "automated_access": p.policy.automated_access,
                    "produces": i.produces, "live_verified": i.live_verified, "docs_url": i.docs_url, "manual_alternative": i.manual_alternative, "description": i.description,
                    "last_attempt": dict(last) if last else None, "last_success": last_ok["attempted_at"] if last_ok else None})
    return out


def status_report(db: Database) -> dict:
    srcs = list_sources(db)
    for s in srcs:
        s["effective_status"] = _effective(s)
    stale = []
    for r in db.all("SELECT dataset, MAX(period) latest FROM index_observations GROUP BY dataset"):
        y, m = (int(x) for x in r["latest"].split("-"))
        age = (today() - parse_date(f"{y:04d}-{m:02d}-01")).days
        if age > 120:
            stale.append({"dataset": r["dataset"], "latest_period": r["latest"], "age_days": age})
    return {"generated_at": now_iso(), "sources": srcs, "queue": cand.queue_counts(db), "stale_datasets": stale,
            "index_observations": db.scalar("SELECT COUNT(*) FROM index_observations") or 0,
            "imports": rows_to_dicts(db.all("SELECT id, kind, adapter, source_name, imported_at, status, accepted_rows, rejected_rows FROM import_manifests ORDER BY id DESC LIMIT 10"))}


def _effective(s: dict) -> str:
    la = s["last_attempt"]
    if s["status"] == "manual-only":
        return "manual-only"
    if la is None:
        return "never attempted"
    if la["outcome"] in ("OK", "NOT_MODIFIED"):
        return "reachable"
    if la["outcome"] == "BLOCKED":
        return "BLOCKED (last attempt)"
    if la["outcome"] == "DRY_RUN":
        return "dry-run only (no real attempt yet)"
    return f"{la['outcome']} (last attempt)"


def refresh_sources(db: Database, actor, *, provider_ids: list[str] | None = None, dry_run: bool = True, fetcher: Fetcher | None = None) -> dict:
    """Run each selected provider in isolation. One provider failing never stops another."""
    fetcher = fetcher or HttpFetcher()
    ids = provider_ids or list(PROVIDERS)
    reports, ok, blocked, skipped, errored = [], 0, 0, 0, 0
    before = db.scalar("SELECT COUNT(*) FROM rate_candidates") or 0
    obs_before = db.scalar("SELECT COUNT(*) FROM index_observations") or 0
    for pid in ids:
        p = PROVIDERS.get(pid)
        if p is None:
            reports.append({"provider": pid, "outcome": "ERROR", "error": "unknown provider"})
            errored += 1
            continue
        try:
            rep = p.refresh(db, actor, fetcher, dry_run=dry_run)
        except Exception as e:  # isolation: report and continue
            rep = {"provider": pid, "outcome": "ERROR", "error": f"{type(e).__name__}: {e}"}
        reports.append(rep)
        o = rep.get("outcome")
        ok += o in ("OK", "NOT_MODIFIED")
        blocked += o == "BLOCKED"
        skipped += o in ("SKIPPED", "DRY_RUN")
        errored += o == "ERROR"
    st = cand.queue_counts(db)
    return {"dry_run": dry_run, "started": now_iso(), "providers": reports,
            "summary": {"successful": ok, "blocked": blocked, "skipped_or_dry_run": skipped, "errors": errored,
                        "new_candidates": (db.scalar("SELECT COUNT(*) FROM rate_candidates") or 0) - before,
                        "new_or_revised_index_rows": (db.scalar("SELECT COUNT(*) FROM index_observations") or 0) - obs_before,
                        "unresolved_proposals": sum(st["by_queue"].values()), "expired_rates": st["expired_rates"],
                        "rates_pending_approval": st["rates_pending_approval"]}}
