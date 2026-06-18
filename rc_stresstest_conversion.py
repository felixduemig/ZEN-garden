"""Stresstest der interpretierbaren conversion-RC.

Validiert, dass `rc_capex_equivalent_input_units` (= „um wie viele EUR/kW muss der
CAPEX sinken, damit die Technologie gebaut wird") wirklich die Bau-Schwelle trifft.

Ablauf:
  1. EIN normaler Lauf mit aktiven Perturbationen -> interpretierbare conversion-RC.
  2. 5 echte Faelle picken: case == buildable_rc, rc_reliable, RATIO_MIN < ratio <= RATIO_MAX
     (Cap bei 90 %, weil CAPEX nie 0/negativ werden darf -> sonst crasht das Modell).
  3. Pro Fall ZWEI Verifikationslaeufe via rc_capex_override (nur dieser eine Knoten):
       - "build"  : CAPEX um (1 + 10 %)·RC senken  -> Tech SOLLTE bauen.
       - "nobuild": CAPEX um (1 - 10 %)·RC senken  -> Tech SOLLTE NICHT bauen.
     Erwartung: build -> value > 0, nobuild -> value == 0.

Der Override setzt `capex_specific_input_units = value` exakt (model_val = value *
fraction_year). C (capex) und R (rc) aus der Baseline sind in derselben Einheit ->
der Test ist fuer ALLE conversion-Techs gueltig (auch unit-konvertierte wie SMR_CCS).

Aufruf:  python rc_stresstest_conversion.py
Achtung: 1 + 2*5 = 11 volle Modelllaeufe -> ca. 1 Stunde. N_CASES senken fuer weniger.

Ausgabe:  outputs_<ts>_rc_stresstest/
            baseline/ , caseNN_<tech>_<node>_{build,nobuild}/ , rc_stresstest_summary.csv
"""
import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

from zen_garden import run

# ---- Stellschrauben -------------------------------------------------------
N_CASES = 5
MARGIN = 0.10           # +/- 10 % der RC
RATIO_MAX = 0.90        # nie mehr als 90 % senken (CAPEX muss positiv bleiben)
RATIO_MIN = 0.01        # winzige RC ueberspringen (Testmarge sonst zu klein)
VALUE_BUILT_TOL = 1e-5  # capacity_addition darueber = "gebaut"
TIGHT_E2P = {"battery": 16, "pumped_hydro": 22, "salt_cavern_storage": 145}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
# absolute paths: zen_garden.run() resolves a RELATIVE dataset/folder_output relative
# to the (temp) config file's directory, not the cwd — absolute paths avoid that trap.
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
    so["Method"] = 2        # reiner Barrier -> deterministische Ecke
    so["Crossover"] = 1     # WICHTIG: liefert eine echte Ecke -> value ist 0 oder echt > 0
    so["Presolve"] = 0
    return c


def run_model(config, out_name):
    """Schreibt config, ruft zen_garden.run, gibt den Szenario-Ordner zurueck."""
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
    """capacity_addition (value) der conversion-power-Zeile; NaN wenn nicht gefunden."""
    f = os.path.join(scenario_dir, "capacity_addition_analysis.csv")
    if not os.path.isfile(f):
        return np.nan
    df = pd.read_csv(f)
    row = df[(df.set_technologies == tech) & (df.set_capacity_types == "power")
             & (df.set_location == node) & (df.set_time_steps_yearly == yidx)]
    return float(row["value"].iloc[0]) if not row.empty else np.nan


def select_cases(conv, n=N_CASES):
    """n interpretierbare buildable_rc-Faelle, ueber die Ratio-Spanne verteilt, distinkte Techs."""
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


def main():
    global ROOT
    ROOT = os.path.join(
        BASE_DIR, f"outputs_{datetime.now().strftime('%Y%m%d-%H%M%S')}_rc_stresstest")
    os.makedirs(ROOT, exist_ok=True)
    print(f"RC-Stresstest (conversion) -> {ROOT}\n")

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

    # 3) je zwei Verifikationslaeufe
    print("\nSCHRITT 3/3: Verifikationslaeufe (2 pro Fall) ...")
    results = []
    for i, r in enumerate(cases.itertuples(), 1):
        tech, node = r.set_technologies, r.set_location
        yidx = int(r.set_time_steps_yearly)
        year = ref_year + yidx * interval
        C = float(r.capex_specific_input_units)
        R = float(r.rc_capex_equivalent_input_units)
        capex_build = C - (1.0 + MARGIN) * R     # 10 % MEHR senken als RC -> bauen
        capex_nobuild = C - (1.0 - MARGIN) * R   # 10 % WENIGER senken als RC -> nicht bauen
        print(f"\n[Fall {i}/{len(cases)}] {tech} @ {node} ({year})  C={C:.2f}  R={R:.4f}")
        if capex_build <= 0:
            print("   !! capex_build <= 0 -> uebersprungen (wuerde Modell crashen)")
            continue

        def ov(value):
            c = base_config()
            c["solver"]["solver_options"]["rc_capex_override"] = [
                {"tech": tech, "node": node, "year": year, "value": float(value)}]
            return c

        try:
            d_b = run_model(ov(capex_build), f"case{i:02d}_{tech}_{node}_build")
            v_b = read_value(d_b, tech, node, yidx)
            d_n = run_model(ov(capex_nobuild), f"case{i:02d}_{tech}_{node}_nobuild")
            v_n = read_value(d_n, tech, node, yidx)
        except Exception as e:
            print(f"   !! Lauf fehlgeschlagen ({e}) -> Fall uebersprungen")
            results.append(dict(case=i, tech=tech, node=node, year=year, capex=C, rc=R,
                                ratio_pct=round(r.ratio_reduction * 100, 3),
                                capex_build=capex_build, value_build=np.nan, built_build=False,
                                capex_nobuild=capex_nobuild, value_nobuild=np.nan,
                                built_nobuild=False, result="ERROR"))
            continue

        built_b = np.isfinite(v_b) and v_b > VALUE_BUILT_TOL
        built_n = np.isfinite(v_n) and v_n > VALUE_BUILT_TOL
        ok = built_b and not built_n
        print(f"   build   CAPEX={capex_build:10.2f} -> value={v_b:.4g}  gebaut={built_b}")
        print(f"   nobuild CAPEX={capex_nobuild:10.2f} -> value={v_n:.4g}  gebaut={built_n}")
        print(f"   => {'PASS' if ok else 'FAIL'}")
        results.append(dict(case=i, tech=tech, node=node, year=year,
                            capex=C, rc=R, ratio_pct=round(r.ratio_reduction * 100, 3),
                            capex_build=capex_build, value_build=v_b, built_build=built_b,
                            capex_nobuild=capex_nobuild, value_nobuild=v_n, built_nobuild=built_n,
                            result="PASS" if ok else "FAIL"))

    # Zusammenfassung
    res = pd.DataFrame(results)
    out_csv = os.path.join(ROOT, "rc_stresstest_summary.csv")
    res.to_csv(out_csv, index=False)
    print("\n" + "=" * 72)
    print("STRESSTEST-ZUSAMMENFASSUNG")
    print("=" * 72)
    if not res.empty:
        print(res[["case", "tech", "node", "ratio_pct", "value_build",
                   "value_nobuild", "result"]].to_string(index=False))
        print(f"\n{(res.result == 'PASS').sum()}/{len(res)} Faelle PASS")
    print(f"\nOutputs: {ROOT}\nSummary: {out_csv}")


if __name__ == "__main__":
    main()
