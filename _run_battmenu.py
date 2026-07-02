"""Run the battery-menu variant and check: (a) does the model pick durations from the
menu, (b) are the per-option RCs clean, (c) are the conversion RCs unchanged vs canonical."""
import json, os
import numpy as np, pandas as pd
from zen_garden import run
pd.set_option("display.width", 170)

BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET = os.path.join(BASE, "6_showcase_countries_battmenu"); DATA = os.path.basename(DATASET)
OUT = os.path.join(BASE, "outputs_showcase_battmenu"); os.makedirs(OUT, exist_ok=True)
cfg = {"analysis": {"time_series_aggregation": {"hoursPerPeriod": 1,
            "clusterMethod": "hierarchical", "extremePeriodMethod": "None"}},
       "solver": {"name": "gurobi", "save_duals": True, "save_reduced_costs": True,
                  "use_scaling": 0,
                  "solver_options": {"Method": 2, "Crossover": 1, "Presolve": 0,
                                     "rc_perturbation": 0,
                                     "rc_storage_power_perturbation": 1e-4,
                                     "rc_tight_e2p": {"battery_2h": 2, "battery_4h": 4, "battery_8h": 8}}}}
tmp = os.path.join(OUT, "_c.json"); json.dump(cfg, open(tmp, "w"), indent=2)
run(config=tmp, dataset=DATASET, folder_output=OUT); os.remove(tmp)

sc = os.path.join(OUT, DATA)
print("\n================ STORAGE MENU RESULTS (year 0) ================")
st = pd.read_csv(os.path.join(sc, "capacity_addition_analysis_storage.csv"))
st = st[st.set_time_steps_yearly == 0]
print(st[["set_technologies", "set_location", "case", "e2p", "C_bundle",
          "ratio_reduction_proportional", "value_power"]].round(3).to_string(index=False))

print("\n================ CONVERSION RC: battmenu vs canonical ================")
def conv(path):
    d = pd.read_csv(os.path.join(path, "capacity_addition_analysis_conversion.csv"))
    return d[d.set_time_steps_yearly == 0].set_index(["set_technologies", "set_location"])
cm = conv(sc)
cc = conv("outputs_showcase_storage_only/6_showcase_countries")
j = cm[["ratio_reduction_operational", "case"]].join(
    cc[["ratio_reduction_operational", "case"]], lsuffix="_menu", rsuffix="_canon")
dif = (j.ratio_reduction_operational_menu - j.ratio_reduction_operational_canon).abs()
print("max |operational ratio  menu - canonical| =", round(np.nanmax(dif.values), 6))
chg = j[(j.case_menu != j.case_canon)]
print("conversion cells with changed case:", len(chg))
if len(chg):
    print(chg.to_string())
print("\nDONE", OUT)
