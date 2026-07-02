# Crystal Ball RC validation — targeted batch (presolve-on)

*`RC_report/cb_validate_targeted.py`. Status: **DONE — 3P/4F** (2026-06-26 22:55). Outputs: `validate_targeted_20260626-211500`.*

High-value untested excerpt cases, presolve ON (primal-only test). **3 PASS / 4 FAIL** of 7.

| # | technology | node | RC ratio [%] | build@-1.01r | nobuild@-0.99r | result |
|---|---|---|---:|---:|---:|---|
| 1 | nuclear | FI | 2.20 | 0 | 0 | **FAIL** |
| 2 | SMR_CCS | SK | 4.28 | 0 | 0 | **FAIL** |
| 3 | methanol_from_hydrogen | SK | 25.66 | 0.002309 | 0 | **PASS** |
| 4 | SMR_CCS | SE | 6.34 | 0 | 0 | **FAIL** |
| 5 | DAC | NO | 32.85 | 0.001737 | 0 | **PASS** |
| 6 | methanol_from_hydrogen | CZ | 9.05 | 0 | 0 | **FAIL** |
| 7 | run-of-river_hydro | FR | 30.56 | 5.157 | 0 | **PASS** |