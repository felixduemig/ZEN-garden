"""Solve the scarcity-island reproducer with the EXACT RC solver settings
(Gurobi Method 2 + Crossover 1 + Presolve 0, use_scaling 0, save_duals/reduced_costs),
then print the operational RC of 'baseload' and the per-step ISL electricity price."""
import os, json, subprocess, sys
from datetime import datetime
import pandas as pd, numpy as np

BASE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(BASE)
os.chdir(ROOT)
# (re)build dataset
subprocess.run([sys.executable, os.path.join(BASE, "build_island.py")], check=True)

from zen_garden import run
DS = os.path.join(ROOT, "rc_scarcity_demo")
OUT = os.path.join(ROOT, "outputs_island", datetime.now().strftime("%H%M%S"))
os.makedirs(OUT, exist_ok=True)
cfg = {
    "solver": {"name": "gurobi", "save_duals": True, "save_reduced_costs": True,
               "use_scaling": 0,
               "solver_options": {"Method": 2, "Crossover": 1, "Presolve": 0}},
}
tmp = os.path.join(OUT, "_cfg.json"); json.dump(cfg, open(tmp, "w"))
run(config=tmp, dataset=DS, folder_output=OUT)

RES = os.path.join(OUT, "rc_scarcity_demo")
conv = pd.read_csv(os.path.join(RES, "capacity_addition_analysis_conversion.csv"))
pd.set_option("display.width", 220)
cols = ["set_technologies", "set_location", "value", "capacity", "capacity_ceiling",
        "case", "capex_specific_input_units", "rc_capex_equivalent_input_units",
        "ratio_reduction", "rc_capex_equivalent_operational_input_units",
        "ratio_reduction_operational", "rc_reliable"]
print("\n=== conversion RC analysis ===")
print(conv[cols].to_string(index=False))

# per-step ISL electricity price (nodal balance dual / duration)
lam = pd.read_hdf(os.path.join(RES, "dual_dict.h5"), "constraint_nodal_energy_balance")
dur = pd.read_hdf(os.path.join(RES, "param_dict.h5"), "time_steps_operation_duration").to_dict()
print("\n=== ISL & MAIN electricity per-hour price (lambda/duration) ===")
for nd in ["ISL", "MAIN"]:
    row = []
    for t in range(4):
        try: row.append(round(float(lam.loc[("electricity", nd, t)]) / dur[t], 3))
        except Exception: row.append(None)
    print(f"  {nd}: {row}")
# dispatch in scarce step 0
out = pd.read_hdf(os.path.join(RES, "var_dict.h5"), "flow_conversion_output")
ft  = pd.read_hdf(os.path.join(RES, "var_dict.h5"), "flow_transport")
print("\n=== scarce step 0 dispatch ===")
o0 = out[(out.index.get_level_values("node") == "ISL") & (out.index.get_level_values("time_operation") == 0)]
print("  ISL conversion output:", {k[0]: round(float(v), 3) for k, v in o0.items() if v > 1e-9})
print("  line flow MAIN->ISL t0:", round(float(ft.loc[("power_line", "MAIN-ISL", 0)]), 3),
      " (cap 30 => congested if =30)")
print("\nOUT:", OUT)
