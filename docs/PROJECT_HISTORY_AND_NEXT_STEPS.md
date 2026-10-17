# Project history and next steps

Written 2026-10-14 so that anyone (including a future session) can see **what was done, why, what the evidence is, and where we left off**. Companion diagrams: [SYSTEM_MAP_BUILT_VS_MISSING.md](SYSTEM_MAP_BUILT_VS_MISSING.md). Branch: `claude/wizardly-einstein-w4ykwd` (never merged to `main`, no PR opened).

## 1. What this is
A local-first, Excel-first **estimating, tendering and procurement-support suite for Saudi construction contractors**. People measure quantities; the system prices deterministically from approved rates, tracks every assumption, drafts queries, builds the 45-document tender pack, and refuses to call anything "submission ready" without registered human approvals. AI only proposes. See `CLAUDE.md` for the non-negotiable rules.

## 2. Timeline

| Phase | What was done | Evidence |
|---|---|---|
| Foundation (iterations 1–3) | Decimal engines (direct cost, indirects, commercial, CPM), approvals + hash-chained audit, resources/rates/assumptions/assemblies, BOQ import, procurement (needs → RFQ → quotes → levelling), reconciliation, 27-sheet Excel workbook, web UI + REST + CLI, project workspaces + indexer, public-source rate updates, optional review-only AI | README "What is in the box" |
| Iteration 4 | Governed parameters (every company number is a versioned, sourced, approved row), WBS/CBS, programme + loading + man-hours, take-off templates, landed cost/FX, risk/Monte Carlo/escalation, cash flow, bids/long-lead, variations/EVM, benchmarks, Basis of Estimate, client profiles, method alternatives, full replay, security hardening | capability matrix |
| Pilot validation + synthetic pilot | Re-usable SYNTHETIC end-to-end run (16 stages) that exposed four real problems | `scripts/run_synthetic_pilot.py`, `docs/SYNTHETIC_PILOT_RUN.md` |
| Four pilot findings closed | Cash-flow/escalation allocation + blocking, indirect eligibility base, day-priced plant, actor-type / synthetic isolation | commit `50e17f2`, 385 tests |
| **"Close the loop" mission** | Workforce/productivity/calendar engine + crew scenarios; unified assumptions register (17 categories, immutability triggers, four-eyes default); standards register (12 sources); tender registers + draft-only query detectors; 45-document tender pack and 17-document hypothetical handover pack (DOCX/XLSX/PDF, deterministic, manifest, validator); readiness closure gate; 27-stage synthetic scenario with an independent oracle; audit + security review | commits `e8c992a`, `ec75844`; 458 tests; `demo_output/synthetic_closure/` |
| **Real-document practice test** | One third-party sample BOQ PDF was the only input (no drawings/specs/contract). Quantities read independently, imported, 36 draft queries, 10 takeoff actions, demonstration pack, negative tests, 9 defects + 3 observations recorded | commit `e2f88d4`; `practice_test/PRACTICE_TEST_RESULTS.md` |
| Defects D-1, D-3, D-4, D-7 fixed | Incomplete-PDF-text flag, BOQ-content detectors, D36 lists unpriced lines, defaulted region/currency flagged (migration 0016) | commit `5b9c4d0`; 464 tests |
| Defects D-9, O-2, O-3 fixed | Discipline completeness matrix; unapproved assumptions in use can never be waived (adopted-unused need a recorded exception); estimate state and caveats reflect synthetic / unchecked data | this commit; 479 tests passed |
| Defects D-2, D-5, D-6, D-8 fixed + priced run | No OCR by design: independent transcription imported with provenance and a second-person check; completeness no longer says OK with nothing priced; demo ≠ synthetic labelling; unknown totals are `None` not `0`; **priced run PRJ-9203** (real quantities × labelled SYNTHETIC placeholder rates) independently re-computed 48/48 lines | this commit; 479 passed (3 min 33 s) |

## 3. Key decisions (so they are not re-litigated)
* **No invented data.** No rates, productivity, calendars, suppliers or customer answers ship. Synthetic values are labelled and can never become "verified".
* **Quantities are human-measured.** No automatic takeoff, **no OCR / PDF-drawing reading** in the product (owner decision, 2026-10-14). A PDF BOQ is transcribed independently, imported with provenance, and checked by a second person.
* **Four-eyes by default**; an Administrator is not exempt for material records. Approved records are immutable (service + DB trigger — a guard, not tamper-proofing).
* **Demo ≠ synthetic.** A demonstration/practice project on real data is labelled DEMONSTRATION; only synthetic content is labelled SYNTHETIC.
* **Defaults are flagged.** Region/currency applied by default block production readiness until a person confirms them.
* **Unknown is not zero.** Unpriced/undefined totals are `None`.
* **India sample ≠ KSA product.** The practice document is Indian (INR, IS 1200); it was used only to test the pipeline. Placeholder rates in the priced run are labelled and have no source.

## 4. Results to date (all re-runnable)
* Automated suite: 479 passed (3 min 33 s) (`python -m pytest -o addopts="" -q`, ≈5 min).
* Synthetic scenario `python scripts/run_closure_scenario.py <fresh dir> --out <dir>`: **27/27 stages**, independent oracle agrees; 0 exports marked submission-ready; all actors test principals.
* Crew scenarios on synthetic norms (head-count / working days): SME 15 → 400, Mid 24 → 212, Large 48 → 170, Enterprise 91 → 170 (the single crane and dependencies bind). Comparisons only, never benchmarks.
* Practice test (`python scripts/run_real_document_practice_test.py <fresh dir>`): 48 BOQ lines imported (0 rejected); 0/48 verified against drawings (none supplied); 40 draft queries (25 system, 15 operator); 24/45 documents BLOCKED by missing inputs; negative tests held (registered humans in production could not produce a submission-ready export). Priced run: direct cost 1,274,224.00 on placeholder rates, equal to the independent recomputation for all 48 lines.
* Standards register: 2 sources verified from primary text (VAT, midday work ban), 4 partial, 6 not verified.

## 5. Defect ledger (practice test)
| # | Defect | Status |
|---|---|---|
| D-1 | PDF "Extracted" although quantities missing | fixed (`Extracted - incomplete`) |
| D-2 | No PDF import path | resolved by design (no OCR); provenance + second-person check |
| D-3 | Detectors ignored BOQ content | fixed in part (remarks, markers, near-duplicates); formula/total checks still manual |
| D-4 | D36 hid unpriced lines | fixed |
| D-5 | Completeness OK with 0/48 priced | fixed |
| D-6 | Demo conflated with synthetic | fixed |
| D-7 | Silent KSA/SAR defaults | fixed (flag + readiness) |
| D-8 | Zero shown for unknown totals | fixed |
| D-9 | No discipline × document completeness matrix in the app | fixed (report `discipline_completeness`, migration 0017, in D33 and the completeness report) |
| O-1 | Human can approve a document built on an Incomplete estimate (status stays Draft) | open, low |
| O-2 | Unapproved assumptions only a waivable *Medium* finding | fixed: in use → **Critical, cannot be waived**; adopted but unused → **High**, needs a Commercial Approver's recorded exception |
| O-3 | Estimate state says Complete despite unchecked transcription / placeholder rates | fixed: state reads "... - SYNTHETIC DATA (not for reliance)" and a caveats list (unchecked transcription, defaulted basis, synthetic/provisional, unapproved assumptions) is shown in completeness, BOE banner and the API |

## 6. What still needs to be done

**A. Needs people and real data (nothing in code will fix these)**
1. Register real `human` users (estimator, procurement, commercial approver) and run in a production environment.
2. Enter and approve real, sourced inputs: rates (or quotations), productivity norms, work calendar (holidays, Ramadan hours, shutdowns), workforce profiles, payment/retention/bond terms, commercial policy, tax approval.
3. Obtain and import the standards that were not read: Saudi Building Code, procurement law, productivity references (the register lists them as "requires human acquisition").
4. Provide a complete tender package (drawings with revisions, specifications, ITT/contract, BOQ as XLSX/CSV) for a real pilot — the practice test had one marketing PDF.
5. Competent persons write the real quality / ITP / HSE / compliance content (only skeletons exist).

**B. Code backlog (ordered)**
1. Remaining defect: O-1 (low). Review whether the O-2 policy (adopted-unused assumptions need an exception) is too heavy in practice — every real project will carry ~80 seeded mandatory assumptions until a person approves or excepts them.
2. Detector for "printed total / formula vs lines" where a BOQ contains subtotal rows.
3. A document-approval button on the pack page and UI forms for governed parameters (calendar, payment terms) — norms, profiles and activities can now be created, submitted and approved in the web UI.
4. Put cash flow in the frozen snapshot; read-only reviewer view of a frozen estimate.
5. Security hardening (docs/SECURITY.md): MFA/SSO, off-box audit anchor, encryption at rest, separated admin duties, rate limiting beyond sign-in lockout, an independent penetration test.
6. KSA specifics to enter only from primary sources (never defaults): statutory labour rules, holiday calendar, VAT treatment per package.

**C. Acceptance for the first real-project pilot**: items A1–A2 and A4, B1, plus a dry run of the practice test on the real package with a second person checking every transcribed quantity.

## 7. How to run it and see what we built
**Quickest:** `scripts/demo_web.sh` builds the SYNTHETIC end-to-end tender (≈1 min, first run only) and serves the web app on http://127.0.0.1:8000 — sign in as `test-commercial` / `synthetic-only-pw`, then **Projects → PRJ-9101 → Control tower**. `scripts/demo_web.sh practice` serves the real-document practice test (needs the PDF in `practice_test/input/`); `scripts/demo_web.sh empty` gives a fresh database with the small demo project.
The web app has a sidebar menu (Overview · Libraries · Governance · System · Help) and, per project, two tab rows: **Tender** (Control tower, Tender desk, Queries & RFIs, Registers & actions, Workforce & programme, Tender pack, Readiness) and **Estimate** (the 16 estimating tabs). Help → "What's built / missing" renders the diagrams.
Manual route:
```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
python -m app.cli init --demo-users      # prints the admin password once; creates estimator/procurement/commercial (demo-only password)
python -m app.cli demo                    # a clearly SYNTHETIC demonstration project
python -m app.cli run                     # http://127.0.0.1:8000
```
Verified in a scratch environment on this branch: `init` and `demo` complete, the server starts and `/login` returns 200. In the UI: open the demo project → BOQ → Mapping → Estimate → Reconciliation → Reports; Workspace tab shows the document index and the new Region/Currency fields.
To watch the whole tender loop without clicking: `python scripts/run_closure_scenario.py /tmp/scn --out /tmp/scn_out` (≈1 min) then open `/tmp/scn_out/PRJ-9101_tender_pack_r2/` (DOCX/PDF/XLSX) and `acceptance_results.json`.
To see the real-document test: `python scripts/run_real_document_practice_test.py /tmp/pt` (needs the PDF in `practice_test/input/`, git-ignored) → `practice_test/real_document/` and `practice_test/PRACTICE_TEST_RESULTS.md`.
Use scratch locations (`KSA_DB_PATH`, `KSA_WORKSPACES_DIR`) if you do not want the demo in your working database.

## 8. Keeping the project lean
* **Do not add**: OCR / PDF-reading, bundled rate libraries, AI features that approve, a second copy of any number. Every new capability must be data-driven (governed parameter / register) or a pure engine with a test.
* **Generated output is not source.** `practice_test/real_document/generated/` and `priced_run/` are git-ignored and rebuilt by the script. `demo_output/synthetic_closure/` (≈4 MB, committed as the reference run) can be dropped from git and regenerated with the scenario script if size matters — say so and it will be removed.
* **Source size now** (approx.): `app/` 4.5 MB, `tests/` 4.5 MB (includes caches), `data/` 1 MB, `docs/` 0.9 MB, tracked `practice_test/` 0.1 MB.
* **Docs**: 40+ files; prefer updating an existing doc over a new one. This file and the system map are the entry points; the rest are reference.
* **Rule of thumb**: if a piece cannot be exercised by a test or a scenario run, do not keep it.

## 9. Where we left off
Last full-suite result: 479 passed (3 min 33 s). Work is committed on the feature branch; O-1 is the only open defect; the next real milestone is a controlled pilot on a complete real tender package with registered human approvers (section 6C).
