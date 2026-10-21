import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.engine.calculator import calculate_day_by_day_ledger
from app.engine.cmf_rates import RateTable
from app.schemas.liquidation import LiquidationParams

FILES = sorted((Path(__file__).parent / "vectors").glob("*.json"))


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_vector(path):
    v = json.loads(path.read_text(encoding="utf-8"))
    led = calculate_day_by_day_ledger(LiquidationParams(**v["params"]), RateTable(v["table"]))
    assert led.interest_clp == Decimal(v["expected"]["interest_clp"])
    assert led.total_clp == Decimal(v["expected"]["total_clp"])
