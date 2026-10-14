from __future__ import annotations

import dataclasses
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from ..estimators.estimate import EstimateResult


def ser(o: Any) -> Any:
    """JSON-safe conversion; Decimals become strings so no precision is lost."""
    if isinstance(o, Decimal):
        return format(o, "f")
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if dataclasses.is_dataclass(o) and not isinstance(o, type):
        return {f.name: ser(getattr(o, f.name)) for f in dataclasses.fields(o)}
    if isinstance(o, dict):
        return {("|".join(map(str, k)) if isinstance(k, tuple) else str(k)): ser(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [ser(v) for v in o]
    return o


def _caveats(est) -> list[str]:
    from ..database import get_db
    from ..services import caveats
    return caveats.estimate_caveats(get_db(), est.project["id"], est)


def estimate_summary(est: EstimateResult, include_lines: bool = False) -> dict:
    c, s = est.commercial, est.schedule
    out = {
        "project_id": est.project["id"], "as_of": est.as_of.isoformat(), "state": est.state, "blockers": est.blockers, "fingerprint": est.fingerprint,
        "flags": est.flags, "completeness": est.completeness, "totals": est.totals(), "caveats": _caveats(est),
        "commercial": None if not c else {
            "method": c.method, "method_label": c.method_label, "policy": c.policy_name, "policy_status": c.policy_status, "direct": c.direct,
            "indirect": c.indirect, "pre_contingency_cost": c.pre_contingency_cost, "contingency": c.contingency, "risk": c.risk, "escalation": c.escalation,
            "total_cost": c.total_cost, "selling_price_pre_discount": c.selling_price_pre_discount, "margin_amount": c.margin_amount,
            "effective_markup_pct": c.effective_markup_pct, "effective_margin_pct": c.effective_margin_pct, "discount": c.discount,
            "net_price": c.net_price, "rounding_delta": c.rounding_delta, "tax_by_category": c.tax_by_category, "tax_total": c.tax_total,
            "final_payable": c.final_payable, "trace": c.trace},
        "schedule": None if not s else {"total_pre_tax": s.total_pre_tax, "commercial_net_price": s.commercial_net_price, "rounding_variance": s.rounding_variance,
                                        "max_rounding_variance": s.max_rounding_variance, "complete": s.complete, "lines": s.lines,
                                        "separate_lines": s.separate_lines, "indirect_allocation": s.indirect_allocation},
        "indirect": {"total": est.indirect.total, "lines": est.indirect.lines, "duration_months": est.indirect.duration_months,
                     "duration_status": est.indirect.duration_status},
        "exceptions": est.exceptions,
    }
    if include_lines:
        out["lines"] = est.direct.lines
        out["items"] = est.direct.items
    return ser(out)
