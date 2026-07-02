"""FINAL batch: the 7 cases that the first targeted run did not reach (time guard). presolve ON
(primal-only test). Generous budget so all 7 finish. Same engine as cb_validate_targeted.py;
separate output doc.
"""
import json, os, sys, time, subprocess
from datetime import datetime
import numpy as np, pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE); os.chdir(BASE)
try:
    import ctypes
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001 | 0x00000040)
except Exception:
    pass

DATASET = os.path.join(BASE, "ZEN-models", "data", "Crystal_Ball")
DATA = os.path.basename(DATASET)
RUNC = os.path.join(BASE, "outputs_CB_overnight", "runC", DATA, "capacity_addition_analysis_conversion.csv")
MARGIN, VTOL, YEAR, YIDX = 0.01, 1e-5, 2050, 0
BUDGET_S, GUARD_FACTOR, DEFAULT_CASE_S = 220 * 60, 1.2, 15 * 60

STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
ROOT = os.path.join(BASE, "outputs_CB_overnight", f"validate_targeted2_{STAMP}"); os.makedirs(ROOT, exist_ok=True)
DOC = os.path.join(BASE, "RC_report", "cb_rc_validation_targeted2.md")

CANDIDATES = [
    ("natural_gas_turbine", "BG"),       # 11.7%  swing 11.7  FLAG (peaker)
    ("methanol_from_hydrogen", "CH"),    # 14.6%  swing 6.6   FLAG
    ("natural_gas_turbine_CCS", "FI"),   # 15.6%  swing 22.2  FLAG
    ("SMR_CCS", "FI"),                   # 17.1%  swing 10.0  FLAG
    ("heat_pump_DH", "FI"),              # 26.4%  swing 0.0   rel
    ("DAC", "FR"),                       # 40.4%  swing 1.6   rel
    ("electrode_boiler", "SK"),          # 44.7%  swing 1.4   rel
]


def others_solving():
    try:
        out = subprocess.run(["tasklist", "/fi", "imagename eq python.exe", "/fo", "csv", "/nh"],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return False
    me = os.getpid(); pids = []
    for line in out.splitlines():
        p = line.replace('"', '').split(',')
        if len(p) >= 2 and p[0].lower().startswith("python"):
            try: pids.append(int(p[1]))
            except Exception: pass
    return any(x != me for x in pids)


def base_config():
    with open("./config.json") as f: c = json.load(f)
    c.pop("plugins", None); c.setdefault("solver", {}); c["solver"].setdefault("solver_options", {})
    c["solver"]["name"] = "gurobi"; c["solver"]["save_duals"] = False
    c["solver"]["save_reduced_costs"] = False; c["solver"]["use_scaling"] = 0
    so = c["solver"]["solver_options"]
    so["Method"] = 2; so["Crossover"] = 1; so["Presolve"] = 2; so["OutputFlag"] = 0
    return c


def run_read(out_name, tech, node):
    from zen_garden import run
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
    if r.empty: return None
    r = r.iloc[0]
    return dict(ratio=float(r["ratio_reduction_operational"]), rc=float(r["rc_capex_equivalent_operational_input_units"]))


def write_doc(rows, status):
    df = pd.DataFrame(rows); npass = int((df.result == "PASS").sum()) if len(df) else 0
    nfail = int((df.result == "FAIL").sum()) if len(df) else 0
    L = ["# Crystal Ball RC validation — final batch (7 remaining, presolve-on)\n",
         f"*`RC_report/cb_validate_targeted2.py`. Status: **{status}** ({datetime.now():%Y-%m-%d %H:%M}). "
         f"Outputs: `{os.path.basename(ROOT)}`.*\n",
         f"**{npass} PASS / {nfail} FAIL** of {len(df)}.\n",
         "| # | technology | node | RC ratio [%] | build@-1.01r | nobuild@-0.99r | result |",
         "|---|---|---|---:|---:|---:|---|"]
    for i, x in enumerate(rows, 1):
        vb = f"{x['v_build']:.4g}" if np.isfinite(x['v_build']) else "—"
        vn = f"{x['v_nobuild']:.4g}" if np.isfinite(x['v_nobuild']) else "—"
        L.append(f"| {i} | {x['tech']} | {x['node']} | {x['ratio_pct']:.2f} | {vb} | {vn} | **{x['result']}** |")
    open(DOC, "w", encoding="utf-8").write("\n".join(L))


def main():
    waited = 0
    while others_solving() and waited < 3600:
        print(f"[wait] another solve running... ({waited}s)", flush=True); time.sleep(20); waited += 20
    from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps
    restore_leftover_swaps(DATASET)
    rows, ctimes, t0 = [], [], time.time()
    write_doc(rows, "running (0 done)")
    for i, (tech, node) in enumerate(CANDIDATES, 1):
        if time.time() - t0 + (max(ctimes) * GUARD_FACTOR if ctimes else DEFAULT_CASE_S) > BUDGET_S:
            print(f"[time guard] stop after {(time.time()-t0)/60:.0f} min", flush=True); break
        info = lookup_ratio(tech, node)
        if info is None: print(f"[{i}] {tech}@{node}: no runC row", flush=True); continue
        ratio = info["ratio"]; cstart = time.time()
        print(f"\n[{i}/{len(CANDIDATES)}] {tech} @ {node}  ratio={ratio*100:.3f}%  (elapsed {(cstart-t0)/60:.0f} min)", flush=True)
        orig = read_capex(DATASET, tech, node, YEAR)
        with capex_file_override(DATASET, [{"tech": tech, "node": node, "year": YEAR, "value": orig*(1-(1+MARGIN)*ratio)}]):
            vb = run_read(f"c{i:02d}_{tech}_{node}_build", tech, node)
        with capex_file_override(DATASET, [{"tech": tech, "node": node, "year": YEAR, "value": orig*(1-(1-MARGIN)*ratio)}]):
            vn = run_read(f"c{i:02d}_{tech}_{node}_nobuild", tech, node)
        bb, bn = (np.isfinite(vb) and vb > VTOL), (np.isfinite(vn) and vn > VTOL); ok = bb and not bn
        ctimes.append(time.time() - cstart)
        print(f"   build->{vb:.4g} ({bb})  nobuild->{vn:.4g} ({bn})  => {'PASS' if ok else 'FAIL'}  [{ctimes[-1]/60:.1f} min]", flush=True)
        rows.append(dict(tech=tech, node=node, ratio_pct=round(ratio*100, 4), rc=round(info["rc"], 3),
                         v_build=vb, v_nobuild=vn, result="PASS" if ok else "FAIL"))
        pd.DataFrame(rows).to_csv(os.path.join(ROOT, "validate_summary.csv"), index=False)
        write_doc(rows, f"running ({len(rows)} done)")
    res = pd.DataFrame(rows)
    write_doc(rows, f"DONE — {(res.result=='PASS').sum() if len(res) else 0}P/{(res.result=='FAIL').sum() if len(res) else 0}F")
    print(f"\nDONE -> {ROOT}\n" + (res.to_string(index=False) if len(res) else "(none)"))


if __name__ == "__main__":
    main()
