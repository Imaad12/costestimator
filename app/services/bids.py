"""Bid evaluation (weighted, evidence-bearing, advisory), long-lead tracking and the package scope / interface matrix with double-count control.
None of these select a supplier or award anything: selection stays the human, approved decision in procurement.selection."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from ..approvals import engine as approvals
from ..core.errors import Conflict, NotFound, ValidationFailed
from ..core.money import ZERO, D, D_opt, to_text
from ..core.timeutil import now_iso, parse_date, today
from ..database import Database, rows_to_dicts
from ..estimators import bid_eval
from ..models.actor import Actor
from . import audit, governed, projects


# ------------------------------------------------------------------------------------------------ evaluation
def _criteria(db: Database, project_id: str, code: str) -> dict:
    r = next((x for x in governed.effective(db, project_id, "evaluation_criteria") if x["code"] == code), None)
    if not r:
        raise NotFound(f"No approved evaluation criteria '{code}'.")
    return r


def _package(db: Database, package_id: str) -> dict:
    p = db.one("SELECT * FROM procurement_packages WHERE id=?", (package_id,))
    if not p:
        raise NotFound(f"Package {package_id} not found.")
    return dict(p)


def record_score(db: Database, actor: Actor, package_id: str, quotation_id: str, criteria_code: str, criterion_id: str, score, evidence: str) -> int:
    approvals.require_author(actor)
    pkg = _package(db, package_id)
    projects.require_active(db, pkg["project_id"])
    q = db.one("SELECT package_id FROM quotations WHERE id=?", (quotation_id,))
    if not q or q["package_id"] != package_id:
        raise ValidationFailed("Quotation does not belong to this package.", code="BID_QUOTE")
    cs = _criteria(db, pkg["project_id"], criteria_code)
    crit = next((c for c in cs["data"]["criteria"] if c["id"] == criterion_id), None)
    if crit is None:
        raise ValidationFailed(f"Criterion '{criterion_id}' is not in criteria set {criteria_code}.", code="BID_CRITERION")
    s = D_opt(score)
    if s is None:
        raise ValidationFailed("score must be a number.", code="BID_SCORE")
    if crit["pass_fail"]:
        if s not in (0, 1):
            raise ValidationFailed("A pass/fail criterion is scored 1 (pass) or 0 (fail).", code="BID_SCORE")
    elif not (0 <= s <= D(cs["data"]["scale_max"])):
        raise ValidationFailed(f"score must be between 0 and {cs['data']['scale_max']}.", code="BID_SCORE")
    if not (evidence or "").strip():
        raise ValidationFailed("Every score needs its evidence (bid section / clarification / reference check).", code="EVIDENCE_REQUIRED")
    sid = db.insert("bid_scores", dict(project_id=pkg["project_id"], package_id=package_id, quotation_id=quotation_id, criteria_code=criteria_code,
                                       criterion_id=criterion_id, score=to_text(s), evidence=evidence.strip(), scored_by=actor.username, scored_at=now_iso()))
    audit.log(db, actor, "bid_score", f"{quotation_id}/{criterion_id}", "score", after={"score": to_text(s)}, comment=evidence, project_id=pkg["project_id"])
    return sid


def evaluation_report(db: Database, package_id: str, criteria_code: str, *, level: dict | None = None) -> dict:
    from ..procurement.leveling import level_package
    pkg = _package(db, package_id)
    cs = _criteria(db, pkg["project_id"], criteria_code)
    level = level or level_package(db, package_id)
    prices = {x["quotation_id"]: x["normalised_total"] for x in level["quotations"]}
    like = {x["quotation_id"]: x["like_for_like"] for x in level["quotations"]}
    rows = rows_to_dicts(db.all("SELECT * FROM bid_scores WHERE package_id=? AND criteria_code=? ORDER BY id", (package_id, criteria_code)))
    scores: dict[str, dict[str, Decimal]] = {}
    who: dict[tuple, str] = {}
    for r in rows:                                                       # latest score per (quotation, criterion) wins; history stays in the table
        scores.setdefault(r["quotation_id"], {})[r["criterion_id"]] = D(r["score"])
        who[(r["quotation_id"], r["criterion_id"])] = f"{r['scored_by']} {r['scored_at'][:10]}: {r['evidence']}"
    res = bid_eval.evaluate(cs["data"], D(cs["data"]["scale_max"]), scores, {q: p for q, p in prices.items()})
    for q, b in res["bids"].items():
        b["like_for_like"] = like.get(q)
        b["evidence"] = {c: who.get((q, c)) for c in b["points"]}
    res.update(package_id=package_id, criteria=dict(code=criteria_code, version=cs["version"], name=cs["data"]["name"], stage=cs["data"]["stage"]),
               advisory="Advisory ranking from the approved criteria and recorded scores. Selection and award are separate human, approved decisions (procurement selection).",
               level_advisory=level.get("advisory"))
    return res


# ------------------------------------------------------------------------------------------------ long lead
def add_long_lead(db: Database, actor: Actor, project_id: str, description: str, lead_time_weeks, required_on_site: str, *, package_id: str | None = None,
                  supplier_id: str | None = None, planned_order_date: str | None = None, vendor_data_due: str | None = None, notes: str | None = None) -> str:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    lw = D_opt(lead_time_weeks)
    if lw is None or lw < 0:
        raise ValidationFailed("lead_time_weeks must be a non-negative number (from the supplier's quotation / confirmation).", code="LEAD_TIME")
    for n, v in (("required_on_site", required_on_site), ("planned_order_date", planned_order_date), ("vendor_data_due", vendor_data_due)):
        if v and parse_date(v) is None:
            raise ValidationFailed(f"{n} must be YYYY-MM-DD.", code="LEAD_DATE")
    if not required_on_site:
        raise ValidationFailed("required_on_site is required.", code="LEAD_DATE")
    n = (db.scalar("SELECT COUNT(*) FROM long_lead_items WHERE project_id=?", (project_id,)) or 0) + 1
    lid = f"LL-{project_id}-{n:03d}"
    db.insert("long_lead_items", dict(id=lid, project_id=project_id, package_id=package_id, description=description, supplier_id=supplier_id, lead_time_weeks=to_text(lw),
                                      required_on_site=required_on_site, planned_order_date=planned_order_date, vendor_data_due=vendor_data_due, notes=notes,
                                      created_by=actor.username, created_at=now_iso()))
    audit.log(db, actor, "long_lead", lid, "create", after={"weeks": to_text(lw), "required": required_on_site}, project_id=project_id)
    return lid


def update_long_lead(db: Database, actor: Actor, lid: str, **changes) -> None:
    approvals.require_author(actor)
    allowed = {"planned_order_date", "actual_order_date", "vendor_data_due", "vendor_data_received", "notes", "lead_time_weeks", "required_on_site"}
    if set(changes) - allowed:
        raise ValidationFailed(f"Not editable: {sorted(set(changes) - allowed)}")
    r = db.one("SELECT * FROM long_lead_items WHERE id=?", (lid,))
    if not r:
        raise NotFound(f"Long-lead item {lid} not found.")
    for k, v in changes.items():
        if k.endswith("_date") or k in ("vendor_data_due", "vendor_data_received", "required_on_site"):
            if v and parse_date(v) is None:
                raise ValidationFailed(f"{k} must be YYYY-MM-DD.", code="LEAD_DATE")
    db.update("long_lead_items", changes, "id=?", (lid,))
    audit.log(db, actor, "long_lead", lid, "update", before={k: r[k] for k in changes}, after=changes, project_id=r["project_id"])


def long_lead_report(db: Database, project_id: str, on: date | None = None) -> dict:
    on = on or today()
    out = []
    for r in rows_to_dicts(db.all("SELECT * FROM long_lead_items WHERE project_id=? ORDER BY id", (project_id,))):
        req = parse_date(r["required_on_site"])
        latest = req - timedelta(days=int(D(r["lead_time_weeks"]) * 7))
        planned, actual = parse_date(r["planned_order_date"]), parse_date(r["actual_order_date"])
        if actual:
            status = "Ordered late" if actual > latest else "Ordered"
            float_days = (latest - actual).days
        elif planned:
            float_days = (latest - planned).days
            status = "At risk: planned order is after the latest order date" if planned > latest else ("Late: order date passed" if on > latest else "On plan")
        else:
            float_days = (latest - on).days
            status = "Late: no order placed" if on > latest else "No order plan"
        due, recv = parse_date(r["vendor_data_due"]), parse_date(r["vendor_data_received"])
        vd = None if not due else ("Received" if recv else ("Overdue" if on > due else "Awaiting"))
        out.append(dict(id=r["id"], description=r["description"], package_id=r["package_id"], supplier_id=r["supplier_id"], lead_time_weeks=r["lead_time_weeks"],
                        required_on_site=r["required_on_site"], latest_order_date=latest.isoformat(), planned_order_date=r["planned_order_date"],
                        actual_order_date=r["actual_order_date"], float_days=float_days, status=status, vendor_data=vd))
    return dict(project_id=project_id, as_of=on.isoformat(), items=out, attention=[x for x in out if x["status"].startswith(("Late", "At risk", "Ordered late")) or x["vendor_data"] == "Overdue"])


# ------------------------------------------------------------------------------------------------ package scope / interface matrix
RESP = ("included", "excluded", "by_others")


def set_scope(db: Database, actor: Actor, project_id: str, package_id: str, ref_type: str, ref: str, responsibility: str, counterpart_package: str | None = None,
              note: str | None = None) -> int:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    if ref_type not in ("boq_item", "cost_prefix"):
        raise ValidationFailed("ref_type must be boq_item or cost_prefix.")
    if responsibility not in RESP:
        raise ValidationFailed(f"responsibility must be one of {RESP}.")
    if not db.one("SELECT 1 FROM procurement_packages WHERE id=? AND project_id=?", (package_id, project_id)):
        raise NotFound(f"Package {package_id} not in project {project_id}.")
    if ref_type == "boq_item" and not db.one("SELECT 1 FROM boq_items WHERE project_id=? AND item_key=? AND item_type='item'", (project_id, ref)):
        raise ValidationFailed(f"BOQ item {ref} not found.", code="SCOPE_REF")
    if ref_type == "cost_prefix" and not db.one("SELECT 1 FROM cost_codes WHERE code LIKE ?", (ref + "%",)):
        raise ValidationFailed(f"Cost prefix {ref} matches no cost code.", code="SCOPE_REF")
    if responsibility == "by_others":
        if not counterpart_package or counterpart_package == package_id or not db.one("SELECT 1 FROM procurement_packages WHERE id=? AND project_id=?", (counterpart_package, project_id)):
            raise ValidationFailed("by_others needs a different, existing counterpart package.", code="SCOPE_COUNTERPART")
    db.execute("INSERT INTO package_scope(project_id,package_id,ref_type,ref,responsibility,counterpart_package,note,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?) "
               "ON CONFLICT(project_id,package_id,ref_type,ref) DO UPDATE SET responsibility=excluded.responsibility, counterpart_package=excluded.counterpart_package, "
               "note=excluded.note, created_by=excluded.created_by, created_at=excluded.created_at",
               (project_id, package_id, ref_type, ref, responsibility, counterpart_package, note, actor.username, now_iso()))
    audit.log(db, actor, "package_scope", f"{package_id}/{ref_type}/{ref}", "set", after={"responsibility": responsibility, "counterpart": counterpart_package}, project_id=project_id)
    return db.scalar("SELECT id FROM package_scope WHERE project_id=? AND package_id=? AND ref_type=? AND ref=?", (project_id, package_id, ref_type, ref))


def interface_report(db: Database, project_id: str) -> dict:
    """Who is responsible for each BOQ item across packages. A direct item entry beats a cost-prefix entry (longest prefix wins among prefixes)."""
    entries = rows_to_dicts(db.all("SELECT * FROM package_scope WHERE project_id=? ORDER BY package_id, ref_type, ref", (project_id,)))
    items = rows_to_dicts(db.all("SELECT item_key, description, cost_code, pricing_method FROM boq_items WHERE project_id=? AND item_type='item' ORDER BY id", (project_id,)))
    findings, matrix = [], []
    if not entries:
        return dict(project_id=project_id, packages=[], matrix=[], findings=[], double_counted=[], clean=True,
                    note="No package scope entries recorded: the interface matrix is not in use, so no gap / double-count check was made.")

    def resp_for(item: dict, pkg: str) -> dict | None:
        direct = [e for e in entries if e["package_id"] == pkg and e["ref_type"] == "boq_item" and e["ref"] == item["item_key"]]
        if direct:
            return direct[0]
        pre = [e for e in entries if e["package_id"] == pkg and e["ref_type"] == "cost_prefix" and (item["cost_code"] or "").startswith(e["ref"])]
        return max(pre, key=lambda e: len(e["ref"])) if pre else None
    pkgs = sorted({e["package_id"] for e in entries})
    for it in items:
        per = {p: resp_for(it, p) for p in pkgs}
        inc = [p for p, e in per.items() if e and e["responsibility"] == "included"]
        matrix.append(dict(item_key=it["item_key"], description=it["description"], cost_code=it["cost_code"], pricing_method=it["pricing_method"],
                           packages={p: (e["responsibility"] + (f" -> {e['counterpart_package']}" if e and e["counterpart_package"] else "") if e else "") for p, e in per.items()}))
        if len(inc) > 1:
            findings.append(dict(severity="Critical", code="PACKAGE_DOUBLE_COUNT", item_key=it["item_key"], packages=inc,
                                 message=f"BOQ {it['item_key']} is included in more than one package ({', '.join(inc)}): it would be bought and priced twice."))
        if not inc and it["pricing_method"] == "subcontract_lump":
            findings.append(dict(severity="High", code="PACKAGE_GAP", item_key=it["item_key"], packages=[], message=f"Subcontract item {it['item_key']} is in no package scope."))
        for p, e in per.items():
            if e and e["responsibility"] == "by_others":
                cp = per.get(e["counterpart_package"]) or resp_for(it, e["counterpart_package"])
                if not cp or cp["responsibility"] != "included":
                    findings.append(dict(severity="High", code="INTERFACE_OPEN", item_key=it["item_key"], packages=[p, e["counterpart_package"]],
                                         message=f"Package {p} leaves BOQ {it['item_key']} to {e['counterpart_package']}, which does not include it: scope falls between packages."))
    return dict(project_id=project_id, packages=pkgs, matrix=matrix, findings=findings, double_counted=sorted({f["item_key"] for f in findings if f["code"] == "PACKAGE_DOUBLE_COUNT"}),
                clean=not findings)
