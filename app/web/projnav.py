"""Project navigation: one ordered, grouped menu for everything inside a project, in the order the work is done.

Each section is (url suffix, label, one-line purpose). The suffix is what follows /projects/<id>/ ('' = the estimate overview). The purpose line is shown on the page and as the menu tooltip,
so a new user can tell what a page is for before opening it.
"""
from __future__ import annotations

GROUPS: list[dict] = [
    dict(key="start", title="Start here", items=[
        ("tower", "Control tower", "Where this tender stands: 11 workflow stages, what is blocking, what to do next."),
        ("", "Estimate overview", "The estimate's state, totals and what is priced or missing."),
        ("readiness", "Readiness", "Why the tender is or is not submission-ready."),
    ]),
    dict(key="docs", title="Tender documents", items=[
        ("tender", "Tender desk", "The enquiry, the documents received, revisions and what is missing."),
        ("workspace", "Files & workspace", "The project folders and every file in them."),
        ("queries", "Queries & RFIs", "Questions to the customer: drafts, approval to issue, responses and their cost or time impact."),
        ("registers", "Clarifications & risk", "Clarifications, assumptions of scope, exclusions and the risk register."),
    ]),
    dict(key="qty", title="Quantities", items=[
        ("boq", "BOQ import", "Import the client's bill of quantities and check it. Quantities are measured by you; the software never measures drawings."),
        ("mapping", "Cost-code mapping", "Map each BOQ item to an approved assembly or a priced allowance."),
    ]),
    dict(key="price", title="Pricing", items=[
        ("assumptions", "Assumptions", "The assumptions this estimate rests on, and any project-specific overrides."),
        ("inputs", "Inputs & parameters", "Company-supplied numbers: calendar, productivity, payment terms, escalation and so on."),
        ("estimate", "Estimate build-up", "Direct cost per line, built from approved rates and assemblies."),
        ("procurement", "Procurement & RFQs", "What must be bought, and the requests for quotation."),
        ("quotes", "Quotations", "Supplier quotations: enter, level, compare and select."),
    ]),
    dict(key="prog", title="Programme", items=[
        ("workforce", "Workforce & programme", "Productivity norms, crews, work calendar and the programme baseline."),
        ("structure", "WBS & schedule", "Work breakdown, cost breakdown and programme structure."),
    ]),
    dict(key="comm", title="Commercial", items=[
        ("commercial", "Indirects & commercials", "Indirect costs, margin, tax and the commercial policy."),
        ("reconciliation", "Reconciliation", "Cross-checks of cost, schedule, offer and assumptions; freeze and approve versions."),
    ]),
    dict(key="sub", title="Controls & submission", items=[
        ("tender-registers", "Quality, HSE & compliance", "ITP, HSE, compliance and other registers, and their action lists."),
        ("completeness", "Completeness", "What is still missing before a trustworthy estimate."),
        ("analysis", "Analysis & controls", "Roll-ups, risk, cash flow, variations and earned value reports."),
        ("reports", "Reports & exports", "Reports, workbooks and exports."),
        ("pack", "Tender pack", "The 45-document pack, its validator and document approvals."),
    ]),
]

FLAT = [(k, lbl, desc, g["title"], g["key"]) for g in GROUPS for (k, lbl, desc) in g["items"]]


def current(path: str, project_id: str) -> tuple[str, str, str, str] | None:
    """(suffix, label, purpose, group title) for the page at `path`, by longest matching suffix."""
    base = f"/projects/{project_id}"
    if not path.startswith(base):
        return None
    rest = path[len(base):].strip("/")
    best = None
    for k, lbl, desc, gt, gk in FLAT:
        if (k == "" and rest == "") or (k and (rest == k or rest.startswith(k + "/"))):
            if best is None or len(k) > len(best[0]):
                best = (k, lbl, desc, gt, gk)
    return best[:4] + (best[4],) if best else None


def label(key: str) -> str:
    """The menu label for a section key (used as the page title so the title, menu and breadcrumb always agree)."""
    for k, lbl, _desc, _g, _gk in FLAT:
        if k == key:
            return lbl
    return key
