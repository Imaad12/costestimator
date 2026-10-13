"""Generate data/mto/templates.json: STRUCTURE ONLY material-take-off templates (driver + resource slots).
No factor, rate or productivity value is included - every number is entered by the user as a governed `mto_factor` parameter and approved.
Run: python scripts/gen_mto_templates.py"""
import json
from pathlib import Path

T = []


def t(code, discipline, name, driver_unit, driver_desc, slots, record="", note=""):
    T.append(dict(code=code, discipline=discipline, name=name, driver_unit=driver_unit, driver_description=driver_desc, capability=record, note=note,
                  slots=[dict(slot=s[0], description=s[1], resource_type=s[2], unit_dim=s[3]) for s in slots]))


HR, KG, M, M2, M3, NR, L, T_ = "time_hr", "mass", "length", "area", "volume", "count", "volume", "mass"
LAB, MAT, PLT, EQP, SUB = "labour", "material", "plant", "equipment", "subcontract"

t("piping.pipe_fab_install", "Process piping", "Pipe fabrication and erection (per inch-diameter)", "inch_dia",
  "Inch-diameter of pipe fabricated/erected, measured by the estimator from the piping MTO", [
      ("fab_labour", "Fabrication labour hours per inch-dia", LAB, HR), ("erect_labour", "Erection labour hours per inch-dia", LAB, HR),
      ("fit_up_labour", "Fit-up / alignment labour hours per inch-dia", LAB, HR), ("pipe_material", "Pipe material per inch-dia (length basis)", MAT, M),
      ("welding_consumables", "Welding consumables per inch-dia", MAT, KG), ("crane_plant", "Mobile crane / handling plant hours per inch-dia", PLT, HR)], "PRC-01")
t("piping.weld_joint", "Process piping", "Welds (per joint)", "joint", "Number of welded joints counted from the piping MTO", [
    ("welder_labour", "Welder hours per joint", LAB, HR), ("fitter_labour", "Fitter hours per joint", LAB, HR), ("consumables", "Welding consumables per joint", MAT, KG),
    ("ndt", "NDT services per joint", SUB, NR), ("pwht", "Post-weld heat treatment per joint", SUB, NR), ("grinding_labour", "Grinding/finishing hours per joint", LAB, HR)], "PRC-01")
t("piping.spool", "Process piping", "Spool fabrication / handling (per spool)", "spool", "Number of spools on the isometric register", [
    ("shop_labour", "Shop fabrication hours per spool", LAB, HR), ("blast_paint", "Blast and paint per spool", SUB, NR), ("transport", "Transport per spool", SUB, NR),
    ("handling_plant", "Handling plant hours per spool", PLT, HR)], "PRC-01 PRC-13")
t("piping.supports", "Process piping", "Pipe supports (per tonne)", "t", "Tonnes of pipe support steel", [
    ("fab_labour", "Support fabrication hours per tonne", LAB, HR), ("install_labour", "Support installation hours per tonne", LAB, HR), ("steel", "Support steel per tonne", MAT, KG),
    ("paint", "Support painting per tonne", SUB, NR)], "PRC-01")
t("piping.valve_install", "Process piping", "Valves and in-line items (per item)", "nr", "Number of valves/in-line items on the piping MTO", [
    ("install_labour", "Installation hours per valve", LAB, HR), ("gaskets_bolting", "Gaskets and bolting sets per valve", MAT, NR), ("test_labour", "Leak-test hours per valve", LAB, HR)], "PRC-01")
t("piping.hydrotest", "Process piping", "Hydrotest and flushing (per system)", "nr", "Number of test packs / systems", [
    ("test_labour", "Test crew hours per pack", LAB, HR), ("test_water", "Test water per pack", MAT, M3), ("test_equipment", "Test pump / temporary spools per pack", EQP, NR)], "PRC-01")
t("equipment.set_and_align", "Process equipment", "Equipment set, level and align (per item)", "nr", "Number of equipment items to set", [
    ("rigging_labour", "Rigging hours per item", LAB, HR), ("fitters_labour", "Fitting / alignment hours per item", LAB, HR), ("crane_plant", "Crane hours per item", PLT, HR),
    ("grout_material", "Grout per item", MAT, M3), ("vendor_rep", "Vendor representative services per item", SUB, NR)], "PRC-02")
t("instrument.loop", "Instrumentation", "Instrument loop (per loop)", "loop", "Number of loops on the instrument index", [
    ("install_labour", "Instrument installation hours per loop", LAB, HR), ("cable_pull", "Cable supply per loop", MAT, M), ("tubing", "Tubing and fittings per loop", MAT, M),
    ("loop_check", "Loop-check hours per loop", LAB, HR), ("calibration", "Calibration hours per loop", LAB, HR), ("jb_glands", "Junction box / glands per loop", MAT, NR),
    ("dcs_config", "DCS/PLC configuration hours per loop", SUB, HR)], "PRC-03")
t("electrical.cable", "Industrial electrical", "Cable supply, pulling and termination (per metre)", "m", "Metres of cable measured by the estimator from the cable schedule", [
    ("cable_material", "Cable per metre (allowing for the estimator's stated cut-length basis)", MAT, M), ("pull_labour", "Pulling hours per metre", LAB, HR),
    ("tray_labour", "Tray/support hours per metre", LAB, HR), ("pull_plant", "Cable-pulling plant hours per metre", PLT, HR)], "PRC-04")
t("electrical.termination", "Industrial electrical", "Cable terminations (per termination)", "nr", "Number of terminations from the cable schedule", [
    ("term_labour", "Termination hours each", LAB, HR), ("lugs_glands", "Lugs and glands each", MAT, NR), ("test_labour", "Insulation/continuity test hours each", LAB, HR)], "PRC-04")
t("steel.structural", "Structural steel", "Structural steel (per tonne)", "t", "Tonnes of structural steel from the steel MTO", [
    ("fab_labour", "Fabrication hours per tonne", LAB, HR), ("erect_labour", "Erection hours per tonne", LAB, HR), ("steel_material", "Steel per tonne (allowing for the stated waste basis)", MAT, KG),
    ("bolts", "Bolts and fixings per tonne", MAT, KG), ("blast_area", "Blast and paint area per tonne", SUB, M2), ("crane_plant", "Crane hours per tonne", PLT, HR)], "PRC-05")
t("tank.field_erected", "Tanks and large vessels", "Field-erected tank plate (per tonne)", "t", "Tonnes of tank plate/steelwork", [
    ("weld_labour", "Welding hours per tonne", LAB, HR), ("fitup_labour", "Fit-up and rigging hours per tonne", LAB, HR), ("ndt_length", "NDT weld length per tonne", SUB, M),
    ("test_water", "Hydrotest water per tonne", MAT, M3), ("crane_plant", "Crane hours per tonne", PLT, HR), ("settlement_survey", "Settlement survey services per tonne", SUB, NR)], "PRC-06")
t("coating.surface", "Coatings and fireproofing", "Surface preparation and coating system (per m2)", "m2", "Surface area measured by the estimator", [
    ("blast_labour", "Blasting hours per m2", LAB, HR), ("primer", "Primer per m2", MAT, L), ("intermediate", "Intermediate coat per m2", MAT, L), ("topcoat", "Top coat per m2", MAT, L),
    ("apply_labour", "Coating application hours per m2", LAB, HR), ("blast_media", "Abrasive media per m2", MAT, KG), ("inspection", "Coating inspection services per m2", SUB, NR)], "PRC-07")
t("coating.fireproofing", "Coatings and fireproofing", "Fireproofing (per m2)", "m2", "Fireproofed surface area measured by the estimator", [
    ("material", "Fireproofing material per m2", MAT, KG), ("apply_labour", "Application hours per m2", LAB, HR), ("mesh_fixings", "Mesh and fixings per m2", MAT, M2)], "PRC-07")
t("insulation.surface", "Thermal insulation", "Insulation and cladding (per m2)", "m2", "Insulated surface area measured by the estimator", [
    ("insulation", "Insulation material per m2 (thickness set in the factor basis)", MAT, M3), ("cladding", "Cladding sheet per m2", MAT, M2), ("fixings", "Bands, screws, sealant per m2", MAT, NR),
    ("install_labour", "Installation hours per m2", LAB, HR)], "PRC-08")
t("scaffold.volume", "Scaffolding", "Scaffolding (per m3 of scaffold)", "m3", "Scaffold volume from the scaffold plan (estimator-measured)", [
    ("erect_labour", "Erection hours per m3", LAB, HR), ("dismantle_labour", "Dismantling hours per m3", LAB, HR), ("hire_material", "Scaffold hire per m3 (period set by the programme)", EQP, NR),
    ("inspection", "Scaffold inspection per m3", SUB, NR)], "PRC-09")
t("lifting.heavy_lift", "Heavy lifting", "Heavy lifts (per lift)", "nr", "Number of lifts on the lift register", [
    ("crane_hire", "Crane hire days per lift", PLT, HR), ("rigging_labour", "Rigging crew hours per lift", LAB, HR), ("engineering", "Lift study / engineering per lift", SUB, NR),
    ("mobilisation", "Mobilisation / demobilisation per lift", SUB, NR)], "PRC-10")
t("services.specialist", "Specialist industrial services", "Specialist services (per unit of work)", "nr", "Number of service units (e.g. CP stations, NDT campaigns, hazardous-area packages)", [
    ("service_cost", "Specialist service per unit", SUB, NR), ("support_labour", "Own-labour support hours per unit", LAB, HR), ("support_material", "Consumables per unit", MAT, NR)], "PRC-11")
t("turnaround.tie_in", "Shutdown and brownfield", "Tie-ins / shutdown work (per tie-in)", "nr", "Number of tie-in points", [
    ("labour", "Labour hours per tie-in", LAB, HR), ("permits_isolation", "Permit / isolation / supervision hours per tie-in", LAB, HR), ("materials", "Materials per tie-in", MAT, NR),
    ("standby_plant", "Standby plant hours per tie-in", PLT, HR)], "PRC-12")
t("module.prefabricated", "Modularisation", "Prefabricated modules (per module)", "nr", "Number of modules", [
    ("yard_labour", "Yard fabrication hours per module", LAB, HR), ("transport", "Transport per module", SUB, NR), ("site_set", "Site setting hours per module", LAB, HR),
    ("lift_plant", "Heavy-lift plant hours per module", PLT, HR)], "PRC-13")
t("temp.site_establishment", "Temporary facilities and remote site", "Site establishment (per person on site)", "nr", "Peak persons on site (from the loading histogram) or the estimator's stated figure", [
    ("camp_accommodation", "Accommodation per person", SUB, NR), ("catering", "Catering per person", SUB, NR), ("transport", "Personnel transport per person", SUB, NR),
    ("welfare_ppe", "Welfare / PPE per person", MAT, NR), ("admin_support", "Site admin support hours per person", LAB, HR)], "IND-02 PRC-14")
t("commissioning.system", "Commissioning and start-up", "Pre-commissioning / commissioning (per system)", "nr", "Number of systems on the completion/commissioning matrix", [
    ("precomm_labour", "Pre-commissioning hours per system", LAB, HR), ("comm_labour", "Commissioning hours per system", LAB, HR), ("vendor_support", "Vendor commissioning services per system", SUB, NR),
    ("consumables", "Commissioning consumables per system", MAT, NR), ("spares", "Commissioning spares per system", MAT, NR)], "CLO-01")
t("handover.documentation", "Close-out", "Handover documentation and training (per system)", "nr", "Number of systems handed over", [
    ("doc_labour", "Documentation hours per system", LAB, HR), ("training", "Training services per system", SUB, NR), ("om_manuals", "O&M manual production per system", SUB, NR)], "CLO-02")

out = Path(__file__).resolve().parent.parent / "data" / "mto" / "templates.json"
out.write_text(json.dumps({"schema": "ksa-estimator/mto-templates/1",
                           "note": "STRUCTURE ONLY. No factors, no rates, no standards are included; factors are governed parameters supplied and approved by the company.",
                           "templates": T}, indent=1), encoding="utf-8")
print(len(T), "templates;", sum(len(x["slots"]) for x in T), "slots ->", out)
