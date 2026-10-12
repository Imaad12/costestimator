"""SYNTHETIC / DEMO / NOT A MARKET QUOTE - every figure below is an invented round number for demonstration and testing only."""
from __future__ import annotations

TAG = "SYNTHETIC / DEMO / NOT A MARKET QUOTE"

# id, type, description, unit, cost_code, rate (None = deliberately MISSING), rate unit (None = same), status ('approved'|'pending'|'expired'|None), extra
RESOURCES = [
    ("DEMO-MAT-001", "material", "Selected fill material, compacted [DEMO]", "m3", "B.03", "30", None, "approved"),
    ("DEMO-MAT-002", "material", "Precast concrete kerb 150x300 [DEMO]", "m", "B.05", "45", None, "approved"),
    ("DEMO-MAT-003", "material", "Ready-mix concrete C35 [DEMO]", "m3", "C.01", "320", None, "approved"),
    ("DEMO-MAT-004", "material", "Reinforcement steel B500 [DEMO]", "kg", "C.03", "3400", "t", "approved"),     # priced per tonne, used in kg
    ("DEMO-MAT-005", "material", "Formwork system and plywood [DEMO]", "m2", "C.02", "40", None, "approved"),
    ("DEMO-MAT-006", "material", "Hollow concrete block 200mm [DEMO]", "nr", "D.01", "3.5", None, "approved"),
    ("DEMO-MAT-007", "material", "Cement-sand mortar [DEMO]", "m3", "D.01", "250", None, "approved"),
    ("DEMO-MAT-008", "material", "Emulsion paint [DEMO]", "l", "D.07", "18", None, "approved"),
    ("DEMO-MAT-009", "material", "Ceramic floor tile 600x600 [DEMO]", "m2", "D.06", "55", None, "pending"),    # unapproved rate
    ("DEMO-MAT-011", "material", "PPR pipe 32mm PN20 [DEMO]", "m", "F.01", "14", None, "approved"),
    ("DEMO-MAT-012", "material", "WC set complete [DEMO]", "nr", "F.03", "450", None, "approved"),
    ("DEMO-MAT-013", "material", "LV cable 4C x 16mm2 [DEMO]", "m", "H.06", "38", None, "approved"),
    ("DEMO-MAT-014", "material", "Cable tray 300mm [DEMO]", "m", "H.07", "55", None, "expired"),              # expired rate
    ("DEMO-MAT-015", "material", "Black steel pipe 50mm for sprinklers [DEMO]", "m", "G.01", "62", None, "approved"),
    ("DEMO-MAT-016", "material", "Sprinkler head, pendant [DEMO]", "nr", "G.01", None, None, None),             # MISSING
    ("DEMO-MAT-017", "material", "Cat6A U/FTP cable [DEMO]", "m", "I.01", "4.5", None, "approved"),
    ("DEMO-EQP-001", "equipment", "Air handling unit 5000 l/s [DEMO]", "nr", "E.02", None, None, None),          # MISSING
    ("DEMO-EQP-002", "equipment", "LED luminaire, recessed [DEMO]", "nr", "H.09", "220", None, "approved"),
    ("DEMO-EQP-003", "equipment", "CCTV IP camera [DEMO]", "nr", "I.03", None, None, None),                      # MISSING
    ("DEMO-SUB-001", "subcontract", "HVAC ductwork supply and install subcontract, per m2 [DEMO]", "m2", "E.04", "150", None, "approved"),
    ("DEMO-SUB-002", "subcontract", "Passenger lift 8 stops, supply, install, test [DEMO]", "set", "J.01", None, None, None),   # MISSING -> RFQ
    ("DEMO-PLT-002", "plant", "Tipper truck 15 m3, hourly [DEMO]", "hr", "B.03", "120", None, "approved"),
    ("DEMO-LAB-004", "labour", "Steel fixer [DEMO]", "hr", "C.03", "15", None, "approved"),
    ("DEMO-LAB-003", "labour", "Carpenter [DEMO]", "hr", "C.02", "16", None, "approved"),
    ("DEMO-LAB-005", "labour", "Mason [DEMO]", "hr", "D.01", "17", None, "approved"),
    ("DEMO-LAB-006", "labour", "Plumber [DEMO]", "hr", "F.01", "18", None, "approved"),
    ("DEMO-LAB-007", "labour", "Electrician [DEMO]", "hr", "H.06", "16", None, "approved"),
    ("DEMO-LAB-008", "labour", "Sprinkler fitter [DEMO]", "hr", "G.01", "17", None, "approved"),
    ("DEMO-LAB-009", "labour", "ELV technician [DEMO]", "hr", "I.01", "15", None, "approved"),
    ("DEMO-LAB-010", "labour", "Painter [DEMO]", "hr", "D.07", "14", None, "approved"),
    ("DEMO-LAB-011", "labour", "HVAC technician [DEMO]", "hr", "E.02", "18", None, "approved"),
]
# labour / plant with build-up components (rate derived deterministically)
LABOUR_BUILDUP = {  # id: components
    "DEMO-LAB-001": dict(desc="General labourer [DEMO]", cc="B.03", comps={"monthly_base_wage": "1800", "allowances_monthly": "400", "accommodation_monthly": "300",
                                                                           "transport_monthly": "150", "employer_costs_monthly": "250", "normal_hours_per_month": "208",
                                                                           "overtime_multiplier": "1.5"}),
    "DEMO-LAB-002": dict(desc="Foreman [DEMO]", cc="C.01", comps={"monthly_base_wage": "3500", "allowances_monthly": "600", "accommodation_monthly": "300",
                                                                  "transport_monthly": "150", "employer_costs_monthly": "400", "normal_hours_per_month": "208",
                                                                  "overtime_multiplier": "1.5"}),
}
PLANT_BUILDUP = {
    "DEMO-PLT-001": dict(desc="Excavator 20t with operator and fuel [DEMO]", cc="B.02", comps={
        "hire_rate": "600", "hire_basis": "day", "hours_per_day": "8", "operator_hourly": "25", "fuel_litres_per_hour": "12",
        "fuel_price_per_litre": "2", "maintenance_pct_of_hire": "5", "mobilisation_lump": "800", "demobilisation_lump": "800"}),
}


def L(t, rid, factor, **kw):
    return dict(line_type=t, resource_id=rid, factor=str(factor), **kw)


# code, description, unit, cost_code, lines
ASSEMBLIES = [
    ("DEMO-A-EXC", "Bulk excavation and disposal per m3 [DEMO]", "m3", "B.02", [
        L("plant", "DEMO-PLT-001", "0.05", utilisation_basis="assumption", utilisation_ref="ASMP-E-003"),
        L("plant", "DEMO-PLT-002", "0.08"),
        L("labour", "DEMO-LAB-001", "0.03", productivity_basis="paid_hours_per_unit")]),
    ("DEMO-A-FILL", "Backfill with selected fill per m3 [DEMO]", "m3", "B.03", [
        L("material", "DEMO-MAT-001", "1.2", factor_includes_waste=1),
        L("labour", "DEMO-LAB-001", "0.1", productivity_basis="paid_hours_per_unit")]),
    ("DEMO-A-KERB", "Precast kerb per m [DEMO]", "m", "B.05", [
        L("material", "DEMO-MAT-002", "1", waste_basis="fixed_pct", waste_value="2"),
        L("labour", "DEMO-LAB-001", "0.2", productivity_basis="paid_hours_per_unit")]),
    ("DEMO-A-RC", "Reinforced concrete, concrete and pour labour only, per m3 [DEMO]", "m3", "C.01", [
        L("material", "DEMO-MAT-003", "1", waste_basis="assumption", waste_ref="ASMP-C-003"),
        L("labour", "DEMO-LAB-001", "12", productivity_basis="output_per_crew_shift",
          crew=[{"resource_id": "DEMO-LAB-001", "count": 3}, {"resource_id": "DEMO-LAB-002", "count": 1}])]),
    ("DEMO-A-REBAR", "Reinforcement supply and fix per tonne [DEMO]", "t", "C.03", [
        L("material", "DEMO-MAT-004", "1000", waste_basis="assumption", waste_ref="ASMP-C-004"),
        L("labour", "DEMO-LAB-004", "14", productivity_basis="paid_hours_per_unit")]),
    ("DEMO-A-FORM", "Formwork per m2 contact area [DEMO]", "m2", "C.02", [
        L("material", "DEMO-MAT-005", "0.5", factor_includes_waste=1),
        L("labour", "DEMO-LAB-003", "0.8", productivity_basis="paid_hours_per_unit")]),
    ("DEMO-A-BLK", "Blockwork 200mm per m2 [DEMO]", "m2", "D.01", [
        L("material", "DEMO-MAT-006", "12.5", waste_basis="assumption", waste_ref="ASMP-C-005"),
        L("material", "DEMO-MAT-007", "0.02", waste_basis="assumption", waste_ref="ASMP-C-008"),
        L("labour", "DEMO-LAB-005", "0.5", productivity_basis="paid_hours_per_unit"),
        L("labour", "DEMO-LAB-001", "0.3", productivity_basis="paid_hours_per_unit")]),
    ("DEMO-A-PNT", "Emulsion painting, 3 coats, per m2 [DEMO]", "m2", "D.07", [
        L("material", "DEMO-MAT-008", "0.25", waste_basis="assumption", waste_ref="ASMP-C-007"),
        L("labour", "DEMO-LAB-010", "0.15", productivity_basis="paid_hours_per_unit")]),
    ("DEMO-A-TILE", "Ceramic floor tiling per m2 [DEMO]", "m2", "D.06", [
        L("material", "DEMO-MAT-009", "1", waste_basis="assumption", waste_ref="ASMP-C-006"),
        L("labour", "DEMO-LAB-005", "0.6", productivity_basis="paid_hours_per_unit")]),
    ("DEMO-A-DUCT", "Ductwork supply and install (subcontract, all-in) per m2 [DEMO]", "m2", "E.04", [
        L("subcontract", "DEMO-SUB-001", "1", includes_labour=1, includes_material=1, includes_plant=1)]),
    ("DEMO-A-AHU", "AHU installation per nr [DEMO]", "nr", "E.02", [
        L("equipment", "DEMO-EQP-001", "1"),
        L("labour", "DEMO-LAB-011", "16", productivity_basis="paid_hours_per_unit")]),
    ("DEMO-A-PPR", "PPR pipework per m [DEMO]", "m", "F.01", [
        L("material", "DEMO-MAT-011", "1", waste_basis="assumption", waste_ref="ASMP-C-010"),
        L("labour", "DEMO-LAB-006", "0.25", productivity_basis="paid_hours_per_unit")]),
    ("DEMO-A-WC", "WC set installation per nr [DEMO]", "nr", "F.03", [
        L("material", "DEMO-MAT-012", "1"),
        L("labour", "DEMO-LAB-006", "3", productivity_basis="paid_hours_per_unit")]),
    ("DEMO-A-CABLE", "LV cable installation per m [DEMO]", "m", "H.06", [
        L("material", "DEMO-MAT-013", "1", waste_basis="assumption", waste_ref="ASMP-C-012"),
        L("labour", "DEMO-LAB-007", "0.1", productivity_basis="paid_hours_per_unit")]),
    ("DEMO-A-TRAY", "Cable tray installation per m [DEMO]", "m", "H.07", [
        L("material", "DEMO-MAT-014", "1"),
        L("labour", "DEMO-LAB-007", "0.25", productivity_basis="paid_hours_per_unit")]),
    ("DEMO-A-LUM", "Lighting point per nr [DEMO]", "nr", "H.09", [
        L("equipment", "DEMO-EQP-002", "1"),
        L("labour", "DEMO-LAB-007", "1.5", productivity_basis="paid_hours_per_unit")]),
    ("DEMO-A-SPPIPE", "Sprinkler pipework per m [DEMO]", "m", "G.01", [
        L("material", "DEMO-MAT-015", "1", waste_basis="assumption", waste_ref="ASMP-C-010"),
        L("labour", "DEMO-LAB-008", "0.4", productivity_basis="paid_hours_per_unit")]),
    ("DEMO-A-SPHEAD", "Sprinkler head per nr [DEMO]", "nr", "G.01", [
        L("material", "DEMO-MAT-016", "1"),
        L("labour", "DEMO-LAB-008", "0.5", productivity_basis="paid_hours_per_unit")]),
    ("DEMO-A-CAT6", "Cat6A cabling per m [DEMO]", "m", "I.01", [
        L("material", "DEMO-MAT-017", "1", waste_basis="assumption", waste_ref="ASMP-C-012"),
        L("labour", "DEMO-LAB-009", "0.08", productivity_basis="paid_hours_per_unit")]),
    ("DEMO-A-CCTV", "CCTV camera install per nr [DEMO]", "nr", "I.03", [
        L("equipment", "DEMO-EQP-003", "1"),
        L("labour", "DEMO-LAB-009", "2", productivity_basis="paid_hours_per_unit")]),
]

# BOQ rows: (code, description, unit, qty, trade, assembly or special)
HEAD = "H"
BOQ = [
    ("1", "CIVIL WORKS", None, None, "Civil", HEAD),
    ("1.1", "Bulk excavation, cart away and dispose", "m3", "2500", "Civil", "DEMO-A-EXC"),
    ("1.2", "Backfill with approved selected fill, compacted", "m3", "1200", "Civil", "DEMO-A-FILL"),
    ("1.3", "Precast concrete kerb 150x300", "m", "400", "Civil", "DEMO-A-KERB"),
    ("2", "STRUCTURAL WORKS", None, None, "Structural", HEAD),
    ("2.1", "Reinforced concrete C35 to foundations and slabs", "m3", "850", "Structural", "DEMO-A-RC"),
    ("2.2", "Reinforcement bars B500, supply and fix", "ton", "95", "Structural", "DEMO-A-REBAR"),     # ambiguous unit on purpose
    ("2.3", "Formwork to slabs and walls", "m2", "3400", "Structural", "DEMO-A-FORM"),
    ("3", "ARCHITECTURAL AND FINISHES", None, None, "Architecture", HEAD),
    ("3.1", "Blockwork 200mm thick internal walls", "m2", "2100", "Architecture", "DEMO-A-BLK"),
    ("3.2", "Emulsion paint, 3 coats, to plastered walls", "m2", "6500", "Architecture", "DEMO-A-PNT"),
    ("3.3", "Ceramic floor tiling 600x600", "m2", "1800", "Architecture", "DEMO-A-TILE"),
    (None, None, None, None, None, "BLANK"),                                                           # blank row
    ("4", "HVAC", None, None, "Mechanical", HEAD),
    ("4.1", "GI ductwork, supply and install, insulated", "m2", "950", "Mechanical", "DEMO-A-DUCT"),
    ("4.2", "Air handling unit 5000 l/s, supply, install, commission", "nr", "6", "Mechanical", "DEMO-A-AHU"),
    ("5", "PLUMBING AND PUBLIC HEALTH", None, None, "Plumbing", HEAD),
    ("5.1", "PPR cold water pipework 32mm", "m", "1200", "Plumbing", "DEMO-A-PPR"),
    ("5.2", "WC sets complete with cistern", "nr", "40", "Plumbing", "DEMO-A-WC"),
    ("6", "ELECTRICAL", None, None, "Electrical", HEAD),
    ("6.1", "LV cable 4Cx16mm2 installed", "m", "3500", "Electrical", "DEMO-A-CABLE"),
    ("6.2", "Cable tray 300mm, supply and install", "m", "900", "Electrical", "DEMO-A-TRAY"),
    ("6.3", "LED recessed luminaires, installed", "nr", "520", "Electrical", "DEMO-A-LUM"),
    ("7", "FIRE PROTECTION", None, None, "Fire", HEAD),
    ("7.1", "Sprinkler pipework 50mm black steel", "m", "2400", "Fire", "DEMO-A-SPPIPE"),
    ("7.2", "Pendant sprinkler heads", "nr", "760", "Fire", "DEMO-A-SPHEAD"),
    ("8", "ELV", None, None, "ELV", HEAD),
    ("8.1", "Cat6A U/FTP structured cabling", "m", "9000", "ELV", "DEMO-A-CAT6"),
    ("8.2", "IP CCTV cameras, installed and configured", "nr", "48", "ELV", "DEMO-A-CCTV"),
    ("9", "SPECIALIST, ALLOWANCES AND OTHERS", None, None, "Specialist", HEAD),
    ("9.1", "Passenger lift 8 stops, supply, install, test and commission", "set", "2", "Specialist", "SUBCON:DEMO-SUB-002"),
    ("9.2", "Provisional sum for testing and commissioning by others", "ls", "1", "General", "PSUM:150000"),
    ("9.3", "Prime cost sum for kitchen equipment", "ls", "1", "Specialist", "PCSUM:80000"),
    ("9.4", "External landscaping by others", "ls", "1", "Civil", "EXCLUDED"),
    ("9.5", "Temporary construction power connection", "ls", "1", "General", "UNPRICED"),
    ("6.1", "LV cable 4Cx25mm2 (duplicate item code in client file)", "m", "800", "Electrical", "DUP"),   # duplicate code
    ("9.6", "Allowance item with quantity to be advised", "item", "TBA", "General", "REJECT"),           # invalid quantity -> rejected row
]

SUPPLIERS = [("DEMO Supplier A [SYNTHETIC]", "supplier", "E,H,I,J"), ("DEMO Supplier B [SYNTHETIC]", "supplier", "E,G,I,J"),
             ("DEMO Supplier C [SYNTHETIC]", "supplier", "G,J")]

# engine keys / assumption values applied as SYNTHETIC project overrides (never changing the global library)
OVERRIDES = {
    "ASMP-D-001": ("8", "SYNTHETIC DEMO value: paid hours per shift"), "ASMP-D-002": ("6", "SYNTHETIC DEMO value"),
    "ASMP-D-003": ("6", "SYNTHETIC DEMO value"), "ASMP-D-004": ("26", "SYNTHETIC DEMO value"), "ASMP-D-005": ("8", "SYNTHETIC DEMO value"),
    "ASMP-E-003": ("80", "SYNTHETIC DEMO value: plant utilisation %"),
    "ASMP-C-003": ("3", "SYNTHETIC DEMO wastage % concrete"), "ASMP-C-004": ("3", "SYNTHETIC DEMO wastage % rebar"),
    "ASMP-C-005": ("5", "SYNTHETIC DEMO wastage % blocks"), "ASMP-C-006": ("8", "SYNTHETIC DEMO wastage % tiles"),
    "ASMP-C-007": ("5", "SYNTHETIC DEMO wastage % paint"), "ASMP-C-008": ("5", "SYNTHETIC DEMO wastage % mortar/plaster"),
    "ASMP-C-010": ("5", "SYNTHETIC DEMO wastage % pipe"), "ASMP-C-012": ("3", "SYNTHETIC DEMO wastage % cable"),
}

INDIRECTS = [  # code, category, description, method, amount, qty, allocation, target, in_subcontract
    ("IND-01", "Project management", "Project manager and construction manager [DEMO]", "per_month", "30000", "2", "pro_rata_direct", None, 0),
    ("IND-02", "Site supervision", "Site engineers and supervisors [DEMO]", "per_month", "18000", "4", "pro_rata_direct", None, 0),
    ("IND-03", "HSE", "HSE officer and safety provisions [DEMO]", "per_month", "9000", "1", "pro_rata_direct", None, 0),
    ("IND-04", "Insurance", "Contractor all-risk insurance [DEMO]", "percent_of_direct", "0.4", "1", "pro_rata_direct", None, 0),
    ("IND-05", "Site facilities", "Temporary offices and welfare (separate line) [DEMO]", "per_month", "25000", "1", "separate_line", None, 0),
    ("IND-06", "Security", "Site security (included in main-contractor subcontract package) [DEMO]", "per_month", "6000", "1", "pro_rata_direct", None, 1),
    ("IND-07", "Mobilisation", "Mobilisation and demobilisation [DEMO]", "fixed", "120000", "1", "separate_line", None, 0),
]
DURATION_MONTHS = "10"
POLICY = {"method": "markup", "markup_pct": "8", "margin_pct": "8", "default_tax_category": "VAT-STD",
          "contingency": {"pct": "3", "base": "direct_indirect"},
          "risk_items": [{"name": "Currency and supply-chain risk (SYNTHETIC)", "pct": "1", "base": "direct"}],
          "escalation": {"pct": "2", "base": "cost_before_escalation"}, "rounding": {"step": "1", "mode": "half_up"}, "rate_dp": 2}
