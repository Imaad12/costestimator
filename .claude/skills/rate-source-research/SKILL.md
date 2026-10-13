---
name: rate-source-research
description: Research and record public data sources for Saudi construction rates/indices (access, terms, format) in the Source Register and access log, and implement or update a provider if a permitted, documented route exists. Use when looking for rate sources or when an adapter must be built/changed.
allowed-tools: Read, Glob, Grep, Edit, Write, Bash(python -m pytest *), Bash(python -m app.cli sources *), WebFetch, WebSearch
argument-hint: <source or topic>
disable-model-invocation: true
---

# rate-source-research

## Purpose
Find out what is genuinely available, legally and technically, and record it honestly — successes, partial reads and blocks — without fabricating data or circumventing controls.

## When to use
Searching for new official/public datasets; GASTAT/KAPSARC/Etimad/open-data questions; a provider breaks; before adding a provider.

## Required context and inputs
A topic or URL; knowledge of what network access exists (direct HTTP may be blocked in cloud sandboxes). Prefer official documentation.

## Read first (exact modules, data files, docs)
- `docs/KSA_DATA_SOURCES.md`
- `data/sources/source_register.csv`
- `data/sources/ACCESS_LOG.md`
- `docs/RATE_UPDATE_WORKFLOW.md`
- `app/sources/base.py` (AccessPolicy, HttpFetcher)
- `app/sources/providers.py`
- `tests/sources/test_rate_pipeline.py`

## Steps
1. Check the register/access log first; do not repeat a documented blocked attempt in a loop.
2. Locate official documentation for the dataset/API (not mirrors) and read the licence/terms text actually shown; note what you could not read.
3. Prefer downloadable files or documented APIs. Fetch sparingly (one request per question; respect robots.txt, rate limits, auth walls, CAPTCHAs). If blocked, record the exact error and URL once and stop.
4. Record in `data/sources/source_register.csv` (id, url, dates, geography, currency, unit basis, trades, licence conditions *as read*, extraction method, access status, limitations, confidence) and append numbered rows to `ACCESS_LOG.md`; run `python scripts/gen_docs.py`.
5. Save any retrieved data **verbatim** under `data/public_data/<name>/` with a `PROVENANCE.md` (request URL, date, tool used, what it is and is not).
6. If a documented, permitted route exists: add/extend a provider in `app/sources/providers.py` with an explicit `AccessPolicy`; write offline tests with `FakeFetcher`/recorded fixtures; set `live_verified` text to what was actually observed. If not: mark manual-only and document the manual import path.
7. Import samples via `python -m app.cli index import … --dry-run` first (indices) or `rates validate` (price lists).

## Outputs and schemas
Updated `source_register.csv`, `ACCESS_LOG.md`, `docs/KSA_DATA_SOURCES.md` (regenerated table), optional `data/public_data/<name>/` files + `PROVENANCE.md`, provider code + tests. Status vocabulary: Accessed / Partially accessed / Blocked / Not attempted.

## Validation checks
- Every fact in the register cites where it was read; unread terms are stated as 'not reviewed'.
- No price copied from a source whose terms forbid reuse; no third-party aggregator treated as official.
- `python -m pytest tests/sources tests/approvals/test_source_boundary.py -q` passes; no test touches the network.

## Approval requirements
Source selection and any data enabled for estimating are human decisions. Imported prices become candidates (Pending Review) — see rate-update-review. A provider never approves or publishes.

## Failure handling
- 403/tunnel/robots refusal → log BLOCKED with the exact message; document the manual alternative; do not retry in a loop or use another route to bypass.
- Terms unclear → treat as not reusable; record 'terms not reviewed'.
- Unexpected data shape → store the raw response, do not coerce; report.

## Explicitly prohibited
- Measuring, inferring or generating quantities, or editing a quantity without an approved change request.
- Inventing prices, wages, productivity, wastage, suppliers, FX/tax values or benchmarks; filling a missing value with a default or a guess.
- Calling an approve/reject/publish function as, or on behalf of, a human; writing `approvals`, status or `audit_log` rows directly; weakening `app/approvals/policy.py` or a reconciliation rule.
- Editing or overwriting original files in `1. Tender Documents/` or any supplier-supplied original.
- Treating AI output, an extract, a summary or an index as authoritative over the original document.
- Bypassing authentication, CAPTCHAs, paywalls, robots.txt or rate limits; scraping Etimad or any site in bulk.
- Presenting an index (CCI) or a tender award value as a market unit price.
- Shipping a supplier list or prices you did not read from a legitimate source.

_Skills orchestrate application functions; they never bypass validation or server-side approvals. AI output remains a suggestion until an authorised human accepts it._
