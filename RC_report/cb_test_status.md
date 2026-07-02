# Crystal Ball RC — test status, results, interim conclusions, open tests

*Master status of everything tested on the **Crystal Ball** (CB) model for the operational
reduced-cost (RC) reconstruction. Stand 2026-06-24. Companion docs: validation
`cb_rc_validation_collected.md`, root cause `docs/rc_crystalball_conversion_failure.md`,
reproducer `docs/rc_scarcity_reproducer_DE.md`, status `docs/rc_interpretability_status_DE.md`,
memory [[cb-snapshot-rc-findings]].*

CB instance: **28 nodes, single year (2050 snapshot), 10 typical hours (TSA)**, 68 conversion
+ 5 storage + 5 transport techs. Solver for RC: Gurobi Method 2 + Crossover 1 + Presolve 0 +
`use_scaling=0`.

---

## 1. What we have tested

| # | Test | Scope | Script / output |
|---|---|---|---|
| A | **3-run snapshot analysis** (clean / rhs-perturbed / lifetime) | all 1145 buildable_rc & reliable conversion cases | `_run_cb_main.py` → `outputs_CB_overnight/runA,B,C`; `OVERNIGHT_REPORT.md` |
| B | **±1% build/no-build validation** (degeneracy-immune ground truth via capex re-solve) | 17 distinct tech–nodes across 3 campaigns | `_rc_analysis/cb_validate5.py`, `RC_report/cb_validate_batch.py` → `cb_rc_validation_collected.md` |
| C | **Root-cause investigation** of the underestimation | nuclear@ES, electrolysis@FI + minimal LP | `_rc_analysis/a*.py`, `toy_lp3.py`, `docs/rc_crystalball_conversion_failure.md` |
| D | **Standalone reproducer** of the mechanism | 2-node import-island toy | `_rc_analysis/build_island.py`, `demo_island.py` |
| E | **Numerical-swallow hypothesis** test | tiny-build precision | `_rc_analysis/test_tiny_build.py` |
| F | **Code/robustness audit** (which duals enter the RC, which constraints are omitted) | `_compute_rc_capex_equivalent` | `zen_garden/postprocess/postprocess.py:486` |

---

## 2. Results

### 2a. Population (3-run snapshot, 1145 cases)
- **With** rhs perturbation: lifetime-RC == operational-RC in **100 %** (1144/1145).
- **Without** perturbation: lifetime-RC collapses to ~0 in **12 %** (native dual collapse).
- Operational RC **perturbation-insensitive** (op_A≈op_B) in **70 %**; **sensitive in 30 %** —
  exactly the marginal/industrial techs (natural_gas_turbine, SMR, BF_BOF, ammonia/methanol
  ICE-ship, haber_bosch), some flipping wildly (SMR ES 138 %→0 %).
- Clean-vs-perturbed operational: **median shift 0 pp** (no systematic bias).

### 2b. ±1% validation — **14 PASS / 3 FAIL**
**PASS (clean operational RC pins the build threshold to ±1 %):**
photovoltaics@CZ, @NO, @SE · wind_onshore@NO, @CH · wind_offshore@FR, @SE · run-of-river@SK,
@SE · reservoir_hydro@CH, @SE · **heat_pump_DH@SE** · **methanol_from_hydrogen@BG** ·
**natural_gas_turbine_CCS@ES** (marginal, builds only 0.003 GW but correct).
→ spans renewables, hydro, **and three non-renewable conversion techs** at well-connected nodes.

**FAIL (all structurally explained — no silent error):**
| tech–node | mechanism | bucket |
|---|---|---|
| nuclear@ES | self-cannibalising baseload at import-island scarcity vertex | degeneracy |
| electrolysis@FI | flexible demand bids up its own input price | degeneracy |
| coal_to_cement_fuel@SK | builds identical 0.383 GW at both ±1 % points; quantity fixed by the `fuel_for_cement` demand | constraint-pinning |

### 2c. Mechanism (proven)
- **Scarcity-vertex degeneracy:** at congested/import-island nodes the carrier price is a
  scarcity *rent* (non-unique dual on `[p_lo,p_hi]`); RC reads `p_hi`, a finite build realises
  `p_lo` → **RC is a lower bound** on the true distance. Magnitudes: nuclear clean 126 €/kW
  (2.26 %) vs true **>659 €/kW (>11.8 %)**; electrolysis 56 (9.74 %) vs **>86 (>14.9 %)**.
- **Unfixable from one solve (proven):** cost-vs-capacity is convex; the gap = the
  self-cannibalisation integral, which is *not* a function of the single-solve duals.
- **Not a numerical artefact:** the FAILs build *exactly* 0 even 5× past the reconstructed
  break-even; tiny builds down to 1e-5 GW are realised exactly (`test_tiny_build.py`).
- **Reproduced** in a clean 2-node island (3× overstatement, same mechanism as ES).

### 2d. Code audit (what the RC actually uses)
Reconstructs RC = capex − (operating value − diffusion − e2p)/scaling, with duals from:
`constraint_technology_lifetime` (legacy), `constraint_capacity_factor_conversion/_transport`
(operational, preferred), diffusion limits, energy-to-power ratio (storage). The capacity
limit enters as an **"at-limit" flag** + `vbasis`, not as a term. Omitted constraints that
also contain capacity: `minimum_full_load_hours`, `min/max_capacity_addition`, storage
capacity-factor (NaN), on/off + capex-PWA (→ non-LP). These are inert for the pure-LP
price-taker greenfield case, so the reconstruction column is **complete there**.

### 2e. nuclear@ES — fully resolved (capex sweep, 2026-06-24)
Clean op RC = 2.26% (126 EUR/kW); capex sweep (`outputs_CB_overnight/es_sweep/sweep.csv`)
gives the **true break-even 12–15%** → RC over-states **~5–6×**. Build is a **step** 0 → full
ceiling 7.163 GW. **No missing dual / no bug:** uranium nodal dual = 0 (not scarce); transport
congestion is real (FR→ES rent 168.4) but enters *correctly* via λ_ES (nuclear capacity is not
in the transport constraint); min_load = 0. The over-statement is **pure dual non-uniqueness at
an over-determined vertex**: both import lines at cap + no interior price-setter (λ_ES = 267.9 ≫
every generator's cost → price set by congestion) ⇒ λ_ES pinned only to an interval ⇒ ν inherits
it. Clean grabbed the optimistic end (2.26%); **op_B (perturbed) = 11.70% ≈ the sweep truth** =
the realistic end. Proof of non-uniqueness: 5× swing under a 1e-3 perturbation (a unique dual is
perturbation-invariant). The earlier "finite build crashes the price" intuition is **wrong** (λ
sticky, 267.9→251.2 for 7 GW) — the ambiguity is in the dual, not the price-quantity response.

---

## 3. Interim conclusions

1. **Prefer the clean operational RC.** It is the degeneracy-immune metric; the rhs perturbation
   is only needed to repair the *lifetime* dual and can slightly deflate the operational value.
2. **It is quantitatively exact** for **price-takers at well-connected nodes with unique marginal
   pricing** — validated across technology *types*, not just renewables (14/14 clean,
   perturbation-stable cases PASS).
3. **At degenerate nodes the RC is a provable lower bound** (over-states closeness for
   self-cannibalising baseload/flexible techs); the true distance is **not single-solve
   recoverable** — only finite bisection gives ground truth.
4. **Two reliability failure modes, asymmetric in detectability:**
   - *Scarcity-vertex degeneracy* → **detectable** via the clean-vs-perturbed **swing**
     (nuclear 9.4 pp, electrolysis 5.0 pp vs PV 0.4, wind 0.09).
   - *Constraint-pinning* (demand-fixed build) → **NOT** caught by the swing; needs a separate
     check on whether the reference-carrier balance / a min constraint binds.
5. **Net:** ~70–88 % of cases (price-takers, well-connected) are already reliable; the rest are
   flaggable, not silently wrong. The remaining work is **engineering a robust detector**, not
   unsolved theory.

---

## 4. Tests we should still run (prioritised)

**P1 — Reliability detector (the actual research gap, §5.2.6):**
- **Perturbation-swing classifier:** compute the clean-vs-pert swing for *all* buildable_rc
  cases, overlay the 17 validated PASS/FAIL labels, pick a threshold, report precision/recall.
  (We have the swing per case in runB/runC — this is a CSV job, no solve.)
- **Constraint-pinning detector:** flag cases whose reference-carrier nodal balance (or a
  min/limit constraint) binds so the build is quantity-fixed; test against coal_to_cement_fuel
  and scan how many buildable_rc cases are pinned. This is the *second* bucket the swing misses.

**P2 — Quantify the lower-bound gap (turn FAILs into numbers):**
- Bisect capex for nuclear@ES, electrolysis@FI (and 1–2 more degenerate techs) to the *true*
  break-even → report the exact underestimation factor (so far only bounds: nuclear >5×).

**P3 — Coverage gaps (validation is conversion-only so far):**
- **Storage bundle** ±1% in CB (battery power+energy) — the RC is a coupled bundle, never
  ±1%-tested at scale on CB.
- **Transport** ±1% in CB (lines) — memory says transport RC = curvature/aggregation, not
  degeneracy; confirm with a CB re-solve.
- **At-limit cases:** verify the "at-limit" flag is correct and RC is appropriately suppressed.
- **min_load / must-run tech:** one case with min_load>0 to confirm the omitted
  `minimum_full_load_hours` dual does not corrupt the RC when the tech is forced to run.

**P4 — Broaden the PASS evidence:**
- Finish the 7 remaining candidates from the stopped batch + sample more nodes/techs
  (target: a few PASS in every technology family for the report). NB the batch slowed badly
  late (15→42 min/solve); run in smaller chunks.

**P5 — Population census (also feeds §5.2.2):**
- Classify all runC cases into built / at-limit / buildable-reliable / flagged and report the
  shares — turns "70–88 %" into an exact CB number.

**P6 — Multi-period check:**
- CB here is a single-year snapshot; confirm the RC behaves identically in a multi-period CB
  slice (the showcase is multi-period and behaves well, but CB at scale is untested multi-year).
