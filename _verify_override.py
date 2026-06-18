"""Einmaliger Verifikationslauf: greift der rc_capex_override jetzt?
HDT_BET @ ES auf 250 EUR/kW (Baseline 259.19, Schwelle ~255.47) -> sollte gesetzt
werden UND bauen."""
import json, os
from zen_garden import run

BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET = os.path.join(BASE, "ZEN-models", "data", "Crystal_Ball")
OUT = os.path.join(BASE, "_verify_override_out")
os.makedirs(OUT, exist_ok=True)

with open("./config.json") as f:
    c = json.load(f)
c.pop("plugins", None)
c.setdefault("solver", {}); c["solver"].setdefault("solver_options", {})
c["solver"]["name"] = "gurobi"; c["solver"]["save_duals"] = True
c["solver"]["save_reduced_costs"] = True; c["solver"]["use_scaling"] = 0
so = c["solver"]["solver_options"]
so["Method"] = 2; so["Crossover"] = 1; so["Presolve"] = 0
so["rc_capex_override"] = [{"tech": "HDT_BET", "node": "ES", "year": 2050, "value": 250.0}]

tmp = os.path.join(BASE, "_verify_cfg.json")
with open(tmp, "w") as f:
    json.dump(c, f)
run(config=tmp, dataset=DATASET, folder_output=OUT)
os.remove(tmp)

import pandas as pd
d = pd.read_csv(os.path.join(OUT, "Crystal_Ball", "capacity_addition_analysis_conversion.csv"))
r = d[(d.set_technologies == "HDT_BET") & (d.set_location == "ES")].iloc[0]
print("\n==================== VERIFY ====================")
print(f"capex_specific_input_units = {r.capex_specific_input_units:.3f}  (erwartet ~250.0, Baseline 259.19)")
print(f"value (capacity_addition)  = {r.value:.5g}  (erwartet > 0 -> baut)")
ok = abs(r.capex_specific_input_units - 250.0) < 1.0
print(f"OVERRIDE GREIFT: {'JA' if ok else 'NEIN'}")
print("===============================================")
