# Approval workflow

## Roles (local users; permissions checked on the server in `approvals/engine.py`)
| Role | Typical authority |
|---|---|
| Estimator | author data; approve BOQ quantity/unit/mapping changes, assemblies, assumptions & project overrides, indirects, durations, exclusions, clarification resolution, pricing decisions, AI-suggestion acceptance; **provisional** (project-scoped) rate approval; low/medium reconciliation exceptions |
| Procurement Reviewer | approve/reject **rates**, quotations, supplier selections, FX rates, dataset publication, suppliers, adjustments |
| Commercial Approver | commercial policies, tax categories, final estimate, offer, tender export, High-severity exceptions, supplier selections at/above the configured value threshold; plus the Estimator/Procurement authorities |
| Administrator | everything above plus users, taxonomy, company settings, backups |
| Viewer | read only |
| AI Assistant | a service principal with no password, no login, **no authority**: every approval check refuses it, whatever role string it carries |

The matrix is `app/approvals/policy.py`. `KSA_ALLOW_SELF_APPROVAL=false` additionally blocks anyone approving a record they created (Administrators exempt). The supplier-selection value threshold is
`approval_thresholds.supplier_selection_commercial_approver_sar` in `config/settings.toml`.

## Statuses
Draft - Pending Review - Approved - Rejected - Expired - Superseded - Provisional - Approved for This Estimate - Not Applicable.
Only *Approved* (and project-scoped *Provisional*) inputs reach a strict estimate. Approved records cannot be edited, rejected or deleted; a change is a new version or pending revision.

## Approval record (table `approvals`, plus a hash-chained `audit_log` entry)
entity type, entity id, version, reviewer, reviewer role, action (`approve`, `approve_provisional`, `reject`, `accept_exception`), timestamp (UTC), previous value, approved value, evidence, comments, override reason.

## What requires approval
| Decision | Where | Notes |
|---|---|---|
| BOQ quantity/description/unit change | Mapping/BOQ page | re-imports queue *pending* changes; the original quantity text is retained |
| Ambiguous/unknown unit | BOQ page | a concrete canonical unit must be chosen; ambiguity is never normalised silently |
| BOQ->assembly mapping | Mapping page | manual = recorded decision; heuristic/AI = *Suggested* until approved |
| New/modified assembly | Assemblies | validation blocks approval (missing factors, double counts, bad bases) |
| Assumption / project override | Assumptions | override needs a reason |
| Resource rate | Resource page | evidence + price date required; index and missing rates cannot be approved; estimators may only approve *provisionally* for one project with a reason |
| Quotation data | Quotations | Procurement verifies against the supplier document; AI-extracted data requires stated verification |
| Supplier selection | Quotations | not-lowest/not-like-for-like needs a documented reason; threshold role |
| Publication of rates from a quote | Quotations | creates *Pending Review* rates; each needs its own approval |
| Project duration, indirect allocation | Commercials | AI duration needs a reviewer comment |
| Commercial policy, tax category | Commercials | tax needs verification evidence |
| Inclusions/exclusions, clarification resolution | Registers | resolution needs the client response and evidence |
| Allowances / provisional / PC sums | Mapping | start *Pending Review*; approve, approve provisionally, or reject (reason mandatory) |
| Reconciliation exception | Reconciliation | only where the rule permits; reason >= 10 chars; High needs Commercial Approver; Critical never |
| Final estimate version | Reconciliation | blocked by blocking findings, Preliminary state, or changed inputs |
| Offer letter | Reports | must match the pricing schedule hash |
| Tender export | Reports | requires approved version + approved offer + fresh reconciliation; re-checked at export time |

## Final submission gate
`export_submission` produces files stamped **SUBMISSION READY** only if: (1) a Commercial Approver's `tender_export` approval record exists for the approved version; (2) a *fresh* reconciliation run has no open
findings in `blocking_severities` (default Critical + High, configurable in `config/reconciliation_rules.json` or the `recon_rules_override` setting); (3) the estimate fingerprint still equals the approved version's; (4) an approved offer matches the schedule.
Every other output is watermarked PRELIMINARY. The export step runs the gate **again** at export time.

## AI
AI-produced items are `ai_suggestions` with status *Pending Review*, provenance (`ai:<model>` / `heuristic`), confidence and source references. A human accepts or rejects them (`suggestions.accept`), which performs the underlying action *as that human*.
There is no code path from `app/ai` to an approval function (asserted by `tests/approvals/test_ai_boundary.py`).

## Audit trail
`audit_log` rows hash the previous row's hash plus their content (`audit.verify_chain`, `python -m app.cli audit-verify`, Settings page). It detects accidental or naive modification. It is **not tamper-proof**: someone with write access to the SQLite file could rebuild the chain.
