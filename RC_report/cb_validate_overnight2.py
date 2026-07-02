"""Overnight (~9 h) +-1% build/nobuild validation of NEW Crystal Ball conversion RCs from the
PRESENTED EXCERPT (20 focus techs x 10 nodes DE/FR/NO/SE/CH/CZ/SK/BG/ES/FI). Goal: expand the
validated PASS set across the technology fleet and confirm that flagged (high-swing) cases are
lower bounds. Same protocol/engine as cb_validate_batch.py; results appended after EVERY case to
a SEPARATE doc so nothing existing is overwritten and a crash loses nothing.
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
BUDGET_S = 540 * 60          # ~9 h window
GUARD_FACTOR = 1.15
DEFAULT_CASE_S = 24 * 60

STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
ROOT = os.path.join(BASE, "outputs_CB_overnight", f"validate_overnight2_{STAMP}")
os.makedirs(ROOT, exist_ok=True)
DOC = os.path.join(BASE, "RC_report", "cb_rc_validation_overnight2.md")

# excerpt cases, buildable_rc, not yet validated, ratio<0.9.
# block 1: diverse reliable (one per tech, max fleet coverage if the run is cut short)
# block 2: flagged small-ratio high-swing -> EXPECT FAIL (confirms lower bound)
# block 3: extra reliable nodes for robustness
CANDIDATES = [
    ("photovoltaics", "SK"),            # 0.2%  rel
    ("electrolysis", "CH"),             # 2.6%  rel
    ("reservoir_hydro", "NO"),          # 7.1%  rel
    ("run-of-river_hydro", "BG"),       # 8.2%  rel
    ("heat_pump_DH", "ES"),             # 11.9% rel
    ("DAC", "SE"),                      # 13.3% rel
    ("wind_onshore", "BG"),             # 14.8% rel
    ("methanol_from_hydrogen", "DE"),   # 17.5% rel
    ("electrode_boiler", "DE"),         # 25.3% rel
    ("fuel_cell", "ES"),                # 28.1% rel
    ("SMR_CCS", "DE"),                  # 32.8% rel
    ("natural_gas_turbine", "NO"),      # 36.8% rel
    ("coal_to_cement_fuel", "CZ"),      # 59.5% rel
    ("natural_gas_turbine_CCS", "BG"),  # 61.6% rel
    ("natural_gas_boiler", "DE"),       # 71.0% rel
    ("natural_gas_turbine_CCS", "SK"),  # 4.3%  swing 105  -> expect FAIL (lower bound)
    ("natural_gas_turbine_CCS", "CZ"),  # 9.8%  swing 117  -> expect FAIL
    ("SMR_CCS", "ES"),                  # 23.9% swing 91   -> expect FAIL
    ("reservoir_hydro", "CZ"),          # 13.1% rel
    ("heat_pump_DH", "FR"),             # 17.7% rel
    ("photovoltaics", "FI"),            # 21.2% rel
    ("run-of-river_hydro", "CH"),       # 26.9% rel
    ("heat_pump_DH", "BG"),             # 19.8% rel
    ("reservoir_hydro", "FR"),          # 16.4% rel
    ("run-of-river_hydro", "CZ"),       # 26.5% rel
    ("heat_pump_DH", "DE"),             # 29.2% rel
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
    L.append("# Crystal Ball RC validation — overnight batch 2 (presented excerpt)\n")
    L.append(f"*Auto-updated by `RC_report/cb_validate_overnight2.py`. Status: **{status}** "
             f"({datetime.now():%Y-%m-%d %H:%M}). Outputs: `{os.path.basename(ROOT)}`.*\n")
    L.append("New (technology, node) cases from the 20-tech x 10-node presented excerpt, not "
             "previously validated. Protocol: re-solve at capex = orig*(1 - 1.01*r) [must build] "
             "and orig*(1 - 0.99*r) [must not build], r = clean operational ratio from run C.\n")
    L.append(f"**{npass} PASS / {nfail} FAIL** of {len(df)} checked.\n")
    L.append("| # | technology | node | RC ratio [%] | build@-1.01r [GW] | nobuild@-0.99r [GW] | result |")
    L.append("|---|---|---|---:|---:|---:|---|")
    for i, x in enumerate(rows, 1):
        vb = f"{x['v_build']:.4g}" if np.isfinite(x['v_build']) else "—"
        vn = f"{x['v_nobuild']:.4g}" if np.isfinite(x['v_nobuild']) else "—"
        L.append(f"| {i} | {x['tech']} | {x['node']} | {x['ratio_pct']:.2f} | {vb} | {vn} | "
                 f"**{x['result']}** |")
    L.append("\n*Flagged cases (natural_gas_turbine_CCS@SK/CZ, SMR_CCS@ES) are expected to FAIL: "
             "their high perturbation swing marks the reconstructed RC as a lower bound.*\n")
    open(DOC, "w", encoding="utf-8").write("\n".join(L))


def main():
    restore_leftover_swaps(DATASET)
    rows, case_times, t0 = [], [], time.time()
    write_doc(rows, "running (0 cases done)")
    for i, (tech, node) in enumerate(CANDIDATES, 1):
        elapsed = time.time() - t0
        est = max(case_times) * GUARD_FACTOR if case_times else DEFAULT_CASE_S
        if elapsed + est > BUDGET_S:
            print(f"\n[time guard] stop: {elapsed/60:.0f} min elapsed, est {est/60:.0f} min "
                  f"> budget {BUDGET_S/60:.0f} min", flush=True)
            break
        info = lookup_ratio(tech, node)
        if info is None:
            print(f"[{i}] {tech}@{node}: no runC row, skip", flush=True); continue
        ratio = info["ratio"]
        if ratio >= 0.95:
            print(f"[{i}] {tech}@{node}: ratio {ratio*100:.1f}% >= 95% (would need negative "
                  f"capex), skip", flush=True); continue
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
    write_doc(rows, f"DONE — {(res.result=='PASS').sum()}/{len(res)} PASS" if len(res) else "DONE — 0 cases")
    print(f"\n{'='*50}\n{(res.result=='PASS').sum() if len(res) else 0}/{len(res)} PASS  ->  {ROOT}")
    print(res.to_string(index=False) if len(res) else "(no cases)")


if __name__ == "__main__":
    main()
