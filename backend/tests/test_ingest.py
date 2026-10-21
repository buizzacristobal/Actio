import csv
import json
from pathlib import Path

import pytest

from app.engine.cmf_ingest import IngestError, build
from app.engine.cmf_rates import RateTable
from app.schemas.liquidation import RateCategory

HEAD = ["period_id", "valid_from", "valid_to", "category", "corriente", "tmc"]


def write(tmp: Path, rows, uf=None):
    p, u = tmp / "p.csv", tmp / "u.csv"
    with p.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(HEAD)
        w.writerows(rows)
    with u.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["month", "uf_10th"])
        w.writerows(uf or [("2024-01", "36000.00"), ("2024-02", "36360.00"), ("2024-03", "36720.00"), ("2024-04", "37000.00")])
    return p, u


def rows(pid, frm, to, c="10.5"):
    return [(pid, frm, to, cat.value, c, "15.75") for cat in RateCategory]


def test_build_ok_and_loadable(tmp_path):
    p, u = write(tmp_path, rows("2024-01", "2024-01-15", "2024-02-14")
                 + rows("2024-02", "2024-02-15", "2024-03-14"))
    data = build(p, u, "test", verified=True)
    assert data["metadata"]["verified"] is True and len(data["periods"]) == 2
    t = RateTable(json.loads(json.dumps(data)))
    assert t.verified


@pytest.mark.parametrize("bad,msg", [
    (rows("2024-01", "2024-01-15", "2024-02-14") + rows("2024-02", "2024-02-20", "2024-03-14"), "hueco"),
    (rows("2024-01", "2024-01-15", "2024-02-14")[:-1], "faltan"),
    ([("2024-01", "2024-01-15", "2024-02-14", "nope", "1", "2")], "categoría"),
    ([("2024-01", "2024-01-15", "2024-02-14", "reajustable_uf_all", "5", "4")], "TMC"),
])
def test_build_rejects_bad_data(tmp_path, bad, msg):
    p, u = write(tmp_path, bad)
    with pytest.raises(IngestError, match=msg):
        build(p, u, "t", False)


def test_uf_coverage_required(tmp_path):
    p, u = write(tmp_path, rows("2024-01", "2024-01-15", "2024-02-14"), uf=[("2024-01", "36000.00")])
    with pytest.raises(IngestError, match="uf.csv"):
        build(p, u, "t", False)
