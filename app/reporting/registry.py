"""Registry of read-only project reports / analyses that are exposed identically by the REST API, the web UI and the CLI.
A report is a function (db, project_id, **params) -> dict. Reports never change an estimate and never approve anything; parameters arrive as strings."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..core.errors import ValidationFailed
from ..database import Database


@dataclass
class Report:
    name: str
    label: str
    description: str
    fn: Callable
    params: list[tuple[str, str, str]] = field(default_factory=list)      # (name, default, help)
    group: str = "Analysis"


REPORTS: dict[str, Report] = {}


def report(name: str, label: str, description: str, params: list[tuple[str, str, str]] | None = None, group: str = "Analysis"):
    def deco(fn):
        REPORTS[name] = Report(name, label, description, fn, params or [], group)
        return fn
    return deco


def run_report(db: Database, name: str, project_id: str, params: dict | None = None) -> dict:
    if name not in REPORTS:
        raise ValidationFailed(f"Unknown report '{name}'. Known: {sorted(REPORTS)}", code="UNKNOWN_REPORT")
    r = REPORTS[name]
    clean = {}
    for pname, default, _ in r.params:
        v = (params or {}).get(pname)
        clean[pname] = default if v in (None, "") else v
    extra = set(params or {}) - {p[0] for p in r.params}
    if extra:
        raise ValidationFailed(f"Unknown parameter(s) {sorted(extra)} for report {name}.", code="UNKNOWN_PARAM")
    return r.fn(db, project_id, **clean)


def listing() -> list[dict]:
    return [dict(name=r.name, label=r.label, description=r.description, group=r.group, params=[dict(name=n, default=d, help=h) for n, d, h in r.params])
            for r in REPORTS.values()]


# ------------------------------------------------------------------------------------------------ registrations
@report("indirect_base", "Percentage-indirect eligibility base", "What each percentage indirect is applied to: eligible, excluded and unclassified direct cost by cost code, BOQ line and kind, and preliminaries inside the base.", group="Risk and commercial")
def _indirect_base(db, pid):
    from ..services import indirect_base
    return indirect_base.indirect_base_report(db, pid)


@report("plant_hire", "Day-priced plant: billable days vs programme window", "Working days vs calendar days, minimum hire, standby, mobilisation and the on-site window read from the programme.", group="Programme")
def _plant_hire(db, pid):
    from ..services import plant_hire
    return plant_hire.plant_hire_report(db, pid)


@report("rollup", "Cost roll-up (CBS / WBS / client cross-walk)", "Direct cost rolled up by cost-code tree, WBS, WBS x division matrix and each client code system; ties out to the estimate.",
        [("preliminary", "0", "1 = include unapproved inputs (flagged)")], group="Structure")
def _rollup(db, pid, preliminary="0"):
    from ..services import wbs
    return wbs.rollup_report(db, pid, include_unapproved=str(preliminary) in ("1", "true", "yes"))


@report("schedule", "Programme: dates, float, critical path", "CPM with relationship types, lags and an optional working calendar.", group="Programme")
def _schedule(db, pid):
    from ..services import programme
    return programme.schedule_report(db, pid)


@report("loading", "Resource loading histogram", "Labour hours, plant hours or cost spread over the programme and bucketed by week / month / block.",
        [("measure", "labour_hours", "labour_hours | plant_hours | cost"), ("period", "week", "week | month | block"), ("block_days", "5", "working days per block when no calendar"),
         ("preliminary", "0", "1 = include unapproved inputs")], group="Programme")
def _loading(db, pid, measure="labour_hours", period="week", block_days="5", preliminary="0"):
    from ..services import programme
    from ..core.money import quantise_tree
    return quantise_tree(programme.loading_report(db, pid, measure=measure, period=period, block_days=int(block_days), include_unapproved=str(preliminary) in ("1", "true", "yes")))


@report("manhours", "Man-hour aggregation", "Own-labour hours by craft, cost code, division and WBS (subcontract labour is not included).",
        [("preliminary", "0", "1 = include unapproved inputs")], group="Programme")
def _manhours(db, pid, preliminary="0"):
    from ..services import programme
    return programme.manhours_report(db, pid, include_unapproved=str(preliminary) in ("1", "true", "yes"))


@report("classification", "Estimate classification and maturity", "Class and accuracy range from the APPROVED classification scheme and the estimator's stated maturity, next to measured maturity facts.",
        group="Basis of estimate")
def _classification(db, pid):
    from ..services import profiles
    return profiles.classification_report(db, pid)


@report("compliance", "Client profile compliance matrix", "Requirements loaded from the owner's controlled documents, evaluated against measured facts or human attestations.",
        group="Basis of estimate")
def _compliance(db, pid):
    from ..services import profiles
    return profiles.compliance_report(db, pid)


@report("mto_status", "Take-off derivation status", "Applications of take-off templates and whether their factors / drivers have changed since.", group="Structure")
def _mto_status(db, pid):
    from ..services import mto
    return mto.status_report(db, pid)


@report("mto_preview", "Take-off derivation preview", "What a template would derive for an item (nothing is written).",
        [("item_key", "", "BOQ item key"), ("template", "", "template code"), ("driver_qty", "", "measured driver quantity (optional)"),
         ("driver_source", "", "source of the driver quantity when given")], group="Structure")
def _mto_preview(db, pid, item_key="", template="", driver_qty="", driver_source=""):
    from ..services import mto
    return mto.preview(db, pid, item_key, template, driver_qty or None, driver_source or None)


@report("boe", "Basis of Estimate (facts)", "Structured facts for the Basis of Estimate; generate the document with the generate_boe action.", group="Basis of estimate")
def _boe(db, pid):
    from ..services import boe
    return boe.build_boe(db, pid)


@report("currency_exposure", "Currency exposure and hedge cover", "Priced direct cost by quotation currency (landed-cost rates split by recorded exposure), approved hedge cover and what-if sensitivity.",
        [("shocks", "5,10", "what-if FX move steps in percent (not forecasts)"), ("preliminary", "0", "1 = include unapproved inputs")], group="Commercial")
def _exposure(db, pid, shocks="5,10", preliminary="0"):
    from ..services import landed
    return landed.exposure_report(db, pid, shocks=shocks, include_unapproved=str(preliminary) in ("1", "true", "yes"))


@report("risk", "Quantified risk: expected value and Monte Carlo", "Seeded simulation over quantified risks and cost ranges; proposes a provision at the chosen confidence level (never applied automatically).",
        [("trials", "10000", "simulation trials (100-1,000,000)"), ("seed", "20260101", "random seed - same seed gives identical results"), ("target_pct", "80", "confidence level for the proposed provision"),
         ("preliminary", "0", "1 = include unapproved inputs")], group="Risk and commercial")
def _risk(db, pid, trials="10000", seed="20260101", target_pct="80", preliminary="0"):
    from ..services import risk
    return risk.risk_report(db, pid, trials=int(trials), seed=int(seed), target_pct=int(target_pct), include_unapproved=str(preliminary) in ("1", "true", "yes"))


@report("escalation", "Time-phased escalation", "Escalation by programme month from each approved profile's base date; index values shown as information.",
        [("index_dataset", "", "optional index dataset to show (e.g. the GASTAT CCI dataset name)"), ("preliminary", "0", "1 = include unapproved inputs")], group="Risk and commercial")
def _escalation(db, pid, index_dataset="", preliminary="0"):
    from ..services import risk
    from ..core.money import quantise_tree
    return quantise_tree(risk.escalation_report(db, pid, index_dataset=index_dataset or None, include_unapproved=str(preliminary) in ("1", "true", "yes")))


@report("cashflow", "Cash flow, retention, bonds and financing", "Monthly cash position from approved payment terms; peak funding, interest and bond cost.",
        [("terms_code", "", "payment-terms code (default: first approved)"), ("preliminary", "0", "1 = include unapproved inputs")], group="Risk and commercial")
def _cashflow(db, pid, terms_code="", preliminary="0"):
    from ..services import cashflow
    from ..core.money import quantise_tree
    return quantise_tree(cashflow.cashflow_report(db, pid, terms_code=terms_code or None, include_unapproved=str(preliminary) in ("1", "true", "yes")))


def _flag(v) -> bool:
    return str(v).lower() in ("1", "true", "yes", "on")


@report("bid_evaluation", "Bid evaluation (weighted, advisory)", "Weighted scores from approved criteria and recorded evidence plus levelled prices; ranking is advisory.",
        [("package_id", "", "procurement package id"), ("criteria_code", "", "approved evaluation-criteria code")], group="Procurement")
def _bid_eval(db, pid, package_id="", criteria_code=""):
    from ..services import bids
    return bids.evaluation_report(db, package_id, criteria_code)


@report("long_lead", "Long-lead items", "Latest order date, float and status for long-lead items and vendor data.", [("on", "", "report date YYYY-MM-DD (default today)")], group="Procurement")
def _long_lead(db, pid, on=""):
    from ..core.timeutil import parse_date
    from ..services import bids
    return bids.long_lead_report(db, pid, parse_date(on) if on else None)


@report("interface_matrix", "Package scope / interface matrix", "Who includes each BOQ item; double counts, gaps and open interfaces.", group="Procurement")
def _interface(db, pid):
    from ..services import bids
    return bids.interface_report(db, pid)


@report("contract_status", "Contract value and variations", "Original contract sum, approved and pending variations, revised sum and time impact.", group="Post-award control")
def _contract(db, pid):
    from ..services import controls
    return controls.contract_status(db, pid)


@report("earned_value", "Earned value and forecast", "PV / EV / AC, CPI / SPI and forecasts at a data date from entered progress and recorded actuals.",
        [("data_date", "", "YYYY-MM-DD (default today)"), ("version_id", "", "baseline from a frozen estimate version (default: live estimate)")], group="Post-award control")
def _evm(db, pid, data_date="", version_id=""):
    from ..services import controls
    return controls.evm_report(db, pid, data_date or None, version_id=int(version_id) if version_id else None)


@report("benchmarks", "Benchmark reasonableness check", "Estimate values compared with the company's approved benchmark ranges.", [("preliminary", "0", "1 = include unapproved inputs")], group="Risk and commercial")
def _bench(db, pid, preliminary="0"):
    from ..services import provisions
    return provisions.benchmark_report(db, pid, include_unapproved=_flag(preliminary))


@report("engineering", "Engineering effort and cost", "Hours and cost of declared engineering deliverables at approved labour rates.", group="Risk and commercial")
def _eng(db, pid):
    from ..services import provisions
    return provisions.engineering_report(db, pid)


@report("overhead", "Overhead pool allocation", "Project share of approved annual overhead pools.", [("pool_code", "", "limit to one pool")], group="Risk and commercial")
def _oh(db, pid, pool_code=""):
    from ..services import provisions
    return provisions.overhead_report(db, pid, pool_code=pool_code or None)


@report("method_comparison", "Construction-method alternatives (what-if)", "Base estimate beside each approved method alternative: direct / indirect / total cost, man-hours, plant hours and duration.",
        [("preliminary", "0", "1 = include unapproved inputs")], group="Structure")
def _methods(db, pid, preliminary="0"):
    from ..services import methods
    return methods.comparison_report(db, pid, include_unapproved=_flag(preliminary))


# ------------------------------------------------------------------------------------------------ end-to-end closure reports
@report("assumption_evidence", "Assumptions: standing of every adopted value", "Each adopted/mandatory assumption classified as verified, company-approved, project-approved, imported-unverified, pending review, AI-proposed, synthetic or missing.", group="Governance")
def _assumption_evidence(db, pid):
    from ..services import assumptions
    return assumptions.evidence_report(db, pid)


@report("productivity_programme", "Productivity-based, resource-constrained programme", "Activities scheduled from approved (or explicitly provisional) productivity norms, a workforce profile and the project calendar; reports gaps and what they do to the programme.",
        [("profile", "", "workforce profile id"), ("provisional", "false", "true = include unapproved norms/profile (result is labelled provisional)")], group="Programme")
def _productivity_programme(db, pid, profile, provisional):
    from ..services import workforce
    if not profile:
        raise ValidationFailed("profile is required (a workforce profile id).", code="FIELD_REQUIRED")
    prov = str(provisional).lower() in ("1", "true", "yes")
    r = workforce.build_programme(db, pid, profile, allow_provisional=prov, allow_unconfirmed_calendar=prov)
    r.pop("workers_by_day", None)
    return r


@report("crew_scenarios", "Crew-size scenarios", "The same activities, norms and calendar scheduled for several workforce profiles: duration, staffing, labour-hours, critical path, constraints and (when role costs are entered) cost.",
        [("profiles", "", "comma separated workforce profile ids"), ("provisional", "false", "true = include unapproved inputs (labelled)")], group="Programme")
def _crew_scenarios(db, pid, profiles, provisional):
    from ..services import workforce
    ids = [x.strip() for x in profiles.split(",") if x.strip()]
    if len(ids) < 1:
        raise ValidationFailed("profiles is required.", code="FIELD_REQUIRED")
    prov = str(provisional).lower() in ("1", "true", "yes")
    return workforce.crew_scenarios(db, pid, ids, allow_provisional=prov, allow_unconfirmed_calendar=prov)


@report("tender_queries", "Technical / commercial query registers", "All draft and issued queries by register and status; unresolved material queries block submission.", group="Tender")
def _tender_queries(db, pid):
    from ..services import tender
    return tender.queries_report(db, pid)


@report("tender_documents", "Received tender documents and revisions", "Documents received, revisions, superseded and missing ones, BOQ-vs-register revision conflicts; says what was only registered, not interpreted.", group="Tender")
def _tender_documents(db, pid):
    from ..services import tender
    return tender.documents_report(db, pid)


@report("discipline_completeness", "Discipline x document completeness", "For each discipline the project expects: drawings, specification and other documents received / missing, and BOQ lines carrying that discipline.", group="Tender")
def _discipline_completeness(db, pid):
    from ..services import tender
    return tender.discipline_matrix(db, pid)


@report("applicability", "Tender document applicability matrix", "Each of the 45 tender documents classified Required / Conditional / Not Applicable / Missing Customer Requirement with a reason.", group="Tender")
def _applicability(db, pid):
    from ..tender import catalogue
    return catalogue.matrix(db, pid)
