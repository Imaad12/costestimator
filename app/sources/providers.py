"""Concrete providers.  Status words are literal:

  implemented exercised by offline tests against the documented interface (mocked/recorded responses); `live_verified` says what was observed for real
  manual-only  no automated access is permitted or documented; a file the user obtained legitimately can be imported
  blocked      automated access is blocked from the environment/by the operator; manual import remains available

A provider's `refresh` returns a report dict and NEVER approves or publishes anything.
"""
from __future__ import annotations

import json
import tempfile
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

from ..config import BASE_DIR
from ..core.timeutil import now_iso, today
from ..database import Database
from ..rate_updates import candidates as cand
from ..rate_updates import index_import
from . import webprice
from .base import AccessPolicy, FetchResult, Fetcher, ProviderInfo, log_access

KAPSARC_DATASET = "construction-cost-index-series-by-sections-and-groups-at-national-level"
KAPSARC_BASE = f"https://datasource.kapsarc.org/api/explore/v2.1/catalog/datasets/{KAPSARC_DATASET}"
PRICE_WATCHLIST = BASE_DIR / "config" / "price_sources.json"


class KapsarcGastatCci:
    """GASTAT Construction Cost Index as republished on the KAPSARC Data Portal (Opendatasoft Explore API v2.1, documented, no key).

    Output: index observations only (escalation reference). Never rate candidates."""
    info = ProviderInfo(
        "kapsarc-gastat-cci", "GASTAT Construction Cost Index via KAPSARC Data Portal", "SRC-002", "official-index", "implemented",
        "Monthly CCI index/M-o-M/Y-o-Y series by section and group (basic materials, labour, equipment rental, energy). An INDEX - not a unit price.",
        "https://datasource.kapsarc.org/explore/assets/" + KAPSARC_DATASET + "/",
        "Open the dataset page in a browser, export CSV (or save the API 'records' JSON) and run: python -m app.cli index import <file> --dataset cci --source SRC-002",
        "index observations",
        live_verified="API shape, fields, licence metadata and 2026-04 records verified 2026-10-12 through a proxy fetch tool; the application's own HTTP client was NOT able to reach the host from the build sandbox (see source_access_log).")
    policy = AccessPolicy(min_interval_s=3.0, max_retries=2, allowed_hosts=("datasource.kapsarc.org",), cache_ttl_s=6 * 3600, respect_robots=True,
                          terms_note="Dataset metadata states licence 'Public Domain', publisher GASTAT (verified 2026-10-12). Cite the publisher.")
    page_size = 100
    max_pages = 40

    def urls(self, since: str) -> list[str]:
        w = quote(f"time_period>=date'{since}-01'")
        return [f"{KAPSARC_BASE}/records?limit={self.page_size}&offset=0&where={w}&order_by={quote('time_period,measure,section_and_group')}"]

    def refresh(self, db: Database, actor, fetcher: Fetcher, *, dry_run: bool, months_back: int = 14) -> dict:
        since_d = today().replace(day=1) - timedelta(days=30 * months_back)
        since = f"{since_d.year:04d}-{since_d.month:02d}"
        first = self.urls(since)[0]
        rep = {"provider": self.info.id, "dry_run": dry_run, "planned_requests": [first, "... then offset += 100 until total_count is read"], "since": since}
        if dry_run:
            log_access(db, self.info.id, url=first, outcome="DRY_RUN", note="refresh --dry-run: no network request made")
            rep["outcome"] = "DRY_RUN"
            return rep
        results: list[dict] = []
        total = None
        offset = 0
        for _ in range(self.max_pages):
            url = first.replace("offset=0", f"offset={offset}")
            res = fetcher.fetch(url, self.policy)
            log_access(db, self.info.id, res)
            if not res.ok:
                rep.update(outcome=res.outcome, error=res.error, status=res.status, fetched_records=len(results))
                return rep
            try:
                data = json.loads(res.text())
            except ValueError:
                rep.update(outcome="ERROR", error="Response was not JSON", fetched_records=len(results))
                return rep
            if "results" not in data:
                rep.update(outcome="ERROR", error=f"Unexpected API response: {str(data)[:200]}", fetched_records=len(results))
                return rep
            total = data.get("total_count", total)
            results += data["results"]
            offset += self.page_size
            if total is None or offset >= total or not data["results"]:
                break
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / f"kapsarc_cci_since_{since}_retrieved_{now_iso()[:10]}.records.json"
            f.write_text(json.dumps({"total_count": total, "results": results}, ensure_ascii=False), encoding="utf-8")
            try:
                out = index_import.import_index_file(db, actor, f, dataset="gastat-cci", source_id=self.info.source_id, source_name=self.info.name,
                                                     source_url=KAPSARC_BASE, description=f"API refresh since {since}; {len(results)} record(s)",
                                                     adapter=self.info.id)
                rep.update(outcome="OK", **out)
            except Exception as e:  # duplicate hash -> unchanged data
                rep.update(outcome="NOT_MODIFIED" if getattr(e, "code", "") == "ALREADY_IMPORTED" else "ERROR", error=str(e))
        return rep


class GastatSite:
    """The GASTAT website itself. No documented public data API was found for the CCI; the pages are not fetched automatically."""
    info = ProviderInfo(
        "gastat-site", "GASTAT statistics website (stats.gov.sa)", "SRC-001", "official-index", "manual-only",
        "Official publisher of the Construction Cost Index and other price statistics. No documented download API was found; automated fetching is "
        "disabled. During development the host returned HTTP 502 to the research tool and was unreachable from the sandbox's own HTTP client.",
        "https://stats.gov.sa/en/statistics-tabs?tab=436312&category=3453505",
        "Download the release (xlsx/csv) in a normal browser. If it is a long table (period, series, value) import it with `index import`; "
        "otherwise use the KAPSARC export of the same series (SRC-002). The file layout of GASTAT's own xlsx has NOT been inspected.",
        "index observations")
    policy = AccessPolicy(automated_access=False, terms_note="Terms: https://www.stats.gov.sa/en/page/45 (not reviewed by this project).")

    def refresh(self, db, actor, fetcher, *, dry_run: bool, **kw) -> dict:
        log_access(db, self.info.id, url=self.info.docs_url, outcome="SKIPPED", note="manual-only provider")
        return {"provider": self.info.id, "dry_run": dry_run, "outcome": "SKIPPED", "error": "Manual-only source: " + self.info.manual_alternative}


class EtimadAwards:
    """Etimad (government tenders platform). Tender metadata is public to view, but it has no documented public price API and its
    terms were not reviewed.  Award values are NOT market quotations.  Manual import only; rows are flagged accordingly."""
    info = ProviderInfo(
        "etimad-awards", "Etimad awarded-tender records", "SRC-006", "procurement-records", "manual-only",
        "Public tender/award listing. No scraping, no authentication bypass. Award totals are contract values, rarely unit prices, and are never "
        "treated as a current market quotation.",
        "https://tenders.etimad.sa",
        "Where reuse is permitted, copy award unit prices you have read into the rate-import template with source URL and date; import with "
        "`rates import <file> --source SRC-006 --source-type 'Public tender award'`. Rows land in 'Requires Verification'.",
        "rate candidates (flagged AWARD_NOT_MARKET_QUOTE)")
    policy = AccessPolicy(automated_access=False, terms_note="Terms of use not reviewed; automated access disabled.")

    def refresh(self, db, actor, fetcher, *, dry_run: bool, **kw) -> dict:
        log_access(db, self.info.id, url=self.info.docs_url, outcome="SKIPPED", note="manual-only provider")
        return {"provider": self.info.id, "dry_run": dry_run, "outcome": "SKIPPED", "error": "Manual-only source: " + self.info.manual_alternative}


class WebPriceWatchlist:
    """Operator-curated list of public product pages (config/price_sources.json).  Nothing is shipped in the list: the project does not
    invent suppliers.  Each page is fetched politely (robots.txt, rate limit, cache) and read with webprice.extract_candidates."""
    info = ProviderInfo(
        "web-price-watchlist", "Public supplier/manufacturer product pages (operator watchlist)", None, "web-prices", "implemented",
        "Fetches only the URLs the operator lists, extracts product/spec/price evidence and creates pending rate candidates. Pages that publish "
        "only specifications yield specification-only candidates (no price inferred).", None,
        "Save the page (HTML) or copy the quoted price into the rate-import template and use `rates import`.", "rate candidates")
    policy = AccessPolicy(min_interval_s=10.0, max_retries=1, respect_robots=True, cache_ttl_s=12 * 3600,
                          terms_note="Only permitted public pages; honour robots.txt and each site's terms.")

    def watchlist(self, path: Path | None = None) -> list[dict]:
        p = path or PRICE_WATCHLIST
        if not p.exists():
            return []
        data = json.loads(p.read_text(encoding="utf-8"))
        return [e for e in data.get("pages", []) if e.get("url") and not e.get("disabled")]

    def refresh(self, db: Database, actor, fetcher: Fetcher, *, dry_run: bool, watchlist: list[dict] | None = None, **kw) -> dict:
        pages = watchlist if watchlist is not None else self.watchlist()
        rep = {"provider": self.info.id, "dry_run": dry_run, "pages": len(pages), "planned_requests": [p["url"] for p in pages]}
        if not pages:
            rep.update(outcome="SKIPPED", error="Watchlist is empty (config/price_sources.json has no pages). Nothing is invented.")
            return rep
        if dry_run:
            for p in pages:
                log_access(db, self.info.id, url=p["url"], outcome="DRY_RUN")
            rep["outcome"] = "DRY_RUN"
            return rep
        created, dup, blocked, errors = [], 0, [], []
        for p in pages:
            res = fetcher.fetch(p["url"], self.policy)
            log_access(db, self.info.id, res)
            if not res.ok:
                (blocked if res.outcome in ("BLOCKED", "SKIPPED") else errors).append({"url": p["url"], "outcome": res.outcome, "error": res.error})
                continue
            out = ingest_page(db, actor, p["url"], res, resource_id=p.get("resource_id"), supplier=p.get("supplier"), source_type=p.get("source_type", "Supplier website"))
            created += out["candidate_ids"]
            dup += out["duplicates"]
        rep.update(outcome="OK" if created or not (blocked or errors) else "ERROR", candidates_created=len(created), duplicates=dup, blocked=blocked, errors=errors,
                   candidate_ids=created)
        return rep


def ingest_page(db: Database, actor, url: str, res: FetchResult, *, resource_id: str | None = None, supplier: str | None = None,
                source_type: str = "Supplier website") -> dict:
    """Turn one retrieved page into pending candidates (also used for pages the user saved manually)."""
    from ..core.errors import Conflict, ValidationFailed
    html = res.text()
    raw = webprice.extract_candidates(html, url, retrieved_on=today())
    ids, dup, rejected = [], 0, []
    for rc in raw:
        d = dict(resource_id=resource_id, description=rc.name, specification=rc.specification, source_type=source_type, source_name=supplier or url.split("/")[2],
                 source_url=url, retrieved_at=res.retrieved_at, effective_date=rc.effective_date, valid_until=(rc.price_valid_until or "")[:10] or None,
                 geography=rc.geography, currency=rc.currency, unit=rc.unit_text, original_price=rc.price, tax_basis=rc.tax_basis,
                 delivery_basis=rc.delivery_basis, installation_included=rc.installation_included, price_kind=rc.price_kind,
                 confidence="Low" if rc.method.startswith(("JSON-LD", "Microdata", "OpenGraph")) else "Unverified", extraction_method=rc.method,
                 evidence_snippet=rc.snippet, flags=list(rc.flags), source_published_at=rc.page_date)
        # unit text from web pages is free text: keep only if the registry can resolve it
        try:
            ids.append(cand.create_candidate(db, actor, d))
        except Conflict:
            dup += 1
        except ValidationFailed as e:
            rejected.append({"name": rc.name, "errors": e.details or [e.message]})
    return {"candidate_ids": ids, "duplicates": dup, "rejected": rejected, "found": len(raw)}


PROVIDERS = {p.info.id: p for p in (KapsarcGastatCci(), GastatSite(), EtimadAwards(), WebPriceWatchlist())}
