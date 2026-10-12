"""Controlled vocabularies used across the suite."""
from __future__ import annotations

from enum import Enum


class Status(str, Enum):
    DRAFT = "Draft"
    PENDING = "Pending Review"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    EXPIRED = "Expired"
    SUPERSEDED = "Superseded"
    PROVISIONAL = "Provisional — Approved for This Estimate"
    NOT_APPLICABLE = "Not Applicable"


STATUS_VALUES = [s.value for s in Status]
# Statuses a record may carry and still be consumed by a submission-ready estimate.
ELIGIBLE_STATUSES = {Status.APPROVED.value}
PROVISIONAL_STATUS = Status.PROVISIONAL.value


class RateType(str, Enum):
    VERIFIED_SUPPLIER_QUOTE = "Verified Supplier Quote"
    PUBLISHED_MARKET_PRICE = "Published Market Price"
    OFFICIAL_INDEX = "Official Index or Benchmark"
    HISTORICAL_ACTUAL = "Historical Actual"
    APPROVED_INTERNAL_BENCHMARK = "Approved Internal Benchmark"
    ESTIMATOR_ALLOWANCE = "Estimator-Entered Allowance"
    SYNTHETIC = "Synthetic Demonstration Rate"
    MISSING = "Missing Rate"


RATE_TYPE_VALUES = [r.value for r in RateType]
# An official index / benchmark is NOT a quotation and cannot be used as a direct unit price.
NON_PRICE_RATE_TYPES = {RateType.OFFICIAL_INDEX.value, RateType.MISSING.value}


class ResourceType(str, Enum):
    MATERIAL = "material"
    LABOUR = "labour"
    PLANT = "plant"
    EQUIPMENT = "equipment"
    SUBCONTRACT = "subcontract"


RESOURCE_TYPES = [r.value for r in ResourceType]


class Role(str, Enum):
    ESTIMATOR = "Estimator"
    PROCUREMENT = "Procurement Reviewer"
    COMMERCIAL = "Commercial Approver"
    ADMIN = "Administrator"
    VIEWER = "Viewer"
    AI = "AI Assistant"  # service principal; can never approve


ROLE_VALUES = [r.value for r in Role]


class Confidence(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    UNVERIFIED = "Unverified"


class Severity(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


class PricingMethod(str, Enum):
    ASSEMBLY = "assembly"
    SUBCONTRACT_LUMP = "subcontract_lump"
    TAKEOFF_RESOURCES = "takeoff_resources"
    PROVISIONAL_SUM = "provisional_sum"
    PRIME_COST_SUM = "prime_cost_sum"
    ALLOWANCE = "allowance"
    EXCLUDED = "excluded"
    UNPRICED = "unpriced"


PRICING_METHODS = [p.value for p in PricingMethod]


class EstimateState(str, Enum):
    COMPLETE = "Complete"
    PRELIMINARY = "Preliminary — Incomplete"
    PROVISIONAL = "Complete with Provisional Inputs"


class Entity(str, Enum):
    """Entity types used in approvals / audit records."""
    BOQ_QUANTITY = "boq_quantity"
    BOQ_MAPPING = "boq_mapping"
    BOQ_UNIT = "boq_unit"
    ASSEMBLY = "assembly"
    ASSUMPTION = "assumption"
    PROJECT_ASSUMPTION = "project_assumption"
    RATE = "rate"
    QUOTATION = "quotation"
    SUPPLIER_SELECTION = "supplier_selection"
    PROJECT_DURATION = "project_duration"
    INDIRECT = "indirect"
    COMMERCIAL_POLICY = "commercial_policy"
    EXCLUSION = "exclusion"
    CLARIFICATION = "clarification"
    ESTIMATE = "estimate"
    TENDER_EXPORT = "tender_export"
    RECON_EXCEPTION = "recon_exception"
    PRICING_DECISION = "pricing_decision"
    TAX_CATEGORY = "tax_category"
    FX_RATE = "fx_rate"
    SUPPLIER = "supplier"
    RESOURCE = "resource"
    AI_SUGGESTION = "ai_suggestion"
    PUBLICATION = "publication"
    OFFER = "offer"
    RATE_CANDIDATE = "rate_candidate"
