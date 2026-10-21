"""Real-provider smoke test. Skipped unless LLM_API_KEY (and, for openai_compatible,
LLM_BASE_URL / LLM_MODEL) are set:  pytest -m live"""
import os

import pytest

from app.core.config import get_settings
from app.schemas.instrument import Pagare
from app.services.extractor import build_client, extract_instrument

TEXT = """PAGARÉ. Santiago, 15 de enero de 2024. Don JUAN PÉREZ GONZÁLEZ, RUT 15.678.901-1,
domiciliado en Avenida Providencia 1234, Providencia, promete pagar a INVERSIONES NORTE SPA,
RUT 76.543.210-3, domiciliada en calle El Golf 40, Las Condes, la suma de $5.000.000 (pesos chilenos)
el 15 de febrero de 2024. Competencia: Tribunales de Santiago."""

pytestmark = [pytest.mark.live,
              pytest.mark.skipif(not os.environ.get("LLM_API_KEY"), reason="LLM_API_KEY not set")]


def test_live_extraction_roundtrip():
    p = extract_instrument(TEXT, build_client(get_settings())).instrument
    assert isinstance(p, Pagare)
    assert str(p.amount) == "5000000" and str(p.maturity_date) == "2024-02-15"
