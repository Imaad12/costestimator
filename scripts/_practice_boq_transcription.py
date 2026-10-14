"""Hand transcription of the BOQ table of the practice-test input PDF (SiteSetu 'Sample BOQ for a Residential Building').

WHY THIS EXISTS: the PDF's text layer contains the descriptions and units but NOT the quantity column (pypdf extracts blanks; the numbers are only visible in the rendered page).
The quantities below were therefore read by eye from the rendered pages (pdftoppm 80 dpi, pages 3-5) and are labelled TRANSCRIBED - NOT VERIFIED. A person must compare them with the PDF before any reliance.
Nothing here is measured, inferred or completed: every number is a number printed in the source.  Rows: (item_no, description, unit, quantity, basis_as_printed, pdf_page, assumption_note)
"""
SOURCE = "Sample BOQ for a Residential Building | SiteSetu (PDF, 7 pages)"
SECTIONS = {"1": ("Earthwork", "Civil / earthwork"), "2": ("Reinforced concrete", "Structural"), "3": ("Formwork / shuttering", "Structural"), "4": ("Masonry walls", "Architectural"),
            "5": ("Doors and windows", "Architectural"), "6": ("Railings and balustrades", "Architectural"), "7": ("Roof", "Architectural / structural (not stated)")}
R = [
 ("1.1", "Excavation in pits for footings", "m³", "314.04", "derived from footing boxes — footing plan + 0.3 m working space each side, ground z=0.0 to underside of blinding", 3, "Assumption printed in source: natural ground level not printed — assumed at project ±0.00; confirm"),
 ("1.2", "PCC blinding 50 mm under footings", "m³", "18.33", "derived — pit plan x blinding thickness", 3, ""),
 ("1.3", "Backfill around footings", "m³", "240.58", "derived — excavation - footing - blinding", 3, ""),
 ("2.1", "Isolated footings", "m³", "55.40", "structural footing layout — sum of 73 mesh volumes", 3, ""),
 ("2.2", "Columns — Foundation", "m³", "1.90", "column keys + column details — sum of 22 mesh volumes", 3, ""),
 ("2.3", "Columns — Ground floor", "m³", "3.30", "column keys + column details — sum of 17 mesh volumes", 3, ""),
 ("2.4", "Columns — First floor", "m³", "1.56", "column keys + column details — sum of 9 mesh volumes", 3, ""),
 ("2.5", "First-floor beams 200x450", "m³", "5.21", "structural slab/beam sheets and beam details — sum of 11 mesh volumes", 3, ""),
 ("2.6", "Roof beams 200x300", "m³", "2.15", "structural slab/beam sheets and beam details — sum of 5 mesh volumes", 3, ""),
 ("2.7", "Slab — Ground floor", "m³", "22.14", "structural slab sheets (net of beam and column footprints) — sum of 7 mesh volumes", 3, ""),
 ("2.8", "Slab — First floor", "m³", "22.35", "structural slab sheets (net of beam and column footprints) — sum of 24 mesh volumes", 3, ""),
 ("2.9", "Slab — Roof", "m³", "11.29", "structural slab sheets (net of beam and column footprints) — sum of 14 mesh volumes", 3, ""),
 ("2.10", "RC stairs (flights + landings)", "m³", "4.13", "architectural plans and section; structural stair sheet quarantined — sum of 5 mesh volumes", 3, ""),
 ("3.1", "Footing sides", "m²", "249.59", "derived from element boxes — 4 sides x depth", 4, ""),
 ("3.2", "Column faces", "m²", "119.38", "derived from element boxes — 4 faces x height", 4, ""),
 ("3.3", "Beam sides and soffit", "m²", "493.69", "derived from element boxes — 2 sides + soffit x length", 4, ""),
 ("3.4", "Slab soffit and edges", "m²", "884.02", "derived from element boxes — soffit + edges", 4, ""),
 ("4.1", "Walls — Ground floor", "m³", "58.94", "architectural plans — sum of 32 mesh volumes", 4, ""),
 ("4.2", "Walls — First floor", "m³", "43.41", "architectural plans — sum of 22 mesh volumes", 4, ""),
 ("4.3", "Walls — Roof", "m³", "9.04", "architectural plans — sum of 5 mesh volumes", 4, ""),
 ("4.4", "Wall plaster area, both faces (gross)", "m²", "1345.20", "derived — 2 x length x height per wall, openings not deducted", 4, ""),
]
_DW = [("5.1", "Door 900 × 2400 mm", "7"), ("5.2", "Door 800 × 2400 mm", "4"), ("5.3", "Door 802 × 2400 mm", "1"), ("5.4", "Door 6467 × 3140 mm", "1"), ("5.5", "Door 2400 × 2400 mm", "1"),
       ("5.6", "Door 736 × 2400 mm", "1"), ("5.7", "Door 1300 × 2400 mm", "1"), ("5.8", "Window 800 × 400 mm", "3"), ("5.9", "Window 2460 × 600 mm", "2"), ("5.10", "Window 3000 × 600 mm", "2"),
       ("5.11", "Window 2600 × 600 mm", "2"), ("5.12", "Window 387 × 3140 mm", "2"), ("5.13", "Window 368 × 3140 mm", "2"), ("5.14", "Window 1500 × 400 mm", "2"), ("5.15", "Window 600 × 2950 mm", "2"),
       ("5.16", "Window 1206 × 2000 mm", "2"), ("5.17", "Window 1800 × 2000 mm", "2"), ("5.18", "Window 2400 × 2000 mm", "2"), ("5.19", "Window 1160 × 2750 mm", "2"), ("5.20", "Window 1200 × 2000 mm", "2"),
       ("5.21", "Window 4274 × 2000 mm", "1"), ("5.22", "Window 2500 × 1600 mm", "1"), ("5.23", "Window 4000 × 2000 mm", "1"), ("5.24", "Window 2400 × 2100 mm", "1"), ("5.25", "Window 2400 × 1600 mm", "1")]
for no, d, q in _DW:
    R.append((no, d, "nos", q, "traced on calibrated plans — count", 4 if int(no.split(".")[1]) <= 13 else 5, ""))
R += [("6.1", "Railings and balustrades", "m", "43.68", "architectural plans/elevations — run length", 5, ""),
      ("7.1", "Roof and canopy members", "m", "48.85", "plans + elevations — member length", 5, "")]
# Totals printed on page 2 ('The house at a glance') - used ONLY as a cross-check of the transcription and of the source's own arithmetic.
GLANCE = {"RCC (footings, columns, beams, slabs, stairs) m3": ("129.42", [f"2.{i}" for i in range(1, 11)]), "Formwork m2": ("1746.67", [f"3.{i}" for i in range(1, 5)]),
          "Masonry walls m3": ("111.38", ["4.1", "4.2", "4.3"]), "Wall plaster gross m2": ("1345.20", ["4.4"]), "Doors nos": ("16", [f"5.{i}" for i in range(1, 8)]),
          "Windows nos": ("32", [f"5.{i}" for i in range(8, 26)])}
