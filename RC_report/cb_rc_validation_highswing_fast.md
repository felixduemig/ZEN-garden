# Crystal Ball RC validation — high-swing remainder (presolve-on, primal-only)

*`RC_report/cb_validate_highswing_fast.py`. Status: **DONE** (2026-06-26 21:21).*

The 2 high-swing cases the earlier run could not reach. Presolve ON (valid: this reads only the primal build, not the RC). High swing predicts a lower bound -> expected FAIL.

| # | technology | node | RC ratio [%] | build@-1.01r [GW] | nobuild@-0.99r [GW] | result |
|---|---|---|---:|---:|---:|---|
| 1 | haber_bosch | SE | 79.34 | 0 | 0 | **FAIL** |
| 2 | natural_gas_turbine_CCS | FR | 83.98 | 0 | 0 | **FAIL** |