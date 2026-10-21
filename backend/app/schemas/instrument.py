"""Pydantic v2 schemas for credit instruments (Pagaré Ley 18.092, Factura Ley 19.983)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.liquidation import Currency


def normalize_rut(raw: str) -> str:
    """Validate a Chilean RUT (módulo 11) and return it as 12.345.678-K."""
    cleaned = raw.replace(".", "").replace("-", "").replace(" ", "").upper()
    body, dv = cleaned[:-1], cleaned[-1:]
    if not body.isdigit() or not dv or not (dv.isdigit() or dv == "K"):
        raise ValueError("RUT mal formado")
    total, factor = 0, 2
    for ch in reversed(body):
        total += int(ch) * factor
        factor = 2 if factor == 7 else factor + 1
    rem = 11 - total % 11
    expected = "0" if rem == 11 else "K" if rem == 10 else str(rem)
    if dv != expected:
        raise ValueError("Dígito verificador inválido en RUT")
    return f"{int(body):,}".replace(",", ".") + f"-{dv}"


class Party(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2)
    rut: str
    address: str | None = None
    commune: str | None = None

    @field_validator("rut")
    @classmethod
    def _rut(cls, v: str) -> str:
        return normalize_rut(v)


class LegalRepresentative(Party):
    capacity: str = Field(min_length=2, description="e.g. 'gerente general', 'apoderado'")


class CourtJurisdiction(BaseModel):
    court_name: str = Field(min_length=2, description="e.g. '12° Juzgado Civil de Santiago'")
    city: str = Field(min_length=2)


class _InstrumentBase(BaseModel):
    creditor: Party
    debtor: Party
    creditor_representatives: list[LegalRepresentative] = Field(default_factory=list)
    debtor_representatives: list[LegalRepresentative] = Field(default_factory=list)
    jurisdiction: CourtJurisdiction | None = None


class Pagare(_InstrumentBase):
    kind: Literal["pagare"] = "pagare"
    amount: Decimal = Field(gt=0)
    currency: Currency
    issue_date: date
    maturity_date: date
    agreed_rate_annual: Decimal | None = Field(default=None, ge=0, description="percent per year")
    guarantors: list[Party] = Field(default_factory=list, description="avales / codeudores")
    signature_authorized: bool | None = Field(
        default=None, description="Firma autorizada ante notario (art. 434 N° 4 CPC)"
    )

    @model_validator(mode="after")
    def _dates(self) -> Pagare:
        if self.maturity_date < self.issue_date:
            raise ValueError("maturity_date anterior a issue_date")
        return self


class FacturaElectronica(_InstrumentBase):
    kind: Literal["factura"] = "factura"
    folio: str = Field(min_length=1)
    net_amount: Decimal = Field(ge=0)
    vat_amount: Decimal = Field(ge=0)
    total_amount: Decimal = Field(gt=0)
    currency: Literal[Currency.CLP] = Currency.CLP
    issue_date: date
    due_date: date | None = None
    receipt_acknowledged: bool | None = Field(
        default=None, description="Acuse de recibo de mercaderías/servicios (Ley 19.983)"
    )

    @model_validator(mode="after")
    def _totals(self) -> FacturaElectronica:
        if self.net_amount + self.vat_amount != self.total_amount:
            raise ValueError("net_amount + vat_amount no coincide con total_amount")
        return self


Instrument = Annotated[Pagare | FacturaElectronica, Field(discriminator="kind")]


class ExtractionResult(BaseModel):
    instrument: Instrument
    missing_fields: list[str] = Field(default_factory=list)


class Attorney(BaseModel):
    """Abogado patrocinante y apoderado (Ley 18.120)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2)
    rut: str
    address: str = Field(min_length=2)
    email: str | None = None
    bar_details: str | None = Field(default=None, description="Colegio/registro profesional")

    @field_validator("rut")
    @classmethod
    def _rut(cls, v: str) -> str:
        return normalize_rut(v)
