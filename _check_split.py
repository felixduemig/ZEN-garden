"""Empirical proof that the storage bundle RC can be split FREELY onto power/energy:
for battery_4h IT (fixed D=4 h), realise the SAME bundle reduction Delta C_bundle three
ways -- proportional, all-on-energy, max-on-power -- and show all build the same; and that
just below the bundle RC none build. (No perturbation: real build decision.)"""
import json, os, shutil
import numpy as np, pandas as pd
from zen_garden import run
from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps

BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET = os.path.join(BASE, "6_showcase_countries_battmenu"); DATA = os.path.basename(DATASET)
SRC = os.path.join(BASE, "outputs_showcase_battmenu", DATA)
ROOT = os.path.join(BASE, "outputs_tmp_split"); os.makedirs(ROOT, exist_ok=True)
TECH, NODE, D, YEAR = "battery_4h", "IT", 4.0, 2025

st = pd.read_csv(SRC + "/capacity_addition_analysis_storage.csv")
r = st[(st.set_technologies == TECH) & (st.set_location == NODE) & (st.set_time_steps_yearly == 0)].iloc[0]
f, Cb = float(r.ratio_reduction_proportional), float(r.C_bundle)
RCb = f * Cb
cp0 = read_capex(DATASET, TECH, NODE, YEAR, "power")
ce0 = read_capex(DATASET, TECH, NODE, YEAR, "energy")
print(f"{TECH} {NODE}: f={f:.3f}  C_bundle={Cb:.0f}  RC_bundle={RCb:.0f} EUR/kW  (capex_power={cp0}, capex_energy={ce0}, D={D})")

def cfg():
    return {"analysis": {"time_series_aggregation": {"hoursPerPeriod": 1,
                "clusterMethod": "hierarchical", "extremePeriodMethod": "None"}},
            "solver": {"name": "gurobi", "save_duals": False, "save_reduced_costs": False,
                       "use_scaling": 0, "solver_options": {"Method": 2, "Crossover": 1, "Presolve": 0}}}
def run_split(name, p, e):
    out = os.path.join(ROOT, name); os.makedirs(out, exist_ok=True)
    tmp = os.path.join(out, "_c.json"); json.dump(cfg(), open(tmp, "w"), indent=2)
    ov = [{"tech": TECH, "node": NODE, "year": YEAR, "capacity_type": "power", "value": p},
          {"tech": TECH, "node": NODE, "year": YEAR, "capacity_type": "energy", "value": e}]
    with capex_file_override(DATASET, ov):
        run(config=tmp, dataset=DATASET, folder_output=out)
    os.remove(tmp)
    d = pd.read_csv(os.path.join(out, DATA, "capacity_addition_analysis.csv"))
    q = d[(d.set_technologies == TECH) & (d.set_location == NODE)
          & (d.set_capacity_types == "power") & (d.set_time_steps_yearly == 0)]
    cbnew = p + D * e
    return (float(q["value"].iloc[0]) if not q.empty else np.nan), cbnew

restore_leftover_swaps(DATASET)
dC = 1.01 * RCb   # 1% beyond the bundle RC -> should build for ANY split on the line
cases = {
    "proportional (build)":  (cp0 * (1 - 1.01 * f),           ce0 * (1 - 1.01 * f)),
    "all-on-energy (build)": (cp0,                            ce0 - dC / D),
    "max-on-power (build)":  (0.0,                            ce0 - (dC - cp0) / D),
    "proportional (nobuild)": (cp0 * (1 - 0.99 * f),          ce0 * (1 - 0.99 * f)),
}
rows = []
for name, (p, e) in cases.items():
    b, cbnew = run_split(name.split()[0] + ("_n" if "nobuild" in name else "_b"), p, e)
    rows.append(dict(split=name, new_power=round(p, 1), new_energy=round(e, 1),
                     C_bundle_new=round(cbnew, 1), battery_build=round(b, 3)))
    print(rows[-1], flush=True)
print("\n" + pd.DataFrame(rows).to_string(index=False))
shutil.rmtree(ROOT, ignore_errors=True)
print("DONE (tmp removed)")
