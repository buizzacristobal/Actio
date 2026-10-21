"""Deterministic day-by-day liquidation engine (Ley 18.010).

Pure Decimal arithmetic. No LLM, no floats, no I/O besides the rate table.

Modelling conventions (documented in docs/LEGAL_SPEC.md):
  * Interest is simple (no anatocismo): annual_rate / basis per day (params.day_count).
  * Conventional interest accrues (issue, maturity]; moratory (maturity, cutoff].
  * Moratory rate = agreed rate if any, else interés corriente; always <= TMC.
  * The CLP bracket (<200 UF / >=200 UF) is fixed by the capital's UF value on
    the issue date.
  * UF operations accrue interest in UF; CLP equivalents use the UF of each date.
  * Monthly interest uses cumulative rounding, so the months sum to the total.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.engine.cmf_rates import RateTable, load_default_table
from app.schemas.liquidation import (
    Currency,
    LedgerDay,
    LedgerMonth,
    LiquidationLedger,
    LiquidationParams,
    Phase,
    RateCategory,
    RateDecision,
)

UF_FLOOR = Decimal(50)
UF_THRESHOLD = Decimal(200)
_PCT = Decimal(100)
_CLP_STEP = Decimal(1)
_UF_STEP = Decimal("0.0001")


def _round(value: Decimal, step: Decimal) -> Decimal:
    return value.quantize(step, ROUND_HALF_UP)


def select_category(currency: Currency, amount_in_uf: Decimal) -> RateCategory:
    if currency is Currency.UF:
        return RateCategory.UF
    if amount_in_uf <= UF_FLOOR:
        return RateCategory.CLP_UNDER_50
    if amount_in_uf < UF_THRESHOLD:
        return RateCategory.CLP_50_TO_200
    return RateCategory.CLP_OVER_200


def apply_tmc_cap(rate: Decimal, tmc_ceiling: Decimal) -> tuple[Decimal, bool]:
    """Return (rate bounded by the TMC, whether the cap was applied)."""
    if rate > tmc_ceiling:
        return tmc_ceiling, True
    return rate, False


def get_applicable_rate(
    on: date,
    currency: Currency,
    amount_in_uf: Decimal,
    agreed_rate: Decimal | None,
    table: RateTable | None = None,
) -> RateDecision:
    table = table or load_default_table()
    category = select_category(currency, amount_in_uf)
    corriente, tmc = table.rate(on, category)
    if agreed_rate is None:
        return RateDecision(
            category=category, annual_rate=corriente, corriente=corriente,
            tmc=tmc, source="corriente", capped=False,
        )
    rate, capped = apply_tmc_cap(agreed_rate, tmc)
    warning = (
        f"{on:%Y-%m}: tasa pactada {agreed_rate}% excede la TMC {tmc}%; "
        f"se aplicó la TMC (art. 6 Ley 18.010)"
        if capped else None
    )
    return RateDecision(
        category=category, annual_rate=rate, corriente=corriente, tmc=tmc,
        source="agreed", capped=capped, warning=warning,
    )


def _daterange(start_exclusive: date, end_inclusive: date):
    d = start_exclusive + timedelta(days=1)
    while d <= end_inclusive:
        yield d
        d += timedelta(days=1)


def calculate_day_by_day_ledger(
    params: LiquidationParams, table: RateTable | None = None
) -> LiquidationLedger:
    table = table or load_default_table()
    is_uf = params.currency is Currency.UF
    step = _UF_STEP if is_uf else _CLP_STEP

    uf_issue = table.uf_value(params.issue_date)
    amount_in_uf = params.principal if is_uf else params.principal / uf_issue
    category = select_category(params.currency, amount_in_uf)

    uf_maturity = table.uf_value(params.maturity_date) if is_uf else None
    warnings: list[str] = [f"Base de cálculo {params.day_count.value}: convención por confirmar."]
    seen_warnings: set[str] = set()
    if not table.verified:
        warnings.append(
            f"Tablas de tasas NO verificadas ({table.source}); no usar en juicio."
        )

    payments_by_day: dict[date, Decimal] = {}
    for pay in params.payments:
        payments_by_day[pay.date] = payments_by_day.get(pay.date, Decimal(0)) + pay.amount

    days: list[LedgerDay] = []
    capital = params.principal
    accrued = Decimal(0)  # total interest generated (exact)
    interest_due = Decimal(0)  # generated and not yet paid (exact)
    paid_total = Decimal(0)
    for d in _daterange(params.issue_date, params.cutoff_date):
        phase = Phase.CONVENTIONAL if d <= params.maturity_date else Phase.MORATORY
        if phase is Phase.CONVENTIONAL and params.agreed_rate is None:
            rate_pct = Decimal(0)
        else:
            decision = get_applicable_rate(
                d, params.currency, amount_in_uf, params.agreed_rate, table
            )
            rate_pct = decision.annual_rate
            if decision.warning and decision.warning not in seen_warnings:
                seen_warnings.add(decision.warning)
                warnings.append(decision.warning)
        daily = capital * rate_pct / _PCT / params.day_count.basis
        accrued += daily
        interest_due += daily
        uf_d = table.uf_value(d) if is_uf else None
        capital_today = capital
        paid_today = payments_by_day.get(d, Decimal(0))
        if paid_today:
            # Imputation: accrued interest first (rounded to the unit), then capital.
            to_interest = min(paid_today, _round(interest_due, step))
            interest_due = max(interest_due - to_interest, Decimal(0))
            capital -= paid_today - to_interest
            if capital < 0:
                raise ValueError(f"El abono del {d} excede la deuda exigible")
            paid_total += paid_today
        days.append(
            LedgerDay(
                date=d, phase=phase, annual_rate=rate_pct, uf_value=uf_d,
                readjustment_factor=(uf_d / uf_maturity)
                if uf_d is not None and uf_maturity is not None else None,
                capital=capital_today,
                capital_clp=_round(capital_today * uf_d, Decimal(1))
                if uf_d is not None else capital_today,
                payment=paid_today, capital_end=capital, interest_due=interest_due,
                daily_interest=daily, accrued_interest=accrued,
            )
        )

    # Monthly rows: interest generated uses cumulative rounding so months add up.
    months: list[LedgerMonth] = []
    prev_rounded = Decimal(0)
    i = 0
    while i < len(days):
        key = (days[i].date.year, days[i].date.month)
        j = i
        while j + 1 < len(days) and (days[j + 1].date.year, days[j + 1].date.month) == key:
            j += 1
        last = days[j]
        month_paid = sum((x.payment for x in days[i:j + 1]), Decimal(0))
        cum_rounded = _round(last.accrued_interest, step)
        uf_end = last.uf_value
        total_native = last.capital_end + _round(last.interest_due, step)
        months.append(
            LedgerMonth(
                period=f"{key[0]}-{key[1]:02d}", days=j - i + 1,
                annual_rate=last.annual_rate, capital=last.capital_end,
                interest=cum_rounded - prev_rounded, payments=month_paid,
                accrued_interest=cum_rounded, uf_value_end=uf_end,
                accumulated_total_clp=_round(total_native * uf_end, Decimal(1))
                if uf_end is not None else total_native,
            )
        )
        prev_rounded = cum_rounded
        i = j + 1

    interest_accrued = _round(accrued, step)
    interest_out = _round(interest_due, step)
    if is_uf:
        uf_cut = table.uf_value(params.cutoff_date)
        principal_clp = _round(capital * uf_cut, Decimal(1))
        interest_clp = _round(interest_out * uf_cut, Decimal(1))
    else:
        principal_clp, interest_clp = capital, interest_out
    total_clp = principal_clp + interest_clp  # ledger rows must add up

    return LiquidationLedger(
        params=params, category=category, days=days, months=months,
        principal_clp=principal_clp, interest_native=interest_out,
        interest_clp=interest_clp, total_clp=total_clp, capital_native=capital,
        interest_accrued_native=interest_accrued, payments_total=paid_total,
        day_count=params.day_count, rate_table_verified=table.verified, warnings=warnings,
    )
