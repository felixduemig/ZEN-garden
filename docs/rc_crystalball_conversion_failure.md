# Why the operational reduced-cost reconstruction UNDER-states the distance-to-build for some Crystal-Ball conversion techs

*Root-cause investigation, 2026-06-23. Data: `outputs_CB_overnight/{runA,runB,runC}` (CB
snapshot, 28 nodes, 1 year, 10 typical hours, pure LP, Gurobi barrier+crossover) and the
clean ground-truth re-solves in `outputs_CB_overnight/validate_*`. Reproduction scripts:
`_rc_analysis/a1..a10_*.py`, `_rc_analysis/toy_lp3.py`. No new CB runs were launched.*

---

## 0. Verdict (TL;DR)

- **It is not an arithmetic, carrier, or completeness bug.** Leads 1 (carrier/conversion
  handling), 2 (a missing value-bearing capacity constraint) and 3 (weighting/scaling) are
  each falsified against the saved duals below. The reconstruction is a *faithful*
  evaluation of capacity value at the no-build dispatch prices — `ν` is reproduced to
  machine precision from the nodal prices `λ`, including the hydrogen reference carrier of
  electrolysis, and the reported RC is reproduced exactly from `Σ mₜ·νₜ / scaling`.
- **The failure is a property of the LP, not the code: a degenerate ("scarcity") no-build
  vertex where the dispatch price the technology is valued at is the *demand-relief* price,
  while a finite build of a new *supply* technology only realizes the much lower
  *supply-displacement* value.** The reconstructed RC is a first-order (marginal) quantity
  read at this knife-edge; the true build threshold is a finite-step quantity. They differ
  by the self-cannibalization the first finite build triggers, which is **invisible to any
  single solve**. This is leads **4 (reported dual ≠ right-derivative) and 5
  (marginal-vs-finite)**, which are two faces of the same kink in the cost-vs-capacity
  function.
- **The prior "marginal-vs-finite" intuition is CONFIRMED, and now has a rigorous KKT /
  LP-sensitivity backing and a minimal counterexample** (`toy_lp3.py`): a 6-variable LP in
  which the reconstructed break-even is provably 9× the true one and the LP builds *exactly
  zero* just below the reconstructed break-even — reproducing the CB validation FAIL.
- **Verdict on fixability: the signal is intrinsically unrecoverable from a single solve for
  these techs.** Every single-solve dual estimate is an *upper bound* on the realized value
  (⇒ a *lower bound* on the distance), because cost-vs-capacity is convex and the duals see
  only the steepest (no-build) slope. A correction formula cannot exist; the honest fix is a
  **degeneracy/unreliability flag** (perturbation-sensitivity, which the multi-run setup
  already exposes) plus a **finite bisection re-solve** for flagged techs. Concrete flag +
  code in §7.

---

## 1. The magnitude of the over-statement (with the saved numbers)

`capacity_addition_analysis_conversion.csv`, four diagnostic techs, all `value = 0`
(unbuilt), `case = buildable_rc`, `rc_reliable = True`. RC in €/kW; ratio = RC/capex.
In run C, lifetime-RC == operational-RC for both failing techs (no capacity-variable leak —
see §3), so this is **not** the degeneracy the operational column was built to remove.

| tech | node | capex €/kW | RC_clean (run C) | RC_pert (run B) | ground-truth ±1% | **true RC (lower bound)** | clean over-statement |
|---|---|---:|---:|---:|---|---:|---:|
| **nuclear** | ES | 5578.7 | 125.99 (**2.26 %**) | 652.54 (11.70 %) | builds 0 even at run B → **FAIL** | **> 659 €/kW (> 11.81 %)** | **> 533 €/kW (> 9.5 % of capex)** |
| **electrolysis** | FI | 576.4 | 56.13 (**9.74 %**) | 85.14 (14.77 %) | builds 0 even at run B → **FAIL** | **> 86 €/kW (> 14.92 %)** | **> 30 €/kW (> 5.2 % of capex)** |
| photovoltaics | CZ | 317.0 | 15.06 (4.75 %) | 13.86 (4.37 %) | builds at 4.75 % → **PASS (clean)** | ≈ 14 €/kW (4.4 %) | ≈ 0 |
| wind_offshore | FR | 1926.3 | 215.39 (11.18 %) | 213.61 (11.09 %) | builds at 11.1 % → **PASS** | ≈ 216 €/kW (11.2 %) | ≈ 0 |

The true-RC lower bound is the hard fact on disk: at the run-B override
capex = capex·(1 − 1.01·ratio) — **4919.6 €/kW** for nuclear, **490.4 €/kW** for
electrolysis — the clean re-solve builds **0** (`validate_20260623-011718/c06`, `…/c04`,
`built=0.0000`). So the true break-even capex is below those, i.e. the true RC exceeds them.
The validation gives only a one-sided bracket (a tighter upper end would need a deeper
bisection, which is intentionally not on disk); it already proves the reconstruction is
confidently wrong — it reports nuclear as **2.26 % from economic when it is at least 11.8 %
away**.

**Direction is uniform:** every reconstruction (lifetime or operational, clean or perturbed)
**understates the distance / over-states the value**. The clean run C is the *worst*
over-statement, so the perturbation is not the cause (it moves the value *toward* truth).

---

## 2. Leads 1–3 are falsified (pure data checks)

### Lead 3 — arithmetic / weighting / scaling: **CORRECT** (`a3_repro2.py`)
The native cap-factor dual is stored at the **10 typical operational steps** (20720 = 2072
(tech,node) × 10) and `Results.get_dual` expands it to 8760. The reconstruction sums over
the **native 10 steps without an extra duration weight**, because the per-typical-step dual
already embeds its cluster duration (the energy-cost objective is duration-weighted, so the
Gurobi dual of the per-step constraint is the *annual* marginal value). Reproducing the
reported operational ratio from the saved native duals:

```
RC_op_ratio = 1 − (Σₜ mₜ·νₜ − opex_fixed·δ) / (af·δ · capex)
```

matches the CSV **exactly** for all four techs (e.g. nuclear ES: V = 391.51, ratio
+0.02258 vs reported 0.022584). Re-introducing an explicit duration weight gives nonsense
(ratio ≈ −1627). ⇒ **No weighting/scaling/fixed-opex bug.**

### Lead 1 — carrier / reference-carrier handling: **CORRECT** (`a4_nu_from_lambda.py`)
Independently reconstructing `ν` from the nodal-balance prices `λ`:

```
νₜ = max(0, λ_ref,node,t − Σ_in α_in·λ_in,node,t − durₜ·var_opex)
```

reproduces the saved cap-factor dual **to machine precision (max |Δ| = 0.0)** for all four,
including **electrolysis** (`ref = hydrogen`, input electricity, α = 1.901):
`νₜ = max(0, λ_H2 − 1.901·λ_elec − dur·var)`. The hydrogen-side value and the
electricity-input cost are netted correctly. ⇒ **No carrier/conversion-factor mismatch.**

### Lead 2 — completeness (a second value-bearing capacity constraint): **NONE binds**
- The model is a **pure LP**: no on/off binaries, no `constraint_technology_on_off`, no
  reserve/firm-capacity/capacity-market constraints exist (`a-checks`; var_dict has no
  binary vars). ⇒ the **min-load / must-run factor is absent**.
- `constraint_technology_capacity_limit_not_reached` dual = **0** for nuclear ES
  (capacity 0 ≪ ceiling 7.163), `…_reached` has no row. The capacity-limit is **slack**, so
  it carries no value. (Electrolysis ceiling is `inf`.) PV and wind also have finite
  ceilings and **pass**, so a binding limit is not the splitter anyway.
- `constraint_technology_lifetime` dual μ = −292.6 (nuclear) equals the operational net
  value 292.8 → **no capacity-variable leak** (`c̄(capacity) = 0`); lifetime-RC ==
  operational-RC in run C. The completeness theorem holds; the operational reconstruction
  loses no real factor.

⇒ Leads 1–3 closed. The reconstruction is correct **given the prices**; the prices are the
problem.

---

## 3. The mechanism (KKT / LP-sensitivity), pinpointed

### 3.1 The dispatch is at a degenerate "scarcity" vertex
At nuclear's dominant value step (ES, step 0, contributing 260 of the 391 total `Σ mₜ·νₜ`),
the saved dispatch (`a7_scarcity.py`) is:

```
ES electricity, step 0 (price λ = 0.179 €/kWh, shed = 0, imports = 0, FR→ES line cap = 0):
  wind_onshore  13.17  (mc 0.0006)  at_cap=True
  reservoir_hyd  6.61  (mc 0.0014)  at_cap=True
  photovoltaics  2.54  (mc 0.0000)  at_cap=True
  biomass_plant  2.14  (mc 0.2294)  at_cap=True
  run-of-river   0.84  (mc 0.0020)  at_cap=True
  natural_gas    0.53  (mc 0.1296)  at_cap=True     ← all six AT availability cap
```

**Every local generator is at its availability cap, the import lines are at their limit, and
demand is met with zero shedding.** The number of binding constraints exceeds what pins a
unique price: this is a primal-degenerate vertex. The reported price **0.179 equals no
running unit's marginal cost** (it sits between NGT 0.130 and biomass 0.229) — it is a
**scarcity / congestion rent**, the value of relaxing *demand*, not the cost of a marginal
generator with slack.

### 3.2 Why a finite build realizes less than the reported price (the KKT argument)
Write the optimal dispatch cost as a function of the candidate's capacity `x`:
`C(x) = annuity(capex)·x + D(x)`, where `D(x)` is the optimal dispatch cost given `x` units
available. `D` is **convex and decreasing** (more cheap firm capacity never hurts), so its
right-derivative `D′(0⁺)` is the *largest* (least negative) slope:

- The operational reconstruction sets the capacity value to `−D′` evaluated with the saved
  no-build dual `λ = 0.179` — the **demand-relief** value (left/steepest slope, `p_hi`).
- A finite build of *supply* displaces the **cheapest curtailable running resources**, so it
  realizes the **supply-displacement** value (`p_lo`), which at this vertex is strictly
  smaller. The optimal dual is **non-unique on `[p_lo, p_hi]`**; the reconstruction reads
  `p_hi`, the build realizes `p_lo`.

Because `D` is convex, **every single-solve dual is `≥` the average value over `[0, x*]`**,
so the reconstruction is an upper bound on the realizable value and the reported RC is a
*lower bound* on the true distance — exactly the observed one-sided failure. The gap is the
**self-cannibalization**: as `x` grows, the candidate floods its own value hours and the
price collapses toward `p_lo` (and below). The LP therefore builds **exactly 0** just below
the reconstructed break-even (not an ε) because the *first* infinitesimal unit already lives
on the lower branch of the kink.

### 3.3 The same mechanism, two carrier sides
- **nuclear ES — output-side scarcity.** Sells electricity into an import-islanded, fully
  saturated node; its value is the scarcity rent (0.179, 2.4× the ~0.07 continental price,
  above its own NGT's cost). Building it directly relieves the scarcity → price collapses to
  the cheap displaced stack (wind/hydro/PV ≈ 0, NGT 0.13). 67 % of its value is in this one
  knife-edge step.
- **electrolysis FI — input-side surplus** (`a10_fingerprint.py`). A flexible *load*: margin
  `= λ_H2 − 1.901·λ_elec`. Its value is concentrated in step 8 where `λ_elec = 0.0014`
  (essentially **free, curtailment-regime electricity** — the degenerate `λ≈0` case) and
  `λ_H2 = 0.069`, margin +0.067. Building it bids up FI's near-free electricity → `λ_elec`
  rises → the margin collapses (and the extra H₂ depresses `λ_H2`). Self-cannibalization on
  the *input*. Same kink, mirror image.

### 3.4 Why PV and wind PASS
PV/wind are **variable price-takers**. At the tested cut the LP builds a *small* amount (PV
0.32 GW, wind 10.6 GW) in deep markets, so the value function is locally linear over the
triggered build → marginal ≈ finite → the RC is exact. (They *also* sit at saturated
vertices — "all-at-cap" is common with 10 typical hours — but their triggered build is too
small to move the price.) The decisive difference is **build-size / cannibalization depth**,
not the vertex type: nuclear is a *price-maker* (a ~6 GW baseload entrant into a thin
islanded node), PV/wind are price-takers.

### 3.5 Degeneracy fingerprint (the practical discriminator)
The reconstruction's perturbation-sensitivity cleanly separates the two classes
(`|RC_runB − RC_runC|`, in percentage points of capex):

| tech | clean→pert swing | reliable? |
|---|---:|---|
| nuclear ES | **9.44 pp** | NO (degenerate) |
| electrolysis FI | **5.03 pp** | NO (degenerate) |
| photovoltaics CZ | 0.38 pp | yes |
| wind_offshore FR | 0.09 pp | yes |

A robust dual is perturbation-invariant; nuclear/electrolysis swing by 5–9 pp because their
value rides on the degenerate branch (and because nuclear sits at a knife-edge — its net
margin is only 6.8 of a 392 gross value, so a 7 % dual wobble becomes a 9 pp RC swing).

---

## 4. The minimal counterexample (`_rc_analysis/toy_lp3.py`, sub-second scipy LP)

1 node, 2 identical hours. Demand 100 each. Incumbents: **G1** cap 100 cost 10 (cheap),
**G2** cap 100 cost 50 (peaker). Candidate **C**: baseload cost 5, invest cost `I`.

```
NO-BUILD: g1 = 100,100 (at cap)   g2 = 0,0 (idle)   → DEGENERATE vertex
price λ is NON-UNIQUE on [10, 50]:
   demand+ε → λ = 50  (G2 cost = DEMAND-RELIEF value, the dual the scarcity solve reports)
   demand−ε → λ = 10  (G1 cost = SUPPLY-DISPLACEMENT value, the right derivative)

operational RC reads λ = 50 → reconstructed break-even I* = 2·(50−5) = 90
TRUE break-even (finite re-solve / bisection)        =  10   (C displaces cheap G1, not idle G2)
                                              OVER-STATEMENT = 9×
At I = 89 (just below the reconstruction): built capacity = 0.0000  → NO BUILD  (= CB FAIL)
```

This reproduces every qualitative feature of the CB failure: a degenerate no-build vertex, a
price interval, a reconstruction that reads the high (demand-relief) end, a true value at the
low (supply-displacement) end, and a **build of exactly zero** below the reconstructed
break-even. It also shows the over-statement is *not* a solver artifact one can perturb away:
when the scarcity structure robustly pins the high end (as ES does across runs A/B/C — the
ES step-0 price is **0.17916 / 0.17915 / 0.17920**, perturbation-invariant), no RHS
perturbation moves the dominant term, so even run B under-shoots.

---

## 5. Confirm / refute the prior "marginal-vs-finite" claim

**CONFIRMED in substance, sharpened in mechanism.** The prior wording ("finite builds move
prices") was incomplete: a *smooth* price slope would still let the LP build an ε and pass
the ±1 % build test. The observed behaviour is a **build of exactly 0**, which requires a
**kink** (discontinuous derivative) at `x = 0`, i.e. a *degenerate* no-build vertex where the
price-setting resource is at zero quantity / the node is saturated. So the precise statement
is:

> The reconstructed RC is the marginal value of the first unit evaluated on the **upper
> branch** of a kink in cost-vs-capacity (the demand-relief dual at a degenerate scarcity
> vertex). The build threshold is the finite-step value on the **lower branch**
> (supply-displacement, then walking down the residual supply curve). They differ by the
> self-cannibalization width of the kink, which is large for high-capacity-factor /
> price-making entrants (nuclear baseload, electrolysis flexible load) and ≈ 0 for
> small-build price-takers (PV, wind).

Lead 4 (reported dual ≠ right-derivative) and lead 5 (marginal vs finite) are the
dual/primal views of this one kink. Ranked by contribution: the **finite-step concavity is
the whole gap**; the no-build dual degeneracy is its infinitesimal-scale signature (and the
reason the build is 0 rather than ε).

---

## 6. Is it fixable? — proof that it is **not**, from a single solve

Let `V(x) = −D(x)` be the (concave, increasing) realizable value of `x` units. The true
break-even capex solves `annuity·capex* = V(x*)/x*`, i.e. it depends on the **average** value
over `[0, x*]`. A single solve yields only duals at `x = 0`, which give `V′(0⁺)` (at best the
right-derivative; the reconstruction in fact reads `V′(0⁻) ≥ V′(0⁺)`). By concavity
`V′(0⁺) ≥ V(x*)/x*` for all `x* > 0`, with **strict** inequality whenever the value function
is curved over `[0, x*]` — which is exactly the self-cannibalizing case. Therefore:

> **Any single-solve reduced-cost reconstruction over-states the realizable value (⇒
> under-states the distance) whenever the technology's finite entry moves its own carrier
> prices, and the size of the error (the integral of the concavity over `[0, x*]`) is not a
> function of the `x = 0` duals.** No re-weighting of `x = 0` duals can recover it.

Even the *exact right-derivative* `V′(0⁺)` (the best a single solve could give, obtained by a
second lexicographic dual solve) would only tighten the upper bound, not reach `V(x*)/x*`.
⇒ **A correction formula is impossible; the finite re-solve (bisection) is the only
degeneracy-immune truth.** The minimal counterexample in §4 is the witness.

---

## 7. The honest fix: detect-and-abstain, then bisect

Since no single-solve correction exists, the deliverable is a **reliability flag** that marks
these RCs as *lower bounds on the distance* (not point estimates), and routes them to a
bisection re-solve. Two complementary signals, both already computable:

**(a) Perturbation-sensitivity flag (robust, needs the 2 solves the harness already does).**
Mark a conversion RC `rc_unreliable_degenerate` when it moves by more than a tolerance
between the clean and the RHS-perturbed solve:

```python
# post-hoc across runC (clean) and runB (rhs-perturbed) conversion CSVs
RC_DEGEN_TOL = 0.01            # 1 pp of capex
merged = clean.merge(pert, on=["set_technologies","set_location"], suffixes=("_c","_p"))
swing = (merged["ratio_reduction_operational_p"] - merged["ratio_reduction_operational_c"]).abs()
merged["rc_unreliable_degenerate"] = swing > RC_DEGEN_TOL   # nuclear 0.094, electro 0.050 → True
                                                            # PV 0.004, wind 0.001          → False
```

This separates the four cases cleanly (§3.5). The reported RC (and especially the smaller of
clean/perturbed) is then to be read as **"distance ≥ this"**, and the true value obtained by
bisection on the override capex.

**(b) Single-solve scarcity-concentration heuristic (a cheaper pre-filter).** Flag when a
large share of `Σ mₜ·νₜ` comes from hours where the reference-carrier node is *saturated*
(all local suppliers of that carrier at their availability cap **and** net import headroom ≈
0, i.e. an islanded/congested scarcity vertex), or, for input-consuming techs, where the
input price is in the near-zero surplus regime. This is a necessary condition for the kink;
it over-flags (PV's saturated hours are harmless) so it must be combined with a build-size
test, hence (a) is preferred as the operative flag.

**Recommended code change** in `save_capacity_addition_classified`
(`postprocess.py:1446`): add a column `rc_is_lower_bound` (default `False`) and, when the
perturbation pair is available, set it from signal (a); annotate `rc_reliable` docs to state
that for `buildable_rc` conversion rows with `rc_is_lower_bound = True` the RC is a **lower
bound on the capex cut**, to be confirmed by `rc_capex_file_override.py` bisection. No change
to `_compute_rc_capex_equivalent` is warranted — it is arithmetically correct; the limitation
is informational, not a bug.

**Cross-check against ground truth:** the flag (a) marks exactly the two techs whose ±1 %
test FAILS (nuclear, electrolysis) and clears the two that PASS (PV, wind). For the cleared
techs the operational RC matches the validation threshold (PV clean 4.75 % builds, wind
11.18 % builds). For the flagged techs the bisected truth (> 11.8 %, > 14.9 %) confirms the
reconstruction was a lower bound, as the flag asserts.

---

## 8. Reproduction artifacts

| script | purpose |
|---|---|
| `_rc_analysis/a3_repro2.py` | reproduces reported RC exactly from native duals (lead 3) |
| `_rc_analysis/a4_nu_from_lambda.py` | `ν` from nodal prices `λ`, machine-precision (lead 1) |
| `_rc_analysis/a7_scarcity.py` | the saturated ES step-0 vertex (all 6 at cap, shed 0) |
| `_rc_analysis/a6_congestion.py` | ES import congestion (FR→ES cap 0, PT→ES at limit) |
| `_rc_analysis/a8_run_compare.py`, `a9_*`, fingerprint `a10_*` | cross-run / scarcity diagnostics |
| `_rc_analysis/toy_lp3.py` | **the minimal counterexample (9× over-statement, build = 0)** |

Saved CB outputs: `outputs_CB_overnight/{runA,runB,runC}/Crystal_Ball`; ground truth:
`outputs_CB_overnight/validate_20260623-011718` (c03–c06) and `…-080711` (PV clean).
