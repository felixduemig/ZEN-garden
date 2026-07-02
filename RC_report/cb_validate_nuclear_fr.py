"""Focused +-1% validation of nuclear @ FR (clean operational RC, ratio 72.84%).
Critical test: low perturbation swing (0.062 pp) says "reliable" for the canonical
self-cannibalising tech -> does it actually PASS? Same harness as cb_validate_batch.py.

build   : capex = orig*(1 - 1.01*r) -> must build
nobuild : capex = orig*(1 - 0.99*r) -> must NOT build
"""
import json, os, sys, time
from datetime import datetime
import numpy as np, pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE); os.chdir(BASE)
try:
    import ctypes
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001 | 0x00000040)
except Exception:
    pass
from zen_garden import run
from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps

DATASET = os.path.join(BASE, "ZEN-models", "data", "Crystal_Ball")
DATA = os.path.basename(DATASET)
RUNC = os.path.join(BASE, "outputs_CB_overnight", "runC", DATA,
                    "capacity_addition_analysis_conversion.csv")
TECH, NODE, YEAR, YIDX = "nuclear", "FR", 2050, 0
MARGIN, VTOL = 0.01, 1e-5
STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
ROOT = os.path.join(BASE, "outputs_CB_overnight", f"validate_nuclearFR_{STAMP}")
os.makedirs(ROOT, exist_ok=True)
DOC = os.path.join(BASE, "RC_report", "cb_nuclear_fr_result.md")


def base_config():
    with open("./config.json") as f:
        c = json.load(f)
    c.pop("plugins", None)
    c.setdefault("solver", {}); c["solver"].setdefault("solver_options", {})
    c["solver"]["name"] = "gurobi"; c["solver"]["save_duals"] = False
    c["solver"]["save_reduced_costs"] = False; c["solver"]["use_scaling"] = 0
    so = c["solver"]["solver_options"]
    so["Method"] = 2; so["Crossover"] = 1; so["Presolve"] = 0; so["OutputFlag"] = 0
    return c


def run_read(out_name):
    out = os.path.join(ROOT, out_name); os.makedirs(out, exist_ok=True)
    tmp = os.path.join(out, "_c.json"); json.dump(base_config(), open(tmp, "w"))
    run(config=tmp, dataset=DATASET, folder_output=out); os.remove(tmp)
    df = pd.read_csv(os.path.join(out, DATA, "capacity_addition_analysis.csv"))
    r = df[(df.set_technologies == TECH) & (df.set_capacity_types == "power")
           & (df.set_location == NODE) & (df.set_time_steps_yearly == YIDX)]
    return float(r["value"].iloc[0]) if not r.empty else np.nan


def main():
    restore_leftover_swaps(DATASET)
    c = pd.read_csv(RUNC)
    row = c[(c.set_technologies == TECH) & (c.set_location == NODE)
            & (c.set_time_steps_yearly == YIDX)].iloc[0]
    ratio = float(row["ratio_reduction_operational"])
    orig = read_capex(DATASET, TECH, NODE, YEAR)
    nb_b = orig * (1 - (1 + MARGIN) * ratio)
    nb_n = orig * (1 - (1 - MARGIN) * ratio)
    t0 = time.time()
    print(f"nuclear@FR  ratio={ratio*100:.3f}%  orig_capex(native)={orig:.4g}", flush=True)
    print(f"  build@{nb_b:.4g}  nobuild@{nb_n:.4g}", flush=True)
    with capex_file_override(DATASET, [{"tech": TECH, "node": NODE, "year": YEAR, "value": nb_b}]):
        vb = run_read("build")
    print(f"  build solve done ({(time.time()-t0)/60:.1f} min) -> {vb:.4g}", flush=True)
    with capex_file_override(DATASET, [{"tech": TECH, "node": NODE, "year": YEAR, "value": nb_n}]):
        vn = run_read("nobuild")
    bb, bn = (np.isfinite(vb) and vb > VTOL), (np.isfinite(vn) and vn > VTOL)
    ok = bb and not bn
    res = "PASS" if ok else "FAIL"
    print(f"\n  build->{vb:.4g} ({bb})  nobuild->{vn:.4g} ({bn})  => {res}  "
          f"[{(time.time()-t0)/60:.1f} min total]", flush=True)
    pd.DataFrame([dict(tech=TECH, node=NODE, ratio_pct=round(ratio*100, 4),
                       rc=round(float(row["rc_capex_equivalent_operational_input_units"]), 2),
                       orig_capex=round(orig, 3), v_build=vb, v_nobuild=vn,
                       result=res)]).to_csv(os.path.join(ROOT, "result.csv"), index=False)
    with open(DOC, "w", encoding="utf-8") as f:
        f.write(f"# nuclear @ FR — ±1% validation\n\n"
                f"*{datetime.now():%Y-%m-%d %H:%M}, `{os.path.basename(ROOT)}`.*\n\n"
                f"Clean operational RC ratio **{ratio*100:.2f}%** (RC {row['rc_capex_equivalent_operational_input_units']:.0f} EUR/kW), "
                f"perturbation swing **0.062 pp** → flagged *reliable*.\n\n"
                f"| point | capex (native) | build [GW] |\n|---|---:|---:|\n"
                f"| build  (−1.01·r) | {nb_b:.4g} | {vb:.4g} |\n"
                f"| nobuild (−0.99·r) | {nb_n:.4g} | {vn:.4g} |\n\n"
                f"**Result: {res}.** "
                + ("The low-swing *reliable* flag is confirmed — the operational RC pins the "
                   "build threshold to ±1% even for nuclear, at a well-connected node, when the "
                   "distance is large and the dual is unique.\n" if ok else
                   "Despite the low swing, the RC does NOT pin the threshold here — a reliability "
                   "blind spot worth investigating (build "
                   f"{'identical at both points (pinning?)' if abs(vb-vn)<1e-3 else 'pattern inconsistent'}).\n"))
    print(f"  -> {DOC}")


if __name__ == "__main__":
    main()
