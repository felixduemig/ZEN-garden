"""
LP run with exact Reduced Costs
================================
Runs the model as a pure LP — no mean-variance plugin — with Gurobi crossover
enabled. This gives the exact LP reduced cost for every technology directly,
without the dual-based approximation needed for the QP/barrier-only setup.

Output in capacity_addition_analysis.csv:
  reduced_cost_input_units      ← exact LP RC in Euro/kW  (use this)
  rc_capex_equivalent_input_units ← dual-based RC in Euro/kW (cross-check)

Both columns should agree closely. Any difference reflects numerical precision
of the crossover step.

Why crossover here but not in the QP runs?
  The mean-variance plugin adds auxiliary variables that cause crossover to
  produce a degenerate basis, making the RC meaningless. Without the plugin
  the model is a pure LP and crossover works correctly.
"""

import json
import os
from datetime import datetime

from zen_garden import run

# ── paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

DATASET = "5_multiple_time_steps_per_year"

# ── output folder ──────────────────────────────────────────────────────────────
now = datetime.now()
time_str = now.strftime("%Y%m%d-%H%M%S")
result_folder = f"./outputs_{time_str}/lp_exact_rc"
os.makedirs(result_folder, exist_ok=True)

# ── build config ───────────────────────────────────────────────────────────────
with open("./config.json") as f:
    config = json.load(f)

# No plugin → pure LP
config.pop("plugins", None)

# Enable crossover so Gurobi returns exact LP reduced costs.
# Crossover=1  → automatic (Gurobi chooses primal or dual crossover)
# Crossover=-1 → Gurobi default (same as 1 for LP)
# We keep Method=2 (barrier) as the interior-point starting point;
# crossover then projects the barrier solution onto an LP vertex.
config["solver"]["solver_options"]["Crossover"] = 1

# Save reduced costs (needed for the RC export in postprocess.py)
config["solver"]["save_reduced_costs"] = True
config["solver"]["save_duals"]         = True

config["solver"]["solver_options"]["LogFile"] = os.path.join(result_folder, "solver.log")

tmp_config = "./config_lp_exact_rc_tmp.json"
with open(tmp_config, "w") as f:
    json.dump(config, f, indent=4)

# ── run ────────────────────────────────────────────────────────────────────────
print(f"Running pure LP with crossover → exact RC")
print(f"Output: {result_folder}")

run(
    config=tmp_config,
    dataset=DATASET,
    folder_output=result_folder,
)

os.remove(tmp_config)

# ── print result location ──────────────────────────────────────────────────────
rc_csv = os.path.join(result_folder, DATASET, "capacity_addition_analysis.csv")
print(f"\nDone.")
print(f"Reduced costs → {rc_csv}")
print()
print("Columns in capacity_addition_analysis.csv:")
print("  reduced_cost_input_units        exact LP RC [Euro/kW]  ← primary result")
print("  rc_capex_equivalent_input_units dual-based RC [Euro/kW] ← cross-check")
print()
print("For built technologies    both ≈ 0")
print("For unbuilt technologies  both ≈ capex premium over breakeven [Euro/kW]")
print("If they agree closely → dual approach was accurate in the QP runs too.")
