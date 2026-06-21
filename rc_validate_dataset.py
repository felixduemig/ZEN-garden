"""Strukturierte Validierung der Reduced-Cost-Formeln fuer 5_multiple_extended_countries.

Ground-Truth-Prinzip: fuer jeden geprueften Fall zwei Modelllaeufe via Datei-CAPEX-Override.
  build   : CAPEX so senken, dass die Senkung 10 % > RC ist  -> Tech MUSS bauen
  nobuild : CAPEX so senken, dass die Senkung 10 % < RC ist   -> Tech darf NICHT bauen
PASS = build baut UND nobuild baut nicht.

Zwei Tech-Klassen, zwei Formeln:
  CONVERSION  rc = capex - Wert/scaling.  Override: capex * (1 - faktor*ratio_reduction).
  STORAGE     Bundle: rc_mathematical = C_bundle - V, beide CAPEX um denselben Anteil f
              (= ratio_reduction_proportional) senken.  Override: power UND energy capex
              * (1 - faktor*f).  (e2p im Validierungslauf fixiert -> selbe Dauer wie RC.)

Ausgeschlossen:
  * Multi-Year-Carry-over (conversion): capacity - value > CARRY_TOL  -> bereits gebaut.
    (Storage-Carry-over ist schon in der Klassifikation als 'built' gefiltert.)
  * Nicht aufloesbare RC: ratio ausserhalb [RATIO_MIN, RATIO_MAX] (capex muss positiv bleiben).
  * rc_reliable == False (Platzhalter etc.).

Aufruf:  python rc_validate_dataset.py
"""
import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

from zen_garden import run
from rc_capex_file_override import capex_file_override, read_capex, restore_leftover_swaps

# ---- Stellschrauben -------------------------------------------------------
N_PER_TECH = 3          # Faelle pro Technologie (None = alle testbaren)
MARGIN = 0.10           # +/- 10 % der RC
RATIO_MIN, RATIO_MAX = 0.03, 0.85   # gut aufloesbares Band; capex bleibt positiv
CARRY_TOL = 1e-2        # capacity - value darueber -> carry-over-gebaut (ausschliessen)
VALUE_BUILT_TOL = 1e-4
TIGHT_E2P = {"battery": 16, "pumped_hydro": 22}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
DATASET = os.path.join(BASE_DIR, "5_multiple_extended_countries")
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
    so["rc_tight_e2p"] = dict(TIGHT_E2P)   # Dauer fix -> Storage baut bei selber Dauer
    return c


def baseline_config():
    """Wie base, plus die Perturbationen -> interpretierbare RC."""
    c = base_config()
    so = c["solver"]["solver_options"]
    so["rc_perturbation"] = 0
    so["rc_lifetime_rhs_perturbation"] = 1e-3
    so["rc_storage_power_perturbation"] = 1e-4
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


def read_value(scenario_dir, tech, node, yidx, ctype="power"):
    f = os.path.join(scenario_dir, "capacity_addition_analysis.csv")
    if not os.path.isfile(f):
        return np.nan
    d = pd.read_csv(f)
    r = d[(d.set_technologies == tech) & (d.set_capacity_types == ctype)
          & (d.set_location == node) & (d.set_time_steps_yearly == yidx)]
    return float(r["value"].iloc[0]) if not r.empty else np.nan


def _reliable(df):
    return df["rc_reliable"].astype(str).str.lower().isin(["true", "1"])


def _spread(cand, n):
    """n ueber die Ratio-Spanne verteilte Zeilen (oder alle)."""
    cand = cand.sort_values("__ratio")
    if n is None or len(cand) <= n:
        return [r for _, r in cand.iterrows()]
    idx = np.unique(np.linspace(0, len(cand) - 1, n).round().astype(int))
    return [cand.iloc[i] for i in idx]


def select_conversion(conv):
    rel = _reliable(conv)
    cand = conv[(conv.case == "buildable_rc") & rel
                & ((conv.capacity - conv.value) <= CARRY_TOL)        # kein carry-over
                & (conv.ratio_reduction > RATIO_MIN)
                & (conv.ratio_reduction <= RATIO_MAX)].copy()
    cand["__ratio"] = cand.ratio_reduction
    out = []
    for tech, g in cand.groupby("set_technologies"):
        out += _spread(g, N_PER_TECH)
    return out


def select_storage(stor):
    rel = _reliable(stor)
    cand = stor[(stor.case == "buildable_rc") & rel
                & (stor.ratio_reduction_proportional > RATIO_MIN)
                & (stor.ratio_reduction_proportional <= RATIO_MAX)].copy()
    cand["__ratio"] = cand.ratio_reduction_proportional
    out = []
    for tech, g in cand.groupby("set_technologies"):
        out += _spread(g, N_PER_TECH)
    return out


def validate_conversion(r, ref_year, interval):
    tech, node = r.set_technologies, r.set_location
    yidx = int(r.set_time_steps_yearly); year = ref_year + yidx * interval
    ratio = float(r.ratio_reduction)
    c = read_capex(DATASET, tech, node, year)
    tag = f"conv_{tech}_{node}_y{yidx}"
    with capex_file_override(DATASET, [{"tech": tech, "node": node, "year": year,
                                        "value": c * (1 - (1 + MARGIN) * ratio)}]):
        vb = read_value(run_model(base_config(), tag + "_build"), tech, node, yidx)
    with capex_file_override(DATASET, [{"tech": tech, "node": node, "year": year,
                                        "value": c * (1 - (1 - MARGIN) * ratio)}]):
        vn = read_value(run_model(base_config(), tag + "_nobuild"), tech, node, yidx)
    return dict(tech_type="conversion", tech=tech, node=node, year_idx=yidx,
                ratio_pct=round(ratio * 100, 2),
                rc=round(float(r.rc_capex_equivalent_input_units), 2)), vb, vn


def validate_storage(r, ref_year, interval):
    tech, node = r.set_technologies, r.set_location
    yidx = int(r.set_time_steps_yearly); year = ref_year + yidx * interval
    f = float(r.ratio_reduction_proportional)
    cp = read_capex(DATASET, tech, node, year, "power")
    ce = read_capex(DATASET, tech, node, year, "energy")
    tag = f"stor_{tech}_{node}_y{yidx}"

    def ov(scale):  # beide CAPEX um denselben Anteil senken (Bundle proportional)
        return [{"tech": tech, "node": node, "year": year, "capacity_type": "power",
                 "value": cp * scale},
                {"tech": tech, "node": node, "year": year, "capacity_type": "energy",
                 "value": ce * scale}]

    with capex_file_override(DATASET, ov(1 - (1 + MARGIN) * f)):
        vb = read_value(run_model(base_config(), tag + "_build"), tech, node, yidx, "power")
    with capex_file_override(DATASET, ov(1 - (1 - MARGIN) * f)):
        vn = read_value(run_model(base_config(), tag + "_nobuild"), tech, node, yidx, "power")
    return dict(tech_type="storage", tech=tech, node=node, year_idx=yidx,
                ratio_pct=round(f * 100, 2),
                rc=round(float(r.rc_mathematical), 2)), vb, vn


def main():
    global ROOT
    ROOT = os.path.join(BASE_DIR, f"outputs_{datetime.now():%Y%m%d-%H%M%S}_rc_validate_dataset")
    os.makedirs(ROOT, exist_ok=True)
    print(f"RC-Formel-Validierung ({DATA_NAME}) -> {ROOT}\n")
    restore_leftover_swaps(DATASET)

    print("SCHRITT 1: Baseline mit Perturbationen (interpretierbare RC) ...")
    base_dir = run_model(baseline_config(), "baseline")
    ref_year, interval = year_map(base_dir)
    conv = pd.read_csv(os.path.join(base_dir, "capacity_addition_analysis_conversion.csv"))
    stor = pd.read_csv(os.path.join(base_dir, "capacity_addition_analysis_storage.csv"))

    conv_cases = select_conversion(conv)
    stor_cases = select_storage(stor)
    total = len(conv_cases) + len(stor_cases)
    print(f"\nSCHRITT 2: {len(conv_cases)} conversion- + {len(stor_cases)} storage-Faelle "
          f"({1 + 2 * total} Modelllaeufe)")
    for r in conv_cases:
        print(f"   [conv] {r.set_technologies:20s} {r.set_location} y{int(r.set_time_steps_yearly)}  "
              f"ratio={r.ratio_reduction*100:6.2f}%")
    for r in stor_cases:
        print(f"   [stor] {r.set_technologies:20s} {r.set_location} y{int(r.set_time_steps_yearly)}  "
              f"f={r.ratio_reduction_proportional*100:6.2f}%")
    if total == 0:
        raise SystemExit("Keine testbaren Faelle gefunden.")

    print("\nSCHRITT 3: Build/Nobuild ...")
    results = []
    for r in conv_cases + stor_cases:
        is_stor = (r.set_technologies in TIGHT_E2P) or ("ratio_reduction_proportional" in r.index)
        try:
            meta, vb, vn = (validate_storage(r, ref_year, interval) if is_stor
                            else validate_conversion(r, ref_year, interval))
        except Exception as e:
            print(f"   !! Fehler ({r.set_technologies} {r.set_location}): {e}")
            continue
        bb = np.isfinite(vb) and vb > VALUE_BUILT_TOL
        bn = np.isfinite(vn) and vn > VALUE_BUILT_TOL
        ok = bb and not bn
        meta.update(value_build=vb, value_nobuild=vn, result="PASS" if ok else "FAIL")
        results.append(meta)
        print(f"   [{meta['tech_type'][:4]}] {meta['tech']:20s} {meta['node']} y{meta['year_idx']} "
              f"ratio={meta['ratio_pct']:6.2f}%  build={vb:.4g} nobuild={vn:.4g} => {meta['result']}")

    res = pd.DataFrame(results)
    out_csv = os.path.join(ROOT, "rc_validate_dataset_summary.csv")
    res.to_csv(out_csv, index=False)
    print("\n" + "=" * 78 + "\nVALIDIERUNG RC-FORMELN — " + DATA_NAME + "\n" + "=" * 78)
    if not res.empty:
        print(res[["tech_type", "tech", "node", "year_idx", "ratio_pct",
                   "value_build", "value_nobuild", "result"]].to_string(index=False))
        for tt, g in res.groupby("tech_type"):
            print(f"\n  {tt:11s}: {(g.result=='PASS').sum()}/{len(g)} PASS")
        print(f"\n  GESAMT     : {(res.result=='PASS').sum()}/{len(res)} PASS")
    print(f"\nSummary: {out_csv}")


if __name__ == "__main__":
    main()
