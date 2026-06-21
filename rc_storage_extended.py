"""Storage-Buendel-Analyse auf dem erweiterten Toy (5_multiple_extended_countries).

Bundle-Prinzip: rc_tight_e2p fixiert die Dauer (battery=16h), rc_storage_power_perturbation
liest die JOINT (power+energy) Bau-Distanz aus der power-Zeile. Ablauf:
  1. Baseline mit Bundle-Config.
  2. Wird battery gebaut? Falls ja: battery-CAPEX (power & energy) hochschrauben (×k),
     bis sie NICHT mehr gebaut wird (dann ist die RC als Bau-Distanz interpretierbar).
  3. Bundle-RC ausgeben (rc_mathematical, RC_power/energy, ratios) + Validierung
     (CAPEX um die RC senken -> sollte wieder bauen).

Aufruf:  python rc_storage_extended.py
"""
import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

from zen_garden import run

E2P = 16
VALUE_BUILT_TOL = 1e-4
ESCALATION = [1.5, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
DATASET = os.path.join(BASE_DIR, "5_multiple_extended_countries")
DATA_NAME = os.path.basename(DATASET)
BAT_ATTR = os.path.join(DATASET, "set_technologies", "set_storage_technologies",
                        "battery", "attributes.json")


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
    so["rc_perturbation"] = 0
    so["rc_lifetime_rhs_perturbation"] = 1e-4
    so["rc_storage_power_perturbation"] = 1e-4
    so["rc_tight_e2p"] = {"battery": E2P}
    return c


def run_model(config, out_name):
    out = os.path.join(ROOT, out_name)
    os.makedirs(out, exist_ok=True)
    tmp = os.path.join(out, "_config.json")
    with open(tmp, "w") as f:
        json.dump(config, f, indent=2)
    print(f"   ... laeuft '{out_name}'", flush=True)
    run(config=tmp, dataset=DATASET, folder_output=out)
    os.remove(tmp)
    return os.path.join(out, DATA_NAME)


def get_battery_capex():
    a = json.load(open(BAT_ATTR))
    return (float(a["capex_specific_storage"]["default_value"]),
            float(a["capex_specific_storage_energy"]["default_value"]))


def set_battery_capex(power, energy):
    a = json.load(open(BAT_ATTR))
    a["capex_specific_storage"]["default_value"] = power
    a["capex_specific_storage_energy"]["default_value"] = energy
    json.dump(a, open(BAT_ATTR, "w"), indent=2)


def read_storage(scenario_dir, tech="battery"):
    f = os.path.join(scenario_dir, "capacity_addition_analysis_storage.csv")
    if not os.path.isfile(f):
        return None
    d = pd.read_csv(f)
    return d[d.set_technologies == tech].copy()


def show(bat, label):
    cols = ["set_location", "set_time_steps_yearly", "value_power", "value_energy",
            "case", "rc_mathematical", "e2p", "capex_power", "capex_energy",
            "C_bundle", "ratio_reduction_proportional", "rc_reliable"]
    cols = [c for c in cols if c in bat.columns]
    print(f"\n--- battery ({label}) ---")
    print(bat[cols].to_string(index=False))
    built = (bat.value_power.fillna(0) > VALUE_BUILT_TOL).any()
    print(f"   gebaut (value_power>0 an einem Knoten/Jahr)?  {built}")
    return built


def main():
    global ROOT
    ROOT = os.path.join(BASE_DIR, f"outputs_{datetime.now():%Y%m%d-%H%M%S}_rc_storage_ext")
    os.makedirs(ROOT, exist_ok=True)
    base_p, base_e = get_battery_capex()
    print(f"Storage-Bundle-Analyse -> {ROOT}")
    print(f"battery base-CAPEX: power={base_p:.2f}  energy={base_e:.2f}  e2p={E2P}\n")

    try:
        # 1) Baseline
        print("SCHRITT 1: Baseline (Bundle-Config) ...")
        sd = run_model(base_config(), "baseline")
        bat = read_storage(sd)
        if bat is None:
            raise SystemExit("Keine Storage-CSV erzeugt.")
        built = show(bat, "baseline")

        # 2) hochschrauben, falls gebaut
        kfac = 1.0
        if built:
            print("\nSCHRITT 2: battery wird gebaut -> CAPEX hochschrauben bis NICHT gebaut ...")
            for k in ESCALATION:
                set_battery_capex(base_p * k, base_e * k)
                sd = run_model(base_config(), f"capex_x{k:g}")
                bat = read_storage(sd)
                built = show(bat, f"capex ×{k:g}")
                kfac = k
                if not built:
                    print(f"\n   -> nicht mehr gebaut bei CAPEX ×{k:g}")
                    break
            else:
                print("\n   !! selbst bei ×20 noch gebaut — Storage extrem wirtschaftlich.")
        else:
            print("\nSCHRITT 2: battery wird NICHT gebaut -> RC direkt interpretierbar (kein Hochschrauben noetig).")

        # 3) Bundle-RC interpretieren (am nicht-gebauten Punkt)
        print("\n" + "=" * 78)
        print(f"BUNDLE-RC (battery, CAPEX ×{kfac:g}) — interpretierbarer Bau-Abstand")
        print("=" * 78)
        cand = bat[(bat.case == "buildable_rc")
                   & bat.rc_reliable.astype(str).str.lower().isin(["true", "1"])]
        if cand.empty:
            print("Keine buildable_rc-Bundle-Zeile (evtl. alle gebaut/blockiert).")
        else:
            cols = ["set_location", "set_time_steps_yearly", "rc_mathematical", "e2p",
                    "capex_power", "capex_energy", "C_bundle", "RC_power", "RC_energy",
                    "ratio_power_reduction", "ratio_energy_reduction",
                    "ratio_reduction_proportional"]
            print(cand[[c for c in cols if c in cand.columns]].to_string(index=False))
            print("\nLesart: rc_mathematical = Bundle-Distanz (power-Zeile); ratio_reduction_proportional")
            print("        = Anteil, um den BEIDE capex (power & energy) sinken muessten, damit battery baut.")
        bat.to_csv(os.path.join(ROOT, "battery_bundle_rc.csv"), index=False)
        print(f"\nCSV: {os.path.join(ROOT,'battery_bundle_rc.csv')}")
    finally:
        set_battery_capex(base_p, base_e)  # Original-CAPEX wiederherstellen
        print("\n[restore] battery-CAPEX auf Original zurueckgesetzt.")


if __name__ == "__main__":
    main()
