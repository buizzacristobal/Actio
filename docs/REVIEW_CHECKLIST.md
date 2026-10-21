# Attorney review checklist

Every item below is an assumption built into the software. Mark each as **confirmed**, **change to…**, or **not applicable** before any real filing. Nothing here has been verified by a lawyer.

## Financial rules (`backend/app/engine`)

| # | Assumption | Where | Status |
|---|---|---|---|
| F1 | Interest is simple (no anatocismo) | `calculator.py` | ☐ |
| F2 | Day count: ACT/360 default (ACT/365 selectable) | `schemas/liquidation.py` `DayCount` | ☐ |
| F3 | CMF rate applies from `valid_from` to `valid_to` of each certificate | `cmf_rates.py` | ☐ |
| F4 | Rate bracket (≤50 / 50–200 / ≥200 UF) fixed once, at issue date | `calculator.select_category` | ☐ |
| F5 | The ≥200 UF bracket merges the CMF's 200–5.000 and >5.000 UF categories | `RateCategory` | ☐ |
| F6 | TMC cap applied per day to the agreed rate (art. 6 Ley 18.010) | `calculator.apply_tmc_cap` | ☐ |
| F7 | Without an agreed rate: no interest before maturity; interés corriente in mora | `calculator.py` | ☐ |
| F8 | Mora starts the day after maturity | `calculator.py` | ☐ |
| F9 | UF value interpolated geometrically between the 10th of consecutive months | `cmf_rates.uf_value` | ☐ |
| F10 | Abonos imputed first to accrued interest, then capital (CC art. 1595); sub-peso remainder carries over | `calculator.py` | ☐ |
| F11 | UF operations: capital and interest in UF, converted at the cut-off date UF | `calculator.py` | ☐ |

## Legal text (`backend/app/engine/legal_templates.py`)

| # | Assumption | Status |
|---|---|---|
| L1 | Pagaré: art. 434 N° 4 CPC and Ley 18.092 (arts. 102 ff.) | ☐ |
| L2 | Factura: art. 434 N° 7 CPC and Ley 19.983 arts. 3 and 5 (8-day claim period) | ☐ |
| L3 | Compensatory vs moratory interest wording and when the split is shown | ☐ |
| L4 | Creditor (or its representative) designates the attorney in Patrocinio y poder (Ley 18.120) | ☐ |
| L5 | Suma format, section order and otrosí order | ☐ |
| L6 | Drafting notes about signature authorization / gestión preparatoria and factura acuse | ☐ |
| L7 | Embargo assets are listed only if the user supplies them | ☐ |

## Data

| # | Item | Status |
|---|---|---|
| D1 | `cmf_rates_seed.json` replaced by verified CMF figures (see `python -m app.engine.cmf_ingest`) | ☐ |
| D2 | At least two real court liquidations added as vectors in `backend/tests/vectors/` | ☐ |
