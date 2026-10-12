"""Shipped reference data: structure, honesty about prices, and the extensibility promises."""
import csv
from pathlib import Path

import pytest

from app.core.errors import ValidationFailed
from app.integrations.base import REGISTRY, NotConfigured
from app.reporting.coverage import library_coverage
from app.services import assemblies, assumptions, rates
from app.services import refdata

from tests.conftest import ADMIN, COMMERCIAL, ESTIMATOR

DATA = Path(__file__).resolve().parents[2] / "data"


def test_every_required_trade_division_and_subtrade_is_present(seeded):
    rows = seeded.all("SELECT * FROM cost_codes")
    divisions = {r["code"] for r in rows if r["level"] == 1}
    assert divisions == set("ABCDEFGHIJKL")
    subs = [r for r in rows if r["level"] == 2]
    assert len(subs) == 140
    names = {r["name"] for r in subs}
    for must in ("Chillers and cooling towers", "Sprinkler systems", "MV and LV switchgear", "Structured cabling and fibre optics", "Lifts and escalators",
                 "Stormwater drainage", "Post-tensioning", "Provisional sums", "Prime-cost sums", "Mobilisation and demobilisation", "EV charging"):
        assert must in names
    assert all(r["parent_code"] in divisions for r in subs)


def test_new_trade_can_be_added_without_code_changes(seeded):
    from app.api.actions import run
    from app.core.errors import PermissionDenied
    with pytest.raises(PermissionDenied):
        run(seeded, ESTIMATOR, "add_cost_code", {"code": "E.14", "name": "Cleanroom HVAC", "parent_code": "E"})        # admin only
    run(seeded, ADMIN, "add_cost_code", {"code": "E.14", "name": "Cleanroom HVAC", "parent_code": "E"})
    run(seeded, ADMIN, "add_cost_code", {"code": "E.14.01", "name": "HEPA filter housings", "parent_code": "E.14"})
    rid = rates.create_resource(seeded, ESTIMATOR, resource_type="equipment", description="HEPA housing", unit="nr", cost_code="E.14.01")
    assert rid.startswith("EQP-E") and seeded.scalar("SELECT level FROM cost_codes WHERE code='E.14.01'") == 3
    assemblies.create_assembly(seeded, ESTIMATOR, code="MY-HEPA", description="HEPA", unit="nr", cost_code="E.14.01", lines_=[dict(line_type="equipment", resource_id=rid, factor="1")])
    assumptions.create_assumption(seeded, ESTIMATOR, id="ASMP-X-001", family="C", name="Custom wastage", value_type="percent")


def test_catalogues_contain_no_prices_and_use_valid_units(seeded):
    for sub, f in (("materials", "materials.csv"), ("labour", "labour_categories.csv"), ("plant", "plant_categories.csv"), ("equipment", "equipment_categories.csv"),
                   ("subcontractors", "subcontract_packages.csv")):
        rows = list(csv.DictReader(open(DATA / sub / f, encoding="utf-8-sig")))
        assert rows and not (set(rows[0]) & {"price", "rate", "unit_price", "cost"}), f
    # every catalogue resource starts with a Missing Rate placeholder and no approved price
    assert seeded.scalar("SELECT COUNT(*) FROM resources") == 927
    assert seeded.scalar("SELECT COUNT(*) FROM resource_rates WHERE unit_price IS NOT NULL") == 0
    assert seeded.scalar("SELECT COUNT(*) FROM resource_rates WHERE rate_type='Missing Rate'") == 927
    cov = library_coverage(seeded)["totals"]
    assert cov == {"resources": 927, "real_approved_rate": 0, "synthetic_approved_rate": 0, "missing": 927, "pct_with_real_approved_rate": 0.0}


def test_assumption_register_has_no_invented_numbers(seeded):
    rows = seeded.all("SELECT * FROM assumptions")
    assert len(rows) >= 300 and {r["family"] for r in rows} == set("ABCDEFGHIJKL")
    with_default = {r["id"]: r["default_value"] for r in rows if r["default_value"] not in (None, "")}
    assert set(with_default.values()) == {"3", "2", "VAT-STD", "180"}                 # only methodological defaults
    assert all(r["status"] == "Pending Review" for r in rows)                          # nothing pre-approved
    keys = {r["engine_key"] for r in rows if r["engine_key"]}
    assert {"qty.rounding_dp", "money.rounding_dp", "labour.shift_hours", "labour.productive_hours_per_shift", "plant.utilisation_pct",
            "calendar.working_days_per_week", "calendar.working_days_per_month", "calendar.hours_per_day", "rates.age_warning_days", "tax.default_category"} <= keys


def test_standard_assemblies_are_structure_only_drafts(seeded):
    drafts = seeded.all("SELECT * FROM assemblies WHERE code LIKE 'STD-%'")
    assert len(drafts) == 26 and all(d["status"] == "Draft" for d in drafts)
    n_lines = seeded.scalar("SELECT COUNT(*) FROM assembly_lines WHERE assembly_pk IN (SELECT pk FROM assemblies WHERE code LIKE 'STD-%')")
    assert n_lines == 72 and seeded.scalar("SELECT COUNT(*) FROM assembly_lines WHERE factor IS NOT NULL AND assembly_pk IN (SELECT pk FROM assemblies WHERE code LIKE 'STD-%')") == 0
    assemblies.submit_assembly(seeded, ESTIMATOR, "STD-CIV-EXC")
    with pytest.raises(ValidationFailed) as e:
        assemblies.approve_assembly(seeded, COMMERCIAL, "STD-CIV-EXC")                 # cannot be approved while factors are missing
    assert e.value.code == "ASSEMBLY_INVALID" and "factor is missing" in str(e.value.details)


def test_tax_and_fx_seeds_are_pending_until_a_human_verifies(seeded):
    vat = seeded.one("SELECT * FROM tax_categories WHERE code='VAT-STD'")
    assert vat["status"] == "Pending Review" and vat["rate_pct"] == "15" and "verify" in vat["verification_note"].lower()
    assert seeded.scalar("SELECT status FROM fx_rates WHERE from_ccy='USD'") == "Pending Review"
    assert seeded.scalar("SELECT COUNT(*) FROM sources") == 27


def test_circular_assemblies_are_prevented(seeded):
    for c in ("CY-A", "CY-B", "CY-C"):
        assemblies.create_assembly(seeded, ESTIMATOR, code=c, description=c, unit="m")
    pa, pb = (assemblies.get(seeded, c)["pk"] for c in ("CY-A", "CY-B"))
    assemblies.add_line(seeded, ESTIMATOR, pa, line_type="assembly", child_assembly_code="CY-B", factor="1")
    assemblies.add_line(seeded, ESTIMATOR, assemblies.get(seeded, "CY-B")["pk"], line_type="assembly", child_assembly_code="CY-C", factor="1")
    with pytest.raises(ValidationFailed) as e:
        assemblies.add_line(seeded, ESTIMATOR, assemblies.get(seeded, "CY-C")["pk"], line_type="assembly", child_assembly_code="CY-A", factor="1")
    assert e.value.code == "CIRCULAR_ASSEMBLY"
    with pytest.raises(ValidationFailed):
        assemblies.add_line(seeded, ESTIMATOR, pa, line_type="assembly", child_assembly_code="CY-A", factor="1")


def test_integration_points_are_honest():
    assert REGISTRY["local-file"].info.implemented
    for name in ("gastat-cci", "etimad-awards", "claude-extraction"):
        assert not REGISTRY[name].info.implemented
        with pytest.raises(NotConfigured) as e:
            REGISTRY[name].stage(None, None, Path("x"))
        assert "NOT implemented" in e.value.message
