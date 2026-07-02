# Crystal Ball reduced-cost validation — collected results

*Auto-updated by `RC_report/cb_validate_batch.py`. Status: **DONE — 8/9 PASS** (2026-06-24 12:12). Outputs: `validate_batch_20260624-084244`.*

## Method

Degeneracy-immune ground truth by re-solving the full Crystal Ball model with the candidate's capex perturbed around its clean operational reduced cost:

- `build`  : capex = orig·(1 − 1.01·r) → the technology **must** build

- `nobuild`: capex = orig·(1 − 0.99·r) → the technology **must not** build

where r = `rc_capex_equivalent_operational / capex` from the clean run C. A case **PASSES** iff it builds at −1.01·r and stays unbuilt at −0.99·r (the RC pins the build threshold to within ±1 %). The relative swap is unit-invariant.

## This batch (new technologies/nodes)

**8 PASS / 1 FAIL** of 9 checked so far.

| # | technology | node | RC ratio [%] | build@−1.01r [GW] | nobuild@−0.99r [GW] | result |
|---|---|---|---:|---:|---:|---|
| 1 | coal_to_cement_fuel | SK | 54.46 | 0.3829 | 0.3829 | **FAIL** |
| 2 | heat_pump_DH | SE | 24.24 | 0.06505 | 0 | **PASS** |
| 3 | wind_offshore | SE | 45.20 | 31.04 | 0 | **PASS** |
| 4 | photovoltaics | SE | 49.24 | 3.603 | 0 | **PASS** |
| 5 | methanol_from_hydrogen | BG | 30.63 | 0.07995 | 0 | **PASS** |
| 6 | run-of-river_hydro | SE | 51.30 | 1.995 | 0 | **PASS** |
| 7 | reservoir_hydro | SE | 44.27 | 11.65 | 0 | **PASS** |
| 8 | wind_onshore | CH | 48.37 | 25.9 | 0 | **PASS** |
| 9 | natural_gas_turbine_CCS | ES | 19.78 | 0.003132 | 0 | **PASS** |

## Previously validated (clean operational RC, earlier runs)

| technology | node | RC ratio [%] | build [GW] | result | note |
|---|---|---:|---:|---|---|
| photovoltaics | CZ | 4.75 | 0.32 | **PASS** | clean op_C |
| photovoltaics | NO | 21.52 | 2.79 | **PASS** | clean op_C |
| wind_onshore | NO | 16.58 | 26.80 | **PASS** | clean op_C |
| wind_offshore | FR | 11.18 | 15.65 | **PASS** | clean op_C |
| run-of-river_hydro | SK | 12.81 | 0.36 | **PASS** | clean op_C |
| reservoir_hydro | CH | 24.42 | 1.64 | **PASS** | clean op_C |
| electrolysis | FI | 12.36 | - | **FAIL** | scarcity-vertex degenerate (import island) |
| nuclear | ES | 3.20 | - | **FAIL** | scarcity-vertex degenerate (import island) |

*The two FAILs are the known import-island conversion techs whose operational RC is a lower bound (scarcity-vertex degeneracy, see `docs/rc_crystalball_conversion_failure.md`); every clean, perturbation-stable candidate validated so far has passed.*

## Focused test — nuclear @ FR (2026-06-24)

Critical detector test: nuclear is the canonical self-cannibalising tech (FAIL at ES/FI),
but at **FR** the swing is **0.062 pp** (flagged *reliable*) and the distance is large
(ratio **72.8 %**). Result: **PASS** — builds **41.1 GW** at −1.01·r and **0** at −0.99·r.
→ Reliability is a property of the **(tech, node) vertex**, not the technology: the *same*
nuclear is exact at a well-connected node (unique dual, FR) and a lower bound at an
import-island scarcity vertex (ES, ratio 2.3 % scheindistanz, swing 9.4 pp). The swing
separates them correctly. (`RC_report/cb_validate_nuclear_fr.py`, `cb_nuclear_fr_result.md`.)

## Takeaways (both runs combined)

- **15 distinct PASS** across a broad spread of technologies and nodes: renewables
  (PV, wind on-/offshore), hydro (run-of-river, reservoir), a heat pump, and — notably —
  three **non-renewable conversion** techs at well-connected nodes
  (`heat_pump_DH`, `methanol_from_hydrogen`, `natural_gas_turbine_CCS`). The clean
  operational RC pins the build threshold to within ±1 % in every one of these cases.
- **3 FAIL, all structurally explained — none is a silent error:**
  1. `electrolysis@FI`, `nuclear@ES` — import-island **scarcity-vertex degeneracy**; the
     operational RC is a *lower bound* on the true distance (detectable via the
     perturbation swing).
  2. `coal_to_cement_fuel@SK` — **constraint-pinned**, a different mechanism: it builds the
     *identical* 0.383 GW at both ±1 % points, i.e. the quantity is fixed by another
     binding constraint (a cement/fuel demand), so the capex RC does not mark a *marginal*
     build threshold. The low perturbation swing does **not** catch this — it is a distinct,
     non-degeneracy failure mode worth flagging in the reliability discussion.
- **One marginal PASS:** `natural_gas_turbine_CCS@ES` builds only 0.003 GW at −1.01·r
  (knife-edge price-setter, like the showcase gas turbine), yet still passes the ±1 % test
  cleanly — the threshold is correct even where the build is tiny.
- **Headline for the report:** at well-behaved (clean, perturbation-stable) tech–nodes the
  operational RC is a quantitatively trustworthy distance-to-build signal across technology
  *types*, not just renewables; the failures fall into two recognisable buckets
  (scarcity-vertex degeneracy, constraint-pinning).
