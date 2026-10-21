"""Build cmf_rates_seed.json from transcribed CMF data (two CSV files), with validation.

    python -m app.engine.cmf_ingest --periods periods.csv --uf uf.csv \\
        --source "CMF certificados ene-2021..oct-2026 (Diario Oficial)" --verified -o data/cmf_rates.json

periods.csv: period_id,valid_from,valid_to,category,corriente,tmc   (one row per category)
uf.csv:      month,uf_10th                                          (YYYY-MM, UF on the 10th)
A file is marked verified=true ONLY with --verified; do that only after checking every figure
against the official publication.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.schemas.liquidation import RateCategory

CATEGORIES = {c.value for c in RateCategory}


class IngestError(ValueError):
    pass


def _dec(raw: str, what: str) -> Decimal:
    try:
        v = Decimal(raw.strip().replace(",", "."))
    except InvalidOperation as exc:
        raise IngestError(f"{what}: número inválido {raw!r}") from exc
    if v <= 0:
        raise IngestError(f"{what}: debe ser positivo ({raw})")
    return v


def build(periods_csv: Path, uf_csv: Path, source: str, verified: bool) -> dict:
    periods: dict[str, dict] = defaultdict(lambda: {"rates": {}})
    with periods_csv.open(encoding="utf-8", newline="") as fh:
        for n, row in enumerate(csv.DictReader(fh), start=2):
            pid, cat = row["period_id"].strip(), row["category"].strip()
            if cat not in CATEGORIES:
                raise IngestError(f"línea {n}: categoría desconocida {cat!r}")
            corr, tmc = _dec(row["corriente"], f"línea {n} corriente"), _dec(row["tmc"], f"línea {n} tmc")
            if tmc <= corr:
                raise IngestError(f"línea {n}: la TMC debe ser mayor que el interés corriente")
            p = periods[pid]
            frm, to = date.fromisoformat(row["valid_from"]), date.fromisoformat(row["valid_to"])
            if p.get("valid_from", frm.isoformat()) != frm.isoformat() or p.get(
                "valid_to", to.isoformat()
            ) != to.isoformat():
                raise IngestError(f"línea {n}: fechas inconsistentes dentro del período {pid}")
            if frm > to:
                raise IngestError(f"línea {n}: valid_from posterior a valid_to")
            p.update(period_id=pid, valid_from=frm.isoformat(), valid_to=to.isoformat())
            p["rates"][cat] = {"corriente": str(corr), "tmc": str(tmc)}
    ordered = sorted(periods.values(), key=lambda p: p["valid_from"])
    if not ordered:
        raise IngestError("periods.csv vacío")
    for p in ordered:
        missing = CATEGORIES - set(p["rates"])
        if missing:
            raise IngestError(f"período {p['period_id']}: faltan categorías {sorted(missing)}")
    for a, b in zip(ordered, ordered[1:], strict=False):
        if date.fromisoformat(b["valid_from"]) != date.fromisoformat(a["valid_to"]) + timedelta(days=1):
            raise IngestError(f"hueco o solape entre {a['period_id']} y {b['period_id']}")
    uf: dict[str, str] = {}
    with uf_csv.open(encoding="utf-8", newline="") as fh:
        for n, row in enumerate(csv.DictReader(fh), start=2):
            uf[row["month"].strip()] = str(_dec(row["uf_10th"], f"uf línea {n}"))
    last = date.fromisoformat(ordered[-1]["valid_to"])
    first = date.fromisoformat(ordered[0]["valid_from"])
    need = {f"{first.year}-{first.month:02d}", f"{last.year}-{last.month:02d}"}
    nm = last.replace(day=1) + timedelta(days=32)
    need.add(f"{nm.year}-{nm.month:02d}")
    if need - set(uf):
        raise IngestError(f"uf.csv debe cubrir al menos: {sorted(need - set(uf))}")
    return {
        "metadata": {"source": source, "verified": verified,
                     "units": "annual percent; uf_10th = UF on the 10th of each month"},
        "uf_10th": dict(sorted(uf.items())),
        "periods": ordered,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--periods", type=Path, required=True)
    ap.add_argument("--uf", type=Path, required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--verified", action="store_true")
    ap.add_argument("-o", "--output", type=Path, required=True)
    a = ap.parse_args()
    data = build(a.periods, a.uf, a.source, a.verified)
    a.output.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(data['periods'])} períodos, {len(data['uf_10th'])} meses UF -> {a.output}")


if __name__ == "__main__":
    main()
