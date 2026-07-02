"""+-1% validation of the menu durations (battery_2h / battery_8h at IT), to show the
bundle RC is exact at any duration. e2p is fixed in the dataset, so build/nobuild runs
need no perturbation."""
import json, os
from datetime import datetime
import numpy as np, pandas as pd
from zen_garden import run
from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps

BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET = os.path.join(BASE, "6_showcase_countries_battmenu"); DATA = os.path.basename(DATASET)
SRC = os.path.join(BASE, "outputs_showcase_battmenu", DATA)
MARGIN = 0.01; REFY = 2025; VTOL = 1e-4
ROOT = os.path.join(BASE, f"outputs_{datetime.now():%Y%m%d-%H%M%S}_val_battmenu"); os.makedirs(ROOT, exist_ok=True)

st = pd.read_csv(SRC + "/capacity_addition_analysis_storage.csv")
def f_of(tech, node, y=0):
    r = st[(st.set_technologies == tech) & (st.set_location == node) & (st.set_time_steps_yearly == y)]
    return float(r.rc_mathematical.iloc[0]), float(r.ratio_reduction_proportional.iloc[0])
def cfg():
    return {"analysis": {"time_series_aggregation": {"hoursPerPeriod": 1,
                "clusterMethod": "hierarchical", "extremePeriodMethod": "None"}},
            "solver": {"name": "gurobi", "save_duals": False, "save_reduced_costs": False,
                       "use_scaling": 0, "solver_options": {"Method": 2, "Crossover": 1, "Presolve": 0}}}
def run_model(name):
    out = os.path.join(ROOT, name); os.makedirs(out, exist_ok=True)
    tmp = os.path.join(out, "_c.json"); json.dump(cfg(), open(tmp, "w"), indent=2)
    run(config=tmp, dataset=DATASET, folder_output=out); os.remove(tmp)
    return os.path.join(out, DATA)
def valc(sc, tech, node, y=0):
    d = pd.read_csv(os.path.join(sc, "capacity_addition_analysis.csv"))
    r = d[(d.set_technologies == tech) & (d.set_capacity_types == "power")
          & (d.set_location == node) & (d.set_time_steps_yearly == y)]
    return float(r["value"].iloc[0]) if not r.empty else np.nan

restore_leftover_swaps(DATASET); res = []
for tech, node in [("battery_2h", "IT"), ("battery_8h", "IT")]:
    rc, f = f_of(tech, node); year = REFY
    cp = read_capex(DATASET, tech, node, year, "power"); ce = read_capex(DATASET, tech, node, year, "energy")
    def ov(s, p=cp, e=ce, nd=node, t=tech, yr=year):
        return [{"tech": t, "node": nd, "year": yr, "capacity_type": "power", "value": p * s},
                {"tech": t, "node": nd, "year": yr, "capacity_type": "energy", "value": e * s}]
    with capex_file_override(DATASET, ov(1 - (1 + MARGIN) * f)):
        vb = valc(run_model(f"{tech}_{node}_b"), tech, node)
    with capex_file_override(DATASET, ov(1 - (1 - MARGIN) * f)):
        vn = valc(run_model(f"{tech}_{node}_n"), tech, node)
    ok = (vb > VTOL) and not (vn > VTOL)
    res.append(dict(tech=tech, node=node, rc=round(rc, 1), ratio=round(f, 3),
                    vbuild=round(vb, 4), vnobuild=round(vn, 4),
                    result="PASS" if ok else "FAIL")); print(res[-1], flush=True)
pd.DataFrame(res).to_csv(os.path.join(ROOT, "val_battmenu_summary.csv"), index=False)
print("\n" + pd.DataFrame(res).to_string(index=False)); print("DONE", ROOT)
