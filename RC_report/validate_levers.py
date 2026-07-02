"""Validate lever equivalence on the showcase via the +-1% build/nobuild test.
Same build margin, reached through a NON-capex lever, must build at -(1+1%)*predicted
and not at -(1-1%)*predicted. Per-node overrides (ceteris paribus). Four variants:
  PV@DE   : capex<->capacity factor   (eps = RC/(capex-RC+opex_fix/af))
  PV@DE   : capex<->fixed opex         (df  = af*RC)
  GT@FR   : capex<->variable opex      (dv  = af*RC/E),  E = annual generation per kW
  GT@FR   : capex<->fixed opex         (df  = af*RC)
"""
import os, json, shutil
from datetime import datetime
import numpy as np, pandas as pd
from zen_garden import run

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(BASE)
DS   = os.path.join(BASE, "6_showcase_countries")
CONV = os.path.join(DS, "set_technologies", "set_conversion_technologies")
BOUT = os.path.join(BASE, "outputs_showcase_storage_only", "6_showcase_countries")
ROOT = os.path.join(BASE, "outputs_showcase_levers", datetime.now().strftime("%H%M%S"))
os.makedirs(ROOT, exist_ok=True)
NODES = ["AT", "CH", "DE", "FR", "IT"]; YEARS = [2025, 2026, 2027]
r, lt = 0.06, 30
af = ((1 + r) ** lt * r) / ((1 + r) ** lt - 1)

# ---- base reduced costs ----------------------------------------------------
conv = pd.read_csv(os.path.join(BOUT, "capacity_addition_analysis_conversion.csv"))
def rc(tech, node):
    row = conv[(conv.set_technologies == tech) & (conv.set_location == node) & (conv.set_time_steps_yearly == 0)].iloc[0]
    return float(row["rc_capex_equivalent_operational_input_units"]), float(row["capex_specific_input_units"])
RC_pv, capex_pv = rc("photovoltaics", "DE");        opexf_pv = 12.0
RC_gt, capex_gt = rc("natural_gas_turbine", "FR");  opexf_gt, opexv_gt = 22.0, 2.9

# ---- E = annual generation per kW for the unbuilt GT@FR (year-0 running steps) ----
nu  = pd.read_hdf(os.path.join(BOUT, "dual_dict.h5"), "constraint_capacity_factor_conversion")
dur = pd.read_hdf(os.path.join(BOUT, "param_dict.h5"), "time_steps_operation_duration")
gt = nu[(nu.index.get_level_values("technology") == "natural_gas_turbine") & (nu.index.get_level_values("node") == "FR")]
gt = gt.reset_index(); gt.columns = ["t", "tech", "node", "nu"]
y0 = gt[(gt.t < 24) & (gt.nu.abs() > 1e-9)]              # year-0 typical steps where it would run
E = float((0.93 * dur.loc[y0.t.values].values).sum())   # 0.93 = GT max_load (availability)

# ---- predictions (relative for CF, absolute for opex) ----------------------
eps_pv = RC_pv / (capex_pv - RC_pv + opexf_pv / af)      # CF: relative increase
dfo_pv = af * RC_pv                                       # fixed opex: EUR/kW/yr reduction
dfo_gt = af * RC_gt
dvo_gt = af * RC_gt / E                                   # var opex: EUR/MWh reduction
print(f"af={af:.5f}  E(GT@FR annual gen/kW)={E:.1f}")
print(f"PV@DE RC={RC_pv:.2f} -> CF +{eps_pv*100:.2f}% | fixedopex -{dfo_pv:.3f} EUR/kW/yr")
print(f"GT@FR RC={RC_gt:.2f} -> varopex -{dvo_gt:.3f} EUR/MWh | fixedopex -{dfo_gt:.3f} EUR/kW/yr")

# ---- override helpers (backup -> write -> run -> restore) ------------------
def grid_csv(col, default, node, value):
    rows = [[n, y, (value if (n == node) else default)] for n in NODES for y in YEARS]
    return pd.DataFrame(rows, columns=["node", "year", col])

class override:
    def __init__(self, paths_writes):  # list of (path, df_or_None_for_maxload_scale)
        self.items = paths_writes
    def __enter__(self):
        self.baks = []
        for path, df in self.items:
            bak = path + ".bak"
            if os.path.isfile(path): shutil.copy2(path, bak)
            df.to_csv(path, index=False); self.baks.append((path, bak))
    def __exit__(self, *a):
        for path, bak in self.baks:
            if os.path.isfile(bak): shutil.move(bak, path)
            elif os.path.isfile(path): os.remove(path)

def cfg():
    return {"solver": {"name": "gurobi", "save_duals": False, "save_reduced_costs": False,
            "use_scaling": 0, "solver_options": {"Method": 2, "Crossover": 1, "Presolve": 0, "OutputFlag": 0}}}

def run_built(tech, node, tag):
    out = os.path.join(ROOT, tag); os.makedirs(out, exist_ok=True)
    tmp = os.path.join(out, "_c.json"); json.dump(cfg(), open(tmp, "w"))
    run(config=tmp, dataset=DS, folder_output=out)
    d = pd.read_csv(os.path.join(out, "6_showcase_countries", "capacity_addition_analysis.csv"))
    row = d[(d.set_technologies == tech) & (d.set_capacity_types == "power") & (d.set_location == node) & (d.set_time_steps_yearly == 0)]
    return float(row["value"].iloc[0]) if len(row) else np.nan

def maxload_scaled(tech, node, factor):
    p = os.path.join(CONV, tech, "max_load.csv"); m = pd.read_csv(p); m[node] = m[node] * factor
    return p, m

def opex_override(tech, node, col, default, value):
    return os.path.join(CONV, tech, col + ".csv"), grid_csv(col, default, node, value)

VTOL = 1e-3
def test(name, tech, node, make_override, pred, rel=False):
    # build point: 1.01x predicted reduction; nobuild: 0.99x
    res = {}
    for lab, k in [("build", 1.01), ("nobuild", 0.99)]:
        ov = make_override(k * pred)
        with override([ov]):
            res[lab] = run_built(tech, node, f"{name.replace(' ','_')}_{lab}")
    ok = (res["build"] > VTOL) and not (res["nobuild"] > VTOL)
    print(f"[{name:18s}] build={res['build']:.4g} nobuild={res['nobuild']:.4g} -> {'PASS' if ok else 'FAIL'}", flush=True)
    return dict(name=name, **res, result="PASS" if ok else "FAIL")

rows = []
# PV CF: scale DE max_load by (1+ s)
rows.append(test("PV CF", "photovoltaics", "DE",
                 lambda s: maxload_scaled("photovoltaics", "DE", 1 + s), eps_pv, rel=True))
# PV fixed opex: DE opex_fixed = 12 - s
rows.append(test("PV fixed-opex", "photovoltaics", "DE",
                 lambda s: opex_override("photovoltaics", "DE", "opex_specific_fixed", opexf_pv, opexf_pv - s), dfo_pv))
# GT var opex: FR opex_variable = 2.9 - s  (may go negative = fuel subsidy)
rows.append(test("GT var-opex", "natural_gas_turbine", "FR",
                 lambda s: opex_override("natural_gas_turbine", "FR", "opex_specific_variable", opexv_gt, opexv_gt - s), dvo_gt))
# GT fixed opex: FR opex_fixed = 22 - s
rows.append(test("GT fixed-opex", "natural_gas_turbine", "FR",
                 lambda s: opex_override("natural_gas_turbine", "FR", "opex_specific_fixed", opexf_gt, opexf_gt - s), dfo_gt))

df = pd.DataFrame(rows); df.to_csv(os.path.join(ROOT, "lever_validation.csv"), index=False)
print("\n" + df.to_string(index=False))
print(f"\n{(df.result=='PASS').sum()}/{len(df)} PASS -> {ROOT}")
