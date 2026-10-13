# Trade taxonomy and cost codes

Generated from `data/taxonomy/cost_codes.csv` by `scripts/gen_docs.py`. The taxonomy is **data, not code**: add a trade, sub-trade or
cost code in *Settings -> Add cost code* (Administrator) or by adding rows to the CSV (loaded idempotently by `refdata.load_taxonomy`).
No calculation-engine change is needed. Codes are stable identifiers used in resources, assemblies, BOQ items, workbooks and reports.

Level 1 = division (A-L); level 2 = sub-trade; level 3+ = user-added cost codes (e.g. `D.07.01`).
A project records its applicable trades (project settings / `project.json`); the cost-code tree itself is global and shared by resources, assemblies, BOQ items and reports.

## A - Preliminaries and general requirements

| Code | Sub-trade |
|---|---|
| `A.01` | Mobilisation and demobilisation |
| `A.02` | Site establishment and temporary facilities |
| `A.03` | Site management and supervision |
| `A.04` | HSE, security and access control |
| `A.05` | Temporary power, water and lighting |
| `A.06` | Hoarding, scaffolding and temporary works |
| `A.07` | Site transport, logistics and accommodation |
| `A.08` | Testing, inspections and third-party certification |
| `A.09` | Temporary access, protection and traffic management |
| `A.10` | Cleaning, demobilisation and handover |

## B - Civil and infrastructure

| Code | Sub-trade |
|---|---|
| `B.01` | Site clearance and demolition |
| `B.02` | Excavation, earthworks, cut and fill |
| `B.03` | Backfilling, compaction and disposal |
| `B.04` | Shoring and excavation support |
| `B.05` | Roads, pavements, kerbs and footpaths |
| `B.06` | Asphalt and road markings |
| `B.07` | Stormwater drainage |
| `B.08` | Sewerage and wastewater networks |
| `B.09` | Potable water and irrigation networks |
| `B.10` | Underground utility networks |
| `B.11` | Duct banks and utility crossings |
| `B.12` | Manholes, chambers and culverts |
| `B.13` | Retaining walls and external structures |
| `B.14` | Fencing, gates and barriers |
| `B.15` | Landscaping and irrigation |
| `B.16` | External lighting and associated networks |
| `B.17` | Utility connections and authority interfaces |

## C - Structural

| Code | Sub-trade |
|---|---|
| `C.01` | Foundations and reinforced concrete |
| `C.02` | Formwork and falsework |
| `C.03` | Reinforcement supply and fixing |
| `C.04` | Structural steel and connections |
| `C.05` | Precast concrete |
| `C.06` | Post-tensioning |
| `C.07` | Metal decking and composite structures |
| `C.08` | Structural waterproofing |
| `C.09` | Concrete repairs and strengthening |
| `C.10` | Structural fire protection |
| `C.11` | Specialist foundations |

## D - Architecture and finishes

| Code | Sub-trade |
|---|---|
| `D.01` | Blockwork and masonry |
| `D.02` | Drywall and partitions |
| `D.03` | Plastering, rendering and screeds |
| `D.04` | Waterproofing and insulation |
| `D.05` | Doors, windows, glazing and curtain walls |
| `D.06` | Flooring, tiles, stone and raised floors |
| `D.07` | Painting and wall coverings |
| `D.08` | Suspended ceilings and access panels |
| `D.09` | Joinery and architectural metalwork |
| `D.10` | Toilet partitions and accessories |
| `D.11` | Acoustic treatments |
| `D.12` | Fire stopping |
| `D.13` | Signage and wayfinding |
| `D.14` | Furniture, fixtures and equipment |
| `D.15` | Architectural protection and finishing |

## E - Mechanical and HVAC

| Code | Sub-trade |
|---|---|
| `E.01` | Chillers and cooling towers |
| `E.02` | Air handling units and fan coil units |
| `E.03` | Ventilation fans and air distribution |
| `E.04` | Ductwork, dampers and accessories |
| `E.05` | Duct insulation and cladding |
| `E.06` | Chilled-water and condenser-water piping |
| `E.07` | Refrigerant piping and DX systems |
| `E.08` | Pumps, valves and pipe supports |
| `E.09` | Air terminals, grilles and diffusers |
| `E.10` | HVAC controls and instrumentation |
| `E.11` | Building management system interfaces |
| `E.12` | Smoke extraction and stair pressurisation |
| `E.13` | Testing, adjusting, balancing and commissioning |

## F - Plumbing and public health

| Code | Sub-trade |
|---|---|
| `F.01` | Domestic cold and hot water |
| `F.02` | Water tanks and booster systems |
| `F.03` | Sanitary fixtures and fittings |
| `F.04` | Soil, waste and vent piping |
| `F.05` | Rainwater and roof drainage |
| `F.06` | Pumps and specialist drainage |
| `F.07` | Water treatment and filtration |
| `F.08` | Water heaters and calorifiers |
| `F.09` | Pipe insulation and supports |
| `F.10` | Testing, flushing, disinfection and commissioning |

## G - Fire protection and life safety

| Code | Sub-trade |
|---|---|
| `G.01` | Sprinkler systems |
| `G.02` | Fire hydrants and hose reels |
| `G.03` | Fire pumps and pump rooms |
| `G.04` | Wet, dry and pre-action systems |
| `G.05` | Clean-agent and specialist suppression |
| `G.06` | Fire alarm and detection |
| `G.07` | Emergency lighting and exit signage |
| `G.08` | Fire stopping and penetrations |
| `G.09` | Integrated life-safety testing and commissioning |

## H - Electrical power and lighting

| Code | Sub-trade |
|---|---|
| `H.01` | MV and LV switchgear |
| `H.02` | Transformers and substations |
| `H.03` | Distribution boards and panelboards |
| `H.04` | Generators and automatic transfer switches |
| `H.05` | UPS and battery systems |
| `H.06` | Busducts, cables and containment |
| `H.07` | Cable trays, ladders and conduits |
| `H.08` | Earthing, bonding and lightning protection |
| `H.09` | Internal and external lighting |
| `H.10` | Small power and final circuits |
| `H.11` | Power quality and metering |
| `H.12` | Solar PV and energy storage |
| `H.13` | Testing and commissioning |

## I - ELV, ICT and security

| Code | Sub-trade |
|---|---|
| `I.01` | Structured cabling and fibre optics |
| `I.02` | Network racks and infrastructure |
| `I.03` | CCTV and video management |
| `I.04` | Access control |
| `I.05` | Intrusion detection |
| `I.06` | Public address and voice alarm |
| `I.07` | Intercom and nurse call |
| `I.08` | Audio-visual and conference systems |
| `I.09` | BMS integration and gateways |
| `I.10` | Testing, configuration and system integration |

## J - Specialist systems and equipment

| Code | Sub-trade |
|---|---|
| `J.01` | Lifts and escalators |
| `J.02` | Building facade access systems |
| `J.03` | Commercial kitchen and laundry equipment |
| `J.04` | Medical gas and specialist healthcare systems |
| `J.05` | Industrial and process equipment |
| `J.06` | Waste handling systems |
| `J.07` | Swimming pools and water features |
| `J.08` | Specialist refrigeration and cold rooms |
| `J.09` | Laboratories and cleanrooms |
| `J.10` | EV charging |
| `J.11` | Renewable energy systems |
| `J.12` | Other configurable specialist packages |

## K - External works and sitewide systems

| Code | Sub-trade |
|---|---|
| `K.01` | External utilities |
| `K.02` | Boundary walls and gates |
| `K.03` | External lighting |
| `K.04` | Landscaping and irrigation |
| `K.05` | Traffic barriers and signage |
| `K.06` | Parking and access-control equipment |
| `K.07` | Stormwater attenuation |
| `K.08` | Utility connections |

## L - Engineering, commercial and closeout

| Code | Sub-trade |
|---|---|
| `L.01` | Design and engineering allowances |
| `L.02` | Authority fees and permits |
| `L.03` | Insurance and bonds |
| `L.04` | Freight, customs and logistics |
| `L.05` | Escalation and currency exposure |
| `L.06` | Risk allowances and contingency |
| `L.07` | Warranties and defects-liability costs |
| `L.08` | Training and O&M manuals |
| `L.09` | Testing, commissioning and handover |
| `L.10` | Provisional sums |
| `L.11` | Prime-cost sums |
| `L.12` | Client allowances and other approved commercial provisions |
