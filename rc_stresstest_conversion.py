"""Stresstest der interpretierbaren conversion-RC (nutzt rc_capex_file_override).

Validiert, dass `rc_capex_equivalent_input_units` (= noetige CAPEX-Senkung zum Bau)
wirklich die Bau-Schwelle trifft.

Ablauf:
  1. EIN normaler Lauf mit aktiven Perturbationen -> interpretierbare conversion-RC.
  2. 5 echte Faelle picken: case == buildable_rc, rc_reliable, RATIO_MIN < ratio <= RATIO_MAX
     (Cap bei 90 %, weil CAPEX nie 0/negativ werden darf).
  3. Pro Fall ZWEI Verifikationslaeufe. Der CAPEX-Override laeuft ueber die gemeinsame
     Datei-Swap-Mechanik (rc_capex_file_override) — robust, da der Dateieingang
     nachweislich korrekt gelesen wird. Override-Wert = Originalwert * (1 - faktor*ratio)
     ueber die dimensionslose ratio, daher unit-korrekt fuer ALLE conversion-Techs.
       - "build"  : faktor 1.1 (10 % MEHR senken als RC) -> sollte bauen.
       - "nobuild": faktor 0.9 (10 % WENIGER senken als RC) -> sollte nicht bauen.

Aufruf:  python rc_stresstest_conversion.py
Achtung: 1 + 2*5 = 11 volle Modelllaeufe -> ca. 1 Stunde. N_CASES senken fuer weniger.
"""
import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

from zen_garden import run
from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps

# ---- Stellschrauben -------------------------------------------------------
N_CASES = 5
MARGIN = 0.10           # +/- 10 % der RC
RATIO_MAX = 0.90        # nie mehr als 90 % senken (CAPEX muss positiv bleiben)
RATIO_MIN = 0.01        # winzige RC ueberspringen (Testmarge sonst zu klein)
VALUE_BUILT_TOL = 1e-5  # capacity_addition darueber = "gebaut"
TIGHT_E2P = {"battery": 16, "pumped_hydro": 22, "salt_cavern_storage": 145}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
DATASET = os.path.join(BASE_DIR, "ZEN-models", "data", "Crystal_Ball")
DATA_NAME = os.path.basename(DATASET)


def base_config():
    """Solver-Setup wie main_rc_simplex, deterministisch (Method=2), ohne Perturbationen."""
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
    so["Crossover"] = 1     # echte Ecke -> value ist 0 oder echt > 0
    so["Presolve"] = 0
    return c


def run_model(config, out_name):
    out = os.path.join(ROOT, out_name)
    os.makedirs(out, exist_ok=True)
    tmp = os.path.join(out, "_config.json")
    with open(tmp, "w") as f:
        json.dump(config, f, indent=2)
    print(f"   ... laeuft '{out_name}' (einige Minuten)", flush=True)
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
    df = pd.read_csv(f)
    row = df[(df.set_technologies == tech) & (df.set_capacity_types == "power")
             & (df.set_location == node) & (df.set_time_steps_yearly == yidx)]
    return float(row["value"].iloc[0]) if not row.empty else np.nan


def select_cases(conv, n=N_CASES):
    rel = conv["rc_reliable"].astype(str).str.lower().isin(["true", "1"])
    cand = conv[(conv["case"] == "buildable_rc") & rel
                & (conv["ratio_reduction"] > RATIO_MIN)
                & (conv["ratio_reduction"] <= RATIO_MAX)].copy()
    cand = cand.dropna(subset=["capex_specific_input_units",
                               "rc_capex_equivalent_input_units"])
    cand = cand.sort_values("ratio_reduction").drop_duplicates("set_technologies")
    if cand.empty:
        return cand
    idx = np.linspace(0, len(cand) - 1, min(n, len(cand))).round().astype(int)
    return cand.iloc[np.unique(idx)].reset_index(drop=True)


def _run_with_override(tech, node, year, yidx, ratio, reduce_factor, out_name):
    """Ein Verifikationslauf: CAPEX = Original * (1 - reduce_factor*ratio); gibt (value, c, new)."""
    c_csv = read_capex(DATASET, tech, node, year)
    new = c_csv * (1.0 - reduce_factor * ratio)
    with capex_file_override(DATASET, [{"tech": tech, "node": node,
                                        "year": year, "value": new}]):
        v = read_value(run_model(base_config(), out_name), tech, node, yidx)
    return v, c_csv, new


def main():
    global ROOT
    ROOT = os.path.join(
        BASE_DIR, f"outputs_{datetime.now().strftime('%Y%m%d-%H%M%S')}_rc_stresstest")
    os.makedirs(ROOT, exist_ok=True)
    print(f"RC-Stresstest (conversion, Datei-Swap) -> {ROOT}\n")
    restore_leftover_swaps(DATASET)

    # 1) Baseline mit Perturbationen -> interpretierbare RC
    print("SCHRITT 1/3: Baseline-Lauf mit Perturbationen (interpretierbare RC) ...")
    cfg = base_config()
    so = cfg["solver"]["solver_options"]
    so["rc_perturbation"] = 0
    so["rc_lifetime_rhs_perturbation"] = 1e-4
    so["rc_storage_power_perturbation"] = 1e-4
    so["rc_tight_e2p"] = TIGHT_E2P
    base_dir = run_model(cfg, "baseline")
    ref_year, interval = year_map(base_dir)
    conv = pd.read_csv(os.path.join(base_dir,
                                    "capacity_addition_analysis_conversion.csv"))

    # 2) Faelle waehlen
    cases = select_cases(conv)
    if cases.empty:
        raise SystemExit("Keine interpretierbaren buildable_rc-conversion-Faelle gefunden.")
    print(f"\nSCHRITT 2/3: {len(cases)} Faelle gewaehlt:")
    for r in cases.itertuples():
        print(f"   {r.set_technologies:24s} {r.set_location:4s} "
              f"C={r.capex_specific_input_units:10.2f}  R={r.rc_capex_equivalent_input_units:10.4f}  "
              f"ratio={r.ratio_reduction * 100:6.2f}%")

    # 3) je zwei Verifikationslaeufe via Datei-Swap
    print("\nSCHRITT 3/3: Verifikationslaeufe (2 pro Fall, CAPEX via Daten-CSV) ...")
    results = []
    for i, r in enumerate(cases.itertuples(), 1):
        tech, node = r.set_technologies, r.set_location
        yidx = int(r.set_time_steps_yearly)
        year = ref_year + yidx * interval
        ratio = float(r.ratio_reduction)
        print(f"\n[Fall {i}/{len(cases)}] {tech} @ {node} ({year})  ratio={ratio*100:.2f}%")
        row = dict(case=i, tech=tech, node=node, year=year,
                   capex_input_units=float(r.capex_specific_input_units),
                   rc_input_units=float(r.rc_capex_equivalent_input_units),
                   ratio_pct=round(ratio * 100, 3))
        try:
            v_b, c, nb = _run_with_override(tech, node, year, yidx, ratio,
                                            1.0 + MARGIN, f"case{i:02d}_{tech}_{node}_build")
            print(f"   build   : CSV {c:.2f} -> {nb:.2f}")
            v_n, _, nn = _run_with_override(tech, node, year, yidx, ratio,
                                            1.0 - MARGIN, f"case{i:02d}_{tech}_{node}_nobuild")
            print(f"   nobuild : CSV {c:.2f} -> {nn:.2f}")
        except Exception as e:
            print(f"   !! Fehler ({e}) -> Fall uebersprungen")
            row.update(result="ERROR")
            results.append(row)
            continue

        built_b = np.isfinite(v_b) and v_b > VALUE_BUILT_TOL
        built_n = np.isfinite(v_n) and v_n > VALUE_BUILT_TOL
        ok = built_b and not built_n
        print(f"   build   value={v_b:.4g}  gebaut={built_b}")
        print(f"   nobuild value={v_n:.4g}  gebaut={built_n}")
        print(f"   => {'PASS' if ok else 'FAIL'}")
        row.update(value_build=v_b, built_build=built_b,
                   value_nobuild=v_n, built_nobuild=built_n,
                   result="PASS" if ok else "FAIL")
        results.append(row)

    res = pd.DataFrame(results)
    out_csv = os.path.join(ROOT, "rc_stresstest_summary.csv")
    res.to_csv(out_csv, index=False)
    print("\n" + "=" * 72)
    print("STRESSTEST-ZUSAMMENFASSUNG")
    print("=" * 72)
    if not res.empty:
        cols = [c for c in ["case", "tech", "node", "ratio_pct", "value_build",
                            "value_nobuild", "result"] if c in res.columns]
        print(res[cols].to_string(index=False))
        if "result" in res.columns:
            print(f"\n{(res.result == 'PASS').sum()}/{len(res)} Faelle PASS")
    print(f"\nOutputs: {ROOT}\nSummary: {out_csv}")


if __name__ == "__main__":
    main()
