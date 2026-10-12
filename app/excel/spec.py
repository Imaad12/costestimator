"""Declarative workbook structure shared by the master workbook, standalone templates, importer and data dictionary.

Colour legend (also written on every sheet):  yellow = input | grey = calculated by formula | blue = read-only value from the application.
The Python application is the authoritative calculator; formulas are transparency aids and are re-verified on import.
"""
from __future__ import annotations

from dataclasses import dataclass, field

HEADER_ROW = 5          # human headers
KEY_ROW = 4             # machine keys (hidden row) used by the importer
FIRST_ROW = 6
TEMPLATE_ROWS = 300     # pre-formatted rows in blank templates

STATUS_LIST = ["Draft", "Pending Review", "Approved", "Rejected", "Expired", "Superseded",
               "Provisional — Approved for This Estimate", "Not Applicable"]
RATE_TYPES = ["Verified Supplier Quote", "Published Market Price", "Official Index or Benchmark", "Historical Actual",
              "Approved Internal Benchmark", "Estimator-Entered Allowance", "Synthetic Demonstration Rate", "Missing Rate"]
RESOURCE_TYPES = ["material", "labour", "plant", "equipment", "subcontract"]
PRICING_METHODS = ["assembly", "subcontract_lump", "takeoff_resources", "provisional_sum", "prime_cost_sum", "allowance", "excluded", "unpriced"]
LISTS: dict[str, list[str]] = {
    "Status": STATUS_LIST, "RateType": RATE_TYPES, "ResourceType": RESOURCE_TYPES, "PricingMethod": PRICING_METHODS,
    "YesNoUnknown": ["Yes", "No", "Unknown"], "Method": ["markup", "margin"],
    "Base": ["direct", "direct_indirect", "cost_before_escalation"],
    "IndirectMethod": ["fixed", "percent_of_direct", "per_day", "per_week", "per_month", "per_duration_month"],
    "Allocation": ["pro_rata_direct", "separate_line", "direct_trade"],
    "LineType": ["material", "labour", "plant", "equipment", "subcontract", "assembly", "other"],
    "WasteBasis": ["none", "fixed_pct", "assumption"],
    "Productivity": ["paid_hours_per_unit", "productive_hours_per_unit", "output_per_crew_shift"],
    "ScopeKind": ["inclusion", "exclusion", "qualification"],
    "ClarStatus": ["Open", "Submitted", "Resolved", "Withdrawn"], "Severity": ["Critical", "High", "Medium", "Low"],
    "Compliance": ["Compliant", "Non-compliant", "Deviation", "Unassessed"], "Confidence": ["High", "Medium", "Low", "Unverified"],
    "TaxTreatment": ["excl", "incl", "exempt"],
}


@dataclass
class Col:
    key: str
    header: str
    width: int = 16
    kind: str = "input"             # input | calc | ro
    fmt: str | None = None          # number format
    dv: str | None = None           # LISTS key or "units"/"regions"/"costcodes"
    formula: str | None = None      # template with {r} (row) -- kind 'calc'
    desc: str = ""
    wrap: bool = False


@dataclass
class Sheet:
    name: str
    title: str
    instructions: str
    cols: list[Col] = field(default_factory=list)
    importable: bool = False
    totals: dict[str, str] = field(default_factory=dict)   # col key -> "SUM"


SAR = '#,##0.00;[Red]-#,##0.00'
QTY = '#,##0.000'
PCT = '0.00'
DATE = 'yyyy-mm-dd'


def C(key, header, width=16, kind="input", fmt=None, dv=None, formula=None, desc="", wrap=False) -> Col:
    return Col(key, header, width, kind, fmt, dv, formula, desc, wrap)


S: dict[str, Sheet] = {}


def _add(s: Sheet) -> Sheet:
    S[s.name] = s
    return s


_add(Sheet("Trade and Cost Code Mapping", "Trade and Cost Code Mapping",
           "Map each BOQ item to an internal cost code and an approved assembly. Mapping suggestions (heuristic/AI) stay 'Suggested' until a human approves them in the application. Cost-code taxonomy is listed on the right for reference.",
           [C("item_key", "BOQ item key", 14, "ro"), C("item_code", "Client code", 12, "ro"), C("description", "Description", 46, "ro", wrap=True),
            C("trade", "Client trade", 16, "ro"), C("cost_code", "Cost code", 12, "input", dv="costcodes", desc="Internal cost code from the taxonomy"),
            C("assembly_code", "Assembly code", 18, "input", desc="Approved assembly code to price this item"),
            C("mapping_status", "Mapping status", 16, "ro"), C("mapping_source", "Mapping source", 14, "ro"),
            C("pricing_method", "Pricing method", 18, "input", dv="PricingMethod")], importable=True))

_add(Sheet("Pricing Schedule", "Pricing Schedule (client-facing basis)",
           "Tendered unit rates and amounts from the application. Amount = ROUND(quantity x unit rate, 2). 'Engine amount' is the authoritative application value; 'Check' flags any difference (stale or edited formula).",
           [C("item_code", "Item", 12, "ro"), C("description", "Description", 48, "ro", wrap=True), C("unit", "Unit", 8, "ro"),
            C("quantity", "Quantity", 14, "ro", QTY), C("unit_rate", "Unit rate (SAR)", 16, "ro", SAR),
            C("amount", "Amount (SAR)", 18, "calc", SAR, formula='=IF(OR(D{r}="",E{r}=""),"",ROUND(D{r}*E{r},2))'),
            C("engine_amount", "Engine amount", 18, "ro", SAR),
            C("check", "Check", 12, "calc", formula='=IF(OR(F{r}="",G{r}=""),"",IF(ABS(F{r}-G{r})>0.01,"MISMATCH","OK"))'),
            C("status", "Status", 14, "ro"), C("flags", "Flags", 30, "ro", wrap=True)], totals={"amount": "SUM", "engine_amount": "SUM"}))

_add(Sheet("BOQ Import", "BOQ Import (measured quantities)",
           "Quantities are measured by the estimator in the tool of choice and imported here; the application never measures or alters them. Re-import is safe: differences become pending change requests. Required: Description, Unit, Quantity.",
           [C("item_code", "Item", 12), C("description", "Description", 50, wrap=True), C("trade", "Trade", 18), C("unit", "Unit", 8),
            C("quantity", "Quantity", 14, fmt=QTY), C("client_rate", "Client rate", 14, fmt=SAR), C("client_amount", "Client amount", 16, fmt=SAR),
            C("drawing_ref", "Drawing ref", 16), C("spec_ref", "Spec ref", 16), C("cost_code", "Cost code", 12, dv="costcodes"),
            C("revision", "Revision", 10),
            C("source_file", "Source file", 22, "ro"), C("source_sheet", "Source sheet", 14, "ro"), C("source_row", "Source row", 10, "ro"),
            C("quantity_original", "Original qty text", 14, "ro"), C("unit_status", "Unit status", 12, "ro"),
            C("validation_status", "Validation", 14, "ro"), C("issues", "Issues", 40, "ro", wrap=True)], importable=True))

_add(Sheet("Direct Cost Build-Up", "Direct Cost Build-Up",
           "One row per resource line: quantity x rate. Unpriced lines are blank (never zero) and listed with their exception. Amount formula = ROUND(qty x rate, 2); 'Engine amount' is authoritative.",
           [C("item_key", "BOQ item", 12, "ro"), C("assembly", "Assembly", 16, "ro"), C("line_ref", "Line ref", 16, "ro"), C("kind", "Kind", 11, "ro"),
            C("resource_id", "Resource ID", 14, "ro"), C("description", "Description", 40, "ro", wrap=True),
            C("quantity", "Quantity", 14, "ro", QTY), C("unit", "Unit", 7, "ro"), C("rate", "Rate (SAR)", 14, "ro", '#,##0.0000'),
            C("amount", "Amount (SAR)", 16, "calc", SAR, formula='=IF(OR(G{r}="",I{r}=""),"",ROUND(G{r}*I{r},2))'),
            C("engine_amount", "Engine amount", 16, "ro", SAR),
            C("check", "Check", 11, "calc", formula='=IF(OR(J{r}="",K{r}=""),"",IF(ABS(J{r}-K{r})>0.01,"MISMATCH","OK"))'),
            C("rate_type", "Rate type", 24, "ro"), C("rate_status", "Rate status", 18, "ro"), C("eligibility", "Eligibility", 12, "ro"),
            C("basis", "Calculation basis", 60, "ro", wrap=True), C("flags", "Flags", 28, "ro", wrap=True)], totals={"amount": "SUM", "engine_amount": "SUM"}))

_LIB = [C("id", "Resource ID", 14, "ro"), C("cost_code", "Cost code", 10, "input", dv="costcodes"), C("category", "Category", 20),
        C("description", "Description", 46, wrap=True), C("specification", "Specification", 40, wrap=True), C("unit", "Unit", 8, dv="units"),
        C("rate", "Current approved rate", 16, "ro", SAR), C("currency", "Currency", 9, "ro"), C("rate_type", "Rate type", 24, "ro"),
        C("rate_status", "Rate status", 18, "ro"), C("price_date", "Price date", 12, "ro", DATE), C("valid_until", "Valid until", 12, "ro", DATE),
        C("supplier", "Supplier", 18, "ro"), C("evidence", "Source / evidence", 30, "ro", wrap=True), C("confidence", "Confidence", 11, "ro"),
        C("region", "Region", 12, "ro"),
        C("new_rate", "PROPOSED new rate", 16, "input", SAR, desc="Imported as a Draft rate proposal; never auto-approved"),
        C("new_rate_type", "Proposed rate type", 24, "input", dv="RateType"), C("new_currency", "Proposed currency", 10, "input"),
        C("new_price_date", "Proposed price date", 13, "input", DATE), C("new_valid_until", "Proposed valid until", 13, "input", DATE),
        C("new_evidence", "Proposed source / evidence", 34, "input", wrap=True)]
for nm, ttl in (("Labour Library", "Labour Library"), ("Material Library", "Material Library"),
                ("Plant and Equipment Library", "Plant and Equipment Library"), ("Subcontract Library", "Subcontract Library")):
    _add(Sheet(nm, ttl, "Resource definitions with their current APPROVED rate (blue, read-only). Enter a proposed rate in the yellow columns: it is imported as a Draft proposal and needs review/approval in the application. A blank rate means the rate is MISSING - it is never treated as zero.",
               list(_LIB), importable=True))

_add(Sheet("Assembly Library", "Assembly Library (one row per assembly line)",
           "Assemblies are versioned; approved versions are immutable. Edits are imported as a NEW draft version for review. Waste: set ONE basis only (factor already includes waste, or fixed %, or assumption reference). Labour needs an explicit productivity basis.",
           [C("assembly_code", "Assembly code", 18), C("version", "Version", 8, "ro"), C("status", "Status", 16, "ro"), C("description", "Assembly description", 36, wrap=True),
            C("unit", "Unit", 8, dv="units"), C("cost_code", "Cost code", 10, dv="costcodes"), C("line_no", "Line", 6, "ro"),
            C("line_type", "Line type", 12, dv="LineType"), C("resource_id", "Resource ID", 14), C("child_assembly_code", "Nested assembly", 16),
            C("factor", "Factor / output", 12, fmt=QTY), C("factor_unit", "Factor unit", 9, dv="units"), C("factor_includes_waste", "Factor incl. waste (1/0)", 12),
            C("waste_basis", "Waste basis", 12, dv="WasteBasis"), C("waste_value", "Waste %", 9), C("waste_ref", "Waste assumption ID", 16),
            C("productivity_basis", "Productivity basis", 22, dv="Productivity"), C("crew", "Crew (resource:count;...)", 28),
            C("includes_labour", "Sub incl. labour", 9), C("includes_material", "Sub incl. material", 9), C("includes_plant", "Sub incl. plant", 9),
            C("utilisation_basis", "Utilisation basis", 12, dv="WasteBasis"), C("utilisation_value", "Utilisation %", 10), C("utilisation_ref", "Utilisation assumption", 16),
            C("confidence", "Confidence", 10, "ro"), C("source", "Source", 24, "ro")], importable=True))

_add(Sheet("Assumptions Register", "Assumptions Register",
           "Effective value for this project (blue). To propose a project override, enter the value and a reason in the yellow columns; it is imported as 'Pending Review' and never changes the global library.",
           [C("id", "Assumption ID", 14, "ro"), C("family", "Family", 7, "ro"), C("name", "Name", 38, "ro", wrap=True), C("description", "Description", 50, "ro", wrap=True),
            C("applies_to", "Applies to", 10, "ro"), C("value", "Effective value", 14, "ro"), C("unit", "Unit", 8, "ro"), C("status", "Status", 16, "ro"),
            C("origin", "Origin", 14, "ro"), C("engine_key", "Engine key", 24, "ro"), C("confidence", "Confidence", 10, "ro"),
            C("override_value", "PROPOSED project value", 16, "input"), C("override_reason", "Reason for override", 36, "input", wrap=True)], importable=True))

_add(Sheet("Indirect Costs", "Indirect Costs & Project Duration",
           "Fixed, percentage and duration-based costs. Project duration must be approved before duration-based items calculate. Items included in a subcontract quotation are excluded to avoid double counting.",
           [C("code", "Code", 10), C("category", "Category", 22), C("description", "Description", 40, wrap=True), C("method", "Method", 18, dv="IndirectMethod"),
            C("amount", "Rate / amount", 14, fmt=SAR), C("quantity", "Quantity (people/units)", 12), C("allocation_method", "Allocation", 16, dv="Allocation"),
            C("allocation_target", "Alloc. target", 10), C("included_in_subcontract", "Incl. in subcontract (1/0)", 12),
            C("status", "Status", 16, "ro"), C("engine_amount", "Calculated amount", 16, "ro", SAR), C("basis", "Calculation basis", 50, "ro", wrap=True)],
           importable=True, totals={"engine_amount": "SUM"}))

_add(Sheet("Procurement Register", "Procurement Register",
           "Missing, expired, unapproved and low-confidence rates become procurement requirements. RFQs are drafted (never sent) from this register.",
           [C("id", "Item ID", 18, "ro"), C("package_id", "Package", 16, "ro"), C("trade", "Trade", 8, "ro"), C("resource_id", "Resource", 14, "ro"),
            C("description", "Description", 40, "ro", wrap=True), C("specification", "Specification", 36, "ro", wrap=True), C("quantity", "Quantity", 12, "ro", QTY),
            C("unit", "Unit", 7, "ro"), C("delivery_location", "Delivery location", 20), C("required_date", "Required date", 12, fmt=DATE),
            C("preferred_suppliers", "Preferred suppliers", 22), C("reason", "Reason", 34, "ro", wrap=True), C("estimated_exposure", "Indicative exposure (SAR)", 16, "ro", SAR),
            C("rfq_status", "RFQ status", 12, "ro"), C("response_deadline", "Response deadline", 13, fmt=DATE), C("quotation_status", "Quotation status", 12, "ro"),
            C("approval_status", "Approval status", 14, "ro")]))

_add(Sheet("Vendor Directory", "Vendor Directory",
           "No contact detail may be entered without a traceable source and permitted use. Never copy contacts from unverified places. Contacts are optional.",
           [C("id", "Vendor ID", 10, "ro"), C("name", "Name", 30), C("supplier_type", "Type", 14), C("trades", "Trades (cost codes)", 20), C("region", "Region", 12),
            C("contact_name", "Contact", 20), C("contact_email", "Email", 26), C("contact_phone", "Phone", 16),
            C("contact_source", "Contact source (required if contact given)", 34, wrap=True), C("qualification_status", "Qualification", 16, "ro"),
            C("is_synthetic", "Synthetic (1/0)", 10, "ro")], importable=True))

_add(Sheet("Vendor Quotations", "Vendor Quotations (one row per quotation line)",
           "Enter or import supplier quotations. Imported quotations start as Draft; a Procurement Reviewer verifies them against the supplier's document. AI-extracted values must be checked by a human.",
           [C("quotation_id", "Quotation ID", 12), C("supplier_id", "Vendor ID", 10), C("reference", "Supplier ref", 16), C("quote_date", "Quote date", 12, fmt=DATE),
            C("valid_until", "Valid until", 12, fmt=DATE), C("currency", "Currency", 8), C("tax_treatment", "Tax (excl/incl/exempt)", 12, dv="TaxTreatment"),
            C("tax_rate_pct", "Tax rate %", 9), C("payment_terms", "Payment terms", 20), C("status", "Status", 14, "ro"),
            C("line_no", "Line", 6), C("procurement_item_id", "Procurement item", 18), C("description", "Description", 36, wrap=True),
            C("quantity", "Qty", 10, fmt=QTY), C("unit", "Unit", 7), C("unit_rate", "Unit rate", 12, fmt=SAR), C("discount_pct", "Disc %", 7),
            C("extended", "Extended (qty x rate x (1-disc))", 18, "calc", SAR, formula='=IF(OR(N{r}="",P{r}=""),"",N{r}*P{r}*(1-IF(Q{r}="",0,Q{r})/100))'),
            C("delivery_included", "Delivery incl.", 9, dv="YesNoUnknown"), C("unloading_included", "Unloading incl.", 9, dv="YesNoUnknown"),
            C("lead_time_days", "Lead time (days)", 10), C("compliance", "Compliance", 13, dv="Compliance"), C("comments", "Comments / deviations", 30, wrap=True)],
           importable=True, totals={"extended": "SUM"}))

_add(Sheet("Quote Comparison", "Quote Comparison (levelled)",
           "Actual quoted prices and the normalised comparison value are shown separately. Normalised = required qty x rate x (1-disc) x FX / tax divisor + APPROVED adjustments only. The cheapest quotation is never auto-awarded.",
           [C("package_id", "Package", 16, "ro"), C("quotation_id", "Quotation", 10, "ro"), C("supplier", "Supplier", 26, "ro"), C("validity", "Validity", 12, "ro"),
            C("coverage", "Coverage", 10, "ro"), C("quoted_total", "Quoted total (as quoted)", 18, "ro", SAR), C("currency", "Currency", 8, "ro"),
            C("approved_adjustments", "Approved adjustments (SAR)", 16, "ro", SAR), C("normalised_total", "Normalised comparison value (SAR, pre-tax)", 20, "ro", SAR),
            C("difference_vs_lowest", "Diff vs lowest like-for-like", 16, "calc", SAR, formula='=IF(OR(I{r}="",K{r}<>"Yes"),"",I{r}-MINIFS($I$6:$I$500,$K$6:$K$500,"Yes"))'),
            C("like_for_like", "Like-for-like", 10, "ro"), C("lead_time_days", "Lead time", 9, "ro"), C("payment_terms", "Payment terms", 20, "ro"),
            C("exclusions", "Exclusions", 30, "ro", wrap=True), C("missing_items", "Missing items", 26, "ro", wrap=True), C("notes", "Notes", 36, "ro", wrap=True)]))

_add(Sheet("Clarification Register", "Client Clarification Register",
           "Clarifications are raised OPEN. A clarification is only resolved by a human with the client response and supporting evidence; AI suggestions are drafts.",
           [C("id", "ID", 14, "ro"), C("question", "Question", 50, wrap=True), C("trade", "Trade", 10), C("boq_item_key", "Related BOQ item", 14),
            C("doc_ref", "Drawing / spec ref", 18), C("reason", "Reason", 28, wrap=True), C("commercial_impact", "Commercial impact", 26, wrap=True),
            C("cost_exposure", "Cost exposure (SAR)", 14, fmt=SAR), C("proposed_wording", "Proposed wording", 40, wrap=True), C("owner", "Owner", 14),
            C("status", "Status", 12, "ro"), C("client_response", "Client response", 36, "ro", wrap=True), C("resolution_date", "Resolution date", 12, "ro", DATE)], importable=True))

_add(Sheet("Inclusions and Exclusions", "Inclusions, Exclusions & Qualifications",
           "Every material requirement must be priced, explicitly excluded/qualified (approved), covered by an approved allowance, or marked unresolved. Entries import as Draft and need approval.",
           [C("id", "ID", 14, "ro"), C("kind", "Kind", 13, dv="ScopeKind"), C("description", "Description", 60, wrap=True), C("trade", "Trade", 10),
            C("boq_item_key", "BOQ item", 14), C("cost_code", "Cost code", 10, dv="costcodes"), C("rationale", "Rationale", 40, wrap=True),
            C("status", "Status", 16, "ro")], importable=True))

_add(Sheet("Risk Register", "Tender Risk Register",
           "Risks and their cost exposure. Quantified risk allowances are priced through the approved commercial policy, not here.",
           [C("id", "ID", 14, "ro"), C("title", "Title", 36), C("description", "Description", 50, wrap=True), C("trade", "Trade", 10),
            C("probability", "Probability", 11), C("impact", "Impact", 11), C("cost_exposure", "Cost exposure (SAR)", 15, fmt=SAR),
            C("mitigation", "Mitigation", 36, wrap=True), C("owner", "Owner", 14), C("status", "Status", 10, "ro")], importable=True))

_add(Sheet("Reconciliation", "Final Reconciliation Findings",
           "Latest reconciliation run. Critical findings block final approval and cannot be excepted. Accept exceptions in the application (documented reason, role-checked).",
           [C("severity", "Severity", 10, "ro"), C("rule_code", "Rule", 26, "ro"), C("title", "Title", 36, "ro", wrap=True), C("detail", "Detail", 70, "ro", wrap=True),
            C("entity", "Entity", 22, "ro"), C("financial_impact", "Financial impact (SAR)", 16, "ro", SAR), C("owner", "Owner", 18, "ro"),
            C("status", "Status", 18, "ro"), C("exception_reason", "Exception reason", 36, "ro", wrap=True)]))

_add(Sheet("Approval Log", "Approval Log",
           "Immutable record of human approval decisions (reviewer, role, timestamp, previous and approved value, evidence, comments).",
           [C("ts", "Timestamp (UTC)", 22, "ro"), C("entity_type", "Entity type", 18, "ro"), C("entity_id", "Entity ID", 24, "ro"), C("version", "Version", 8, "ro"),
            C("reviewer", "Reviewer", 14, "ro"), C("reviewer_role", "Role", 20, "ro"), C("action", "Action", 18, "ro"), C("previous_value", "Previous value", 30, "ro", wrap=True),
            C("approved_value", "Approved value / decision", 36, "ro", wrap=True), C("evidence", "Evidence", 30, "ro", wrap=True),
            C("comments", "Comments", 36, "ro", wrap=True), C("override_reason", "Override reason", 30, "ro", wrap=True)]))

_add(Sheet("Source Register", "Source Register",
           "Provenance for public data: source, URL, dates, licence/reuse conditions, extraction method, limitations and confidence. Failed or blocked access is recorded honestly.",
           [C("source_id", "Source ID", 10, "ro"), C("name", "Name", 40, "ro", wrap=True), C("organisation", "Organisation", 26, "ro"), C("url", "URL", 44, "ro"),
            C("type", "Type", 18, "ro"), C("date_accessed", "Date accessed", 12, "ro"), C("publication_date", "Publication date", 12, "ro"),
            C("geographic_relevance", "Geography", 18, "ro"), C("currency", "Currency", 8, "ro"), C("unit_price_basis", "Unit / price basis", 22, "ro"),
            C("applicable_trades", "Trades", 18, "ro"), C("licence_reuse_conditions", "Licence / reuse", 30, "ro", wrap=True),
            C("extraction_method", "Extraction method", 22, "ro"), C("access_status", "Access status", 14, "ro"),
            C("limitations", "Limitations", 40, "ro", wrap=True), C("confidence", "Confidence", 10, "ro"), C("data_collected", "Data collected", 30, "ro", wrap=True)]))

# standalone-only column sets (templates not tied to a master sheet)
TAKEOFF_COLS = [C("item_code", "Item", 12), C("description", "Description", 46, wrap=True), C("trade", "Trade", 16), C("unit", "Unit", 8),
                C("quantity", "Quantity", 14, fmt=QTY), C("drawing_ref", "Drawing ref", 16), C("spec_ref", "Spec ref", 16),
                C("measure_note", "Measurement note (e.g. L x W x H, deductions)", 40, wrap=True),
                C("resource_id", "Resource ID (optional: pre-calculated resource qty)", 20), C("resource_quantity", "Resource quantity", 14, fmt=QTY),
                C("resource_unit", "Resource unit", 9, dv="units")]
