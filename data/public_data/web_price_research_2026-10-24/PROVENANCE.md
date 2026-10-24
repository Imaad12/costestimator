# Web price research, 24 Oct 2026

**What this is:** public retail / supplier / price-guide prices for Saudi construction items, collected on 2026-10-24 by research agents using Firecrawl search and scrape, one JSON file per trade (`A_steel`, `B_hvac`, `C_fire`, `D_elec_plumb`, `E_civil`) plus `G_gastat_anchor` (the GASTAT monthly national averages for Aug 2026 as republished by saudimaterialprices.com, read from a search excerpt).
Every row carries the exact page URL, the page date (or "not stated"), the unit as the page states it and a **verbatim quote** containing the price.

**What it is not:** not quotations, not approved rates, not verified. Prices are indicative web prices; VAT and delivery basis are mostly not stated. Terms of use of the sites were **not reviewed**. The rows are kept here as evidence for the human check; they are not a second source of truth (the database holds candidates and rates).

**How it was used:** `python scripts/consolidate_web_prices.py DB OUT.xlsx` audits each row (the price must appear in its own quote; floors such as "as low as", pre-2025 data, excluded sources and unit mismatches are set aside), matches only rows whose product and unit match a catalogue resource, cross-checks sources per item, and writes the price-list workbook. A range becomes its midpoint with the range written into the evidence. Rows for items not in the catalogue go on the sheet "Unmatched - to map". The workbook is uploaded on the Rates workbook page and every row becomes a candidate in **Pending Review**.

**Excluded on purpose:** gccpricing.com (wrong currency and unit labels seen), CEIC (paywalled), the SCA price report (written permission required), QS Mind (anonymous, self-described approximate), rows older than 2025, "from / as low as" prices, SAR 0.00 demo prices.
**Spot check:** six prices were re-fetched by hand on 2026-10-24 and matched the live pages. One shop page (Almanara) carries 2022 metadata, so shop prices without a stated date may be stale.
