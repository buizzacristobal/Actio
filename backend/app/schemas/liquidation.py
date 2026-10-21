"""Typed schemas for liquidation inputs and the itemized ledger output."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Currency(str, Enum):
    CLP = "CLP"
    UF = "UF"


class RateCategory(str, Enum):
    CLP_UNDER_50 = "non_reajustable_clp_under_50_uf"  # <= 50 UF
    CLP_50_TO_200 = "non_reajustable_clp_50_to_200_uf"  # > 50 and < 200 UF
    CLP_OVER_200 = "non_reajustable_clp_over_200_uf"  # >= 200 UF
    UF = "reajustable_uf_all"


class DayCount(str, Enum):
    """Day-count convention. Which one courts apply is UNVERIFIED; it is recorded
    on every ledger so the attorney can confirm it."""

    ACT_360 = "ACT/360"
    ACT_365 = "ACT/365"

    @property
    def basis(self) -> Decimal:
        return Decimal(360 if self is DayCount.ACT_360 else 365)


class Phase(str, Enum):
    CONVENTIONAL = "conventional"  # issue date -> maturity, agreed interest only
    MORATORY = "moratory"  # day after maturity -> cut-off


class Payment(BaseModel):
    """Abono, in the same currency as the principal (CLP or UF). Imputed first to
    accrued interest, then to capital (Código Civil art. 1595)."""

    model_config = ConfigDict(frozen=True)

    date: date
    amount: Decimal = Field(gt=0)


class LiquidationParams(BaseModel):
    model_config = ConfigDict(frozen=True)

    principal: Decimal = Field(gt=0, description="Capital in `currency` units")
    currency: Currency
    issue_date: date
    maturity_date: date
    cutoff_date: date
    agreed_rate: Decimal | None = Field(
        default=None, ge=0, description="Annual agreed interest, in percent"
    )
    day_count: DayCount = DayCount.ACT_360
    payments: tuple[Payment, ...] = ()

    @model_validator(mode="after")
    def _check_dates(self) -> LiquidationParams:
        if self.maturity_date < self.issue_date:
            raise ValueError("maturity_date cannot precede issue_date")
        if self.cutoff_date < self.maturity_date:
            raise ValueError("cutoff_date cannot precede maturity_date")
        for p in self.payments:
            if not self.issue_date < p.date <= self.cutoff_date:
                raise ValueError("payment date must fall after issue_date and not after cutoff_date")
        return self


class RateDecision(BaseModel):
    """Rate selected for one date, with the legal ceiling that applied."""

    model_config = ConfigDict(frozen=True)

    category: RateCategory
    annual_rate: Decimal
    corriente: Decimal
    tmc: Decimal
    source: str  # "agreed" | "corriente"
    capped: bool
    warning: str | None = None


class LedgerDay(BaseModel):
    date: date
    phase: Phase
    annual_rate: Decimal
    uf_value: Decimal | None
    readjustment_factor: Decimal | None
    capital: Decimal  # capital accruing interest that day, native units (CLP or UF)
    capital_clp: Decimal
    payment: Decimal = Decimal(0)  # abono applied at the end of the day, native units
    capital_end: Decimal = Decimal(0)  # capital after the day's abono
    interest_due: Decimal = Decimal(0)  # generated and unpaid after the day's abono
    daily_interest: Decimal  # native units, unrounded (Decimal precision)
    accrued_interest: Decimal  # native units, unrounded


class LedgerMonth(BaseModel):
    period: str  # YYYY-MM
    days: int
    annual_rate: Decimal  # rate of the last day of the month
    capital: Decimal
    interest: Decimal  # interest generated in the month, native, rounded; months sum to the total generated
    payments: Decimal = Decimal(0)
    accrued_interest: Decimal  # rounded cumulative, native units
    uf_value_end: Decimal | None
    accumulated_total_clp: Decimal


class LiquidationLedger(BaseModel):
    params: LiquidationParams
    category: RateCategory
    days: list[LedgerDay]
    months: list[LedgerMonth]
    principal_clp: Decimal  # capital outstanding at cut-off
    interest_native: Decimal  # interest outstanding (generated - paid): CLP 0 dp, UF 4 dp
    interest_clp: Decimal
    total_clp: Decimal
    capital_native: Decimal = Decimal(0)  # capital outstanding, native units
    interest_accrued_native: Decimal = Decimal(0)  # total interest generated
    payments_total: Decimal = Decimal(0)
    day_count: DayCount
    rate_table_verified: bool
    warnings: list[str] = Field(default_factory=list)
