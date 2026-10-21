"""Turn an uploaded file into text for extraction. Everything stays in memory
(zero data retention); scanned pages go to a vision model for OCR."""
from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
from pathlib import Path

from pypdf import PdfReader

from app.services.extractor import VisionClient

MAX_PAGES = 12
MIN_TEXT_CHARS = 40  # below this a PDF is treated as scanned


class UnsupportedFileError(ValueError):
    """Unknown or disallowed file type (HTTP 415)."""


class OcrUnavailableError(RuntimeError):
    """Scanned content but no way to OCR it (HTTP 422)."""


def sniff(data: bytes) -> str:
    if data[:4] == b"%PDF":
        return "pdf"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    try:
        data[:4096].decode("utf-8")
        return "text"
    except UnicodeDecodeError as exc:
        raise UnsupportedFileError("Formato no soportado: use PDF, PNG, JPG, WEBP o texto") from exc


def _pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in reader.pages[:MAX_PAGES]).strip()


def _render_pdf_pages(data: bytes) -> list[bytes]:
    exe = shutil.which("pdftoppm")
    if exe is None:
        raise OcrUnavailableError(
            "PDF escaneado: el servidor no tiene poppler (pdftoppm). Suba imágenes de las páginas.")
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "in.pdf").write_bytes(data)
        subprocess.run([exe, "-r", "150", "-l", str(MAX_PAGES), "-png", str(Path(tmp) / "in.pdf"),
                        str(Path(tmp) / "pg")], check=True, capture_output=True, timeout=120)
        return [p.read_bytes() for p in sorted(Path(tmp).glob("pg*.png"))]


def text_from_upload(data: bytes, vision: VisionClient) -> str:
    kind = sniff(data)
    if kind == "text":
        return data.decode("utf-8", errors="replace")
    if kind == "pdf":
        text = _pdf_text(data)
        if len(text) >= MIN_TEXT_CHARS:
            return text
        return "\n\n".join(vision.transcribe(img, "image/png") for img in _render_pdf_pages(data))
    return vision.transcribe(data, kind)
