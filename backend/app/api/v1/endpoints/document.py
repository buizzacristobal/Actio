from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.engine.calculator import calculate_day_by_day_ledger
from app.engine.legal_templates import Block, build_lawsuit, drafting_notes
from app.schemas.instrument import Attorney, FacturaElectronica, Instrument, Pagare
from app.schemas.liquidation import Currency, DayCount, LiquidationParams, Payment
from app.services.generator import docx_to_pdf, generate_lawsuit_docx

router = APIRouter()
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class BlockIn(BaseModel):
    kind: Literal["banner", "suma", "heading", "paragraph", "pagebreak"]
    text: str = Field(default="", max_length=20_000)


class LawsuitRequest(BaseModel):
    instrument: Instrument
    attorney: Attorney
    cutoff_date: date
    day_count: DayCount = DayCount.ACT_360
    payments: tuple[Payment, ...] = ()
    assets: list[str] = Field(default_factory=list, max_length=50)
    edited_blocks: list[BlockIn] | None = Field(default=None, max_length=300)
    format: Literal["docx", "pdf"] = "docx"


class PreviewResponse(BaseModel):
    blocks: list[BlockIn]
    notes: list[str]
    total_clp: str
    warnings: list[str]


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


def _ledger(req: LawsuitRequest):
    return calculate_day_by_day_ledger(
        params_from_instrument(req.instrument, req.cutoff_date, req.day_count, req.payments))


@router.post("/preview-lawsuit", response_model=PreviewResponse)
def preview_lawsuit(req: LawsuitRequest) -> PreviewResponse:
    ledger = _ledger(req)
    blocks = build_lawsuit(req.instrument, ledger, req.attorney, req.assets)
    return PreviewResponse(
        blocks=[BlockIn(kind=b.kind, text=b.text) for b in blocks],
        notes=drafting_notes(req.instrument, ledger, req.assets),
        total_clp=str(ledger.total_clp), warnings=ledger.warnings)


@router.post("/generate-lawsuit", response_class=Response)
def generate_lawsuit(req: LawsuitRequest) -> Response:
    """The ledger is recomputed server-side so the document never carries client numbers.
    Only the narrative text may be edited by the attorney (`edited_blocks`)."""
    ledger = _ledger(req)
    blocks = ([Block(b.kind, b.text) for b in req.edited_blocks]
              if req.edited_blocks is not None else None)
    data = generate_lawsuit_docx(req.instrument, ledger, req.attorney,
                                 assets=req.assets, blocks=blocks)
    if req.format == "pdf":
        data = docx_to_pdf(data)
        return Response(content=data, media_type="application/pdf", headers={
            "Content-Disposition": 'attachment; filename="demanda_ejecutiva.pdf"'})
    return Response(content=data, media_type=DOCX, headers={
        "Content-Disposition": 'attachment; filename="demanda_ejecutiva.docx"'})
