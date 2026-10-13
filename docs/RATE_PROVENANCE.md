# Rate provenance

## Rate types (every rate has exactly one)
| Type | Meaning | Usable as a unit price? |
|---|---|---|
| Verified Supplier Quote | from a verified, approved quotation (linked line, supplier, date, validity) | yes, once approved |
| Published Market Price | public catalogue/price list with a source reference | yes, once approved |
| Official Index or Benchmark | e.g. a construction cost index | **never** (reference only) |
| Historical Actual | actual project cost with a ledger/source reference | yes, once approved |
| Approved Internal Benchmark | company benchmark with evidence | yes, once approved |
| Estimator-Entered Allowance | an allowance; estimators can only approve it **provisionally for one project** | yes (provisional) |
| Synthetic Demonstration Rate | invented for demo/testing; flagged everywhere; blocks submission in non-demo projects | demo only |
| Missing Rate | placeholder meaning "no verified price"; cannot be approved | no |

## Record contents (`resource_rates`)
resource, version, rate type, price (NULL for Missing), currency, **unit** (convertible to the resource unit), region, supplier, originating quotation line, source id, evidence text, price date, valid-until,
tax basis, delivery basis, installation/freight inclusion, confidence, status, project scope (for provisional), synthetic flag, labour/plant build-up components, notes, creator, approver, timestamps, `superseded_by`.
Resource master data (`resources`) carries the ID, type, trade/sub-trade, category, description (+Arabic field, aliases), specification, brand/equivalence requirements, unit, currency, geographic applicability, installation & freight/unloading inclusion, tax and delivery basis, notes.

## Rules
* **Versioned, immutable once approved.** New price = new version; approving it supersedes the previous approved rate for the same resource/region (history retained and linked).
* **Approval requirements:** a real price type, a valid `price_date`, `valid_until >= price_date` and **not already lapsed**, evidence/source for non-allowance types, a linked quotation line or evidence for *Verified Supplier Quote*.
* **Validity:** a rate whose `valid_until` passes is unusable (status Expired via `expire_stale_rates`, or detected at calculation time) and reappears as a procurement need.
* **Age and confidence:** rates older than `rates.age_warning_days` or with Low/Unverified confidence stay usable but raise a `RATE_WARNING` and a procurement "re-confirm" line.
* **Region:** applicability is by region code (`KSA-ALL`, regional codes) - there is **no regional multiplier** anywhere.
* **Currency:** original currency preserved; converted only with an approved, date-valid FX rate.
* **Synthetic:** `is_synthetic` propagates to cost lines, items, schedule lines, workbooks, documents (banner) and reconciliation (`SYNTHETIC_IN_REAL_PROJECT` is Critical for non-demo projects).

## Tracing a number
Every cost line records: BOQ item -> assembly (+version) -> assembly line -> resource -> **rate id** (type, status, currency, FX used) -> assumptions applied -> the calculation `basis` string.
Change history: `audit_log` (entity `rate`/`resource`), approval records, and `superseded_by` links.

## Candidate stage (public sources, datasets, web pages) — see [RATE_UPDATE_WORKFLOW.md](RATE_UPDATE_WORKFLOW.md)
Before a price becomes a `resource_rates` version it exists as a `rate_candidates` row with: exact source URL / uploaded-file reference, source type/name/id, retrieval timestamp, source publication and effective dates, geography,
**original price/currency/unit (immutable)**, separate normalised price + method + steps, tax/delivery/installation basis, price kind, extraction method, evidence snippet, flags, queue/status, reviewer and comments, manifest id.
The published rate's `evidence` text repeats the candidate ref, URL, retrieval date, original figures, basis, normalisation method and reviewer comment, so a rate can be traced back to the exact page or file.
Original files and manifests are kept in `var/imports/`. A published rate is VAT-exclusive; its `tax_basis` is `Excluded`. Regional multipliers and index-adjusted unit prices do not exist anywhere.
Official indices live in `index_observations` and are never rates.
