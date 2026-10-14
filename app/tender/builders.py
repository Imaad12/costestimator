"""Content builders for the 45 tender documents and the 17 handover documents.

Every figure is read from ONE source: the frozen estimate version (totals / schedule / trace) or the registers in the database. Nothing is typed into a template. Missing inputs
appear as explicit `[[MISSING: ...]]` markers, which turn the document into a BLOCKED one - they are never replaced by an invented value.
"""
from __future__ import annotations

import json
from decimal import Decimal

from ..core.errors import AppError
from ..core.money import D_opt
from ..database import Database, rows_to_dicts
from ..reporting import registry
from ..services import assumptions, estimates, offers, registers, tender, workforce
from .model import Doc, Section, Table, missing

D = Decimal


def fmt(x, dp: int = 2) -> str:
    d = D_opt(x)
    return "-" if d is None else f"{d:,.{dp}f}"


def flat(v):
    if isinstance(v, (dict, list, tuple)):
        s = json.dumps(v, default=str, ensure_ascii=False)
        return s if len(s) < 300 else s[:297] + "..."
    return "" if v is None else str(v)


class Ctx:
    def __init__(self, db: Database, project_id: str, version_id: int, *, issue_date: str, revision: int, readiness: dict | None = None, pack_docs: list | None = None,
                 hypothetical: bool = False):
        self.db, self.pid, self.vid = db, project_id, version_id
        self.issue_date, self.revision, self.readiness, self.pack_docs, self.hypothetical = issue_date, revision, readiness, pack_docs or [], hypothetical
        self.project = dict(db.one("SELECT * FROM projects WHERE id=?", (project_id,)))
        self.v = estimates.get_version(db, version_id)
        self.t = self.v["totals"]
        self.res = self.v["result"]
        self.enq = tender.get_enquiry(db, project_id)
        self.tctx = tender.context(db, project_id)
        self.prog_row = workforce.latest_baseline(db, project_id, approved_only=True) or workforce.latest_baseline(db, project_id)
        self.prog = self.prog_row["result"] if self.prog_row else None
        self._reports: dict = {}
        self.errors: dict = {}

    @property
    def customer(self) -> str:
        n = (self.enq or {}).get("customer_name") or self.project.get("client") or ""
        return n or missing("customer name")

    @property
    def demo(self) -> bool:
        return bool(self.project.get("is_demo"))

    @property
    def synthetic(self) -> bool:
        """True only when the content really is synthetic (fictional customer, synthetic rates in the frozen estimate, synthetic registers) - a demonstration/practice project on real data is NOT synthetic."""
        if (self.enq or {}).get("customer_is_synthetic") or (self.res.get("flags") or {}).get("synthetic"):
            return True
        return bool(self.db.scalar("SELECT 1 FROM tender_documents WHERE project_id=? AND is_synthetic=1 LIMIT 1", (self.pid,))
                    or self.db.scalar("SELECT 1 FROM tender_register_items WHERE project_id=? AND is_synthetic=1 LIMIT 1", (self.pid,)))

    def rep(self, name: str, **params):
        key = (name, tuple(sorted(params.items())))
        if key not in self._reports:
            try:
                self._reports[key] = registry.run_report(self.db, name, self.pid, params)
            except AppError as e:
                self.errors[name] = f"{e.code}: {e}"
                self._reports[key] = None
        return self._reports[key]

    def facts(self) -> dict:
        f = dict(estimate_version=self.v["version_no"], fingerprint=self.v["inputs_hash"][:16], net_price=self.t.get("commercial_net_price"), vat=self.t.get("tax"),
                 payable=self.t.get("final_payable"), schedule_total=self.t.get("selling_price_pre_tax"), direct_cost=self.t.get("direct_cost"), indirect_cost=self.t.get("indirect_cost"), total_cost=self.t.get("total_cost"))
        if self.prog:
            f.update(programme_wd=self.prog["working_days"], programme_cd=self.prog["calendar_days"], programme_start=self.prog["start_date"], programme_finish=self.prog["finish_date"])
        return f


def sec_table(heading, headers, rows, paras=None, caption=""):
    return Section(heading, paras or [], Table(headers, rows, caption))


def report_sections(title: str, rep: dict | None, why_missing: str) -> list[Section]:
    if rep is None:
        return [Section(title, [missing(why_missing)])]
    scal = [[k, flat(v)] for k, v in rep.items() if not isinstance(v, (list, tuple)) or (v and not isinstance(v[0], dict))]
    out = [sec_table(f"{title} - summary", ["Field", "Value"], scal)]
    for k, v in rep.items():
        if isinstance(v, (list, tuple)) and v and isinstance(v[0], dict):
            cols = list(v[0].keys())[:9]
            out.append(sec_table(f"{title} - {k}", cols, [[flat(r.get(c)) for c in cols] for r in v[:300]]))
    return out


def items_table(c: Ctx, register: str, cols: list[str], heading: str, none_text: str) -> list[Section]:
    items = tender.list_items(c.db, c.pid, register)
    if not items:
        return [Section(heading, [missing(none_text)])]
    return [sec_table(heading, ["Key"] + cols + ["Status"], [[i["item_key"]] + [flat(i["data"].get(k)) for k in cols] + [i["status"]] for i in items])]


def queries_section(c: Ctx, registers_: tuple, heading: str) -> list[Section]:
    qs = [q for q in tender.list_queries(c.db, c.pid) if q["register"] in registers_]
    if not qs:
        return [Section(heading, ["No query is registered in this register."])]
    return [sec_table(heading, ["Query ID", "Register", "Question", "Why", "Due", "Status", "Response", "Cost impact (SAR)", "Time impact (d)"],
                      [[q["id"], q["register"], q["question"], q["why"], q["response_due"], q["status"],
                        (q["response_text"] + (" [SYNTHETIC RESPONSE]" if q["response_is_synthetic"] else "")) if q["response_text"] else "", q["cost_impact"], q["time_impact_days"]] for q in qs])]


def _priced_rows(c: Ctx):
    return [[l["item"], l["qty"], l["rate"], l["amount"], l["status"]] for l in (c.res.get("schedule") or [])]


def _lim(c: Ctx, *extra: str) -> list[str]:
    base = ["Quantities are human-measured BOQ quantities; the application does not measure drawings.", f"Figures are taken from frozen estimate version v{c.v['version_no']} (fingerprint {c.v['inputs_hash'][:16]})."]
    if c.synthetic:
        base.append("SYNTHETIC / DEMONSTRATION data: rates, quotations, productivity norms, customer and responses are fictional test inputs, not market evidence.")
    elif c.demo:
        base.append("DEMONSTRATION / PRACTICE project: not a tender and not for submission; any quantity taken from a third-party document is unverified until a person checks it.")
    return base + list(extra)


# ================================================================================================ commercial documents
def d01(c):
    return Doc("D01", "Tender cover letter", [
        Section("Addressee", [f"To: {c.customer}", f"Tender reference: {c.project.get('tender_ref') or missing('tender reference')}",
                              f"Project: {c.project['name']} ({c.pid})", f"Tender deadline: {(c.enq or {}).get('tender_deadline') or missing('tender deadline')}",
                              f"Submission instructions: {(c.enq or {}).get('submission_instructions') or missing('submission instructions')}"]),
        Section("Letter", [f"We submit herewith our tender pack for {c.project['name']}, comprising the documents listed in the attached document register.",
                           f"Offered price (before VAT): SAR {fmt(c.t.get('commercial_net_price'))}; VAT: SAR {fmt(c.t.get('tax'))}; total payable: SAR {fmt(c.t.get('final_payable'))}.",
                           "This letter is a draft prepared by the estimating system. The authorised signatory, signature and company details are entered by the signatory at signing.",
                           "Pack status: see the banner above. This letter makes no statement of approval, technical compliance or submission readiness; the banner above and document D15 state what the application gate verified."])],
               facts=c.facts(), refs=[f"{c.pid}-D06", f"{c.pid}-D33", f"{c.pid}-D45"], sources=[f"estimate version v{c.v['version_no']}"], limitations=_lim(c))


def d02(c):
    p = c.prog
    secs = [Section("Opportunity", [(c.enq or {}).get("brief") or missing("enquiry brief")]),
            Section("Offer in figures", [f"Net price before VAT SAR {fmt(c.t.get('commercial_net_price'))}; VAT SAR {fmt(c.t.get('tax'))}; payable SAR {fmt(c.t.get('final_payable'))}. "
                                         f"Direct cost SAR {fmt(c.t.get('direct_cost'))}; indirect SAR {fmt(c.t.get('indirect_cost'))}; total cost SAR {fmt(c.t.get('total_cost'))}."]),
            Section("Programme", [f"{p['working_days']} working days / {p['calendar_days']} calendar days, {p['start_date']} to {p['finish_date']} ({p['profile']['name']})." if p else missing("programme baseline")]),
            Section("Estimate state", [f"Estimate state: {c.v['state']}. Open material queries: {len(tender.open_material_queries(c.db, c.pid))}."])]
    return Doc("D02", "Executive summary", secs, facts=c.facts(), refs=[f"{c.pid}-D06", f"{c.pid}-D19", f"{c.pid}-D25"], limitations=_lim(c))


def d03(c):
    return Doc("D03", "Bid/no-bid record", items_table(c, "bid_no_bid", ["criterion", "assessment", "evidence"], "Bid / no-bid assessment", "bid/no-bid assessment not recorded"), facts=c.facts(),
               limitations=_lim(c, "The assessment is a person's judgement recorded here; the system does not decide whether to bid."))


def d04(c):
    sc = rows_to_dicts(c.db.all("SELECT id, kind, description, status FROM scope_register WHERE project_id=? ORDER BY id", (c.pid,)))
    trades = rows_to_dicts(c.db.all("SELECT COALESCE(trade,'(none)') AS trade, COUNT(*) AS n FROM boq_items WHERE project_id=? AND item_type='item' GROUP BY trade ORDER BY trade", (c.pid,)))
    return Doc("D04", "Scope of work and scope boundary", [
        Section("Scope summary", [(c.enq or {}).get("scope_summary") or missing("scope summary")]),
        sec_table("BOQ items by trade", ["Trade", "BOQ items"], [[t["trade"], t["n"]] for t in trades]),
        sec_table("Scope register (inclusions, exclusions, assumptions)", ["ID", "Kind", "Description", "Status"], [[s["id"], s["kind"], s["description"], s["status"]] for s in sc] or [["-", "-", "none registered", "-"]])],
               facts=c.facts(), refs=[f"{c.pid}-D09", f"{c.pid}-D33"], limitations=_lim(c))


def d05(c):
    return Doc("D05", "Priced BOQ / pricing schedule", [
        sec_table("Pricing schedule (SAR)", ["Item", "Quantity", "Unit rate", "Amount", "Status"], _priced_rows(c)),
        sec_table("Totals", ["Measure", "SAR"], [["Direct cost", fmt(c.t.get("direct_cost"))], ["Indirect cost", fmt(c.t.get("indirect_cost"))], ["Total cost", fmt(c.t.get("total_cost"))],
                                                  ["Selling price before tax", fmt(c.t.get("selling_price_pre_tax"))], ["Net price", fmt(c.t.get("commercial_net_price"))], ["VAT", fmt(c.t.get("tax"))],
                                                  ["Final payable", fmt(c.t.get("final_payable"))]])],
               facts=c.facts(), refs=[f"{c.pid}-D34", f"{c.pid}-D36"], xlsx=True, limitations=_lim(c, "Unpriced lines are shown as unpriced, never as zero."))


def d06(c):
    o = offers.latest_offer(c.db, c.pid)
    return Doc("D06", "Commercial offer summary", [
        sec_table("Offer", ["Item", "Value"], [["Net price (SAR, before VAT)", fmt(c.t.get("commercial_net_price"))], ["VAT (SAR)", fmt(c.t.get("tax"))], ["Final payable (SAR)", fmt(c.t.get("final_payable"))],
                                              ["Estimate state", c.v["state"]], ["Letter of offer", f"v{o['version_no']} ({o['status']})" if o else missing("letter of offer")]]),
        Section("Basis", ["Commercial price build-up trace from the frozen estimate:"]),
        sec_table("Commercial trace", ["Step", "Amount", "Formula"], [[t["step"], t["amount"], t["formula"]] for t in (c.res.get("trace") or [])])],
               facts=c.facts(), refs=[f"{c.pid}-D05", f"{c.pid}-D12", f"{c.pid}-D14"], limitations=_lim(c))


def d07(c):
    b = c.rep("boe")
    return Doc("D07", "Pricing basis and basis of estimate (BOE)", report_sections("Basis of estimate", b, "BOE facts could not be produced") +
               [Section("Estimate classification", ["The product's internal capability levels 1-5 are NOT AACE estimate classes and are not official classifications of any owner. Estimate class, if any, comes from a company-approved classification scheme only."])],
               facts=c.facts(), refs=[f"{c.pid}-D08", f"{c.pid}-D35"], limitations=_lim(c))


def d08(c):
    ev = assumptions.evidence_report(c.db, c.pid)
    rows = [[r["id"], r["category"], r["name"], r["value"] if r["value"] is not None else "", r["unit"] or "", r["status"], f"v{r['version']}", r["data_class"], "yes" if r["mandatory"] else ""] for r in ev["rows"]]
    paras = [f"Classification counts: {json.dumps({k: v for k, v in ev['by_class'].items() if v})}.",
             "FULLY VERIFIED: yes" if ev["fully_verified"] else "NOT fully verified: " + "; ".join(ev["problems"][:12])]
    return Doc("D08", "Assumptions register", [Section("Status", paras), sec_table("Assumptions", ["ID", "Category", "Assumption", "Value", "Unit", "Status", "Version", "Data class", "Mandatory"], rows)],
               facts=c.facts(), xlsx=True, refs=[f"{c.pid}-D37"], limitations=_lim(c, "An estimate never appears fully verified while a material assumption is missing, synthetic, unverified or pending review."))


def d09(c):
    ex = rows_to_dicts(c.db.all("SELECT id, kind, description, status FROM scope_register WHERE project_id=? AND kind IN ('exclusion','qualification','assumption') ORDER BY id", (c.pid,)))
    dev = tender.list_items(c.db, c.pid, "deviation")
    return Doc("D09", "Exclusions and qualifications", [
        sec_table("Exclusions and qualifications", ["ID", "Kind", "Description", "Status"], [[e["id"], e["kind"], e["description"], e["status"]] for e in ex] or [["-", "-", "none registered", "-"]]),
        sec_table("Technical deviations carried as qualifications", ["Ref", "Deviation", "Justification", "Status"], [[d["item_key"], d["data"].get("deviation"), d["data"].get("justification"), d["status"]] for d in dev] or [["-", "none registered", "", ""]])],
               facts=c.facts(), refs=[f"{c.pid}-D24"], limitations=_lim(c))


def d10(c):
    return Doc("D10", "Commercial clarifications", queries_section(c, ("commercial", "scope_exclusion"), "Commercial clarifications"), facts=c.facts(), xlsx=True, refs=[f"{c.pid}-D25"], limitations=_lim(c, "Queries are drafts until a person releases them; responses shown were entered as received."))


def d11(c):
    rk = registers.list_risks(c.db, c.pid)
    return Doc("D11", "Risk and opportunity register", [
        sec_table("Risks", ["ID", "Title", "Category", "Probability %", "Cost low", "Likely", "High", "Status"],
                  [[r["id"], r["title"], r.get("category"), r.get("prob_pct"), r.get("cost_low"), r.get("cost_likely"), r.get("cost_high"), r.get("status")] for r in rk] or [["-", "none registered", "", "", "", "", "", ""]]),
        Section("Opportunities", ["No opportunity is recorded in the register."] if True else [])], facts=c.facts(), xlsx=True, refs=[f"{c.pid}-D40"], limitations=_lim(c))


def d12(c):
    tx = c.rep("boe")
    cats = sorted({l.get("status") for l in (c.res.get("schedule") or [])})
    return Doc("D12", "Tax and commercial terms summary", [
        sec_table("Tax", ["Item", "Value"], [["VAT amount (SAR)", fmt(c.t.get("tax"))], ["Net price (SAR)", fmt(c.t.get("commercial_net_price"))], ["Final payable (SAR)", fmt(c.t.get("final_payable"))],
                                           ["Tax determination", "from the approved tax categories frozen with the estimate snapshot"]]),
        Section("Note", ["Tax treatment has not been verified by a tax professional unless the approved tax category record says so; confirm with ZATCA guidance before submission."])],
               facts=c.facts(), refs=[f"{c.pid}-D06"], limitations=_lim(c))


def d13(c):
    cf = c.rep("cashflow")
    if cf is None:
        return Doc("D13", "Payment milestones and cash-flow basis", [Section("Cash flow", [missing("approved payment terms (advance, retention, certification lag, bonds)")])], facts=c.facts(), xlsx=True, limitations=_lim(c))
    secs = report_sections("Cash flow", {k: v for k, v in cf.items() if k not in ("rows",)}, "")
    if cf.get("rows"):
        cols = list(cf["rows"][0].keys())
        secs.append(sec_table("Monthly cash position", cols, [[flat(r.get(k)) for k in cols] for r in cf["rows"]]))
    return Doc("D13", "Payment milestones and cash-flow basis", secs, facts={**c.facts(), "cashflow_status": str(cf.get("status"))}, xlsx=True, refs=[f"{c.pid}-D06"],
               limitations=_lim(c, "Cash-flow values use the current approved payment terms and programme; they are not part of the frozen estimate snapshot."))


def d14(c):
    p = c.prog
    o = offers.latest_offer(c.db, c.pid)
    ll = c.rep("long_lead")
    return Doc("D14", "Validity, delivery and programme qualifications", [
        sec_table("Validity and programme", ["Item", "Value"], [["Offer validity", (f"{o.get('validity_days')} days (offer v{o['version_no']})" if o else missing("letter of offer validity"))],
                                                               ["Programme duration", f"{p['working_days']} working days / {p['calendar_days']} calendar days" if p else missing("programme")],
                                                               ["Programme calendar", json.dumps(p["calendar"], default=str) if p else missing("calendar")],
                                                               ["Programme claim", (c.prog.get("claims") if p else "n/a")]]),
        Section("Qualifications", [f"Open material queries at issue: {len(tender.open_material_queries(c.db, c.pid))}.", "Long-lead items and procurement dates are qualifications: see the procurement and long-lead schedule." if ll else "No long-lead items registered."])],
               facts=c.facts(), refs=[f"{c.pid}-D19", f"{c.pid}-D22"], limitations=_lim(c))


def d15(c):
    r = c.readiness or {}
    reasons = r.get("reasons", [])
    return Doc("D15", "Bid approval and submission-readiness record", [
        sec_table("Application gate", ["Item", "Result"], [["Classification", r.get("classification", missing("readiness evaluation"))], ["Production ready", str(r.get("production_ready"))],
                                                            ["Environment", r.get("environment", "")], ["Project is demonstration", str(r.get("project_is_demo"))], ["Synthetic data used", str(r.get("synthetic_data"))]]),
        sec_table("Reasons the pack is not submission-ready", ["#", "Reason"], [[i + 1, x] for i, x in enumerate(reasons)] or [["-", "none"]]),
        sec_table("Approval chain recorded", ["Approval", "By", "Role", "Actor type", "Environment"], [[a.get("label"), a.get("by"), a.get("role"), a.get("actor_type"), a.get("environment")] for a in r.get("chain", [])] or [["none", "", "", "", ""]])],
               facts={**c.facts(), "classification": r.get("classification")}, refs=[f"{c.pid}-D41"], limitations=_lim(c, "This record states what the application gate verified; it is not itself an approval."))


# ================================================================================================ technical documents
def d16(c):
    return Doc("D16", "Technical proposal", [
        Section("Contents", ["This proposal summarises: understanding (D17), methodology (D18), programme (D19), workforce (D20), plant (D21), procurement (D22), compliance (D23/D24), queries (D25), interfaces (D26), quality (D27/D28), HSE (D29), submittals (D30), testing and commissioning (D31) and closeout (D32)."]),
        Section("Programme headline", [f"{c.prog['working_days']} working days / {c.prog['calendar_days']} calendar days, finish {c.prog['finish_date']}; {c.prog['claims'] if 'claims' in c.prog else ''}" if c.prog else missing("programme baseline")]),
        Section("Status", ["This technical proposal is a draft assembled from registers. Specialist engineering, HSE and regulatory content must be completed and approved by competent persons before release. No compliance with any owner or national standard is stated."])],
               facts=c.facts(), refs=[f"{c.pid}-D{n:02d}" for n in range(17, 33)], limitations=_lim(c))


def d17(c):
    docs = tender.list_documents(c.db, c.pid, include_superseded=False)
    return Doc("D17", "Understanding of the project and scope", [
        Section("Enquiry", [(c.enq or {}).get("brief") or missing("enquiry brief")]),
        Section("Scope", [(c.enq or {}).get("scope_summary") or missing("scope summary")]),
        sec_table("Customer documents on which this understanding rests", ["Ref", "Type", "Title", "Rev", "Status", "Content status"], [[d["doc_ref"], d["doc_type"], d["title"], d["revision"], d["status"], d["content_status"]] for d in docs]),
        Section("Limit of interpretation", ["Documents marked 'registered_only' have been registered but not interpreted by the system; statements about their content are limited to what a person has parsed or reviewed."])],
               facts=c.facts(), refs=[f"{c.pid}-D33"], limitations=_lim(c))


def d18(c):
    s = items_table(c, "execution_review", ["topic", "content"], "Execution and constructability review", "constructability / execution review topics")
    acts = workforce.list_activities(c.db, c.pid)
    return Doc("D18", "Execution methodology", s + [sec_table("Execution sequence (work activities)", ["Activity", "Name", "Predecessors", "Crews", "Work fronts", "Norm"],
                                                              [[a["code"], a["name"], a["predecessors"], a["crews"], a["work_fronts"], a["norm_id"]] for a in acts] or [["-", missing("work activities"), "", "", "", ""]])],
               facts=c.facts(), refs=[f"{c.pid}-D19", f"{c.pid}-D20", f"{c.pid}-D29"], limitations=_lim(c, "Methodology topics are entered and reviewed by a competent person; none is generated as engineering advice."))


def d19(c):
    p = c.prog
    if not p:
        return Doc("D19", "Construction programme and milestones", [Section("Programme", [missing("programme baseline (work activities, approved norms, workforce profile, calendar)")])], facts=c.facts(), xlsx=True, limitations=_lim(c))
    acts = [[a["code"], a["name"], a["status"], a["labour_hours"], a["unconstrained_wd"], a["resource_start"], a["resource_finish"], a["resource_delay_wd"], a["total_float_wd"],
             "CRITICAL" if a["critical"] else "", "resource-limited" if a["resource_limited"] else ""] for a in p["activities"]]
    cal = p["calendar"]
    return Doc("D19", "Construction programme and milestones", [
        sec_table("Programme summary", ["Item", "Value"], [["Baseline", f"v{c.prog_row['version_no']} ({c.prog_row['status']})"], ["Workforce profile", f"{p['profile']['name']} ({p['profile']['archetype']})"],
                                                          ["Unconstrained duration (working days)", p["unconstrained_project_wd"]], ["Dependency-constrained", p["dependency_constrained_wd"]], ["Procurement-constrained", p["procurement_constrained_wd"]],
                                                          ["Resource-constrained (baseline)", p["working_days"]], ["Calendar days", p["calendar_days"]], ["Start", p["start_date"]], ["Finish", p["finish_date"]],
                                                          ["Critical path", " > ".join(p["critical_path"])], ["Claim", p.get("claims", "")]]),
        sec_table("Work calendar used (never assumed)", ["Item", "Value"], [["Start date", cal["start"]], ["Working weekdays (0=Mon)", cal["work_weekdays"]], ["Standard hours per day", cal["standard_hours"]],
                                                                          ["Reduced-hour windows", json.dumps(cal["reduced_hours"])], ["Shutdowns", json.dumps(cal["shutdowns"])], ["Holidays", json.dumps(cal["holidays"])],
                                                                          ["Calendar confirmed", cal["confirmed"]]]),
        sec_table("Activities (working-day indices from project start)", ["Code", "Activity", "Status", "Labour hours", "Unconstrained wd", "Start", "Finish", "Resource delay", "Float", "Critical", "Constraint"], acts),
        sec_table("Gaps affecting the programme", ["Activity", "Kind", "Detail"], [[g["code"], g["kind"], g["detail"]] for g in p["gaps"]] or [["-", "none", ""]])],
               facts=c.facts(), xlsx=True, refs=[f"{c.pid}-D20", f"{c.pid}-D37"], limitations=_lim(c, "Durations come from productivity norms; any norm that is not Approved, or any synthetic norm, makes the programme provisional."))


def d20(c):
    p = c.prog
    if not p:
        return Doc("D20", "Workforce and resource-loading plan", [Section("Workforce", [missing("programme baseline / workforce profile")])], facts=c.facts(), xlsx=True, limitations=_lim(c))
    sc = None
    try:
        ids = [r["id"] for r in workforce.list_profiles(c.db) if r["status"] == "Approved" or r["is_synthetic"]]
        sc = workforce.crew_scenarios(c.db, c.pid, ids, allow_provisional=True, allow_unconfirmed_calendar=True) if len(ids) > 1 else None
    except AppError as e:
        c.errors["scenarios"] = str(e)
    wbd = p.get("workers_by_day") or {}
    hist = [[k, v] for k, v in list(wbd.items())[:400]]
    secs = [sec_table("Selected workforce profile", ["Item", "Value"], [["Profile", p["profile"]["name"]], ["Archetype (configurable planning band)", p["profile"]["archetype"]], ["Pool (role: head-count per shift)", json.dumps(p["profile"]["pool"])],
                                                                  ["Indirect staff", json.dumps(p["profile"]["indirect"])], ["Shifts", p["profile"]["shifts"]], ["Productive hours per shift", p["profile"]["productive_hours"]],
                                                                  ["Peak direct manpower", p["peak_workers"]], ["Total labour-hours", p["labour_hours"]]]),
            sec_table("Daily direct manpower (working-day index: workers)", ["Day", "Workers"], hist)]
    if sc:
        secs.append(sec_table("Crew-size scenarios (same activities, norms and calendar)", ["Profile", "Archetype", "Head-count (own direct + indirect)", "Subcontract capacity", "Working days", "Calendar days", "Finish", "Peak workers", "Labour-hours", "Resource-limited", "Cost (planning only)", "Claim"],
                              [[s["profile"], s["archetype"], s["headcount"], s["subcontract_capacity"], s["working_days"] if s["schedulable"] else "NOT SCHEDULABLE", s["calendar_days"] if s["schedulable"] else "-", s["finish"] if s["schedulable"] else "-", s["peak_workers"],
                                s["labour_hours"], ",".join(s["resource_limited"]), s["cost"].get("total") if s["cost"].get("computed") else "not computed", s["claim"]] for s in sc["scenarios"]]))
        secs.append(Section("Reading the scenarios", [sc["note"]]))
    return Doc("D20", "Workforce and resource-loading plan", secs, facts=c.facts(), xlsx=True, refs=[f"{c.pid}-D19"], limitations=_lim(c, "Workforce bands are configurable company planning assumptions, not industry-standard categories."))


def d21(c):
    ph = c.rep("plant_hire")
    plant = [[l["item"], l["amount"]] for l in []]
    return Doc("D21", "Plant and equipment plan", report_sections("Plant hire", ph, "no day-priced plant terms recorded") if ph else [Section("Plant", ["No day-priced plant exists in the estimate, or its terms are missing."])],
               facts=c.facts(), xlsx=True, refs=[f"{c.pid}-D39"], limitations=_lim(c))


def d22(c):
    from ..procurement import leveling
    ll = c.rep("long_lead")
    needs = rows_to_dicts(c.db.all("SELECT id, description, quantity, unit, reason, estimated_exposure, priority, closed FROM procurement_items WHERE project_id=? ORDER BY id", (c.pid,)))
    secs = report_sections("Long-lead items", ll, "no long-lead items") + [sec_table("Procurement needs", ["ID", "Description", "Qty", "Unit", "Reason", "Exposure", "Priority", "Closed"],
                                                                                       [[n["id"], n["description"], n["quantity"], n["unit"], n["reason"], n["estimated_exposure"], n["priority"], n["closed"]] for n in needs] or [["-", "none", "", "", "", "", "", ""]])]
    rf = rows_to_dicts(c.db.all("SELECT id, package_id, supplier_id, subject, status, response_deadline, issued_at FROM rfqs WHERE project_id=? ORDER BY id", (c.pid,)))
    secs.append(sec_table("RFQ register (drafts are prepared here; nothing is sent by the application)", ["RFQ", "Package", "Supplier", "Subject", "Status", "Response deadline", "Issued"], [[r[k] for k in ("id", "package_id", "supplier_id", "subject", "status", "response_deadline", "issued_at")] for r in rf] or [["-", "none", "", "", "", "", ""]]))
    for pkg in rows_to_dicts(c.db.all("SELECT DISTINCT package_id FROM quotations WHERE project_id=? AND package_id IS NOT NULL", (c.pid,))):
        try:
            lv = leveling.level_package(c.db, pkg["package_id"])
        except AppError as e:
            secs.append(Section(f"Quotation comparison {pkg['package_id']}", [missing(f"quotation levelling: {e}")]))
            continue
        secs.append(sec_table(f"Quotation comparison and levelling - package {pkg['package_id']} (SYNTHETIC suppliers in a demonstration; never live quotations)",
                              ["Quotation", "Headline total", "Approved adjustments", "Evaluated total", "Validity", "Valid until", "Coverage", "Non-compliant items", "Delivery/unloading excluded", "Missing items", "Like-for-like"],
                              [[q["quotation_id"], q["quoted_total"], q["approved_adjustments"], q["normalised_total"], q["validity"], q["valid_until"], q["coverage"], q["non_compliant_items"],
                                len(q["delivery_or_unloading_excluded"]), q["missing_items"], q["like_for_like"]] for q in lv["quotations"]],
                              caption=f"Suggested lowest like-for-like quotation: {lv['suggested_lowest_like_for_like']} (advisory: a person selects and approves)"))
    secs += items_table(c, "procurement_strategy", ["package", "approach", "rationale"], "Subcontract and package strategy", "procurement strategy")
    secs += items_table(c, "supplier_qualification", ["supplier", "status", "basis"], "Supplier qualification status", "supplier qualification status")
    return Doc("D22", "Procurement and long-lead schedule", secs, facts=c.facts(), xlsx=True, refs=[f"{c.pid}-D36"], limitations=_lim(c, "Synthetic quotations are test inputs and never live supplier quotations."))


def d23(c):
    return Doc("D23", "Technical compliance matrix", items_table(c, "compliance", ["requirement_ref", "requirement", "response", "evidence"], "Compliance matrix", "compliance responses (no specification parsed)"),
               facts=c.facts(), xlsx=True, refs=[f"{c.pid}-D24"], limitations=_lim(c, "Compliance is stated only where a person recorded a response with evidence; the system states what was loaded and checked, not that a standard is met."))


def d24(c):
    return Doc("D24", "Technical deviations and exceptions", items_table(c, "deviation", ["requirement_ref", "deviation", "justification"], "Deviations", "technical deviations (none recorded)"), facts=c.facts(), xlsx=True, refs=[f"{c.pid}-D23"], limitations=_lim(c))


def d25(c):
    return Doc("D25", "Technical query / RFI register", queries_section(c, tender.QUERY_REGISTERS, "All query registers"), facts=c.facts(), xlsx=True, refs=[f"{c.pid}-D10"],
               limitations=_lim(c, "Detected queries are drafts; none has been sent and no customer response is generated."))


def d26(c):
    im = c.rep("interface_matrix")
    return Doc("D26", "Design and interface matrix", report_sections("Package interfaces", im, "no package scope recorded") + items_table(c, "interface", ["interface", "parties", "responsibility"], "Design interfaces", "design interfaces"),
               facts=c.facts(), xlsx=True, limitations=_lim(c))


def d27(c):
    return Doc("D27", "Quality plan summary", items_table(c, "quality_plan", ["topic", "content"], "Quality plan outline", "quality plan outline content") + items_table(c, "ncr_structure", ["field", "description"], "Nonconformance / corrective-action log structure", "NCR log structure"),
               facts=c.facts(), refs=[f"{c.pid}-D28"], limitations=_lim(c, "Outline only: a quality plan must be written and approved by competent quality personnel."))


def d28(c):
    return Doc("D28", "ITP and inspection register", items_table(c, "itp", ["activity", "inspection_point", "acceptance_criteria", "hold_point"], "ITP register", "ITP content"), facts=c.facts(), xlsx=True, refs=[f"{c.pid}-D27"],
               limitations=_lim(c, "Inspection points and acceptance criteria must come from the specification / quality plan; skeleton rows are placeholders."))


def d29(c):
    return Doc("D29", "HSE execution summary and risk register", items_table(c, "hse_risk", ["hazard", "activity", "control_measures", "residual_risk"], "HSE risk register", "HSE risks") + items_table(c, "permit", ["permit", "authority", "needed_before"], "Permit and access requirements", "permit requirements") +
               items_table(c, "method_statement", ["activity", "scope", "status_note"], "Method statement register", "method statements"), facts=c.facts(), xlsx=True,
               limitations=_lim(c, "Specialist HSE content must be completed and approved by a competent HSE professional."))


def d30(c):
    return Doc("D30", "Material and technical submittal schedule", items_table(c, "submittal_material", ["item", "specification_ref", "required_by"], "Material submittals", "material submittals") + items_table(c, "submittal_shop", ["item", "drawing_ref", "required_by"], "Shop drawing / technical submittals", "shop drawing submittals"),
               facts=c.facts(), xlsx=True, limitations=_lim(c))


def d31(c):
    return Doc("D31", "Testing and commissioning plan", items_table(c, "test_commissioning", ["system", "test", "acceptance", "when"], "Testing and commissioning register", "testing and commissioning content"), facts=c.facts(), xlsx=True, limitations=_lim(c))


def d32(c):
    return Doc("D32", "Handover and closeout plan", items_table(c, "handover_obligation", ["obligation", "source", "owner"], "Handover obligations", "handover obligations (from the contract / specification)"), facts=c.facts(), limitations=_lim(c))


# ================================================================================================ supporting records
def d33(c):
    r = tender.documents_report(c.db, c.pid)
    cols = ["doc_ref", "doc_type", "title", "revision", "received_date", "status", "content_status", "source"]
    allrows = r["current"] + r["superseded"] + r["missing"]
    dm = tender.discipline_matrix(c.db, c.pid)
    return Doc("D33", "Tender document register and revision log", [
        sec_table("Register", ["Ref", "Type", "Title", "Rev", "Received", "Status", "Content status", "Source"], [[d[k] for k in cols] for d in allrows]),
        sec_table("Revision conflicts (BOQ vs register)", ["BOQ item", "Document", "BOQ revision", "Register revision"], [[x["item_key"], x["doc_ref"], x["boq_revision"], x["register_revision"]] for x in r["revision_conflicts"]] or [["-", "none", "", ""]]),
        sec_table("Discipline completeness (drawings / specification / other: current, missing)", ["Discipline", "Drawings", "Specification", "Other", "BOQ lines", "Gaps"],
                  [[x["discipline"], f"{x['drawings']['state']} ({x['drawings']['current']}/{x['drawings']['missing']})", f"{x['specification']['state']} ({x['specification']['current']}/{x['specification']['missing']})",
                    f"{x['other']['state']} ({x['other']['current']}/{x['other']['missing']})", x["boq_lines"], "; ".join(x["gaps"]) or "none"] for x in dm["rows"]] or [["-", "none registered", "", "", "", ""]],
                  paras=([f"Documents without a discipline (cannot be placed): {', '.join(dm['documents_without_discipline'])}"] if dm["documents_without_discipline"] else [])),
        Section("Not interpreted", [", ".join(r["not_interpreted"]) or "none"])], facts=c.facts(), xlsx=True, limitations=_lim(c))


def d34(c):
    items = rows_to_dicts(c.db.all("SELECT item_key, description, unit_original, unit, unit_status, quantity, mapping_status, pricing_method, validation_status FROM boq_items WHERE project_id=? AND item_type='item' ORDER BY id", (c.pid,)))
    keys = {}
    dup = [i["item_key"] for i in items if keys.setdefault((i["description"] or "").strip().lower(), i["item_key"]) != i["item_key"]]
    return Doc("D34", "BOQ mapping and quantity validation report", [
        sec_table("Summary", ["Measure", "Count"], [["BOQ items", len(items)], ["Unmapped", sum(1 for i in items if i["mapping_status"] == "Unmapped")], ["Unit not ok", sum(1 for i in items if i["unit_status"] != "ok")],
                                                  ["Needs review", sum(1 for i in items if i["validation_status"] != "OK")], ["Possible duplicate descriptions", len(dup)]]),
        sec_table("Items", ["Item", "Description", "Unit (original)", "Unit", "Unit status", "Qty", "Mapping", "Pricing", "Validation"], [[i[k] for k in ("item_key", "description", "unit_original", "unit", "unit_status", "quantity", "mapping_status", "pricing_method", "validation_status")] for i in items])],
               facts=c.facts(), xlsx=True, refs=[f"{c.pid}-D05"], limitations=_lim(c))


def d35(c):
    from ..reconciliation import engine as recon
    from ..services import snapshots
    g = recon.final_gate(c.db, "system:pack", c.pid)
    rp = snapshots.replay_estimate(c.db, c.vid)
    fnd = rows_to_dicts(c.db.all("SELECT rule_code, severity, entity_id, title AS message, status FROM recon_findings WHERE run_id=(SELECT MAX(id) FROM recon_runs WHERE project_id=?) ORDER BY severity, rule_code", (c.pid,)))
    exc = rows_to_dicts(c.db.all("SELECT rule_code, entity_id, accepted_by, accepted_role, accepted_actor_type, environment, reason FROM recon_exceptions WHERE project_id=? AND revoked=0", (c.pid,)))
    return Doc("D35", "Estimate audit and reconciliation report", [
        sec_table("Gate", ["Item", "Result"], [["Final gate blocked", str(g["blocked"])], ["Blockers", len(g["blockers"])], ["Replay of frozen version reproduces totals", str(rp.get("ok"))], ["Replay differences", "; ".join(rp.get("differences", [])) or "none"]]),
        sec_table("Findings", ["Rule", "Severity", "Entity", "Message", "Status"], [[f[k] for k in ("rule_code", "severity", "entity_id", "message", "status")] for f in fnd] or [["-", "-", "-", "none", ""]]),
        sec_table("Accepted exceptions", ["Rule", "Entity", "By", "Role", "Actor type", "Environment"], [[e[k] for k in ("rule_code", "entity_id", "accepted_by", "accepted_role", "accepted_actor_type", "environment")] for e in exc] or [["-", "none", "", "", "", ""]])],
               facts={**c.facts(), "replay_ok": str(rp.get("ok"))}, xlsx=True, refs=[f"{c.pid}-D15"], limitations=_lim(c))


def d36(c):
    boq = {r["item_key"]: r for r in c.db.all("SELECT item_key, description, quantity_original, unit, mapping_status FROM boq_items WHERE project_id=? AND item_type='item'", (c.pid,))}
    # every BOQ line of the frozen estimate that is not fully priced (an unmapped line never reaches the pricing schedule, so the schedule alone would hide it)
    un = []
    for it in (c.res.get("items") or []):
        if it.get("complete"):
            continue
        b = boq.get(it["item_key"])
        un.append([it["item_key"], (b["description"] if b else "")[:70], f'{b["quantity_original"]} {b["unit"] or ""}'.strip() if b else "", b["mapping_status"] if b else "", it.get("method") or "unpriced"])
    needs = rows_to_dicts(c.db.all("SELECT id, description, reason, estimated_exposure, closed FROM procurement_items WHERE project_id=? ORDER BY id", (c.pid,)))
    unmapped = sum(1 for r in un if r[3] == "Unmapped")
    need_note = ([f"No procurement need has been raised, but {len(un)} BOQ line(s) are unpriced ({unmapped} unmapped). Procurement needs are detected from MAPPED lines only: map the lines to assemblies/resources first, then run need detection."]
                 if un and not needs else [])
    return Doc("D36", "Missing-rate and procurement report", [
        Section("Summary", [f"{len(un)} of {len(c.res.get('items') or [])} BOQ line(s) are unpriced or incomplete in the frozen estimate (never carried as zero)."]),
        sec_table("Unpriced or incomplete BOQ lines", ["Item", "Description", "Quantity", "Mapping", "Pricing"], un or [["-", "none", "", "", ""]]),
        sec_table("Procurement needs", ["ID", "Description", "Reason", "Exposure", "Closed"], [[n[k] for k in ("id", "description", "reason", "estimated_exposure", "closed")] for n in needs] or [["-", "none", "", "", ""]], paras=need_note),
        sec_table("Exceptions recorded in the frozen estimate (as at freeze; not necessarily resolved)", ["Code", "Severity", "Message"], [[e.get("code"), e.get("severity"), e.get("message")] for e in (c.res.get("exceptions") or [])][:200] or [["-", "-", "none"]])],
               facts=c.facts(), xlsx=True, refs=[f"{c.pid}-D22"], limitations=_lim(c))


def d37(c):
    norms = workforce.list_norms(c.db)
    used = {a["norm_id"] for a in workforce.list_activities(c.db, c.pid) if a["norm_id"]}
    rows = [[n["id"], n["version"], n["trade"], n["activity"], n["basis"], n["value"], n["output_unit"], n["status"], n["evidence_status"], n["origin"], n["source"], "synthetic" if n["is_synthetic"] else ""] for n in norms if n["id"] in used]
    gaps = c.prog["gaps"] if c.prog else []
    return Doc("D37", "Productivity and programme assumptions report", [
        sec_table("Productivity norms used", ["Norm", "Ver", "Trade", "Activity", "Basis", "Value", "Unit", "Status", "Evidence", "Origin", "Source", "Flag"], rows or [["-", "", "", missing("productivity norms"), "", "", "", "", "", "", "", ""]]),
        sec_table("Gaps", ["Activity", "Kind", "Detail"], [[g["code"], g["kind"], g["detail"]] for g in gaps] or [["-", "none", ""]]),
        Section("Method", ["Required labour-hours = quantity x approved labour-hours per unit; crew-days = hours / (productive hours per worker x crew size); duration = ceil(crew-days / effective crews). Crew-output norms use units per crew-day and do not re-apply the labour-hours formula."])],
               facts=c.facts(), xlsx=True, refs=[f"{c.pid}-D19", f"{c.pid}-D08"], limitations=_lim(c, "No norm is an industry benchmark; every value is a sourced company/project entry."))


def d38(c):
    return Doc("D38", "Indirect-cost eligibility report", report_sections("Percentage-indirect eligibility", c.rep("indirect_base"), "indirect base report unavailable"), facts=c.facts(), xlsx=True, refs=[f"{c.pid}-D35"], limitations=_lim(c))


def d39(c):
    return Doc("D39", "Plant-hire and equipment exposure report", report_sections("Day-priced plant", c.rep("plant_hire"), "plant hire report unavailable"), facts=c.facts(), xlsx=True, refs=[f"{c.pid}-D21"], limitations=_lim(c))


def d40(c):
    secs = report_sections("Quantified risk", c.rep("risk"), "no quantified risks / ranges") + report_sections("Escalation", c.rep("escalation"), "no approved escalation profile")
    return Doc("D40", "Estimate risk / sensitivity report", secs, facts=c.facts(), xlsx=True, refs=[f"{c.pid}-D11"], limitations=_lim(c, "Sensitivity uses only quantified ranges that a person entered and approved."))


def d41(c):
    ap = rows_to_dicts(c.db.all("SELECT ts, entity_type, entity_id, action, reviewer, reviewer_role, actor_type, environment FROM approvals WHERE project_id=? OR project_id IS NULL ORDER BY id", (c.pid,)))
    return Doc("D41", "Approval and decision log", [sec_table("Approvals recorded (actor type is resolved from registered users, never a display name)", ["Time", "Entity", "Id", "Action", "By", "Role", "Actor type", "Environment"],
                                                          [[a["ts"], a["entity_type"], a["entity_id"], a["action"], a["reviewer"], a["reviewer_role"], a["actor_type"], a["environment"]] for a in ap][-300:] or [["-", "none", "", "", "", "", "", ""]])],
               facts=c.facts(), xlsx=True, refs=[f"{c.pid}-D15"], limitations=_lim(c, "Test principals' approvals are recorded as such and never count towards submission readiness."))


def open_actions(c):
    rows = []
    for q in tender.open_material_queries(c.db, c.pid):
        rows.append([q["id"], f"Resolve query ({q['register']}): {q['question'][:120]}", q["status"], "Estimator"])
    for a in rows_to_dicts(c.db.all("SELECT id, description, owner, due, status FROM open_actions WHERE project_id=? AND status='Open' ORDER BY id", (c.pid,))):
        rows.append([a["id"], a["description"], f"Open (due {a['due']})", a["owner"]])
    for r in (c.readiness or {}).get("reasons", []):
        rows.append(["GATE", r, "Open", "Commercial Approver"])
    return rows


def d42(c):
    secs = [sec_table("Outstanding", ["Ref", "Item", "Status", "Owner"], open_actions(c) or [["-", "none", "", ""]])]
    secs += items_table(c, "required_input", ["input", "needed_for", "status_note"], "Required-inputs checklist", "required-inputs checklist")
    secs += items_table(c, "responsibility", ["role", "responsibility", "assigned_to"], "Responsibility assignment", "responsibility assignment")
    return Doc("D42", "Open actions and outstanding information register", secs, facts=c.facts(), xlsx=True, refs=[f"{c.pid}-D25", f"{c.pid}-D15"], limitations=_lim(c))


def d43(c):
    r = c.readiness or {}
    chk = [["Frozen estimate version recorded", f"v{c.v['version_no']}"], ["Estimate state", c.v["state"]], ["Open material queries", len(tender.open_material_queries(c.db, c.pid))],
           ["Programme baseline approved", "yes" if c.prog_row and c.prog_row["status"] == "Approved" else "no"], ["Readiness classification", r.get("classification", "not evaluated")],
           ["Production ready", str(r.get("production_ready"))]]
    return Doc("D43", "Tender handover checklist", [sec_table("Checklist (computed from the application's records)", ["Check", "Result"], chk)], facts=c.facts(), refs=[f"{c.pid}-D15", f"{c.pid}-D42"], limitations=_lim(c))


def d44(c):
    return Doc("D44", "Post-award project setup checklist", [Section("Post-award setup", ["Applicable only after an award. Items: confirm contract documents; appoint project manager and owners (see handover owners); set up cost control against the cost baseline; issue purchase orders for long-lead items; submit baseline programme; mobilisation plan; HSE and quality plans; insurances and bonds."]),
                                                              Section("Status", ["No award has been made. This checklist is part of a hypothetical post-award handover simulation." if c.hypothetical else "No award has been made."])],
               facts=c.facts(), limitations=_lim(c))


def d45(c):
    docs = c.pack_docs
    return Doc("D45", "Final document manifest", [sec_table("Documents in this pack", ["Code", "Document ID", "Title", "Rev", "Status", "Applicability", "Template", "Formats", "SHA-256 (docx or first file)"],
                                                           [[d["code"], d["doc_id"], d["title"], d["revision"], d["status"], d["applicability"], d["template"], d["formats"], d["sha256"]] for d in docs] or [["-", "", "", "", "", "", "", "", ""]]),
                                 Section("Self reference", ["This manifest cannot contain its own checksum; the machine-readable manifest.json beside the pack carries the hash of every file including this one."])],
               facts=c.facts(), xlsx=True, refs=[f"{c.pid}-D33"], limitations=_lim(c))


BUILDERS = {i: globals()[f"d{i:02d}"] for i in range(1, 46)}
