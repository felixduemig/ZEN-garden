# Technology RC Workflow

This guide summarizes the most relevant parameters for the technologies we discussed: PV, heat pumps, CHP, and gas pipelines. It focuses on which parameters are usually the strongest levers for reduced costs and investment decisions.

## General reading rule

The model minimizes discounted total system cost:

$$
J = \sum_y NPC_y
$$

with yearly cost decomposition

$$
C_y = CAPEX_y + OPEX_y^\mathrm{t} + OPEX_y^\mathrm{c} + OPEX_y^\mathrm{e}
$$

So a parameter matters if it changes one of these components, the feasibility set, or the coupling between technology build and system operation.

## PV

### Main parameters

| Parameter | Mathematical role | Expected effect |
| --- | --- | --- |
| `capex_specific_conversion` | $I_{i,n,y} = \alpha_{i,y} \Delta S_{i,n,y}$ | Direct CAPEX lever. Lowering it reduces annualized investment cost. |
| `opex_specific_fixed` | enters $OPEX_y^\mathrm{t}$ | Can prevent build if operating a PV-backed system becomes more expensive. |
| `opex_specific_variable` | enters $OPEX_y^\mathrm{t}$ | Usually weaker for PV, but still relevant when operation is nontrivial. |
| `max_load` | operational upper bound | Restricts use of installed capacity. If reduced, PV becomes less attractive. |
| `capacity_limit` | investment upper bound | Can block build even if costs are low. |
| `conversion_factor` | output per input relation | Improves or worsens effective energy yield and thus system value. |

### Practical interpretation

For PV, the first test is usually CAPEX. If PV still does not build after strong CAPEX reductions, the reason is often competition from other technologies or a system-level demand/dispatch constraint rather than PV CAPEX alone.

## Heat pump

### Main parameters

| Parameter | Mathematical role | Expected effect |
| --- | --- | --- |
| `capex_specific_conversion` | investment cost term | Direct lever, but often not the only bottleneck. |
| `conversion_factor` | heat output per electricity input | Very important. Higher COP reduces required electricity and OPEX. |
| `opex_specific_variable` | operating cost term | Strong influence when electricity input dominates total cost. |
| `max_load` / `min_load` | operating bounds | Can restrict flexibility and make HP less attractive. |
| `carbon_intensity_technology` | emissions term | Relevant if technology-specific emissions are modeled. |

### Practical interpretation

Heat pumps are often driven more by operating economics than by CAPEX alone. In RC terms, a lower CAPEX may still not trigger build if the electricity input cost or the conversion factor keeps total system cost high.

## CHP

### Main parameters

| Parameter | Mathematical role | Expected effect |
| --- | --- | --- |
| `capex_specific_conversion` | investment cost term | Direct but often not sufficient alone. |
| `conversion_factor` | joint heat/electricity production | Strong structural driver because CHP is a coupled output technology. |
| `opex_specific_variable` | operating cost term | Influences cost of dispatch strongly. |
| `input_carrier` / `output_carrier` | flow topology | Determines what the technology can consume and produce. |
| `max_load` / `min_load` | operating constraints | Can reduce dispatch flexibility and keep RC positive. |

### Practical interpretation

CHP is more structurally coupled than PV. The build decision is not just a CAPEX question, but also depends on whether the produced heat/electricity mix is valuable relative to alternative technologies. A high RC can persist even when CAPEX falls, if the coupled outputs do not fit the system well.

## Gas pipelines

### Main parameters

| Parameter | Mathematical role | Expected effect |
| --- | --- | --- |
| `capex_per_distance_transport` | $\alpha_{j,e,y} = \alpha^\mathrm{dist}_{j,e,y} h_{j,e}$ | Direct distance-dependent CAPEX lever. |
| `capex_specific_transport` | $\alpha_{j,e,y} = \alpha^\mathrm{const}_{j,y}$ | Fixed installation cost lever. |
| `transport_loss_factor_linear` | transport loss term | Higher losses worsen economic performance and can kill build. |
| `capacity_limit` | upper bound | Limits maximum pipeline use or build-out. |
| `max_load` | utilization bound | Restricts actual use of installed capacity. |

### Practical interpretation

For pipelines, the biggest question is often whether the edge itself is worth building. That is why the distance-dependent CAPEX and the fixed transport CAPEX are usually the first things to test. If one direction is built and the reverse is not, that is a strong sign that network topology, direction-specific flows, and system balance matter more than a simple symmetric cost reduction.

## Why CAPEX is not enough by itself

The reduced cost is locally influenced by both the objective coefficient and the active constraints:

$$
RC_j = c_j - A_j^T y
$$

This means:

1. CAPEX changes the direct coefficient $c_j$.
2. Efficiency, losses, and carrier conversion can change feasibility and operating cost.
3. Capacity and utilization limits can keep a variable nonbasic even when it becomes cheaper.
4. Competition with other technologies changes the shadow prices $y$ and therefore the RC.

## Recommended workflow

1. Start with the main CAPEX parameter for the technology.
2. If RC does not move enough, test the operating-cost parameter next.
3. Then test the key physical coupling parameter:
   - PV and CHP: `conversion_factor`
   - Heat pumps: `conversion_factor`
   - Pipelines: `transport_loss_factor_linear`
4. If the technology still does not build, inspect `max_load`, `capacity_limit`, and location-specific constraints.
