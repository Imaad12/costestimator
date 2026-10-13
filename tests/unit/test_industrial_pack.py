"""Optional industrial definitions pack (audit record LIB-04): definitions only, insert-only, idempotent, admin-only, never a price."""
from __future__ import annotations

import csv
import shutil

import pytest

from app.api.actions import run
from app.core.errors import NotFound, PermissionDenied, ValidationFailed
from app.services import refdata
from tests.conftest import ADMIN, ESTIMATOR


def _base_counts(db):
    return (db.one("SELECT COUNT(*) n FROM resources")["n"], db.one("SELECT COUNT(*) n FROM cost_codes")["n"])


def test_pack_not_loaded_by_default_and_listed(seeded):
    assert _base_counts(seeded)[0] == 927                                          # base catalogue unchanged
    assert seeded.one("SELECT 1 FROM cost_codes WHERE code='M'") is None
    packs = {p["name"]: p for p in refdata.list_packs(seeded)}
    assert packs["industrial"]["loaded"] is False and packs["industrial"]["resources"] == 258


def test_load_industrial_pack_is_definitions_only_and_idempotent(seeded):
    r0, c0 = _base_counts(seeded)
    out = refdata.load_pack(seeded, ADMIN, "industrial")
    assert out["cost_codes_added"] == 19 and out["resources_added"] == 258
    assert _base_counts(seeded) == (r0 + 258, c0 + 19)
    assert seeded.one("SELECT COUNT(*) n FROM cost_codes WHERE code LIKE 'M.%'")["n"] == 18
    # every new resource has exactly one placeholder rate, type Missing, no price; nothing approved
    rows = seeded.all("SELECT rr.* FROM resource_rates rr JOIN resources r ON r.id=rr.resource_id WHERE r.created_by='pack:industrial'")
    assert len(rows) == 258 and all(x["rate_type"] == "Missing Rate" and x["unit_price"] is None and x["status"] != "Approved" for x in rows)
    again = refdata.load_pack(seeded, ADMIN, "industrial")
    assert again["cost_codes_added"] == 0 and again["resources_added"] == 0
    assert _base_counts(seeded) == (r0 + 258, c0 + 19)
    assert seeded.one("SELECT COUNT(*) n FROM audit_log WHERE action='load_pack'")["n"] == 2
    assert {p["name"]: p for p in refdata.list_packs(seeded)}["industrial"]["loaded"] is True


def test_pack_load_is_admin_only_and_unknown_pack_refused(seeded):
    with pytest.raises(PermissionDenied):
        refdata.load_pack(seeded, ESTIMATOR, "industrial")
    with pytest.raises(NotFound):
        refdata.load_pack(seeded, ADMIN, "../etc")
    assert run(seeded, ADMIN, "load_pack", {"name": "industrial"})["resources_added"] == 258


def test_pack_with_price_column_or_unknown_unit_is_refused(seeded, settings, tmp_path):
    src = settings.data_dir / "packs" / "industrial"
    for variant in ("price", "unit"):
        dd = tmp_path / f"data_{variant}"
        shutil.copytree(src, dd / "packs" / "industrial")
        rp = dd / "packs" / "industrial" / "resources.csv"
        rows = list(csv.DictReader(open(rp, newline="", encoding="utf-8")))
        if variant == "price":
            for r in rows:
                r["unit_price"] = "10"
        else:
            rows[0]["unit"] = "zzz_not_a_unit"
        with open(rp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
        old = settings.data_dir
        settings.data_dir = dd
        try:
            with pytest.raises(ValidationFailed) as e:
                refdata.load_pack(seeded, ADMIN, "industrial")
            assert e.value.code in ("PACK_HAS_PRICES", "PACK_UNKNOWN_UNIT")
        finally:
            settings.data_dir = old
    assert seeded.one("SELECT 1 FROM cost_codes WHERE code='M'") is None                # nothing half-loaded
