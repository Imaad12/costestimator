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
        if not r.get("source_id") or db.one("SELECT 1 FROM sources WHERE source_id=?", (r["source_id"],)):
            continue
        db.insert("sources", {k: (v or None) for k, v in r.items() if k in cols})
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
            created_by="system:seed", created_at=now_iso()))
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
