"""
RC Analysis â€” Primal Simplex (exact replication of outputs_20260506-124801)
===========================================================================
Runs the model as a pure LP with Primal Simplex (Method=0) and Presolve=0.

Primal Simplex lands on an LP vertex â†’ exact duals for all constraints.
Presolve=0 is critical: Gurobi's presolve eliminates constraints before solving,
which suppresses their dual variables in the output.

The duals of constraint_technology_lifetime are used to compute
rc_capex_equivalent_input_units [Euro/kW] â€” the capex reduction needed
for each technology to become optimal.

Output: <result_folder>/<dataset>/capacity_addition_analysis.csv
  value                           optimal capacity addition [GW]
  reduced_cost                    Gurobi RC attribute [model units]
  rc_capex_equivalent             dual-based RC [model units]
  rc_capex_equivalent_input_units dual-based RC [Euro/kW]  <- primary result
"""

import json
import os
from datetime import datetime

from zen_garden import run
from rc_capex_file_override import capex_file_override

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# Mean-Variance Optimization: set to None to disable, or to a lambda value to enable
MV_LAMBDA = None  # e.g., 1e-5

DATASETS = {
    "toy":    "5_multiple_time_steps_per_year",
    "toyplus":    "5_multiple_extended_countries",
    "full":   os.path.join("ZEN-models", "data", "Crystal_Ball"),
    "small":  os.path.join("ZEN-models", "data", "Crystal_Ball_small", "data", "Crystal_Ball"),
    "dechat":   os.path.join("ZEN-models", "data", "Crystal_Ball_DECHAT"),
    "extended": "5_multiple_extended",
    "extended_cb": "5_multiple_extended_cb",
    "extended_cb_v2": "5_multiple_extended_cb_v2",
    "capex_test":     "5_multiple_extended_cb_v2_capex_test",
    "cb_rc":          "6_cb_rc_model",
    "greenfield":     "7_cb_greenfield_2050",
}
DATASET = DATASETS["full"]

now = datetime.now().strftime("%Y%m%d-%H%M%S")
result_folder = f"./outputs_{now}/rc_analysis"
os.makedirs(result_folder, exist_ok=True)

with open("./config.json") as f:
    config = json.load(f)

config.pop("plugins", None)

# Add Mean-Variance plugin if enabled
if MV_LAMBDA is not None:
    config["plugins"] = {
        "mean_variance_optimization": {
            "weighting_factor": MV_LAMBDA,
            "include_variances_for": ["technology_capex"]
        }
    }

config.setdefault("solver", {})
config["solver"].setdefault("solver_options", {})

config["solver"]["name"] = "gurobi"
config["solver"]["save_duals"] = True
config["solver"]["save_reduced_costs"] = True
config["solver"]["solver_options"]["Method"] = 2 
config["solver"]["solver_options"]["Crossover"] = 1
config["solver"]["use_scaling"] = 0   
config["solver"]["solver_options"]["Presolve"] = 0
# +eps perturbation on capacity_addition to break dual degeneracy at unbuilt
# technologies (moves the lifetime dual to the economically correct endpoint).
# Popped before being passed to Gurobi. use_scaling=0 -> acts in raw objective
# units. Set to None to disable. Subtract eps from reported native reduced_cost.
config["solver"]["solver_options"]["rc_perturbation"] = 0
# +delta perturbation on the RHS of constraint_technology_lifetime (= a tiny
# phantom existing capacity). RHS perturbation: tilts the otherwise flat dual
# objective (capacity_existing * lambda = 0*lambda) so the lifetime dual is pinned
# to the economically correct "value" endpoint -> rc_capex_equivalent shows the
# true distance-to-build instead of a spurious 0 at unbuilt nodes. This is the
# correct knob for the single-node (primal) degeneracy; rc_perturbation (objective)
# cannot select within the dual interval. Units = capacity units (GW). Choose
# > solver feasibility tolerance (>> 1e-6) and smaller than the smallest positive
# capacity_limit. Popped before being passed to Gurobi. Set to 0/None to disable.
config["solver"]["solver_options"]["rc_lifetime_rhs_perturbation"] = 1e-4
# +yotta lower bound on capacity_addition of STORAGE POWER at unbuilt greenfield
# nodes. The energy_to_power_ratio_min constraint then forces a matching energy
# addition, so the storage RC reflects the joint (power+energy) distance-to-build
# (read it from the power row; the energy row is mechanically 0). Storage is
# excluded from rc_lifetime_rhs_perturbation. Path A (active): a FIXED ratio is set
# per storage tech (energy_to_power_ratio_min = ratio_max = D: battery 16h,
# pumped_hydro 22h, salt_cavern 145h) so rc_power is the unambiguous bundle distance
# at duration D. See docs/rc_storage_power_energy.md. Units = GW. Popped before
# Gurobi. 0/None = off.
config["solver"]["solver_options"]["rc_storage_power_perturbation"] = 0
# Tight (fixed) energy-to-power ratio per storage tech, set from HERE instead of
# hard-coded in the dataset (dataset stays at its loose default min=0/max=inf).
# Sets energy_to_power_ratio_min = ratio_max = duration[h] -> forces a fixed
# duration AND enables the storage-power perturbation above. {} or removal = off.
# Applied in optimization_setup.apply_parameter_overrides_for_rc() (popped before
# Gurobi). See docs/rc_storage_power_energy.md.
#config["solver"]["solver_options"]["rc_tight_e2p"] = {
#    "battery": 16,
#    "pumped_hydro": 22,
#    # "salt_cavern_storage": 145,  # (nur Crystal_Ball)
#}
# Per-(tech, node, year) capex override via the robust DATA-CSV swap
# (rc_capex_file_override.py): temporarily writes `value` into the technology's capex
# input CSV (the path the model reliably reads), runs, then restores the original
# byte-for-byte — even on error. RC is a per-node quantity, so this moves the reduced
# cost of a SINGLE node/year only. `value` is in the tech's NATIVE capex input units
# (Euro/kW for power, Euro/kWh for storage energy; for storage add
# "capacity_type": "power"|"energy"). Empty list = off. Applied around run() below.
RC_CAPEX_OVERRIDE = [
    #heat_pump,power,DE,0,conversion,gigawatt,0.0,0.001,inf,0.0,buildable_rc,3600.0,1.1728653757459426,107.02396553681726,0.02972887931578257,True
    #{"tech": "heat_pump", "node": "CH", "year": 2024, "value": 1511},
    #{"tech": "heat_pump", "node": "CH", "year": 2025, "value": 1510},
    #{"tech": "natural_gas_boiler", "node": "IT", "year": 2025, "value": 0}
    # oil_boiler,power,NL,0,conversion,gigawatt,0.0,0.0001,inf,0.0,buildable_rc,300.7725541250466,235.8794773299577,235.8794773299577,0.784245351162894,True
    # {"tech": "photovoltaics", "node": "DE", "year": 2024, "value": 180},
    # {"tech": "battery", "node": "CH", "year": 2050, "capacity_type": "power", "value": 70.0},
]
#heat_pump,power,ES,1,conversion,gigawatt,0.0,0.0,inf,0.0,buildable_rc,3600.0,22.926446529021725,2092.038245773232,0.5811217349370089,True
#natural_gas_boiler,power,IT,2,conversion,gigawatt,0.0,155.2280712103449,inf,-1.0,buildable_rc,876.0,21.648343226653935,1975.4113194321715,2.2550357527764513,True

#reservoir_hydro,power,CZ,0,conversion,gigawatt,0.0,0.0,0.711483902285,0.0,buildable_rc,2523.2837795151254,326.23623119297235,326.23623119297235,0.12929034531964612,True
#config["solver"]["solver_options"].pop("Crossover", None)
#config["solver"]["solver_options"].pop("BarHomogeneous", None)
config["solver"]["solver_options"]["LogFile"] = os.path.join(result_folder, "solver.log")

tmp_config = "./config_rc_tmp.json"
with open(tmp_config, "w") as f:
    json.dump(config, f, indent=4)

print(f"Running RC analysis (Primal Simplex, Presolve=0) -> {result_folder}")
with capex_file_override(os.path.abspath(DATASET), RC_CAPEX_OVERRIDE):
    run(config=tmp_config, dataset=DATASET, folder_output=result_folder)
os.remove(tmp_config)

csv = os.path.join(result_folder, DATASET, "capacity_addition_analysis.csv")
print(f"\nDone. Results -> {csv}")
print("Primary column: rc_capex_equivalent_input_units [Euro/kW]")



