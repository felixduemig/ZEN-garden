# Reduced Cost Export — Documentation

## Overview

ZEN-garden exports two types of reduced cost signals for `capacity_addition` via
`postprocess.py → save_capacity_addition_analysis()`. The results are written to:

```
<output_folder>/<dataset>/capacity_addition_analysis.csv
```

The economically meaningful column is **`rc_capex_equivalent_input_units`** (Euro/kW).
It answers: *"By how much would the capex of this technology need to decrease to make
it optimal to build?"*

---

## Output Columns

| Column | Unit | Source | When reliable |
|---|---|---|---|
| `value` | GW | LP solution | always |
| `reduced_cost` | model units | Gurobi `RC` attribute | Simplex only |
| `reduced_cost_input_units` | Euro/kW | Gurobi `RC` / `fraction_year` | Simplex only |
| `rc_capex_equivalent` | model units | dual of `constraint_technology_lifetime` | always |
| `rc_capex_equivalent_input_units` | Euro/kW | dual-based, back-converted | always |

---

## Approach 1 — Direct Gurobi RC (`reduced_cost_input_units`)

Gurobi exposes the reduced cost of every LP variable via the `RC` attribute, read in
`save_reduced_costs()`:

```python
arr = self.model.variables[name].get_solver_attribute("RC")
```

**Only valid with a vertex solution (Simplex).** With the Barrier method (`Method=2`)
and `Crossover=0`, Gurobi does not land on an LP vertex. The `RC` attribute then
returns the barrier perturbation term $\mu / x_j$ instead of the true LP reduced cost
— a numerically meaningless value for any variable near zero.

The column is populated only when:
```python
crossover_enabled = solver_options.get("Crossover", -1) != 0
```

Unit conversion:
```python
reduced_cost_input_units = reduced_cost / fraction_year
fraction_year = unaggregated_time_steps_per_year / total_hours_per_year
```

---

## Approach 2 — Dual-based RC (`rc_capex_equivalent_input_units`)

### Why duals instead of Gurobi RC

With `Method=2, Crossover=0` (Barrier, no crossover), the direct Gurobi RC is
unusable. The dual of `constraint_technology_lifetime` is available and exact for
both Simplex and Barrier (with only a small $\mu$-perturbation in the Barrier case).

### Mathematical derivation

`constraint_technology_lifetime` defines installed capacity from capacity additions:

$$S_{h,p,y} - \sum_{y' \in \mathcal{W}(y)} \Delta S_{h,p,y'} = S^\text{ex}_{h,p,y}$$

Its dual $\pi_y$ is the shadow price of capacity: the change in total system cost when
1 GW of capacity is made available for free in year $y$.

For a minimisation problem with valuable capacity: $\pi_y < 0$ (more capacity reduces
cost). For an unbuilt technology with no operational value: $\pi_y \approx 0$ or
positive (fixed OPEX effect).

The LP optimality condition for `capacity_addition[y_inv]` at its lower bound gives:

$$\text{RC} = \underbrace{c_h \cdot f_h \cdot \sum_{y \in \mathcal{Y}_\text{pay}} \delta_y}_{\text{investment cost in objective}} - \underbrace{\sum_{y \in \mathcal{Y}_\text{pay}} (-\pi_y)}_{\text{capacity value (elec\_value)}}$$

Dividing by `scaling` $= f_h \cdot \sum_{y} \delta_y$ to express in capex units:

$$\boxed{r_h^c = c_h - \frac{\displaystyle\sum_{y \in \mathcal{Y}_\text{pay}} (-\pi_y)}{f_h \cdot \displaystyle\sum_{y \in \mathcal{Y}_\text{pay}} \delta_y}}$$

where:
- $c_h$ = `capex_specific` as stored internally (= input capex × `fraction_year`)
- $f_h$ = annuity factor $= \dfrac{r(1+r)^{l_h}}{(1+r)^{l_h}-1}$
- $\delta_y$ = discount factor $= \dfrac{1}{(1+r)^y}$
- $\mathcal{Y}_\text{pay}$ = years in the depreciation window of investment year $y_\text{inv}$

Back-conversion to input units (Euro/kW):

$$r_h^{c,\text{input}} = r_h^c \;/\; \text{fraction\_year}$$

### Interpretation

| Value | Meaning |
|---|---|
| $r_h^{c,\text{input}} \approx 0$ | Technology is competitive, built at optimum |
| $r_h^{c,\text{input}} > 0$ | Capex must decrease by this amount to become optimal |
| $r_h^{c,\text{input}} >$ actual capex | Even at capex = 0 not competitive (fixed OPEX dominates or end-of-horizon effect) |

---

## Required ZEN-garden Settings

### Recommended: Primal Simplex

```json
"solver": {
    "name": "gurobi",
    "save_duals": true,
    "save_reduced_costs": true,
    "solver_options": {
        "Method": 0,
        "Presolve": 0
    }
}
```

- `Method=0` (Primal Simplex) or `Method=1` (Dual Simplex): lands on an LP vertex,
  both `reduced_cost_input_units` and `rc_capex_equivalent_input_units` are exact.
- `Presolve=0`: prevents Gurobi from eliminating variables before solving, which can
  suppress dual/RC output.
- No `Crossover` key needed — Simplex does not use it.
- No plugin (`mean_variance_optimization` must be removed): the RC is only meaningful
  for a pure LP.

### Alternative: Barrier + Crossover

```json
"solver_options": {
    "Method": 2,
    "Crossover": 1
}
```

Barrier finds the interior-point solution fast; crossover then projects it onto a
vertex. Produces exact RCs but can be slow or unstable on degenerate problems.

### Current default (Barrier, no crossover)

```json
"solver_options": {
    "Method": 2,
    "Crossover": 0
}
```

`reduced_cost_input_units` is `NaN` (intentionally). `rc_capex_equivalent_input_units`
is still computed from duals and is the only usable signal, with a small
$\mu$-perturbation error on near-optimal technologies.

---

## Reliability Summary

| Solver setting | `rc_capex_equiv_input_units` | `reduced_cost_input_units` |
|---|---|---|
| `Method=0` or `Method=1` (Simplex) | exact ✓ | exact ✓ |
| `Method=2, Crossover=1` | exact ✓ | exact ✓ |
| `Method=2, Crossover=0` (Barrier only) | small $\mu$-error | NaN ✗ |

### Known limitations (independent of solver method)

**End-of-horizon truncation:** For investments in later years, only the planning
periods within the model horizon count as pay years. A technology with a 24-year
lifetime invested in year 1 of a 3-year model sees only 2 pay years. The RC will be
larger than for the same investment in year 0. This is a model-structural effect, not
a numerical error.

**Near-optimal technologies (RC < ~30 Euro/kW):** The dual-based formula is
sensitive to small perturbations when the technology is close to its breakeven capex.
Treat such values as qualitative rather than quantitative.

---

## Entry Points

| Script | Purpose |
|---|---|
| `main_standard.py` | Barrier + no crossover. Only `rc_capex_equivalent_input_units` usable. |
| `main_lp_exact_rc.py` | Barrier + Crossover=1. Both columns exact, cross-check available. |
| `main_test_simplex_rc.py` | Primal and Dual Simplex. Both columns exact, fastest validation. |
