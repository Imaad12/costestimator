# Excel data dictionary

Generated from `app/excel/spec.py` (the single source of truth for all workbooks). Row 5 = headers, hidden row 4 = machine keys, data from row 6.

## Trade and Cost Code Mapping

Map each BOQ item to an internal cost code and an approved assembly. Mapping suggestions (heuristic/AI) stay 'Suggested' until a human approves them in the application. Cost-code taxonomy is listed on the right for reference.

| Header | Key | Class | Format / list |
|---|---|---|---|
| BOQ item key | `item_key` | Read-only (blue) |  |
| Client code | `item_code` | Read-only (blue) |  |
| Description | `description` | Read-only (blue) |  |
| Client trade | `trade` | Read-only (blue) |  |
| Cost code | `cost_code` | Input (yellow) |  list costcodes |
| Assembly code | `assembly_code` | Input (yellow) |  |
| Mapping status | `mapping_status` | Read-only (blue) |  |
| Mapping source | `mapping_source` | Read-only (blue) |  |
| Pricing method | `pricing_method` | Input (yellow) |  list PricingMethod |

## Pricing Schedule

Tendered unit rates and amounts from the application. Amount = ROUND(quantity x unit rate, 2). 'Engine amount' is the authoritative application value; 'Check' flags any difference (stale or edited formula).

| Header | Key | Class | Format / list |
|---|---|---|---|
| Item | `item_code` | Read-only (blue) |  |
| Description | `description` | Read-only (blue) |  |
| Unit | `unit` | Read-only (blue) |  |
| Quantity | `quantity` | Read-only (blue) | #,##0.000 |
| Unit rate (SAR) | `unit_rate` | Read-only (blue) | #,##0.00;[Red]-#,##0.00 |
| Amount (SAR) | `amount` | Formula (grey, locked) | #,##0.00;[Red]-#,##0.00 / `=IF(OR(D{r}="",E{r}=""),"",ROUND(D{r}*E{r},2))` |
| Engine amount | `engine_amount` | Read-only (blue) | #,##0.00;[Red]-#,##0.00 |
| Check | `check` | Formula (grey, locked) |  `=IF(OR(F{r}="",G{r}=""),"",IF(ABS(F{r}-G{r})>0.01,"MISMATCH","OK"))` |
| Status | `status` | Read-only (blue) |  |
| Flags | `flags` | Read-only (blue) |  |

## BOQ Import

Quantities are measured by the estimator in the tool of choice and imported here; the application never measures or alters them. Re-import is safe: differences become pending change requests. Required: Description, Unit, Quantity.

| Header | Key | Class | Format / list |
|---|---|---|---|
| Item | `item_code` | Input (yellow) |  |
| Description | `description` | Input (yellow) |  |
| Trade | `trade` | Input (yellow) |  |
| Unit | `unit` | Input (yellow) |  |
| Quantity | `quantity` | Input (yellow) | #,##0.000 |
| Client rate | `client_rate` | Input (yellow) | #,##0.00;[Red]-#,##0.00 |
| Client amount | `client_amount` | Input (yellow) | #,##0.00;[Red]-#,##0.00 |
| Drawing ref | `drawing_ref` | Input (yellow) |  |
| Spec ref | `spec_ref` | Input (yellow) |  |
| Cost code | `cost_code` | Input (yellow) |  list costcodes |
| Revision | `revision` | Input (yellow) |  |
| Source file | `source_file` | Read-only (blue) |  |
| Source sheet | `source_sheet` | Read-only (blue) |  |
| Source row | `source_row` | Read-only (blue) |  |
| Original qty text | `quantity_original` | Read-only (blue) |  |
| Unit status | `unit_status` | Read-only (blue) |  |
| Validation | `validation_status` | Read-only (blue) |  |
| Issues | `issues` | Read-only (blue) |  |

## Direct Cost Build-Up

One row per resource line: quantity x rate. Unpriced lines are blank (never zero) and listed with their exception. Amount formula = ROUND(qty x rate, 2); 'Engine amount' is authoritative.

| Header | Key | Class | Format / list |
|---|---|---|---|
| BOQ item | `item_key` | Read-only (blue) |  |
| Assembly | `assembly` | Read-only (blue) |  |
| Line ref | `line_ref` | Read-only (blue) |  |
| Kind | `kind` | Read-only (blue) |  |
| Resource ID | `resource_id` | Read-only (blue) |  |
| Description | `description` | Read-only (blue) |  |
| Quantity | `quantity` | Read-only (blue) | #,##0.000 |
| Unit | `unit` | Read-only (blue) |  |
| Rate (SAR) | `rate` | Read-only (blue) | #,##0.0000 |
| Amount (SAR) | `amount` | Formula (grey, locked) | #,##0.00;[Red]-#,##0.00 / `=IF(OR(G{r}="",I{r}=""),"",ROUND(G{r}*I{r},2))` |
| Engine amount | `engine_amount` | Read-only (blue) | #,##0.00;[Red]-#,##0.00 |
| Check | `check` | Formula (grey, locked) |  `=IF(OR(J{r}="",K{r}=""),"",IF(ABS(J{r}-K{r})>0.01,"MISMATCH","OK"))` |
| Rate type | `rate_type` | Read-only (blue) |  |
| Rate status | `rate_status` | Read-only (blue) |  |
| Eligibility | `eligibility` | Read-only (blue) |  |
| Calculation basis | `basis` | Read-only (blue) |  |
| Flags | `flags` | Read-only (blue) |  |

## Labour Library

Resource definitions with their current APPROVED rate (blue, read-only). Enter a proposed rate in the yellow columns: it is imported as a Draft proposal and needs review/approval in the application. A blank rate means the rate is MISSING - it is never treated as zero.

| Header | Key | Class | Format / list |
|---|---|---|---|
| Resource ID | `id` | Read-only (blue) |  |
| Cost code | `cost_code` | Input (yellow) |  list costcodes |
| Category | `category` | Input (yellow) |  |
| Description | `description` | Input (yellow) |  |
| Specification | `specification` | Input (yellow) |  |
| Unit | `unit` | Input (yellow) |  list units |
| Current approved rate | `rate` | Read-only (blue) | #,##0.00;[Red]-#,##0.00 |
| Currency | `currency` | Read-only (blue) |  |
| Rate type | `rate_type` | Read-only (blue) |  |
| Rate status | `rate_status` | Read-only (blue) |  |
| Price date | `price_date` | Read-only (blue) | yyyy-mm-dd |
| Valid until | `valid_until` | Read-only (blue) | yyyy-mm-dd |
| Supplier | `supplier` | Read-only (blue) |  |
| Source / evidence | `evidence` | Read-only (blue) |  |
| Confidence | `confidence` | Read-only (blue) |  |
| Region | `region` | Read-only (blue) |  |
| PROPOSED new rate | `new_rate` | Input (yellow) | #,##0.00;[Red]-#,##0.00 |
| Proposed rate type | `new_rate_type` | Input (yellow) |  list RateType |
| Proposed currency | `new_currency` | Input (yellow) |  |
| Proposed price date | `new_price_date` | Input (yellow) | yyyy-mm-dd |
| Proposed valid until | `new_valid_until` | Input (yellow) | yyyy-mm-dd |
| Proposed source / evidence | `new_evidence` | Input (yellow) |  |

## Material Library

Resource definitions with their current APPROVED rate (blue, read-only). Enter a proposed rate in the yellow columns: it is imported as a Draft proposal and needs review/approval in the application. A blank rate means the rate is MISSING - it is never treated as zero.

| Header | Key | Class | Format / list |
|---|---|---|---|
| Resource ID | `id` | Read-only (blue) |  |
| Cost code | `cost_code` | Input (yellow) |  list costcodes |
| Category | `category` | Input (yellow) |  |
| Description | `description` | Input (yellow) |  |
| Specification | `specification` | Input (yellow) |  |
| Unit | `unit` | Input (yellow) |  list units |
| Current approved rate | `rate` | Read-only (blue) | #,##0.00;[Red]-#,##0.00 |
| Currency | `currency` | Read-only (blue) |  |
| Rate type | `rate_type` | Read-only (blue) |  |
| Rate status | `rate_status` | Read-only (blue) |  |
| Price date | `price_date` | Read-only (blue) | yyyy-mm-dd |
| Valid until | `valid_until` | Read-only (blue) | yyyy-mm-dd |
| Supplier | `supplier` | Read-only (blue) |  |
| Source / evidence | `evidence` | Read-only (blue) |  |
| Confidence | `confidence` | Read-only (blue) |  |
| Region | `region` | Read-only (blue) |  |
| PROPOSED new rate | `new_rate` | Input (yellow) | #,##0.00;[Red]-#,##0.00 |
| Proposed rate type | `new_rate_type` | Input (yellow) |  list RateType |
| Proposed currency | `new_currency` | Input (yellow) |  |
| Proposed price date | `new_price_date` | Input (yellow) | yyyy-mm-dd |
| Proposed valid until | `new_valid_until` | Input (yellow) | yyyy-mm-dd |
| Proposed source / evidence | `new_evidence` | Input (yellow) |  |

## Plant and Equipment Library

Resource definitions with their current APPROVED rate (blue, read-only). Enter a proposed rate in the yellow columns: it is imported as a Draft proposal and needs review/approval in the application. A blank rate means the rate is MISSING - it is never treated as zero.

| Header | Key | Class | Format / list |
|---|---|---|---|
| Resource ID | `id` | Read-only (blue) |  |
| Cost code | `cost_code` | Input (yellow) |  list costcodes |
| Category | `category` | Input (yellow) |  |
| Description | `description` | Input (yellow) |  |
| Specification | `specification` | Input (yellow) |  |
| Unit | `unit` | Input (yellow) |  list units |
| Current approved rate | `rate` | Read-only (blue) | #,##0.00;[Red]-#,##0.00 |
| Currency | `currency` | Read-only (blue) |  |
| Rate type | `rate_type` | Read-only (blue) |  |
| Rate status | `rate_status` | Read-only (blue) |  |
| Price date | `price_date` | Read-only (blue) | yyyy-mm-dd |
| Valid until | `valid_until` | Read-only (blue) | yyyy-mm-dd |
| Supplier | `supplier` | Read-only (blue) |  |
| Source / evidence | `evidence` | Read-only (blue) |  |
| Confidence | `confidence` | Read-only (blue) |  |
| Region | `region` | Read-only (blue) |  |
| PROPOSED new rate | `new_rate` | Input (yellow) | #,##0.00;[Red]-#,##0.00 |
| Proposed rate type | `new_rate_type` | Input (yellow) |  list RateType |
| Proposed currency | `new_currency` | Input (yellow) |  |
| Proposed price date | `new_price_date` | Input (yellow) | yyyy-mm-dd |
| Proposed valid until | `new_valid_until` | Input (yellow) | yyyy-mm-dd |
| Proposed source / evidence | `new_evidence` | Input (yellow) |  |

## Subcontract Library

Resource definitions with their current APPROVED rate (blue, read-only). Enter a proposed rate in the yellow columns: it is imported as a Draft proposal and needs review/approval in the application. A blank rate means the rate is MISSING - it is never treated as zero.

| Header | Key | Class | Format / list |
|---|---|---|---|
| Resource ID | `id` | Read-only (blue) |  |
| Cost code | `cost_code` | Input (yellow) |  list costcodes |
| Category | `category` | Input (yellow) |  |
| Description | `description` | Input (yellow) |  |
| Specification | `specification` | Input (yellow) |  |
| Unit | `unit` | Input (yellow) |  list units |
| Current approved rate | `rate` | Read-only (blue) | #,##0.00;[Red]-#,##0.00 |
| Currency | `currency` | Read-only (blue) |  |
| Rate type | `rate_type` | Read-only (blue) |  |
| Rate status | `rate_status` | Read-only (blue) |  |
| Price date | `price_date` | Read-only (blue) | yyyy-mm-dd |
| Valid until | `valid_until` | Read-only (blue) | yyyy-mm-dd |
| Supplier | `supplier` | Read-only (blue) |  |
| Source / evidence | `evidence` | Read-only (blue) |  |
| Confidence | `confidence` | Read-only (blue) |  |
| Region | `region` | Read-only (blue) |  |
| PROPOSED new rate | `new_rate` | Input (yellow) | #,##0.00;[Red]-#,##0.00 |
| Proposed rate type | `new_rate_type` | Input (yellow) |  list RateType |
| Proposed currency | `new_currency` | Input (yellow) |  |
| Proposed price date | `new_price_date` | Input (yellow) | yyyy-mm-dd |
| Proposed valid until | `new_valid_until` | Input (yellow) | yyyy-mm-dd |
| Proposed source / evidence | `new_evidence` | Input (yellow) |  |

## Assembly Library

Assemblies are versioned; approved versions are immutable. Edits are imported as a NEW draft version for review. Waste: set ONE basis only (factor already includes waste, or fixed %, or assumption reference). Labour needs an explicit productivity basis.

| Header | Key | Class | Format / list |
|---|---|---|---|
| Assembly code | `assembly_code` | Input (yellow) |  |
| Version | `version` | Read-only (blue) |  |
| Status | `status` | Read-only (blue) |  |
| Assembly description | `description` | Input (yellow) |  |
| Unit | `unit` | Input (yellow) |  list units |
| Cost code | `cost_code` | Input (yellow) |  list costcodes |
| Line | `line_no` | Read-only (blue) |  |
| Line type | `line_type` | Input (yellow) |  list LineType |
| Resource ID | `resource_id` | Input (yellow) |  |
| Nested assembly | `child_assembly_code` | Input (yellow) |  |
| Factor / output | `factor` | Input (yellow) | #,##0.000 |
| Factor unit | `factor_unit` | Input (yellow) |  list units |
| Factor incl. waste (1/0) | `factor_includes_waste` | Input (yellow) |  |
| Waste basis | `waste_basis` | Input (yellow) |  list WasteBasis |
| Waste % | `waste_value` | Input (yellow) |  |
| Waste assumption ID | `waste_ref` | Input (yellow) |  |
| Productivity basis | `productivity_basis` | Input (yellow) |  list Productivity |
| Crew (resource:count;...) | `crew` | Input (yellow) |  |
| Sub incl. labour | `includes_labour` | Input (yellow) |  |
| Sub incl. material | `includes_material` | Input (yellow) |  |
| Sub incl. plant | `includes_plant` | Input (yellow) |  |
| Utilisation basis | `utilisation_basis` | Input (yellow) |  list WasteBasis |
| Utilisation % | `utilisation_value` | Input (yellow) |  |
| Utilisation assumption | `utilisation_ref` | Input (yellow) |  |
| Confidence | `confidence` | Read-only (blue) |  |
| Source | `source` | Read-only (blue) |  |

## Assumptions Register

Effective value for this project (blue). To propose a project override, enter the value and a reason in the yellow columns; it is imported as 'Pending Review' and never changes the global library.

| Header | Key | Class | Format / list |
|---|---|---|---|
| Assumption ID | `id` | Read-only (blue) |  |
| Family | `family` | Read-only (blue) |  |
| Name | `name` | Read-only (blue) |  |
| Description | `description` | Read-only (blue) |  |
| Applies to | `applies_to` | Read-only (blue) |  |
| Effective value | `value` | Read-only (blue) |  |
| Unit | `unit` | Read-only (blue) |  |
| Status | `status` | Read-only (blue) |  |
| Origin | `origin` | Read-only (blue) |  |
| Engine key | `engine_key` | Read-only (blue) |  |
| Confidence | `confidence` | Read-only (blue) |  |
| PROPOSED project value | `override_value` | Input (yellow) |  |
| Reason for override | `override_reason` | Input (yellow) |  |

## Indirect Costs

Fixed, percentage and duration-based costs. Project duration must be approved before duration-based items calculate. Items included in a subcontract quotation are excluded to avoid double counting.

| Header | Key | Class | Format / list |
|---|---|---|---|
| Code | `code` | Input (yellow) |  |
| Category | `category` | Input (yellow) |  |
| Description | `description` | Input (yellow) |  |
| Method | `method` | Input (yellow) |  list IndirectMethod |
| Rate / amount | `amount` | Input (yellow) | #,##0.00;[Red]-#,##0.00 |
| Quantity (people/units) | `quantity` | Input (yellow) |  |
| Allocation | `allocation_method` | Input (yellow) |  list Allocation |
| Alloc. target | `allocation_target` | Input (yellow) |  |
| Incl. in subcontract (1/0) | `included_in_subcontract` | Input (yellow) |  |
| Status | `status` | Read-only (blue) |  |
| Calculated amount | `engine_amount` | Read-only (blue) | #,##0.00;[Red]-#,##0.00 |
| Calculation basis | `basis` | Read-only (blue) |  |

## Procurement Register

Missing, expired, unapproved and low-confidence rates become procurement requirements. RFQs are drafted (never sent) from this register.

| Header | Key | Class | Format / list |
|---|---|---|---|
| Item ID | `id` | Read-only (blue) |  |
| Package | `package_id` | Read-only (blue) |  |
| Trade | `trade` | Read-only (blue) |  |
| Resource | `resource_id` | Read-only (blue) |  |
| Description | `description` | Read-only (blue) |  |
| Specification | `specification` | Read-only (blue) |  |
| Quantity | `quantity` | Read-only (blue) | #,##0.000 |
| Unit | `unit` | Read-only (blue) |  |
| Delivery location | `delivery_location` | Input (yellow) |  |
| Required date | `required_date` | Input (yellow) | yyyy-mm-dd |
| Preferred suppliers | `preferred_suppliers` | Input (yellow) |  |
| Reason | `reason` | Read-only (blue) |  |
| Indicative exposure (SAR) | `estimated_exposure` | Read-only (blue) | #,##0.00;[Red]-#,##0.00 |
| RFQ status | `rfq_status` | Read-only (blue) |  |
| Response deadline | `response_deadline` | Input (yellow) | yyyy-mm-dd |
| Quotation status | `quotation_status` | Read-only (blue) |  |
| Approval status | `approval_status` | Read-only (blue) |  |

## Vendor Directory

No contact detail may be entered without a traceable source and permitted use. Never copy contacts from unverified places. Contacts are optional.

| Header | Key | Class | Format / list |
|---|---|---|---|
| Vendor ID | `id` | Read-only (blue) |  |
| Name | `name` | Input (yellow) |  |
| Type | `supplier_type` | Input (yellow) |  |
| Trades (cost codes) | `trades` | Input (yellow) |  |
| Region | `region` | Input (yellow) |  |
| Contact | `contact_name` | Input (yellow) |  |
| Email | `contact_email` | Input (yellow) |  |
| Phone | `contact_phone` | Input (yellow) |  |
| Contact source (required if contact given) | `contact_source` | Input (yellow) |  |
| Qualification | `qualification_status` | Read-only (blue) |  |
| Synthetic (1/0) | `is_synthetic` | Read-only (blue) |  |

## Vendor Quotations

Enter or import supplier quotations. Imported quotations start as Draft; a Procurement Reviewer verifies them against the supplier's document. AI-extracted values must be checked by a human.

| Header | Key | Class | Format / list |
|---|---|---|---|
| Quotation ID | `quotation_id` | Input (yellow) |  |
| Vendor ID | `supplier_id` | Input (yellow) |  |
| Supplier ref | `reference` | Input (yellow) |  |
| Quote date | `quote_date` | Input (yellow) | yyyy-mm-dd |
| Valid until | `valid_until` | Input (yellow) | yyyy-mm-dd |
| Currency | `currency` | Input (yellow) |  |
| Tax (excl/incl/exempt) | `tax_treatment` | Input (yellow) |  list TaxTreatment |
| Tax rate % | `tax_rate_pct` | Input (yellow) |  |
| Payment terms | `payment_terms` | Input (yellow) |  |
| Status | `status` | Read-only (blue) |  |
| Line | `line_no` | Input (yellow) |  |
| Procurement item | `procurement_item_id` | Input (yellow) |  |
| Description | `description` | Input (yellow) |  |
| Qty | `quantity` | Input (yellow) | #,##0.000 |
| Unit | `unit` | Input (yellow) |  |
| Unit rate | `unit_rate` | Input (yellow) | #,##0.00;[Red]-#,##0.00 |
| Disc % | `discount_pct` | Input (yellow) |  |
| Extended (qty x rate x (1-disc)) | `extended` | Formula (grey, locked) | #,##0.00;[Red]-#,##0.00 / `=IF(OR(N{r}="",P{r}=""),"",N{r}*P{r}*(1-IF(Q{r}="",0,Q{r})/100))` |
| Delivery incl. | `delivery_included` | Input (yellow) |  list YesNoUnknown |
| Unloading incl. | `unloading_included` | Input (yellow) |  list YesNoUnknown |
| Lead time (days) | `lead_time_days` | Input (yellow) |  |
| Compliance | `compliance` | Input (yellow) |  list Compliance |
| Comments / deviations | `comments` | Input (yellow) |  |

## Quote Comparison

Actual quoted prices and the normalised comparison value are shown separately. Normalised = required qty x rate x (1-disc) x FX / tax divisor + APPROVED adjustments only. The cheapest quotation is never auto-awarded.

| Header | Key | Class | Format / list |
|---|---|---|---|
| Package | `package_id` | Read-only (blue) |  |
| Quotation | `quotation_id` | Read-only (blue) |  |
| Supplier | `supplier` | Read-only (blue) |  |
| Validity | `validity` | Read-only (blue) |  |
| Coverage | `coverage` | Read-only (blue) |  |
| Quoted total (as quoted) | `quoted_total` | Read-only (blue) | #,##0.00;[Red]-#,##0.00 |
| Currency | `currency` | Read-only (blue) |  |
| Approved adjustments (SAR) | `approved_adjustments` | Read-only (blue) | #,##0.00;[Red]-#,##0.00 |
| Normalised comparison value (SAR, pre-tax) | `normalised_total` | Read-only (blue) | #,##0.00;[Red]-#,##0.00 |
| Diff vs lowest like-for-like | `difference_vs_lowest` | Formula (grey, locked) | #,##0.00;[Red]-#,##0.00 / `=IF(OR(I{r}="",K{r}<>"Yes"),"",I{r}-MINIFS($I$6:$I$500,$K$6:$K$500,"Yes"))` |
| Like-for-like | `like_for_like` | Read-only (blue) |  |
| Lead time | `lead_time_days` | Read-only (blue) |  |
| Payment terms | `payment_terms` | Read-only (blue) |  |
| Exclusions | `exclusions` | Read-only (blue) |  |
| Missing items | `missing_items` | Read-only (blue) |  |
| Notes | `notes` | Read-only (blue) |  |

## Clarification Register

Clarifications are raised OPEN. A clarification is only resolved by a human with the client response and supporting evidence; AI suggestions are drafts.

| Header | Key | Class | Format / list |
|---|---|---|---|
| ID | `id` | Read-only (blue) |  |
| Question | `question` | Input (yellow) |  |
| Trade | `trade` | Input (yellow) |  |
| Related BOQ item | `boq_item_key` | Input (yellow) |  |
| Drawing / spec ref | `doc_ref` | Input (yellow) |  |
| Reason | `reason` | Input (yellow) |  |
| Commercial impact | `commercial_impact` | Input (yellow) |  |
| Cost exposure (SAR) | `cost_exposure` | Input (yellow) | #,##0.00;[Red]-#,##0.00 |
| Proposed wording | `proposed_wording` | Input (yellow) |  |
| Owner | `owner` | Input (yellow) |  |
| Status | `status` | Read-only (blue) |  |
| Client response | `client_response` | Read-only (blue) |  |
| Resolution date | `resolution_date` | Read-only (blue) | yyyy-mm-dd |

## Inclusions and Exclusions

Every material requirement must be priced, explicitly excluded/qualified (approved), covered by an approved allowance, or marked unresolved. Entries import as Draft and need approval.

| Header | Key | Class | Format / list |
|---|---|---|---|
| ID | `id` | Read-only (blue) |  |
| Kind | `kind` | Input (yellow) |  list ScopeKind |
| Description | `description` | Input (yellow) |  |
| Trade | `trade` | Input (yellow) |  |
| BOQ item | `boq_item_key` | Input (yellow) |  |
| Cost code | `cost_code` | Input (yellow) |  list costcodes |
| Rationale | `rationale` | Input (yellow) |  |
| Status | `status` | Read-only (blue) |  |

## Risk Register

Risks and their cost exposure. Quantified risk allowances are priced through the approved commercial policy, not here.

| Header | Key | Class | Format / list |
|---|---|---|---|
| ID | `id` | Read-only (blue) |  |
| Title | `title` | Input (yellow) |  |
| Description | `description` | Input (yellow) |  |
| Trade | `trade` | Input (yellow) |  |
| Probability | `probability` | Input (yellow) |  |
| Impact | `impact` | Input (yellow) |  |
| Cost exposure (SAR) | `cost_exposure` | Input (yellow) | #,##0.00;[Red]-#,##0.00 |
| Mitigation | `mitigation` | Input (yellow) |  |
| Owner | `owner` | Input (yellow) |  |
| Status | `status` | Read-only (blue) |  |

## Reconciliation

Latest reconciliation run. Critical findings block final approval and cannot be excepted. Accept exceptions in the application (documented reason, role-checked).

| Header | Key | Class | Format / list |
|---|---|---|---|
| Severity | `severity` | Read-only (blue) |  |
| Rule | `rule_code` | Read-only (blue) |  |
| Title | `title` | Read-only (blue) |  |
| Detail | `detail` | Read-only (blue) |  |
| Entity | `entity` | Read-only (blue) |  |
| Financial impact (SAR) | `financial_impact` | Read-only (blue) | #,##0.00;[Red]-#,##0.00 |
| Owner | `owner` | Read-only (blue) |  |
| Status | `status` | Read-only (blue) |  |
| Exception reason | `exception_reason` | Read-only (blue) |  |

## Approval Log

Immutable record of human approval decisions (reviewer, role, timestamp, previous and approved value, evidence, comments).

| Header | Key | Class | Format / list |
|---|---|---|---|
| Timestamp (UTC) | `ts` | Read-only (blue) |  |
| Entity type | `entity_type` | Read-only (blue) |  |
| Entity ID | `entity_id` | Read-only (blue) |  |
| Version | `version` | Read-only (blue) |  |
| Reviewer | `reviewer` | Read-only (blue) |  |
| Role | `reviewer_role` | Read-only (blue) |  |
| Action | `action` | Read-only (blue) |  |
| Previous value | `previous_value` | Read-only (blue) |  |
| Approved value / decision | `approved_value` | Read-only (blue) |  |
| Evidence | `evidence` | Read-only (blue) |  |
| Comments | `comments` | Read-only (blue) |  |
| Override reason | `override_reason` | Read-only (blue) |  |

## Source Register

Provenance for public data: source, URL, dates, licence/reuse conditions, extraction method, limitations and confidence. Failed or blocked access is recorded honestly.

| Header | Key | Class | Format / list |
|---|---|---|---|
| Source ID | `source_id` | Read-only (blue) |  |
| Name | `name` | Read-only (blue) |  |
| Organisation | `organisation` | Read-only (blue) |  |
| URL | `url` | Read-only (blue) |  |
| Type | `type` | Read-only (blue) |  |
| Date accessed | `date_accessed` | Read-only (blue) |  |
| Publication date | `publication_date` | Read-only (blue) |  |
| Geography | `geographic_relevance` | Read-only (blue) |  |
| Currency | `currency` | Read-only (blue) |  |
| Unit / price basis | `unit_price_basis` | Read-only (blue) |  |
| Trades | `applicable_trades` | Read-only (blue) |  |
| Licence / reuse | `licence_reuse_conditions` | Read-only (blue) |  |
| Extraction method | `extraction_method` | Read-only (blue) |  |
| Access status | `access_status` | Read-only (blue) |  |
| Limitations | `limitations` | Read-only (blue) |  |
| Confidence | `confidence` | Read-only (blue) |  |
| Data collected | `data_collected` | Read-only (blue) |  |
