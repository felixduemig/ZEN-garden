"""+-1% build/nobuild validation of 5 ROBUST Crystal Ball conversion RCs (clean ground
truth via the data-CSV capex swap). 5 distinct techs x 4 countries, all perturbation-stable
(swing < 0.002 between runC and runB) -> expected to PASS, proving RC interpretability works
in CB at well-behaved tech-nodes. Sequential (shared CAPEX file): 5 cases x 2 runs ~ 110 min.

build   : capex = orig*(1 - 1.01*ratio)  -> must build
nobuild : capex = orig*(1 - 0.99*ratio)  -> must NOT build
ratio = clean (run C) operational RC ratio.
"""
import json, os
from datetime import datetime
import numpy as np, pandas as pd
from zen_garden import run
from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(BASE)
DATASET = os.path.join(BASE, "ZEN-models", "data", "Crystal_Ball")
DATA = os.path.basename(DATASET)
MARGIN = 0.01
VTOL = 1e-5
ROOT = os.path.join(BASE, "outputs_CB_overnight", f"validate5_{datetime.now():%Y%m%d-%H%M%S}")
os.makedirs(ROOT, exist_ok=True)

CASES = [
    {"tech": "photovoltaics",      "node": "NO", "year": 2050, "yidx": 0, "ratio": 0.215210, "label": "op_C clean"},
    {"tech": "wind_onshore",       "node": "NO", "year": 2050, "yidx": 0, "ratio": 0.165792, "label": "op_C clean"},
    {"tech": "wind_offshore",      "node": "FR", "year": 2050, "yidx": 0, "ratio": 0.111820, "label": "op_C clean"},
    {"tech": "run-of-river_hydro", "node": "SK", "year": 2050, "yidx": 0, "ratio": 0.128073, "label": "op_C clean"},
    {"tech": "reservoir_hydro",    "node": "CH", "year": 2050, "yidx": 0, "ratio": 0.244228, "label": "op_C clean"},
]

def base_config():
    with open("./config.json") as f: c = json.load(f)
    c.pop("plugins", None)
    c.setdefault("solver", {}); c["solver"].setdefault("solver_options", {})
    c["solver"]["name"] = "gurobi"; c["solver"]["save_duals"] = False
    c["solver"]["save_reduced_costs"] = False; c["solver"]["use_scaling"] = 0
    so = c["solver"]["solver_options"]; so["Method"] = 2; so["Crossover"] = 1
    so["Presolve"] = 0; so["OutputFlag"] = 0
    return c

def run_read(out_name, tech, node, yidx):
    out = os.path.join(ROOT, out_name); os.makedirs(out, exist_ok=True)
    tmp = os.path.join(out, "_c.json"); json.dump(base_config(), open(tmp, "w"))
    run(config=tmp, dataset=DATASET, folder_output=out); os.remove(tmp)
    f = os.path.join(out, DATA, "capacity_addition_analysis.csv")
    df = pd.read_csv(f)
    r = df[(df.set_technologies == tech) & (df.set_capacity_types == "power")
           & (df.set_location == node) & (df.set_time_steps_yearly == yidx)]
    return float(r["value"].iloc[0]) if not r.empty else np.nan

def main():
    restore_leftover_swaps(DATASET)
    rows = []
    for i, c in enumerate(CASES, 1):
        tech, node, year, yidx, ratio = c["tech"], c["node"], c["year"], c["yidx"], c["ratio"]
        lab = c.get("label", "")
        print(f"\n[{i}/{len(CASES)}] {tech} @ {node} ({year}) ratio={ratio*100:.3f}% [{lab}]", flush=True)
        orig = read_capex(DATASET, tech, node, year)
        nb_build = orig * (1 - (1 + MARGIN) * ratio)
        nb_nobuild = orig * (1 - (1 - MARGIN) * ratio)
        with capex_file_override(DATASET, [{"tech": tech, "node": node, "year": year, "value": nb_build}]):
            vb = run_read(f"c{i:02d}_{tech}_{node}_build", tech, node, yidx)
        with capex_file_override(DATASET, [{"tech": tech, "node": node, "year": year, "value": nb_nobuild}]):
            vn = run_read(f"c{i:02d}_{tech}_{node}_nobuild", tech, node, yidx)
        built_b, built_n = (np.isfinite(vb) and vb > VTOL), (np.isfinite(vn) and vn > VTOL)
        ok = built_b and not built_n
        print(f"   orig={orig:.2f} build@{nb_build:.2f}->{vb:.4g} ({built_b}) "
              f"nobuild@{nb_nobuild:.2f}->{vn:.4g} ({built_n}) => {'PASS' if ok else 'FAIL'}", flush=True)
        rows.append(dict(tech=tech, node=node, ratio_pct=round(ratio*100, 4), label=lab,
                         orig_capex=round(orig, 3), v_build=vb, v_nobuild=vn,
                         built_build=built_b, built_nobuild=built_n, result="PASS" if ok else "FAIL"))
        pd.DataFrame(rows).to_csv(os.path.join(ROOT, "validate_summary.csv"), index=False)
    res = pd.DataFrame(rows)
    print("\n" + res.to_string(index=False))
    print(f"\n{(res.result=='PASS').sum()}/{len(res)} PASS  ->  {ROOT}")

if __name__ == "__main__":
    main()
