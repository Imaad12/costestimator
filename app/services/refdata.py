"""Load reference data (taxonomy, units, regions, sources, catalogues) from data/ into the database.

Idempotent: existing rows are never overwritten (so admin additions and approved records survive re-seeding).
"""
from __future__ import annotations

import csv
from pathlib import Path

from ..config import get_settings
from ..core.timeutil import now_iso
from ..database import Database
from ..models.actor import SYSTEM_SEED
from . import audit


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _data(sub: str, name: str) -> Path:
    return get_settings().data_dir / sub / name


def load_units(db: Database) -> int:
    n = 0
    for r in read_csv(_data("units", "units.csv")):
        if db.one("SELECT 1 FROM units WHERE code=?", (r["code"],)):
            continue
        db.insert("units", dict(code=r["code"], name=r["name"], dimension=r["dimension"], to_base=r["to_base"],
                                synonyms=r.get("synonyms"), ambiguous_synonyms=r.get("ambiguous_synonyms"), active=1))
        n += 1
    return n


def load_regions(db: Database) -> int:
    n = 0
    for r in read_csv(_data("regions", "regions.csv")):
        if db.one("SELECT 1 FROM regions WHERE code=?", (r["code"],)):
            continue
        db.insert("regions", dict(code=r["code"], name=r["name"], name_ar=r.get("name_ar"),
                                  parent_code=r.get("parent_code") or None, kind=r.get("kind"), notes=r.get("notes")))
        n += 1
    return n


def load_taxonomy(db: Database) -> int:
    n = 0
    rows = sorted(read_csv(_data("taxonomy", "cost_codes.csv")), key=lambda r: (int(r["level"]), r["code"]))
    for r in rows:
        if db.one("SELECT 1 FROM cost_codes WHERE code=?", (r["code"],)):
            continue
        db.insert("cost_codes", dict(code=r["code"], parent_code=r["parent_code"] or None, level=int(r["level"]),
                                     kind=r["kind"], name=r["name"], name_ar=r.get("name_ar"),
                                     short_name=r.get("short_name"), default_unit=r.get("default_unit") or None,
                                     description=r.get("description"), active=int(r.get("active", 1) or 1),
                                     is_system=int(r.get("is_system", 0) or 0)))
        n += 1
    return n


def load_sources(db: Database) -> int:
    p = _data("sources", "source_register.csv")
    if not p.exists():
        return 0
    n = 0
    cols = {c["name"] for c in db.all("PRAGMA table_info(sources)")}
    for r in read_csv(p):
        if not r.get("source_id"):
            continue
        vals = {k: (v or None) for k, v in r.items() if k in cols}
        cur = db.one("SELECT * FROM sources WHERE source_id=?", (r["source_id"],))
        if cur:                                   # the register is repo-owned reference data: refresh descriptive fields when the CSV changed
            diff = {k: v for k, v in vals.items() if k != "source_id" and cur[k] != v}
            if diff:
                db.update("sources", diff, "source_id=?", (r["source_id"],))
            continue
        db.insert("sources", vals)
        n += 1
    return n


CATALOGUES = [
    ("materials", "materials.csv"),
    ("labour", "labour_categories.csv"),
    ("plant", "plant_categories.csv"),
    ("equipment", "equipment_categories.csv"),
    ("subcontractors", "subcontract_packages.csv"),
]


def load_resource_catalogues(db: Database) -> dict[str, int]:
    """Load definition-only catalogues. Each new resource gets a 'Missing Rate' placeholder (no price)."""
    from . import rates as rate_service

    counts: dict[str, int] = {}
    for sub, fname in CATALOGUES:
        p = _data(sub, fname)
        counts[fname] = 0
        if not p.exists():
            continue
        for r in read_csv(p):
            if db.one("SELECT 1 FROM resources WHERE id=?", (r["id"],)):
                continue
            db.insert("resources", dict(
                id=r["id"], resource_type=r["resource_type"], cost_code=r.get("cost_code") or None,
                category=r.get("category"), description=r["description"], aliases=r.get("aliases"),
                specification=r.get("specification"), brand_requirements=r.get("brand_requirements"),
                unit=r["unit"], currency="SAR", geographic_applicability="KSA-ALL", notes=r.get("notes"),
                is_synthetic=0, is_active=1, created_by="system:seed", created_at=now_iso(), updated_at=now_iso()))
            rate_service.create_missing_placeholder(db, r["id"], unit=r["unit"], created_by="system:seed")
            counts[fname] += 1
    return counts


def load_assumption_register(db: Database) -> int:
    from .assumptions import FAMILY_DEFAULT_CATEGORY
    p = _data("assumptions", "assumptions_register.csv")
    if not p.exists():
        return 0
    n = 0
    for r in read_csv(p):
        if db.one("SELECT 1 FROM assumptions WHERE id=?", (r["id"],)):
            continue
        db.insert("assumptions", dict(
            id=r["id"], version=1, family=r["family"], name=r["name"], description=r.get("description"),
            applies_to=r.get("applies_to") or "ALL", applicability=r.get("applicability"),
            value_type=r.get("value_type") or "text", default_value=(r.get("default_value") or None),
            unit=r.get("unit") or None, engine_key=r.get("engine_key") or None,
            mandatory_for_projects=int(r.get("mandatory_for_projects") or 0), confidence=r.get("confidence") or "Low",
            source=r.get("source"), status="Pending Review", notes=r.get("notes"), is_synthetic=0,
            created_by="system:seed", created_at=now_iso(), origin="seed", category=FAMILY_DEFAULT_CATEGORY.get(r["family"])))
        n += 1
    return n


def load_standard_assemblies(db: Database) -> int:
    """Structure-only assemblies (no factors). Loaded as Draft: they cannot be mapped or approved until an estimator supplies the factors."""
    from . import assemblies as asm_service
    p = _data("assemblies", "standard_assemblies.csv")
    if not p.exists():
        return 0
    groups: dict[str, list[dict]] = {}
    for r in read_csv(p):
        groups.setdefault(r["assembly_code"], []).append(r)
    n = 0
    for code, ls in groups.items():
        if db.one("SELECT 1 FROM assemblies WHERE code=?", (code,)):
            continue
        first = ls[0]
        lines = [dict(line_type=l["line_type"], resource_id=l["resource_id"], productivity_basis=l["productivity_basis"] or None, notes=l["notes"]) for l in ls]
        for l in lines:
            if l["productivity_basis"] is None:
                del l["productivity_basis"]
        asm_service.create_assembly(db, SYSTEM_SEED, code=code, description=first["description"], unit=first["unit"], cost_code=first["cost_code"],
                                    source="Structure only - consumption/productivity factors NOT provided (not a benchmark)", confidence="Unverified",
                                    notes="Draft structure from data/assemblies/standard_assemblies.csv", lines_=lines)
        n += 1
    return n


def seed_reference(db: Database) -> dict:
    """Seed everything that is real structure (no prices). Safe to run repeatedly."""
    with db.tx():
        out = {
            "units": load_units(db),
            "regions": load_regions(db),
            "cost_codes": load_taxonomy(db),
            "sources": load_sources(db),
            "assumptions": load_assumption_register(db),
            "resources": load_resource_catalogues(db),
        }
        out["tax_categories"] = seed_tax_categories(db)
        out["standard_assemblies"] = load_standard_assemblies(db)
        out["fx_rates"] = seed_fx(db)
        audit.log(db, SYSTEM_SEED, "seed", "reference", "seed_reference", after=out)
    return out


def seed_tax_categories(db: Database) -> int:
    """Structural tax categories. VAT-STD is seeded PENDING REVIEW: its rate/date must be verified against
    current official ZATCA guidance by a Commercial Approver before use (see docs/KSA_DATA_SOURCES.md)."""
    n = 0
    seeds = [
        ("VAT-STD", "Standard-rated VAT", "15", "2020-07-01",
         "15% is shown on ZATCA's VAT page (read via Firecrawl, 2026-10-12, see data/sources/ACCESS_LOG.md); the 1 July 2020 "
         "effective date is inferred from ZATCA Implementing Regulation text, no single sentence pairs both. "
         "A Commercial Approver must verify against the VAT Law/current ZATCA guidance before approving."),
        ("VAT-ZERO", "Zero-rated", "0", "2018-01-01",
         "Structural category. Applicability of zero-rating to a given supply must be confirmed by the user."),
        ("VAT-EXEMPT", "Exempt / out of scope", "0", "2018-01-01",
         "Structural category. Applicability to a given supply must be confirmed by the user."),
    ]
    for code, name, rate, vf, note in seeds:
        if db.one("SELECT 1 FROM tax_categories WHERE code=? AND valid_from=?", (code, vf)):
            continue
        db.insert("tax_categories", dict(code=code, name=name, rate_pct=rate, valid_from=vf, recoverable=1,
                                         source_ref="ZATCA (to be verified)", verification_note=note,
                                         status="Pending Review", created_by="system:seed"))
        n += 1
    return n


def seed_fx(db: Database) -> int:
    """SAR/USD peg proposal with its official citation. Seeded PENDING REVIEW - a reviewer must approve before any conversion uses it."""
    if db.one("SELECT 1 FROM fx_rates WHERE from_ccy='USD' AND to_ccy='SAR' AND source LIKE 'SAMA%'"):
        return 0
    db.insert("fx_rates", dict(from_ccy="USD", to_ccy="SAR", rate="3.75", rate_date="2020-05-04", source="SAMA news 'SAMA Affirms Commitment to Exchange Rate Policy', 04 May 2020 (see data/sources ACCESS_LOG.md); verify the peg is still current",
                               status="Pending Review", is_synthetic=0, created_by="system:seed"))
    return 1


# ------------------------------------------------------------------------------------------------ optional definition packs
def _packs_dir() -> Path:
    return get_settings().data_dir / "packs"


def list_packs(db: Database | None = None) -> list[dict]:
    """Optional definitions-only packs under data/packs/<name>/ (manifest.json + cost_codes.csv + resources.csv)."""
    import json

    out = []
    root = _packs_dir()
    if not root.exists():
        return out
    for d in sorted(p for p in root.iterdir() if p.is_dir() and (p / "manifest.json").exists()):
        man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        loaded = None
        if db is not None:
            codes = [r["code"] for r in read_csv(d / "cost_codes.csv")] if (d / "cost_codes.csv").exists() else []
            have = sum(1 for c in codes if db.one("SELECT 1 FROM cost_codes WHERE code=?", (c,)))
            loaded = have == len(codes) and bool(codes)
        out.append(dict(name=d.name, description=man.get("description", ""), cost_codes=man.get("cost_codes"), resources=man.get("resources"), loaded=loaded))
    return out


def load_pack(db: Database, actor, name: str) -> dict:
    """Load an optional definitions-only pack. Insert-only and idempotent: existing cost codes/resources are never changed.
    Every new resource gets a 'Missing Rate' placeholder (no price). Packs must not carry prices - a priced column is refused."""
    from ..approvals import engine as approvals
    from ..core.errors import NotFound, ValidationFailed
    from . import rates as rate_service

    approvals.require_admin(actor, "loading a definitions pack")
    d = _packs_dir() / name
    if not name.replace("_", "").isalnum() or not (d / "manifest.json").exists():
        raise NotFound(f"Unknown pack '{name}'. Available: {[p['name'] for p in list_packs()]}")
    codes = read_csv(d / "cost_codes.csv") if (d / "cost_codes.csv").exists() else []
    res = read_csv(d / "resources.csv") if (d / "resources.csv").exists() else []
    forbidden = {"price", "unit_price", "rate", "amount", "cost"}
    for rows, label in ((codes, "cost_codes.csv"), (res, "resources.csv")):
        if rows and forbidden & {k.lower() for k in rows[0]}:
            raise ValidationFailed(f"Pack file {label} contains a price column; packs are definitions only.", code="PACK_HAS_PRICES")
    unit_codes = {r["code"] for r in db.all("SELECT code FROM units")}
    bad_units = sorted({r["unit"] for r in res if r["unit"] not in unit_codes})
    if bad_units:
        raise ValidationFailed(f"Pack uses units not in the unit registry: {bad_units}.", code="PACK_UNKNOWN_UNIT")
    added_codes = added_res = 0
    with db.tx():
        for r in sorted(codes, key=lambda r: (int(r["level"]), r["code"])):
            if db.one("SELECT 1 FROM cost_codes WHERE code=?", (r["code"],)):
                continue
            if r["parent_code"] and not db.one("SELECT 1 FROM cost_codes WHERE code=?", (r["parent_code"],)):
                raise ValidationFailed(f"Pack cost code {r['code']} has unknown parent {r['parent_code']}.", code="PACK_BAD_PARENT")
            db.insert("cost_codes", dict(code=r["code"], parent_code=r["parent_code"] or None, level=int(r["level"]), kind=r["kind"], name=r["name"],
                                         short_name=r.get("short_name") or None, default_unit=r.get("default_unit") or None, description=r.get("description"),
                                         active=int(r.get("active", 1) or 1), is_system=int(r.get("is_system", 0) or 0)))
            added_codes += 1
        for r in res:
            if db.one("SELECT 1 FROM resources WHERE id=?", (r["id"],)):
                continue
            if r.get("cost_code") and not db.one("SELECT 1 FROM cost_codes WHERE code=?", (r["cost_code"],)):
                raise ValidationFailed(f"Pack resource {r['id']} references unknown cost code {r['cost_code']}.", code="PACK_BAD_COST_CODE")
            db.insert("resources", dict(
                id=r["id"], resource_type=r["resource_type"], cost_code=r.get("cost_code") or None, category=r.get("category"),
                description=r["description"], aliases=r.get("aliases"), specification=r.get("specification"),
                brand_requirements=r.get("brand_requirements"), unit=r["unit"], currency="SAR", geographic_applicability="KSA-ALL",
                notes=r.get("notes"), is_synthetic=0, is_active=1, created_by=f"pack:{name}", created_at=now_iso(), updated_at=now_iso()))
            rate_service.create_missing_placeholder(db, r["id"], unit=r["unit"], created_by=f"pack:{name}")
            added_res += 1
        out = dict(pack=name, cost_codes_added=added_codes, resources_added=added_res, cost_codes_in_pack=len(codes), resources_in_pack=len(res))
        audit.log(db, actor, "pack", name, "load_pack", after=out)
    return out
