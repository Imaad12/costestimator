# Rate update workflow (public sources → reviewed global rates)

Status: **implemented and tested offline** (`app/sources/`, `app/rate_updates/`; UI *Rate updates*; CLI `sources`, `rates`, `index`).
Core estimating never needs internet access. **No real rate has been approved by this work**: the library still has 0 approved real rates.

## Principles
1. Everything automatic produces a **proposal** (index observation or rate *candidate*). Nothing is approved, published or applied automatically.
2. Two human decisions are needed before a price can enter an estimate: *Approved for Publication* (candidate review, role Procurement Reviewer / Commercial Approver / Administrator)
   and then the normal **rate approval** of the published *Pending Review* version (same roles). Estimators can propose, edit matching fields and publish approved candidates, but approve neither.
   AI principals are refused by `approvals.authorize`.
3. The **original price/currency/unit is stored as found and is immutable** (`original_*`); any comparison price is stored separately (`normalised_*`).
4. A blocked or unavailable source is recorded honestly (`source_access_log`) and never affects other sources or normal estimating.
5. No scraper that assumes one site layout; no authentication/CAPTCHA/robots/rate-limit circumvention; an index is never a unit price.

## Providers (provider-independent interface: `app/sources/base.py`)
| Provider id | What | Status | Live evidence |
|---|---|---|---|
| `kapsarc-gastat-cci` (SRC-002) | GASTAT Construction Cost Index republished on the KAPSARC portal through the **documented** Opendatasoft Explore API v2.1 (`…/catalog/datasets/construction-cost-index-series-by-sections-and-groups-at-national-level/records`); fields `time_period, measure (Index / M-o-M / Y-o-Y), section_and_group, index`; metadata licence "Public Domain", publisher GASTAT | **implemented**; paging, import, manifest, dedupe tested with mocked responses | API shape, metadata and the 39 records for 2026-04 were read on 2026-10-12 through a proxy fetch tool and saved verbatim (`data/public_data/gastat_cci/`). **The application's own HTTP client was blocked from this sandbox** (`Tunnel connection failed: 403 Forbidden` while reading robots.txt; the request was then not made). Live success is therefore **unverified**; run `sources refresh` on a normal machine |
| `gastat-site` (SRC-001/003) | stats.gov.sa pages | **manual-only**: no documented download API found; host returned HTTP 502 to the research tool and was unreachable from the sandbox. The layout of GASTAT's own xlsx was not inspected | n/a |
| `etimad-awards` (SRC-006/007) | Etimad public tender/award listings | **manual-only**: no documented public price API; terms not reviewed; award values are contract values, not market quotes. Imported rows are flagged `AWARD_NOT_MARKET_QUOTE` and land in *Requires Verification* | n/a |
| `web-price-watchlist` | public supplier/manufacturer product pages the **operator lists** in `config/price_sources.json` (shipped empty) | **implemented**; extraction + candidate creation tested with fixtures; no live page ever fetched | none |
| (manual) | any CSV/XLSX/JSON price list, a saved web page, a supplier letter typed into the template | **implemented** | n/a |

Commands (all state-changing ones authenticate as a real user: `--user NAME` or `KSA_CLI_USER`, password from `KSA_CLI_PASSWORD` or prompt):
```
python -m app.cli sources list | status
python -m app.cli sources refresh --dry-run            # no network, no login needed; plans requests and reports
python -m app.cli sources refresh [--provider ID]      # live; only providers whose policy permits automated access
python -m app.cli rates validate FILE …                 # dry-run import with a per-row report (stores only a 'Dry run' manifest)
python -m app.cli rates import FILE --source SRC-… --source-name … --source-type "Manual dataset" [--url …] [--dry-run]
python -m app.cli rates pending [--queue Conflicting]
python -m app.cli rates review RC-000012 approve|reject|needs_verification --comment "…"
python -m app.cli rates publish RC-000012               # creates a Pending Review rate version
python -m app.cli index import FILE --dataset gastat-cci --source SRC-002 [--dry-run]
python -m app.cli coverage
```
UI: **Rate updates** (queue, import forms, source status, dry-run/live refresh), candidate detail page (evidence, flags, edit matching, decide, publish), **Approvals** (candidates + published rates awaiting approval).

## Access policy (`AccessPolicy`, per provider)
`automated_access` (False = never contacted), `allowed_hosts`, `min_interval_s`, `max_retries` with exponential backoff (2 s, 4 s …; only for 408/425/429/5xx/timeouts), `timeout_s`, `respect_robots`
(robots.txt must be readable and allow the URL, otherwise nothing is fetched), `cache_ttl_s` (disk cache in `var/source_cache`), `max_bytes`. 401/403/407/451 are **never retried or circumvented**; they are logged as `BLOCKED`.
Every attempt (including dry runs and skips) is a `source_access_log` row. A refresh failing for one provider is isolated from the others.

## Manual / file import (`rates import`)
Accepts CSV, XLSX (sheet *Rate Dataset* of `templates/resource_rate_template.xlsx` or any header row containing a price column plus resource id or description) and JSON.
Header synonyms are listed in `app/rate_updates/importer.py`. **Required per row:** unit price, currency (never assumed), a known resource id (resources are never auto-created), a valid date; the source reference is the URL
you give or `uploaded-file:<stored name>`. Rows failing validation are rejected with the reason; accepted rows become candidates (queue + flags computed). The exact same file is refused the second time (`ALREADY_IMPORTED`).
**Manifest** (`import_manifests` + `var/imports/<sha10>_<file>.manifest-N.json`): original path, SHA-256, source name/URL, timestamp, description, parsing info (columns, rows read), accepted/rejected counts, validation errors, resulting candidate ids.
The original file is copied to `var/imports/` byte-for-byte.

## Public web price discovery (`app/sources/webprice.py`)
For each URL on the watchlist: fetch politely → read **machine-readable markup only** (schema.org JSON-LD `Product/Offer`, microdata `itemprop`, OpenGraph product tags) and, only if none exists, an explicit low-confidence text pattern (`SAR 1,234.50`).
Each candidate stores the exact URL, retrieval timestamp, extraction method and the evidence snippet. Classification (explicit statements only, otherwise `Unknown` + a flag):
price kind (List / Promotional / Quote required / Specification only), currency and Saudi applicability (SAR, `.sa` domain, page mentions), VAT included/excluded, delivery (Delivered / Supply only / unknown), installation, unit text, freshness (`priceValidUntil`, page modified date → `STALE`, `STALE_EXPIRED`, `NO_PAGE_DATE`), contradictions (same SKU, different prices → `CONTRADICTORY`).
A page with a specification but no price yields a **specification-only candidate** (no price inferred; it can inform an RFQ but can never be published). A quote-required page yields `Quote required`.
Inaccessible/disallowed pages → logged; use the manual route.

## Candidate record (`rate_candidates`) — required fields
Resource ID (`resource_id`, or `suggested_resource_id` from deterministic token overlap — never auto-applied) · candidate id (`candidate_ref`, RC-nnnnnn) · description · specification · source type · source name · source id ·
exact source URL / uploaded-file reference · retrieval date · source publication date · effective date (`valid_until`) · geography · currency · unit · **original price** (+ original currency/unit) · normalised price + method + JSON of steps ·
tax basis · delivery basis · installation inclusion · price kind · confidence classification (`Unverified` / `Low` / `Medium`; extraction-based, set to a *classification*, not a score) · extraction method · evidence snippet · flags · queue · status · reviewer, reviewed-at, review comments · manifest id · published rate id.

## Normalisation (`app/rate_updates/normalise.py`) — only when every input is known
1. **Currency → SAR** needs an **Approved** `fx_rates` row `from→SAR` with `rate_date ≤ price date` and not past `valid_until`. (The seeded USD/SAR 3.75 is *Pending Review* and dated 2020, so USD candidates stay *Requires Verification* until a reviewer records and approves a current FX rate.)
2. **Unit → resource unit** only within length/area/volume/mass using the registry's fixed factor (`ton`/`tons` are ambiguous and are not guessed; `t`/`tonne` are fine). Time and counts never convert.
3. **VAT-inclusive → exclusive** needs an **Approved** tax category valid on the price date. Published rates are always **VAT-exclusive** (the commercial engine adds tax on the schedule).
Not done, by design: regional multipliers, index-based "inflation" of a unit price, quantity-break/delivery/installation adjustments without explicit recorded amounts. If any input is missing: `NORMALISATION_INCOMPLETE`, price blank, reason listed.

## Review queue (`rate_candidates.queue`, recomputed on every edit)
`Conflicting` (other open candidate for the same resource/currency/unit with a different price, or `CONTRADICTORY`) › `Expired` (source validity passed, or the library's approved rate for the resource is expired) › `Requires Verification` (any of: VAT/geography/unit/currency unknown, no price, stale, promotional, price range, text-pattern only, unmatched resource, incomplete normalisation, award value, foreign currency) › `Updated` (an approved global rate exists with a different price) › `New`.
Statuses: `Pending Review` → `Needs Verification` (reviewer asked for more) / `Approved for Publication` / `Rejected` (terminal, comment required) → `Published`.
"Rates approved for publication" and "expired rates" / "rates pending approval" appear as counts on the screen. Editable by a human: resource, unit, VAT, delivery, installation, geography, specification, price kind, validity/effective date, confidence — **not** the original price, currency, source or retrieval details.
Approval for publication is refused (with reasons) unless: price present, resource matched, VAT Included/Excluded, price kind not promotional/unknown, source validity not passed, and a complete normalisation (or an original that is already SAR, resource unit, VAT-exclusive).

## Publication and versioning
`rates publish` (author role) turns an *Approved for Publication* candidate into a **new `resource_rates` version with status Pending Review** (rate type from the source type: Manual dataset / Supplier or Manufacturer website → *Published Market Price*, Quotation → *Verified Supplier Quote*, Historical project / Public tender award → *Historical Actual*; evidence text carries candidate ref, URL, retrieval date, original price, basis, normalisation method and reviewer comment).
The rate then needs `approve_rate` (Procurement Reviewer / Commercial Approver / Administrator), which supersedes the previous approved version (kept, linked via `superseded_by`).
**A rate update never alters an approved or frozen estimate**: frozen versions keep their results and input snapshot; new calculations pick the newly approved rate (`snapshots.verify_snapshot` lists "newer rates available"). Tested end-to-end.

## Index series (`rates`-independent)
`index import` / the KAPSARC provider store `index_observations` (dataset, series, measure, period, exact published value). Re-import of an identical file is refused; a revised value is stored as a new row (history kept). The Excel/estimating engines do not read index data; it is an escalation reference for a human choosing an escalation assumption.

## Scheduled / manual refresh
`sources refresh --dry-run` reports what would be requested. A live `sources refresh` is a **manual command** (cron/Task Scheduler may call it; the app never schedules itself and normal estimating never requires it).
The report lists successful/blocked/skipped/failed providers, new candidates, new or revised index rows, stale datasets (>120 days behind), unresolved proposals, expired rates and published rates awaiting approval.

## Not implemented / open
* No live fetch has succeeded from the build sandbox; KAPSARC live behaviour (pagination, robots.txt of the portal) must be confirmed once on a normal network.
* GASTAT's own downloadable file format; Etimad structured award parsing; SCA/Muqawil price reports (copyright disclaimer — permission required); any commercial price database.
* Candidate import has no per-row region/geography column mapping beyond text; regional applicability of a published rate is `KSA-ALL` until a human sets otherwise on the rate.
* The legacy dataset staging flow (`dataset_imports`/`rate_staging`, UI *Settings → datasets*) still exists beside this pipeline; consolidating them is NEXT_STEPS #12.


## Synthetic data
`rates import FILE --synthetic …` (or `extra_flags=["SYNTHETIC_DATA"]` in code) labels every candidate synthetic; publication then creates a *Synthetic Demonstration Rate* (`is_synthetic=1`, evidence prefixed `SYNTHETIC / TEST ONLY / NOT A MARKET QUOTE`). Without the flag a candidate is published as a market/quotation/historical rate according to its source type. Use `--synthetic` for any test or demonstration file; never for real prices.
