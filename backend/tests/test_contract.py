"""Frontend/backend contract: the sample instruments the UI ships must validate against the
backend schemas, and the API must accept the exact payload shapes the UI sends."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from app.main import create_app
from app.schemas.instrument import Instrument

SAMPLES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "samples.json"
ATT = {"name": "María Soto", "rut": "11.111.111-1", "address": "Huérfanos 1117"}


@pytest.fixture(scope="module")
def samples():
    return json.loads(SAMPLES.read_text(encoding="utf-8"))


@pytest.mark.parametrize("kind", ["pagare", "factura"])
def test_frontend_samples_validate(samples, kind):
    assert TypeAdapter(Instrument).validate_python(samples[kind]).kind == kind


@pytest.mark.parametrize("kind", ["pagare", "factura"])
def test_ui_payloads_accepted(samples, kind):
    c = TestClient(create_app())
    body = {"instrument": samples[kind], "attorney": ATT, "cutoff_date": "2024-06-01",
            "day_count": "ACT/360", "payments": [{"date": "2024-04-01", "amount": "1000"}], "assets": []}
    r = c.post("/api/v1/preview-lawsuit", json=body)
    assert r.status_code == 200, r.text
    r = c.post("/api/v1/generate-lawsuit", json={**body, "edited_blocks": r.json()["blocks"]})
    assert r.status_code == 200, r.text


def test_ledger_exposes_fields_the_ui_reads(samples):
    c = TestClient(create_app())
    p = samples["pagare"]
    body = {"principal": p["amount"], "currency": "CLP", "issue_date": p["issue_date"],
            "maturity_date": p["maturity_date"], "cutoff_date": "2024-06-01", "agreed_rate": "24",
            "day_count": "ACT/360", "payments": []}
    j = c.post("/api/v1/liquidate", json=body).json()
    types_ts = (SAMPLES.parent / "types.ts").read_text(encoding="utf-8")
    for key in [*j, *j["months"][0], *j["days"][0]]:
        assert key in types_ts, f"frontend/src/lib/types.ts does not declare API field {key!r}"
