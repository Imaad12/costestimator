"""SYNTHETIC inputs for the closure scenario 'Dammam Industrial Utilities - Synthetic Tender Closure'.

Every name, quantity, rate, norm, crew, date and customer response here is a fictional TEST fixture: none is market evidence, an industry benchmark, a real customer or a live supplier quotation.
"""
from __future__ import annotations

import json
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "closure_scenario"
PROJECT_ID = "PRJ-9101"
SYN = "SYNTHETIC TEST DATA - NOT AN INDUSTRY BENCHMARK - NOT A MARKET QUOTE"
BANNER = "SYNTHETIC SOFTWARE VALIDATION ONLY - FICTIONAL CUSTOMER - NOT A REAL TENDER - NOT FOR SUBMISSION OR COMMERCIAL RELIANCE."
ISSUE_DATE = "2027-02-15"
START_DATE = "2027-03-07"                 # a Sunday in the synthetic calendar
CUSTOMER = "Gulf Process Utilities Co. (FICTIONAL SYNTHETIC CUSTOMER)"


def lines() -> list[dict]:
    return json.loads((FIX / "lines_SYNTHETIC.json").read_text())


UNIT_EXTRA = {"inch_dia": "inch_dia"}

# ---- synthetic productivity norms: id, trade, activity, unit, basis, value, crew, evidence_status, extra
NORMS = [
    ("N-EXC", "Civil", "Trench excavation", "m3", "crew_output_per_crew_day", "60", {"operator": 1, "labourer": 2}),
    ("N-EXCH", "Civil", "Excavation in hard material", "m3", "crew_output_per_crew_day", "12", {"operator": 1, "labourer": 2}),
    ("N-BACK", "Civil", "Backfill and compaction", "m3", "crew_output_per_crew_day", "80", {"operator": 1, "labourer": 2}),
    ("N-SHORE", "Civil", "Trench shoring", "m", "crew_output_per_crew_day", "40", {"skilled": 2, "labourer": 2}),
    ("N-ROAD", "Civil", "Road reinstatement", "m2", "crew_output_per_crew_day", "45", {"semi_skilled": 2, "labourer": 3}),
    ("N-FORM", "Structural", "Formwork", "m2", "crew_output_per_crew_day", "20", {"skilled": 3, "labourer": 2}),
    ("N-REBAR", "Structural", "Reinforcement fix", "kg", "labour_hours_per_unit", "0.04", {"skilled": 3, "labourer": 2}),
    ("N-POUR", "Structural", "Concrete pour", "m3", "crew_output_per_crew_day", "24", {"skilled": 2, "semi_skilled": 2, "labourer": 4}),
    ("N-STEEL", "Structural", "Steel erection", "kg", "crew_output_per_crew_day", "2500", {"skilled": 3, "semi_skilled": 1, "operator": 1, "eq:crane": 1}),
    ("N-SUPP", "Piping", "Support fabrication", "kg", "crew_output_per_crew_day", "500", {"skilled": 2, "semi_skilled": 1}),
    ("N-PUMP", "Mechanical", "Pump skid setting", "nr", "crew_output_per_crew_day", "0.5", {"skilled": 3, "eq:crane": 1}),
    ("N-PIPE", "Piping", "Pipe fabrication and installation", "inch_dia", "labour_hours_per_unit", "0.5", {"skilled": 2, "semi_skilled": 1, "labourer": 1}),
    ("N-WELD", "Piping", "Butt welding", "joint", "labour_hours_per_unit", "3", {"skilled": 2, "labourer": 1}),
    ("N-COAT", "Piping", "Coating", "m2", "crew_output_per_crew_day", "60", {"semi_skilled": 2, "labourer": 2}),
    ("N-TRAY", "Electrical", "Cable tray", "m", "crew_output_per_crew_day", "45", {"sub:electrical": 4}),
    ("N-CABLE", "Electrical", "Cable pulling", "m", "crew_output_per_crew_day", "120", {"sub:electrical": 4}),
    ("N-FIBRE", "ELV", "Fibre backbone", "m", "crew_output_per_crew_day", "100", {"sub:electrical": 2}),
]
UNVERIFIED_NORMS = {"N-WELD", "N-EXCH"}           # approved by TEST ACTORs but their evidence stays 'unverified' (never 'verified'): the programme reports it
NDT_NORM = ("N-NDT", "Piping", "Radiographic testing", "joint", "crew_output_per_crew_day", "6", {"skilled": 2})        # proposed late (programme gap resolved in step 21)

# activity code, name, BOQ item key, norm, crews, fronts, fixed_days, predecessors, cost_code, long_lead
ACTIVITIES = [
    ("A-MOB", "Mobilisation", None, None, 1, 1, {"fixed_only": True, "setup": 5}, "", "A.01"),
    ("A-EXC", "Trench excavation", "C-010", "N-EXC", 2, 2, {}, "A-MOB", "B.02"),
    ("A-EXCH", "Hard-material excavation", "C-013", "N-EXCH", 1, 1, {}, "A-EXC", None),
    ("A-SHORE", "Trench shoring", "C-012", "N-SHORE", 1, 1, {}, "A-MOB", "B.04"),
    ("A-FORM", "Pipe-rack formwork", "C-021", "N-FORM", 2, 2, {}, "A-EXC", "C.02"),
    ("A-REBAR", "Pipe-rack reinforcement", "C-022", "N-REBAR", 2, 2, {}, "A-EXC", "C.03"),
    ("A-POUR", "Pipe-rack concrete", "C-020", "N-POUR", 1, 1, {"curing": 7}, "A-FORM,A-REBAR", "C.01"),
    ("A-STEEL", "Pipe-rack steel erection", "C-023", "N-STEEL", 2, 2, {}, "A-POUR", "C.04"),
    ("A-SUPP", "Pipe support fabrication", "C-040", "N-SUPP", 1, 1, {}, "A-POUR", None),
    ("A-PUMP", "Pump skid setting", "C-045", "N-PUMP", 1, 1, {}, "A-POUR", "E.08"),
    ("A-PIPE100", "Pipe installation DN100", "C-032", "N-PIPE", 3, 3, {}, "A-STEEL,A-SUPP", None),
    ("A-PIPE50", "Pipe installation DN50", "C-033", "N-PIPE", 2, 2, {}, "A-STEEL,A-SUPP", None),
    ("A-WELD", "Butt welding", "C-037", "N-WELD", 3, 3, {}, "A-PIPE100,A-PIPE50", None),
    ("A-NDT", "Weld radiography", "C-038", None, 1, 1, {}, "A-WELD", None),
    ("A-HYDRO", "Hydrotest and flushing", None, None, 1, 1, {"fixed_only": True, "testing": 8}, "A-NDT,A-PUMP", "E.06"),
    ("A-BACK", "Backfill", "C-011", "N-BACK", 1, 1, {}, "A-HYDRO", None),
    ("A-ROAD", "Road reinstatement", "C-014", "N-ROAD", 1, 1, {}, "A-BACK", "B.05"),
    ("A-COAT", "Coating", "C-041", "N-COAT", 1, 1, {}, "A-HYDRO", None),
    ("A-TRAY", "Cable tray", "C-062", "N-TRAY", 1, 1, {}, "A-STEEL", "H.03"),
    ("A-CABLE", "Cable pulling", "C-061", "N-CABLE", 1, 1, {}, "A-TRAY", None),
    ("A-ELV", "Fibre backbone", "C-070", "N-FIBRE", 1, 1, {}, "A-TRAY", "I.01"),
    ("A-COMM", "Testing and commissioning", None, None, 1, 1, {"fixed_only": True, "testing": 10}, "A-COAT,A-CABLE,A-ELV,A-ROAD", None),
    ("A-DEMOB", "Demobilisation", None, None, 1, 1, {"fixed_only": True, "setup": 3}, "A-COMM", None),
]

# workforce archetypes: id, archetype, name, direct roles, indirect roles, shifts, night eff, attendance, availability, productive h, fronts, sub capacity
PROFILES = [
    ("WP-SME", "sme", "SME crew (SYNTHETIC)", {"skilled": 4, "semi_skilled": 3, "labourer": 5, "operator": 2, "eq:crane": 1}, {"foreman": 1}, 1, None, "92", "95", "6", 2, {"electrical": 4}),
    ("WP-MID", "mid", "Mid-sized crew (SYNTHETIC)", {"skilled": 7, "semi_skilled": 4, "labourer": 6, "operator": 2, "eq:crane": 1}, {"foreman": 2, "engineer": 1, "qc": 1, "hse": 1}, 1, None, "92", "95", "6", 3, {"electrical": 6}),
    ("WP-LARGE", "large", "Large crew (SYNTHETIC)", {"skilled": 14, "semi_skilled": 8, "labourer": 12, "operator": 3, "eq:crane": 1}, {"foreman": 3, "supervisor": 2, "engineer": 2, "qc": 2, "hse": 2}, 1, None, "92", "95", "6", 4, {"electrical": 8}),
    ("WP-ENT", "enterprise", "Enterprise crew (SYNTHETIC)", {"skilled": 28, "semi_skilled": 18, "labourer": 24, "operator": 4, "eq:crane": 1}, {"foreman": 5, "supervisor": 3, "engineer": 3, "qc": 3, "hse": 3}, 1, None, "92", "95", "6", 6, {"electrical": 12}),
]
ROLE_DAY_COST = {"skilled": 220, "semi_skilled": 160, "labourer": 110, "operator": 240, "foreman": 300, "supervisor": 320, "engineer": 520, "qc": 380, "hse": 340, "sub:electrical": 250}

SUPPLIERS = {
    "A": dict(name="SYNTHETIC Supplier A (fictional)", valid_days=14, delivery_included="Yes", rates={"SYN-C-045": "96000", "SYN-C-046": "540", "SYN-C-047": "15800"}),
    "B": dict(name="SYNTHETIC Supplier B (fictional)", valid_days=21, delivery_included="No", rates={"SYN-C-045": "91000", "SYN-C-046": "530", "SYN-C-047": "15100"}),
    "C": dict(name="SYNTHETIC Supplier C (fictional)", valid_days=7, delivery_included="Yes", rates={"SYN-C-045": "99000", "SYN-C-046": "520", "SYN-C-047": "14900"}),
}
DELIVERY_ADJ_B = "21500"
QUOTE_QTY = {"SYN-C-045": 2, "SYN-C-046": 80, "SYN-C-047": 4}
EXPECTED_QUOTE_TOTALS = {"A": "298400", "B": "284800", "C": "299200"}        # hand-computed headline totals (independent of the application)
EXPECTED_EVALUATED = {"A": "298400", "B": "306300", "C": "299200"}

INDIRECT_ELIGIBILITY = {"default": "exclude", "rules": [{"cost_prefix": "A", "eligible_pct": 0, "note": "preliminaries and plant are BOQ lines"}, {"cost_prefix": "B", "eligible_pct": 100},
                                                        {"cost_prefix": "C", "eligible_pct": 100}, {"cost_prefix": "E", "eligible_pct": 100}, {"cost_prefix": "G", "eligible_pct": 100},
                                                        {"cost_prefix": "H", "eligible_pct": 100}, {"cost_prefix": "I", "eligible_pct": 100}]}

DOCS = [   # doc_ref, type, title, revision, status
    ("ITT-001", "contract", "Invitation to tender and instructions (FICTIONAL)", "0", "Current"),
    ("COND-001", "contract", "Conditions of contract (FICTIONAL)", "0", "Current"),
    ("BOQ-001", "boq", "Bill of quantities (FICTIONAL)", "1", "Current"),
    ("SPEC-PIPE-001", "specification", "Piping specification (FICTIONAL)", "0", "Current"),
    ("SPEC-ST-001", "specification", "Structural steel and concrete specification (FICTIONAL)", "0", "Current"),
    ("SPEC-EL-001", "specification", "Electrical specification (FICTIONAL)", "0", "Current"),
    ("DWG-PR-001", "drawing", "Process piping layout (FICTIONAL)", "B", "Current"),
    ("DWG-ST-001", "drawing", "Pipe-rack foundations (FICTIONAL)", "B", "Current"),
    ("GEO-001", "geotechnical", "Geotechnical factual report (FICTIONAL)", "0", "Current"),
    ("FORM-001", "client_form", "Price schedule form (FICTIONAL)", "0", "Current"),
    ("DWG-EL-010", "drawing", "Earthing layout (FICTIONAL)", "-", "Missing"),
]
SYN_RESPONSES = {   # detector key prefix -> (response text, cost impact text)
    "AMBIG:C-013": "SYNTHETIC CUSTOMER RESPONSE: the 120 m3 of hard-material excavation is a firm quantity; no further allowance is intended.",
    "AMBIG:C-055": "SYNTHETIC CUSTOMER RESPONSE: the customer provides the tie-in flanges; the contractor supplies and installs three (not two) tie-in assemblies.",
    "MISSDOC:DWG-EL-010": "SYNTHETIC CUSTOMER RESPONSE: drawing DWG-EL-010 revision A is issued with this reply.",
    "CONFLICT:quality plan required": "SYNTHETIC CUSTOMER RESPONSE: a project quality plan IS required; the specification governs over the letter.",
}
