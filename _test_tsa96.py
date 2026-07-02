"""TSA-resolution test: does the transport RC tighten when we use MORE typical hours?
Hypothesis: CH-AT overstates (~10%) at 24h because the dual rests on 1-2 typical hours.
If true, 96 typical hours -> less concentration -> CH-AT RC accuracy improves toward AT-CH.

Procedure (separate output folder, system.json restored at the end):
  1. set aggregated_time_steps_per_year = NHOURS, run spert preset -> read transport RC
  2. for AT-CH and CH-AT: bisect the true build threshold (per-edge capex override)
  3. report predicted value (capex - RC) vs true threshold -> error %
Run also produces the 24h baseline numbers for direct comparison.
"""
import json, os, shutil
import numpy as np, pandas as pd
from zen_garden import run

BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
DATASET = os.path.join(BASE, "6_showcase_countries"); DATA = "6_showcase_countries"
SYS = os.path.join(DATASET, "system.json")
PLDIR = os.path.join(DATASET, "set_technologies", "set_transport_technologies", "power_line")
RATE_CSV = os.path.join(PLDIR, "capex_per_distance_transport.csv")
EDGES = list(pd.read_csv(os.path.join(PLDIR, "distance.csv"))["edge"].astype(str))
BASE_RATE = 546.0
CAPEX_AT_BASE = 371.28   # per-edge capex of AT-CH / CH-AT at rate 546

NHOURS = 96
ROOT = os.path.join(BASE, "outputs_showcase_96h"); os.makedirs(ROOT, exist_ok=True)

def set_rate(edge, capex):
    rate = BASE_RATE * capex / CAPEX_AT_BASE
    pd.DataFrame({"edge": EDGES,
        "capex_per_distance_transport": [rate if e == edge else BASE_RATE for e in EDGES]
    }).to_csv(RATE_CSV, index=False)
def clear_rate():
    if os.path.isfile(RATE_CSV): os.remove(RATE_CSV)

def cfg(save_duals):
    c = {"analysis": {"time_series_aggregation": {"hoursPerPeriod": 1,
            "clusterMethod": "hierarchical", "extremePeriodMethod": "None"}},
         "solver": {"name": "gurobi", "save_duals": save_duals, "save_reduced_costs": False,
                    "use_scaling": 0,
                    "solver_options": {"Method": 2, "Crossover": 1, "Presolve": 0,
                                       "rc_perturbation": 0,
                                       "rc_storage_power_perturbation": 1e-4,
                                       "rc_tight_e2p": {"battery": 4}}}}
    return c

def do_run(name, save_duals):
    out = os.path.join(ROOT, name); os.makedirs(out, exist_ok=True)
    tmp = os.path.join(out, "_c.json"); json.dump(cfg(save_duals), open(tmp, "w"))
    run(config=tmp, dataset=DATASET, folder_output=out); os.remove(tmp)
    return os.path.join(out, DATA)

def read_build(folder, edge):
    d = pd.read_csv(os.path.join(folder, "capacity_addition_analysis.csv"))
    r = d[(d.set_technologies == "power_line") & (d.set_location == edge) &
          (d.set_capacity_types == "power") & (d.set_time_steps_yearly == 0)]
    return float(r["value"].iloc[0]) if not r.empty else np.nan

# ---- back up + set system.json ----
sys_orig = open(SYS).read()
clear_rate()
results = {}
try:
    s = json.loads(sys_orig); s["aggregated_time_steps_per_year"] = NHOURS
    json.dump(s, open(SYS, "w"), indent=2)
    print(f"=== system set to {NHOURS} typical hours ===", flush=True)

    # 1. main run with duals -> RC
    f = do_run("main", True); clear_rate()
    tr = pd.read_csv(os.path.join(f, "capacity_addition_analysis_transport.csv"))
    tr = tr[tr.set_time_steps_yearly == 0]
    for edge in ["AT-CH", "CH-AT"]:
        r = tr[(tr.set_technologies == "power_line") & (tr.set_location == edge)]
        rc = float(r["rc_capex_equivalent_operational"].iloc[0])
        capex = float(r["capex_specific_input_units"].iloc[0])
        results[edge] = {"capex": capex, "rc": rc, "pred_value": capex - rc,
                         "ratio": rc / capex}
        print(f"{edge}: capex={capex:.2f} RC={rc:.2f} pred_value={capex-rc:.2f} ratio={rc/capex:.4f}", flush=True)

    # 2. bisect threshold around the predicted value
    for edge in ["AT-CH", "CH-AT"]:
        v = results[edge]["pred_value"]
        grid = sorted({round(v * fr, 3) for fr in [1.08, 1.03, 0.99, 0.95, 0.90, 0.84]}, reverse=True)
        curve = []
        for capex in grid:
            set_rate(edge, capex)
            b = read_build(do_run(f"{edge}_{capex}", False), edge); clear_rate()
            curve.append((capex, b))
            print(f"   {edge}  capex={capex:8.3f} -> build={b:.6f} GW", flush=True)
        results[edge]["curve"] = curve
finally:
    open(SYS, "w").write(sys_orig)   # restore 24h
    clear_rate()
    print("=== system.json restored ===", flush=True)

# ---- report ----
print("\n================ TSA-96h RESULT ================")
for edge in ["AT-CH", "CH-AT"]:
    r = results[edge]; v = r["pred_value"]
    curve = sorted(r["curve"])  # ascending capex
    # threshold = highest capex that still builds (>1e-4), interpolated with next
    thr = None
    builds = [(c, b) for c, b in curve]
    for i in range(len(builds) - 1):
        c_lo, b_lo = builds[i]; c_hi, b_hi = builds[i + 1]
        if b_lo > 1e-4 and b_hi <= 1e-4:
            thr = c_lo + (c_hi - c_lo) * (b_lo - 1e-4) / (b_lo - b_hi)
            break
    if thr is None:
        thr = builds[0][0] if builds[0][1] > 1e-4 else builds[-1][0]
    err = 100 * (v - thr) / thr
    print(f"{edge}: pred_value={v:.2f}  true_threshold~={thr:.2f}  error={err:+.1f}%")
print("(24h baseline: AT-CH ~+0.5%, CH-AT ~+11%)")
print("DONE", ROOT)
