# Provenance - KAPSARC-hosted GASTAT Construction Cost Index, period 2026-04

* **File:** `kapsarc_cci_2026-04.records.json` - the 39 records returned for `time_period = 2026-04` (verbatim values, same JSON shape as the API `records` response).
* **Dataset:** "Construction Cost Index Series by Sections and Groups at National Level" (id `construction-cost-index-series-by-sections-and-groups-at-national-level`), KAPSARC Data Portal (Opendatasoft Explore API v2.1).
* **Publisher (per dataset metadata):** General Authority for Statistics (GASTAT). Metadata licence field: "Public Domain"; `source-copyrights`: https://www.stats.gov.sa/en/page/45 (not independently reviewed).
* **Request:** `GET https://datasource.kapsarc.org/api/explore/v2.1/catalog/datasets/construction-cost-index-series-by-sections-and-groups-at-national-level/records?limit=100&where=time_period=date'2026-04-01'&order_by=measure,section_and_group`
* **Retrieved:** 2026-10-12, through the Firecrawl fetch tool during development (this sandbox's own HTTP client cannot reach the host - see `data/sources/ACCESS_LOG.md`). The application did NOT retrieve it itself.
* **Dataset last modified (metadata):** 2026-06-03. Expected next release (metadata): 2026-12-28.
* **Nature:** index points (base-period index), month-on-month and year-on-year percentage changes. **It is an index. It is not a unit price and must never be used as one.** Permitted use: cost-escalation reference only.
