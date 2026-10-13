"""Approval policy: which role may take which decision on which entity type.

Enforced on the server in `approvals.engine.authorize`; the UI merely mirrors it.
Actions: approve, approve_provisional, reject, request_changes, accept_exception.
"""
from __future__ import annotations

from ..models.enums import Entity, Role

E, P, C, A = Role.ESTIMATOR.value, Role.PROCUREMENT.value, Role.COMMERCIAL.value, Role.ADMIN.value

# entity_type -> action -> roles allowed
POLICY: dict[str, dict[str, set[str]]] = {
    Entity.BOQ_QUANTITY.value: {"approve": {E, C, A}, "reject": {E, C, A}},
    Entity.BOQ_MAPPING.value: {"approve": {E, C, A}, "reject": {E, C, A}},
    Entity.BOQ_UNIT.value: {"approve": {E, C, A}, "reject": {E, C, A}},
    Entity.ASSEMBLY.value: {"approve": {E, C, A}, "reject": {E, C, A}, "request_changes": {E, C, A}},
    Entity.ASSUMPTION.value: {"approve": {E, C, A}, "reject": {E, C, A}},
    Entity.PROJECT_ASSUMPTION.value: {"approve": {E, C, A}, "reject": {E, C, A}},
    # Rates: Estimators may only grant project-scoped PROVISIONAL approval; verified approval needs procurement/commercial.
    Entity.RATE.value: {"approve": {P, C, A}, "approve_provisional": {E, P, C, A}, "reject": {E, P, C, A}},
    Entity.QUOTATION.value: {"approve": {P, C, A}, "reject": {P, C, A}},
    Entity.SUPPLIER_SELECTION.value: {"approve": {P, C, A}, "reject": {P, C, A}},
    Entity.SUPPLIER.value: {"approve": {P, C, A}, "reject": {P, C, A}},
    Entity.FX_RATE.value: {"approve": {P, C, A}, "reject": {P, C, A}},
    Entity.PUBLICATION.value: {"approve": {P, C, A}, "reject": {P, C, A}},
    Entity.RATE_CANDIDATE.value: {"approve": {P, C, A}, "reject": {P, C, A}, "request_changes": {P, C, A}},
    Entity.RESOURCE.value: {"approve": {E, P, C, A}, "reject": {E, P, C, A}},
    Entity.PROJECT_DURATION.value: {"approve": {E, C, A}, "reject": {E, C, A}},
    Entity.INDIRECT.value: {"approve": {E, C, A}, "reject": {E, C, A}},
    Entity.COMMERCIAL_POLICY.value: {"approve": {C, A}, "reject": {C, A}},
    Entity.TAX_CATEGORY.value: {"approve": {C, A}, "reject": {C, A}},
    Entity.EXCLUSION.value: {"approve": {E, C, A}, "reject": {E, C, A}},
    Entity.CLARIFICATION.value: {"approve": {E, C, A}, "reject": {E, C, A}},
    Entity.PRICING_DECISION.value: {"approve": {E, C, A}, "approve_provisional": {E, C, A}, "reject": {E, C, A}},
    Entity.ESTIMATE.value: {"approve": {C, A}, "reject": {C, A}},
    Entity.OFFER.value: {"approve": {C, A}, "reject": {C, A}},
    Entity.TENDER_EXPORT.value: {"approve": {C, A}, "reject": {C, A}},
    # Reconciliation exceptions: roles listed here; per-severity limits are in reconciliation.rules
    Entity.RECON_EXCEPTION.value: {"accept_exception": {E, P, C, A}},
    Entity.AI_SUGGESTION.value: {"approve": {E, P, C, A}, "reject": {E, P, C, A}},
}

# Governed parameters: one entity type per kind ("param:<kind>"), approver roles defined with the kind.
from ..estimators.param_kinds import KINDS as _PARAM_KINDS  # noqa: E402

for _k in _PARAM_KINDS.values():
    POLICY[f"param:{_k.name}"] = {"approve": set(_k.approvers), "reject": set(_k.approvers)}

# Authoring (creating drafts / proposing) permissions by role. Viewers and AI cannot author approved data.
WRITE_ROLES = {E, P, C, A}
ADMIN_ONLY = {"user_admin", "taxonomy_admin", "settings", "backup", "restore"}


def allowed_roles(entity_type: str, action: str) -> set[str]:
    return POLICY.get(entity_type, {}).get(action, set())
