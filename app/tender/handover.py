"""Hypothetical post-award handover documents (H01-H17): composed from the same builders and registers as the tender pack, so scope, cost, programme and obligations cannot diverge."""
from __future__ import annotations

from ..core.money import D_opt
from ..services import tender, workforce
from . import builders as b
from .model import Doc, Section, missing


def _compose(code: str, title: str, c, *parts: Doc, extra: list[Section] | None = None, refs=None, xlsx=True) -> Doc:
    secs = [Section("Simulation notice", ["HYPOTHETICAL POST-AWARD HANDOVER: no award has been made. This pack shows what a project manager would receive if the tender were awarded on the frozen estimate; it creates no commitment."])]
    for p in parts:
        secs += p.sections
    secs += extra or []
    d = Doc(code, title, secs, facts=c.facts(), refs=refs or [], xlsx=xlsx, limitations=b._lim(c, "Simulated handover: owners, dates and obligations shown are those recorded in the registers; none is invented."))
    return d


def h01(c): return _compose("H01", "Awarded scope and scope boundaries", c, b.d04(c), refs=[f"{c.pid}-H03"])
def h02(c): return _compose("H02", "Final tender BOQ and cost baseline", c, b.d05(c), refs=[f"{c.pid}-H16"])
def h03(c): return _compose("H03", "Approved assumptions and exclusions", c, b.d08(c), b.d09(c))
def h04(c): return _compose("H04", "Customer clarifications and responses", c, b.d25(c))
def h05(c): return _compose("H05", "Programme baseline and constraints", c, b.d19(c), b.d14(c))
def h06(c): return _compose("H06", "Procurement and long-lead commitments", c, b.d22(c))
def h07(c): return _compose("H07", "Subcontract interfaces", c, b.d26(c))
def h08(c): return _compose("H08", "Technical submittal obligations", c, b.d30(c))
def h09(c): return _compose("H09", "Quality, inspection and test obligations", c, b.d27(c), b.d28(c))
def h10(c): return _compose("H10", "HSE and access requirements", c, b.d29(c))
def h11(c): return _compose("H11", "Commissioning and handover obligations", c, b.d31(c), b.d32(c))
def h12(c): return _compose("H12", "Commercial terms, payment milestones and retention", c, b.d06(c), b.d13(c))
def h13(c): return _compose("H13", "Risk register and mitigation owners", c, b.d11(c))
def h14(c): return _compose("H14", "Outstanding decisions and actions", c, b.d42(c))


def h15(c):
    return _compose("H15", "Document register and revisions", c, b.d33(c), extra=[Section("Tender pack revisions", [
        f"Tender pack revisions recorded for this project: {c.db.scalar("SELECT COUNT(*) FROM tender_packs WHERE project_id=? AND kind='tender'", (c.pid,))}."])])


def h16(c):
    from ..services import snapshots
    rp = snapshots.replay_estimate(c.db, c.vid)
    return Doc("H16", "Estimate snapshot and replay fingerprint", [
        Section("Simulation notice", ["HYPOTHETICAL POST-AWARD HANDOVER: simulation only."]),
        b.sec_table("Frozen estimate", ["Item", "Value"], [["Version", f"v{c.v['version_no']}"], ["State", c.v["state"]], ["Fingerprint (SHA-256)", c.v["inputs_hash"]], ["Replay reproduces frozen totals", str(rp.get("ok"))],
                                                          ["Replayed fingerprint", rp.get("fingerprint")], ["Net price", b.fmt(c.t.get("commercial_net_price"))], ["Payable", b.fmt(c.t.get("final_payable"))]])],
               facts={**c.facts(), "replay_ok": str(rp.get("ok"))}, refs=[f"{c.pid}-H02"], limitations=b._lim(c))


def h17(c):
    rows = b.open_actions(c)
    from ..database import rows_to_dicts
    acts = rows_to_dicts(c.db.all("SELECT id, description, owner, due FROM open_actions WHERE project_id=? AND status='Open'", (c.pid,)))
    no_owner = [a["id"] for a in acts if not a["owner"]]
    secs = [Section("Simulation notice", ["HYPOTHETICAL POST-AWARD HANDOVER: simulation only."]),
            b.sec_table("Follow-up actions and named owners", ["Ref", "Item", "Status", "Owner"], rows or [["-", "none", "", ""]])]
    if no_owner:
        secs.append(Section("Missing owners", [missing("named human owner for " + ", ".join(no_owner))]))
    return Doc("H17", "Follow-up action owners", secs, facts=c.facts(), refs=[f"{c.pid}-H14"], limitations=b._lim(c))


HANDOVER = {f"H{i:02d}": globals()[f"h{i:02d}"] for i in range(1, 18)}
