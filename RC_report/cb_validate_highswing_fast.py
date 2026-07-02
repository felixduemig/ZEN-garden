"""Fast +-1% build/nobuild test of the 2 remaining high-swing cases (haber_bosch@SE,
natural_gas_turbine_CCS@FR) that the earlier run could not reach (SMR@SK took 21 h).

KEY: the build/nobuild test only reads the PRIMAL capacity_addition (does it build?), NOT the
duals/RC. So Presolve may be turned ON here -- it does not change the primal optimum but avoids
the pathological barrier slowdown. (RC values themselves still come from runC with Presolve 0.)
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
MARGIN = 0.01
VTOL = 1e-5
YEAR, YIDX = 2050, 0

STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
ROOT = os.path.join(BASE, "outputs_CB_overnight", f"validate_highswing_fast_{STAMP}")
os.makedirs(ROOT, exist_ok=True)
DOC = os.path.join(BASE, "RC_report", "cb_rc_validation_highswing_fast.md")

CANDIDATES = [
    ("haber_bosch", "SE"),              # 79.3%  swing 73
    ("natural_gas_turbine_CCS", "FR"),  # 84.0%  swing 53
]


def base_config():
    with open("./config.json") as f:
        c = json.load(f)
    c.pop("plugins", None)
    c.setdefault("solver", {}); c["solver"].setdefault("solver_options", {})
    c["solver"]["name"] = "gurobi"; c["solver"]["save_duals"] = False
    c["solver"]["save_reduced_costs"] = False; c["solver"]["use_scaling"] = 0
    so = c["solver"]["solver_options"]
    so["Method"] = 2; so["Crossover"] = 1; so["Presolve"] = 2; so["OutputFlag"] = 0  # presolve ON (primal-only test)
    return c


def run_read(out_name, tech, node):
    out = os.path.join(ROOT, out_name); os.makedirs(out, exist_ok=True)
    tmp = os.path.join(out, "_c.json"); json.dump(base_config(), open(tmp, "w"))
    run(config=tmp, dataset=DATASET, folder_output=out); os.remove(tmp)
    df = pd.read_csv(os.path.join(out, DATA, "capacity_addition_analysis.csv"))
    r = df[(df.set_technologies == tech) & (df.set_capacity_types == "power")
           & (df.set_location == node) & (df.set_time_steps_yearly == YIDX)]
    return float(r["value"].iloc[0]) if not r.empty else np.nan


def lookup_ratio(tech, node):
    c = pd.read_csv(RUNC)
    r = c[(c.set_technologies == tech) & (c.set_location == node) & (c.set_time_steps_yearly == YIDX)]
    if r.empty:
        return None
    r = r.iloc[0]
    return dict(ratio=float(r["ratio_reduction_operational"]),
                rc=float(r["rc_capex_equivalent_operational_input_units"]),
                capex=float(r["capex_specific_input_units"]))


def write_doc(rows, status):
    L = ["# Crystal Ball RC validation — high-swing remainder (presolve-on, primal-only)\n",
         f"*`RC_report/cb_validate_highswing_fast.py`. Status: **{status}** "
         f"({datetime.now():%Y-%m-%d %H:%M}).*\n",
         "The 2 high-swing cases the earlier run could not reach. Presolve ON (valid: this reads "
         "only the primal build, not the RC). High swing predicts a lower bound -> expected FAIL.\n",
         "| # | technology | node | RC ratio [%] | build@-1.01r [GW] | nobuild@-0.99r [GW] | result |",
         "|---|---|---|---:|---:|---:|---|"]
    for i, x in enumerate(rows, 1):
        vb = f"{x['v_build']:.4g}" if np.isfinite(x['v_build']) else "—"
        vn = f"{x['v_nobuild']:.4g}" if np.isfinite(x['v_nobuild']) else "—"
        L.append(f"| {i} | {x['tech']} | {x['node']} | {x['ratio_pct']:.2f} | {vb} | {vn} | **{x['result']}** |")
    open(DOC, "w", encoding="utf-8").write("\n".join(L))


def main():
    restore_leftover_swaps(DATASET)
    rows = []
    write_doc(rows, "running")
    for i, (tech, node) in enumerate(CANDIDATES, 1):
        info = lookup_ratio(tech, node)
        if info is None:
            print(f"[{i}] {tech}@{node}: no runC row, skip", flush=True); continue
        ratio = info["ratio"]
        print(f"\n[{i}/{len(CANDIDATES)}] {tech} @ {node}  ratio={ratio*100:.3f}%", flush=True)
        cstart = time.time()
        orig = read_capex(DATASET, tech, node, YEAR)
        with capex_file_override(DATASET, [{"tech": tech, "node": node, "year": YEAR, "value": orig*(1-(1+MARGIN)*ratio)}]):
            vb = run_read(f"c{i:02d}_{tech}_{node}_build", tech, node)
        with capex_file_override(DATASET, [{"tech": tech, "node": node, "year": YEAR, "value": orig*(1-(1-MARGIN)*ratio)}]):
            vn = run_read(f"c{i:02d}_{tech}_{node}_nobuild", tech, node)
        bb, bn = (np.isfinite(vb) and vb > VTOL), (np.isfinite(vn) and vn > VTOL)
        ok = bb and not bn
        print(f"   build->{vb:.4g} ({bb})  nobuild->{vn:.4g} ({bn})  => "
              f"{'PASS' if ok else 'FAIL'}  [{(time.time()-cstart)/60:.1f} min]", flush=True)
        rows.append(dict(tech=tech, node=node, ratio_pct=round(ratio*100, 4), rc=round(info["rc"], 3),
                         v_build=vb, v_nobuild=vn, result="PASS" if ok else "FAIL"))
        pd.DataFrame(rows).to_csv(os.path.join(ROOT, "validate_summary.csv"), index=False)
        write_doc(rows, f"running ({len(rows)} done)")
    write_doc(rows, "DONE")
    print(f"\nDONE -> {ROOT}")
    print(pd.DataFrame(rows).to_string(index=False) if rows else "(none)")


if __name__ == "__main__":
    main()
