"""
RC Analysis Run
===============
Runs the model as a pure LP with Homogeneous Barrier (Method=2, BarHomogeneous=1,
Crossover=0).

Homogeneous Barrier solves a self-dual extended problem — numerically stable even
for poorly-scaled models, and does not require a feasible starting point.
Crossover is disabled: duals come from the interior-point solution, which is a
weighted average over all optimal vertices. Acceptable for exploratory RC analysis.

The duals of constraint_technology_lifetime are used to compute
rc_capex_equivalent_input_units [Euro/kW] — the capex reduction needed
for each technology to become optimal.

Output: <result_folder>/<dataset>/capacity_addition_analysis.csv
  value                           optimal capacity addition [GW]
  reduced_cost                    Gurobi RC attribute [model units]
  rc_capex_equivalent             dual-based RC [model units]
  rc_capex_equivalent_input_units dual-based RC [Euro/kW]  ← primary result
"""

import json
import os
from datetime import datetime

from zen_garden import run

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# Dataset path — either:
#   a) just the folder name if the dataset sits directly in BASE_DIR
#   b) a relative path from BASE_DIR (e.g. ZEN-models/data/Crystal_Ball)
#   c) an absolute path
DATASETS = {
    "toy":         "5_multiple_time_steps_per_year",
    "full":        os.path.join("ZEN-models", "data", "Crystal_Ball"),
    "small":       os.path.join("ZEN-models", "data", "Crystal_Ball_small", "data", "Crystal_Ball"),
    "dechat":      os.path.join("ZEN-models", "data", "Crystal_Ball_DECHAT"),
}
DATASET = DATASETS["toy"]

now = datetime.now().strftime("%Y%m%d-%H%M%S")
result_folder = f"./outputs_{now}/rc_analysis"
os.makedirs(result_folder, exist_ok=True)

with open("./config.json") as f:
    config = json.load(f)

# Pure LP — no mean-variance plugin
config.pop("plugins", None)

# Barrier + Crossover: fast interior-point solve, then crossover to LP vertex
# → exact duals identical to Simplex, typically 10-100x faster on large models
config.setdefault("solver", {})
config["solver"].setdefault("solver_options", {})

config["solver"]["name"] = "gurobi"
config["solver"]["save_duals"] = True
config["solver"]["save_reduced_costs"] = True
# Homogeneous Barrier: numerically stable, no feasible start needed, no crossover
config["solver"]["solver_options"]["Method"] = 0         # Barrier
#config["solver"]["solver_options"]["BarHomogeneous"] = 1  # Homogeneous algorithm
config["solver"]["solver_options"]["Crossover"] = 1      # Interior-point duals, no vertex projection
#config["solver"]["solver_options"].pop("Presolve", None)  # Let Gurobi presolve reduce problem
config["solver"]["solver_options"]["LogFile"] = os.path.join(result_folder, "solver.log")

tmp_config = "./config_rc_tmp.json"
with open(tmp_config, "w") as f:
    json.dump(config, f, indent=4)

print(f"Running RC analysis (Primal Simplex) → {result_folder}")
run(config=tmp_config, dataset=DATASET, folder_output=result_folder)
os.remove(tmp_config)

csv = os.path.join(result_folder, DATASET, "capacity_addition_analysis.csv")
print(f"\nDone. Reduced costs → {csv}")
print("Primary column: rc_capex_equivalent_input_units [Euro/kW]")
