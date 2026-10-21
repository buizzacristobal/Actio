# Liquidation test vectors

Each `*.json` file is one case: `table` (a rate table in `cmf_rates_seed.json` format), `params`
(`LiquidationParams`) and `expected` (`interest_clp`, `total_clp`). Run by `tests/test_vectors.py`.

To add a **real** judicial liquidation: copy the rates the court used into `table`, the inputs into
`params`, the approved amounts into `expected`, set `"verified": true` and cite the case in `source`.
Current vectors are NOT verified court cases.
