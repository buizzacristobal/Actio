from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.schemas.instrument import ExtractionResult
from app.services.documents import OcrUnavailableError, UnsupportedFileError, text_from_upload
from app.services.extractor import LLMClient, build_client, extract_instrument

router = APIRouter()


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200_000, description="Texto / salida OCR")


def get_llm_client(settings: Settings = Depends(get_settings)) -> LLMClient:
    return build_client(settings)


@router.post("/extract", response_model=ExtractionResult)
def extract(req: ExtractRequest, client: LLMClient = Depends(get_llm_client)) -> ExtractionResult:
    return extract_instrument(req.text, client)


MAX_UPLOAD = 10 * 1024 * 1024


@router.post("/extract-file", response_model=ExtractionResult)
async def extract_file(file: UploadFile, client: LLMClient = Depends(get_llm_client)) -> ExtractionResult:
    """PDF (text or scanned), PNG/JPG/WEBP image, or plain text. Nothing is stored."""
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="Archivo demasiado grande (máx. 10 MB)")
    try:
        text = text_from_upload(data, client)  # type: ignore[arg-type]
    except UnsupportedFileError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except OcrUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not text.strip():
        raise HTTPException(status_code=422, detail="No se pudo leer texto del archivo")
    return extract_instrument(text, client)
