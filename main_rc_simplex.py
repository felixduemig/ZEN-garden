"""
RC Analysis — manual runner (Barrier + Presolve 0, dual reconstruction)
=======================================================================
Run a model as a pure LP and reconstruct the reduced cost (RC) of every
capacity_addition — i.e. "how much CAPEX reduction would make this technology
build?". Configured here for the validated **showcase** model `6_showcase_countries`,
but the Crystal_Ball / toy datasets still work (switch DATASET below).

Why these solver settings (do not change for RC work):
  * Method = 2 (Barrier) + Crossover = 1 -> lands on an LP vertex with clean duals;
    the operational reconstruction is correct for any method, lifetime only here.
  * Presolve = 0 -> Gurobi's presolve eliminates the coupled lifetime/capex
    constraints and returns a different (collapsed) dual; off keeps the duals we read.
  * use_scaling = 0 -> duals come back in raw objective units (no row/col rescaling).

Two RC columns are written side by side in capacity_addition_analysis.csv:
  rc_capex_equivalent[_input_units]              legacy, from the lifetime dual μ
  rc_capex_equivalent_operational[_input_units]  robust, from the capacity-factor dual
The operational column is the primary, degeneracy-robust result (conversion only;
storage/transport use the lifetime/bundle metric). See docs/rc_operational_reconstruction.md.

Output: ./outputs_<timestamp>/rc_analysis/<dataset>/  (classified CSVs + heatmaps/)
"""

import json
import os
from datetime import datetime

from zen_garden import run
from rc_capex_file_override import capex_file_override

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# ---------------------------------------------------------------------------
# 1) Which model to run
# ---------------------------------------------------------------------------
DATASETS = {
    "showcase":       "6_showcase_countries",          # <- validated report showcase
    "toy":            "5_multiple_time_steps_per_year",
    "toyplus":        "5_multiple_extended_countries",
    "full":           os.path.join("ZEN-models", "data", "Crystal_Ball"),
    "small":          os.path.join("ZEN-models", "data", "Crystal_Ball_small", "data", "Crystal_Ball"),
    "dechat":         os.path.join("ZEN-models", "data", "Crystal_Ball_DECHAT"),
}
DATASET = DATASETS["showcase"]
IS_SHOWCASE = os.path.basename(DATASET) == "6_showcase_countries"

# ---------------------------------------------------------------------------
# 2) RC perturbation preset  (applied in optimization_setup, popped before Gurobi)
#    Storyline-pure showcase = STORAGE-ONLY perturbation:
#      conversion + transport are read from the clean (un-perturbed) model, and only
#      storage gets a perturbation (its bundle RC is otherwise undefined/degenerate).
# ---------------------------------------------------------------------------
# objective perturbation on capacity_addition — superseded, keep 0 (can't select the
# dual endpoint).
RC_PERTURBATION = 0
# +delta on the RHS of constraint_technology_lifetime (a tiny phantom existing capacity)
# -> pins the lifetime dual to the correct "value" endpoint for unbuilt conversion/transport.
# 0 = clean (Schritt-1 model). Set to 1e-3 to also resolve degenerate conversion ties
# (e.g. the photovoltaics_capex twins in PV-building nodes) and for Crystal_Ball.
RC_LIFETIME_RHS_PERTURBATION = 0
# +yotta lower bound on storage POWER capacity_addition at unbuilt greenfield nodes;
# energy follows via energy_to_power_ratio_min, so the RC is the joint power+energy
# bundle distance-to-build (read from the power row). 0/None = off.
RC_STORAGE_POWER_PERTURBATION = 1e-4
# Fix the storage duration (energy-to-power ratio, hours) — REQUIRED for the storage
# perturbation to fire and to make the bundle RC unambiguous. {} = off.
RC_TIGHT_E2P = {"battery": 4}
# Build the (serif/no-blue, vmax 150) RC heatmaps right after the run.
GENERATE_HEATMAPS = True

# Per-(tech, node, year) CAPEX override via the robust data-CSV swap (off by default).
# `value` in native input units (Euro/kW power, Euro/kWh storage energy; for storage add
# "capacity_type": "power"|"energy"). Used e.g. for ±1% build/nobuild validation.
RC_CAPEX_OVERRIDE = [
    # {"tech": "photovoltaics", "node": "DE", "year": 2025, "value": 180},
    # {"tech": "battery", "node": "CH", "year": 2025, "capacity_type": "power", "value": 70.0},
]

# Mean-Variance optimization (off by default; None disables).
MV_LAMBDA = None

# ---------------------------------------------------------------------------
# 3) Build the runtime config and run
# ---------------------------------------------------------------------------
now = datetime.now().strftime("%Y%m%d-%H%M%S")
result_folder = f"./outputs_{now}/rc_analysis"
os.makedirs(result_folder, exist_ok=True)

with open("./config.json") as f:
    config = json.load(f)
config.pop("plugins", None)

if MV_LAMBDA is not None:
    config["plugins"] = {"mean_variance_optimization": {
        "weighting_factor": MV_LAMBDA, "include_variances_for": ["technology_capex"]}}

# dataset is passed explicitly to run(); drop any stale default from config.json
config.setdefault("analysis", {})
config["analysis"].pop("dataset", None)
# Showcase: internal time-series aggregation over the full 8760 h. hoursPerPeriod MUST
# be 1 (24 crashes this ZEN version); storage still arbitrages via reconstructed chronology.
if IS_SHOWCASE:
    config["analysis"]["time_series_aggregation"] = {
        "hoursPerPeriod": 1, "clusterMethod": "hierarchical", "extremePeriodMethod": "None"}

config.setdefault("solver", {})
config["solver"].setdefault("solver_options", {})
config["solver"]["name"] = "gurobi"
config["solver"]["save_duals"] = True
config["solver"]["save_reduced_costs"] = True
config["solver"]["use_scaling"] = 0
so = config["solver"]["solver_options"]
so["Method"] = 2
so["Crossover"] = 1
so["Presolve"] = 0
so["rc_perturbation"] = RC_PERTURBATION
so["rc_lifetime_rhs_perturbation"] = RC_LIFETIME_RHS_PERTURBATION
so["rc_storage_power_perturbation"] = RC_STORAGE_POWER_PERTURBATION
if RC_TIGHT_E2P:
    so["rc_tight_e2p"] = RC_TIGHT_E2P
so["LogFile"] = os.path.join(result_folder, "solver.log")

tmp_config = "./config_rc_tmp.json"
with open(tmp_config, "w") as f:
    json.dump(config, f, indent=4)

print(f"Running RC analysis on '{DATASET}' (Method 2 / Barrier, Presolve 0) -> {result_folder}")
print(f"  perturbation: rhs={RC_LIFETIME_RHS_PERTURBATION}  storage={RC_STORAGE_POWER_PERTURBATION}  e2p={RC_TIGHT_E2P}")
with capex_file_override(os.path.abspath(DATASET), RC_CAPEX_OVERRIDE):
    run(config=tmp_config, dataset=DATASET, folder_output=result_folder)
os.remove(tmp_config)

scenario_dir = os.path.join(result_folder, os.path.basename(DATASET))
print(f"\nDone. Results -> {os.path.join(scenario_dir, 'capacity_addition_analysis.csv')}")
print("Primary columns: rc_capex_equivalent_operational_input_units [Euro/kW], ratio_reduction_operational")

# ---------------------------------------------------------------------------
# 4) RC heatmaps (conversion / transport / storage), serif, vmax 150
# ---------------------------------------------------------------------------
if GENERATE_HEATMAPS:
    import rc_heatmaps
    print("\nGenerating RC heatmaps ...")
    rc_heatmaps.run(result_folder, vmax=150.0, storage_metric="proportional", annotate=True)
    print(f"Heatmaps -> {os.path.join(scenario_dir, 'heatmaps')}/<year>/<techtype>/")
