"""Integration points for external data. Nothing here scrapes websites.

Design rule (docs/KSA_DATA_SOURCES.md): prefer official DOWNLOADABLE datasets. An adapter's only job is to turn a file the user
obtained legitimately into the staging format (`imports.datasets`), keeping provenance. Anything an adapter cannot do raises
`NotConfigured` with the exact manual alternative - it never pretends to have fetched data.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..core.errors import AppError


class NotConfigured(AppError):
    status_code = 501
    code = "INTEGRATION_NOT_CONFIGURED"


@dataclass
class AdapterInfo:
    name: str
    source_id: str | None
    description: str
    implemented: bool
    manual_alternative: str


class DatasetAdapter(Protocol):
    info: AdapterInfo

    def stage(self, db, actor, path: Path) -> dict: ...


class LocalFileAdapter:
    """IMPLEMENTED: any CSV/XLSX/JSON rate dataset the user supplies, staged and validated with full provenance."""
    info = AdapterInfo("local-file", None, "Stage a locally supplied rate dataset (CSV/XLSX/JSON).", True, "")

    def stage(self, db, actor, path: Path, source_id: str | None = None) -> dict:
        from ..imports import datasets
        return datasets.stage_rate_dataset(db, actor, Path(path), source_id=source_id)


class _Unavailable:
    implemented = False

    def stage(self, *a, **k):
        raise NotConfigured(f"{self.info.name}: {self.info.description} is NOT implemented. {self.info.manual_alternative}")


class GastatConstructionCostIndex(_Unavailable):
    """NOT IMPLEMENTED (documented gap). The official page was unreachable from the build environment (HTTP 502 / proxy block)."""
    info = AdapterInfo("gastat-cci", "SRC-001", "GASTAT Construction Cost Index (official statistic, an index - never a unit price)", False,
                       "Download the official dataset (or its KAPSARC mirror, SRC-002) manually and stage it with LocalFileAdapter using rate type "
                       "'Official Index or Benchmark'.")


class EtimadAwardedTenders(_Unavailable):
    """NOT IMPLEMENTED. The public listing shows tender metadata, not rates; terms of use were not reviewed."""
    info = AdapterInfo("etimad-awards", "SRC-006", "Etimad awarded-tender metadata", False,
                       "Review the platform terms first. Enter relevant award values manually as 'Historical Actual' only where reuse is permitted.")


class ClaudeDocumentExtraction(_Unavailable):
    """Provided by app.ai.service.ai_extract_quotation when AI is configured; listed here as the documented integration point."""
    info = AdapterInfo("claude-extraction", None, "AI document extraction (optional)", False, "Set KSA_AI_ENABLED=true and ANTHROPIC_API_KEY; output is review-pending.")


REGISTRY = {a.info.name: a for a in (LocalFileAdapter(), GastatConstructionCostIndex(), EtimadAwardedTenders(), ClaudeDocumentExtraction())}
