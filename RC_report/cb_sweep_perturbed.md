# Crystal Ball — true break-even vs clean (op_C) and perturbed (op_B) RC

*`RC_report/cb_sweep_perturbed.py`. Status: **DONE** (2026-06-27 18:12). Outputs: `sweep_perturbed_20260627-155504`.*

Degenerate (flagged) cases. Capex sweep (presolve on) brackets the true break-even; compared with op_C (clean) and op_B (perturbed). Expectation (cf. nuclear@ES): op_C < op_B <= true.

| tech | node | op_C [%] | op_B [%] | true break-even [%] | op_B a lower bound? |
|---|---|---:|---:|---:|---|
| nuclear | FI | 2.2 | 10.6 | 11--16 | YES (true > op_B) |
| electrolysis | FI | 9.7 | 14.8 | 20--27 | YES (true > op_B) |
| methanol_from_hydrogen | CZ | 9.0 | 17.0 | 17--17 | op_B ~ true |
| SMR_CCS | SE | 6.3 | 17.2 | 17--22 | YES (true > op_B) |

## Per-cut build [GW]

**nuclear@FI** (op_C 2.2%, op_B 10.6%): 11%->0, 16%->1.64, 23%->1.67, 36%->3.3
**electrolysis@FI** (op_C 9.7%, op_B 14.8%): 15%->0, 20%->0, 27%->0.246, 40%->0.33
**methanol_from_hydrogen@CZ** (op_C 9.0%, op_B 17.0%): 17%->0.395, 22%->0.878, 29%->1.07, 42%->1.07
**SMR_CCS@SE** (op_C 6.3%, op_B 17.2%): 17%->0, 22%->0.665, 29%->1.33, 42%->2.88