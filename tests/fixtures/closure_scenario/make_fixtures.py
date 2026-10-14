"""One-off generator of the SYNTHETIC BOQ fixture for 'Dammam Industrial Utilities - Synthetic Tender Closure'. Every quantity, rate and name is fictional test data.
Run: python tests/fixtures/closure_scenario/make_fixtures.py   (rewrites boq_SYNTHETIC_TEST_ONLY.csv and lines_SYNTHETIC.json)"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
# item, description, trade, unit, qty, cost_code, resource type, synthetic installed rate (None = NO RATE on purpose), drawing, spec, revision
L = [
 ("C-001", "Mobilisation and demobilisation", "preliminaries", "ls", 1, "A.01", "subcontract", 85000, "", "", "1"),
 ("C-002", "Site management and supervision (monthly)", "preliminaries", "month", 5, "A.02", "subcontract", 42000, "", "", "1"),
 ("C-003", "Temporary facilities and site utilities", "preliminaries", "ls", 1, "A.03", "subcontract", 36000, "", "", "1"),
 ("C-004", "HSE provisions and PPE", "preliminaries", "ls", 1, "A.04", "material", 18000, "", "", "1"),
 ("C-010", "Excavation for pipe trench", "civil", "m3", 850, "B.02", "subcontract", 38, "DWG-CV-001", "SPEC-CV-001", "A"),
 ("C-011", "Backfill with approved material", "civil", "m3", 640, "B.03", "subcontract", 52, "DWG-CV-001", "SPEC-CV-001", "A"),
 ("C-012", "Pipe trench shoring", "civil", "m", 400, "B.04", "subcontract", 46, "DWG-CV-001", "SPEC-CV-001", "A"),
 ("C-013", "Excavation in hard material (quantity approximate, as required)", "civil", "m3", 120, "B.02", "subcontract", 165, "DWG-CV-001", "SPEC-CV-001", "A"),
 ("C-014", "Road reinstatement", "civil", "m2", 180, "B.05", "subcontract", 210, "DWG-CV-002", "SPEC-CV-001", "A"),
 ("C-020", "Pipe-rack foundations RC", "structural", "m3", 96, "C.01", "subcontract", 1450, "DWG-ST-001", "SPEC-ST-001", "B"),
 ("C-021", "Formwork to pipe-rack foundations", "structural", "m2", 410, "C.02", "subcontract", 118, "DWG-ST-001", "SPEC-ST-001", "B"),
 ("C-022", "Reinforcement steel supply and fix", "structural", "kg", 11500, "C.03", "subcontract", 6.4, "DWG-ST-001", "SPEC-ST-001", "B"),
 ("C-023", "Pipe-rack structural steel supply and erect", "structural", "kg", 28000, "C.04", "subcontract", 14.8, "DWG-ST-002", "SPEC-ST-001", "B"),
 ("C-024", "Anchor bolts and base plates", "structural", "nr", 120, "C.05", "material", 265, "DWG-ST-002", "SPEC-ST-001", "B"),
 ("C-025", "Concrete equipment plinths", "structural", "m3", 14, "C.01", "subcontract", 1650, "DWG-ST-003", "SPEC-ST-001", "B"),
 ("C-030", "Carbon steel pipe DN100 supply", "piping", "m", 520, "E.06", "material", 330, "DWG-PR-001", "SPEC-PIPE-001", "B"),
 ("C-031", "Carbon steel pipe DN50 supply", "piping", "m", 310, "E.06", "material", 190, "DWG-PR-001", "SPEC-PIPE-001", "B"),
 ("C-032", "Pipe fabrication and installation DN100", "piping", "inch_dia", 5200, "E.06", "subcontract", 38, "DWG-PR-001", "SPEC-PIPE-001", "B"),
 ("C-033", "Pipe fabrication and installation DN50", "piping", "inch_dia", 1550, "E.06", "subcontract", 36, "DWG-PR-001", "SPEC-PIPE-001", "B"),
 ("C-034", "Gate valve DN100 supply", "piping", "nr", 14, "E.06", "material", 1480, "DWG-PR-002", "SPEC-PIPE-001", "B"),
 ("C-035", "Check valve DN100 supply", "piping", "nr", 8, "E.06", "material", 1890, "DWG-PR-002", "SPEC-PIPE-001", "B"),
 ("C-036", "Flange, gasket and bolt sets", "piping", "set", 96, "E.06", "material", 410, "DWG-PR-002", "SPEC-PIPE-001", "B"),
 ("C-037", "Butt welding of pipe joints", "piping", "joint", 640, "E.06", "subcontract", 215, "DWG-PR-001", "SPEC-PIPE-001", "B"),
 ("C-038", "Weld radiography (sample)", "piping", "joint", 130, "E.06", "subcontract", 175, "DWG-PR-001", "SPEC-PIPE-001", "B"),
 ("C-039", "Hydrostatic test and flushing of pipework", "piping", "nr", 6, "E.06", "subcontract", 9200, "DWG-PR-001", "SPEC-PIPE-001", "B"),
 ("C-040", "Pipe supports, fabricated steel", "piping", "kg", 6400, "E.06", "material", 26, "DWG-PR-003", "SPEC-PIPE-001", "B"),
 ("C-041", "Corrosion protection coating system", "piping", "m2", 1900, "E.06", "subcontract", 68, "DWG-PR-001", "SPEC-PIPE-001", "B"),
 ("C-045", "Transfer pump skid supply (long lead)", "mechanical", "nr", 2, "E.08", "material", None, "DWG-ME-001", "SPEC-ME-001", "A"),
 ("C-046", "Stainless steel pipe DN100 supply", "piping", "m", 80, "E.06", "material", None, "DWG-PR-001", "SPEC-PIPE-001", "B"),
 ("C-047", "Pneumatic control valve DN100 supply", "piping", "nr", 4, "E.06", "material", None, "DWG-PR-002", "SPEC-PIPE-001", "B"),
 ("C-050", "Mobile crane 50t hire (BOQ days)", "plant", "day", 10, "A.05", "plant", 2800, "", "", "1"),
 ("C-051", "Telehandler hire (BOQ days)", "plant", "day", 14, "A.05", "plant", 950, "", "", "1"),
 ("C-052", "Scaffolding access hire", "plant", "week", 6, "A.05", "plant", 7400, "", "", "1"),
 ("C-055", "Fire water tie-in to existing ring main by others (interface to be confirmed)", "fire", "nr", 2, "G.02", "subcontract", 14500, "DWG-FP-001", "SPEC-FP-001", "A"),
 ("C-056", "Fire hydrant assembly", "fire", "nr", 4, "G.02", "material", 8900, "DWG-FP-001", "SPEC-FP-001", "A"),
 ("C-060", "LV distribution board", "electrical", "nr", 3, "H.03", "material", 31500, "DWG-EL-001", "SPEC-EL-001", "A"),
 ("C-061", "LV armoured power cable supply and install", "electrical", "m", 2400, "H.03", "subcontract", 78, "DWG-EL-001", "SPEC-EL-001", "A"),
 ("C-062", "Cable tray and supports", "electrical", "m", 900, "H.03", "subcontract", 96, "DWG-EL-001", "SPEC-EL-001", "A"),
 ("C-063", "Earthing and lightning protection", "electrical", "ls", 1, "H.03", "subcontract", 64000, "DWG-EL-010", "SPEC-EL-001", "A"),
 ("C-064", "Lighting poles and luminaires", "electrical", "nr", 24, "H.03", "material", 4200, "DWG-EL-001", "SPEC-EL-001", "A"),
 ("C-070", "Fibre optic backbone", "elv", "m", 1200, "I.01", "subcontract", 44, "DWG-IT-001", "SPEC-IT-001", "A"),
 ("C-071", "CCTV cameras", "elv", "nr", 12, "I.03", "material", 3600, "DWG-IT-001", "SPEC-IT-001", "A"),
 ("C-071", "CCTV cameras", "elv", "nr", 14, "I.03", "material", 3600, "DWG-IT-001", "SPEC-IT-001", "A"),            # duplicate item code with a different quantity (BOQ discrepancy)
 ("C-072", "Access control readers", "elv", "nr", 8, "I.02", "material", 2100, "DWG-IT-001", "SPEC-IT-001", "A"),
]
cols = ["item", "description", "trade", "unit", "qty", "cost_code", "rtype", "rate", "drawing", "spec", "revision"]
(HERE / "lines_SYNTHETIC.json").write_text(json.dumps([dict(zip(cols, r)) for r in L], indent=1), encoding="utf-8")
with open(HERE / "boq_SYNTHETIC_TEST_ONLY.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["SYNTHETIC / TEST ONLY / NOT A MARKET QUOTE - Dammam Industrial Utilities (fictional customer); measured quantities are fictional fixture values"])
    w.writerow(["Item", "Description", "Trade", "Unit", "Qty", "Rate", "Cost Code", "Drawing", "Spec", "Rev"])
    for r in L:
        w.writerow([r[0], r[1], r[2], r[3], r[4], "", r[5], r[8], r[9], r[10]])
print(len(L), "lines")
