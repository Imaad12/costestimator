"""Reconciliation findings for the extended controls (benchmarks, take-off derivations, package interfaces, long-lead items, quantified risk, client profile,
pending governed parameters). Severities and exception policy live in config/reconciliation_rules.json like every other rule."""
from __future__ import annotations

from ..database import Database
from .engine import Finding


def collect_extended(db: Database, project_id: str, est) -> list[Finding]:
    from ..services import bids, mto, profiles, provisions
    F: list[Finding] = []
    bm = provisions.benchmark_report(db, project_id, est=est)
    for r in bm["outside"]:
        F.append(Finding("BENCHMARK_OUTSIDE_RANGE", f"{r['name']} [{r['benchmark']}]: {r['subject']} = {r['value']:.2f}, {r['status'].lower()} {r['low']}-{r['high']} ({r['source']}).",
                         "benchmark", f"{r['benchmark']}:{r['subject']}"))
    for a in mto.status_report(db, project_id)["stale"]:
        F.append(Finding("MTO_STALE", f"Take-off derivation {a['template']} on BOQ {a['item_key']} is out of date ({', '.join(a['flags'])}); re-apply and re-approve.",
                         "mto_application", f"{a['item_key']}:{a['template']}"))
    ir = bids.interface_report(db, project_id)
    for f in ir["findings"]:
        F.append(Finding(f["code"], f["message"], "boq_item", f["item_key"]))
    for it in bids.long_lead_report(db, project_id)["attention"]:
        F.append(Finding("LONG_LEAD_AT_RISK", f"{it['id']} {it['description']}: {it['status']} (latest order {it['latest_order_date']}, float {it['float_days']} d)"
                         + (f"; vendor data {it['vendor_data']}" if it["vendor_data"] == "Overdue" else ""), "long_lead", it["id"]))
    for r in db.all("SELECT id, title FROM risks WHERE project_id=? AND status='Open' AND (prob_pct IS NULL OR cost_likely IS NULL)", (project_id,)):
        F.append(Finding("RISK_UNQUANTIFIED", f"Open risk {r['id']} '{r['title']}' has no probability / cost range and is outside the quantified risk analysis.", "risk", r["id"]))
    if db.one("SELECT 1 FROM project_profiles WHERE project_id=?", (project_id,)):
        c = profiles.compliance_report(db, project_id, est=est)
        for rid in c["mandatory_unmet"]:
            q = next(x for x in c["requirements"] if x["req_id"] == rid)
            F.append(Finding("PROFILE_MANDATORY_UNMET", f"Profile {c['profile']['code']} v{c['profile']['version']} {rid} '{q['title']}' ({q['source_ref']}): {q['status']}.", "profile_requirement", rid))
    for p in db.all("SELECT kind, code, version, status FROM governed_params WHERE (project_id=? OR project_id IS NULL) AND status IN ('Draft','Pending Review') "
                    "AND kind IN ('productivity_factor','plant_hire_terms','mto_factor','calendar')", (project_id,)):
        F.append(Finding("PARAMETER_UNAPPROVED", f"{p['kind']} '{p['code']}' v{p['version']} is {p['status']} and is not used in the strict estimate.", "governed_param", f"{p['kind']}:{p['code']}:{p['version']}"))
    return F
