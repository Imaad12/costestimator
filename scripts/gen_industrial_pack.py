"""Generates data/packs/industrial/{cost_codes.csv,resources.csv,manifest.json}.  DEFINITIONS ONLY: no prices, no factors, no standards claims.
Specification fields are prompts for the project team ('to be confirmed per project'), exactly like the base catalogues.
Run: python scripts/gen_industrial_pack.py"""
import csv, json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "packs" / "industrial"
SUBS = [
 ("M.01", "Process piping"), ("M.02", "Valves and in-line items"), ("M.03", "Instrumentation and control systems"), ("M.04", "Industrial electrical power"),
 ("M.05", "Industrial structural steel and supports"), ("M.06", "Tanks, vessels and heat exchangers"), ("M.07", "Rotating and packaged equipment"),
 ("M.08", "Coatings and surface preparation"), ("M.09", "Insulation, heat tracing and fireproofing"), ("M.10", "Scaffolding and temporary access (industrial)"),
 ("M.11", "Heavy lifting, rigging and transport"), ("M.12", "Inspection, NDT and testing"), ("M.13", "Cathodic protection and corrosion control"),
 ("M.14", "Shutdown, turnaround and brownfield works"), ("M.15", "Modularisation and prefabrication"), ("M.16", "Pre-commissioning, commissioning and start-up"),
 ("M.17", "Engineering services"), ("M.18", "Home-office and project-management services"),
]
SPEC = "Attributes to confirm per project (material/grade, size, rating/class, standard, design conditions): __ ; source documents: __"
SUBSPEC = "Scope inclusions/exclusions, labour/material/plant inclusion, design responsibility, inspection and testing: to be defined in the RFQ"
LABSPEC = "Skill grade, trade test/certification (including any client or authority qualification), years of experience: to be confirmed per project"
NOTE_M = "Definition only: no price is held. Obtain a quotation or approved rate; no universal Saudi rate is assumed."
NOTE_L = "Rate build-up (base wage, allowances, accommodation, transport, employer/statutory costs) to be entered per project/company; no universal Saudi rate assumed"
R = []  # (type, code, category, description, unit)
def mat(code, cat, items, unit): R.extend(("material", code, cat, d, u or unit) for d, u in items) if False else None
def add(rtype, code, cat, unit, descs):
    for d in descs:
        if isinstance(d, tuple): d, u = d
        else: u = unit
        R.append((rtype, code, cat, d, u))

add("material","M.01","Pipe","m",["Seamless carbon steel pipe — size/schedule/grade per pipe class","Welded carbon steel pipe — size/schedule/grade per pipe class","Stainless steel pipe — grade/size/schedule per pipe class",
 "Alloy steel pipe (low-temperature or high-temperature service) — grade/size/schedule","Duplex / super-duplex pipe — grade/size/schedule","Lined carbon steel pipe (rubber, PTFE or other) — lining per specification",
 "GRE / GRP pipe — pressure class and size","HDPE process or utility pipe — PE grade and pressure class","Copper-nickel or non-ferrous pipe — grade and size"])
add("material","M.01","Fittings and flanges","nr",["Butt-weld fittings (elbow, tee, reducer, cap) — material/size/schedule","Forged fittings (socket-weld or threaded) — material/size/class",
 "Weld-neck flange — material/size/pressure rating/facing","Slip-on or socket-weld flange — material/size/pressure rating","Blind flange — material/size/pressure rating","Spectacle blind / spade — size/rating",
 "Olet / branch connection — type/size/material","Expansion joint or flexible hose — type/size/rating"])
add("material","M.01","Joint materials","set",["Gasket set (spiral wound, RTJ or sheet) — type/size/rating","Stud bolt and nut set — grade/size/length","Pipe support (shoe, guide, anchor, spring) — type and load","Pipe hanger or clamp — type and size"])
add("material","M.01","Welding consumables","kg",["Welding electrodes and filler wire — process/grade per WPS","Shielding and purge gas — type"])
add("material","M.02","Valves","nr",["Gate valve — material/size/rating/ends","Globe valve — material/size/rating/ends","Check valve — type/material/size/rating","Ball valve — material/size/rating/ends/actuation",
 "Butterfly valve (industrial) — material/size/rating/actuation","Plug valve — material/size/rating","Control valve with actuator and positioner — Cv/size/rating/trim","Pressure safety / relief valve — set pressure/orifice/material",
 "Motor-operated or pneumatic on/off valve with actuator — size/rating/fail-position","Strainer or filter — type/size/rating","Steam trap — type/size/pressure","Sampling point or valve assembly — type"])
add("material","M.03","Field instruments","nr",["Pressure transmitter — range/accuracy/area classification","Differential pressure / flow transmitter — range/element type","Temperature element with thermowell — type/range",
 "Level transmitter (radar, guided wave, DP, displacer) — type/range","Flow meter (Coriolis, magnetic, vortex, ultrasonic) — size/type","Analyser (gas, pH, conductivity, moisture) — type/range",
 "Gas / fire detector — type/area classification","Local gauge (pressure/temperature) — range","Limit switch or proximity sensor — type","Instrument air filter regulator or manifold — type"])
add("material","M.03","Instrument installation bulks","m",["Instrument cable (single or multi-pair) — type/size/screening","Instrument tubing — material/size","Multi-core control cable — type/cores"])
add("material","M.03","Instrument installation bulks","nr",["Junction box or marshalling cabinet — type/area classification","Cable gland and accessories — type/size","Instrument stand, bracket or enclosure — type"])
add("equipment","M.03","Control systems","set",["Distributed control system (DCS) — hardware, licences and I/O cabinets","Programmable logic controller (PLC) package — hardware and licences","SCADA / HMI servers and workstations — hardware and licences",
 "Safety instrumented / emergency shutdown system — hardware and licences","Fire and gas system — hardware and licences","Analyser shelter or sampling system — package"])
add("material","M.04","Cables and accessories","m",["MV power cable — voltage/conductor/insulation/armour","LV power cable — conductor/insulation/armour/size","Control and signal cable (industrial) — cores/screening",
 "Earthing conductor — material/size","Cable tray / ladder (industrial) — material/width/load class","Conduit (rigid or flexible, area-rated) — material/size"])
add("material","M.04","Terminations and accessories","nr",["MV cable termination or joint kit — voltage/type","LV cable lug and gland set — size/type/area classification","Earth rod or earth pit — material/depth","Lightning protection component — type",
 "Hazardous-area light fitting — protection type/area classification","Hazardous-area junction box or push-button station — protection type","Local control station — type"])
add("equipment","M.04","Power equipment","nr",["MV switchgear panel — voltage/rating/fault level/form","LV switchgear or motor control centre (MCC) section — rating/form","Variable speed drive — power/voltage","Power transformer (oil or dry-type) — MVA/voltage/vector group",
 "Electric motor (industrial) — kW/voltage/enclosure/protection","Uninterruptible power supply and battery system — kVA/autonomy","Emergency diesel generator package — kVA/fuel system","Capacitor bank or harmonic filter — kVAr/voltage",
 "Substation building (prefabricated) — dimensions/ratings"])
add("material","M.05","Structural steel","t",["Fabricated structural steel — grade/section class/connection type","Pipe rack or equipment support steel — fabricated","Platform, stair and ladder steel — fabricated"])
add("material","M.05","Steel accessories","nr",["Anchor bolt or chemical anchor set — grade/size/length","Grating panel — type/material/load class","Handrail and toe-plate assembly — material","Base plate and grout set — size"])
add("material","M.05","Steel accessories","kg",["High-strength bolt set (structural) — grade/size","Non-shrink grout — type"])
add("material","M.06","Plate and linings","t",["Carbon steel plate for tank or vessel fabrication — grade/thickness","Stainless or clad plate — grade/thickness"])
add("equipment","M.06","Vessels and exchangers","nr",["Pressure vessel (vertical or horizontal) — design pressure/temperature/materials/weight","Shell-and-tube heat exchanger — duty/materials/TEMA type","Plate or air-cooled heat exchanger — duty/materials",
 "Storage tank, atmospheric (field-erected kit) — diameter/height/roof type/materials","Storage tank, shop-fabricated — volume/materials","Column or reactor internals — type","Filter, separator or package skid — duty/materials"])
add("equipment","M.07","Pumps and compressors","nr",["Centrifugal pump (process) — duty/materials/sealing/driver","Positive displacement or dosing pump — duty/materials","Reciprocating or screw compressor package — duty/driver","Centrifugal compressor package — duty/driver",
 "Fan or blower (industrial) — duty/drive","Packaged unit (water treatment, utilities) — skid scope","Mixer or agitator — duty/materials","Crane or hoist (permanent, industrial) — capacity/span"])
add("material","M.08","Coating systems","l",["Primer (zinc-rich, epoxy or other) — system per coating specification","Intermediate coat — system per coating specification","Topcoat — system per coating specification","Tank or pipe internal lining — system per specification"])
add("material","M.08","Surface preparation","kg",["Abrasive blasting media — type/grade"])
add("material","M.08","Galvanising","t",["Hot-dip galvanising of fabricated steel — coating mass per specification"])
add("material","M.09","Insulation and cladding","m2",["Mineral wool insulation — thickness/density/service","Cellular glass insulation — thickness/service","PIR / PUF insulation — thickness/service","Cold (cryogenic or chilled) insulation system — thickness/vapour barrier",
 "Aluminium or stainless jacketing — gauge/finish","Cementitious fireproofing — rating/thickness","Intumescent fireproofing — rating/DFT","Acoustic insulation or lagging — specification"])
add("material","M.09","Heat tracing","m",["Electric heat-trace cable — W/m and type","Steam tracing tube and fittings — size"])
add("plant","M.10","Scaffolding","m3",["Scaffold erect and dismantle — industrial access (priced per volume)","Scaffold hire — per volume and period"])
add("plant","M.11","Cranes and lifting","day",["Mobile crane, 50 t class — with operator","Mobile crane, 100–200 t class — with operator","Crawler crane, 300 t class and above — with operator","Strand jack or gantry lifting system — per lift system",
 "Self-propelled modular transporter (SPMT) — per set","Heavy-haul trailer and prime mover — per unit","Rigging gear and spreader beams — per set"])
add("plant","M.12","Testing equipment","day",["Hydrostatic test pump and manifold","Radiography source and exposure equipment","Ultrasonic / phased-array test equipment","Pneumatic test compressor and relief set","Chemical cleaning / flushing skid","Post-weld heat-treatment equipment"])
add("plant","M.02","Welding and fabrication plant","month",["Welding machine (multi-process) — per unit","Pipe bevelling / cutting machine","Hot-tap or line-stopping equipment","Portable generator or compressor (industrial site)"])
add("material","M.13","Cathodic protection","nr",["Sacrificial anode — material/mass","Impressed-current anode and junction box — type","Reference electrode or test post — type","Transformer-rectifier unit — rating","Cathodic protection monitoring unit — type"])
add("material","M.13","Cathodic protection","m",["Anode cable and cable-to-pipe connection kit — size","Coating repair or field-joint coating system — type"])
add("subcontract","M.01","Piping","inch_dia",["Pipe fabrication (shop) — carbon steel, priced per inch-diameter","Pipe fabrication (shop) — stainless / alloy, priced per inch-diameter","Pipe erection and welding (field) — priced per inch-diameter",
 "Small-bore piping and tubing installation (field) — priced per inch-diameter"])
add("subcontract","M.01","Piping","t",["Pipe supports fabrication and installation — priced per tonne"])
add("subcontract","M.12","Inspection and testing","joint",["Radiographic examination of welds — priced per joint","Ultrasonic / phased-array examination of welds — priced per joint","Magnetic particle or dye-penetrant examination — priced per joint","Post-weld heat treatment — priced per joint","Positive material identification — priced per joint"])
add("subcontract","M.12","Inspection and testing","item",["Hydrostatic / pneumatic test packs — priced per test pack","Flushing, chemical cleaning and passivation — priced per system","Third-party inspection and certification — per package","Welder qualification and procedure testing — per package"])
add("subcontract","M.03","Instrumentation","loop",["Instrument installation, tubing and termination — priced per loop","Loop checking and calibration — priced per loop","Control-system configuration, FAT and SAT — priced per loop or lump sum"])
add("subcontract","M.04","Electrical","m",["MV/LV cable pulling and termination — priced per cable length","Cable tray and conduit installation — priced per length"])
add("subcontract","M.04","Electrical","item",["Substation installation and testing — per substation","Motor and drive installation, alignment and testing — per package","Earthing and lightning protection installation — per area"])
add("subcontract","M.05","Structural steel","t",["Structural steel fabrication — priced per tonne","Structural steel erection and bolting/welding — priced per tonne","Steel grating, handrail and stair installation — priced per tonne"])
add("subcontract","M.06","Tanks and vessels","t",["Field-erected tank (plate erection, welding and testing) — priced per tonne of plate","Vessel installation, setting and alignment — priced per tonne"])
add("subcontract","M.06","Tanks and vessels","item",["Tank foundation ring and bund works — per tank","Tank hydrotest, settlement survey and commissioning support — per tank","Heat-exchanger bundle pulling and retubing — per unit"])
add("subcontract","M.07","Rotating equipment","item",["Pump / compressor installation, alignment and grouting — per unit","Vendor-representative support for installation and start-up — per package"])
add("subcontract","M.08","Coatings","m2",["Abrasive blasting and shop coating — priced per m2","Field coating and touch-up — priced per m2","Tank / vessel internal lining — priced per m2"])
add("subcontract","M.09","Insulation","m2",["Insulation and jacketing installation — priced per m2","Fireproofing application — priced per m2"])
add("subcontract","M.09","Insulation","m",["Heat tracing installation and testing — priced per length"])
add("subcontract","M.10","Scaffolding","m3",["Scaffolding erection, inspection, modification and dismantling — priced per m3"])
add("subcontract","M.11","Lifting and transport","item",["Heavy-lift engineering study and lift plan — per lift","Heavy transport and route survey — per move","Module / vessel lifting and setting — per lift"])
add("subcontract","M.13","Cathodic protection","item",["Cathodic protection design, installation and commissioning — per system","Corrosion monitoring and coupon systems — per system"])
add("subcontract","M.14","Shutdown and brownfield","item",["Shutdown / turnaround execution package — per work package","Hot-tap, line-stop or tie-in works — per tie-in","Isolation, blinding and de-blinding — per isolation","Operations standby, permit and fire-watch support — per period","Decontamination, gas-freeing and waste handling — per system"])
add("subcontract","M.15","Modularisation","t",["Module fabrication in yard — priced per tonne","Module hook-up and interconnection at site — priced per tonne"])
add("subcontract","M.15","Modularisation","item",["Module transport (road/sea) and import logistics — per module","Pre-assembled skid fabrication — per skid"])
add("subcontract","M.16","Commissioning","item",["Pre-commissioning (cleaning, drying, leak testing) — per system","Commissioning and start-up support — per system","Performance testing — per package","Operator training and handover documentation — per package","Commissioning spares and consumables supply — per package"])
add("subcontract","M.17","Engineering","item",["Detailed engineering package — per discipline package","Vendor-data review and technical queries support — per package","Procurement and expediting support — per package","As-built documentation and records — per package"])
add("labour","M.01","Piping crafts","hr",["Pipe fitter","Pipe welder (6G qualified or equivalent per client requirement)","Pipe foreman","Pipe rigger / helper","Pipe designer / checker (site)"])
add("labour","M.03","Instrument and control crafts","hr",["Instrument technician","Instrument fitter / tubing installer","Control-system engineer (site)","Loop-check technician"])
add("labour","M.04","Electrical crafts","hr",["Industrial electrician (cable and terminations)","MV cable jointer / terminator","Hazardous-area electrician (certified)","Electrical commissioning engineer"])
add("labour","M.05","Steel and mechanical crafts","hr",["Structural steel erector / rigger","Structural welder","Mechanical fitter (rotating equipment)","Millwright / alignment technician","Boilermaker (vessels and tanks)"])
add("labour","M.08","Coating and insulation crafts","hr",["Abrasive blaster","Industrial painter / coating applicator","Insulation applicator","Fireproofing applicator","Scaffold supervisor"])
add("labour","M.12","Inspection and quality","hr",["NDT technician (radiography)","NDT technician (UT/MPI/PT)","QA/QC inspector (welding / coating)","Quality engineer","HSE advisor (industrial / permit-to-work)"])
add("labour","M.14","Shutdown crafts","hr",["Shutdown planner / coordinator","Permit coordinator","Fire watch / safety standby"])
add("labour","M.16","Commissioning","hr",["Pre-commissioning technician","Commissioning engineer (process)","Start-up superintendent"])
add("labour","M.17","Engineering staff","hr",["Process engineer","Piping design engineer","Civil / structural engineer","Electrical engineer","Instrument and control engineer","Mechanical / rotating equipment engineer","Project controls engineer (cost / planning)","Document controller","CAD / 3D modeller"])
add("labour","M.18","Home-office and management staff","hr",["Project director","Project manager (home office)","Procurement / contracts manager","Cost engineer / estimator","Planner / scheduler","Finance and administration staff"])

cc = [dict(code="M", parent_code="", level=1, kind="division", name="Industrial and process plant", short_name="INDPLANT", default_unit="", description="Optional pack: definitions only", active=1, is_system=0)]
cc += [dict(code=c, parent_code="M", level=2, kind="subtrade", name=n, short_name="", default_unit="", description="", active=1, is_system=0) for c, n in SUBS]
with open(OUT / "cost_codes.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(cc[0]), lineterminator="\n"); w.writeheader(); w.writerows(cc)
pref = {"material": "MAT", "labour": "LAB", "plant": "PLT", "equipment": "EQP", "subcontract": "SUB"}
cnt = {}
rows = []
for rtype, code, cat, d, unit in R:
    cnt[rtype] = cnt.get(rtype, 0) + 1
    rid = f"PRC-{pref[rtype]}-{cnt[rtype]:03d}"
    spec = LABSPEC if rtype == "labour" else SUBSPEC if rtype == "subcontract" else SPEC
    desc = f"Labour category: {d}" if rtype == "labour" else f"Plant item: {d}" if rtype == "plant" else f"Equipment supply: {d}" if rtype == "equipment" else f"{d} — subcontract package" if rtype == "subcontract" else d
    rows.append(dict(id=rid, resource_type=rtype, cost_code=code, category=cat, description=desc, aliases="", specification=spec,
                     brand_requirements="Approved make / vendor list per client requirement: to be confirmed" if rtype in ("material", "equipment") else "Not applicable",
                     unit=unit, notes=NOTE_L if rtype == "labour" else NOTE_M))
with open(OUT / "resources.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n"); w.writeheader(); w.writerows(rows)
json.dump({"name": "industrial", "description": "Optional definitions-only pack for industrial / process-plant estimating: cost division M and resource definitions (no prices, no factors, no standards claims). "
           "Load with: python -m app.cli pack load industrial", "cost_codes": len(cc), "resources": len(rows), "by_type": cnt}, open(OUT / "manifest.json", "w"), indent=1)
print(len(cc), "cost codes;", len(rows), "resources;", cnt)
