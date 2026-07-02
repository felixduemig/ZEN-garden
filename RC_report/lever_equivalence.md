# Equivalent cost levers: re-expressing the reduced cost across a technology's inputs

*Derivation for the thesis (Methodology/Appendix + Showcase §5.1). Term: we call this
**lever equivalence** / **equivalent cost levers** — NOT "conversion" (collides with conversion
technologies). The build margin is one scalar; the reduced cost can be **allocated** across a
technology's cost/performance inputs, exactly as the storage power+energy bundle splits freely.*

---

## 1. General technology

Per unit of capacity (one kW), annualised, for a single (technology, node, year). Inputs:
`c` capex [EUR/kW], `f` fixed opex [EUR/kW·yr], `v` variable opex [EUR/MWh], availability
profile `m_t` (max_load), and the operational dual `ν_t` of the capacity-factor constraint
`m_t S ≥ G` (the duration-weighted per-step operating margin the capacity earns).

- **Annual cost:**  `K = CRF·c + f`   (CRF = capital recovery factor)
- **Annual gross operating value:**  `V = Σ_t m_t ν_t`
   with `ν_t = ( λ^ref_t·η − Σ_in α_in λ^in_t − v )^+ · w_t`  (price × efficiency − input costs
   − variable cost, weighted by the hours `w_t` the typical step represents; `(·)^+` because the
   technology only runs when the margin is positive).
- **Build margin (gap):**  `G = K − V = CRF·c + f − Σ_t m_t ν_t`. The first unit builds iff `G ≤ 0`.
- **Capex-equivalent reduced cost:**  `RC = G / CRF`  (the break-even capex is `c − RC`).

**Lever equivalence.** `G` is a single scalar. To **first order** — the same ceteris-paribus
assumption that makes the reduced cost valid (prices `λ`, hence `ν_t`, held fixed) — closing the
gap by any input has exchange rate `∂G/∂(input)`:

| Lever | `∂G/∂(·)` | single-lever change to reach the build margin |
|---|---|---|
| capex `c` | `CRF` | `Δc = −G/CRF = −RC` |
| fixed opex `f` | `1` | `Δf = −G = −CRF·RC` |
| variable opex `v` | `+E` | `Δv = −G/E`,  `E = Σ_{t:run} m_t w_t` = annual generation per kW |
| capacity factor (uniform `m_t→(1+ε)m_t`) | `−V` | `ε = G/V` (relative) |
| capacity factor (shape `Δm_t`) | `−ν_t` per step | `Σ_t ν_t Δm_t = G` (put yield where `ν_t` is high) |

**Canonical allocation.** Any combination of input changes that satisfies the *one* linear
equation
```
   CRF·Δc + Δf + E·Δv − Σ_t ν_t Δm_t  =  −G
```
reaches the build margin — a whole **indifference hyperplane** of equivalent cuts. The reduced
cost is just the capex coordinate; it can be re-allocated freely onto fixed opex, variable opex,
or capacity factor via the table. (This is the generic version of the storage bundle's free
split already reported in §5.1: there it was a line in (capex_power, capex_energy); here it is a
hyperplane over all cost drivers.) Every quantity needed — `V = Σ m_t ν_t`, `E = Σ m_t w_t`, CRF
— is already produced by the operational reconstruction, so the distance to build can be reported
as a **menu of equivalent levers at no extra solve**.

**Which levers are *meaningful* is technology-specific** (next two sections): a lever is only
useful where the technology actually carries that cost/performance margin.

---

## 2. Photovoltaics — capex-heavy, non-constant CF, ~zero variable cost

Profile: large `c`, small `f`, `v ≈ 0` (no fuel), `m_t` = irradiation profile (peak midday,
zero at night) — **non-constant**. Then `ν_t = λ^el_t · w_t` (PV just earns the electricity
price in sunlit hours), and `V = Σ_t m_t λ^el_t w_t`.

- **capex** (base): `Δc = −RC`.
- **fixed opex**: `Δf = −G = −CRF·RC`.
- **capacity factor** (uniform): `ε = G/V` relative increase in yield/availability. Hour-resolved
  shape: a `Δm_t` placed in the **highest-price** sunlit hours is most efficient (`Σ ν_t Δm_t`),
  so the lever also tells you *when* extra PV yield is worth most.
- **variable opex**: **degenerate** — `v ≈ 0`, nothing to reduce. PV's value does not live in
  variable cost, so this lever is empty.

PV's natural alternative lever is therefore the **capacity factor**.

**Two variants to validate (±1%):**
1. **capex ↔ CF.** Predict `ε = G/V`; build run scales `m_t` by `(1+1.01·ε)`, no-build by
   `(1+0.99·ε)`, holding capex fixed; the technology must build / not build.
2. **capex ↔ fixed opex.** Predict `Δf = −G`; override fixed opex to `f − 1.01·G` (build) and
   `f − 0.99·G` (no-build).

---

## 3. Gas turbine — variable-cost-heavy (fuel), dispatchable, ~full availability

Profile: small `c`, moderate `f`, **large `v`** (fuel), `m_t ≈ 1` (dispatchable, available every
hour) but it only *runs* when `λ^el_t > v` (peak hours). Then `ν_t = (λ^el_t − v)^+ w_t` and
`V = Σ_t (λ^el_t − v)^+ w_t`; `E = Σ_{t:run} m_t w_t` is **small** (few running hours).

- **capex** (base): `Δc = −RC`.
- **variable opex / fuel**: `Δv = −G/E`. Because `E` is small, a given EUR/MWh fuel reduction
  moves the margin only a little, so the required `Δv` is comparatively large — the lever reflects
  that a peaker's economics hinge on fuel price in its few running hours.
- **fixed opex**: `Δf = −G`.
- **capacity factor / availability**: **degenerate** — `m_t ≈ 1` already; the turbine's *low
  utilisation* is a dispatch outcome, not an availability limit, so raising `m_t` does nothing.

The gas turbine's natural alternative lever is therefore the **variable (fuel) cost**.

**Two variants to validate (±1%):**
1. **capex ↔ variable opex.** Predict `Δv = −G/E`; override variable opex (or the fuel price) to
   `v − 1.01·G/E` (build) / `v − 0.99·G/E` (no-build).
2. **capex ↔ fixed opex.** Predict `Δf = −G`.

---

## 4. The punchline

PV and the gas turbine have **complementary** natural levers — PV's margin lives in
yield/availability (CF lever; variable-cost lever empty), the gas turbine's in fuel
(variable-cost lever; CF lever empty). The capex-equivalent reduced cost is the **common
currency**; the exchange rates translate it into whichever lever a technology actually carries.
The canonical allocation (the indifference hyperplane) is universal; *which coordinate is
meaningful* is set by the technology's cost structure.

**Limits (state honestly):** first order only — breaks under self-cannibalisation (a finite CF or
capacity change moves `λ`, hence `ν_t`); the CF lever depends on the assumed *shape* of the
change; **cross-technology levers (e.g. a carbon price) are NOT a ceteris-paribus exchange** —
they shift the prices `ν_t` themselves and require a re-solve.

---

## 4a. Empirical validation on the showcase (2026-06-23)

Re-solves via `RC_report/validate_levers*.py` (PV@DE, GT@FR), per-node overrides.

- **PV fixed opex — PASS (clean).** Predicted `Δf = af·RC = -6.24` EUR/kW·yr; PV builds 0.042 GW
  at `-1.01·Δf` and nothing at `-0.99·Δf`. The **volume-neutral lever is an exact equivalence** —
  the core proof that the reduced cost re-allocates canonically.
- **PV capacity factor — first order, mildly optimistic.** Predicted `ε = +15.09%`. A CF sweep
  builds 0 at +15%, **0.64 GW at +18%**, 1.96 at +21%, 16.3 at +25%; the true break-even is
  *above* the predicted point (the +15.24% build point built 0). The CF lever makes the unit more
  valuable per kW, drives a *larger* build, and self-cannibalises more than the volume-neutral
  lever — the same marginal-versus-finite gap, now in the lever context. Value-side levers (CF,
  variable opex) inherit it; the fixed-opex lever does not.
- **Gas turbine (fixed + variable opex) — FAIL, because it is a knife-edge price-setter.** GT@FR
  builds only ~0.002 GW even at its *capex* reduced cost (report validation table) and sets the
  price it earns; both levers tip it just below build (exactly 0). The levers **inherit the
  reliability of the underlying capex reduced cost** — they do not repair a knife-edge case.

- **Heat pump COP — derive the COP needed to build (value-side, first order).** A heat pump given
  a bad COP of 1.25 (`RC_report/hp_cop_phase*.py`) is unbuilt at DE (operational RC 6.84 EUR/kW).
  The COP lever `1/COP_1 = 1/COP_0 - scaling·RC/W` (with `W = Σ_{run} m_t λ^{el}_t`, read from the
  duals) predicts the heat pump needs **COP 1.27** to build. A COP sweep confirms it builds from
  **COP ≈ 1.32** (0 at 1.30, 1.6 GW at 1.33) — the prediction is ~4\% optimistic, again the
  marginal-versus-finite gap (the COP improvement triggers a sizeable 1.6 GW build that depresses
  the heat price). So **the reduced cost does answer ``to what COP must it rise to build''**, as a
  first-order estimate. (Bonus: at high COP the per-node build allocation is degenerate -- DE flips
  to 0 while FR absorbs more -- the heat pump's known spread degeneracy.)

**Takeaway:** the volume-neutral lever (fixed opex) is an *exact* equivalence; value-side levers
(CF, variable opex / COP) are *first-order* estimates carrying the same marginal-versus-finite
caveat (shown twice: PV-CF and heat-pump-COP); every lever is only as reliable as the capex
reduced cost it derives from.

---

## 5. Validation plan (showcase, fast re-solves)

Probes already in `6_showcase_countries`: base `photovoltaics` + clones `photovoltaics_opex`
(2× fixed opex) and `photovoltaics_lowcf` (½ CF) isolate the drivers; `natural_gas_turbine`
carries the fuel cost. Procedure per variant: (i) one base solve → read `V, E, CRF, G` from the
operational reconstruction; (ii) compute the predicted lever change; (iii) override that lever's
input CSV/attribute to the ±1% points and re-solve; (iv) check build/no-build. Needs the override
harness (`rc_capex_file_override.py`) extended from capex to `max_load` / `opex_specific_fixed` /
`opex_specific_variable`.
