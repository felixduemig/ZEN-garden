"""Proper transport +-1% validation. Transport capex = capex_per_distance_transport
(EUR/km/MW) * distance, so we override the PER-EDGE rate (write a per-edge
capex_per_distance_transport.csv; only the target edge changes, others keep 546).
Working in rate space, scaling the rate by (1 -+ (1+-1%)*ratio) scales the edge capex by
the same fraction. Validates the OPERATIONAL transport RC (== lifetime here). Sanity:
prints the resulting per-edge capex so we can see the override actually took effect."""
import json, os
from datetime import datetime
import numpy as np, pandas as pd
from zen_garden import run

BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET = os.path.join(BASE, "6_showcase_countries"); DATA = os.path.basename(DATASET)
SRC = os.path.join(BASE, "outputs_showcase_storage_only", DATA)
PLDIR = os.path.join(DATASET, "set_technologies", "set_transport_technologies", "power_line")
RATE_CSV = os.path.join(PLDIR, "capex_per_distance_transport.csv")
BAK = RATE_CSV + ".bak"
BASE_RATE, MARGIN, REFY, VTOL = 546.0, 0.01, 2025, 1e-4
ROOT = os.path.join(BASE, f"outputs_{datetime.now():%Y%m%d-%H%M%S}_val_tr2"); os.makedirs(ROOT, exist_ok=True)

EDGES = list(pd.read_csv(os.path.join(PLDIR, "distance.csv"))["edge"].astype(str))
tr = pd.read_csv(SRC + "/capacity_addition_analysis_transport.csv")
tr = tr[tr.set_time_steps_yearly == 0]
def ratio_op(edge):
    r = tr[(tr.set_technologies == "power_line") & (tr.set_location == edge)]
    return float(r.ratio_reduction_operational.iloc[0])

def set_rate(target_edge, rate):
    df = pd.DataFrame({"edge": EDGES,
                       "capex_per_distance_transport": [rate if e == target_edge else BASE_RATE for e in EDGES]})
    df.to_csv(RATE_CSV, index=False)
def clear_rate():
    if os.path.isfile(RATE_CSV):
        os.remove(RATE_CSV)

def cfg():
    return {"analysis": {"time_series_aggregation": {"hoursPerPeriod": 1,
                "clusterMethod": "hierarchical", "extremePeriodMethod": "None"}},
            "solver": {"name": "gurobi", "save_duals": False, "save_reduced_costs": False,
                       "use_scaling": 0, "solver_options": {"Method": 2, "Crossover": 1, "Presolve": 0}}}
def run_read(name, edge):
    out = os.path.join(ROOT, name); os.makedirs(out, exist_ok=True)
    tmp = os.path.join(out, "_c.json"); json.dump(cfg(), open(tmp, "w"), indent=2)
    run(config=tmp, dataset=DATASET, folder_output=out); os.remove(tmp)
    d = pd.read_csv(os.path.join(out, DATA, "capacity_addition_analysis.csv"))
    r = d[(d.set_technologies == "power_line") & (d.set_location == edge) & (d.set_time_steps_yearly == 0)]
    bld = float(r["value"].iloc[0]) if not r.empty else np.nan
    tc = pd.read_csv(os.path.join(out, DATA, "capacity_addition_analysis_transport.csv"))
    tcr = tc[(tc.set_technologies == "power_line") & (tc.set_location == edge) & (tc.set_time_steps_yearly == 0)]
    capx = float(tcr.capex_specific_input_units.iloc[0]) if not tcr.empty else np.nan
    return bld, capx

clear_rate()  # crash safety
res = []
try:
    for edge in ["AT-CH", "CH-AT"]:
        ratio = ratio_op(edge)
        set_rate(edge, BASE_RATE * (1 - (1 + MARGIN) * ratio))
        vb, capb = run_read(f"{edge}_b", edge); clear_rate()
        set_rate(edge, BASE_RATE * (1 - (1 - MARGIN) * ratio))
        vn, capn = run_read(f"{edge}_n", edge); clear_rate()
        ok = (vb > VTOL) and not (vn > VTOL)
        res.append(dict(edge=edge, ratio_op=round(ratio, 3), capex_build=round(capb, 1),
                        vbuild=round(vb, 4), capex_nobuild=round(capn, 1), vnobuild=round(vn, 4),
                        result="PASS" if ok else "FAIL")); print(res[-1], flush=True)
finally:
    clear_rate()
pd.DataFrame(res).to_csv(os.path.join(ROOT, "val_tr2_summary.csv"), index=False)
print("\n" + pd.DataFrame(res).to_string(index=False)); print("DONE", ROOT)
