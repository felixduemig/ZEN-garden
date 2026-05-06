"""
RC Analysis Run
===============
Runs the model as a pure LP with Primal Simplex (Method=0).
Primal Simplex lands on an LP vertex, giving exact duals for all constraints.

The exact duals of constraint_technology_lifetime are used to compute
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

#DATASET = "5_multiple_time_steps_per_year"
DATASET = "ZEN-models\data\Crystal_Ball"

now = datetime.now().strftime("%Y%m%d-%H%M%S")
result_folder = f"./outputs_{now}/rc_analysis"
os.makedirs(result_folder, exist_ok=True)

with open("./config.json") as f:
    config = json.load(f)

# Pure LP — no mean-variance plugin
config.pop("plugins", None)

# Primal Simplex: lands on an LP vertex → exact duals and reduced costs
# Presolve=0: prevents Gurobi from eliminating variables before solving,
#             which can suppress dual output for some constraints
config.setdefault("solver", {})
config["solver"].setdefault("solver_options", {})

config["solver"]["name"] = "gurobi"
config["solver"]["save_duals"] = True
config["solver"]["save_reduced_costs"] = True
config["solver"]["solver_options"]["Method"] = 0
config["solver"]["solver_options"]["Presolve"] = 0
config["solver"]["solver_options"].pop("Crossover", None)
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
