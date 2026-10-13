"""Industrial/process units (audit record SCO-04): exact conversions, no silent re-meaning, administrator-managed additions."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.api.actions import run
from app.core.errors import Conflict, PermissionDenied, ValidationFailed
from app.core.units import registry
from app.imports import boq as bi
from app.services import projects
from tests.conftest import ADMIN, ESTIMATOR
from tests.helpers import write_boq


def test_industrial_units_resolve_and_convert_exactly(seeded):
    reg = registry(seeded)
    for text, code in (("inch-dia", "inch_dia"), ("Joints", "joint"), ("spool", "spool"), ("Loop", "loop"), ("MVA", "mva"), ("m3/h", "m3_h"), ("LPS", "l_s"), ("L/S", "ls"),
                       ("bar", "bar"), ("MPa", "mpa"), ("MW", "mw"), ("ft", "ft"), ("sq.ft", "ft2"), ("lbs", "lb"), ("bbl", "bbl"), ("man-hours", "hr")):
        assert reg.resolve(text).code == code, text
    assert reg.convert(Decimal(2), "mva", "kva") == 2000 and reg.convert(Decimal(3), "mw", "kw") == 3000
    assert reg.convert(Decimal(1), "bar", "kpa") == 100 and reg.convert(Decimal(2), "mpa", "bar") == 20
    assert reg.convert(Decimal(10), "l_s", "m3_h") == 36                                       # 1 l/s = 3.6 m3/h exactly
    assert reg.convert(Decimal(1), "ft", "inch") == Decimal("12")                              # 0.3048 / 0.0254
    assert reg.convert(Decimal(1), "gal", "l") == Decimal("3.785411784")
    assert reg.resolve("ton").status == "ambiguous"                                            # still never guessed
    # nothing converts across count-like or non-exact dimensions
    for a, b in (("inch_dia", "joint"), ("psi", "bar"), ("loop", "nr"), ("m", "ft2"), ("kw", "kva")):
        assert not reg.can_convert(a, b), (a, b)


def test_industrial_boq_imports_with_no_unknown_units(seeded, tmp_path):
    pid = projects.create_project(seeded, ESTIMATOR, name="Piping BOQ (SYNTHETIC)", is_demo=True)
    rows = [("1", "6in CS pipe fabrication", "inch-dia", "100", "", ""), ("2", "Butt welds", "joint", "50", "", ""), ("3", "Pipe spools", "spool", "40", "", ""),
            ("4", "Instrument loops", "loop", "10", "", ""), ("5", "Transformer", "MVA", "2", "", ""), ("6", "Pump duty", "m3/h", "250", "", ""),
            ("7", "Hydrotest pressure", "bar", "40", "", "")]
    r = bi.import_boq(seeded, ESTIMATOR, pid, write_boq(tmp_path / "ind.csv", rows))
    units = {x["item_key"]: (x["unit"], x["unit_status"]) for x in seeded.all("SELECT item_key, unit, unit_status FROM boq_items WHERE project_id=?", (pid,))}
    assert r["rejected"] == 0 and all(s == "ok" for _, s in units.values()), units
    assert units["1"][0] == "inch_dia" and units["5"][0] == "mva"


def test_administrator_adds_units_with_guards(seeded):
    with pytest.raises(PermissionDenied):
        run(seeded, ESTIMATOR, "add_unit", {"code": "wp", "name": "work pack", "dimension": "work_pack"})
    assert run(seeded, ADMIN, "add_unit", {"code": "wp", "name": "work pack", "dimension": "work_pack", "synonyms": "workpack|wpk"}) == "wp"
    assert registry(seeded).resolve("WPK").code == "wp"                                          # takes effect immediately, audited
    assert seeded.scalar("SELECT COUNT(*) FROM audit_log WHERE entity_type='unit' AND entity_id='wp'") == 1
    for bad, code in (({"code": "wp", "name": "x", "dimension": "work_pack"}, "UNIT_EXISTS"),
                      ({"code": "w2", "name": "x", "dimension": "work_pack", "synonyms": "m3"}, "UNIT_SPELLING_CLASH"),    # would silently change how m3 is read
                      ({"code": "w3", "name": "x", "dimension": "work_pack", "synonyms": "ton"}, "UNIT_SPELLING_CLASH"),   # already declared ambiguous
                      ({"code": "w4", "name": "x", "dimension": "brand_new", "to_base": "5"}, "NO_BASE_UNIT"),
                      ({"code": "w5", "name": "x", "dimension": "work_pack", "to_base": "-1"}, "BAD_UNIT_FACTOR"),
                      ({"code": "W6!", "name": "x", "dimension": "work_pack"}, "BAD_UNIT_CODE")):
        with pytest.raises((Conflict, ValidationFailed)) as e:
            run(seeded, ADMIN, "add_unit", bad)
        assert e.value.code == code, (bad, e.value.code)
    # a new dimension is NOT auto-convertible even with an exact factor
    run(seeded, ADMIN, "add_unit", {"code": "wp2", "name": "double pack", "dimension": "work_pack", "to_base": "2"})
    assert not registry(seeded).can_convert("wp2", "wp")
