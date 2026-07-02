# Crystal Ball RC validation — overnight batch 2 (presented excerpt)

*Auto-updated by `RC_report/cb_validate_overnight2.py`. Status: **DONE — 21/26 PASS** (2026-06-25 05:50). Outputs: `validate_overnight2_20260624-234730`.*

New (technology, node) cases from the 20-tech x 10-node presented excerpt, not previously validated. Protocol: re-solve at capex = orig*(1 - 1.01*r) [must build] and orig*(1 - 0.99*r) [must not build], r = clean operational ratio from run C.

**21 PASS / 5 FAIL** of 26 checked.

| # | technology | node | RC ratio [%] | build@-1.01r [GW] | nobuild@-0.99r [GW] | result |
|---|---|---|---:|---:|---:|---|
| 1 | photovoltaics | SK | 0.25 | 0.2291 | 0 | **PASS** |
| 2 | electrolysis | CH | 2.62 | 0.02055 | 0 | **PASS** |
| 3 | reservoir_hydro | NO | 7.10 | 1.197 | 0 | **PASS** |
| 4 | run-of-river_hydro | BG | 8.18 | 0.0224 | 0 | **PASS** |
| 5 | heat_pump_DH | ES | 11.95 | 0.5449 | 0 | **PASS** |
| 6 | DAC | SE | 13.27 | 0.002193 | 0 | **PASS** |
| 7 | wind_onshore | BG | 14.78 | 2.06 | 0 | **PASS** |
| 8 | methanol_from_hydrogen | DE | 17.48 | 0.05201 | 0 | **PASS** |
| 9 | electrode_boiler | DE | 25.28 | 1.141 | 0 | **PASS** |
| 10 | fuel_cell | ES | 28.11 | 0.5356 | 0 | **PASS** |
| 11 | SMR_CCS | DE | 32.84 | 0.02102 | 0 | **PASS** |
| 12 | natural_gas_turbine | NO | 36.78 | 0 | 0 | **FAIL** |
| 13 | coal_to_cement_fuel | CZ | 59.45 | 0.4887 | 0 | **PASS** |
| 14 | natural_gas_turbine_CCS | BG | 61.60 | 0 | 0 | **FAIL** |
| 15 | natural_gas_boiler | DE | 70.98 | 1.141 | 0 | **PASS** |
| 16 | natural_gas_turbine_CCS | SK | 4.27 | 0 | 0 | **FAIL** |
| 17 | natural_gas_turbine_CCS | CZ | 9.77 | 0 | 0 | **FAIL** |
| 18 | SMR_CCS | ES | 23.87 | 0 | 0 | **FAIL** |
| 19 | reservoir_hydro | CZ | 13.09 | 0.1154 | 0 | **PASS** |
| 20 | heat_pump_DH | FR | 17.66 | 0.1087 | 0 | **PASS** |
| 21 | photovoltaics | FI | 21.20 | 1.468 | 0 | **PASS** |
| 22 | run-of-river_hydro | CH | 26.94 | 2.146 | 0 | **PASS** |
| 23 | heat_pump_DH | BG | 19.85 | 0.0369 | 0 | **PASS** |
| 24 | reservoir_hydro | FR | 16.44 | 7.55 | 0 | **PASS** |
| 25 | run-of-river_hydro | CZ | 26.51 | 0.04023 | 0 | **PASS** |
| 26 | heat_pump_DH | DE | 29.21 | 0.8217 | 0 | **PASS** |

*Flagged cases (natural_gas_turbine_CCS@SK/CZ, SMR_CCS@ES) are expected to FAIL: their high perturbation swing marks the reconstructed RC as a lower bound.*
