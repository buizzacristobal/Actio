"""LLM entity extraction -> validated instrument schemas.

The LLM only transcribes fields (JSON). It never does arithmetic: totals and RUT
check digits are validated by deterministic Python in the schemas.
Zero data retention: nothing is persisted or logged; error messages carry only field
paths and rule messages, never document text or input values.
"""
from __future__ import annotations

import base64
import json
from typing import Any, Protocol

from pydantic import TypeAdapter, ValidationError

from app.core.config import Settings
from app.schemas.instrument import ExtractionResult, Instrument, Pagare

DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_ATTEMPTS = 2

SYSTEM_PROMPT = """Eres un extractor de datos de títulos de crédito chilenos.
Devuelve SOLO un objeto JSON, sin texto adicional ni markdown.
Reglas: transcribe literalmente; NO calcules ni infieras montos; si un dato no
aparece, omite el campo. Fechas en ISO (YYYY-MM-DD). Montos como cadenas decimales
sin separador de miles. RUT tal como figura en el documento.
Campo "kind": "pagare" o "factura".
Pagaré: creditor, debtor, amount, currency (CLP|UF), issue_date, maturity_date,
agreed_rate_annual (porcentaje anual), guarantors, signature_authorized,
creditor_representatives, debtor_representatives, jurisdiction{court_name,city}.
Factura: creditor (emisor), debtor (receptor), folio, net_amount, vat_amount,
total_amount, issue_date, due_date, receipt_acknowledged, jurisdiction.
Party = {name, rut, address, commune}. Representante añade capacity."""


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str: ...


class ExtractionError(RuntimeError):
    """The model output could not be turned into a valid instrument."""


class AnthropicClient:
    """Thin adapter over the Anthropic SDK (imported lazily)."""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def transcribe(self, image: bytes, mime: str) -> str:
        content: list[Any] = [
            {"type": "image", "source": {"type": "base64", "media_type": mime,
                                         "data": base64.b64encode(image).decode()}},
            {"type": "text", "text": OCR_PROMPT},
        ]
        msg = self._client.messages.create(
            model=self._model, max_tokens=4096, messages=[{"role": "user", "content": content}])
        return "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text")

    def complete(self, system: str, user: str) -> str:
        msg = self._client.messages.create(
            model=self._model, max_tokens=4096,
            system=system, messages=[{"role": "user", "content": user}],
        )
        return "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text")


OCR_PROMPT = ("Transcribe literalmente todo el texto visible del documento, en el mismo orden. "
              "No resumas, no corrijas, no interpretes ni agregues nada.")


class VisionClient(Protocol):
    def transcribe(self, image: bytes, mime: str) -> str: ...


class OpenAICompatibleClient:
    """Any OpenAI-compatible endpoint (OpenRouter, Qwen, vLLM, ...) in JSON mode."""

    def __init__(self, model: str, api_key: str | None = None, base_url: str | None = None,
                 client: object | None = None, vision_model: str | None = None) -> None:
        if client is None:
            import openai

            client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self._client = client
        self._model = model
        self._vision_model = vision_model

    def transcribe(self, image: bytes, mime: str) -> str:
        if not self._vision_model:
            raise RuntimeError("OCR no configurado: defina LLM_VISION_MODEL con un modelo con visión")
        url = f"data:{mime};base64,{base64.b64encode(image).decode()}"
        resp = self._client.chat.completions.create(  # type: ignore[attr-defined]
            model=self._vision_model, temperature=0,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": OCR_PROMPT},
                {"type": "image_url", "image_url": {"url": url}}]}],
        )
        return resp.choices[0].message.content or ""

    def complete(self, system: str, user: str) -> str:
        schema = json.dumps(TypeAdapter(Instrument).json_schema(), ensure_ascii=False)
        resp = self._client.chat.completions.create(  # type: ignore[attr-defined]
            model=self._model, temperature=0, response_format={"type": "json_object"},
            messages=[
                {"role": "system",
                 "content": f"{system}\nEl JSON debe cumplir este JSON Schema:\n{schema}"},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""


def build_client(settings: Settings) -> LLMClient:
    if settings.llm_provider == "anthropic":
        return AnthropicClient(model=settings.llm_model, api_key=settings.llm_api_key)
    if settings.llm_provider == "openai_compatible":
        if not settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY no configurado para openai_compatible")
        return OpenAICompatibleClient(
            model=settings.llm_model, api_key=settings.llm_api_key, base_url=settings.llm_base_url,
            vision_model=settings.llm_vision_model)
    raise RuntimeError(f"LLM_PROVIDER desconocido: {settings.llm_provider}")


def _first_json_object(text: str) -> dict:
    start = text.find("{")
    if start < 0:
        raise ValueError("la respuesta no contiene un objeto JSON")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(obj, dict):
        raise ValueError("la respuesta JSON no es un objeto")
    return obj


def find_missing(i: Instrument) -> list[str]:
    """Optional fields that matter for the lawsuit but were not found in the document."""
    missing: list[str] = []
    if i.jurisdiction is None:
        missing.append("jurisdiction")
    for who, party in (("creditor", i.creditor), ("debtor", i.debtor)):
        if not party.address:
            missing.append(f"{who}.address")
    if isinstance(i, Pagare):
        if i.agreed_rate_annual is None:
            missing.append("agreed_rate_annual")
        if i.signature_authorized is None:
            missing.append("signature_authorized")
    else:
        if i.due_date is None:
            missing.append("due_date")
        if i.receipt_acknowledged is None:
            missing.append("receipt_acknowledged")
    return missing


def _safe_error(exc: Exception) -> str:
    """Field paths and rule messages only: never echo input values (zero data retention)."""
    if isinstance(exc, ValidationError):
        return "; ".join(f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors())[:800]
    return str(exc)[:200]


def extract_instrument(document_text: str, client: LLMClient) -> ExtractionResult:
    """Extract and validate an instrument from raw text / OCR output."""
    if not document_text.strip():
        raise ExtractionError("documento vacío")
    adapter: TypeAdapter[Any] = TypeAdapter(Instrument)
    user = f"Documento:\n\"\"\"\n{document_text}\n\"\"\""
    last_error = ""
    for _ in range(MAX_ATTEMPTS):
        prompt = user if not last_error else (
            f"{user}\n\nTu respuesta anterior fue inválida: {last_error}\nCorrígela."
        )
        raw = client.complete(SYSTEM_PROMPT, prompt)
        try:
            instrument = adapter.validate_python(_first_json_object(raw))
            return ExtractionResult(instrument=instrument, missing_fields=find_missing(instrument))
        except (ValueError, ValidationError) as exc:
            last_error = _safe_error(exc)
    raise ExtractionError(f"extracción inválida tras {MAX_ATTEMPTS} intentos: {last_error}")
