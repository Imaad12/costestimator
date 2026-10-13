"""Construction-method alternatives: side-by-side comparison of the estimate priced with different assemblies (equipment/crew choices) and project duration.
Alternatives are what-if only - nothing is stored on the BOQ and the estimate is unchanged; adopting one means re-mapping the items through the normal approved route."""
from __future__ import annotations

from decimal import Decimal

from ..core.errors import ValidationFailed
from ..core.money import ZERO
from ..database import Database
from ..estimators.context import load_inputs
from ..estimators.estimate import compute_estimate_from, load_extras
from . import governed


def check_alternative(db: Database, clean: dict) -> None:
    for ik, code in clean["item_assemblies"].items():
        if not db.one("SELECT 1 FROM assemblies WHERE code=? AND status='Approved'", (code,)):
            raise ValidationFailed(f"Assembly {code} does not exist or is not approved: an alternative may only use approved assemblies.", code="METHOD_ASSEMBLY")


def _summary(est) -> dict:
    hours = sum((l.hours for l in est.direct.lines if l.kind == "labour" and l.hours is not None), ZERO)
    plant = sum((l.hours for l in est.direct.lines if l.kind == "plant" and l.hours is not None), ZERO)
    c = est.commercial
    return dict(direct_cost=est.direct.direct_cost_total, indirect_cost=est.indirect.total, total_cost=c.total_cost if c else None, net_price=c.net_price if c else None,
                labour_hours=hours, plant_hours=plant, duration_months=est.indirect.duration_months, items_unpriced=est.completeness["items_unpriced"], state=est.state)


def comparison_report(db: Database, project_id: str, *, include_unapproved: bool = False) -> dict:
    alts = governed.effective(db, project_id, "method_alternative", include_unapproved=include_unapproved)
    base_inp = load_inputs(db, project_id, include_unapproved=include_unapproved)
    base_ex = load_extras(db, base_inp)
    base = compute_estimate_from(base_inp, base_ex)
    b = _summary(base)
    rows = []
    keys = {i["item_key"] for i in base_inp.items if i["item_type"] == "item"}
    for a in alts:
        d = a["data"]
        unknown = sorted(set(d["item_assemblies"]) - keys)
        if unknown:
            rows.append(dict(alternative=a["code"], name=d["name"], error=f"unknown BOQ item(s): {unknown}"))
            continue
        inp = load_inputs(db, project_id, include_unapproved=include_unapproved, item_overrides=d["item_assemblies"])
        ex = load_extras(db, inp)
        if d.get("duration_months"):
            ex.duration_rows = ex.duration_rows + [dict(id=10**9, project_id=project_id, months=d["duration_months"], source_type="estimator_input", status="Approved",
                                                        basis_note=f"WHAT-IF duration of method alternative {a['code']}")]
        s = _summary(compute_estimate_from(inp, ex))
        delta = {k: (None if s[k] is None or b[k] is None or not isinstance(s[k], Decimal) else s[k] - b[k]) for k in ("direct_cost", "indirect_cost", "total_cost", "net_price", "labour_hours", "plant_hours")}
        rows.append(dict(alternative=a["code"], version=a["version"], name=d["name"], basis=d["basis"], items=d["item_assemblies"], duration_months_whatif=d.get("duration_months"),
                         summary=s, delta_vs_base=delta, unapproved=bool(a.get("unapproved"))))
    return dict(project_id=project_id, base=b, alternatives=rows,
                note="WHAT-IF comparison. The estimate, the BOQ mapping and the approved duration are unchanged. To adopt an alternative, re-map the items to its assemblies and have the mapping approved.")
