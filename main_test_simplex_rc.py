"""
Test: Simplex RC vs Dual-based RC
==================================
Runs the model twice (Method=0 and Method=1) and compares
  reduced_cost_input_units  (direct Gurobi RC via Simplex)
vs
  rc_capex_equivalent_input_units  (dual-based reconstruction)

If Simplex RC is correct, both columns should agree closely.
"""

import json
import os
from datetime import datetime

from zen_garden import run

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

DATASET = "5_multiple_time_steps_per_year"

now = datetime.now().strftime("%Y%m%d-%H%M%S")

with open("./config.json") as f:
    config = json.load(f)

config.pop("plugins", None)
config["solver"]["save_reduced_costs"] = True
config["solver"]["save_duals"] = True
# Crossover not needed for Simplex — Simplex always lands on a vertex
config["solver"]["solver_options"].pop("Crossover", None)

for method, label in [(0, "primal_simplex"), (1, "dual_simplex")]:
    result_folder = f"./outputs_{now}/simplex_rc_{label}"
    os.makedirs(result_folder, exist_ok=True)

    cfg = json.loads(json.dumps(config))
    cfg["solver"]["solver_options"]["Method"] = method
    cfg["solver"]["solver_options"]["LogFile"] = os.path.join(result_folder, "solver.log")

    tmp = f"./config_simplex_{label}_tmp.json"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=4)

    print(f"\n{'='*60}")
    print(f"Running Method={method} ({label})")
    print(f"Output: {result_folder}")
    run(config=tmp, dataset=DATASET, folder_output=result_folder)
    os.remove(tmp)

    csv = os.path.join(result_folder, DATASET, "capacity_addition_analysis.csv")
    print(f"\nResults -> {csv}")

print("\nDone. Compare 'reduced_cost_input_units' vs 'rc_capex_equivalent_input_units'")
print("They should agree if Simplex RC is correct.")
