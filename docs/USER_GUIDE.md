# User guide

This guide walks through the **synthetic demonstration project** (everything labelled SYNTHETIC / DEMO / NOT A MARKET QUOTE), then explains each section of the application. The same steps apply to a real project.

## 0. Start
```
python -m app.cli init --demo-users      # prints the admin password once
python -m app.cli demo                    # creates PRJ-0001 with nine packages, deliberately left with realistic open issues
python -m app.cli run                     # http://127.0.0.1:8000
```
Demo logins (if `--demo-users`): `estimator`, `procurement`, `commercial` / `demo-only-change-me`. Use the matching role for each step - the server enforces it.

## 1. Walkthrough (what to do, in order)
1. **Dashboard** - PRJ-0001 shows *Preliminary - Incomplete*, unpriced lines, indicative exposure, unapproved assumptions in use, no reconciliation run yet. Percentages show "n/a" when undefined.
2. **BOQ import** - the demo BOQ was imported from `data/demo/demo_boq.xlsx`: 26 items, 9 headings, 1 blank row, 1 rejected row (quantity `TBA`), item `2.2` with the **ambiguous unit "ton"**, and duplicate code `6.1`.
   *Estimator*: approve the pending unit change for 2.2 (choose `t`), and *Acknowledge flags* on `6.1#2` with a reason. To import your own BOQ: *BOQ import -> upload -> check the detected header/mapping -> Import*.
3. **Mapping** - items are mapped to approved synthetic assemblies. Try *Suggest mappings (keyword match)* on any unmapped item and approve/reject the suggestion. Set a pricing method for lump-sum/subcontract, provisional sum, PC sum, allowance or excluded items.
4. **Estimate build-up** - see every resource line with its rate, status, calculation *basis*, and flags; items without an eligible rate show **UNPRICED** (with indicative value if a non-approved rate exists). Toggle *Preliminary view* to include unapproved inputs (clearly flagged).
5. **Resource libraries** - tile rate (DEMO-MAT-009) is *Pending Review*; cable tray (DEMO-MAT-014) is *Expired*. *Procurement Reviewer*: approve the tile rate; propose a new tray rate (new version) and approve it.
6. **Procurement & RFQs** - *Detect procurement needs*: sprinkler heads, AHU, CCTV cameras and lifts have no rate. Create an RFQ per package, export XLSX/DOCX or copy the email text. You send it yourself.
7. **Quotations** - enter the supplier's quotation (or import the completed RFQ sheet), submit, then the **Procurement Reviewer** verifies it. Open *Compare quotations*: quoted totals vs normalised values, coverage and notes. Propose a selection (a reason is required if not the lowest like-for-like), approve it, *Propose rates from this quotation*, then approve each rate on the resource page.
8. **Indirects & commercials** - indirects, duration and the commercial policy are approved (synthetic). The tax category **VAT-STD is Pending Review**: a *Commercial Approver* must enter verification evidence and approve it before tax and final payable resolve.
9. **Clarifications & risk** - resolve the two open clarifications (client response + evidence), approve the scope entries (inclusion/exclusion/qualification). Approve the provisional sum / PC sum / allowance decisions on the Mapping page.
10. **Reconciliation** - *Run reconciliation*. Fix or (where the rule allows) accept documented exceptions; Critical findings can never be waived.
11. **Reports & exports** - generate the **offer letter**, have it approved; freeze an estimate version, submit it and have a **Commercial Approver** approve it (Reconciliation page); approve the tender export; then *Export submission package*. Preliminary outputs are available at any time and are watermarked.

`tests/integration/test_full_workflow.py` performs exactly this journey with explicit human actors and independently computed expected values.

## 2. Sections
| Section | Purpose |
|---|---|
| Dashboard | per-project value, missing-rate exposure, unapproved assumptions, pending/expired quotations, clarifications, Critical findings, approval status, completeness |
| Projects | create (name, client, region, stage, tax category); archive (read-only); project package export |
| BOQ import | preview, header detection, column mapping, validation summary, rejected rows, pending change requests, re-import diff, take-off resource lines |
| Mapping | cost code, assembly, pricing method; suggestions; allowance approvals |
| Estimate build-up | lines, items, exceptions, cost-to-price reconciliation, strict vs preliminary |
| Resource libraries | search/filter 927+ resources, rate versions, propose/approve rates, history |
| Assumptions | global register and project overrides; what-if effect |
| Procurement & RFQs, Vendor quotations, Quote levelling | see [PROCUREMENT_GUIDE.md](PROCUREMENT_GUIDE.md) |
| Indirects & commercials | indirect items and allocation, duration proposals/approval, commercial policy, tax categories |
| Clarifications & risk | clarification register, inclusions/exclusions/qualifications, risk register, rule-based scope checks |
| Reconciliation | findings by severity, exceptions, version freeze/approval |
| Approvals | queue of everything awaiting a decision + the approval log |
| Reports & exports | workbook download/re-import, offer, preliminary and final exports, estimate-vs-actual |
| Settings & data sources | company details, users, tax/FX, source register, rate dataset ingestion, taxonomy, backups |

## 3. Working in Excel
*Reports -> Download master workbook* gives a 27-sheet workbook (see [EXCEL_WORKBOOK_GUIDE.md](EXCEL_WORKBOOK_GUIDE.md)). Edit only yellow cells, then *Re-import*. Imports create drafts/proposals; status columns typed in the file are ignored.

## 4. Optional AI
Set `KSA_AI_ENABLED=true` and `ANTHROPIC_API_KEY` (environment only). AI can suggest mappings, extract quotation fields from text you paste, draft clarifications and flag scope gaps. Everything lands as *Pending Review* with a confidence and source references; you accept or reject it.
Without a key every deterministic feature still works.

## 5. Adding things without touching code
See [EXTENDING.md](EXTENDING.md).
