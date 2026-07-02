"""+-1% build/nobuild validation for TRANSPORT (lifetime RC), storage-only run.
power_line AT-CH / CH-AT are the only buildable edges (ratio<1); also check a
ratio>1 edge does not build even at capex~0."""
import json, os
from datetime import datetime
import numpy as np, pandas as pd
from zen_garden import run
from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps

BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET = os.path.join(BASE, "6_showcase_countries"); DATA = os.path.basename(DATASET)
SRC = os.path.join(BASE, "outputs_showcase_storage_only", DATA)
MARGIN = 0.01; REFY = 2025; VTOL = 1e-4
ROOT = os.path.join(BASE, f"outputs_{datetime.now():%Y%m%d-%H%M%S}_val_transport")
os.makedirs(ROOT, exist_ok=True)

tr = pd.read_csv(SRC + "/capacity_addition_analysis_transport.csv")
def rc_of(edge, y=0):
    r = tr[(tr.set_technologies == "power_line") & (tr.set_location == edge)
           & (tr.set_time_steps_yearly == y)]
    return (float(r.rc_capex_equivalent_input_units.iloc[0]),
            float(r.ratio_reduction.iloc[0]))

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
def valc(sc, tech, edge, y=0):
    d = pd.read_csv(os.path.join(sc, "capacity_addition_analysis.csv"))
    r = d[(d.set_technologies == tech) & (d.set_location == edge) & (d.set_time_steps_yearly == y)]
    return float(r["value"].iloc[0]) if not r.empty else np.nan

restore_leftover_swaps(DATASET); res = []

for edge in ["AT-CH", "CH-AT"]:
    rc, ratio = rc_of(edge); year = REFY; capex = read_capex(DATASET, "power_line", edge, year)
    cb = capex * (1 - (1 + MARGIN) * ratio); cn = capex * (1 - (1 - MARGIN) * ratio)
    with capex_file_override(DATASET, [{"tech": "power_line", "node": edge, "year": year, "value": cb}]):
        vb = valc(run_model(f"power_line_{edge}_b"), "power_line", edge)
    with capex_file_override(DATASET, [{"tech": "power_line", "node": edge, "year": year, "value": cn}]):
        vn = valc(run_model(f"power_line_{edge}_n"), "power_line", edge)
    ok = (vb > VTOL) and not (vn > VTOL)
    res.append(dict(tech="power_line", edge=edge, rc=round(rc, 1), ratio=round(ratio, 3),
                    vbuild=round(vb, 4), vnobuild=round(vn, 4),
                    result="PASS" if ok else "FAIL")); print(res[-1], flush=True)

# ratio>1 edge: must NOT build even at capex~1
with capex_file_override(DATASET, [{"tech": "power_line", "node": "AT-DE", "year": REFY, "value": 1.0}]):
    vfree = valc(run_model("power_line_AT-DE_free"), "power_line", "AT-DE")
res.append(dict(tech="power_line", edge="AT-DE", rc="ratio>1", ratio=">1",
                vbuild=round(vfree, 4), vnobuild="-",
                result="PASS (no build @ capex~0)" if vfree <= VTOL else "FAIL (builds!)"))
print(res[-1], flush=True)

pd.DataFrame(res).to_csv(os.path.join(ROOT, "val_transport_summary.csv"), index=False)
print("\n" + pd.DataFrame(res).to_string(index=False)); print("DONE", ROOT)
