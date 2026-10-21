import json

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints.extraction import get_llm_client
from app.main import create_app
from app.services.documents import OcrUnavailableError, UnsupportedFileError, sniff, text_from_upload
from app.services.extractor import OpenAICompatibleClient, find_missing
from tests.test_extraction import PAGARE, FakeOpenAI

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def minimal_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offs)
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref)


class Vision:
    def __init__(self, text="TEXTO OCR"):
        self.text, self.calls = text, []

    def transcribe(self, image, mime):
        self.calls.append(mime)
        return self.text


def test_sniff():
    assert sniff(b"%PDF-1.7") == "pdf" and sniff(PNG) == "image/png"
    assert sniff(b"\xff\xd8\xff\xe0abc") == "image/jpeg" and sniff("hola ñ".encode()) == "text"
    with pytest.raises(UnsupportedFileError):
        sniff(b"\x00\xff\xfe\x80\x81binary")


def test_text_pdf_needs_no_ocr():
    v = Vision()
    txt = text_from_upload(minimal_pdf("PAGARE por la suma de un millon de pesos, deudor Juan Perez"), v)
    assert "PAGARE" in txt and v.calls == []


def test_image_goes_to_vision_and_scanned_pdf_without_poppler(monkeypatch):
    v = Vision("PAGARE ESCANEADO")
    assert text_from_upload(PNG, v) == "PAGARE ESCANEADO" and v.calls == ["image/png"]
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(OcrUnavailableError):
        text_from_upload(minimal_pdf("x"), v)  # almost no text -> treated as scanned


def test_openai_vision_requires_model_and_sends_data_uri():
    with pytest.raises(RuntimeError, match="no configurado"):
        OpenAICompatibleClient("m", client=FakeOpenAI("x")).transcribe(PNG, "image/png")
    fake = FakeOpenAI("TRANSCRITO")
    out = OpenAICompatibleClient("m", client=fake, vision_model="vl").transcribe(PNG, "image/png")
    call = fake.calls[0]
    assert out == "TRANSCRITO" and call["model"] == "vl"
    assert call["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")


class Both:
    """Fake LLM client with text completion and OCR."""

    def complete(self, system, user):
        assert "TEXTO OCR" in user or "PAGARE" in user
        return json.dumps(PAGARE)

    def transcribe(self, image, mime):
        return "TEXTO OCR del pagare"


def test_extract_file_endpoint():
    app = create_app()
    app.dependency_overrides[get_llm_client] = lambda: Both()
    c = TestClient(app, raise_server_exceptions=False)
    r = c.post("/api/v1/extract-file", files={"file": ("p.png", PNG, "image/png")})
    assert r.status_code == 200 and r.json()["instrument"]["kind"] == "pagare"
    assert "jurisdiction" in r.json()["missing_fields"] or "debtor.address" in r.json()["missing_fields"]
    junk = {"file": ("x.bin", b"\x00\xff\xfe\x80\x81", "application/octet-stream")}
    r = c.post("/api/v1/extract-file", files=junk)
    assert r.status_code == 415


def test_missing_fields():
    from app.schemas.instrument import Pagare
    p = Pagare(**PAGARE)
    m = find_missing(p)
    assert {"jurisdiction", "signature_authorized", "debtor.address"} <= set(m)
    assert "agreed_rate_annual" not in m  # present in the fixture
