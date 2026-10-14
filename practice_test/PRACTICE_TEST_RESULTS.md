# PRACTICE TEST RESULTS — real-document practice test

**PRACTICE EXERCISE — NOT A TENDER, NOT A SUBMISSION, NOT AN ESTIMATE FOR RELIANCE.** Run 2026-10-14 on branch `claude/wizardly-einstein-w4ykwd` against a scratch database. `main` and `projects/PRJ-0001-mini-synthetic` were not touched; nothing was sent, issued or approved by a person.
Re-run: `python scripts/run_real_document_practice_test.py <fresh scratch dir>` → `practice_test/real_document/results.json` (every figure below comes from that file or from the commands quoted).
How to read verdicts: **PASS** means the application behaved correctly *for the evidence available*, which is often "it refused / reported a gap". It does **not** mean an estimate, programme or tender document is usable.

## 0. The most important fact: the input package is one file

The task refers to "the actual documents in this test project's input folder". **No input folder existed** and no other tender material exists on the machine. The only input is the single uploaded file below; I created `practice_test/input/` to hold it (the PDF itself is git-ignored — third-party material; its SHA-256 is recorded).
There are **no drawings, no specifications, no contract/ITT, no addenda, no spreadsheet and no BOQ file**. The "document" is a marketing web page printed to PDF. Consequences: steps D (verify quantities against drawings) and E (compare BOQ with architectural/structural/civil/MEP documents) could only be done as *gap findings*, never as verification, and a large part of the suite (programme, procurement, compliance, commercial) had nothing to work on. Those features are exercised only by the separate synthetic run (§12).

## 1. Input files processed / not processed

| File | Format | Bytes | Pages | SHA-256 | Revision / date visible | Discipline | Status |
|---|---|---:|---:|---|---|---|---|
| `1ddcacd6-Sample_BOQ_for_a_Residential_Building___SiteSetu.pdf` | PDF (Chrome "Skia/PDF" print of a web page) | 3,131,031 | 7 | `9e55f977217142626c38bb16cdb3db6bcda77c430fc691ecc5e0fdf8db066ab0` | "Published 1 October 2026" (p.1); "Quantities as delivered on 6 September 2026" (p.5); **no revision identifier** | Civil/earthwork, structural RCC + formwork, masonry, openings, railings, roof. No MEP, finishes, external works | Marketing page; **not** a contract document or an issued-for-tender BOQ; rates blank; quantity column has **no text layer** |

* **Processed:** the one PDF — copied unchanged into the workspace (checksum identical before/after in the input folder and in the workspace copy: stage `A2_originals_unchanged` PASS), indexed, registered, and its BOQ table transcribed (§3).
* **Not processed (nothing to process):** drawings, specifications, contract/ITT, addenda, geotechnical/survey, MEP documents — none supplied.
* **Not used from the PDF:** pages 1, 2 (images), 6, 7 other than their statements of scope/exclusions; the two images on p.2 (a ground-floor-plan thumbnail and a 3D render) are illustrations and were not read for any dimension or quantity; the sign-up form and WhatsApp prompts are irrelevant.
* The PDF refers to a "16-sheet drawing set" and a 434-element 3D model that produced the quantities. **Neither was supplied**; both are registered as *Missing* (§4).

## 2. Import / index success per file

| Step | Result | Evidence |
|---|---|---|
| Copy to workspace `1. Tender Documents` | PASS, byte-identical | sha256 original = copy |
| Application index (`project index`) | Reports **"Extracted"**, 8,929 characters, category `boq` | stage `A1` |
| …but is the BOQ readable from that text? | **No.** 0 of 22 decimal quantities appear in the extracted text (integer counts cannot be tested this way). The text layer contains descriptions, units and bases but the Quantity column is blank | stage `A0`/`A1`; defect D-1 |
| Import through the BOQ importer | **The importer cannot read a PDF** (CSV/XLSX only). The PDF was **not** imported by the application. | defect D-2 |
| Workaround | Quantities were read by eye from the rendered pages (pdftoppm, pp.3–5) into `derived/BOQ_TRANSCRIBED_FROM_PDF_UNVERIFIED.csv`; every row carries "source PDF p.N; TRANSCRIBED FROM RENDERED PAGE – NOT VERIFIED". Done by one reader (me); **no second person has checked it.** Independent partial corroboration: the page-2 totals reconcile with the transcribed lines to within 0.01 for all six groups (§4), which makes a gross misreading unlikely but does not prove each line |

## 3. BOQ import (application workflow) — line counts and validation

Imported with the real importer (`app/imports/boq.py`) from the CSV above: **55 rows read = 7 section headings + 48 items**; 0 blank, 0 rejected, 0 duplicates, 0 needing review, 0 change requests.
* Descriptions: 48/48 identical to the transcription. Quantities (`quantity_original`): 48/48 identical. Original text retained; the "Remarks" column (basis + page + the source's own assumption note) is kept in `original_json`.
* **Unit conversions recorded:** `m³ → m3` (16 lines), `m² → m2` (5), `nos → nr` (25), `m → m` (2); all `unit_status = ok`; originals are kept in `unit_original`. No quantity conversion occurred (the source is already metric).
* **Mapping:** 0 of 48 lines mapped to an assembly. This is deliberate: mapping is a human decision (rule 4), there is no approved assembly/rate for these items, and nothing was invented. Mapping status for all 48 = *Unmapped*; pricing = *unpriced*.
* Document references: each item's printed measurement basis (e.g. "structural footing layout — sum of 73 mesh volumes") is stored as its Drawing Ref; the PDF page is in the remarks and in `drawing_to_boq_traceability.csv`.

## 4. Drawing-to-BOQ traceability and quantity verification

* **Traceable to a PDF page and printed measurement basis: 48/48. Traceable to a drawing actually supplied: 0/48. Verified against a drawing: 0/48.** No quantity can be called verified.
* Arithmetic checks that *are* possible (all from the document itself):

| Check | Printed | From the lines | Result |
|---|---:|---:|---|
| RCC total (2.1–2.10) | 129.42 m³ | 129.43 | differs 0.01 |
| Formwork total (3.1–3.4) | 1,746.67 m² | 1,746.68 | differs 0.01 |
| Masonry total (4.1–4.3) | 111.38 m³ | 111.39 | differs 0.01 |
| Plaster gross (4.4) | 1,345.20 m² | 1,345.20 | agrees |
| Doors | 16 | 16 | agrees |
| Windows | 32 | 32 | agrees |
| Item 1.3 backfill "= excavation − footing − blinding" | 240.58 m³ | 314.04 − 55.40 − 18.33 = **240.31** | **differs 0.27 m³** (query raised) |

* **Manual takeoff required — not measured, not invented.** 10 open actions (`ACT-PRJ-9201-001…010`) were created, each naming the BOQ item and the drawing/location a person must use, e.g. reinforcement steel + BBS (excluded by the source), plaster net of openings, finishes, MEP, external works, structural stair (item 2.10: the structural sheet is "quarantined"), ground level (1.1–1.3), roof members (7.1), railings (6.1). Every drawing named is itself *not supplied*.

## 5. Missing information and generated draft queries

**36 queries, all `Draft` (none issued, none approved)**, all marked blocking:
* **21 system-detected** (`generated_by = system:detector`): 11 `missing_input` (one per Missing document: ITT/contract, architectural set, MEP, 4 structural drawings, BBS, 2 specifications, site levels) and 10 `assumption_confirmation` (grouped by category).
* **15 operator drafts** (I wrote them from evidence in the PDF; labelled `user (practice-test operator)`; they are not system output): backfill arithmetic; page-2 totals; natural ground level; missing drawing set; quarantined stair sheet; reinforcement excluded; plaster measurement basis; finishes/MEP omitted; unusual opening sizes (6467×3140 door, 387×3140 / 368×3140 / 600×2950 / 4274×2000 windows); near-duplicate door sizes 800/802/736; no specification (grades, materials); IS 1200/INR vs the suite's region basis; roof/canopy members unspecified; two undated-revision dates; no commercial terms.
* By register: missing_input 14, assumption_confirmation 10, boq_discrepancy 4, technical 3, scope_exclusion 3, commercial 1, design_interface 1. Full text: `queries.json`; rendered in D25.
* **The application's own detectors found none of the BOQ-content problems** (defect D-3).

Missing inputs for estimate/programme (stage G2): rates for all 48 lines; productivity norms 0; workforce profiles 0; work activities 0; calendar none; lead times none; payment terms none; cost allocations none.

## 6. Assumptions and rates that remain unverified

* Rates: **none exist**. The library has 927 catalogue resources and 0 approved real rates (application's own completeness report: 927 catalogue resources, 0 approved real rates). Nothing was priced, nothing was approved.
* Assumptions register — 5 rows entered, all `Draft`/pending, none approved, none adopted as a value:

| ID | Origin | Class reported by the application |
|---|---|---|
| ASMP-PT-001 quantities used as printed | import | Imported but unverified |
| ASMP-PT-002 ground level assumed ±0.00 (source's own assumption) | import | Imported but unverified |
| ASMP-PT-003 scope limited to what the BOQ lists | manual (user-entered) | Pending human review |
| ASMP-PT-004 derived sums (system arithmetic) | calculated (system calculation) | Pending human review |
| ASMP-PT-005 region/currency/standard not established | manual | Pending human review |

* **Source-backed facts:** nothing can be classed "Verified source data" — that class needs a person's approval; none was given. **AI proposals: 0** (AI is disabled; two attempts to write an AI assumption — as `origin='ai'` and as an AI actor — were refused `AI_FORBIDDEN`). **Synthetic inputs in the real project: 0.**
* Project evidence report: 85 mandatory/adopted assumptions → 81 *Missing data*, 4 *Pending human review*, 0 verified/approved.
* Productivity values: none anywhere in this test.

## 7. Estimate and programme — to the extent supported

* Estimate state **Preliminary — Incomplete**: 0/48 lines priced, 0 mapped, blockers "48 BOQ item(s) are unpriced or incomplete" and "No computable commercial policy"; total cost, price, tax, payable = `None` (not zero). Reconciliation (the same BOQ as a non-demo project): 52 findings, 49 Critical (§10).
* Programme: `build_programme` → `CALENDAR_REQUIRED`; productivity programme report → needs a profile; schedule → `NO_SCHEDULE`; cash flow → `TERMS_NONE`; long-lead and plant-hire reports empty; procurement `detect_needs` → 0 needs. **No duration, crew, workforce or cost was produced.** A programme here would have been invented.

## 8. Documents actually generated and where

`practice_test/real_document/generated/PRJ-9201_tender_pack_r1/` — 112 files: 42 DOCX + 42 PDF + 26 XLSX + `manifest.json` + `applicability_matrix.json`; each DOCX/PDF/XLSX was parse-checked by the pack validator. Pack classification **demonstration**, banner "DEMONSTRATION EXPORT – NOT SUBMISSION READY"; `production_ready = false`.
Applicability (45 catalogue items): Required 25, Conditional 6, Not Applicable 3, Missing Customer Requirement 11. Status: **24 BLOCKED**, 18 *Preliminary (DEMONSTRATION)*, 3 Not Applicable.

| Requested output | Application document | Status |
|---|---|---|
| Basis of estimate | D07 | generated (Preliminary) — see defect D-6/D-7 |
| BOQ import and mapping report | D34 | generated — 48 items, 48 unmapped, 0 unit problems (matches DB) |
| Document completeness and revision report | D33 | generated — 1 current, 11 missing, 0 superseded |
| Technical query / RFI register | D25 | generated — 36 draft queries |
| BOQ discrepancy and scope-gap report | D34 + D25 (+ `queries.json`) | generated; no separate scope-gap document exists |
| Assumptions and exclusions register | D08, D09 | generated |
| Technical compliance matrix | D23 | **BLOCKED** — "no specification received: compliance requirements are unknown" |
| Procurement and missing-rate report | D36 | generated but **misleading** — defect D-4 |
| Workforce and programme report | D19, D20, D37 | **BLOCKED** — no activities / no norms |
| Preliminary technical proposal; execution methodology | D16, D17, D18 | **BLOCKED** — "tender documents do not state whether a technical proposal is required". *Not worked around*: writing one would require inventing scope and method |
| Commercial estimate and reconciliation report | D35 (+ D06, D13, D14) | D35 generated (reports 48 unpriced); D06/D13/D14 **BLOCKED** (no offer, payment terms, calendar) |
| Document applicability matrix | `applicability_matrix.json` / report | generated |
| Open actions and handover checklist | D42, D43 | D42 **BLOCKED** (required-input checklist, responsibilities); D43 generated (36 open queries, no baseline, not ready) |

Also written by the runner (not application documents): `drawing_to_boq_traceability.csv`, `derived/BOQ_TRANSCRIBED_FROM_PDF_UNVERIFIED.csv`, `queries.json`, `inventory.json`, `results.json`. The **drawing register is empty** (no drawing supplied; 6 drawing/survey documents referenced by the BOQ are registered as *Missing*); the **revision register** has one entry with no revision identifier. The **discipline completeness matrix** (8 disciplines: drawings Missing, specification Missing; BOQ partial for architectural/structural/civil, absent for all MEP) is in `results.json` stage `B2`; it was written by the runner from the register (defect D-9).

## 9. Calculation and document consistency checks

* Quantity arithmetic: §4 (6 groups + backfill).
* Estimate DB values vs documents: D34 states 48 items / 48 unmapped / 0 unit issues = DB; D43 states 36 open queries = DB; all generated documents carry the same estimate fingerprint `400c9f6df7ae5579` (v1).
* Pack validator: `ok = true`, 0 errors, 1 warning (D31 placeholder), 110 files checked, 24 blocked documents listed. **Note:** `ok` means the files are well-formed and consistent; it does *not* mean the pack is complete — completeness is carried by the BLOCKED list and the readiness result.
* Audit chain verify: PASS.
* No arithmetic on prices was possible (no prices), so no price consistency check exists for this project; those are covered by the synthetic run and its independent oracle (§12).

## 10. Approval gates and negative tests (actual results)

| Test | Result |
|---|---|
| Readiness, test environment | `demonstration`, not production-ready: 11 reasons incl. 50 reconciliation findings, estimate Incomplete, 36 open material queries, 11 required documents not received, D16/D06 unapproved |
| Readiness, forced to production environment | still `demonstration`/not ready (project flagged demo) |
| Author approves own assumption | refused `SELF_APPROVAL_BLOCKED` |
| Viewer creates assumption | refused `PERMISSION_DENIED` |
| AI origin / AI actor writes an assumption | refused `AI_FORBIDDEN` (×2) |
| Export without export approval | refused `EXPORT_NOT_APPROVED` |
| Approve an Incomplete estimate version (test actor) | refused `ESTIMATE_PRELIMINARY` |
| Approve a BLOCKED document (D16) | refused `DOC_BLOCKED` |
| **Real (non-demo) project, registered `human` users, production environment, same BOQ:** approve version | refused `ESTIMATE_PRELIMINARY` |
| …approve tender export / export submission | refused `ESTIMATE_NOT_APPROVED` / `EXPORT_NOT_APPROVED` |
| …pack generated for it | classification `not_ready`, `production_ready = false`, 25 blocked documents |
| …approve D16 (blocked) | refused `DOC_BLOCKED` |
| …approve D07 (not blocked) | **allowed** (an approval record is written) — but D07 stays *Draft* and the pack `not_ready`; it never reads "Approved for Submission" (observation O-1) |
| …reconciliation | 52 findings: 49 Critical (48 `UNPRICED_ITEM` + 1 `POLICY_UNAPPROVED`), 1 High (`INDIRECT_UNAPPROVED`), 2 Medium (`OFFER_MISSING`, `UNAPPROVED_ADOPTED_ASSUMPTION`) |
| …accept (waive) a Critical finding as a human Commercial Approver | refused `EXCEPTION_NOT_ALLOWED` |
| …final gate | blocked |
| Exports marked `submission_ready` in the database | **0** |

Conclusion supported by the evidence: with mandatory inputs missing (unpriced lines, no payment terms, no offer, missing documents, open queries), **neither a test actor nor registered human actors could produce a submission-ready status or label.** Several independent blocks held (Critical findings that cannot be waived, estimate state, missing export approval, BLOCKED documents).
**Caveat on unapproved assumptions (observation O-2):** `UNAPPROVED_ADOPTED_ASSUMPTION` is configured *Medium* with `exception_allowed = true` (`config/reconciliation_rules.json`), and it is one finding for all adopted-but-unapproved assumptions. So in this test unapproved assumptions were **not shown to block on their own** — the project was blocked by the other items. By design a registered human Commercial Approver may accept that finding as a recorded exception; only *synthetic* assumptions feeding an estimate, and unapproved norms/profiles/baselines, hard-block production readiness (closure gate, proven in the synthetic scenario). If the requirement is "no unapproved assumption may ever reach a submission-ready export", this needs a severity/policy change, which I did not make.
What this test does *not* prove: that a completely resolved package with genuine human approvals would be correctly accepted — that path is only exercised synthetically (§12).

## 11. Manual actions still required (by a person)

1. Obtain the full document package (drawing set with revisions, specifications, ITT/contract, BBS, site levels) and register it; re-run.
2. A second person compares the transcribed quantities with the PDF page images and signs the check; or obtain the BOQ as XLSX/CSV from the author.
3. Perform the 10 takeoff actions (reinforcement, plaster net, finishes, MEP, external works, stair, roof, railings, ground level).
4. Decide the region, currency, tax, measurement standard (the document is INR/IS 1200) and enter them; fix project defaults.
5. Review/issue/close the 36 draft queries (the system does not issue anything).
6. Map the 48 lines to assemblies (human decision), obtain/enter rates with sources, approve through the normal chain.
7. Enter and approve governed parameters (norms, calendar, workforce profile, payment terms) before any programme/cost-time claim.
8. State the customer's requirement for a technical proposal / quality plan so D16–D18 and D27–D30 can be generated.

## 12. Synthetic end-to-end scenario (kept separate)

`python scripts/run_closure_scenario.py /tmp/claude-0/syn_sep --out /tmp/claude-0/syn_sep_out` — separate scratch DB and output directory; no data shared with the real-document test. **All 27 stages PASS** (≈57 s). Summary: `practice_test/synthetic_separate_run.json` (acceptance_results SHA-256 recorded). The canonical committed outputs of that scenario remain in `demo_output/synthetic_closure/` and were not changed. It exercises what this input cannot: pricing, quotes, productivity/programme, tax/cash flow, document pack with approvals, freeze/replay.

## 13. Defects and observations found in the application

| # | Defect (evidence) | Severity |
|---|---|---|
| D-1 | **Silent partial extraction.** The indexer marks the PDF "Extracted" and the completeness report says "0 not text-extracted", although the Quantity column is absent from the text (0/22 decimal quantities). There is no check that tabular numeric content was readable | High for real use: a BOQ PDF looks indexed and "searchable" but cannot be searched for any quantity |
| D-2 | **No PDF/table import path.** The importer accepts only CSV/XLSX; a PDF BOQ needs manual transcription outside the application's provenance chain (the CSV is a derived file, not an imported original) | Medium |
| D-3 | **Draft-query detectors do not read BOQ content beyond description wording.** They found none of: the 0.27 m³ backfill discrepancy, totals mismatch, the source's own "assumed … confirm" note (kept in an unmapped Remarks column), near-duplicate or unusual sizes. The marker list has no "assumed"/"confirm". All 21 system queries came from register gaps/assumption categories | Medium |
| D-4 | **D36 (missing-rate/procurement report) misreports.** With 48 unmapped, unpriced lines it prints "Unpriced schedule lines: none" and "Procurement needs: none", and lists the 48 `UNPRICED_ITEM` exceptions under the heading "Resolved exceptions from the estimate". `detect_needs` also returns 0 for unmapped lines | High (a reader would conclude nothing is unpriced) |
| D-5 | **Completeness report** shows "Lines priced from eligible rates — OK" with 0/48 priced, and says "this demonstration project uses SYNTHETIC rates" for a project with none | Medium |
| D-6 | **Demo is conflated with synthetic.** Every generated document says "SYNTHETIC TEST DATA – FICTIONAL CUSTOMER" and "CONFIDENTIAL (synthetic test data)"; D07 says "SYNTHETIC DATA". Here the data are real third-party data, not synthetic. Conservative, but inaccurate labelling | Low–Medium |
| D-7 | **Silent regional defaults.** The project got region `KSA-ALL` and currency `SAR` by default and D07 prints them, while the only source uses INR/IS 1200. A default is shown as if it were a project fact | Medium |
| D-8 | **Zero vs unknown.** Estimate totals show `direct_cost = "0"` / `indirect_cost = "0"` while `total_cost = None`; completeness shows `missing_rate_lines 0`, `indicative_exposure 0` with 48 unpriced lines. The "Incomplete" state mitigates it | Low |
| D-9 | No discipline × document-type completeness matrix exists in the application (the runner built it) | Low (feature gap) |
| O-2 | Unapproved adopted assumptions are a single *Medium*, waivable reconciliation finding (see §10 caveat); they do not block submission-ready by themselves | Observation / policy decision |
| O-1 | A human Commercial Approver can approve a non-blocked document (D07) while the estimate is Incomplete; status stays *Draft* and the pack *not_ready*, so no false claim results | Observation |

I did **not** change application code in this task; none of these defects was fixed. The full automated suite was not re-run (only scripts/data were added); the synthetic scenario was.

## 14. Is the application suitable to progress to an authorised real-project pilot?

**Not on the strength of this test alone — conditionally yes afterwards.** (Decision for the project owner; I am reporting evidence, not authorising a pilot.)
* What the evidence supports: the controls hold under incomplete, unverified data — nothing was priced, mapped, approved or labelled submission-ready; missing items became blocked documents, draft queries and open actions; originals were preserved with checksums; AI and self-approval paths are refused.
* What it does not support: the input was a single non-contract web page with no drawings or specifications, so the real-data paths (quotation/rate approval with real evidence, programme from approved norms, a full pack with human approvals) were not exercised on real material, and the BOQ quantities came in via an unverified manual transcription.
* Before a pilot: fix D-1, D-3, D-4, D-5, D-7 (they can mislead a reader on a real package); supply a complete real package including an XLSX/CSV BOQ; keep the single-site/no-MFA limits in `docs/SECURITY.md` in force.
