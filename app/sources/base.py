"""Provider interface, access policies and a conservative HTTP fetcher.

* `AccessPolicy` is per-source: minimum interval, retries with exponential backoff, timeout, robots.txt, cache TTL, and
  `automated_access` (False = the application never contacts this source by itself; manual import only).
* `HttpFetcher` uses only the standard library, honours the process proxy settings, caches responses on disk (so repeat refreshes
  do not re-hit a source), never retries authentication / access-control refusals (401/403/407/451) and records every attempt.
* Tests inject a fake fetcher; the test-suite never needs internet access.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from ..config import get_settings
from ..core.timeutil import now_iso
from ..database import Database

USER_AGENT = "KSA-Estimator/0.2 (+local estimating tool; polite, rate-limited; contact: see operator)"
NO_RETRY_STATUS = {400, 401, 403, 404, 405, 407, 410, 451}
RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}


class SourceUnavailable(Exception):
    """A source cannot be used automatically (blocked, not permitted, not configured). Carries the honest reason."""

    def __init__(self, message: str, outcome: str = "BLOCKED"):
        super().__init__(message)
        self.outcome = outcome


@dataclass
class AccessPolicy:
    automated_access: bool = True
    min_interval_s: float = 5.0
    max_retries: int = 2
    backoff_base_s: float = 2.0
    timeout_s: float = 30.0
    respect_robots: bool = True
    cache_ttl_s: int = 24 * 3600
    max_bytes: int = 5_000_000
    allowed_hosts: tuple[str, ...] = ()
    terms_note: str = ""


@dataclass
class FetchResult:
    url: str
    outcome: str                  # OK / BLOCKED / ERROR / NOT_MODIFIED / SKIPPED
    status: int | None = None
    body: bytes | None = None
    content_type: str | None = None
    error: str | None = None
    from_cache: bool = False
    retrieved_at: str = field(default_factory=now_iso)

    @property
    def ok(self) -> bool:
        return self.outcome in ("OK", "NOT_MODIFIED") and self.body is not None

    @property
    def sha256(self) -> str | None:
        return hashlib.sha256(self.body).hexdigest() if self.body is not None else None

    def text(self) -> str:
        return (self.body or b"").decode("utf-8", errors="replace")


class Fetcher(Protocol):
    def fetch(self, url: str, policy: AccessPolicy) -> FetchResult: ...


def log_access(db: Database | None, provider: str, res: FetchResult | None = None, *, url: str | None = None, outcome: str | None = None,
               error: str | None = None, note: str | None = None) -> None:
    if db is None:
        return
    db.insert("source_access_log", dict(provider=provider, url=url or (res.url if res else None), attempted_at=now_iso(),
                                        outcome=outcome or (res.outcome if res else "ERROR"), http_status=res.status if res else None,
                                        error=error or (res.error if res else None), bytes=len(res.body) if res and res.body else None, note=note))


class HttpFetcher:
    def __init__(self, cache_dir: Path | None = None, sleep: Callable[[float], None] = time.sleep,
                 opener: urllib.request.OpenerDirector | None = None):
        self.cache_dir = cache_dir or get_settings().source_cache_dir
        self._sleep = sleep
        self._opener = opener or urllib.request.build_opener()
        self._last_hit: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    # ---- cache
    def _cache_key(self, url: str) -> Path:
        return self.cache_dir / (hashlib.sha256(url.encode()).hexdigest()[:32] + ".json")

    def _cache_get(self, url: str, ttl: int) -> FetchResult | None:
        f = self._cache_key(url)
        if not f.exists():
            return None
        try:
            meta = json.loads(f.read_text(encoding="utf-8"))
            body = (self.cache_dir / meta["body_file"]).read_bytes()
        except (OSError, ValueError, KeyError):
            return None
        if time.time() - meta["fetched_epoch"] > ttl:
            return None
        return FetchResult(url, "OK", meta.get("status"), body, meta.get("content_type"), from_cache=True, retrieved_at=meta["retrieved_at"])

    def _cache_put(self, res: FetchResult) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            key = self._cache_key(res.url)
            bf = key.with_suffix(".body")
            bf.write_bytes(res.body or b"")
            key.write_text(json.dumps({"url": res.url, "status": res.status, "content_type": res.content_type, "retrieved_at": res.retrieved_at,
                                       "fetched_epoch": time.time(), "body_file": bf.name}), encoding="utf-8")
        except OSError:
            pass

    # ---- robots
    def _robots_allows(self, url: str, timeout: float) -> bool:
        p = urllib.parse.urlsplit(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                req = urllib.request.Request(origin + "/robots.txt", headers={"User-Agent": USER_AGENT})
                with self._opener.open(req, timeout=timeout) as r:
                    rp.parse(r.read(200_000).decode("utf-8", "replace").splitlines())
                self._robots[origin] = rp
            except urllib.error.HTTPError as e:
                # 4xx on robots.txt = no restrictions published; 5xx/blocked = be conservative and refuse
                self._robots[origin] = rp if e.code in (404, 410) else None
                if e.code in (404, 410):
                    rp.parse([])
            except Exception:
                self._robots[origin] = None
        rp = self._robots[origin]
        return bool(rp and rp.can_fetch(USER_AGENT, url))

    # ---- fetch
    def fetch(self, url: str, policy: AccessPolicy) -> FetchResult:
        host = urllib.parse.urlsplit(url).hostname or ""
        if not policy.automated_access:
            return FetchResult(url, "SKIPPED", error="Automated access is disabled for this source (manual import only).")
        if policy.allowed_hosts and not any(host == h or host.endswith("." + h) for h in policy.allowed_hosts):
            return FetchResult(url, "SKIPPED", error=f"Host {host} is not in this source's allow-list.")
        cached = self._cache_get(url, policy.cache_ttl_s)
        if cached:
            return cached
        if policy.respect_robots and not self._robots_allows(url, policy.timeout_s):
            return FetchResult(url, "BLOCKED", error="robots.txt disallows (or could not be read for) this URL; not fetched.")
        wait = policy.min_interval_s - (time.monotonic() - self._last_hit.get(host, -1e9))
        if wait > 0:
            self._sleep(wait)
        last: FetchResult | None = None
        for attempt in range(policy.max_retries + 1):
            if attempt:
                self._sleep(policy.backoff_base_s * (2 ** (attempt - 1)))
            self._last_hit[host] = time.monotonic()
            last = self._once(url, policy)
            if last.outcome == "OK":
                self._cache_put(last)
                return last
            if last.status in NO_RETRY_STATUS or (last.status is None and last.outcome == "BLOCKED"):
                break
        return last or FetchResult(url, "ERROR", error="no attempt made")

    def _once(self, url: str, policy: AccessPolicy) -> FetchResult:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.8, */*;q=0.5"})
        try:
            with self._opener.open(req, timeout=policy.timeout_s) as r:
                body = r.read(policy.max_bytes + 1)
                if len(body) > policy.max_bytes:
                    return FetchResult(url, "ERROR", r.status, error=f"Response larger than {policy.max_bytes} bytes; not stored.")
                return FetchResult(url, "OK", r.status, body, r.headers.get("Content-Type"))
        except urllib.error.HTTPError as e:
            out = "BLOCKED" if e.code in (401, 403, 407, 451) else "ERROR"
            return FetchResult(url, out, e.code, error=f"HTTP {e.code} {e.reason}")
        except urllib.error.URLError as e:
            reason = str(getattr(e, "reason", e))
            blocked = any(k in reason.lower() for k in ("tunnel", "proxy", "refused", "forbidden", "name or service not known", "resolution"))
            return FetchResult(url, "BLOCKED" if blocked else "ERROR", error=f"{type(e).__name__}: {reason}")
        except TimeoutError:
            return FetchResult(url, "ERROR", error="timeout")
        except Exception as e:  # ssl, connection reset...
            return FetchResult(url, "ERROR", error=f"{type(e).__name__}: {e}")


@dataclass
class ProviderInfo:
    id: str                       # stable provider id, e.g. 'kapsarc-gastat-cci'
    name: str
    source_id: str | None         # Source Register id (data/sources/source_register.csv)
    kind: str                     # official-index / procurement-records / web-prices / manual
    status: str                   # functional / manual-only / blocked / stub
    description: str
    docs_url: str | None = None
    manual_alternative: str = ""
    produces: str = ""            # index observations / rate candidates


class Provider(Protocol):
    info: ProviderInfo
    policy: AccessPolicy

    def refresh(self, db: Database, actor, fetcher: Fetcher, *, dry_run: bool) -> dict: ...
