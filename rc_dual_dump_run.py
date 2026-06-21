"""Treiber fuer den RC-Dual-Dump: 1 Baseline-Lauf (Perturbationen wie im Stresstest),
der fuer die 5 Fall-Techs die per-Constraint-Zerlegung des Reduced Cost von
capacity_addition ausgibt (rc_dual_decomposition.csv)."""
import json, os
from datetime import datetime
from zen_garden import run

BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET = os.path.join(BASE, "ZEN-models", "data", "Crystal_Ball")
OUT = os.path.join(BASE, f"outputs_{datetime.now():%Y%m%d-%H%M%S}_rc_dualdump")
os.makedirs(OUT, exist_ok=True)

TARGETS = [
    {"tech": "wind_onshore", "node": "BG"},       # PASS
    {"tech": "H2_DRI", "node": "ES"},             # PASS
    {"tech": "oil_boiler", "node": "NL"},         # FAIL (unterschaetzt)
    {"tech": "ammonia_ICE_ship", "node": "LV"},   # FAIL (unterschaetzt)
    {"tech": "HDT_BET", "node": "ES"},            # FAIL (ueberschaetzt)
]

with open("./config.json") as f:
    c = json.load(f)
c.pop("plugins", None)
c.setdefault("solver", {}); c["solver"].setdefault("solver_options", {})
c["solver"]["name"] = "gurobi"; c["solver"]["save_duals"] = True
c["solver"]["save_reduced_costs"] = True; c["solver"]["use_scaling"] = 0
so = c["solver"]["solver_options"]
so["Method"] = 2; so["Crossover"] = 1; so["Presolve"] = 0
# gleiche Perturbationen wie der Stresstest-Baseline (interpretierbare RC)
so["rc_perturbation"] = 0
so["rc_lifetime_rhs_perturbation"] = 1e-4
so["rc_storage_power_perturbation"] = 1e-4
so["rc_tight_e2p"] = {"battery": 16, "pumped_hydro": 22, "salt_cavern_storage": 145}
# Dual-Dump aktivieren
c.setdefault("analysis", {})
c["analysis"]["rc_dual_dump"] = True
c["analysis"]["rc_dual_dump_targets"] = TARGETS

tmp = os.path.join(BASE, "_dualdump_cfg.json")
with open(tmp, "w") as f:
    json.dump(c, f)
print(f"RC dual dump -> {OUT}")
run(config=tmp, dataset=DATASET, folder_output=OUT)
os.remove(tmp)

import pandas as pd
f = os.path.join(OUT, "Crystal_Ball", "rc_dual_decomposition.csv")
print("\n================ RC DUAL DECOMPOSITION ================")
pd.set_option("display.width", 200); pd.set_option("display.max_rows", 200)
print(pd.read_csv(f).to_string(index=False))
print(f"\nCSV: {f}")
