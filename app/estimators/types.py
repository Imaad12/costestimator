"""Plain data structures shared by the calculation engine (no database access)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from ..core.units import UnitRegistry


@dataclass
class AssumptionValue:
    id: str
    value: str | None
    status: str               # effective status
    origin: str = "global_default"
    name: str = ""
    unit: str | None = None
    engine_key: str | None = None

    @property
    def approved(self) -> bool:
        return self.status == "Approved" and self.value not in (None, "")

    @property
    def has_value(self) -> bool:
        return self.value not in (None, "")


@dataclass
class AssemblyDef:
    code: str
    version: int
    unit: str
    description: str
    status: str
    is_synthetic: bool
    lines: list[dict]
    cost_code: str | None = None


@dataclass
class EstimateInputs:
    project: dict
    as_of: date
    items: list[dict]
    assemblies: dict[str, AssemblyDef]          # code -> definition effective for this project
    resources: dict[str, dict]
    rates: dict[str, list[dict]]                # resource_id -> rate records
    assumptions: dict[str, AssumptionValue]     # assumption id -> value
    engine_keys: dict[str, AssumptionValue]     # engine_key -> value
    takeoff: dict[str, list[dict]]              # item_key -> lines
    fx: list[dict]
    units: UnitRegistry
    region_parents: dict[str, str | None] = field(default_factory=dict)
    include_unapproved: bool = False            # preliminary "what-if" view; every use is flagged
    max_depth: int = 8
    params: dict[str, list[dict]] = field(default_factory=dict)      # governed parameters in force, by kind (see param_kinds)
    item_wbs: dict[str, str] = field(default_factory=dict)           # item_key -> WBS code
    wbs_parent: dict[str, str | None] = field(default_factory=dict)  # WBS code -> parent code


@dataclass
class CostLine:
    item_key: str
    assembly_code: str | None
    assembly_version: int | None
    path: str
    line_ref: str
    kind: str                                    # material / labour / plant / equipment / subcontract / allowance / plant_mobilisation / other
    resource_id: str | None
    description: str
    quantity: Decimal | None                     # in resource unit (gross of waste)
    unit: str | None
    base_quantity: Decimal | None = None         # before waste
    rate: Decimal | None = None                  # per resource unit, in project currency
    rate_id: int | None = None
    rate_type: str | None = None
    rate_status: str | None = None
    rate_currency: str | None = None
    fx_rate: Decimal | None = None
    eligibility: str = "MISSING"
    amount: Decimal | None = None                # None => unpriced (never silently zero)
    indicative_amount: Decimal | None = None     # non-eligible indicative value (excluded from totals)
    hours: Decimal | None = None
    basis: str = ""
    assumptions: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    is_provisional: bool = False
    is_synthetic: bool = False
    cost_code: str | None = None
    subcontract_includes: dict[str, bool] = field(default_factory=dict)

    @property
    def priced(self) -> bool:
        return self.amount is not None


@dataclass
class EngineException:
    code: str
    severity: str                  # suggested severity (Critical/High/Medium/Low); reconciliation applies policy
    message: str
    item_key: str | None = None
    resource_id: str | None = None
    exposure: Decimal | None = None
    assumption_id: str | None = None
    rate_id: int | None = None


@dataclass
class ItemCost:
    item_key: str
    item_code: str | None
    description: str | None
    unit: str | None
    quantity: Decimal | None
    cost_code: str | None
    pricing_method: str
    direct_cost: Decimal = Decimal(0)
    lines: int = 0
    unpriced_lines: int = 0
    complete: bool = False
    provisional: bool = False
    synthetic: bool = False
    indicative_exposure: Decimal = Decimal(0)
    unknown_exposure_lines: int = 0

    @property
    def unit_cost(self) -> Decimal | None:
        if self.quantity and self.quantity != 0 and self.complete:
            return self.direct_cost / self.quantity
        return None


@dataclass
class DirectCostResult:
    lines: list[CostLine]
    items: dict[str, ItemCost]
    exceptions: list[EngineException]
    direct_cost_total: Decimal
    used_assumptions: set[str]
    used_rates: set[int]
    provisional_used: bool
    synthetic_used: bool
    money_dp: int
    qty_dp: int
    currency: str
    include_unapproved: bool = False

    def by_cost_code(self) -> dict[str, Decimal]:
        out: dict[str, Decimal] = {}
        for it in self.items.values():
            k = it.cost_code or "(unassigned)"
            out[k] = out.get(k, Decimal(0)) + it.direct_cost
        return out

    def by_kind(self) -> dict[str, Decimal]:
        out: dict[str, Decimal] = {}
        for l in self.lines:
            if l.amount is not None:
                out[l.kind] = out.get(l.kind, Decimal(0)) + l.amount
        return out
