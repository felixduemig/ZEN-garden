"""Validierungsskript: bestaetigt die interpretierbare RC fuer electricity-Carrier-Techs.

Pro Tech wird EIN Knoten getestet (buildable_rc, rc_reliable, gut aufloesbarer RC).
Zwei Modelllaeufe via Datei-Override (rc_capex_file_override):
    build   : CAPEX = capex * (1 - (1+MARGIN)*ratio)  -> 10 % MEHR senken als RC -> MUSS bauen
    nobuild : CAPEX = capex * (1 - (1-MARGIN)*ratio)   -> 10 % WENIGER senken    -> darf NICHT bauen
PASS = build baut UND nobuild baut nicht.

Sicherheitsfilter: nur Techs mit reference_carrier == 'electricity' werden getestet
(die laut Methodik zuverlaessige Klasse). Nicht-electricity-Techs werden uebersprungen.

Aufruf:  python rc_validate_electricity.py
Laufzeit: 1 + 2*len(TARGET_TECHS) volle Modelllaeufe (~6 min je Lauf). TARGET_TECHS
kuerzen fuer weniger.
"""
import json
import os
import glob
from datetime import datetime

import numpy as np
import pandas as pd

from zen_garden import run
from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps

# ---- Stellschrauben -------------------------------------------------------
# None = ALLE electricity-Conversion-Techs automatisch finden und testen;
# alternativ eine feste Liste setzen, z.B. ["photovoltaics", "nuclear"].
TARGET_TECHS = None
NODES_PER_TECH = 1      # Knoten pro Tech (2-3 fuer noch mehr Absicherung)
MARGIN = 0.10           # +/- 10 % der RC
RATIO_MIN, RATIO_MAX = 0.02, 0.80   # nur Knoten mit gut aufloesbarem RC
TARGET_RATIO = 0.20     # bevorzuge Knoten mit RC nahe diesem Anteil (klar testbar)
VALUE_BUILT_TOL = 1e-5
TIGHT_E2P = {"battery": 16, "pumped_hydro": 22, "salt_cavern_storage": 145}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
DATASET = os.path.join(BASE_DIR, "ZEN-models", "data", "Crystal_Ball")
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
    print(f"   ... laeuft '{out_name}'", flush=True)
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


def reference_carrier(tech):
    p = glob.glob(os.path.join(DATASET, "set_technologies", "**", tech, "attributes.json"),
                  recursive=True)
    if not p:
        return None
    a = json.load(open(p[0]))
    v = a.get("reference_carrier", {})
    v = v.get("default_value") if isinstance(v, dict) else v
    return v[0] if isinstance(v, list) and v else v


def discover_electricity_conversion_techs():
    """Alle Conversion-Techs (inkl. Retrofit) mit reference_carrier == 'electricity'."""
    techs = []
    for attr in glob.glob(os.path.join(DATASET, "set_technologies",
                                       "set_conversion_technologies", "**", "attributes.json"),
                          recursive=True):
        tech = os.path.basename(os.path.dirname(attr))
        if tech.startswith("set_"):
            continue
        if reference_carrier(tech) == "electricity":
            techs.append(tech)
    return sorted(set(techs))


def pick_nodes(conv, tech, n):
    """Bis zu n Knoten mit buildable_rc + rc_reliable + RATIO_MIN<=ratio<=RATIO_MAX,
    bevorzugt nahe TARGET_RATIO."""
    rel = conv["rc_reliable"].astype(str).str.lower().isin(["true", "1"])
    cand = conv[(conv.set_technologies == tech) & (conv.case == "buildable_rc") & rel
                & (conv.ratio_reduction >= RATIO_MIN)
                & (conv.ratio_reduction <= RATIO_MAX)].copy()
    if cand.empty:
        return []
    cand["__d"] = (cand.ratio_reduction - TARGET_RATIO).abs()
    return [r for _, r in cand.sort_values("__d").head(n).iterrows()]


def main():
    global ROOT
    ROOT = os.path.join(
        BASE_DIR, f"outputs_{datetime.now():%Y%m%d-%H%M%S}_rc_validate_elec")
    os.makedirs(ROOT, exist_ok=True)
    print(f"RC-Validierung (electricity-Techs) -> {ROOT}\n")
    restore_leftover_swaps(DATASET)

    # Baseline mit Perturbationen -> interpretierbare RC
    print("SCHRITT 1: Baseline-Lauf mit Perturbationen ...")
    cfg = base_config()
    so = cfg["solver"]["solver_options"]
    so["rc_perturbation"] = 0
    so["rc_lifetime_rhs_perturbation"] = 1e-4
    so["rc_storage_power_perturbation"] = 1e-4
    so["rc_tight_e2p"] = TIGHT_E2P
    base_dir = run_model(cfg, "baseline")
    ref_year, interval = year_map(base_dir)
    conv = pd.read_csv(os.path.join(base_dir, "capacity_addition_analysis_conversion.csv"))

    # Ziel-Techs: auto-discover ALLE electricity-Conversion-Techs (oder feste Liste)
    techs = TARGET_TECHS or discover_electricity_conversion_techs()
    print(f"\nSCHRITT 2: {len(techs)} electricity-Conversion-Techs gefunden -> testbare auswaehlen")
    cases = []
    for tech in techs:
        rc_carrier = reference_carrier(tech)
        if rc_carrier != "electricity":
            print(f"   [skip] {tech}: reference_carrier='{rc_carrier}'")
            continue
        nodes = pick_nodes(conv, tech, NODES_PER_TECH)
        if not nodes:
            s = conv[conv.set_technologies == tech]
            why = "ueberall gebaut (RC=0)" if (s.case == "built").all() else \
                  f"kein buildable_rc im {RATIO_MIN:.0%}-{RATIO_MAX:.0%}-Band (zu weit weg / zu nah)"
            print(f"   [skip] {tech}: {why}")
            continue
        cases.extend(nodes)
    if not cases:
        raise SystemExit("Keine validierbaren electricity-Faelle gefunden.")
    print(f"\n   -> {len(cases)} Test-Faelle ({1+2*len(cases)} Modelllaeufe):")
    for r in cases:
        print(f"      {r.set_technologies:20s} {r.set_location:4s} "
              f"capex={r.capex_specific_input_units:9.2f}  RC={r.rc_capex_equivalent_input_units:9.3f}  "
              f"ratio={r.ratio_reduction*100:6.2f}%")

    # build/nobuild je Fall
    print("\nSCHRITT 3: Validierungslaeufe (2 pro Fall) ...")
    results = []
    for r in cases:
        tech, node = r.set_technologies, r.set_location
        yidx = int(r.set_time_steps_yearly)
        year = ref_year + yidx * interval
        ratio = float(r.ratio_reduction)
        c = read_capex(DATASET, tech, node, year)
        print(f"\n[{tech} @ {node}]  ratio={ratio*100:.2f}%  (RC sagt: bei capex {c:.1f} -> {c*(1-ratio):.1f} baut sie)")
        try:
            with capex_file_override(DATASET, [{"tech": tech, "node": node, "year": year,
                                                "value": c * (1 - (1 + MARGIN) * ratio)}]):
                vb = read_value(run_model(base_config(), f"{tech}_{node}_build"), tech, node, yidx)
            with capex_file_override(DATASET, [{"tech": tech, "node": node, "year": year,
                                                "value": c * (1 - (1 - MARGIN) * ratio)}]):
                vn = read_value(run_model(base_config(), f"{tech}_{node}_nobuild"), tech, node, yidx)
        except Exception as e:
            print(f"   !! Fehler ({e})")
            results.append(dict(tech=tech, node=node, ratio_pct=round(ratio*100, 2), result="ERROR"))
            continue
        bb, bn = (np.isfinite(vb) and vb > VALUE_BUILT_TOL), (np.isfinite(vn) and vn > VALUE_BUILT_TOL)
        ok = bb and not bn
        print(f"   build   value={vb:.4g}  gebaut={bb}")
        print(f"   nobuild value={vn:.4g}  gebaut={bn}")
        print(f"   => {'PASS' if ok else 'FAIL'}")
        results.append(dict(tech=tech, node=node, ratio_pct=round(ratio*100, 2),
                            capex=round(c, 2), rc=round(float(r.rc_capex_equivalent_input_units), 3),
                            value_build=vb, value_nobuild=vn, result="PASS" if ok else "FAIL"))

    res = pd.DataFrame(results)
    out_csv = os.path.join(ROOT, "rc_validate_electricity_summary.csv")
    res.to_csv(out_csv, index=False)
    print("\n" + "=" * 64 + "\nVALIDIERUNG electricity-Techs\n" + "=" * 64)
    print(res.to_string(index=False))
    if "result" in res.columns:
        print(f"\n{(res.result == 'PASS').sum()}/{len(res)} PASS")
    print(f"\nSummary: {out_csv}")


if __name__ == "__main__":
    main()
