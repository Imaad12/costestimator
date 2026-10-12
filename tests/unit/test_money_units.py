from decimal import Decimal

import pytest

from app.core.errors import ValidationFailed
from app.core.money import D, D_opt, largest_remainder_allocate, quantize, to_text
from app.core.units import UnitRegistry

U = UnitRegistry([
    dict(code="m", name="m", dimension="length", to_base="1", synonyms="metre|lm|rm", ambiguous_synonyms=""),
    dict(code="mm", name="mm", dimension="length", to_base="0.001", synonyms="millimetre", ambiguous_synonyms=""),
    dict(code="m2", name="m2", dimension="area", to_base="1", synonyms="sqm|m²", ambiguous_synonyms=""),
    dict(code="m3", name="m3", dimension="volume", to_base="1", synonyms="cum|m³", ambiguous_synonyms="cm"),
    dict(code="kg", name="kg", dimension="mass", to_base="1", synonyms="", ambiguous_synonyms=""),
    dict(code="t", name="t", dimension="mass", to_base="1000", synonyms="tonne", ambiguous_synonyms="ton|tons"),
    dict(code="hr", name="hr", dimension="time_hr", to_base="1", synonyms="", ambiguous_synonyms=""),
    dict(code="day", name="day", dimension="time_day", to_base="1", synonyms="", ambiguous_synonyms=""),
    dict(code="ls", name="ls", dimension="lump", to_base="1", synonyms="lump sum", ambiguous_synonyms="sum"),
])


def test_decimal_parsing():
    assert D("1,234.50") == Decimal("1234.50")
    assert D("5%") == Decimal("5")
    assert D(0.1) == Decimal("0.1")          # no binary-float artefacts
    assert D_opt("abc") is None and D_opt("") is None and D_opt(None) is None
    with pytest.raises(ValueError):
        D("NaN")
    with pytest.raises(ValueError):
        D(True)


def test_to_text_canonical():
    assert to_text(Decimal("1.2300")) == "1.23" and to_text(Decimal("100")) == "100" and to_text(None) is None
    assert to_text(Decimal("1E+3")) == "1000"


def test_quantize_half_up_and_even():
    assert quantize(Decimal("2.675"), 2) == Decimal("2.68")
    assert quantize(Decimal("2.665"), 2, "half_even") == Decimal("2.66")
    assert quantize(Decimal("-2.675"), 2) == Decimal("-2.68")


def test_largest_remainder_sums_exactly():
    parts = largest_remainder_allocate(Decimal("100.00"), [Decimal(1)] * 3, 2)
    assert sum(parts) == Decimal("100.00") and sorted(parts) == [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")]
    parts = largest_remainder_allocate(Decimal("1000.01"), [Decimal("3"), Decimal("5"), Decimal("7")], 2)
    assert sum(parts) == Decimal("1000.01")
    assert largest_remainder_allocate(Decimal("10"), [Decimal(0), Decimal(0)], 2) == [Decimal("5.00"), Decimal("5.00")]
    assert largest_remainder_allocate(Decimal("5"), [], 2) == []


def test_unit_resolution():
    assert U.resolve("Sq.M").status == "unknown"        # not in this tiny test registry
    assert U.resolve("SQM").code == "m2" and U.resolve("m²").code == "m2" and U.resolve("LM").code == "m"
    r = U.resolve("ton")
    assert r.status == "ambiguous" and r.code is None       # never silently normalised
    assert U.resolve("cm").status == "ambiguous"
    assert U.resolve("sum").status == "ambiguous"
    assert U.resolve("").status == "missing" and U.resolve(None).status == "missing"
    assert U.resolve("furlong").status == "unknown"


def test_unit_conversion_rules():
    assert U.factor("t", "kg") == Decimal("1000")
    assert U.convert(Decimal("2.5"), "m", "mm") == Decimal("2500")
    assert not U.can_convert("m", "m2")
    assert not U.can_convert("hr", "day")                   # time never converts without an approved calendar
    with pytest.raises(ValidationFailed) as e:
        U.factor("hr", "day")
    assert e.value.code == "UNIT_CONVERSION_UNAVAILABLE"
