# Tender document applicability matrix

Not every tender needs every document. `app/tender/catalogue.py` classifies each of the 45 catalogue items as **Required**, **Conditional**, **Not Applicable** or **Missing Customer Requirement** with a stated reason, from the project's trades, delivery model, contract type, the customer's *recorded* requirements, the documents received and the project stage. Report: `python -m app.cli report PRJ-nnnn applicability`.

## Inputs the matrix reads
* `tender_context` register item: `contract_type`, `delivery_model`, `customer_requires` (e.g. `{technical_proposal: yes|no, quality_plan: yes|no}`), `award_scenario` (`hypothetical` only for simulations).
* The received-document register (a current `specification` makes compliance documents Required; its absence makes them *Missing Customer Requirement*).
* Work activities, payment terms, long-lead items, indirect items, plant-hire terms, BOQ trades and commissioned trades (mechanical, HVAC, electrical, ELV, fire, piping, plumbing, industrial, instrument).

## Rules (the whole rule set)

| documents | rule |
|---|---|
| always Required | D01-D09, D11, D12, D14, D15, D25, D29, D33-D36, D40-D43, D45 - core tender record for every tender |
| D10 | Required when a commercial clarification is registered, else Conditional |
| D13 | Required with approved payment terms, else Missing Customer Requirement |
| D16-D18 | customer_requires.technical_proposal: yes -> Required, no -> Not Applicable, unrecorded -> Missing Customer Requirement |
| D19-D20 | Required when work activities exist, else Missing Customer Requirement |
| D21 | Required with plant-hire terms, else Conditional |
| D22 | Required with long-lead items, else Conditional |
| D23-D24 | Required when a specification is received, else Missing Customer Requirement |
| D26 | Required for design-build / EPC delivery, else Conditional |
| D27, D28, D30 | customer_requires.quality_plan decides; with a specification and no statement -> Required |
| D31 | Required with a commissioned trade, else Conditional |
| D32 | Conditional (confirm customer handover requirements) |
| D37 | Required when activities exist, else Conditional |
| D38 | Required when indirect items exist, else Not Applicable |
| D39 | Required when plant-hire terms exist, else Not Applicable |
| D44 | Required only with an award scenario selected, else Not Applicable (tender stage) |


## The catalogue

| code | group | document | formats | template id (version 1.0.0) |
|---|---|---|---|---|
| D01 | Executive and commercial | Tender cover letter | DOCX, PDF | T-COVER |
| D02 | Executive and commercial | Executive summary | DOCX, PDF | T-EXEC |
| D03 | Executive and commercial | Bid/no-bid record | DOCX, PDF | T-BIDNOBID |
| D04 | Executive and commercial | Scope of work and scope boundary | DOCX, PDF | T-SCOPE |
| D05 | Executive and commercial | Priced BOQ / pricing schedule | DOCX, PDF, XLSX | T-PRICED-BOQ |
| D06 | Executive and commercial | Commercial offer summary | DOCX, PDF | T-OFFER |
| D07 | Executive and commercial | Pricing basis and basis of estimate (BOE) | DOCX, PDF | T-BOE |
| D08 | Executive and commercial | Assumptions register | DOCX, PDF, XLSX | T-ASSUMPTIONS |
| D09 | Executive and commercial | Exclusions and qualifications | DOCX, PDF | T-EXCLUSIONS |
| D10 | Executive and commercial | Commercial clarifications | DOCX, PDF, XLSX | T-COMM-CLARIF |
| D11 | Executive and commercial | Risk and opportunity register | DOCX, PDF, XLSX | T-RISK |
| D12 | Executive and commercial | Tax and commercial terms summary | DOCX, PDF | T-TAX |
| D13 | Executive and commercial | Payment milestones and cash-flow basis | DOCX, PDF, XLSX | T-CASHFLOW |
| D14 | Executive and commercial | Validity, delivery and programme qualifications | DOCX, PDF | T-VALIDITY |
| D15 | Executive and commercial | Bid approval and submission-readiness record | DOCX, PDF | T-READINESS |
| D16 | Technical | Technical proposal | DOCX, PDF | T-TECH-PROPOSAL |
| D17 | Technical | Understanding of the project and scope | DOCX, PDF | T-UNDERSTANDING |
| D18 | Technical | Execution methodology | DOCX, PDF | T-METHODOLOGY |
| D19 | Technical | Construction programme and milestones | DOCX, PDF, XLSX | T-PROGRAMME |
| D20 | Technical | Workforce and resource-loading plan | DOCX, PDF, XLSX | T-WORKFORCE |
| D21 | Technical | Plant and equipment plan | DOCX, PDF, XLSX | T-PLANT |
| D22 | Technical | Procurement and long-lead schedule | DOCX, PDF, XLSX | T-PROCUREMENT |
| D23 | Technical | Technical compliance matrix | DOCX, PDF, XLSX | T-COMPLIANCE |
| D24 | Technical | Technical deviations and exceptions | DOCX, PDF, XLSX | T-DEVIATIONS |
| D25 | Technical | Technical query / RFI register | DOCX, PDF, XLSX | T-RFI |
| D26 | Technical | Design and interface matrix | DOCX, PDF, XLSX | T-INTERFACE |
| D27 | Technical | Quality plan summary | DOCX, PDF | T-QUALITY |
| D28 | Technical | ITP and inspection register | DOCX, PDF, XLSX | T-ITP |
| D29 | Technical | HSE execution summary and risk register | DOCX, PDF, XLSX | T-HSE |
| D30 | Technical | Material and technical submittal schedule | DOCX, PDF, XLSX | T-SUBMITTALS |
| D31 | Technical | Testing and commissioning plan | DOCX, PDF, XLSX | T-TESTING |
| D32 | Technical | Handover and closeout plan | DOCX, PDF | T-CLOSEOUT |
| D33 | Supporting records | Tender document register and revision log | DOCX, PDF, XLSX | T-DOCREG |
| D34 | Supporting records | BOQ mapping and quantity validation report | DOCX, PDF, XLSX | T-BOQ-VALIDATION |
| D35 | Supporting records | Estimate audit and reconciliation report | DOCX, PDF, XLSX | T-RECON |
| D36 | Supporting records | Missing-rate and procurement report | DOCX, PDF, XLSX | T-MISSING-RATES |
| D37 | Supporting records | Productivity and programme assumptions report | DOCX, PDF, XLSX | T-PRODUCTIVITY |
| D38 | Supporting records | Indirect-cost eligibility report | DOCX, PDF, XLSX | T-INDIRECT-ELIG |
| D39 | Supporting records | Plant-hire and equipment exposure report | DOCX, PDF, XLSX | T-PLANT-EXPOSURE |
| D40 | Supporting records | Estimate risk / sensitivity report | DOCX, PDF, XLSX | T-SENSITIVITY |
| D41 | Supporting records | Approval and decision log | DOCX, PDF, XLSX | T-APPROVALS |
| D42 | Supporting records | Open actions and outstanding information register | DOCX, PDF, XLSX | T-OPEN-ACTIONS |
| D43 | Supporting records | Tender handover checklist | DOCX, PDF | T-HANDOVER-CHECK |
| D44 | Supporting records | Post-award project setup checklist | DOCX, PDF | T-POSTAWARD |
| D45 | Supporting records | Final document manifest | DOCX, PDF, XLSX | T-MANIFEST |

Handover (simulated post-award) documents H01-H17: H01 Awarded scope and scope boundaries; H02 Final tender BOQ and cost baseline; H03 Approved assumptions and exclusions; H04 Customer clarifications and responses; H05 Programme baseline and constraints; H06 Procurement and long-lead commitments; H07 Subcontract interfaces; H08 Technical submittal obligations; H09 Quality, inspection and test obligations; H10 HSE and access requirements; H11 Commissioning and handover obligations; H12 Commercial terms, payment milestones and retention; H13 Risk register and mitigation owners; H14 Outstanding decisions and actions; H15 Document register and revisions; H16 Estimate snapshot and replay fingerprint; H17 Follow-up action owners.

## Matrix produced for the synthetic closure project (revision 1 pack, before the open items were resolved)
Counts: {'Conditional': 2, 'Missing Customer Requirement': 1, 'Not Applicable': 1, 'Required': 41}. Inputs: {'award_scenario': False, 'contract_type': 'lump sum (FICTIONAL)', 'customer_requires': {'quality_plan': 'yes', 'technical_proposal': 'yes'}, 'delivery_model': 'construct-only (fictional)', 'documents': 12}.

| code | document | applicability | reason |
|---|---|---|---|
| D01 | Tender cover letter | Required | core tender record produced for every tender |
| D02 | Executive summary | Required | core tender record produced for every tender |
| D03 | Bid/no-bid record | Required | core tender record produced for every tender |
| D04 | Scope of work and scope boundary | Required | core tender record produced for every tender |
| D05 | Priced BOQ / pricing schedule | Required | core tender record produced for every tender |
| D06 | Commercial offer summary | Required | core tender record produced for every tender |
| D07 | Pricing basis and basis of estimate (BOE) | Required | core tender record produced for every tender |
| D08 | Assumptions register | Required | core tender record produced for every tender |
| D09 | Exclusions and qualifications | Required | core tender record produced for every tender |
| D10 | Commercial clarifications | Required | 1 commercial clarification(s) are registered |
| D11 | Risk and opportunity register | Required | core tender record produced for every tender |
| D12 | Tax and commercial terms summary | Required | core tender record produced for every tender |
| D13 | Payment milestones and cash-flow basis | Missing Customer Requirement | no approved payment terms (contract payment / retention / bond terms) have been supplied |
| D14 | Validity, delivery and programme qualifications | Required | core tender record produced for every tender |
| D15 | Bid approval and submission-readiness record | Required | core tender record produced for every tender |
| D16 | Technical proposal | Required | the customer requires a technical proposal (tender_context.customer_requires.technical_proposal = yes) |
| D17 | Understanding of the project and scope | Required | the customer requires a technical proposal (tender_context.customer_requires.technical_proposal = yes) |
| D18 | Execution methodology | Required | the customer requires a technical proposal (tender_context.customer_requires.technical_proposal = yes) |
| D19 | Construction programme and milestones | Required | work activities with norms are defined for the programme |
| D20 | Workforce and resource-loading plan | Required | work activities with norms are defined for the programme |
| D21 | Plant and equipment plan | Required | plant hire terms / plant resources are in the estimate |
| D22 | Procurement and long-lead schedule | Required | long-lead items are registered |
| D23 | Technical compliance matrix | Required | a specification / standard has been received that requires a compliance response |
| D24 | Technical deviations and exceptions | Required | a specification / standard has been received that requires a compliance response |
| D25 | Technical query / RFI register | Required | core tender record produced for every tender |
| D26 | Design and interface matrix | Conditional | construct-only delivery; interfaces still need recording where the BOQ names other parties |
| D27 | Quality plan summary | Required | the customer requires a quality plan / ITP / submittal schedule (tender_context.customer_requires.quality_plan = yes) |
| D28 | ITP and inspection register | Required | the customer requires a quality plan / ITP / submittal schedule (tender_context.customer_requires.quality_plan = yes) |
| D29 | HSE execution summary and risk register | Required | core tender record produced for every tender |
| D30 | Material and technical submittal schedule | Required | the customer requires a quality plan / ITP / submittal schedule (tender_context.customer_requires.quality_plan = yes) |
| D31 | Testing and commissioning plan | Required | the scope includes systems that need testing and commissioning |
| D32 | Handover and closeout plan | Conditional | required by most contracts; confirm customer handover requirements |
| D33 | Tender document register and revision log | Required | core tender record produced for every tender |
| D34 | BOQ mapping and quantity validation report | Required | core tender record produced for every tender |
| D35 | Estimate audit and reconciliation report | Required | core tender record produced for every tender |
| D36 | Missing-rate and procurement report | Required | core tender record produced for every tender |
| D37 | Productivity and programme assumptions report | Required | productivity norms drive the programme |
| D38 | Indirect-cost eligibility report | Required | indirect items exist |
| D39 | Plant-hire and equipment exposure report | Required | day-priced plant exists |
| D40 | Estimate risk / sensitivity report | Required | core tender record produced for every tender |
| D41 | Approval and decision log | Required | core tender record produced for every tender |
| D42 | Open actions and outstanding information register | Required | core tender record produced for every tender |
| D43 | Tender handover checklist | Required | core tender record produced for every tender |
| D44 | Post-award project setup checklist | Not Applicable | tender stage: applicable only after an award (no award scenario selected) |
| D45 | Final document manifest | Required | core tender record produced for every tender |


## What a status means

| status | meaning |
|---|---|
| BLOCKED | the document contains an explicit `[[MISSING: ...]]` marker (missing input or Missing Customer Requirement); it cannot be approved until the input exists |
| Preliminary (DEMONSTRATION) | pack classification is `demonstration` (demo/synthetic data, test environment or test actors) - never submission-ready |
| Draft | classification `not_ready` |
| For Review | the approval chain verifies in a production environment **and** the pack has no BLOCKED documents and no placeholders; awaiting document approval |
| Approved for Submission | as above **and** that document was approved by a registered human Commercial Approver/Administrator in production |
| Not Applicable | no files; reason recorded |

