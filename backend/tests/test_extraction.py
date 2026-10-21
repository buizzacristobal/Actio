import json
from datetime import date
from decimal import Decimal as D

import pytest
from pydantic import ValidationError

from app.schemas.instrument import FacturaElectronica, Pagare, normalize_rut
from app.services.extractor import ExtractionError, extract_instrument


class FakeClient:
    def __init__(self, *replies: str) -> None:
        self.replies, self.calls = list(replies), []

    def complete(self, system: str, user: str) -> str:
        self.calls.append(user)
        return self.replies.pop(0)


PAGARE = {
    "kind": "pagare", "amount": "1000000", "currency": "CLP",
    "issue_date": "2024-01-01", "maturity_date": "2024-06-30", "agreed_rate_annual": "24",
    "creditor": {"name": "Banco Ejemplo SpA", "rut": "76.086.428-5"},
    "debtor": {"name": "Juan Pérez", "rut": "12.345.678-5"},
}


def test_rut_validation():
    assert normalize_rut("12345678-5") == "12.345.678-5"
    assert normalize_rut("76086428-5") == "76.086.428-5"
    assert normalize_rut("11.111.111-1") == "11.111.111-1"
    for bad in ("12.345.678-9", "abc", "1-"):
        with pytest.raises(ValueError):
            normalize_rut(bad)


def test_extract_pagare_from_fenced_json():
    client = FakeClient("Aquí está:\n```json\n" + json.dumps(PAGARE) + "\n```")
    res = extract_instrument("PAGARE ...", client)
    p = res.instrument
    assert isinstance(p, Pagare) and p.amount == D(1_000_000)
    assert p.maturity_date == date(2024, 6, 30) and p.debtor.rut == "12.345.678-5"


def test_retry_on_invalid_then_success():
    bad = dict(PAGARE, maturity_date="2023-01-01")
    client = FakeClient(json.dumps(bad), json.dumps(PAGARE))
    assert isinstance(extract_instrument("doc", client).instrument, Pagare)
    assert "inválida" in client.calls[1]


def test_gives_up_after_max_attempts():
    with pytest.raises(ExtractionError):
        extract_instrument("doc", FakeClient("no json", "{ nope"))
    with pytest.raises(ExtractionError):
        extract_instrument("   ", FakeClient())


def test_factura_total_checked_deterministically():
    base = {
        "kind": "factura", "folio": "1234", "net_amount": "100000", "vat_amount": "19000",
        "total_amount": "119000", "issue_date": "2024-02-01",
        "creditor": PAGARE["creditor"], "debtor": PAGARE["debtor"],
    }
    assert isinstance(extract_instrument("f", FakeClient(json.dumps(base))).instrument,
                      FacturaElectronica)
    with pytest.raises(ValidationError):
        FacturaElectronica(**{**base, "total_amount": "120000"})


# --- openai_compatible provider (mock client, fully offline) ---
from types import SimpleNamespace

from app.core.config import Settings
from app.services.extractor import (
    AnthropicClient,
    OpenAICompatibleClient,
    build_client,
)


class FakeOpenAI:
    def __init__(self, *contents: str) -> None:
        self.contents, self.calls = list(contents), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        msg = SimpleNamespace(content=self.contents.pop(0))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_openai_compatible_parses_json_mode():
    fake = FakeOpenAI(json.dumps(PAGARE))
    client = OpenAICompatibleClient("qwen/qwen-2.5-72b-instruct", client=fake)
    p = extract_instrument("doc", client).instrument
    assert isinstance(p, Pagare) and p.amount == D(1_000_000)
    call = fake.calls[0]
    assert call["response_format"] == {"type": "json_object"} and call["temperature"] == 0
    assert call["model"] == "qwen/qwen-2.5-72b-instruct"
    assert "JSON Schema" in call["messages"][0]["content"]


def test_openai_compatible_retries_on_schema_error():
    bad = dict(PAGARE, maturity_date="2023-01-01")
    fake = FakeOpenAI(json.dumps(bad), json.dumps(PAGARE))
    res = extract_instrument("doc", OpenAICompatibleClient("m", client=fake))
    assert isinstance(res.instrument, Pagare) and len(fake.calls) == 2
    assert "inválida" in fake.calls[1]["messages"][1]["content"]


def test_errors_never_leak_document_or_values():
    bad = dict(PAGARE, debtor={"name": "Juan", "rut": "12.345.678-9"})
    fake = FakeOpenAI(json.dumps(bad), json.dumps(bad))
    with pytest.raises(ExtractionError) as ei:
        extract_instrument("TEXTO-CONFIDENCIAL 12.345.678-9", OpenAICompatibleClient("m", client=fake))
    msg = str(ei.value)
    assert "CONFIDENCIAL" not in msg and "12.345.678-9" not in msg
    assert "CONFIDENCIAL" not in fake.calls[1]["messages"][1]["content"].split("Tu respuesta")[1]


def test_build_client_selects_provider():
    oa = build_client(Settings(llm_provider="openai_compatible", llm_api_key="k",
                               llm_base_url="https://openrouter.ai/api/v1", llm_model="m"))
    assert isinstance(oa, OpenAICompatibleClient)
    assert isinstance(build_client(Settings(llm_provider="anthropic", llm_api_key="k")), AnthropicClient)
    with pytest.raises(RuntimeError):
        build_client(Settings(llm_provider="openai_compatible", llm_api_key=None))
