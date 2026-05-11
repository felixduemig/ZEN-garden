"""
Wind CAPEX Sweep
================
Runs the LP (Primal Simplex, Presolve=0) for a range of wind_onshore capex values
and collects capacity_addition + RC results in a single summary CSV.

For each capex value the script temporarily patches
  5_multiple_extended/set_technologies/set_conversion_technologies/wind_onshore/attributes.json
runs the model, reads the output, then restores the original file.

Output: ./wind_capex_sweep/summary.csv
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from zen_garden import run

BASE_DIR = Path(__file__).parent
os.chdir(BASE_DIR)

DATASET = "5_multiple_extended"
WIND_ATTR = Path(DATASET) / "set_technologies" / "set_conversion_technologies" / "wind_onshore" / "attributes.json"

# ── capex values to test [Euro/kW] ───────────────────────────────────────────
CAPEX_VALUES = [1133, 1000, 900, 800, 700, 600, 500, 400, 300, 268, 200, 100, 50, 12]

# ── output folder ─────────────────────────────────────────────────────────────
SWEEP_DIR = Path("./wind_capex_sweep")
SWEEP_DIR.mkdir(exist_ok=True)

# ── solver config ─────────────────────────────────────────────────────────────
with open("./config.json") as f:
    config = json.load(f)

config.pop("plugins", None)
config.setdefault("solver", {})
config["solver"].setdefault("solver_options", {})
config["solver"]["name"] = "gurobi"
config["solver"]["save_duals"] = True
config["solver"]["save_reduced_costs"] = True
config["solver"]["solver_options"]["Method"] = 0
config["solver"]["solver_options"]["Presolve"] = 0
config["solver"]["solver_options"].pop("Crossover", None)
config["solver"]["solver_options"].pop("BarHomogeneous", None)

# ── helpers ───────────────────────────────────────────────────────────────────

def read_wind_results(csv_path: Path) -> list[dict]:
    """Parse capacity_addition_analysis.csv and return wind_onshore rows."""
    import csv
    results = []
    if not csv_path.exists():
        return results
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            if row["set_technologies"] == "wind_onshore":
                results.append({
                    "node":     row["set_location"],
                    "year":     int(row["set_time_steps_yearly"]),
                    "built_gw": float(row["value"]),
                    "rc_euro_per_kw": float(row["rc_capex_equivalent_input_units"]),
                    "rc_per_kw_eff": float(row.get("rc_capex_equivalent_per_kw_eff", "nan")),
                })
    return results


def patch_capex(capex: float) -> dict:
    """Overwrite wind_onshore capex in attributes.json; return original content."""
    with open(WIND_ATTR) as f:
        original = json.load(f)
    patched = json.loads(json.dumps(original))
    patched["capex_specific_conversion"]["default_value"] = capex
    with open(WIND_ATTR, "w") as f:
        json.dump(patched, f, indent=2)
    return original


def restore_capex(original: dict):
    with open(WIND_ATTR, "w") as f:
        json.dump(original, f, indent=2)


# ── sweep ─────────────────────────────────────────────────────────────────────

summary_rows = []

tmp_config = BASE_DIR / "config_wind_sweep_tmp.json"

for capex in CAPEX_VALUES:
    run_dir = SWEEP_DIR / f"capex_{capex:04d}"

    config["solver"]["solver_options"]["LogFile"] = str(run_dir / "solver.log")
    with open(tmp_config, "w") as f:
        json.dump(config, f, indent=4)

    print(f"\n{'='*60}")
    print(f"  wind capex = {capex} Euro/kW")
    print(f"{'='*60}")

    original = patch_capex(capex)
    try:
        run(config=str(tmp_config), dataset=DATASET, folder_output=str(run_dir))
    finally:
        restore_capex(original)

    csv_path = run_dir / DATASET / "capacity_addition_analysis.csv"
    for row in read_wind_results(csv_path):
        summary_rows.append({"capex_euro_per_kw": capex, **row})

if tmp_config.exists():
    tmp_config.unlink()

# ── write summary ──────────────────────────────────────────────────────────────

import csv

summary_path = SWEEP_DIR / "summary.csv"
if summary_rows:
    fields = list(summary_rows[0].keys())
    with open(summary_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(summary_rows)

print(f"\nDone. Summary → {summary_path}")

# ── quick console table ────────────────────────────────────────────────────────

print(f"\n{'capex':>8}  {'node':<5} {'year':>4}  {'built_gw':>9}  {'rc [€/kw]':>12}  {'built?'}")
print("-" * 60)
for r in summary_rows:
    built = "✓" if r["built_gw"] > 1e-6 else ""
    print(f"{r['capex_euro_per_kw']:>8}  {r['node']:<5} {r['year']:>4}  "
          f"{r['built_gw']:>9.3f}  {r['rc_euro_per_kw']:>12.1f}  {built}")
