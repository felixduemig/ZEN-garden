"""Capex sweep for nuclear@ES to find the TRUE break-even and the build curve
(temporary; delete after). For each cut, set capex=orig*(1-cut), re-solve, read
the built nuclear@ES capacity. Brackets the break-even between the known points
(0% and 11.7% -> 0 GW; 50% -> 7.16 GW)."""
import json, os, sys
import pandas as pd, numpy as np
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE); os.chdir(BASE)
try:
    import ctypes
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001 | 0x00000040)
except Exception:
    pass
from zen_garden import run
from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps

DATASET = os.path.join(BASE, "ZEN-models", "data", "Crystal_Ball"); DATA = "Crystal_Ball"
ROOT = os.path.join(BASE, "outputs_CB_overnight", "es_sweep"); os.makedirs(ROOT, exist_ok=True)
CUTS = [0.08, 0.15, 0.22, 0.30, 0.40]   # fraction capex reduction


def cfg():
    with open("./config.json") as f: c = json.load(f)
    c.pop("plugins", None); c.setdefault("solver", {}); c["solver"].setdefault("solver_options", {})
    c["solver"]["name"] = "gurobi"; c["solver"]["save_duals"] = False
    c["solver"]["save_reduced_costs"] = False; c["solver"]["use_scaling"] = 0
    so = c["solver"]["solver_options"]; so["Method"] = 2; so["Crossover"] = 1
    so["Presolve"] = 0; so["OutputFlag"] = 0
    return c


def main():
    restore_leftover_swaps(DATASET)
    orig = read_capex(DATASET, "nuclear", "ES", 2050)
    print(f"nuclear@ES orig capex = {orig:.0f}; known: 0%->0, 11.7%->0, 50%->7.16 GW", flush=True)
    rows = []
    for cut in CUTS:
        new = orig * (1 - cut)
        with capex_file_override(DATASET, [{"tech": "nuclear", "node": "ES", "year": 2050, "value": new}]):
            out = os.path.join(ROOT, f"cut{int(cut*100)}"); os.makedirs(out, exist_ok=True)
            tmp = os.path.join(out, "_c.json"); json.dump(cfg(), open(tmp, "w"))
            run(config=tmp, dataset=DATASET, folder_output=out); os.remove(tmp)
        cap = pd.read_csv(os.path.join(out, DATA, "capacity_addition_analysis.csv"))
        b = cap[(cap.set_technologies == "nuclear") & (cap.set_location == "ES")
                & (cap.set_capacity_types == "power") & (cap.set_time_steps_yearly == 0)]
        built = float(b["value"].iloc[0]) if len(b) else np.nan
        rows.append((cut, new, built))
        print(f"  cut {cut*100:>4.1f}%  capex {new:>6.0f}  -> built {built:>7.3f} GW", flush=True)
        pd.DataFrame(rows, columns=["cut", "capex", "built_GW"]).to_csv(
            os.path.join(ROOT, "sweep.csv"), index=False)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
