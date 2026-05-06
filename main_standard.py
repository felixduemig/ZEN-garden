"""
Standard run of the 5_multiple_time_steps_per_year dataset —
no mean-variance plugin, no lambda weighting, pure LP.
"""

import json
import os
from datetime import datetime

from zen_garden import run

# ── paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

DATASET = "5_multiple_time_steps_per_year"

# ── output folder with timestamp ─────────────────────────────────────────────
now = datetime.now()
time_str = now.strftime("%Y%m%d-%H%M%S")
result_folder = f"./outputs_{time_str}/standard"
os.makedirs(result_folder, exist_ok=True)

# ── build config: start from config.json, strip out the plugin ───────────────
with open("./config.json") as f:
    config = json.load(f)

# remove mean_variance_optimization plugin entirely
config.pop("plugins", None)

# point the solver log at the result folder
config["solver"]["solver_options"]["LogFile"] = f"{result_folder}/solver.log"

# write a temporary run config (no permanent side-effects on config.json)
tmp_config_path = "./config_standard_tmp.json"
with open(tmp_config_path, "w") as f:
    json.dump(config, f, indent=4)

# ── run ───────────────────────────────────────────────────────────────────────
print(f"Running standard LP — output → {result_folder}")
run(
    config=tmp_config_path,
    dataset=DATASET,
    folder_output=result_folder,
)

# clean up temporary config
os.remove(tmp_config_path)

print(f"\nDone. Results in: {result_folder}")
print(f"Capacity addition analysis: {result_folder}/{DATASET}/capacity_addition_analysis.csv")
