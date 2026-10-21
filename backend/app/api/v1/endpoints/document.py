from __future__ import annotations

from datetime import date

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel

from app.engine.calculator import calculate_day_by_day_ledger
from app.schemas.instrument import Attorney, FacturaElectronica, Instrument, Pagare
from app.schemas.liquidation import Currency, DayCount, LiquidationParams, Payment
from app.services.generator import generate_lawsuit_docx

router = APIRouter()
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class LawsuitRequest(BaseModel):
    instrument: Instrument
    attorney: Attorney
    cutoff_date: date
    day_count: DayCount = DayCount.ACT_360
    payments: tuple[Payment, ...] = ()


def params_from_instrument(
    instr: Instrument, cutoff: date, day_count: DayCount, payments: tuple[Payment, ...] = ()
) -> LiquidationParams:
    if isinstance(instr, Pagare):
        return LiquidationParams(
            principal=instr.amount, currency=instr.currency, issue_date=instr.issue_date,
            maturity_date=instr.maturity_date, cutoff_date=cutoff,
            agreed_rate=instr.agreed_rate_annual, day_count=day_count, payments=payments)
    assert isinstance(instr, FacturaElectronica)
    if instr.due_date is None:
        raise ValueError("La factura requiere due_date (fecha de vencimiento)")
    return LiquidationParams(
        principal=instr.total_amount, currency=Currency.CLP, issue_date=instr.issue_date,
        maturity_date=instr.due_date, cutoff_date=cutoff, day_count=day_count, payments=payments)


@router.post("/generate-lawsuit", response_class=Response)
def generate_lawsuit(req: LawsuitRequest) -> Response:
    """The ledger is recomputed server-side so the document never carries client numbers."""
    ledger = calculate_day_by_day_ledger(
        params_from_instrument(req.instrument, req.cutoff_date, req.day_count, req.payments))
    data = generate_lawsuit_docx(req.instrument, ledger, req.attorney)
    return Response(content=data, media_type=DOCX, headers={
        "Content-Disposition": 'attachment; filename="demanda_ejecutiva.docx"'})
