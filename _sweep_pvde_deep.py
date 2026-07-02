"""Deep continuation of the PV DE 2025 sweep: very low CAPEX to find saturation
(hard cap 250 GW vs economic/curtailment saturation)."""
import json, os
from datetime import datetime
import numpy as np, pandas as pd
from zen_garden import run
from rc_capex_file_override import capex_file_override, restore_leftover_swaps

BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET = os.path.join(BASE, "6_showcase_countries"); DATA = os.path.basename(DATASET)
ROOT = os.path.join(BASE, f"outputs_{datetime.now():%Y%m%d-%H%M%S}_sweep_pvde_deep")
os.makedirs(ROOT, exist_ok=True)
CAPS = [200, 150, 100, 50, 5]   # deep reductions (base capex 490, cap 250 GW)

def cfg():
    return {"analysis": {"time_series_aggregation": {"hoursPerPeriod": 1,
                "clusterMethod": "hierarchical", "extremePeriodMethod": "None"}},
            "solver": {"name": "gurobi", "save_duals": False, "save_reduced_costs": False,
                       "use_scaling": 0, "solver_options": {"Method": 2, "Crossover": 1, "Presolve": 0}}}
def pv_de_build(sc):
    d = pd.read_csv(os.path.join(sc, "capacity_addition_analysis.csv"))
    r = d[(d.set_technologies == "photovoltaics") & (d.set_location == "DE")
          & (d.set_capacity_types == "power") & (d.set_time_steps_yearly == 0)]
    return float(r["value"].iloc[0]) if not r.empty else np.nan

restore_leftover_swaps(DATASET); rows = []
for cap in CAPS:
    out = os.path.join(ROOT, f"cap_{cap}"); os.makedirs(out, exist_ok=True)
    tmp = os.path.join(out, "_c.json"); json.dump(cfg(), open(tmp, "w"), indent=2)
    with capex_file_override(DATASET, [{"tech": "photovoltaics", "node": "DE", "year": 2025, "value": float(cap)}]):
        run(config=tmp, dataset=DATASET, folder_output=out)
    os.remove(tmp)
    bld = pv_de_build(os.path.join(out, DATA))
    rows.append(dict(capex=cap, reduction=490 - cap, pv_de_build=round(bld, 3)))
    print(rows[-1], flush=True)
pd.DataFrame(rows).to_csv(os.path.join(ROOT, "sweep_deep.csv"), index=False)
print("\n" + pd.DataFrame(rows).to_string(index=False)); print("cap=250 GW (hard limit)"); print("DONE", ROOT)
