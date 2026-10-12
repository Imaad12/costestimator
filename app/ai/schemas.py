"""Strict output schemas for AI tasks. `extra='forbid'`: any additional key (e.g. an injected "approved": true) invalidates the output."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


Confidence = Literal["High", "Medium", "Low"]


class MappingSuggestion(_Strict):
    item_key: str
    assembly_code: str
    confidence: Confidence
    rationale: str = Field(max_length=500)
    source_refs: list[str] = Field(default_factory=list)


class MappingSuggestions(_Strict):
    suggestions: list[MappingSuggestion]


class ExtractedQuoteLine(_Strict):
    description: str
    specification: str | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_rate: float | None = None
    discount_pct: float | None = None
    lead_time_days: float | None = None
    delivery_included: Literal["Yes", "No", "Unknown"] = "Unknown"
    evidence_quote: str = Field(description="Verbatim text from the document supporting this line", max_length=600)


class QuoteExtraction(_Strict):
    supplier_name: str | None = None
    reference: str | None = None
    quote_date: str | None = None
    valid_until: str | None = None
    currency: str | None = None
    tax_treatment: Literal["excl", "incl", "exempt"] | None = None
    tax_rate_pct: float | None = None
    payment_terms: str | None = None
    exclusions: str | None = None
    deviations: str | None = None
    lines: list[ExtractedQuoteLine]
    confidence: Confidence
    uncertainties: list[str] = Field(default_factory=list)


class ClarificationDraft(_Strict):
    question: str
    trade: str | None = None
    boq_item_key: str | None = None
    reason: str
    proposed_wording: str | None = None
    confidence: Confidence
    source_refs: list[str] = Field(default_factory=list)


class ClarificationDrafts(_Strict):
    drafts: list[ClarificationDraft]


class ScopeGap(_Strict):
    description: str
    kind: Literal["omission", "contradiction", "ambiguity"]
    related_items: list[str] = Field(default_factory=list)
    confidence: Confidence
    source_refs: list[str] = Field(default_factory=list)


class ScopeGaps(_Strict):
    gaps: list[ScopeGap]


class RFQEmailDraft(_Strict):
    subject: str
    body: str


class ExclusionSummary(_Strict):
    exclusions: list[str]
    deviations: list[str]
    confidence: Confidence


SCHEMAS = {
    "mapping": MappingSuggestions, "quote_extraction": QuoteExtraction, "clarifications": ClarificationDrafts,
    "scope_gaps": ScopeGaps, "rfq_email": RFQEmailDraft, "exclusion_summary": ExclusionSummary,
}
