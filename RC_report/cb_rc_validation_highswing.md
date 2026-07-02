# Crystal Ball RC validation — high-swing screen (lower-half excerpt)

*Auto-updated by `RC_report/cb_validate_highswing.py`. Status: **DONE — 0/2 PASS** (2026-06-26 08:55). Outputs: `validate_highswing_20260625-112454`.*

Untested high-swing (>5pp) conversion cases from the lower half of the excerpt. A high swing predicts the reconstructed RC is a **lower bound** (expected FAIL). Protocol: re-solve at capex = orig*(1 - 1.01*r) [must build] and orig*(1 - 0.99*r).

| # | technology | node | RC ratio [%] | build@-1.01r [GW] | nobuild@-0.99r [GW] | result |
|---|---|---|---:|---:|---:|---|
| 1 | SMR_CCS | CH | 8.58 | 0 | 0 | **FAIL** |
| 2 | SMR | SK | 90.52 | 0 | 0 | **FAIL** |