"""RC-Dual-Dump #2: reproduziert die Nutzer-Config (Perturbationen AUS, reservoir_hydro
CZ via Datei-Override auf 2250) und dumpt die per-Constraint-Zerlegung fuer
reservoir_hydro CZ (vbasis=0, RC laut Nutzer KORREKT) vs. oil_boiler NL (FALSCH) vs.
wind_onshore BG (korrekt). Soll zeigen, was reservoir_hydro strukturell unterscheidet."""
import json, os
from datetime import datetime
from zen_garden import run
from rc_capex_file_override import capex_file_override

BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET = os.path.join(BASE, "ZEN-models", "data", "Crystal_Ball")
OUT = os.path.join(BASE, f"outputs_{datetime.now():%Y%m%d-%H%M%S}_rc_dualdump2")
os.makedirs(OUT, exist_ok=True)

TARGETS = [
    {"tech": "reservoir_hydro", "node": "CZ"},   # vbasis=0, RC laut Nutzer KORREKT
    {"tech": "oil_boiler", "node": "NL"},         # FALSCH (RC_true=0 im 1. Dump)
    {"tech": "wind_onshore", "node": "BG"},       # korrekt
]
CAPEX_OVERRIDE = [{"tech": "reservoir_hydro", "node": "CZ", "year": 2050, "value": 2250}]

with open("./config.json") as f:
    c = json.load(f)
c.pop("plugins", None)
c.setdefault("solver", {}); c["solver"].setdefault("solver_options", {})
c["solver"]["name"] = "gurobi"; c["solver"]["save_duals"] = True
c["solver"]["save_reduced_costs"] = True; c["solver"]["use_scaling"] = 0
so = c["solver"]["solver_options"]
so["Method"] = 2; so["Crossover"] = 1; so["Presolve"] = 0
# Perturbationen AUS (wie in deinem main_rc_simplex)
so["rc_perturbation"] = 0
so["rc_lifetime_rhs_perturbation"] = 0
so["rc_storage_power_perturbation"] = 0
# Dual-Dump
c.setdefault("analysis", {})
c["analysis"]["rc_dual_dump"] = True
c["analysis"]["rc_dual_dump_targets"] = TARGETS

tmp = os.path.join(BASE, "_dualdump2_cfg.json")
with open(tmp, "w") as f:
    json.dump(c, f)
print(f"RC dual dump #2 -> {OUT}")
with capex_file_override(os.path.abspath(DATASET), CAPEX_OVERRIDE):
    run(config=tmp, dataset=DATASET, folder_output=OUT)
os.remove(tmp)

import pandas as pd
f = os.path.join(OUT, "Crystal_Ball", "rc_dual_decomposition.csv")
print("\n================ RC DUAL DECOMPOSITION #2 ================")
pd.set_option("display.width", 200); pd.set_option("display.max_rows", 300)
print(pd.read_csv(f).to_string(index=False))
print(f"\nCSV: {f}")
