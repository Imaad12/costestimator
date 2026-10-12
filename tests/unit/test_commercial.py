"""Commercial engine tests. Expected values are computed independently by hand (SYNTHETIC)."""
from decimal import Decimal

import pytest

from app.core.errors import ValidationFailed
from app.estimators.commercial import compute_commercial, validate_policy

D = Decimal


def calc(policy, direct="100000", indirect="20000", shares=None, rates=None):
    return compute_commercial(policy, direct=D(direct), indirect=D(indirect), money_dp=2, tax_shares=shares or {"VAT-STD": D(1)},
                              tax_rates=rates or {"VAT-STD": D(15)})


def test_markup_method_independent_calculation():
    p = {"method": "markup", "markup_pct": "10", "contingency": {"pct": "5", "base": "direct_indirect"},
         "risk_items": [{"name": "Supply chain", "pct": "2", "base": "direct"}, {"name": "Fixed allowance", "amount": "1500"}],
         "escalation": {"pct": "3", "base": "cost_before_escalation"}}
    c = calc(p)
    # C0 120,000 ; Ct 6,000 ; R 2,000 + 1,500 = 3,500 ; base for E = 129,500 -> 3,885 ; T = 133,385 ; S = T x 1.10 = 146,723.50
    assert c.pre_contingency_cost == D("120000.00") and c.contingency == D("6000.00") and c.risk == D("3500.00")
    assert c.escalation == D("3885.00") and c.total_cost == D("133385.00")
    assert c.selling_price_pre_discount == D("146723.50") and c.margin_amount == D("13338.50")
    assert c.net_price == D("146723.50") and c.method == "markup" and "Cost x (1 + Markup)" in c.method_label


def test_gross_margin_method_differs_from_markup():
    base = {"contingency": {"pct": "0", "base": "direct"}}
    m = calc({"method": "markup", "markup_pct": "20", **base})
    g = calc({"method": "margin", "margin_pct": "20", **base})
    assert m.selling_price_pre_discount == D("144000.00")        # 120,000 x 1.2
    assert g.selling_price_pre_discount == D("150000.00")        # 120,000 / 0.8
    assert g.effective_margin_pct == D("20") and m.effective_markup_pct == D("20")
    assert "Gross Margin" in g.method_label and g.method_label != m.method_label


def test_contingency_base_is_explicit_and_changes_result():
    a = calc({"method": "markup", "markup_pct": "0", "contingency": {"pct": "10", "base": "direct"}})
    b = calc({"method": "markup", "markup_pct": "0", "contingency": {"pct": "10", "base": "direct_indirect"}})
    assert a.contingency == D("10000.00") and b.contingency == D("12000.00")
    with pytest.raises(ValidationFailed):
        calc({"method": "markup", "markup_pct": "0", "contingency": {"pct": "10", "base": "everything"}})


def test_discount_rounding_and_tax_separation():
    p = {"method": "markup", "markup_pct": "10", "discount": {"pct": "2"}, "rounding": {"step": "100", "mode": "half_up"}}
    c = calc(p)
    # T=120,000 ; S=132,000 ; discount 2% = 2,640 ; N=129,360 ; rounded to nearest 100 = 129,400 ; tax 15% = 19,410
    assert c.discount == D("2640.00") and c.net_price_unrounded == D("129360.00") and c.net_price == D("129400.00")
    assert c.rounding_delta == D("40.00") and c.tax_total == D("19410.00") and c.final_payable == D("148810.00")
    assert c.net_price + c.tax_total == c.final_payable            # tax kept separate from price


def test_fixed_discount_and_multiple_tax_categories():
    p = {"method": "markup", "markup_pct": "10", "discount": {"amount": "1000"}}
    c = calc(p, shares={"VAT-STD": D("3"), "VAT-ZERO": D("1")}, rates={"VAT-STD": D("15"), "VAT-ZERO": D("0")})
    assert c.net_price == D("131000.00")                            # 132,000 - 1,000
    assert c.tax_by_category["VAT-STD"]["base"] == D("98250.00") and c.tax_by_category["VAT-ZERO"]["base"] == D("32750.00")
    assert c.tax_total == D("14737.50")


def test_unresolved_tax_rate_never_assumed():
    c = calc({"method": "markup", "markup_pct": "5"}, rates={"VAT-STD": None})
    assert c.tax_by_category["VAT-STD"]["tax"] is None and c.tax_total == 0 and any(e.code == "TAX_RATE_UNRESOLVED" for e in c.exceptions)


def test_policy_validation_and_double_count_guards():
    assert validate_policy({}) and "method" in validate_policy({})[0]
    assert validate_policy({"method": "markup"})                                         # markup_pct required
    assert validate_policy({"method": "margin", "margin_pct": "100"})                    # division by zero guard
    assert validate_policy({"method": "margin", "margin_pct": "-1"})
    dup = {"method": "markup", "markup_pct": "5", "risk_items": [{"name": "X", "amount": "1"}, {"name": "x ", "amount": "2"}]}
    assert any("twice" in p for p in validate_policy(dup))
    cont = {"method": "markup", "markup_pct": "5", "contingency": {"pct": "5", "base": "direct"}, "risk_items": [{"name": "Extra contingency", "pct": "1", "base": "direct"}]}
    assert any("contingency" in p.lower() for p in validate_policy(cont))
    assert validate_policy({"method": "markup", "markup_pct": "5", "risk_items": [{"name": "r", "pct": "1"}]})   # base missing
    with pytest.raises(ValidationFailed):
        calc({"method": "margin", "margin_pct": "100"})


def test_zero_and_trivial_values_permitted():
    c = calc({"method": "markup", "markup_pct": "0"}, direct="0", indirect="0")
    assert c.net_price == 0 and c.final_payable == 0
    c = calc({"method": "markup", "markup_pct": "0", "contingency": {"pct": "0", "base": "direct"}})
    assert c.total_cost == D("120000.00") == c.net_price


def test_trace_documents_every_step():
    c = calc({"method": "markup", "markup_pct": "10", "contingency": {"pct": "5", "base": "direct"}})
    names = [t.name for t in c.trace]
    assert names[0].startswith("Pre-contingency") and "Contingency" in names and any(n.startswith("Selling price") for n in names)
    cont = next(t for t in c.trace if t.name == "Contingency")
    assert cont.base_name == "direct" and cont.base_value == D("100000")
