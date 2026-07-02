"""Incremental-build sweep for PV @ DE, 2025. Vary ONLY that CAPEX across a range
around the tipping point (RC = 85.9 EUR/kW, i.e. break-even capex 404.1) and record
the resulting PV DE build [GW]. Shows that build ramps incrementally from the RC
tipping point, not 0->100. No duals / no perturbation (we only need the build)."""
import json, os
from datetime import datetime
import numpy as np, pandas as pd
from zen_garden import run
from rc_capex_file_override import capex_file_override, restore_leftover_swaps

BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET = os.path.join(BASE, "6_showcase_countries"); DATA = os.path.basename(DATASET)
ROOT = os.path.join(BASE, f"outputs_{datetime.now():%Y%m%d-%H%M%S}_sweep_pvde")
os.makedirs(ROOT, exist_ok=True)
BASE_CAPEX, RC = 490.0, 85.9   # PV DE 2025: operational RC ~85.9 -> break-even capex ~404.1

# capex points: above tipping (no build), around it (dense), and well below (ramp)
CAPS = [415, 410, 406, 405, 404.1, 403, 401, 398, 394, 388, 378, 363, 340, 305, 260]

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
    with capex_file_override(DATASET, [{"tech": "photovoltaics", "node": "DE",
                                        "year": 2025, "value": float(cap)}]):
        run(config=tmp, dataset=DATASET, folder_output=out)
    os.remove(tmp)
    bld = pv_de_build(os.path.join(out, DATA))
    red = BASE_CAPEX - cap
    rows.append(dict(capex=cap, reduction=round(red, 1),
                     reduction_pct=round(100 * red / BASE_CAPEX, 2),
                     pv_de_build=round(bld, 4)))
    print(rows[-1], flush=True)

df = pd.DataFrame(rows)
df.to_csv(os.path.join(ROOT, "sweep_pvde.csv"), index=False)
print("\n" + df.to_string(index=False)); print("RC =", RC, "-> break-even capex ~404.1"); print("DONE", ROOT)
