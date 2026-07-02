"""Is the FR photovoltaics_capex RC shift (2.0%->1.4% in the menu run) REAL or degeneracy?
Ground truth (NO perturbation): find the true build threshold of the FR PV clone in BOTH
the menu dataset and the canonical dataset. If both build only at ~CAPEX 490 (=2.0%),
the menu's 1.4% is a degeneracy/perturbation artifact, not a real economic shift."""
import json, os, shutil
import numpy as np, pandas as pd
from zen_garden import run
from rc_capex_file_override import capex_file_override, restore_leftover_swaps

BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
ROOT = os.path.join(BASE, "outputs_tmp_frcheck"); os.makedirs(ROOT, exist_ok=True)
# clone base CAPEX = 500. menu RC 1.38% -> build pt 493.1 ; canonical RC 2.0% -> build pt 489.9
CAPS = [493.1, 490.1, 489.9, 488.0]   # straddle both candidate thresholds
DSETS = {"canonical": "6_showcase_countries", "menu": "6_showcase_countries_battmenu"}

def cfg():
    return {"analysis": {"time_series_aggregation": {"hoursPerPeriod": 1,
                "clusterMethod": "hierarchical", "extremePeriodMethod": "None"}},
            "solver": {"name": "gurobi", "save_duals": False, "save_reduced_costs": False,
                       "use_scaling": 0, "solver_options": {"Method": 2, "Crossover": 1, "Presolve": 0}}}
def build_fr(ds, cap):
    out = os.path.join(ROOT, f"{ds}_{cap}"); os.makedirs(out, exist_ok=True)
    tmp = os.path.join(out, "_c.json"); json.dump(cfg(), open(tmp, "w"), indent=2)
    dpath = os.path.join(BASE, DSETS[ds])
    with capex_file_override(dpath, [{"tech": "photovoltaics_capex", "node": "FR", "year": 2025, "value": cap}]):
        run(config=tmp, dataset=dpath, folder_output=out)
    os.remove(tmp)
    d = pd.read_csv(os.path.join(out, DSETS[ds], "capacity_addition_analysis.csv"))
    r = d[(d.set_technologies == "photovoltaics_capex") & (d.set_location == "FR")
          & (d.set_capacity_types == "power") & (d.set_time_steps_yearly == 0)]
    return float(r["value"].iloc[0]) if not r.empty else np.nan

rows = []
for ds in DSETS:
    restore_leftover_swaps(os.path.join(BASE, DSETS[ds]))
    for cap in CAPS:
        b = build_fr(ds, cap)
        rows.append(dict(dataset=ds, capex_FR_clone=cap, reduction_pct=round(100*(500-cap)/500, 2),
                         fr_clone_build=round(b, 4)))
        print(rows[-1], flush=True)
print("\n" + pd.DataFrame(rows).to_string(index=False))
shutil.rmtree(ROOT, ignore_errors=True)
print("DONE (tmp removed)")
