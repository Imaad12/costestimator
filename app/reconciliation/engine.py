"""Final reconciliation: cross-checks BOQ, estimate, indirects, quotations, assumptions, scope registers, pricing schedule and offer."""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from ..approvals import engine as approvals
from ..core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from ..core.money import ZERO, D, D_opt, quantize, to_text
from ..core.timeutil import now_iso, parse_date
from ..database import Database, jload, rows_to_dicts
from ..estimators.estimate import EstimateResult, compute_estimate
from ..models.actor import Actor
from ..models.enums import SEVERITY_ORDER, Entity, Status
from ..services import assumptions as assumption_service
from ..services import audit
from .rules import OWNERS, load_rules, rule


@dataclass
class Finding:
    rule_code: str
    detail: str
    entity_type: str | None = None
    entity_id: str | None = None
    impact: Decimal | None = None
    title: str | None = None


RATE_CODES = {"MISSING_RATE", "UNAPPROVED_RATE", "RATE_REGION_MISMATCH", "INDEX_ONLY_NO_PRICE", "RATE_NOT_YET_EFFECTIVE", "FX_MISSING"}
UNIT_CODES = {"UNIT_CONVERSION", "ITEM_UNIT_INCOMPATIBLE", "UNIT_MISSING"}
ASSUMPTION_CODES = {"ASSUMPTION_MISSING", "ASSUMPTION_NOT_APPROVED", "ASSUMPTION_NOT_NUMERIC"}
COVERED_BY_ITEM = {"FACTOR_MISSING", "MAPPING_NOT_APPROVED", "ASSEMBLY_UNAVAILABLE", "CHILD_ASSEMBLY_UNAVAILABLE", "QUANTITY_MISSING",
                   "UNPRICED_ITEM", "NO_PRODUCTIVITY_BASIS", "ALLOWANCE_NOT_APPROVED", "ALLOWANCE_AMOUNT_MISSING"}


def collect_findings(db: Database, project_id: str, est: EstimateResult) -> list[Finding]:
    F: list[Finding] = []
    inp, direct = est.inputs, est.direct
    proj = est.project
    items_by_key = {i["item_key"]: i for i in inp.items}
    # ---- A. item-level pricing completeness
    reasons: dict[str, list[str]] = defaultdict(list)
    for e in direct.exceptions:
        if e.item_key:
            reasons[e.item_key].append(f"{e.code}: {e.message}")
    approved_excl = rows_to_dicts(db.all("SELECT * FROM scope_register WHERE project_id=? AND kind='exclusion' AND status='Approved'", (project_id,)))
    excl_keys = {x["boq_item_key"] for x in approved_excl if x["boq_item_key"]}
    excl_codes = [x["cost_code"] for x in approved_excl if x["cost_code"]]
    for k, ic in direct.items.items():
        it = items_by_key[k]
        if ic.pricing_method == "excluded":
            ok = k in excl_keys or any((ic.cost_code or "").startswith(c) for c in excl_codes)
            if not ok:
                F.append(Finding("EXCLUSION_UNAPPROVED", f"BOQ {k} is marked excluded but no approved exclusion covers it.", "boq_item", k))
            continue
        if not ic.complete:
            why = "; ".join(reasons.get(k, [])[:4]) or "no pricing method"
            kind = "ALLOWANCE_UNAPPROVED" if any("ALLOWANCE_" in r for r in reasons.get(k, [])) else "UNPRICED_ITEM"
            F.append(Finding(kind, f"BOQ {k} '{(ic.description or '')[:60]}' is not fully priced. {why}", "boq_item", k,
                             ic.indicative_exposure or None))
    # ---- B. engine exceptions
    by_res: dict[tuple[str, str], list] = defaultdict(list)
    sysx: dict[tuple[str, str | None], list] = defaultdict(list)
    for e in direct.exceptions:
        if e.code in RATE_CODES and e.resource_id:
            by_res[("MISSING_RATE", e.resource_id)].append(e)
        elif e.code == "EXPIRED_RATE" and e.resource_id:
            by_res[("EXPIRED_RATE", e.resource_id)].append(e)
        elif e.code == "RATE_WARNING" and e.resource_id:
            by_res[("LOW_CONFIDENCE_RATE", e.resource_id)].append(e)
        elif e.code == "DOUBLE_COUNT_SUBCONTRACT":
            F.append(Finding("DOUBLE_COUNT", e.message, "boq_item", e.item_key))
        elif e.code in UNIT_CODES:
            F.append(Finding("UNIT_INCONSISTENT", e.message, "boq_item", e.item_key))
        elif e.code in ASSUMPTION_CODES:
            F.append(Finding("UNAPPROVED_ASSUMPTION", e.message, "assumption", e.assumption_id or "?"))
        elif e.code in COVERED_BY_ITEM or e.code in ("ITEM_MISSING_IN_REVISION",):
            continue
        else:
            sysx[(e.code, e.item_key)].append(e)
    for (rc, rid), es in by_res.items():
        exposure = sum((e.exposure for e in es if e.exposure is not None), ZERO) or None
        msg = es[0].message if len(es) == 1 else f"{es[0].message} (+{len(es) - 1} more line(s))"
        F.append(Finding(rc, msg, "resource", rid, exposure))
    for (code, ik), es in sysx.items():
        F.append(Finding("SYSTEM_EXCEPTION", f"{code}: {es[0].message}", "boq_item" if ik else "estimate", ik or code))
    # ---- C. assumptions
    for aid in sorted(direct.used_assumptions):
        ra = assumption_service.resolve(db, project_id, aid)
        if ra.status != Status.APPROVED.value or not ra.has_value:
            F.append(Finding("UNAPPROVED_ASSUMPTION", f"Assumption {aid} '{ra.name}' used in the estimate has status '{ra.status}'"
                             f"{'' if ra.has_value else ' and no value'}.", "assumption", aid))
    adopted = [a for a in assumption_service.project_assumption_status(db, project_id) if a["status"] != Status.APPROVED.value
               and a["id"] not in direct.used_assumptions]
    if adopted:
        F.append(Finding("UNAPPROVED_ADOPTED_ASSUMPTION", f"{len(adopted)} adopted assumption(s) are not approved: "
                         + ", ".join(a["id"] for a in adopted[:25]) + (" ..." if len(adopted) > 25 else ""), "project", project_id))
    # ---- D. duplicates
    groups: dict[tuple, list[str]] = defaultdict(list)
    for it in inp.items:
        if it["item_type"] == "item":
            groups[(re.sub(r"\W+", " ", (it.get("description") or "").lower()).strip(), it.get("unit"), it.get("quantity"))].append(it["item_key"])
    for (d_, u, q), ks in groups.items():
        if len(ks) > 1 and d_:
            F.append(Finding("POSSIBLE_DUPLICATE_ITEM", f"BOQ items {', '.join(ks)} share the same description, unit and quantity.", "boq_item", ks[0]))
    lines_by: dict[tuple, set] = defaultdict(set)
    for l in direct.lines:
        if l.amount and l.resource_id and l.kind in ("material", "equipment", "subcontract") and l.quantity:
            lines_by[(l.resource_id, quantize(l.quantity, 3))].add(((l.cost_code or "?")[0], l.item_key))
    for (rid, q), s in lines_by.items():
        if len({d for d, _ in s}) > 1:
            F.append(Finding("POSSIBLE_DUPLICATE_ITEM", f"Resource {rid} with identical quantity {q} is costed in several packages: "
                             + ", ".join(sorted(k for _, k in s)), "resource", rid))
    prelim_desc = " ".join((direct.items[k].description or "").lower() for k in direct.items
                           if (direct.items[k].cost_code or "").startswith("A") and direct.items[k].complete)
    for l in est.indirect.lines:
        if l.amount and not l.excluded_reason:
            toks = {t for t in re.findall(r"[a-z]{5,}", f"{l.category} {l.description}".lower()) if t not in ("costs", "project", "general", "site")}
            hit = sorted(t for t in toks if t in prelim_desc)
            if hit:
                F.append(Finding("POSSIBLE_DUPLICATE_INDIRECT", f"Indirect {l.code} '{l.description}' may duplicate priced preliminaries "
                                 f"BOQ items (shared terms: {', '.join(hit)}).", "indirect", l.code, l.amount))
    # ---- E. BOQ hygiene
    for it in inp.items:
        if it["item_type"] != "item":
            continue
        if it["unit_status"] in ("ambiguous", "unknown", "missing"):
            F.append(Finding("UNIT_INCONSISTENT", f"BOQ {it['item_key']}: unit '{it['unit_original']}' is {it['unit_status']}.", "boq_item", it["item_key"]))
        issues = [i for i in jload(it.get("issues_json"), []) if i["level"] == "error" and not i["code"].startswith("UNIT_")]
        if issues:
            F.append(Finding("BOQ_NEEDS_REVIEW", f"BOQ {it['item_key']}: " + "; ".join(i["message"] for i in issues), "boq_item", it["item_key"]))
        if it["status_in_revision"] != "Current":
            F.append(Finding("BOQ_ITEM_MISSING_IN_REVISION", f"BOQ {it['item_key']} is absent from the latest BOQ revision.", "boq_item", it["item_key"]))
        if it["pricing_method"] in ("assembly", "subcontract_lump", "takeoff_resources") and re.search(
                r"provisional\s+sum|\bp\.?c\.?\s+sum|prime\s+cost", it.get("description") or "", re.I):
            F.append(Finding("SUM_NOT_SET_AS_SUM", f"BOQ {it['item_key']} reads like a provisional/PC sum but is priced by {it['pricing_method']}.", "boq_item", it["item_key"]))
    for r in db.all("SELECT import_id, COUNT(*) n FROM boq_rejected_rows WHERE project_id=? GROUP BY import_id", (project_id,)):
        F.append(Finding("BOQ_ROWS_REJECTED", f"{r['n']} row(s) were rejected on BOQ import #{r['import_id']}; confirm none is measured scope.", "boq_import", str(r["import_id"])))
    for ch in db.all("SELECT * FROM change_requests WHERE project_id=? AND status='Pending Review'", (project_id,)):
        F.append(Finding("BOQ_CHANGE_PENDING", f"Pending {ch['field']} change on {ch['entity_id']}: {ch['old_value']} -> {ch['new_value']} ({ch['reason']})",
                         "change_request", str(ch["id"])))
    # ---- F. provisional / synthetic
    if direct.provisional_used:
        keys = sorted({l.item_key for l in direct.lines if l.is_provisional})
        F.append(Finding("PROVISIONAL_INPUTS", f"Provisional (project-approved) inputs are used in {len(keys)} item(s): {', '.join(keys[:15])}.", "project", project_id))
    if direct.synthetic_used:
        F.append(Finding("SYNTHETIC_DEMO" if proj["is_demo"] else "SYNTHETIC_IN_REAL_PROJECT",
                         "Synthetic / DEMO / NOT-A-MARKET-QUOTE rates are used in this estimate.", "project", project_id))
    # ---- G. clarifications
    for c in db.all("SELECT * FROM clarifications WHERE project_id=? AND status IN ('Open','Submitted')", (project_id,)):
        linked = c["boq_item_key"] and c["boq_item_key"] in direct.items and direct.items[c["boq_item_key"]].pricing_method != "excluded"
        F.append(Finding("CLARIFICATION_OPEN" if (linked or c["cost_exposure"]) else "CLARIFICATION_OPEN_GENERAL",
                         f"{c['id']}: {c['question'][:140]}", "clarification", c["id"], D_opt(c["cost_exposure"])))
    # ---- H. commercial / tax / policy / duration / indirect
    codes = {}
    for e in est.exceptions:
        codes.setdefault(e["code"], []).append(e)
    for c in ("TAX_RATE_UNRESOLVED", "TAX_RATE_UNVERIFIED", "TAX_CATEGORY_MISSING"):
        for e in codes.get(c, []):
            F.append(Finding("TAX_UNVERIFIED", e["message"], "tax", c))
    for c in ("POLICY_MISSING", "POLICY_NOT_APPROVED", "POLICY_INVALID", "POLICY_ASSUMPTION_UNRESOLVED", "POLICY_ASSUMPTION_NOT_APPROVED"):
        for e in codes.get(c, []):
            F.append(Finding("POLICY_UNAPPROVED", e["message"], "commercial_policy", c))
    for e in codes.get("DURATION_NOT_APPROVED", [])[:1]:
        F.append(Finding("DURATION_UNAPPROVED", e["message"], "project_duration", project_id))
    for c in ("INDIRECT_NOT_APPROVED", "INDIRECT_AMOUNT_MISSING", "CALENDAR_MISSING"):
        for e in codes.get(c, []):
            F.append(Finding("INDIRECT_UNAPPROVED", e["message"], "indirect", c))
    if not est.indirect.lines:
        F.append(Finding("INDIRECT_UNAPPROVED", "No indirect cost items are defined (add items, or an explicit approved zero).", "indirect", project_id))
    # ---- I. totals and schedule reconciliation
    tol = D(rules_tolerance(db))
    sum_lines = sum((l.amount for l in direct.lines if l.amount is not None), ZERO)
    sum_items = sum((i.direct_cost for i in direct.items.values()), ZERO)
    if sum_lines != direct.direct_cost_total or sum_items != direct.direct_cost_total:
        F.append(Finding("TOTALS_DO_NOT_RECONCILE", f"Direct cost: lines {sum_lines}, items {sum_items}, total {direct.direct_cost_total}.", "estimate", project_id,
                         abs(sum_lines - sum_items)))
    c, sch = est.commercial, est.schedule
    if c and sch:
        ind_in_sch = sum((a["amount"] for a in sch.indirect_allocation if a["amount"] is not None and a.get("allocation") != "separate_line"), ZERO)
        spread = sum((l.allocated_indirect for l in sch.lines), ZERO) + sum((s["amount"] for s in sch.separate_lines), ZERO)
        if sch.complete and abs(spread - est.indirect.total) > tol:
            F.append(Finding("TOTALS_DO_NOT_RECONCILE", f"Indirect total {est.indirect.total} vs allocated to schedule {spread}.", "estimate", project_id,
                             abs(spread - est.indirect.total)))
        var = abs(sch.total_pre_tax - c.net_price)
        tol = tol + sch.max_rounding_variance      # unit-rate rounding is expected; anything beyond is a finding
        if sch.complete and var > tol:
            big = var > max(tol * 100, c.net_price * Decimal("0.01"))
            F.append(Finding("SCHEDULE_RECON_MAJOR" if big else "SCHEDULE_RECON",
                             f"Pricing schedule total {sch.total_pre_tax} differs from commercial net price {c.net_price} by {var} "
                             f"(tolerance {tol}).", "pricing_schedule", project_id, var))
        # independent re-derivation of the commercial chain
        t = c.direct + c.indirect + c.contingency + c.risk + c.escalation
        sell = t * (1 + D(est.policy["markup_pct"]) / 100) if c.method == "markup" else t / (1 - D(est.policy["margin_pct"]) / 100)
        if abs(quantize(sell, est.direct.money_dp) - c.selling_price_pre_discount) > tol:
            F.append(Finding("TOTALS_DO_NOT_RECONCILE", f"Selling price {c.selling_price_pre_discount} does not re-derive ({quantize(sell, 2)}).", "estimate", project_id))
    # ---- J. quotations behind used rates
    for rid in direct.used_rates:
        r = db.one("SELECT r.id, r.quotation_line_id, r.valid_until, q.id qid, q.status, q.valid_until qv FROM resource_rates r "
                   "LEFT JOIN quotation_lines l ON l.id=r.quotation_line_id LEFT JOIN quotations q ON q.id=l.quotation_id WHERE r.id=?", (rid,))
        if r and r["qid"] and (r["status"] == "Expired" or (r["qv"] and parse_date(r["qv"]) < est.as_of)):
            F.append(Finding("QUOTATION_EXPIRED", f"Quotation {r['qid']} behind rate {rid} expired on {r['qv']}.", "quotation", r["qid"]))
    # ---- K. offer letter vs schedule & scope
    offer = db.one("SELECT * FROM offers WHERE project_id=? ORDER BY version_no DESC LIMIT 1", (project_id,))
    inc_all = rows_to_dicts(db.all("SELECT * FROM scope_register WHERE project_id=? AND status='Approved'", (project_id,)))
    for x in inc_all:
        if x["kind"] == "exclusion" and x["boq_item_key"] in direct.items:
            ic = direct.items[x["boq_item_key"]]
            if ic.pricing_method != "excluded" and ic.direct_cost > 0:
                F.append(Finding("PRICED_BUT_EXCLUDED", f"{x['id']} excludes BOQ {x['boq_item_key']} but the item is priced ({ic.direct_cost}).",
                                 "scope_entry", x["id"], ic.direct_cost))
    if offer is None:
        F.append(Finding("OFFER_MISSING", "No letter of offer has been generated for this project.", "offer", project_id))
    elif sch:
        snap = _schedule_snapshot_hash(sch)
        if offer["schedule_hash"] != snap or D_opt(offer["total_pre_tax"]) != sch.total_pre_tax:
            F.append(Finding("OFFER_STALE", f"Offer v{offer['version_no']} total {offer['total_pre_tax']} no longer matches the pricing schedule "
                             f"({sch.total_pre_tax}); regenerate the offer.", "offer", str(offer["version_no"]),
                             abs((D_opt(offer["total_pre_tax"]) or ZERO) - sch.total_pre_tax)))
        offered_ids = {i["id"] for i in jload(offer["inclusions_json"], [])} | {i["id"] for i in jload(offer["exclusions_json"], [])}
        now_ids = {x["id"] for x in inc_all if x["kind"] in ("inclusion", "exclusion", "qualification")}
        if now_ids - offered_ids:
            F.append(Finding("OFFER_STALE", f"Scope register entries not in offer v{offer['version_no']}: {', '.join(sorted(now_ids - offered_ids))}.",
                             "offer", str(offer["version_no"])))
        for i in jload(offer["inclusions_json"], []):
            k, cc = i.get("boq_item_key"), i.get("cost_code")
            targets = [direct.items[k]] if k in direct.items else [ic for ic in direct.items.values() if cc and (ic.cost_code or "").startswith(cc)]
            if (k or cc) and (not targets or not any(t.complete and t.pricing_method != "excluded" for t in targets)):
                F.append(Finding("OFFER_COMMITMENT_NOT_PRICED", f"Offer inclusion {i['id']} '{i['description'][:80]}' is not represented by priced scope.",
                                 "scope_entry", i["id"]))
    # ---- L. version differences & stale workbook
    vers = rows_to_dicts(db.all("SELECT * FROM estimate_versions WHERE project_id=? ORDER BY version_no DESC LIMIT 2", (project_id,)))
    if len(vers) == 2:
        a, b = [jload(v["totals_json"], {}) for v in vers]
        na, nb = D_opt(a.get("commercial_net_price")), D_opt(b.get("commercial_net_price"))
        if na and nb and nb != 0 and abs(na - nb) / abs(nb) > Decimal("0.05"):
            F.append(Finding("VERSION_DIFFERENCE", f"v{vers[0]['version_no']} differs from v{vers[1]['version_no']} by {quantize((na - nb) / nb * 100, 1)}%.",
                             "estimate_version", str(vers[0]["version_no"]), abs(na - nb)))
    wb = db.one("SELECT * FROM exports WHERE project_id=? AND kind='master_workbook' ORDER BY id DESC LIMIT 1", (project_id,))
    if wb and wb["approval_ref"] and wb["approval_ref"] != est.fingerprint:
        F.append(Finding("STALE_WORKBOOK", "The latest exported master workbook was generated from different estimate data; re-export.", "export", str(wb["id"])))
    from .ext_rules import collect_extended          # extended controls (benchmarks, take-off derivations, package interfaces, long-lead, risk, client profile)
    F.extend(collect_extended(db, project_id, est))
    return F


def _schedule_snapshot_hash(sch) -> str:
    payload = "|".join(f"{l.item_key}:{to_text(l.amount)}:{to_text(l.unit_rate)}" for l in sch.lines)
    payload += "|" + "|".join(f"{s['code']}:{to_text(s['price'])}" for s in sch.separate_lines)
    return hashlib.sha256(payload.encode()).hexdigest()


def schedule_hash(sch) -> str:
    return _schedule_snapshot_hash(sch)


def rules_tolerance(db: Database) -> str:
    from ..config import get_settings
    return str(get_settings().reconciliation.get("rounding_tolerance_sar", "1.00"))


def _fingerprint(f: Finding) -> str:
    return hashlib.sha1(f"{f.rule_code}|{f.entity_type}|{f.entity_id}".encode()).hexdigest()[:16]


def run_reconciliation(db: Database, actor: Actor | str, project_id: str, est: EstimateResult | None = None) -> dict:
    est = est or compute_estimate(db, project_id)
    rules = load_rules(db)
    findings = collect_findings(db, project_id, est)
    exceptions = {r["fingerprint"]: r for r in db.all("SELECT * FROM recon_exceptions WHERE project_id=? AND revoked=0", (project_id,))}
    with db.tx():
        run_id = db.insert("recon_runs", dict(project_id=project_id, ts=now_iso(), run_by=getattr(actor, "username", actor),
                                               inputs_hash=est.fingerprint, summary_json={}))
        counts: dict[str, int] = {}
        out = []
        for f in findings:
            r = rule(rules, f.rule_code)
            sev = r["severity"]
            fp = _fingerprint(f)
            exc = exceptions.get(fp) if r["exception_allowed"] else None
            status = "Accepted Exception" if exc else "Open"
            fid = db.insert("recon_findings", dict(run_id=run_id, project_id=project_id, rule_code=f.rule_code, severity=sev,
                                                    title=f.title or r["title"], detail=f.detail, entity_type=f.entity_type,
                                                    entity_id=f.entity_id, fingerprint=fp, financial_impact=to_text(f.impact),
                                                    owner=OWNERS.get(f.rule_code, "Estimator"), status=status,
                                                    exception_id=exc["id"] if exc else None))
            if status == "Open":
                counts[sev] = counts.get(sev, 0) + 1
            out.append(fid)
        summary = {"open_by_severity": counts, "total_findings": len(findings), "blocking": _blocking(rules, counts),
                   "state": est.state, "fingerprint": est.fingerprint}
        db.update("recon_runs", {"summary_json": summary}, "id=?", (run_id,))
    audit.log(db, actor, "reconciliation", run_id, "run", after=summary, project_id=project_id)
    return {"run_id": run_id, **summary}


def _blocking(rules: dict, counts: dict[str, int]) -> bool:
    return any(counts.get(s, 0) for s in rules["blocking_severities"])


def get_run(db: Database, run_id: int | None = None, project_id: str | None = None) -> dict:
    if run_id is None:
        r = db.one("SELECT * FROM recon_runs WHERE project_id=? ORDER BY id DESC LIMIT 1", (project_id,))
    else:
        r = db.one("SELECT * FROM recon_runs WHERE id=?", (run_id,))
    if not r:
        raise NotFound("No reconciliation run found. Run reconciliation first.")
    d = dict(r)
    d["summary"] = jload(d["summary_json"], {})
    fs = rows_to_dicts(db.all("SELECT f.*, e.reason AS exception_reason, e.accepted_by AS exception_by FROM recon_findings f "
                              "LEFT JOIN recon_exceptions e ON e.id=f.exception_id WHERE f.run_id=?", (d["id"],)))
    fs.sort(key=lambda f: (SEVERITY_ORDER.get(f["severity"], 9), f["rule_code"], f["entity_id"] or ""))
    d["findings"] = fs
    return d


def accept_exception(db: Database, actor: Actor, finding_id: int, reason: str) -> None:
    f = db.one("SELECT * FROM recon_findings WHERE id=?", (finding_id,))
    if not f:
        raise NotFound("Finding not found.")
    approvals.authorize(actor, Entity.RECON_EXCEPTION.value, "accept_exception")
    rules = load_rules(db)
    r = rule(rules, f["rule_code"])
    if not r["exception_allowed"] or f["severity"] == "Critical":
        raise PermissionDenied(f"Policy does not permit an exception for {f['rule_code']} ({f['severity']}); resolve it.",
                               code="EXCEPTION_NOT_ALLOWED")
    if f["severity"] == "High" and actor.role not in ("Commercial Approver", "Administrator"):
        raise PermissionDenied("High-severity exceptions need a Commercial Approver.", code="EXCEPTION_ROLE")
    if not reason or len(reason.strip()) < 10:
        raise ValidationFailed("A documented reason (min. 10 characters) is required.", code="REASON_REQUIRED")
    if f["status"] != "Open":
        raise Conflict(f"Finding is {f['status']}.")
    with db.tx():
        eid = db.insert("recon_exceptions", dict(project_id=f["project_id"], rule_code=f["rule_code"], entity_type=f["entity_type"],
                                                  entity_id=f["entity_id"], fingerprint=f["fingerprint"], reason=reason,
                                                  accepted_by=actor.username, accepted_role=actor.role, accepted_at=now_iso()))
        db.update("recon_findings", {"status": "Accepted Exception", "exception_id": eid}, "id=?", (finding_id,))
        approvals.record(db, actor, Entity.RECON_EXCEPTION.value, f"{f['rule_code']}:{f['entity_id']}", "accept_exception",
                         project_id=f["project_id"], approved_value={"severity": f["severity"], "impact": f["financial_impact"]},
                         comments=reason, override_reason=reason)


def revoke_exception(db: Database, actor: Actor, exception_id: int, reason: str) -> None:
    approvals.authorize(actor, Entity.RECON_EXCEPTION.value, "accept_exception")
    db.update("recon_exceptions", {"revoked": 1}, "id=?", (exception_id,))
    audit.log(db, actor, "recon_exception", exception_id, "revoke", comment=reason)


def final_gate(db: Database, actor: Actor | str, project_id: str) -> dict:
    """Fresh reconciliation + blocking decision. Critical (and configured blocking severities) must be resolved/excepted."""
    est = compute_estimate(db, project_id)
    res = run_reconciliation(db, actor, project_id, est)
    run = get_run(db, res["run_id"])
    rules = load_rules(db)
    blockers = [f for f in run["findings"] if f["status"] == "Open" and f["severity"] in rules["blocking_severities"]]
    return {"blocked": bool(blockers), "run_id": res["run_id"], "blockers": blockers, "estimate": est, "fingerprint": est.fingerprint,
            "state": est.state}
