"""Diagnose transport RC: for the two buildable corridors (AT-CH, CH-AT), does the line
build at the RC-predicted point, at a deep cut, or never (phantom)? No perturbation."""
import json, os, shutil
import numpy as np, pandas as pd
from zen_garden import run
from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps

BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET = os.path.join(BASE, "6_showcase_countries"); DATA = os.path.basename(DATASET)
ROOT = os.path.join(BASE, "outputs_tmp_diagtr"); os.makedirs(ROOT, exist_ok=True)
EDGES = {"AT-CH": 0.78, "CH-AT": 0.71}   # edge -> reported ratio (op==life)

def cfg():
    return {"analysis": {"time_series_aggregation": {"hoursPerPeriod": 1,
                "clusterMethod": "hierarchical", "extremePeriodMethod": "None"}},
            "solver": {"name": "gurobi", "save_duals": False, "save_reduced_costs": False,
                       "use_scaling": 0, "solver_options": {"Method": 2, "Crossover": 1, "Presolve": 0}}}
def build(edge, cap):
    out = os.path.join(ROOT, f"{edge}_{cap:.1f}"); os.makedirs(out, exist_ok=True)
    tmp = os.path.join(out, "_c.json"); json.dump(cfg(), open(tmp, "w"), indent=2)
    with capex_file_override(DATASET, [{"tech": "power_line", "node": edge, "year": 2025, "value": cap}]):
        run(config=tmp, dataset=DATASET, folder_output=out)
    os.remove(tmp)
    d = pd.read_csv(os.path.join(out, DATA, "capacity_addition_analysis.csv"))
    r = d[(d.set_technologies == "power_line") & (d.set_location == edge) & (d.set_time_steps_yearly == 0)]
    return float(r["value"].iloc[0]) if not r.empty else np.nan

restore_leftover_swaps(DATASET); rows = []
for edge, ratio in EDGES.items():
    base = read_capex(DATASET, "power_line", edge, 2025)
    pts = {"RC build-pt": base * (1 - 1.01 * ratio), "half capex": base * 0.5,
           "10% capex": base * 0.1, "≈free (1.0)": 1.0}
    for label, cap in pts.items():
        b = build(edge, cap)
        rows.append(dict(edge=edge, point=label, capex=round(cap, 1), build_GW=round(b, 4)))
        print(rows[-1], flush=True)
print("\n" + pd.DataFrame(rows).to_string(index=False))
shutil.rmtree(ROOT, ignore_errors=True)
print("DONE")
