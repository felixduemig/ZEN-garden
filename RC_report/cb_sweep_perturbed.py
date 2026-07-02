"""For a few SWING-FLAGGED (degenerate) cases, bracket the TRUE break-even via a small capex sweep
(presolve ON -- reads only the primal build) and compare it against op_C (clean operational RC,
runC) and op_B (rhs-perturbed RC, runB). Goal: more 'nuclear@ES-style' comparison rows showing
clean < perturbed <= true, i.e. that the perturbed value is a TIGHTER lower bound, not the truth.

For each case: cuts = {op_B, op_B+5pp, op_B+12pp, op_B+25pp} (clipped to (op_C, 55%]); the smallest
cut at which capacity_addition>0 brackets the true break-even (the build is a step 0->ceiling).
Waits for any other solve to finish; crash-safe; separate doc.
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
RUNB = os.path.join(BASE, "outputs_CB_overnight", "runB", DATA, "capacity_addition_analysis_conversion.csv")
VTOL, YEAR, YIDX = 1e-5, 2050, 0
BUDGET_S = 230 * 60

STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
ROOT = os.path.join(BASE, "outputs_CB_overnight", f"sweep_perturbed_{STAMP}"); os.makedirs(ROOT, exist_ok=True)
DOC = os.path.join(BASE, "RC_report", "cb_sweep_perturbed.md")

# degenerate (class-1) flagged cases with moderate swing -> testable sweep range
CASES = [
    ("nuclear", "FI"),                  # op_C 2.2%, swing 8.4   (mirror of nuclear@ES)
    ("electrolysis", "FI"),             # the original flexible-load FAIL
    ("methanol_from_hydrogen", "CZ"),   # op_C 9.0%, swing 8.0
    ("SMR_CCS", "SE"),                  # op_C 6.3%, swing 10.8
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


def solve_built(out_name, tech, node):
    from zen_garden import run
    out = os.path.join(ROOT, out_name); os.makedirs(out, exist_ok=True)
    tmp = os.path.join(out, "_c.json"); json.dump(base_config(), open(tmp, "w"))
    run(config=tmp, dataset=DATASET, folder_output=out); os.remove(tmp)
    df = pd.read_csv(os.path.join(out, DATA, "capacity_addition_analysis.csv"))
    r = df[(df.set_technologies == tech) & (df.set_capacity_types == "power")
           & (df.set_location == node) & (df.set_time_steps_yearly == YIDX)]
    return float(r["value"].iloc[0]) if not r.empty else np.nan


def ratio_from(path, tech, node):
    c = pd.read_csv(path)
    r = c[(c.set_technologies == tech) & (c.set_location == node) & (c.set_time_steps_yearly == YIDX)]
    return float(r["ratio_reduction_operational"].iloc[0]) if not r.empty else np.nan


def write_doc(rows, status):
    L = ["# Crystal Ball — true break-even vs clean (op_C) and perturbed (op_B) RC\n",
         f"*`RC_report/cb_sweep_perturbed.py`. Status: **{status}** ({datetime.now():%Y-%m-%d %H:%M}). "
         f"Outputs: `{os.path.basename(ROOT)}`.*\n",
         "Degenerate (flagged) cases. Capex sweep (presolve on) brackets the true break-even; "
         "compared with op_C (clean) and op_B (perturbed). Expectation (cf. nuclear@ES): "
         "op_C < op_B <= true.\n",
         "| tech | node | op_C [%] | op_B [%] | true break-even [%] | op_B a lower bound? |",
         "|---|---|---:|---:|---:|---|"]
    for x in rows:
        L.append(f"| {x['tech']} | {x['node']} | {x['opC']:.1f} | {x['opB']:.1f} | {x['true_lo']:.0f}--{x['true_hi']} "
                 f"| {x['verdict']} |")
    L.append("\n## Per-cut build [GW]\n")
    for x in rows:
        L.append(f"**{x['tech']}@{x['node']}** (op_C {x['opC']:.1f}%, op_B {x['opB']:.1f}%): " +
                 ", ".join(f"{int(round(c*100))}%->{b:.3g}" for c, b in x["sweep"]))
    open(DOC, "w", encoding="utf-8").write("\n".join(L))


def main():
    waited = 0
    while others_solving() and waited < 5400:
        print(f"[wait] another solve running... ({waited}s)", flush=True); time.sleep(20); waited += 20
    from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps
    restore_leftover_swaps(DATASET)
    rows, t0 = [], time.time()
    write_doc(rows, "running (0 done)")
    for ci, (tech, node) in enumerate(CASES, 1):
        if time.time() - t0 > BUDGET_S - 40 * 60:
            print(f"[time guard] stop before {tech}@{node}", flush=True); break
        rC = ratio_from(RUNC, tech, node); rB = ratio_from(RUNB, tech, node)
        if not np.isfinite(rC) or not np.isfinite(rB):
            print(f"[{ci}] {tech}@{node}: missing ratio, skip", flush=True); continue
        cuts = sorted({round(min(max(rB + d, rC + 0.01), 0.55), 4) for d in (0.0, 0.05, 0.12, 0.25)})
        print(f"\n[{ci}/{len(CASES)}] {tech}@{node}  op_C={rC*100:.1f}%  op_B={rB*100:.1f}%  cuts={[round(c*100,1) for c in cuts]}", flush=True)
        orig = read_capex(DATASET, tech, node, YEAR); sweep = []
        for cut in cuts:
            if time.time() - t0 > BUDGET_S:
                print("[time guard] stop mid-case", flush=True); break
            with capex_file_override(DATASET, [{"tech": tech, "node": node, "year": YEAR, "value": orig * (1 - cut)}]):
                b = solve_built(f"c{ci}_{tech}_{node}_cut{int(round(cut*100))}", tech, node)
            sweep.append((cut, b))
            print(f"   cut {cut*100:5.1f}%  -> built {b:8.4g} GW", flush=True)
        built_cuts = [c for c, b in sweep if np.isfinite(b) and b > VTOL]
        noB = [c for c, b in sweep if not (np.isfinite(b) and b > VTOL)]
        true_lo = (max(noB) if noB else cuts[0]) * 100
        true_hi = f"{min(built_cuts)*100:.0f}" if built_cuts else f">{cuts[-1]*100:.0f}"
        verdict = "YES (true > op_B)" if (built_cuts and min(built_cuts)*100 > rB*100 + 0.5) else \
                  ("op_B ~ true" if built_cuts else "true beyond swept range")
        rows.append(dict(tech=tech, node=node, opC=rC*100, opB=rB*100, true_lo=true_lo, true_hi=true_hi,
                         verdict=verdict, sweep=sweep))
        pd.DataFrame([{k: v for k, v in r.items() if k != "sweep"} for r in rows]).to_csv(
            os.path.join(ROOT, "sweep_summary.csv"), index=False)
        write_doc(rows, f"running ({len(rows)} done)")
    write_doc(rows, "DONE")
    print(f"\nDONE -> {ROOT}", flush=True)


if __name__ == "__main__":
    main()
