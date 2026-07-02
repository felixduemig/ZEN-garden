"""One-solve proof of self-cannibalisation at nuclear@ES (temporary; delete after).
Cut nuclear@ES capex to 0.5x (well past the true break-even ~11.8%) so it builds a
FINITE amount, then read how far the ES h0 electricity price collapses from 267.9.
If build>0 and price<<267.9 -> the 'value' the clean RC read was a congestion rent
that a finite build destroys = the marginal-vs-finite mechanism, measured."""
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
OUT = os.path.join(BASE, "outputs_CB_overnight", "es_finite_proof")
os.makedirs(OUT, exist_ok=True)


def cfg():
    with open("./config.json") as f: c = json.load(f)
    c.pop("plugins", None); c.setdefault("solver", {}); c["solver"].setdefault("solver_options", {})
    c["solver"]["name"] = "gurobi"; c["solver"]["save_duals"] = True
    c["solver"]["save_reduced_costs"] = False; c["solver"]["use_scaling"] = 0
    so = c["solver"]["solver_options"]; so["Method"] = 2; so["Crossover"] = 1
    so["Presolve"] = 0; so["OutputFlag"] = 0
    return c


def main():
    restore_leftover_swaps(DATASET)
    orig = read_capex(DATASET, "nuclear", "ES", 2050)
    new = orig * 0.5
    print(f"nuclear@ES capex {orig:.0f} -> {new:.0f} (0.5x)", flush=True)
    with capex_file_override(DATASET, [{"tech": "nuclear", "node": "ES", "year": 2050, "value": new}]):
        tmp = os.path.join(OUT, "_c.json"); json.dump(cfg(), open(tmp, "w"))
        run(config=tmp, dataset=DATASET, folder_output=OUT); os.remove(tmp)
    cap = pd.read_csv(os.path.join(OUT, DATA, "capacity_addition_analysis.csv"))
    b = cap[(cap.set_technologies == "nuclear") & (cap.set_location == "ES")
            & (cap.set_capacity_types == "power") & (cap.set_time_steps_yearly == 0)]
    built = float(b["value"].iloc[0]) if len(b) else np.nan
    lam = pd.read_hdf(os.path.join(OUT, DATA, "dual_dict.h5"), "constraint_nodal_energy_balance")
    es = lam[(lam.index.get_level_values("carrier") == "electricity")
             & (lam.index.get_level_values("node") == "ES")]
    t = es.index.get_level_values("time_operation")
    price = {int(tt): float(v) for tt, v in zip(t, es.values)}
    print(f"\nRESULT  nuclear@ES built = {built:.3f} GW", flush=True)
    print(f"  ES h0 price: clean 267.91  ->  now {price.get(0):.2f}   (collapse "
          f"{267.91 - price.get(0,0):.1f})", flush=True)
    print(f"  ES all-hour prices now: {{h:round(p,1) for h,p in sorted(price.items())}}"
          .replace("{h:round(p,1) for h,p in sorted(price.items())}",
                   str({h: round(p, 1) for h, p in sorted(price.items())})), flush=True)
    open(os.path.join(OUT, "result.txt"), "w").write(
        f"nuclear@ES capex {orig:.0f}->{new:.0f} (0.5x): built {built:.3f} GW; "
        f"ES h0 price 267.91 -> {price.get(0):.2f}\n")
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
