# Ultracode task — Derive, mathematically and rigorously, why the operational reduced-cost reconstruction UNDERESTIMATES the distance-to-build for some Crystal Ball conversion technologies; then either give a correct fix or prove it is unfixable.

You are working in the ZEN-garden energy-system optimization repo. A reduced-cost (RC) post-processing
method reconstructs, for every `capacity_addition`, "how much CAPEX reduction would make this technology
build". On a small validated showcase it is exact; on the full **Crystal Ball (CB) snapshot** it FAILS the
ground-truth ±1% test for several conversion technologies, always in the same direction (the technology does
**not** build even at the predicted build point → the RC **overstates the value / underestimates the distance**).
The previous hand-wavy explanation ("marginal-vs-finite effect") is NOT accepted. Your job is a rigorous,
math-backed root-cause, verified against the data already on disk, and a verdict: **a concrete fix, or a proof
that the signal is intrinsically unreliable for these techs.**

## Hard constraints
- **Do NOT launch full CB optimization runs** (each ≈ 11 min; ~734k rows). No "ewige Läufe".
- You MAY: read all existing CSV/HDF5 outputs and the source code; do small/fast pandas analyses; and
  **build & solve tiny toy LPs** (scipy.optimize.linprog or gurobipy, sub-second) to demonstrate/verify a
  mechanism. That is encouraged for the proof.
- Environment: run Python via `C:/Users/felix/anaconda3/envs/zen-garden-env/python.exe`. Repo root:
  `C:\Users\felix\Documents\GitHub\ZEN-garden`. Windows; use the Bash tool with that python path.
- Be skeptical of the prior conclusion. Reconcile every claim with the actual saved numbers.

## Background — how the RC is built (read these first)
- Target variable `capacity_addition`. Its native LP reduced cost is structurally 0: it appears in exactly two
  constraints — `constraint_technology_lifetime` (capacity[y] − Σ additions = existing; the VALUE side) and
  `constraint_capacity_coupling` (the CAPEX side) — whose duals cancel ("native collapse").
- Two reconstructions, written side by side in `capacity_addition_analysis*.csv`:
  - **lifetime** `rc_capex_equivalent[_input_units]`: from the `constraint_technology_lifetime` dual μ.
  - **operational** `rc_capex_equivalent_operational[_input_units]` (the PRIMARY, degeneracy-robust one):
    from the capacity-factor constraint dual ν of `constraint_capacity_factor_conversion` (`m·S ≥ G`, a pure
    upper bound on the reference-carrier throughput). Formula (see code):
    `RC_op = capex_specific − [ Σ_pay-years Σ_t (m_t · ν_{t}) / scaling − fixed_opex·δ ]`.
  - `ratio_reduction[_operational] = RC / capex_specific` (dimensionless distance-to-build).
- Code to read carefully:
  - `zen_garden/postprocess/postprocess.py` — `_compute_rc_capex_equivalent` (line ~486), called from
    `save_capacity_addition_analysis` (~874) and `save_capacity_addition_classified` (~1324).
  - Output `rc_components.csv` per run dumps a per-constraint decomposition, but NOTE: in these runs it
    contains ONLY the **lifetime** chain (constraint_type == 'lifetime', 2952 rows; no capacity-factor rows).
    So the operational ν is NOT in rc_components.csv — read it from `dual_dict.h5` (see below). rc_components
    cols: set_technologies, set_capacity_types, set_location, set_time_steps_yearly, scaling, constraint_type,
    component_year, raw_dual, coefficient, discount_factor, contribution_to_rc.
- Docs (read for the theory + prior dead ends): `docs/rc_reduced_cost_methodology.md`,
  `docs/rc_operational_reconstruction.md`, `docs/rc_reliability_findings.md`,
  `docs/rc_analysis_known_issues.md`, `docs/rc_lifetime_rhs_perturbation.md`.
- Key prior theorem (verify it / its assumptions): the operational reconstruction is COMPLETE (loses no real
  factor vs lifetime) **iff the capacity-factor constraint is the only value-bearing constraint containing the
  `capacity` variable.** It removes the capacity-variable "leak"; it does NOT remove dispatch-price degeneracy.

## The model (already solved — use the outputs, do not re-solve)
Crystal Ball snapshot: **28 nodes, 1 optimized year (2050), 10 typical hours (TSA), 68 conversion + 5 storage +
5 transport techs.** Solver was Gurobi `Method 2` (barrier) + `Crossover 1` + `Presolve 0` + `use_scaling 0`,
`save_duals`+`save_reduced_costs` ON. Three solved runs are on disk:
- `outputs_CB_overnight/runA/Crystal_Ball/` — no rhs perturbation (storage power-pert 1e-4 + fixed durations
  battery 16h / pumped_hydro 22h / salt_cavern 145h).
- `outputs_CB_overnight/runB/Crystal_Ball/` — rhs perturbation 1e-3 (+ same storage treatment).
- `outputs_CB_overnight/runC/Crystal_Ball/` — **fully clean, NO perturbation at all** (use this as the
  reference for the "true" RC; the perturbations are only tools to repair the lifetime dual).
Each folder has: `capacity_addition_analysis_conversion.csv` (op + lifetime RC, ratios, case, rc_reliable),
`rc_components.csv` (lifetime-only, see note above), `dual_dict.h5`, `reduced_costs_dict.h5`, `var_dict.h5`,
`param_dict.h5`, `system.json`.

**Saved duals (`dual_dict.h5`, 47 constraints — all present, verified).** The ones you need:
- `constraint_capacity_factor_conversion` — the operational dual ν (the heart of RC_op).
- `constraint_nodal_energy_balance` — nodal prices λ per (carrier, node, time); reconstruct ν independently
  from λ to cross-check (electricity AND hydrogen carriers both present).
- `constraint_technology_lifetime` — the lifetime dual μ.
- `constraint_technology_capacity_limit_reached` / `_not_reached`, `constraint_capacity_coupling`,
  `constraint_capex_coupling`, `constraint_carrier_conversion`, `constraint_carbon_emissions_annual_limit`
  — every OTHER constraint that can contain a tech's capacity/throughput; check which carry a nonzero dual
  at the optimum for nuclear/electrolysis (this is exactly lead 2, the completeness check).
Read via `zen_garden.postprocess.results.results.Results(...).get_dual(name)`, or fall back to reading
`dual_dict.h5` directly with `h5py` / pandas `read_hdf` if the Results wrapper is awkward.
`param_dict.h5` holds the `max_load` (m_t), capex, opex, conversion_factor params; `var_dict.h5` holds the
primal flows/capacities at the optimum.

## The puzzle — the validation failures (clean ground truth, ±1% build/nobuild)
Ground truth = override the per-(tech,node) CAPEX in the data CSV and re-solve CLEAN (no perturbation,
primal-only), then read the PRIMAL `capacity_addition` ("does it actually build?"). PASS = builds at
capex·(1−1.01·ratio) and NOT at capex·(1−0.99·ratio). These ground-truth runs are on disk (do not re-run them):
- `outputs_CB_overnight/validate_20260623-011718/` — 6 cases: c01 PV CZ (op_A), c02 wind_offshore FR (op_A),
  c03/c04 electrolysis FI (op_A / op_B), c05/c06 nuclear ES (op_A / op_B). Plus `validate_summary.csv`.
- `outputs_CB_overnight/validate_20260623-080711/` — c01 PV CZ at the CLEAN op_C ratio (this one PASSES).
- Per case: subfolders `cNN_<tech>_<node>_build/Crystal_Ball/capacity_addition_analysis.csv` and `…_nobuild/…`
  give the primal built capacity at the two overridden CAPEX values (these runs saved no duals — primal only).
Summary of results:

| tech | node | CAPEX | op_A (pert) | op_B (rhs-pert) | op_C (clean) | lifetime_C | ±1% result | true threshold |
|---|---|---|---|---|---|---|---|---|
| wind_offshore | FR | 1926.26 | 11.09% | 11.09% | 11.18% | (≈op) | **PASS** | ≈ 11.1% |
| photovoltaics | CZ | 316.99 | 4.38% | 4.37% | **4.75%** | (≈op) | clean **PASS**, pert **FAIL** | ≈ 4.75% |
| electrolysis | FI | 576.43 | 12.36% | 14.77% | **9.74%** | (≈op) | **FAIL all** | **> 14.8%** |
| nuclear | ES | 5578.68 | 3.20% | 11.70% | **2.26%** | (≈op) | **FAIL all** | **> 11.7%** |

So: wind_offshore and PV (with the clean RC) validate. **electrolysis and nuclear fail badly: the true build
threshold is far beyond ANY reconstructed RC (op or lifetime, with or without perturbation).** The
reconstruction overstates the marginal value of these technologies' capacity.

## What is already established (do not re-derive, but you may re-check)
- The perturbation is NOT the cause of the genuine failures: clean op (run C) is even *smaller* (worse) for
  electrolysis/nuclear; the aggregate clean-vs-pert shift is 0pp (median over 394 buildable cases). With pert,
  lifetime == operational in 100% of 1145 buildable_rc cases; without pert lifetime collapses to ~0 in 12%.
- The same "RC overstates value at an unbuilt corner" pattern was found for TRANSPORT lines and attributed
  (after much back-and-forth) to a degenerate corner / marginal-vs-finite gap. That explanation is exactly what
  is in doubt now and must be made rigorous or replaced.

## Structural leads you MUST investigate (these are concrete and checkable from data)
1. **Carrier / reference-carrier mismatch.** `electrolysis` has `reference_carrier = hydrogen` (output), input
   electricity; `nuclear`/`wind_offshore`/`photovoltaics` have `reference_carrier = electricity`. The
   capacity-factor constraint `m·S ≥ G` is on the *reference* carrier. Verify the operational reconstruction
   reads the correct dual and that ν for electrolysis correctly encodes the hydrogen-side value (H2 nodal price
   − electricity input cost / conversion factor). A wrong carrier/ conversion-factor handling would
   systematically misvalue electrolysis.
2. **A second value-bearing constraint on `capacity` (completeness violation).** `nuclear`,
   `wind_offshore`, `photovoltaics` have `capacity_limit` default 0 in attributes.json — almost certainly
   overridden per node by a `capacity_limit.csv` (renewable/nuclear potentials). Enumerate EVERY model
   constraint that contains the `capacity` (or `capacity_addition`) variable for nuclear and electrolysis
   (grep `zen_garden/model/`), and check (from `dual_dict.h5`) which of them are binding / carry a nonzero
   dual at the optimum. If a binding capacity constraint exists that the operational sum omits, the
   completeness theorem is violated and the operational RC is provably wrong — derive the corrected formula.
3. **Verify the reconstruction arithmetic.** Recompute RC_op by hand from the saved duals
   (`constraint_capacity_factor_conversion` dual ν, the `m_t` max_load params, `scaling`, discount) and confirm
   it equals the reported `rc_capex_equivalent_operational`. Check the `scaling`, the per-typical-hour weights
   (do the 10 typical hours carry their cluster weights?), discounting, and fixed-OPEX term. A weighting/scaling
   bug would be the simplest fix.
4. **Degeneracy: reported dual vs true right-derivative.** Test whether the reported ν (→ RC) exceeds the true
   right-derivative of the optimal cost w.r.t. capacity. The validation builds (`validate_*` folders) bracket
   the true threshold; reconcile in € the reported RC against that bracket. Check primal/dual degeneracy at the
   unbuilt vertex (slack of `m·S ≥ G`, the reference flow at its bounds, multiple marginal suppliers at equal
   cost on the relevant carrier).
5. **Self-cannibalization / TSA (the prior, doubted hypothesis).** If 1–4 do not fully account for the gap,
   make the marginal-vs-finite argument RIGOROUS with a minimal toy LP you build yourself: a baseload tech
   (nuclear-like, flat output) and a flexible-demand tech (electrolysis-like) in a few-hour market, where
   the reported capacity-factor dual at zero capacity provably exceeds the right-derivative because a finite
   build moves the carrier price. Quantify and compare the toy's gap shape to the CB numbers. State clearly
   whether the 10-typical-hour aggregation is necessary for the effect or merely amplifies it (you may reason
   about it analytically; you may NOT re-run CB at higher resolution).

## How to read the saved duals (Python)
```python
from zen_garden.postprocess.results.results import Results
r = Results("outputs_CB_overnight/runC/Crystal_Ball")
nu  = r.get_dual("constraint_capacity_factor_conversion")  # VERIFIED: DataFrame, index (technology, node),
                                                           # columns = 8760 time steps (10 typical hours
                                                           # expanded to the full year). e.g. nu.loc[('nuclear','ES')]
lam = r.get_dual("constraint_nodal_energy_balance")        # nodal prices λ; has a 'carrier' index level —
                                                           # lam.xs('electricity', level='carrier'), 'hydrogen'
mu  = r.get_dual("constraint_technology_lifetime")         # lifetime dual μ
```
(VERIFIED on runC: `nu.shape == (2072, 8760)`, index names `['technology','node']`. The operational RC sums
`m_t · ν` over these 8760 columns with the per-step weights, then `/scaling`. `param_dict.h5` gives `max_load`
(m_t) and conversion factors; reading the h5 files directly with h5py/pandas also works if needed.)

## Deliverable
A rigorous writeup (save to `docs/rc_crystalball_conversion_failure.md`) that:
1. States, with the actual CB numbers, the exact magnitude of the over-statement for nuclear ES and
   electrolysis FI (reconstructed RC vs the bracketed true threshold, in € and %).
2. Identifies the mechanism with a KKT / LP-sensitivity derivation, **pinpointed to which of leads 1–5 it is**
   (it may be more than one; rank by contribution, backed by the saved duals — not assertions).
3. Either: (a) gives the CORRECTED reconstruction (formula + the code change in `postprocess.py`, and a check
   that the corrected RC matches the validation thresholds for nuclear/electrolysis/PV/wind), OR (b) proves the
   signal is intrinsically unrecoverable from a single solve for these techs, with the minimal counterexample.
4. Explicitly confirms or refutes the prior "marginal-vs-finite" claim, with evidence.

Start by reconciling lead 3 (arithmetic) and lead 2 (which constraints bind), because they are pure data
checks; only invoke leads 4–5 (degeneracy / toy LP) if 1–3 do not close the gap. Show your numbers.
```
