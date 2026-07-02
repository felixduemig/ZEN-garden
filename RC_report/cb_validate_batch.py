"""Overnight (=4 h) +-1% build/nobuild validation of a LARGE batch of *not-yet-validated*,
robust Crystal Ball conversion RCs (clean run C operational RC, ground truth via the data-CSV
capex swap). Goal: find as many "correct" RCs as possible, across diverse techs/nodes.

Per case (clean op_C ratio = rc_capex_equivalent_operational / capex, read from runC):
  build   : capex = orig*(1 - 1.01*ratio)  -> MUST build      (PASS needs this True)
  nobuild : capex = orig*(1 - 0.99*ratio)  -> MUST NOT build   (PASS needs this False)
The relative swap is unit-invariant, so orig is read in native data-CSV units.

Robustness: results are appended to validate_summary.csv AND the collecting doc
(RC_report/cb_rc_validation_collected.md) after EVERY case, so a crash/abort loses nothing.
A time guard stops launching new cases before the 4 h window closes (~11 min/solve, 2/case).
"""
import json, os, sys, time
from datetime import datetime
import numpy as np, pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE); os.chdir(BASE)

# Keep Windows awake for the whole run: an earlier overnight attempt died after ~17 min when
# the machine idle-slept. ES_CONTINUOUS holds for this (main) thread's lifetime = the process.
try:
    import ctypes
    ctypes.windll.kernel32.SetThreadExecutionState(
        0x80000000 | 0x00000001 | 0x00000040)  # CONTINUOUS | SYSTEM_REQUIRED | AWAYMODE_REQUIRED
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
BUDGET_S = 235 * 60          # hard ceiling, safely under the 4 h window
GUARD_FACTOR = 1.15         # safety margin on the worst observed case time
DEFAULT_CASE_S = 26 * 60    # first-case estimate (2 solves)

STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
ROOT = os.path.join(BASE, "outputs_CB_overnight", f"validate_batch_{STAMP}")
os.makedirs(ROOT, exist_ok=True)
DOC = os.path.join(BASE, "RC_report", "cb_rc_validation_collected.md")

# diverse techs first (so a short run still spans all 9 technologies), then repeats
CANDIDATES = [
    ("coal_to_cement_fuel", "SK"), ("heat_pump_DH", "SE"), ("wind_offshore", "SE"),
    ("photovoltaics", "SE"), ("methanol_from_hydrogen", "BG"), ("run-of-river_hydro", "SE"),
    ("reservoir_hydro", "SE"), ("wind_onshore", "CH"), ("natural_gas_turbine_CCS", "ES"),
    ("coal_to_cement_fuel", "HU"), ("wind_offshore", "DK"), ("heat_pump_DH", "IE"),
    ("photovoltaics", "LT"), ("heat_pump_DH", "FI"), ("photovoltaics", "LV"),
    ("wind_onshore", "SI"),
]

# previously validated clean operational RCs (context for the collecting doc)
PRIOR = [
    ("photovoltaics", "CZ", 4.75, "PASS", "0.32", "clean op_C"),
    ("photovoltaics", "NO", 21.52, "PASS", "2.79", "clean op_C"),
    ("wind_onshore", "NO", 16.58, "PASS", "26.80", "clean op_C"),
    ("wind_offshore", "FR", 11.18, "PASS", "15.65", "clean op_C"),
    ("run-of-river_hydro", "SK", 12.81, "PASS", "0.36", "clean op_C"),
    ("reservoir_hydro", "CH", 24.42, "PASS", "1.64", "clean op_C"),
    ("electrolysis", "FI", 12.36, "FAIL", "-", "scarcity-vertex degenerate (import island)"),
    ("nuclear", "ES", 3.20, "FAIL", "-", "scarcity-vertex degenerate (import island)"),
]


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
    r = c[(c.set_technologies == tech) & (c.set_location == node)
          & (c.set_time_steps_yearly == YIDX)]
    if r.empty:
        return None
    r = r.iloc[0]
    return dict(ratio=float(r["ratio_reduction_operational"]),
                rc=float(r["rc_capex_equivalent_operational_input_units"]),
                capex=float(r["capex_specific_input_units"]), case=str(r["case"]))


def write_doc(rows, status):
    df = pd.DataFrame(rows)
    npass = int((df.result == "PASS").sum()) if len(df) else 0
    nfail = int((df.result == "FAIL").sum()) if len(df) else 0
    L = []
    L.append("# Crystal Ball reduced-cost validation — collected results\n")
    L.append(f"*Auto-updated by `RC_report/cb_validate_batch.py`. Status: **{status}** "
             f"({datetime.now():%Y-%m-%d %H:%M}). Outputs: `{os.path.basename(ROOT)}`.*\n")
    L.append("## Method\n")
    L.append("Degeneracy-immune ground truth by re-solving the full Crystal Ball model with the "
             "candidate's capex perturbed around its clean operational reduced cost:\n")
    L.append("- `build`  : capex = orig·(1 − 1.01·r) → the technology **must** build\n")
    L.append("- `nobuild`: capex = orig·(1 − 0.99·r) → the technology **must not** build\n")
    L.append("where r = `rc_capex_equivalent_operational / capex` from the clean run C. A case "
             "**PASSES** iff it builds at −1.01·r and stays unbuilt at −0.99·r (the RC pins the "
             "build threshold to within ±1 %). The relative swap is unit-invariant.\n")
    L.append("## This batch (new technologies/nodes)\n")
    L.append(f"**{npass} PASS / {nfail} FAIL** of {len(df)} checked so far.\n")
    L.append("| # | technology | node | RC ratio [%] | build@−1.01r [GW] | nobuild@−0.99r [GW] | result |")
    L.append("|---|---|---|---:|---:|---:|---|")
    for i, x in enumerate(rows, 1):
        vb = f"{x['v_build']:.4g}" if np.isfinite(x['v_build']) else "—"
        vn = f"{x['v_nobuild']:.4g}" if np.isfinite(x['v_nobuild']) else "—"
        L.append(f"| {i} | {x['tech']} | {x['node']} | {x['ratio_pct']:.2f} | {vb} | {vn} | "
                 f"**{x['result']}** |")
    L.append("\n## Previously validated (clean operational RC, earlier runs)\n")
    L.append("| technology | node | RC ratio [%] | build [GW] | result | note |")
    L.append("|---|---|---:|---:|---|---|")
    for t, n, rp, res, gw, note in PRIOR:
        L.append(f"| {t} | {n} | {rp:.2f} | {gw} | **{res}** | {note} |")
    L.append("\n*The two FAILs are the known import-island conversion techs whose operational RC "
             "is a lower bound (scarcity-vertex degeneracy, see "
             "`docs/rc_crystalball_conversion_failure.md`); every clean, perturbation-stable "
             "candidate validated so far has passed.*\n")
    open(DOC, "w", encoding="utf-8").write("\n".join(L))


def main():
    restore_leftover_swaps(DATASET)
    rows, case_times, t0 = [], [], time.time()
    write_doc(rows, "running (0 cases done)")
    for i, (tech, node) in enumerate(CANDIDATES, 1):
        elapsed = time.time() - t0
        est = max(case_times) * GUARD_FACTOR if case_times else DEFAULT_CASE_S
        if elapsed + est > BUDGET_S:
            print(f"\n[time guard] stop: {elapsed/60:.0f} min elapsed, next case est "
                  f"{est/60:.0f} min > budget {BUDGET_S/60:.0f} min", flush=True)
            break
        info = lookup_ratio(tech, node)
        if info is None:
            print(f"[{i}] {tech}@{node}: no runC row, skip", flush=True); continue
        ratio = info["ratio"]
        print(f"\n[{i}/{len(CANDIDATES)}] {tech} @ {node}  ratio={ratio*100:.3f}%  "
              f"(elapsed {elapsed/60:.0f} min)", flush=True)
        cstart = time.time()
        orig = read_capex(DATASET, tech, node, YEAR)
        nb_b = orig * (1 - (1 + MARGIN) * ratio)
        nb_n = orig * (1 - (1 - MARGIN) * ratio)
        with capex_file_override(DATASET, [{"tech": tech, "node": node, "year": YEAR, "value": nb_b}]):
            vb = run_read(f"c{i:02d}_{tech}_{node}_build", tech, node)
        with capex_file_override(DATASET, [{"tech": tech, "node": node, "year": YEAR, "value": nb_n}]):
            vn = run_read(f"c{i:02d}_{tech}_{node}_nobuild", tech, node)
        bb, bn = (np.isfinite(vb) and vb > VTOL), (np.isfinite(vn) and vn > VTOL)
        ok = bb and not bn
        case_times.append(time.time() - cstart)
        print(f"   build->{vb:.4g} ({bb})  nobuild->{vn:.4g} ({bn})  => "
              f"{'PASS' if ok else 'FAIL'}  [{case_times[-1]/60:.1f} min]", flush=True)
        rows.append(dict(tech=tech, node=node, ratio_pct=round(ratio*100, 4),
                         rc=round(info["rc"], 3), orig_capex=round(orig, 3),
                         v_build=vb, v_nobuild=vn, built_build=bb, built_nobuild=bn,
                         result="PASS" if ok else "FAIL"))
        pd.DataFrame(rows).to_csv(os.path.join(ROOT, "validate_summary.csv"), index=False)
        write_doc(rows, f"running ({len(rows)} cases done)")
    res = pd.DataFrame(rows)
    write_doc(rows, f"DONE — {(res.result=='PASS').sum()}/{len(res)} PASS")
    print(f"\n{'='*50}\n{(res.result=='PASS').sum()}/{len(res)} PASS  ->  {ROOT}")
    print(res.to_string(index=False) if len(res) else "(no cases)")


if __name__ == "__main__":
    main()
