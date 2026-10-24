# Source Access Log - KSA public data sources

Date of research: 2026-10-12. Register: `source_register.csv` (27 sources, SRC-001 to SRC-027).

## Method and constraints

- Shell `curl` was not used against any blocked site. Direct `WebFetch` of zatca.gov.sa failed immediately (`getaddrinfo ENOTFOUND zatca.gov.sa`), so all access went through Firecrawl (`firecrawl_search`, `firecrawl_scrape`).
- No authentication, login, CAPTCHA or rate limit was bypassed. One Firecrawl API rate-limit error (Etimad scrape) was simply retried later.
- Firecrawl often returned **cached copies** (`cacheState: hit`, `cachedAt` 2026-10-11 or 2026-10-12). `date_accessed` in the register is the date the tool returned the content, not necessarily the date the site last rendered it.
- "Accessed" means page or PDF text was returned and read. "Partially accessed" means only search-result excerpts or an empty shell were seen. No terms-of-use pages were read unless stated, so licence cells say "Terms not reviewed" except where a licence/disclaimer was actually seen.
- No prices or index values were copied into the register.

## Verified facts (exact quotes)

| Fact | Quote and location | Source |
|---|---|---|
| VAT standard rate is 15% | ZATCA VAT page, section "Goods and services subject to VAT", table row: `Food & Beverages \| 15%` (the page is a tabbed widget and only the first tab was captured). Also, ZATCA Guideline on Amendments to the Implementing Regulation (BoD Res. 01-06-24 of 19 Nov 2024), extracted answer: "VAT-registered individuals must charge VAT at a standard rate of 15%, where applicable." | SRC-012, SRC-015 |
| VAT was originally 5% | ZATCA "About Vat" page: "imposed VAT on January 1, 2018 ... VAT was introduced at a standard rate of 5%." | SRC-013 |
| Increase effective 1 July 2020 | ZATCA Implementing Regulations (English PDF, page 51, para (10), footnote 51 citing BoD Res. 2-3-20 dated 09/06/2020): "the modified standard Tax rate shall be applied ... if an Invoice is issued or Consideration for Goods or service is paid before 1/7/2020 and the Supply was made after this date, the Tax will be determined based on the date of Supply". Further: "the modified Tax Rate shall be applied to the partly executed Supplies after 1 July 2020". | SRC-014 |
| SAR/USD peg 3.75 | SAMA news "SAMA Affirms Commitment to Exchange Rate Policy", 04 May 2020: "SAMA remains committed to maintaining the exchange rate at the official rate of 3.75 riyals to the dollar as an anchor of monetary and financial stability." | SRC-017 |
| Working hours | HRSD article 312, Labor Law Art. 98: "may not be actually employed for more than (8) hours per day ... or more than (48) hours per week ... Ramadan ... (6) hours per day, or (36) hours per week". Art. 107: overtime "equivalent to the hourly wage plus 50% of his basic wage". Article authored 15 Nov 2019. | SRC-018 |
| Etimad scale | Visitor listing counters: active 1840, awarded 467439, bids submitted 2055253 (cached 2026-10-11). | SRC-006 |

**VAT caveat:** the 15% figure and the 1 July 2020 date were verified from official ZATCA pages, but on different pages. No single ZATCA sentence I read states "15% effective 1 July 2020". The English Implementing Regulations PDF I read does not print "15%". Several secondary sites (search excerpts only: noblecoreksa.com, cleartax.com, synergystrat.com, zoho.com) state "15% from 1 July 2020", which is consistent but is not primary evidence. The Nov 2024 guideline sentence was obtained via Firecrawl query extraction. Confirm against the VAT Law (Article 2) text before relying on it in a contract.

## Attempt log

| # | Tool | URL / query | Outcome |
|---|---|---|---|
| 1 | WebFetch | https://zatca.gov.sa/en/RulesRegulations/Taxes/Pages/VAT.aspx (URL guessed, not from brief) | FAILED - `getaddrinfo ENOTFOUND zatca.gov.sa`. No data. |
| 2 | firecrawl_search | "ZATCA VAT standard rate 15% effective 1 July 2020 Saudi Arabia" | OK - 6 results, secondary sites state 15% from 1 July 2020 (excerpts only). |
| 3 | firecrawl_search | "GASTAT construction cost index building materials price index Saudi Arabia" | OK - found stats.gov.sa CCI methodology page, KAPSARC mirror, news articles (Argaam, Arab News) citing CCI +2.3% YoY July 2026 (news only, not recorded). |
| 4 | firecrawl_search | "Saudi Central Bank riyal US dollar peg 3.75 official" | OK - found sama.gov.sa news-557, IMF DSBB, Wikipedia. |
| 5 | firecrawl_scrape | sama.gov.sa/en-US/MediaCenter/News/Pages/news-557.aspx | OK (cached) - peg quote verified. |
| 6 | firecrawl_scrape | stats.gov.sa CCI methodology page | FAILED - first attempt tool timeout (60s); retry returned HTTP 502 nginx error page. Not read. |
| 7 | firecrawl_scrape | zatca.gov.sa Implementing Regulations PDF (81 pp) | OK - 168k chars saved, searched locally. Found 1/7/2020 modified-rate provisions; does not print "15%". |
| 8 | firecrawl_search | "value added tax standard rate 15% ZATCA", includeDomains zatca.gov.sa | OK - 8 ZATCA URLs (VAT page, guidelines). |
| 9 | firecrawl_search | "Saudi Building Code SBC access public download" | OK - sbc.gov.sa listed plus third-party PDF copies (not legitimate sources). |
| 10 | firecrawl_search | "data.gov.sa open data construction cost index dataset" | OK - KAPSARC CCI dataset, my.gov.sa open-data page. |
| 11 | firecrawl_search | "Etimad tenders platform public tenders listing" | OK - tenders.etimad.sa visitor page appears in results. |
| 12 | firecrawl_scrape | zatca.gov.sa VAT page (RulesRegulations/VAT/Pages/default.aspx) | OK (cached) - rate table row "Food & Beverages 15%"; last update 24 Sep 2026. |
| 13 | firecrawl_scrape | ZATCA Amendments guideline PDF (query mode) | OK - answer "standard rate of 15%" (model-extracted). |
| 14 | firecrawl_scrape | https://www.sbc.gov.sa/En/Pages/default.aspx | FAILED - `ERR_TUNNEL_CONNECTION_FAILED`. Marked Blocked (proxy). |
| 15 | firecrawl_scrape | https://my.gov.sa/en/content/open-data | FAILED - all scraping engines failed. |
| 16 | firecrawl_scrape | zatca.gov.sa About-Vat page | OK (cached) - states 5% at introduction (2018); no 15%. |
| 17 | firecrawl_scrape | stats.gov.sa CCI page (retry, 120s) | FAILED - HTTP 502 error page. |
| 18 | firecrawl_search | Saudi labour working hours | OK - hrsd.gov.sa article 312 found. |
| 19 | firecrawl_search | SEC tariffs | OK - se.com.sa pages found plus third-party tariff figures (not verified, not recorded). |
| 20 | firecrawl_scrape | hrsd.gov.sa/en/knowledge-centre/articles/312 | OK - Arts. 98-100, 107 quoted. |
| 21 | firecrawl_scrape | se.com.sa ConsumptionTariffs page | PARTIAL - returned only a skip-link shell (JS-rendered); no tariff table. |
| 22 | firecrawl_search | Saudi Aramco engineering standards SAES public | OK - only third-party copies (Scribd, Academia, Facebook) and one aramco.com supplier PDF (ertqa.pdf, not opened). |
| 23 | firecrawl_search | SASO standards catalogue | OK - saso.gov.sa homepage excerpt ("Purchasing Standards" e-service). |
| 24 | firecrawl_scrape | se.com.sa CorporateNews32 | PARTIAL - empty shell, no body. |
| 25 | firecrawl_scrape | KAPSARC CCI dataset page | OK - metadata, xlsx attachment link (not downloaded), last modified 3 Jun 2026. |
| 26 | firecrawl_scrape | tenders.etimad.sa | First attempt: Firecrawl API rate-limit error (retried later, not circumvented). |
| 27 | firecrawl_search | Muqawil / SCA | OK - muqawil.org pages in results (excerpts only). |
| 28 | firecrawl_search | MOMAH building permits open data | OK - momah.gov.sa e-services, balady.gov.sa open-data page. |
| 29 | firecrawl_search | Etimad awarded tenders | OK - MOH, my.gov.sa descriptions; third-party aggregators (tendersalerts, parse.bot). |
| 30 | firecrawl_scrape | tenders.etimad.sa (retry) | OK (cached 2026-10-11) - Arabic visitor listing with counters and filter incl. "تم اعلان الترسية". |
| 31 | firecrawl_scrape | balady.gov.sa/en/open-data | OK (cached) - reuse conditions and CC licence statement read; 42-dataset table. |
| 32 | firecrawl_search | open.data.gov.sa licence / datasets | OK - Wikipedia and portal pages in results (excerpts). |
| 33 | firecrawl_search | Ministry of Investment MISA | OK - MISA FDI report PDF excerpt only. |
| 34 | firecrawl_search | online building materials store prices | OK - Madar, msamer blog, CEIC, Scribd, and an SCA PDF in results (excerpts). |
| 35 | firecrawl_scrape | https://open.data.gov.sa/en/pages/policies/license | FAILED - `ERR_TUNNEL_CONNECTION_FAILED`. Licence text NOT read. |
| 36 | firecrawl_scrape | muqawil.org SCA Q3 2020 PDF | OK - read (34 pp). Disclaimer prohibits reproduction without written SCA permission; nothing copied to the register. |
| 37 | firecrawl_scrape | KAPSARC catalog API: .../api/explore/v2.1/catalog/datasets/construction-cost-index-series-by-sections-and-groups-at-national-level | OK - dataset metadata JSON: fields (time_period, measure, section_and_group, index), 1,391 records, license "Public Domain", publisher GASTAT, update frequency monthly, attachments (xlsx). |
| 38 | firecrawl_search | "GASTAT construction cost index dataset download xlsx stats.gov.sa building materials price" | OK - excerpts only: GASTAT methodology page, SPA/GASTAT news releases (CCI bulletins), KAPSARC dataset. No documented download API for stats.gov.sa found. |
| 39 | firecrawl_scrape | KAPSARC .../records?limit=8&order_by=time_period desc | OK - confirmed record shape; latest period 2026-04. |
| 40 | firecrawl_scrape | KAPSARC .../records?...where=time_period='2026-04' | FAILED - HTTP 400 IncompatibleTypesInComparisonFilter (time_period is a date field; query was wrong, not blocked). Not repeated in the same form. |
| 41 | firecrawl_scrape | KAPSARC .../records?limit=100&where=time_period=date'2026-04-01'&order_by=... | OK - 39 records; saved verbatim to data/public_data/gastat_cci/kapsarc_cci_2026-04.records.json. |
| 42 | curl (HEAD, one attempt each) | https://www.stats.gov.sa, https://datasaudi.sa, https://opendata.stats.gov.sa, https://datasource.kapsarc.org, https://data.gov.sa, https://tenders.etimad.sa | ALL FAILED from the sandbox (curl exit/HTTP code 000 via the agent proxy). Recorded as blocked from the environment; not retried. |
| 43 | application HTTP client (`python -m app.cli sources refresh --provider kapsarc-gastat-cci`), twice | datasource.kapsarc.org/robots.txt then the records endpoint | BLOCKED - `URLError: Tunnel connection failed: 403 Forbidden` reading robots.txt; no data request made (conservative). Logged in `source_access_log`. First attempt (before the message was clarified) showed the same refusal. |
| 44 | firecrawl_search / firecrawl_scrape (5 research agents + manual spot checks), ~190 calls in total, rate-limited by the plan, no retry loops | 32 public retail / supplier / price-guide sites (see SRC-028 onward) | OK for public pages; swsg.co, youmats.com blocked (403/CAPTCHA) and left; gccpricing.com read but judged unreliable (wrong currency/units) and excluded; CEIC (paywalled) and the SCA report (written permission needed) excluded; 6 of 6 sampled prices re-fetched and matched the live page (2026-10-24). |

## Reuse assessment (short)

- **Genuinely accessible and usable as references:** ZATCA VAT rules, SAMA peg, HRSD working-hours rules (facts and rules only), MOMAH/Balady open datasets (attribution required; counts only, no rates), GASTAT CCI via KAPSARC (escalation indices only; licence text not seen).
- **Accessible but not reusable without permission:** the SCA building-materials price report (explicit written-permission requirement; also 2020-dated).
- **Not obtained:** current GASTAT CCI methodology/data file, SBC, SASO standards (appear to be sold), Aramco SAES (only unofficial copies found), SEC official tariff table, Ministry of Energy, CPI, open.data.gov.sa licence text, any construction unit-rate dataset.
- **Gap:** no free, legitimately reusable source of SAR unit rates (labour, plant, materials, BoQ rates) was found. Etimad tender and award data are public to view but need a terms review and a permitted method before any bulk use. Unit rates will need supplier quotations or licensed data.
