# Synthetic tender closure - generated output

**SYNTHETIC TEST DATA - FICTIONAL CUSTOMER - NOT A REAL TENDER - NOT A MARKET QUOTE - NOT FOR SUBMISSION.** Produced by `python scripts/run_closure_scenario.py <fresh dir> --out demo_output/synthetic_closure` from the scenario in `tests/closure/` (project `PRJ-9101`, "Dammam Industrial Utilities - Synthetic Tender Closure"). All actors were registered TEST ACTORS; the packs are DEMONSTRATION packs and can never be submission-ready.

| Path | What it is |
|---|---|
| `PRJ-9101_tender_pack_r2/` | the final demonstration tender pack (45 catalogue items: 44 applicable documents in DOCX + PDF, XLSX for registers; 1 Not Applicable with its reason), `manifest.json`, `applicability_matrix.json` |
| `PRJ-9101_handover_pack_r1/` | the **hypothetical** post-award handover pack H01-H17 (no award was made) |
| `MANIFEST.json` | machine-readable list of every file with SHA-256, bytes, status and template version |
| `acceptance_results.json` | machine-readable verdict and evidence of each of the 27 stages |
| `tender_manifest_rev1_before_resolution.json`, `applicability_matrix_rev1_before_resolution.json` | the first pack (revision 1, generated while documents D06, D13, D14 and D30 were BLOCKED by missing inputs); its files are not committed |

Revision 3 (regenerated after a global library change to prove the frozen figures do not move) is not committed; the run verified every printed estimate figure equals revision 2. Verify a file: `sha256sum <file>` against `MANIFEST.json`. Evidence report: `docs/SYNTHETIC_END_TO_END_CLOSURE_REPORT.md`.
