"""Calculator tests. Expected values are computed by hand (see comments), not by
the engine. NOTE: these are arithmetic reference cases on a synthetic rate table;
they are not transcriptions of real court rulings."""
from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from pydantic import ValidationError

from app.engine.calculator import (
    apply_tmc_cap,
    calculate_day_by_day_ledger,
    get_applicable_rate,
    select_category,
)
from app.engine.cmf_rates import RateNotFoundError, RateTable, load_default_table
from app.schemas.liquidation import Currency, DayCount, LiquidationParams, RateCategory


def _rates(under50, mid, over, uf, tmc_mid=None):
    r = lambda c, t=None: {"corriente": str(c), "tmc": str(t if t is not None else D(str(c)) * D("1.5"))}
    return {"non_reajustable_clp_under_50_uf": r(under50),
            "non_reajustable_clp_50_to_200_uf": r(mid, tmc_mid),
            "non_reajustable_clp_over_200_uf": r(over), "reajustable_uf_all": r(uf)}

def _period(ym, frm, to, rates):
    return {"period_id": ym, "valid_from": frm, "valid_to": to, "rates": rates}

UF10 = {"2023-12": "36000.00", "2024-01": "36000.00", "2024-02": "36360.00",
        "2024-03": "36720.00", "2024-04": "37000.00"}
TABLE = RateTable({
    "metadata": {"verified": True, "source": "synthetic test table"}, "uf_10th": UF10,
    "periods": [
        _period("2024-01", "2024-01-01", "2024-01-31", _rates("28.00", "28.00", "12.00", "5.00")),
        _period("2024-02", "2024-02-01", "2024-02-29", _rates("30.00", "30.00", "13.00", "5.00")),
        _period("2024-03", "2024-03-01", "2024-03-31", _rates("30.00", "30.00", "13.00", "5.00")),
    ],
})

# UNVERIFIED vectors supplied by an external research tool (Q1 2024, >=200 UF).
def _q1(p2_to):
    o = lambda c: _rates("28.12", "21.34", c, "5.12")
    return RateTable({"metadata": {"verified": True, "source": "external vector"}, "uf_10th": UF10,
        "periods": [_period("2024-01", "2024-01-15", "2024-02-14", o("14.40")),
                    _period("2024-02", "2024-02-15", p2_to, o("13.80")),
                    _period("2024-03", "2024-03-16" if p2_to == "2024-03-15" else "2024-03-15",
                            "2024-04-14", o("13.10"))]})

def clp(**kw):
    base = dict(principal=D(1_000_000), currency=Currency.CLP, issue_date=date(2024, 1, 1),
                day_count=DayCount.ACT_365)
    return LiquidationParams(**{**base, **kw})

def test_single_month_corriente():
    # 1,000,000 * 30% * 29 / 365 = 23,835.616 -> 23,836
    led = calculate_day_by_day_ledger(
        clp(maturity_date=date(2024, 1, 31), cutoff_date=date(2024, 2, 29)), TABLE)
    assert led.interest_clp == D(23836) and led.total_clp == D(1_023_836)
    assert len(led.days) == 59 and led.category is RateCategory.CLP_UNDER_50
    assert not [w for w in led.warnings if "TMC" in w]

def test_no_interest_before_maturity_without_agreed_rate():
    led = calculate_day_by_day_ledger(
        clp(maturity_date=date(2024, 1, 20), cutoff_date=date(2024, 1, 20)), TABLE)
    assert led.interest_clp == 0 and led.total_clp == D(1_000_000)

def test_cross_month_rate_change_and_cumulative_rounding():
    # Jan 21-31: 11d @28% = 8,438.356 ; Feb 1-10: 10d @30% = 8,219.178
    # total 16,657.534 -> 16,658 ; Jan cum 8,438 ; Feb row = 16,658 - 8,438 = 8,220
    led = calculate_day_by_day_ledger(
        clp(maturity_date=date(2024, 1, 20), cutoff_date=date(2024, 2, 10)), TABLE)
    assert led.interest_clp == D(16658)
    jan, feb = led.months
    assert (jan.period, jan.days, jan.interest) == ("2024-01", 30, D(8438))
    assert jan.interest + feb.interest == D(16658)
    assert feb.interest == D(8220)

def test_tmc_cap_and_warning():
    # agreed 60% > TMC 45% (30*1.5): 1,000,000*45%*29/365 = 35,753.42 -> 35,753
    led = calculate_day_by_day_ledger(
        clp(maturity_date=date(2024, 1, 31), cutoff_date=date(2024, 2, 29),
            issue_date=date(2024, 1, 31), agreed_rate=D(60)), TABLE)
    assert led.interest_clp == D(35753)
    assert any("excede la TMC" in w for w in led.warnings)

def test_agreed_rate_below_cap_applies_both_phases():
    # 59 days @24% : 1,000,000*24%*59/365 = 38,794.52 -> 38,795
    led = calculate_day_by_day_ledger(
        clp(maturity_date=date(2024, 1, 31), cutoff_date=date(2024, 2, 29),
            agreed_rate=D(24)), TABLE)
    assert led.interest_clp == D(38795) and not [w for w in led.warnings if "TMC" in w]

def test_bracket_gte_200_uf():
    # 10,000,000 / 36,000 = 277.8 UF -> >=200 ; 13% : *13%*29/365 = 103,287.67->103,288
    led = calculate_day_by_day_ledger(
        clp(principal=D(10_000_000), maturity_date=date(2024, 1, 31),
            cutoff_date=date(2024, 2, 29)), TABLE)
    assert led.category is RateCategory.CLP_OVER_200 and led.interest_clp == D(103288)

def test_uf_value_anchors_and_interpolation():
    assert TABLE.uf_value(date(2024, 2, 10)) == D("36360.00")
    expected = 36000 * (36360 / 36000) ** (26 / 31)  # Feb 5 is day 26 of 31
    assert abs(float(TABLE.uf_value(date(2024, 2, 5))) - expected) <= 0.0051

def test_uf_operation_ledger():
    # 100 UF, 10 days @5% : 100*0.05*10/365 = 0.136986 -> 0.1370 UF
    led = calculate_day_by_day_ledger(
        LiquidationParams(principal=D(100), currency=Currency.UF,
                          issue_date=date(2024, 2, 10), maturity_date=date(2024, 2, 10),
                          cutoff_date=date(2024, 2, 20), day_count=DayCount.ACT_365), TABLE)
    assert led.interest_native == D("0.1370") and led.category is RateCategory.UF
    uf_cut = 36360 * (36720 / 36360) ** (10 / 29)
    assert abs(float(led.total_clp) - 100.1370 * uf_cut) <= 1.0
    assert led.days[-1].readjustment_factor == led.days[-1].uf_value / TABLE.uf_value(date(2024, 2, 10))
    assert led.total_clp == led.principal_clp + led.interest_clp

def test_get_applicable_rate_and_cap_helpers():
    d = get_applicable_rate(date(2024, 2, 15), Currency.CLP, D(50), None, TABLE)
    assert (d.annual_rate, d.tmc, d.source) == (D("30.00"), D("45.00"), "corriente")
    assert apply_tmc_cap(D(50), D(45)) == (D(45), True)
    assert apply_tmc_cap(D(40), D(45)) == (D(40), False)
    assert select_category(Currency.CLP, D(50)) is RateCategory.CLP_UNDER_50
    assert select_category(Currency.CLP, D("50.01")) is RateCategory.CLP_50_TO_200
    assert select_category(Currency.CLP, D("199.99")) is RateCategory.CLP_50_TO_200
    assert select_category(Currency.CLP, D(200)) is RateCategory.CLP_OVER_200
    assert select_category(Currency.UF, D(5000)) is RateCategory.UF

def test_validation_errors():
    with pytest.raises(ValidationError):
        clp(maturity_date=date(2024, 1, 31), cutoff_date=date(2024, 1, 30))
    with pytest.raises(ValidationError):
        clp(principal=D(0), maturity_date=date(2024, 1, 31), cutoff_date=date(2024, 2, 1))
    with pytest.raises(RateNotFoundError):
        calculate_day_by_day_ledger(
            clp(maturity_date=date(2024, 1, 31), cutoff_date=date(2024, 6, 1)), TABLE)

def test_seed_file_integrity_and_unverified_flag():
    t = load_default_table()
    assert t.verified is False
    prev_end = None
    for start, end, cats in t._periods:
        assert start <= end and (prev_end is None or start == prev_end + timedelta(days=1))
        prev_end = end
        assert set(cats) == {c.value for c in RateCategory}
        assert all(c["corriente"] < c["tmc"] <= 2 * c["corriente"] for c in cats.values())
    led = calculate_day_by_day_ledger(
        clp(issue_date=date(2024, 1, 20), maturity_date=date(2024, 3, 20),
            cutoff_date=date(2025, 3, 20)))
    assert any("NO verificadas" in w for w in led.warnings)
    assert sum(m.interest for m in led.months) == led.interest_accrued_native

# --- external vectors (day count ACT/360, the default) ---
A = dict(principal=D(10_000_000), currency=Currency.CLP, issue_date=date(2024, 1, 15),
         maturity_date=date(2024, 1, 15), cutoff_date=date(2024, 3, 15))

def test_vector_a_with_period2_extended_to_cutoff():
    # 30d @14.40 = 120,000 ; 30d @13.80 = 115,000 ; total 235,000
    led = calculate_day_by_day_ledger(LiquidationParams(**A), _q1("2024-03-15"))
    assert (led.interest_clp, led.total_clp) == (D(235_000), D(10_235_000))

def test_vector_a_with_its_own_validity_windows_differs():
    # Period 2 ends 03-14, so 03-15 uses 13.10: 111,166.667 + 3,638.889 + 120,000 = 234,805.556
    led = calculate_day_by_day_ledger(LiquidationParams(**A), _q1("2024-03-14"))
    assert led.interest_clp == D(234_806)

def test_vector_b_tmc_cap():
    # 5,000,000 CLP = 138 UF -> 50-200 bracket, TMC 28.50: 5e6*28.5/36000*30 = 118,750
    t = RateTable({"metadata": {"verified": True}, "uf_10th": UF10, "periods": [
        _period("2024-01", "2024-01-15", "2024-02-14", _rates("21.34", "21.34", "14.40", "5.12", "28.50"))]})
    led = calculate_day_by_day_ledger(LiquidationParams(
        principal=D(5_000_000), currency=Currency.CLP, issue_date=date(2024, 1, 15),
        maturity_date=date(2024, 2, 14), cutoff_date=date(2024, 2, 14), agreed_rate=D(45)), t)
    assert led.interest_clp == D(118_750)  # uncapped would be 187,500
    assert any("excede la TMC" in w for w in led.warnings)


# --- payments (abonos): interest first, then capital (CC art. 1595) ---
from app.schemas.liquidation import Payment


def test_payment_smaller_than_interest_is_imputed_to_interest_only():
    # Jan 21-31: 8,438.356 due; abono 5,000 -> interest due 3,438.356, capital intact.
    # Feb 1-10: +8,219.178 -> outstanding 11,657.534 -> 11,658 ; generated 16,658 ; paid 5,000
    led = calculate_day_by_day_ledger(clp(
        maturity_date=date(2024, 1, 20), cutoff_date=date(2024, 2, 10),
        payments=(Payment(date=date(2024, 1, 31), amount=D(5000)),)), TABLE)
    assert (led.capital_native, led.interest_native) == (D(1_000_000), D(11_658))
    assert (led.interest_accrued_native, led.payments_total) == (D(16_658), D(5000))
    assert led.total_clp == D(1_011_658)
    assert led.months[0].payments == D(5000)


def test_payment_exceeding_interest_reduces_capital():
    # On Feb 10 interest due rounds to 16,658; abono 20,000 -> 3,342 reduces capital.
    led = calculate_day_by_day_ledger(clp(
        maturity_date=date(2024, 1, 20), cutoff_date=date(2024, 2, 10),
        payments=(Payment(date=date(2024, 2, 10), amount=D(20_000)),)), TABLE)
    assert (led.capital_native, led.interest_native, led.total_clp) == (D(996_658), D(0), D(996_658))


def test_capital_reduction_lowers_later_interest():
    # Abono 108,438 on Jan 31 clears interest (8,438) and 100,000 capital.
    # 0.356 of Jan interest stays unpaid; Feb 1-10 on 900,000 @30%: 7,397.260 + 0.356 = 7,397.616 -> 7,398
    led = calculate_day_by_day_ledger(clp(
        maturity_date=date(2024, 1, 20), cutoff_date=date(2024, 2, 10),
        payments=(Payment(date=date(2024, 1, 31), amount=D(108_438)),)), TABLE)
    assert (led.capital_native, led.interest_native, led.total_clp) == (D(900_000), D(7_398), D(907_398))


def test_payment_validation():
    with pytest.raises(ValidationError):
        clp(maturity_date=date(2024, 1, 20), cutoff_date=date(2024, 2, 10),
            payments=(Payment(date=date(2024, 3, 1), amount=D(1)),))
    with pytest.raises(ValueError, match="excede"):
        calculate_day_by_day_ledger(clp(
            maturity_date=date(2024, 1, 20), cutoff_date=date(2024, 2, 10),
            payments=(Payment(date=date(2024, 2, 10), amount=D(2_000_000)),)), TABLE)


def test_uf_payment_reduces_capital_in_uf():
    led = calculate_day_by_day_ledger(LiquidationParams(
        principal=D(100), currency=Currency.UF, issue_date=date(2024, 2, 10),
        maturity_date=date(2024, 2, 10), cutoff_date=date(2024, 2, 20), day_count=DayCount.ACT_365,
        payments=(Payment(date=date(2024, 2, 20), amount=D(10)),)), TABLE)
    assert led.capital_native == D(90) or led.capital_native == D(100) - (D(10) - led.interest_accrued_native)
    uf_cut = TABLE.uf_value(date(2024, 2, 20))
    assert led.principal_clp == (led.capital_native * uf_cut).quantize(D(1), "ROUND_HALF_UP")
