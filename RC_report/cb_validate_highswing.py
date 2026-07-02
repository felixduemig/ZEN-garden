"""Targeted +-1% screen of 5 UNTESTED, HIGH-SWING (>5pp) conversion RCs from the lower half of
the presented Crystal Ball excerpt. Goal: understand the high-swing cases -- confirm whether the
reconstructed RC is a lower bound (expected FAIL) and read the build behaviour. Same engine as
cb_validate_overnight2.py; crash-safe, writes to a SEPARATE doc.
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
BUDGET_S = 200 * 60
GUARD_FACTOR = 1.15
DEFAULT_CASE_S = 24 * 60

STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
ROOT = os.path.join(BASE, "outputs_CB_overnight", f"validate_highswing_{STAMP}")
os.makedirs(ROOT, exist_ok=True)
DOC = os.path.join(BASE, "RC_report", "cb_rc_validation_highswing.md")

# untested, swing>5pp, ratio<0.95, lower-half excerpt techs.
# coal_to_cement@CH and SMR_CCS@CH look close (small RC) but have high swing -> the instructive ones.
CANDIDATES = [
    # coal_to_cement_fuel@CH already done in the first (crashed) run -> FAIL (lower bound). Restarting the rest.
    ("SMR_CCS", "CH"),                  # 8.6%   swing 34  -- close-looking, high swing
    ("SMR", "SK"),                      # 90.5%  swing 90
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
    L = []
    L.append("# Crystal Ball RC validation — high-swing screen (lower-half excerpt)\n")
    L.append(f"*Auto-updated by `RC_report/cb_validate_highswing.py`. Status: **{status}** "
             f"({datetime.now():%Y-%m-%d %H:%M}). Outputs: `{os.path.basename(ROOT)}`.*\n")
    L.append("Untested high-swing (>5pp) conversion cases from the lower half of the excerpt. A "
             "high swing predicts the reconstructed RC is a **lower bound** (expected FAIL). "
             "Protocol: re-solve at capex = orig*(1 - 1.01*r) [must build] and orig*(1 - 0.99*r).\n")
    L.append("| # | technology | node | RC ratio [%] | build@-1.01r [GW] | nobuild@-0.99r [GW] | result |")
    L.append("|---|---|---|---:|---:|---:|---|")
    for i, x in enumerate(rows, 1):
        vb = f"{x['v_build']:.4g}" if np.isfinite(x['v_build']) else "—"
        vn = f"{x['v_nobuild']:.4g}" if np.isfinite(x['v_nobuild']) else "—"
        L.append(f"| {i} | {x['tech']} | {x['node']} | {x['ratio_pct']:.2f} | {vb} | {vn} | "
                 f"**{x['result']}** |")
    open(DOC, "w", encoding="utf-8").write("\n".join(L))


def main():
    restore_leftover_swaps(DATASET)
    rows, case_times, t0 = [], [], time.time()
    write_doc(rows, "running (0 cases done)")
    for i, (tech, node) in enumerate(CANDIDATES, 1):
        elapsed = time.time() - t0
        est = max(case_times) * GUARD_FACTOR if case_times else DEFAULT_CASE_S
        if elapsed + est > BUDGET_S:
            print(f"\n[time guard] stop: {elapsed/60:.0f} min elapsed", flush=True)
            break
        info = lookup_ratio(tech, node)
        if info is None:
            print(f"[{i}] {tech}@{node}: no runC row, skip", flush=True); continue
        ratio = info["ratio"]
        if ratio >= 0.95:
            print(f"[{i}] {tech}@{node}: ratio {ratio*100:.1f}% >= 95%, skip", flush=True); continue
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
    write_doc(rows, f"DONE — {(res.result=='PASS').sum() if len(res) else 0}/{len(res)} PASS")
    print(f"\n{'='*50}\nDONE -> {ROOT}")
    print(res.to_string(index=False) if len(res) else "(no cases)")


if __name__ == "__main__":
    main()
