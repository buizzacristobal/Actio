"""CMF rate periods (valid_from..valid_to)  and UF series (Ley 18.010).

All values are Decimals parsed from strings; floats never enter the engine.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.schemas.liquidation import RateCategory

SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "cmf_rates_seed.json"
UF_PERIOD_START_DAY = 10  # UF readjustment period runs 10th -> 9th


class RateNotFoundError(LookupError):
    """Requested month/date is outside the loaded tables."""


def _month_key(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


class RateTable:
    def __init__(self, data: Mapping[str, Any]) -> None:
        meta = data.get("metadata", {})
        self.verified: bool = bool(meta.get("verified", False))
        self.source: str = str(meta.get("source", "unknown"))
        self._uf10: dict[str, Decimal] = {
            k: Decimal(v) for k, v in data["uf_10th"].items()
        }
        self._periods: list[tuple[date, date, dict[str, dict[str, Decimal]]]] = sorted(
            (
                date.fromisoformat(p["valid_from"]),
                date.fromisoformat(p["valid_to"]),
                {c: {"corriente": Decimal(str(r["corriente"])), "tmc": Decimal(str(r["tmc"]))}
                 for c, r in p["rates"].items()},
            )
            for p in data["periods"]
        )

    def rate(self, d: date, category: RateCategory) -> tuple[Decimal, Decimal]:
        """Return (interés corriente, TMC), annual %, of the period valid on `d`."""
        for start, end, cats in self._periods:
            if start <= d <= end:
                try:
                    r = cats[category.value]
                except KeyError as exc:
                    raise RateNotFoundError(f"No {category.value} rate for {d}") from exc
                return r["corriente"], r["tmc"]
        raise RateNotFoundError(f"No CMF rate period covers {d.isoformat()}")

    def uf_value(self, d: date) -> Decimal:
        """UF on `d`: geometric daily interpolation between the 10th anchors,
        rounded half-up to 2 decimals as published."""
        y, m = d.year, d.month
        if d.day < UF_PERIOD_START_DAY:
            y, m = _shift_month(y, m, -1)
        ny, nm = _shift_month(y, m, 1)
        try:
            start = self._uf10[f"{y}-{m:02d}"]
            end = self._uf10[f"{ny}-{nm:02d}"]
        except KeyError as exc:
            raise RateNotFoundError(f"No UF series covering {d.isoformat()}") from exc
        p_start = date(y, m, UF_PERIOD_START_DAY)
        p_end = date(ny, nm, UF_PERIOD_START_DAY)
        k = (d - p_start).days
        n = (p_end - p_start).days
        if k == 0:
            return start.quantize(Decimal("0.01"), ROUND_HALF_UP)
        value = start * (end / start) ** (Decimal(k) / Decimal(n))
        return value.quantize(Decimal("0.01"), ROUND_HALF_UP)


@lru_cache(maxsize=1)
def load_default_table() -> RateTable:
    with SEED_PATH.open(encoding="utf-8") as fh:
        return RateTable(json.load(fh))
