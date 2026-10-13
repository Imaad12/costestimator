"""Post-award control: variations (change orders) priced from approved rates and approved by a Commercial Approver, contract-value status, and earned-value
reporting from human-entered task progress, the programme and recorded actuals. Forecasts are analyses; approvals are human."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from ..approvals import engine as approvals
from ..core.errors import Conflict, NotFound, ValidationFailed
from ..core.money import ONE, ZERO, D, D_opt, quantize, to_text
from ..core.timeutil import now_iso, parse_date, today
from ..core.units import registry
from ..database import Database, rows_to_dicts
from ..estimators import evm, programme as prog_engine
from ..estimators.rate_resolution import resolve_rate
from ..models.actor import Actor
from . import audit, governed, landed, programme, projects
from . import rates as rate_service

ENTITY = "variation"


# ------------------------------------------------------------------------------------------------ variations
def create_variation(db: Database, actor: Actor, project_id: str, title: str, *, description: str = "", instructed_by: str | None = None,
                     instruction_ref: str | None = None, time_days=None) -> str:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    if not (title or "").strip():
        raise ValidationFailed("A variation needs a title.")
    td = D_opt(time_days)
    n = (db.scalar("SELECT COUNT(*) FROM variations WHERE project_id=?", (project_id,)) or 0) + 1
    vid = f"VO-{project_id}-{n:03d}"
    db.insert("variations", dict(id=vid, project_id=project_id, title=title.strip(), description=description, instructed_by=instructed_by, instruction_ref=instruction_ref,
                                 time_days=to_text(td), status="Draft", created_by=actor.username, created_at=now_iso()))
    audit.log(db, actor, ENTITY, vid, "create", after={"title": title}, project_id=project_id)
    return vid


def _var(db: Database, vid: str) -> dict:
    v = db.one("SELECT * FROM variations WHERE id=?", (vid,))
    if not v:
        raise NotFound(f"Variation {vid} not found.")
    return dict(v)


def add_line(db: Database, actor: Actor, vid: str, resource_id: str, quantity, *, unit: str | None = None, direction: str = "add", description: str | None = None) -> int:
    approvals.require_author(actor)
    v = _var(db, vid)
    projects.require_active(db, v["project_id"])
    if v["status"] != "Draft":
        raise Conflict("Only a Draft variation can be edited.", code="VARIATION_LOCKED")
    if direction not in ("add", "omit"):
        raise ValidationFailed("direction must be add or omit.")
    q = D_opt(quantity)
    if q is None or q <= 0:
        raise ValidationFailed("quantity must be a positive number (use direction=omit for omissions).", code="VARIATION_QTY")
    res = db.one("SELECT * FROM resources WHERE id=?", (resource_id,))
    if not res:
        raise NotFound(f"Resource {resource_id} not found.")
    if unit and unit != res["unit"] and not registry(db).can_convert(unit, res["unit"]):
        raise ValidationFailed(f"Unit {unit} cannot be converted to {res['unit']}.", code="UNIT_CONVERSION")
    n = (db.scalar("SELECT COUNT(*) FROM variation_lines WHERE variation_id=?", (vid,)) or 0) + 1
    lid = db.insert("variation_lines", dict(variation_id=vid, line_no=n, resource_id=resource_id, description=description or res["description"], direction=direction,
                                            quantity=to_text(q), unit=unit or res["unit"]))
    audit.log(db, actor, ENTITY, vid, "add_line", after={"resource": resource_id, "qty": to_text(q), "dir": direction}, project_id=v["project_id"])
    return lid


def price_variation(db: Database, vid: str, as_of: date | None = None) -> dict:
    """Prices every line from the strictly eligible approved rate on `as_of`; a line with no eligible rate stays unpriced (never zero)."""
    v = _var(db, vid)
    proj = dict(db.one("SELECT * FROM projects WHERE id=?", (v["project_id"],)))
    as_of = as_of or parse_date(proj.get("rate_as_of_date")) or today()
    reg = registry(db)
    fx = landed.fx_lookup(db, as_of, proj["currency"])
    parents = {r["code"]: r["parent_code"] for r in db.all("SELECT code, parent_code FROM regions")}
    lines, total, unpriced = [], ZERO, 0
    for ln in rows_to_dicts(db.all("SELECT * FROM variation_lines WHERE variation_id=? ORDER BY line_no", (vid,))):
        res = dict(db.one("SELECT * FROM resources WHERE id=?", (ln["resource_id"],)))
        rr = resolve_rate(rate_service.rates_for(db, ln["resource_id"]), project_id=v["project_id"], project_region=proj.get("region") or "KSA-ALL", as_of=as_of, region_parents=parents)
        row = dict(line_no=ln["line_no"], resource_id=ln["resource_id"], description=ln["description"], direction=ln["direction"], quantity=ln["quantity"], unit=ln["unit"],
                   rate=None, rate_id=None, amount=None, note=None)
        if not rr.usable:
            unpriced += 1
            row["note"] = f"No eligible rate: {rr.message or rr.eligibility}"
        else:
            rate = rr.rate
            f = ONE if rate["currency"] == proj["currency"] else fx(rate["currency"])
            if f is None:
                unpriced += 1
                row["note"] = f"No approved FX rate {rate['currency']}->{proj['currency']}"
            else:
                q = D(ln["quantity"]) * (reg.factor(ln["unit"], res["unit"]) if ln["unit"] != res["unit"] else ONE)
                price = D(rate["unit_price"]) * f / reg.factor(rate["unit"], res["unit"])
                amt = quantize(q * price, 2) * (1 if ln["direction"] == "add" else -1)
                row.update(rate=price, rate_id=rate["id"], amount=amt, rate_status=rate["status"], is_synthetic=bool(rate.get("is_synthetic")))
                total += amt
        lines.append(row)
    mk = governed.effective(db, v["project_id"], "variation_markup")
    markup = None
    amount = None
    if mk and unpriced == 0 and lines:
        d = mk[0]["data"]
        oh, pr = D(d["overhead_pct"]), D(d["profit_pct"])
        oh_amt = quantize(total * oh / 100, 2)
        pr_amt = quantize((total + oh_amt) * pr / 100, 2)
        markup = dict(code=mk[0]["code"], version=mk[0]["version"], overhead_pct=oh, profit_pct=pr, overhead=oh_amt, profit=pr_amt, clause=d["contract_clause"])
        amount = total + oh_amt + pr_amt
    return dict(variation_id=vid, as_of=as_of.isoformat(), lines=lines, direct_total=total, unpriced_lines=unpriced, markup=markup, amount=amount,
                time_days=v["time_days"], currency=proj["currency"], complete=bool(lines) and unpriced == 0 and markup is not None,
                blockers=([] if lines else ["no lines"]) + ([f"{unpriced} unpriced line(s)"] if unpriced else []) + ([] if mk else ["no approved variation_markup"]))


def submit_variation(db: Database, actor: Actor, vid: str) -> dict:
    approvals.require_author(actor)
    v = _var(db, vid)
    projects.require_active(db, v["project_id"])
    if v["status"] != "Draft":
        raise Conflict("Only a Draft variation can be submitted.")
    pr = price_variation(db, vid)
    if not pr["complete"]:
        raise ValidationFailed(f"Variation cannot be submitted: {'; '.join(pr['blockers'])}.", code="VARIATION_INCOMPLETE")
    db.update("variations", {"status": "Pending Review", "priced_json": json.dumps(_ser(pr)), "amount_pre_markup": to_text(pr["direct_total"]), "amount": to_text(pr["amount"]),
                             "submitted_at": now_iso()}, "id=?", (vid,))
    audit.log(db, actor, ENTITY, vid, "submit", after={"amount": to_text(pr["amount"])}, project_id=v["project_id"])
    return pr


def decide_variation(db: Database, actor: Actor, vid: str, approve: bool, comments: str) -> None:
    v = _var(db, vid)
    action = "approve" if approve else "reject"
    approvals.authorize(actor, ENTITY, action, created_by=v["created_by"])
    if v["status"] != "Pending Review":
        raise Conflict(f"Variation is {v['status']}.")
    if not (comments or "").strip():
        raise ValidationFailed("A decision comment is required.", code="REASON_REQUIRED")
    with db.tx():
        db.update("variations", {"status": "Approved" if approve else "Rejected", "decided_by": actor.username, "decided_at": now_iso(), "decision_comments": comments}, "id=?", (vid,))
        approvals.record(db, actor, ENTITY, vid, action, project_id=v["project_id"], approved_value={"amount": v["amount"], "time_days": v["time_days"]}, comments=comments)


def _ser(o):
    from .analysis import jsonable
    return jsonable(o)


def contract_status(db: Database, project_id: str) -> dict:
    base = governed.effective(db, project_id, "contract_baseline")
    if not base:
        raise ValidationFailed("No approved contract baseline: record the awarded contract sum as a governed 'contract_baseline'.", code="BASELINE_NONE")
    b = base[0]["data"]
    vs = rows_to_dicts(db.all("SELECT * FROM variations WHERE project_id=? ORDER BY id", (project_id,)))
    appr = [v for v in vs if v["status"] == "Approved"]
    pend = [v for v in vs if v["status"] == "Pending Review"]
    s = lambda rows, k: sum((D(r[k]) for r in rows if r[k] is not None), ZERO)
    orig = D(b["contract_sum"])
    return dict(project_id=project_id, baseline=dict(code=base[0]["code"], **b), original_contract_sum=orig, approved_variations=s(appr, "amount"), revised_contract_sum=orig + s(appr, "amount"),
                pending_variations=s(pend, "amount"), exposure_if_pending_approved=orig + s(appr, "amount") + s(pend, "amount"),
                approved_time_days=s(appr, "time_days"), pending_time_days=s(pend, "time_days"), cumulative_effect_pct=(s(appr, "amount") * 100 / orig),
                count={"approved": len(appr), "pending": len(pend), "draft": sum(1 for v in vs if v["status"] == "Draft"), "rejected": sum(1 for v in vs if v["status"] == "Rejected")},
                variations=[dict(id=v["id"], title=v["title"], status=v["status"], amount=v["amount"], time_days=v["time_days"]) for v in vs])


# ------------------------------------------------------------------------------------------------ earned value
def record_progress(db: Database, actor: Actor, project_id: str, task_code: str, as_of: str, pct, basis: str) -> int:
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    if not db.one("SELECT 1 FROM schedule_tasks WHERE project_id=? AND task_code=?", (project_id, task_code)):
        raise NotFound(f"Task {task_code} not found.")
    p = D_opt(pct)
    if p is None or not (0 <= p <= 100):
        raise ValidationFailed("pct must be between 0 and 100.", code="PROGRESS_PCT")
    if parse_date(as_of) is None:
        raise ValidationFailed("as_of must be a date.", code="PROGRESS_DATE")
    if not (basis or "").strip():
        raise ValidationFailed("State how progress was measured (quantities installed, inspection, milestone).", code="PROGRESS_BASIS")
    pid = db.insert("task_progress", dict(project_id=project_id, task_code=task_code, as_of=as_of, pct=to_text(p), basis=basis.strip(), entered_by=actor.username, entered_at=now_iso()))
    audit.log(db, actor, "task_progress", f"{project_id}/{task_code}", "record", after={"pct": to_text(p), "as_of": as_of}, comment=basis, project_id=project_id)
    return pid


def evm_report(db: Database, project_id: str, data_date: str | None = None, *, est=None, version_id: int | None = None) -> dict:
    """Earned-value metrics at `data_date`. BAC = direct cost of the estimate (or of a frozen version's snapshot). Cost not tied to a task is part of BAC but cannot be
    planned/earned and is reported separately. AC = recorded actuals up to the data date."""
    from ..estimators.estimate import compute_estimate
    dd = parse_date(data_date) if data_date else today()
    if dd is None:
        raise ValidationFailed("data_date must be a date.", code="PROGRESS_DATE")
    if version_id:
        from . import snapshots
        snap = snapshots.get_snapshot(db, version_id)
        if snap is None:
            raise ValidationFailed("No snapshot for that version.", code="NO_SNAPSHOT")
        from ..estimators.estimate import compute_estimate_from
        est = compute_estimate_from(snapshots.inputs_from_snapshot(db, snap), snapshots.extras_from_snapshot(snap))
    est = est or compute_estimate(db, project_id)
    cal = programme.calendar_for(db, project_id)
    if cal is None:
        raise ValidationFailed("Earned value needs the programme and an approved project calendar.", code="CALENDAR_REQUIRED")
    rows = rows_to_dicts(db.all("SELECT * FROM schedule_tasks WHERE project_id=? ORDER BY id", (project_id,)))
    if not rows:
        raise ValidationFailed("Earned value needs a programme (tasks).", code="NO_SCHEDULE")
    sch = prog_engine.schedule(programme.to_engine_tasks(rows, cal))
    durs = {c: t.duration for c, t in sch.tasks.items()}
    budget: dict[str, Decimal] = {}
    unscheduled = ZERO
    for l in est.direct.lines:
        if l.amount is None:
            continue
        alloc = programme.assign_lines_to_tasks(rows, l.cost_code, programme._wbs_chain(est.inputs, l.item_key), durs)
        if not alloc:
            unscheduled += l.amount
        for tc, w in alloc:
            budget[tc] = budget.get(tc, ZERO) + l.amount * w
    bac = sum(budget.values(), ZERO) + unscheduled
    offset = Decimal(cal.offset_of(dd)) if dd >= cal.start else ZERO
    pv = ev = ZERO
    task_rows = []
    for tc, b in sorted(budget.items()):
        t = sch.tasks[tc]
        prog = db.one("SELECT pct, as_of FROM task_progress WHERE project_id=? AND task_code=? AND as_of<=? ORDER BY as_of DESC, id DESC LIMIT 1", (project_id, tc, dd.isoformat()))
        pct = D(prog["pct"]) if prog else ZERO
        pp = evm.planned_pct(offset, t.es, t.ef)
        pv += b * pp
        ev += b * pct / 100
        task_rows.append(dict(task_code=tc, budget=b, planned_pct=pp * 100, progress_pct=pct, progress_as_of=prog["as_of"] if prog else None))
    ac = sum((D(r["actual_amount"]) for r in db.all("SELECT actual_amount FROM actual_costs WHERE project_id=? AND actual_amount IS NOT NULL AND (cost_date IS NULL OR cost_date<=?)",
                                                   (project_id, dd.isoformat()))), ZERO)
    m = evm.metrics(bac - unscheduled, pv, ev, ac)
    return dict(project_id=project_id, data_date=dd.isoformat(), metrics=m, bac_total_including_unscheduled=bac, unscheduled_budget=unscheduled, tasks=task_rows,
                no_progress_recorded=[t["task_code"] for t in task_rows if t["progress_as_of"] is None], estimate_state=est.state,
                note="Planned value is linear over each task's working days; earned value uses the progress percentages people entered (with their basis). Actuals are only those "
                     "recorded with a source. Cost not tied to a task is excluded from PV/EV/BAC of the metrics. Forecasts are analyses, not approved figures.")
