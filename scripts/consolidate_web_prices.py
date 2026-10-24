"""Rebuild the web-price workbook from the saved research rows in data/public_data/web_price_research_2026-10-24/. Consolidate the researched price rows: audit each against its own quote, match units to the catalogue, cross-check sources, and write the filled price-list workbook.
Nothing here invents a number: a row is kept only if its price(s) appear in its verbatim quote; ranges become their midpoint with the range written into the evidence."""
import glob, json, re, statistics, sys
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.units import registry
from app.database import Database
from app.excel import templates as T

R = Path(__file__).resolve().parent.parent / "data" / "public_data"
OUTDIR = "web_price_research_2026-10-24"
DB = Database(sys.argv[1] if len(sys.argv) > 1 else "var/ksa.db")   # usage: python scripts/consolidate_web_prices.py DB_FILE OUT.xlsx
RETRIEVED = "2026-10-24"
BANNED = {"gccpricing.com", "ceicdata.com"}
reg = registry(DB)
cat = {r["id"]: dict(r) for r in DB.all("SELECT id, description, unit, resource_type, cost_code FROM resources WHERE is_active=1")}
AR = str.maketrans("٠١٢٣٤٥٦٧٨٩٬٫", "0123456789,.")


def num_in(text: str, v) -> bool:
    t = re.sub(r"(?<=\d),(?=\d{3})", "", (text or "").translate(AR))
    for cand in {f"{v:g}", f"{v:.2f}", f"{v:.1f}", f"{v:.0f}", str(v)}:
        if re.search(rf"(?<![\d.]){re.escape(cand)}(?![\d])", t) or re.search(rf"(?<![\d.]){re.escape(cand)}(?=\.\D|\.$)", t):
            return True
    return False


def canon_unit(u: str, cat_unit: str | None = None) -> str | None:
    s = (u or "").lower().translate(AR)
    if cat_unit == "bag" and re.search(r"\d+\s*kg", s):
        return "bag"                                      # 'per 50 kg' for a bagged product is the bag
    for pat, code in [(r"m3|m³|cubic|cum|م3|م³", "m3"), (r"m2|m²|sq\.? ?m|square|م2|م²", "m2"), (r"ton|tonne|طن|\bmt\b", "t"), (r"\bkg\b|kilo|كجم|كيلو", "kg"),
                      (r"/ ?m\b|per m\b|metre|meter|\blm\b|running|متر", "m"), (r"bag|كيس", "bag"), (r"\bset\b|طقم", "set"), (r"lump|\bls\b", "ls"),
                      (r"hour|\bhr\b|ساعة", "hr"), (r"day|يوم", "day"), (r"month|شهر", "month"), (r"litre|liter|\bltr\b|لتر", "l"),
                      (r"block|piece|pcs|\bpc\b|each|\bnr\b|unit|قطعة|حبة|/ ?no\b|number", "nr")]:
        if re.search(pat, s):
            return code
    return None


def iso(d: str) -> tuple[str, str]:
    d = (d or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", d) or None
    if m:
        return d[:10], ""
    m = re.match(r"(\d{2})-(\d{2})-(\d{4})", d)
    if m:
        return f"{m[3]}-{m[2]}-{m[1]}", ""
    m = re.match(r"(\d{4})-(\d{2})\b", d)
    if m:
        return f"{m[1]}-{m[2]}-01", "month average/edition; price date set to the 1st of the month"
    return "", "page date not stated: retrieval date used as the price date"


rows, quarantined = [], []
for f in sorted(glob.glob(str(R / OUTDIR / "*.json"))):
    for r in json.load(open(f)):
        r["_file"] = Path(f).name
        host = urlparse(r.get("source_url") or "").netloc.lower().removeprefix("www.")
        why = None
        lo, hi, p = r.get("price_low"), r.get("price_high"), r.get("price")
        if not r.get("source_url") or not r.get("quote"):
            why = "no source URL or no verbatim quote"
        elif any(b in host for b in BANNED):
            why = f"source {host} judged unreliable (wrong currency/units seen)"
        elif re.search(r"as low as|starting (price|from|at)|starts from|\bfrom sar|ابتداء|يبدأ|يبدأ من|estimated price", (r.get("quote") or "") + " " + (r.get("description") or ""), re.I):
            why = "a 'from / as low as / starting' floor or an estimate, not a stated price"
        elif re.search(r"qsmind|sca\.gov|muqawil|contractors authority", (host + " " + (r.get("source_name") or "")).lower()):
            why = "source excluded: anonymous approximate aggregator, or report that requires written permission to reuse"
        elif (yr := re.search(r"(20\d\d)", (r.get("page_date") or "") + " " + (r.get("source_name") or ""))) and int(yr.group(1)) < 2025 and r.get("tier") != "A-mirror":
            why = f"historical ({yr.group(1)}): too old to be a current price"
        elif p is None and (lo is None or hi is None):
            why = "no price"
        elif p is not None and not num_in(r["quote"], p) and r.get("tier") != "A-mirror":
            why = f"price {p} not found in its own quote (audit failed)"
        elif p is None and not (num_in(r["quote"], lo) and num_in(r["quote"], hi)):
            why = f"range {lo}-{hi} not found in its own quote (audit failed)"
        elif (p or lo) is not None and (p or lo) <= 0:
            why = "non-positive price"
        if why:
            quarantined.append((r, why)); continue
        if r.get("currency", "SAR").upper() != "SAR":
            quarantined.append((r, f"currency {r['currency']} (no approved FX in this system - not imported)")); continue
        price = Decimal(str(p)) if p is not None else (Decimal(str(lo)) + Decimal(str(hi))) / 2
        is_range = p is None
        rid = r.get("resource_id") or ""
        unit = None
        if rid:
            if rid not in cat:
                quarantined.append((r, f"resource {rid} not in catalogue")); continue
            cu = cat[rid]["unit"]
            su = canon_unit(r["unit_as_stated"], cu) if not r.get("unit_canon") else r["unit_canon"]
            if su is None:
                quarantined.append((r, f"unit '{r['unit_as_stated']}' not understood")); continue
            if su == "nr" and cu == "length_piece":
                su = cu                                    # a pipe/bar sold 'per piece' of stated length is the catalogue's piece
            if su == cu:
                unit = cu
            elif su in reg.units and cu in reg.units and reg.can_convert(su, cu):
                price = price / reg.factor(su, cu); unit = cu
                r["conv"] = f"converted from per {su} to per {cu} (exact, x{1/reg.factor(su,cu):g})"
            else:
                quarantined.append((r, f"unit '{r['unit_as_stated']}' ({su}) does not match catalogue unit {cu}")); continue
            if is_range:
                lo, hi = Decimal(str(lo)), Decimal(str(hi))
                if su != cu:
                    lo, hi = lo / reg.factor(su, cu), hi / reg.factor(su, cu)
                r["range_txt"] = f"{lo:g}-{hi:g}"
        r["_price"], r["_range"], r["_unit"], r["_rid"] = price, is_range, unit, rid
        rows.append(r)

# ---- cross-check per catalogue item (only rows matched with a comparable unit)
by = {}
for r in rows:
    if r["_rid"]:
        by.setdefault(r["_rid"], []).append(r)
xc = {}
for rid, rs in by.items():
    ps = [float(x["_price"]) for x in rs]
    med = statistics.median(ps)
    spread = (max(ps) - min(ps)) / med if med else 0
    hosts = {urlparse(x["source_url"]).netloc.removeprefix("www.") for x in rs}
    distinct = len({re.sub(r"\W+", " ", (x.get("description") or "").lower()) for x in rs})
    kind = "Single source" if len(rs) == 1 else ("Single site only" if len(hosts) == 1 and spread <= 0.25 else "Corroborated" if spread <= 0.25 else ("SPEC-DEPENDENT RANGE (different models/sizes priced under one generic item)" if distinct == len(rs) else "CONFLICT"))
    status = kind + (f" ({len(rs)} rows, {len(hosts)} site(s), spread {spread:.0%})" if len(rs) > 1 else "")
    xc[rid] = dict(n=len(rs), sites=len(hosts), lo=min(ps), med=med, hi=max(ps), spread=spread, status=status)
TYPE = {"manufacturer": "Manufacturer website", "supplier/retailer": "Supplier website", "marketplace": "Supplier website"}
prefill = {}
for rid, rs in by.items():
    for x in rs:
        d, dnote = iso(x.get("page_date", ""))
        ev = [f"[{x.get('tier','')}] " if x.get("tier") else "", "INDICATIVE PUBLISHED PRICE - UNVERIFIED. ",
              f"RANGE {x['range_txt']} as published; midpoint used. " if x["_range"] else "", f"“{x['quote'][:230]}” ", x.get("spec_notes") or "", " " + (x.get("conv") or ""),
              " " + (x.get("notes") or "")[:200], f" | {dnote}" if dnote else "", f" | Cross-check: {xc[rid]['status']}, median {xc[rid]['med']:.2f}"]
        pr = {"Unit price": float(round(x["_price"], 4)), "Currency": "SAR", "Rate type": "Published Market Price", "Price date": d or None,
              "Tax basis": x["vat_basis"] if x["vat_basis"] in ("Included", "Excluded") else None, "Delivery basis": (x.get("delivery_basis") or "")[:60] or None,
              "Evidence / reference": re.sub(r"\s+", " ", "".join(ev))[:900], "Source type": TYPE.get(x.get("source_kind"), "Manual dataset"), "Source URL": x["source_url"],
              "Supplier / source name": x["source_name"][:120], "Retrieval date": RETRIEVED}
        prefill.setdefault(rid, []).append(pr)
out = Path(sys.argv[2] if len(sys.argv) > 2 else "Price_list_prefilled_web_prices.xlsx")
T.price_list_workbook(out, DB, prefill=prefill)
from openpyxl import load_workbook
from openpyxl.styles import Font
wb = load_workbook(out)
ws = wb.create_sheet("Cross-check")
ws.append(["Resource", "Description", "Sources", "Sites", "Low", "Median", "High", "Spread", "Result"])
for rid, v in sorted(xc.items()):
    ws.append([rid, cat[rid]["description"], v["n"], v["sites"], round(v["lo"], 2), round(v["med"], 2), round(v["hi"], 2), f"{v['spread']:.0%}", v["status"]])
for c in ws[1]: c.font = Font(bold=True)
ws.column_dimensions["B"].width = 60; ws.column_dimensions["I"].width = 50
um = wb.create_sheet("Unmatched - to map")
um.cell(1, 1, "Prices found on the web for items that are not (yet) in the catalogue, or that could not be tied to one catalogue item. They upload like the others and appear in the review queue as 'resource unmatched': a person picks the catalogue resource (or adds one).").font = Font(bold=True)
for c, h in enumerate(T.PRICE_LIST_HEADERS, 1):
    um.cell(5, c, h).font = Font(bold=True)
n = 5
for r in rows:
    if r["_rid"]:
        continue
    d, dnote = iso(r.get("page_date", ""))
    pr = {"Resource ID": None, "Description (for new resources)": (r.get("description") or "")[:200], "Unit": r.get("unit_as_stated"), "Unit price": float(round(r["_price"], 4)), "Currency": "SAR",
          "Rate type": "Published Market Price", "Price date": d or None, "Tax basis": r["vat_basis"] if r["vat_basis"] in ("Included", "Excluded") else None,
          "Delivery basis": (r.get("delivery_basis") or "")[:60] or None,
          "Evidence / reference": re.sub(r"\s+", " ", "[%s] INDICATIVE PUBLISHED PRICE - UNVERIFIED. %s“%s” %s %s%s" % (r.get("tier", ""), f"RANGE {r.get('price_low')}-{r.get('price_high')} as published; midpoint used. " if r["_range"] else "", r["quote"][:230], r.get("spec_notes") or "", (r.get("notes") or "")[:200], f" | {dnote}" if dnote else ""))[:900],
          "Source type": TYPE.get(r.get("source_kind"), "Manual dataset"), "Source URL": r["source_url"], "Supplier / source name": r["source_name"][:120], "Retrieval date": RETRIEVED}
    n += 1
    for c, h in enumerate(T.PRICE_LIST_HEADERS, 1):
        um.cell(n, c, pr.get(h))
um.column_dimensions["B"].width = 50; um.column_dimensions["N"].width = 60
st = wb["Start here"]
st.cell(5, 1, "WEB-SOURCED PRICES - INDICATIVE AND UNVERIFIED. Every filled price was read from a public web page on 24 Oct 2026 (URL, page date and the exact quote are in each row's Evidence / Source URL columns). They are published market/retail prices or published ranges (a range is entered as its midpoint, say so in Evidence), not quotations. Terms of use of the sites were not reviewed. Check each price, correct or clear it, then upload. See the 'Cross-check' and 'Not uploaded' sheets at the end.").font = Font(bold=True, color="9C5700")
ns = wb.create_sheet("Not uploaded")
ns.append(["Where it was found", "What", "Low", "High", "Stated unit", "Quote", "Why it is not in the price list", "Link"])
for r, why in quarantined:
    ns.append([r.get("source_name"), r.get("description"), r.get("price_low") if r.get("price") is None else r.get("price"), r.get("price_high"), r.get("unit_as_stated"), (r.get("quote") or "")[:250], why, r.get("source_url")])
for c in ns[1]: c.font = Font(bold=True)
ns.column_dimensions["B"].width = 50; ns.column_dimensions["G"].width = 60
print("unmatched rows in 'Unmatched - to map':", n - 5)
wb.save(out)
print("kept rows:", len(rows), "matched items:", len(by), "unmatched rows:", sum(1 for r in rows if not r['_rid']), "quarantined:", len(quarantined))
for r, why in quarantined: print("  QUARANTINE:", (r.get('description') or '')[:50], '|', why)
print({k: sum(1 for v in xc.values() if v['status'].startswith(k)) for k in ('Single', 'Corroborated', 'CONFLICT')})
