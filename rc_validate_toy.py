"""Vollstaendige RC-Validierung des Toy-Models (5_multiple_time_steps_per_year).

Testet JEDEN interpretierbaren RC-Fall (buildable_rc + rc_reliable, ratio im testbaren
Band) per Build/Nobuild ueber den Datei-CAPEX-Override:
    build   : capex * (1 - (1+MARGIN)*ratio)  -> MUSS bauen
    nobuild : capex * (1 - (1-MARGIN)*ratio)   -> darf NICHT bauen
Toy loest in Sekunden -> vollstaendige Abdeckung praktikabel.

Aufruf:  python rc_validate_toy.py
"""
import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

from zen_garden import run
from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps

MARGIN = 0.10
RATIO_MIN, RATIO_MAX = 0.01, 0.85
VALUE_BUILT_TOL = 1e-5

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
DATASET = os.path.join(BASE_DIR, "5_multiple_time_steps_per_year")
DATA_NAME = os.path.basename(DATASET)


def base_config():
    with open("./config.json") as f:
        c = json.load(f)
    c.pop("plugins", None)
    c.setdefault("solver", {})
    c["solver"].setdefault("solver_options", {})
    c["solver"]["name"] = "gurobi"
    c["solver"]["save_duals"] = True
    c["solver"]["save_reduced_costs"] = True
    c["solver"]["use_scaling"] = 0
    so = c["solver"]["solver_options"]
    so["Method"] = 2
    so["Crossover"] = 1
    so["Presolve"] = 0
    return c


def run_model(config, out_name):
    out = os.path.join(ROOT, out_name)
    os.makedirs(out, exist_ok=True)
    tmp = os.path.join(out, "_config.json")
    with open(tmp, "w") as f:
        json.dump(config, f, indent=2)
    run(config=tmp, dataset=DATASET, folder_output=out)
    os.remove(tmp)
    return os.path.join(out, DATA_NAME)


def year_map(scenario_dir):
    try:
        s = json.load(open(os.path.join(scenario_dir, "system.json")))
        return int(s.get("reference_year", 0)), int(s.get("interval_between_years", 1)) or 1
    except Exception:
        return 0, 1


def read_value(scenario_dir, tech, node, yidx):
    f = os.path.join(scenario_dir, "capacity_addition_analysis.csv")
    if not os.path.isfile(f):
        return np.nan
    d = pd.read_csv(f)
    r = d[(d.set_technologies == tech) & (d.set_capacity_types == "power")
          & (d.set_location == node) & (d.set_time_steps_yearly == yidx)]
    return float(r["value"].iloc[0]) if not r.empty else np.nan


def main():
    global ROOT
    ROOT = os.path.join(BASE_DIR, f"outputs_{datetime.now():%Y%m%d-%H%M%S}_rc_validate_toy")
    os.makedirs(ROOT, exist_ok=True)
    print(f"RC-Vollvalidierung Toy-Model -> {ROOT}\n")
    restore_leftover_swaps(DATASET)

    print("SCHRITT 1: Baseline mit Perturbation ...")
    cfg = base_config()
    cfg["solver"]["solver_options"]["rc_perturbation"] = 0
    cfg["solver"]["solver_options"]["rc_lifetime_rhs_perturbation"] = 1e-4
    base_dir = run_model(cfg, "baseline")
    ref_year, interval = year_map(base_dir)
    conv = pd.read_csv(os.path.join(base_dir, "capacity_addition_analysis_conversion.csv"))

    rel = conv["rc_reliable"].astype(str).str.lower().isin(["true", "1"])
    cand = conv[(conv.case == "buildable_rc") & rel
                & (conv.ratio_reduction > RATIO_MIN)
                & (conv.ratio_reduction <= RATIO_MAX)].copy()
    cand = cand.sort_values(["set_technologies", "set_location", "set_time_steps_yearly"])
    print(f"\nSCHRITT 2: {len(cand)} testbare RC-Faelle (ratio {RATIO_MIN:.0%}-{RATIO_MAX:.0%}):")
    for r in cand.itertuples():
        print(f"   {r.set_technologies:20s} {r.set_location} y{int(r.set_time_steps_yearly)}  "
              f"capex={r.capex_specific_input_units:9.1f}  RC={r.rc_capex_equivalent_input_units:9.2f}  "
              f"ratio={r.ratio_reduction*100:6.2f}%")
    if cand.empty:
        raise SystemExit("Keine testbaren Faelle.")

    print(f"\nSCHRITT 3: Build/Nobuild ({1+2*len(cand)} Laeufe) ...")
    results = []
    for i, r in enumerate(cand.itertuples(), 1):
        tech, node = r.set_technologies, r.set_location
        yidx = int(r.set_time_steps_yearly)
        year = ref_year + yidx * interval
        ratio = float(r.ratio_reduction)
        c = read_capex(DATASET, tech, node, year)
        tag = f"{tech}_{node}_y{yidx}"
        try:
            with capex_file_override(DATASET, [{"tech": tech, "node": node, "year": year,
                                                "value": c * (1 - (1 + MARGIN) * ratio)}]):
                vb = read_value(run_model(base_config(), f"{i:02d}_{tag}_build"), tech, node, yidx)
            with capex_file_override(DATASET, [{"tech": tech, "node": node, "year": year,
                                                "value": c * (1 - (1 - MARGIN) * ratio)}]):
                vn = read_value(run_model(base_config(), f"{i:02d}_{tag}_nobuild"), tech, node, yidx)
        except Exception as e:
            print(f"   [{tag}] Fehler: {e}")
            results.append(dict(tech=tech, node=node, year_idx=yidx, ratio_pct=round(ratio*100, 2),
                                result="ERROR"))
            continue
        bb = np.isfinite(vb) and vb > VALUE_BUILT_TOL
        bn = np.isfinite(vn) and vn > VALUE_BUILT_TOL
        ok = bb and not bn
        print(f"   [{tag:24s}] build={vb:.4g} ({bb})  nobuild={vn:.4g} ({bn})  => {'PASS' if ok else 'FAIL'}")
        results.append(dict(tech=tech, node=node, year_idx=yidx, ratio_pct=round(ratio*100, 2),
                            rc=round(float(r.rc_capex_equivalent_input_units), 3),
                            value_build=vb, value_nobuild=vn, result="PASS" if ok else "FAIL"))

    res = pd.DataFrame(results)
    out_csv = os.path.join(ROOT, "rc_validate_toy_summary.csv")
    res.to_csv(out_csv, index=False)
    print("\n" + "=" * 70 + "\nTOY-MODEL VOLLVALIDIERUNG\n" + "=" * 70)
    print(res.to_string(index=False))
    if "result" in res.columns:
        print(f"\n{(res.result == 'PASS').sum()}/{len(res)} PASS")
    print(f"\nSummary: {out_csv}")


if __name__ == "__main__":
    main()
