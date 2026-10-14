# Next steps (prioritised roadmap)

> **2026-10-13 update:** a five-level capability audit was completed — see [ESTIMATING_CAPABILITY_MATRIX.md](ESTIMATING_CAPABILITY_MATRIX.md) (<!-- MATRIX_COUNTS_BEGIN -->141 records = 93 IT + 3 IU + 42 PA + 3 MI + 0 NA (IT implemented and tested, IU implemented but unverified, PA partial, MI missing, NA not applicable) - generated from `docs/capability_matrix.json`<!-- MATRIX_COUNTS_END -->) and the dependency-ordered [ESTIMATING_GAP_ROADMAP.md](ESTIMATING_GAP_ROADMAP.md) (work packages WP-00a … WP-22). The table below is the original iteration-2 roadmap and is kept; the audit adds the section *"Capability audit follow-ups"* at the end, and the audit-driven priority order replaces the old "next three" list (retained below for history).

Status words: **Done** (implemented and verified as stated), **Partial**, **Not started**, **Blocked** (needs something outside the code). "Done" never means "a class exists": each row says how it was validated.
Priority: P0 = prerequisite for real use, P1 = high value next, P2 = valuable, P3 = later.

| # | Task | Pri | Status | Why | Depends on | Acceptance criteria | Validation method | Human approval needed? | Needs credentials / internet? |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Verify and document the existing implementation | P0 | **Done** (2026-10-12/13; capability audit 2026-10-13) | Reported results had to be re-checked | — | Tests re-run, claims compared to code, gaps listed | Full suite 164→current count green; `DEVELOPMENT_AUDIT.md` lists every discrepancy found | No | No |
| 2 | Root and project-specific CLAUDE.md | P0 | **Done** | Future sessions must not rediscover the codebase | 1 | Root file covers the 15 required topics; each project gets a generated file with preserved human notes | `tests/workspaces` (content, idempotency, notes preserved), `tests/unit/test_instruction_system.py` (all referenced paths exist) | No (content facts must be human-recorded) | No |
| 3 | Task-specific skills (14) | P0 | **Done** (documents, structurally tested) | Repeatable, safe procedures | 2 | Each has purpose/when/inputs/reads/steps/outputs/validation/approval/failure/prohibited | `tests/unit/test_instruction_system.py`. **Not run end-to-end by a live Claude Code session** — treat as untested procedures until used | No | No |
| 4 | Numbered project workspaces + indexer + snapshots + migration | P0 | **Done** | Project isolation, reproducibility | 1 | Ten fixed folders created automatically, idempotent, never overwrite; document index; frozen inputs; copy-only migration | `tests/workspaces/*`, `tests/integration/test_workspace_ui.py`; live CLI run on a scratch DB | No | No |
| 5 | Validate existing Excel and estimate workflows | P0 | **Partial** | LibreOffice only; Excel itself untested | 1 | Master + templates recalculated with 0 errors/mismatches in LibreOffice (done); opened and recalculated in Microsoft Excel (not done) | `verify-workbook`; manual Excel test by a user | Yes (user opens in Excel) | Needs MS Excel |
| 6 | Public-source dataset imports (CSV/XLSX/JSON, manifests, dry-run) | P0 | **Done** (offline) | Only legitimate route to real rates today | 4 | Validated rows → candidates; manifest with hash; duplicate refusal; originals kept | `tests/sources/test_rate_pipeline.py`; live import of a synthetic list and of the real CCI sample | Yes (every candidate) | No |
| 7 | GASTAT integration where documented | P1 | **Partial** | CCI is reachable via KAPSARC's documented API; GASTAT's own site has no documented API | 6 | Index observations loaded by the application itself from the live API; GASTAT-native file layout inspected and parsed | Provider tests (mocked) pass; **live run from a normal network still to do** (`sources refresh --provider kapsarc-gastat-cci`) | No (index is reference data; escalation assumption is a human decision) | **Internet** (blocked in the build sandbox) |
| 8 | Rate discovery and review queues | P1 | **Partial** | Queue, normalisation, publication done; discovery tested on fixtures only | 6 | A real, permitted supplier page processed end-to-end into a reviewed rate | Fixture tests pass; needs an operator-chosen watchlist and a real page | Yes | **Internet**; permission check per site |
| 9 | Real Saudi rate coverage from evidence | P0 for real use | **Not started** (0 approved real rates) | Without rates nothing prices | 6, 8, 10 | A stated list of resources with approved evidence-backed rates; `coverage` reports them; no synthetic values mixed in | `python -m app.cli coverage` | Yes (every rate) | Supplier quotations / licensed or permitted price lists |
| 10 | Procurement, quotation comparison, final reconciliation on a real project | P1 | **Partial** (verified on the SYNTHETIC nine-package project) | Real quotes behave differently | 9 | A real package levelled and selected with documented reasons; reconciliation clean | End-to-end test (synthetic) exists; real-project run is a user pilot | Yes | Real quotations |
| 11 | Usability and project-level reporting | P2 | **Partial** | First-run guide, workspace page, completeness report, rate-update screens added; no browser-level tests | 4, 6 | Pilot users complete the primary journey unaided | HTTP-level tests exist; usability session needed | No | No |
| 12 | Consolidate the two dataset flows (`rate_staging` vs `rate_candidates`) and retire `integrations/base.py` stubs | P2 | Not started | Two overlapping paths confuse users | 6 | One import path; legacy data migrated or read-only | Tests migrated; no behaviour loss | No | No |
| 13 | Full replay of frozen estimates (indirects, commercial, tax) from snapshots | P2 | Not started (direct-cost replay done) | Complete reproducibility proof | 4 | `replay_estimate(version)` reproduces every total of a frozen version after library changes | Property tests across projects | No | No |
| 14 | OCR and CAD/BIM text extraction in the indexer | P3 | Not started | Scanned drawings and DWG are skipped today | 4 | Image-only PDFs text-extracted with confidence notes; DWG/IFC metadata | Fixtures; extracts remain non-authoritative | No | Optional OCR engine install |
| 15 | Live test of the optional Claude features | P3 | Not started | Only the mock provider has been exercised | — | Schema-valid outputs on real documents; injection tests; all results stay Pending Review | Opt-in integration test with a key | Yes | **API key + internet** |
| 16 | Production hardening (TLS, CSRF tokens, lockout, rotation, encrypted backups, multi-user concurrency) | P1 before any shared deployment | Not started | Current design is local single-user/small-team | — | Security review passed; load test on large BOQs | Security review, load tests | Yes | No |
| 17 | Regional / Arabic UI and RTL layout; Arabic RFQ review | P3 | Not started | English-only UI | — | Native-reviewed Arabic templates | Reviewer sign-off | Yes | No |

## Production-readiness definition (item "remaining work")
Before relying on the system for a real tender: (a) real approved rates with evidence for every priced resource (#9); (b) VAT category and FX rate verified and approved by a Commercial Approver/Procurement Reviewer; (c) all required assumptions approved; (d) workbooks opened in Microsoft Excel (#5); (e) live source refresh confirmed on a normal network (#7); (f) a pilot project reconciled end-to-end by humans (#10); (g) security hardening if more than one person or any network exposure (#16).

## Previous "next three" list (iteration 2, kept for history; superseded by the audit-driven list below)
1. **#9 + #6/#8:** load a first set of evidence-backed rates (supplier quotations through the RFQ/quotation workflow, permitted price lists through `rates import`) and approve them — nothing prices without this.
2. **#7:** run `python -m app.cli sources refresh --provider kapsarc-gastat-cci` (and `--dry-run` first) on a normal network to confirm the live KAPSARC/GASTAT path; record the outcome in `data/sources/ACCESS_LOG.md`.
3. **#5:** open the generated master workbook and the Rate Dataset template in Microsoft Excel, confirm recalculation, and record the result (then #12 consolidation).

## Capability audit follow-ups (2026-10-13)
Result of the audit (details and evidence in the matrix): **Levels 5–4 conditionally supported, Levels 3–1 not supported; 0 approved real rates; no industrial/EPC modules; strongest area is governance.** Defects found and already fixed (with regression tests): O(n²) estimate computation, missing `pypdf` dependency (PDFs were never text-extracted on a default install), schedule→duration path untested/unreachable and not protected for archived projects, several untested claims now tested.

### Status update after iteration 4 (2026-10-13)
Items 1-3 of the list below that were **code** are done: WP-01 (units), WP-02 (WBS/CBS) and most of WP-03..10, 15, 16, 19-22 (see the status table in [ESTIMATING_GAP_ROADMAP.md](ESTIMATING_GAP_ROADMAP.md) §0a). What remains is **mostly data and verification that only you can provide**; the new next three:
1. **Load real data** for a pilot BOQ: approved rates (`rates import`, RFQs) and your own factors as governed parameters (`Inputs & parameters`): productivity, take-off factors, hire terms, calendar, escalation, payment terms. Until then every estimate is Preliminary and every analysis says what it lacks.
2. **Verify where the sandbox could not:** run `python -m app.cli sources refresh --dry-run` then live on a normal network; open the master workbook and templates in Microsoft Excel; record both in `data/sources/ACCESS_LOG.md` / the audit.
3. **Pilot one real project end to end** (BOQ -> templates/assemblies -> analyses -> Basis of Estimate -> reconciliation -> approvals), then decide which Partial records (discipline templates, DSC-01..11) need real acceptance tests; load any owner's estimating requirements as a client profile **only from documents you are authorised to supply**.

### Next three highest-priority tasks (as set at the 2026-10-13 audit; superseded by the update above)
1. **WP-00a — load evidence-backed rates and productivity/consumption factors** for a named pilot BOQ (through RFQs, quotations, permitted price lists, company actuals). Nothing real prices without this; it is data and human approval, not code.
2. **WP-01 + WP-02 — units/dimensions management and the WBS/CBS cross-walk with roll-ups.** These are the foundational code blockers for every industrial and large-project module (piping and instrument BOQs cannot even be imported today; no WBS exists).
3. **WP-11 + WP-00b — verification that needs a normal environment:** run `sources refresh` on an unrestricted network and open the workbooks in Microsoft Excel; record both outcomes.

### Mapping of the original items to the audit work packages
| Original item | Audit work package(s) |
|---|---|
| #5 Excel validation | WP-00b |
| #7 GASTAT integration | WP-11 (live check), WP-09 (use of index data for escalation) |
| #8 Rate discovery & review queues | WP-11 |
| #9 Real rate coverage | WP-00a |
| #10 Procurement on a real project | WP-16, WP-17 |
| #11 Usability and reporting | WP-02 (roll-ups), WP-04 (man-hour reports), WP-22 |
| #12 Consolidate dataset flows | unchanged (not an estimating capability) |
| #13 Full replay | WP-15 (GOV-05) |
| #14 OCR / CAD extraction | WP-18 (SCO-10) |
| #15 Live Claude test | WP-18 (SCO-11) |
| #16 Production hardening | WP-22 (GOV-12) |
| #17 Arabic UI / RTL | not scheduled; SAU-01 limitation |

### Constraints that do not change
No invented prices, no automatic approval, no silent overwrite of approved rates, no automated quantity takeoff, no autonomous tender submission, no compliance claim for any client without that client's controlled documents loaded and traced.

## After the end-to-end closure (2026-10-14): the next three actions
1. **Run one authorised real package through the registers** with registered *human* approvers in a production environment: the project's confirmed calendar, company-sourced productivity norms and workforce profiles, the customer's actual requirements, real rates/quotations. Compare the programme, the cost chain and the document pack with the company's own estimate; record every difference. (Nothing about estimating accuracy is claimed until this is done.)
2. **Identity and audit hardening** before any wider deployment (`docs/ASSUMPTIONS_GOVERNANCE_AND_SECURITY_AUDIT.md` section 6): anchor the audit chain outside the database, separate administrator duties, MFA/SSO, encrypted storage; refuse to *record* an approval from an unregistered or mismatched actor in a production environment.
3. **Acquire and record the sources** the register lists as unverified (Saudi Building Code edition, current Labor Law and Executive Regulations, in-force procurement law, AACE recommended practices) and have competent persons author the quality, ITP, method-statement and HSE content that the registers currently hold only as structure (WP-23).
