"""Erweiterte, klassifizierte RC-Analyse fuer einen *bestehenden* Output-Ordner.

Spiegelt 1:1 die Logik von
`Postprocess.save_capacity_addition_classified()` (postprocess.py), erzeugt die
Ergebnisse aber aus den schon geschriebenen CSVs, damit man einen alten Lauf
auswerten kann, ohne das Modell neu zu loesen.

Unterschied zur In-Model-Variante: CAPEX und e2p werden nicht aus den
Model-Parametern gelesen, sondern
  * CAPEX  : aus capacity_addition_analysis.csv + rc_components.csv zurueckgerechnet
             capex_specific = rc_capex_equivalent - sum(contribution_to_rc)
             (exakte Identitaet; erfasst Per-Node/Per-Year-Werte; = Wert in den
              capex-Files fuer das Planungsjahr) -> /fraction_year = Euro/kW.
  * e2p    : aus den attributes.json der Storage-Technologien (energy_to_power_ratio_min).
  * Tech-Typ: aus der Ordnerstruktur des Datensatzes.

Nutzung:
  python rc_classify_existing.py [OUTPUT_DIR] [--dataset DATASET_DIR]

OUTPUT_DIR  = Ordner mit capacity_addition_analysis.csv (+ rc_components.csv,
              system.json). Default: der zuletzt analysierte Lauf unten.
DATASET_DIR = Datensatz-Wurzel mit set_technologies/. Default: Crystal_Ball.

Schreibt neben die Eingabe:
  capacity_addition_analysis_conversion.csv
  capacity_addition_analysis_transport.csv
  capacity_addition_analysis_storage.csv
"""
import os
import sys
import json
import argparse
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_OUT = os.path.join(
    BASE,
    "outputs_20260617-175519",
    "Output_afterBatteryCHRC_combined_implemented",
    "Crystal_Ball",
)
DEFAULT_DATA = os.path.join(BASE, "ZEN-models", "data", "Crystal_Ball")

# ── Toleranzen (identisch zu postprocess.save_capacity_addition_classified) ──
CEIL_ZERO = 1e-6
CEIL_REL = 1e-4
RC_ZERO = 1e-6
VALUE_TOL = 1e-6
YOTTA = 1e-4                      # Storage-Power-Probe (rc_storage_power_perturbation)
STORAGE_BUILT_TOL = max(5.0 * YOTTA, VALUE_TOL)

IDX = ["set_technologies", "set_capacity_types", "set_location", "set_time_steps_yearly"]
STORAGE_PLACEHOLDER = ("oil_storage", "natural_gas_storage")


def tech_types(dataset_dir, out_dir=None):
    """tech -> 'conversion'|'transport'|'storage'.

    Primaer aus system.json des Outputs (enthaelt alle Set-Mitgliedschaften,
    inkl. set_retrofitting_technologies). Fallback: Ordnerstruktur des Datensatzes.
    Retrofitting-Technologien (*_CCS) sind Conversion-artig -> 'conversion'.
    """
    # Klassen-Reihenfolge: retrofitting zuletzt (gewinnt -> 'conversion')
    classes = (("set_conversion_technologies", "conversion"),
               ("set_transport_technologies", "transport"),
               ("set_storage_technologies", "storage"),
               ("set_retrofitting_technologies", "conversion"))
    mapping = {}
    sysd = None
    if out_dir:
        try:
            sysd = json.load(open(os.path.join(out_dir, "system.json")))
        except Exception:
            sysd = None
    if sysd:
        for sname, name in classes:
            for t in sysd.get(sname, []) or []:
                mapping[str(t)] = name
        if mapping:
            return mapping
    # Fallback: Ordnerstruktur (kennt keine retrofitting techs)
    base = os.path.join(dataset_dir, "set_technologies")
    for sub, name in classes[:3]:
        d = os.path.join(base, sub)
        if not os.path.isdir(d):
            continue
        for t in os.listdir(d):
            if os.path.isdir(os.path.join(d, t)):
                mapping[t] = name
    return mapping


def e2p_ratios(dataset_dir, out_dir=None):
    """Storage-Tech -> D (energy_to_power_ratio_min); ungueltig/0 -> nan.

    Primaer aus dem Output (`param_dict.h5`), weil das den tatsaechlichen Run
    widerspiegelt — inkl. config-getriebener Tight-e2p-Overrides (rc_tight_e2p) und
    unabhaengig davon, ob der Datensatz inzwischen geaendert/zurueckgesetzt wurde.
    Fallback: `attributes.json` im Datensatz.
    """
    # 1) param_dict.h5 des Outputs
    if out_dir:
        try:
            s = pd.read_hdf(os.path.join(out_dir, "param_dict.h5"),
                            "energy_to_power_ratio_min")
            out = {}
            for tech, v in s.items():
                try:
                    v = float(v)
                except Exception:
                    v = np.nan
                out[str(tech)] = v if (np.isfinite(v) and v > 0) else np.nan
            if out:
                return out
        except Exception:
            pass
    # 2) Fallback: attributes.json im Datensatz
    out = {}
    d = os.path.join(dataset_dir, "set_technologies", "set_storage_technologies")
    if not os.path.isdir(d):
        return out
    for t in os.listdir(d):
        attr = os.path.join(d, t, "attributes.json")
        if not os.path.isfile(attr):
            continue
        try:
            a = json.load(open(attr))
            v = float(a.get("energy_to_power_ratio_min", {}).get("default_value"))
        except Exception:
            v = np.nan
        out[t] = v if (np.isfinite(v) and v > 0) else np.nan
    return out


def storage_capex_from_csv(dataset_dir):
    """Liest die Storage-CAPEX *direkt* aus den Input-CSVs (1:1, keine Skalierung).

    Storage-CAPEX sind sauberes Euro/kW (power) bzw. Euro/kWh (energy), node- und
    jahresaufgeloest -> hier ist die Input-CSV exakt der Wert, gegen den die RC
    gemessen wird (anders als bei Conversion-Techs mit Nicht-kW-Referenzeinheiten).

    Returns {(tech, ctype) -> {"by_node_year": {(node, year): val},
                               "by_year": {year: val},   # node-lose Files
                               "default": float}}.
    """
    out = {}
    d = os.path.join(dataset_dir, "set_technologies", "set_storage_technologies")
    if not os.path.isdir(d):
        return out
    files = (("power", "capex_specific_storage.csv", "capex_specific_storage"),
             ("energy", "capex_specific_storage_energy.csv", "capex_specific_storage_energy"))
    for tech in os.listdir(d):
        fol = os.path.join(d, tech)
        if not os.path.isdir(fol):
            continue
        try:
            attr = json.load(open(os.path.join(fol, "attributes.json")))
        except Exception:
            attr = {}
        for ctype, fname, akey in files:
            try:
                default = float(attr.get(akey, {}).get("default_value"))
            except Exception:
                default = np.nan
            by_node_year, by_year = {}, {}
            fp = os.path.join(fol, fname)
            if os.path.isfile(fp):
                try:
                    df = pd.read_csv(fp)
                    valcol = [c for c in df.columns if c.startswith("capex")][0]
                    has_year = "year" in df.columns
                    has_node = "node" in df.columns
                    for _, r in df.iterrows():
                        v = float(r[valcol])
                        yr = int(r["year"]) if has_year else None
                        if has_node:
                            by_node_year[(str(r["node"]), yr)] = v
                        else:
                            by_year[yr] = v
                except Exception:
                    pass
            out[(tech, ctype)] = {"by_node_year": by_node_year,
                                  "by_year": by_year, "default": default}
    return out


def lookup_storage_capex(store, tech, ctype, node, year):
    """CSV-CAPEX fuer (tech, ctype, node, year); Fallback: node-los -> default."""
    e = store.get((str(tech), ctype))
    if not e:
        return np.nan
    v = e["by_node_year"].get((str(node), year))
    if v is None:
        v = e["by_node_year"].get((str(node), None))
    if v is None:
        v = e["by_year"].get(year, e["by_year"].get(None))
    if v is None:
        v = e["default"]
    return v


def classify(value, capacity, ceiling, rc, built_tol):
    v = value if np.isfinite(value) else 0.0
    cap = capacity if np.isfinite(capacity) else 0.0
    rcv = rc if np.isfinite(rc) else 0.0
    inf_ceiling = not np.isfinite(ceiling)
    if v > built_tol:
        return "built"
    if (not inf_ceiling) and ceiling <= CEIL_ZERO:
        return "not_buildable"
    if (not inf_ceiling) and cap > CEIL_ZERO \
            and abs(cap - ceiling) <= CEIL_REL * max(1.0, abs(ceiling)):
        return "at_limit"
    if rcv > RC_ZERO:
        return "buildable_rc"
    if rcv < -RC_ZERO:
        return "blocked_profitable"
    return "breakeven_unreliable"


def run(out_dir, dataset_dir):
    cap = pd.read_csv(os.path.join(out_dir, "capacity_addition_analysis.csv"))
    comp = pd.read_csv(os.path.join(out_dir, "rc_components.csv"))
    try:
        sysd = json.load(open(os.path.join(out_dir, "system.json")))
        fy = sysd["unaggregated_time_steps_per_year"] / sysd["total_hours_per_year"]
        ref_year = int(sysd.get("reference_year", 0))
        interval = int(sysd.get("interval_between_years", 1))
    except Exception:
        fy, ref_year, interval = 1.0, 0, 1

    ttype = tech_types(dataset_dir, out_dir)
    e2p = e2p_ratios(dataset_dir, out_dir)  # primaer aus Output-param_dict.h5
    storage_csv = storage_capex_from_csv(dataset_dir)  # Storage-CAPEX 1:1 aus Input-CSV

    # CAPEX (model units) zurueckrechnen: capex = rc - sum(contribution_to_rc)
    csum = comp.groupby(IDX)["contribution_to_rc"].sum().rename("contrib_sum")
    m = cap.merge(csum, on=IDX, how="left")
    m["contrib_sum"] = m["contrib_sum"].fillna(0.0)
    m["capex_specific_input_units"] = (m["rc_capex_equivalent"] - m["contrib_sum"]) / fy
    m["tech_type"] = m["set_technologies"].map(lambda t: ttype.get(str(t), "unknown"))

    unknown = sorted(m.loc[m.tech_type == "unknown", "set_technologies"].unique())
    if unknown:
        print(f"[warn] kein Tech-Typ fuer: {unknown} (werden uebersprungen)")

    # ── conversion / transport ──────────────────────────────────────────────
    ns = m[m.tech_type.isin(["conversion", "transport"])].copy()
    if not ns.empty:
        ns["case"] = [classify(r.value, r.capacity, r.capacity_ceiling,
                               r.rc_capex_equivalent_input_units, VALUE_TOL)
                      for r in ns.itertuples()]

        def ratio(r):
            cs = r.capex_specific_input_units
            if r.case in ("built", "buildable_rc") and np.isfinite(cs) and cs > CEIL_ZERO:
                return r.rc_capex_equivalent_input_units / cs
            return np.nan
        ns["ratio_reduction"] = [ratio(r) for r in ns.itertuples()]
        ns["rc_reliable"] = ns["case"].isin(["built", "buildable_rc"])

        cols = IDX + ["tech_type", "unit", "value", "capacity", "capacity_ceiling",
                      "vbasis", "case", "capex_specific_input_units",
                      "rc_capex_equivalent", "rc_capex_equivalent_input_units",
                      "ratio_reduction", "rc_reliable"]
        for tname in ("conversion", "transport"):
            sub = ns[ns.tech_type == tname]
            if sub.empty:
                continue
            f = os.path.join(out_dir, f"capacity_addition_analysis_{tname}.csv")
            sub[cols].to_csv(f, index=False)
            print(f"[ok] {tname:11s} -> {os.path.basename(f)} ({len(sub)} Zeilen)")
            _summary(sub, "case")

    # ── storage (Buendel-Struktur) ──────────────────────────────────────────
    st = m[m.tech_type == "storage"].copy()
    if not st.empty:
        pw = st[st.set_capacity_types == "power"].set_index(
            ["set_technologies", "set_location", "set_time_steps_yearly"])
        en = st[st.set_capacity_types == "energy"].set_index(
            ["set_technologies", "set_location", "set_time_steps_yearly"])
        rows = []
        max_capex_dev = 0.0   # groesste Abweichung CSV vs. Back-Out (Cross-Check)
        for key in pw.index.union(en.index):
            tech, node, yidx = key
            year = ref_year + int(yidx) * interval
            p = pw.loc[key] if key in pw.index else None
            e = en.loc[key] if key in en.index else None
            D = e2p.get(str(tech), np.nan)

            v_p = float(p["value"]) if p is not None else np.nan
            cap_p = float(p["capacity"]) if p is not None else np.nan
            ceil_p = float(p["capacity_ceiling"]) if p is not None else np.nan
            rc_p = float(p["rc_capex_equivalent_input_units"]) if p is not None else np.nan

            # CAPEX 1:1 aus den Storage-Input-CSVs (Euro/kW power, Euro/kWh energy).
            cx_p = lookup_storage_capex(storage_csv, tech, "power", node, year)
            cx_e = lookup_storage_capex(storage_csv, tech, "energy", node, year)
            # Back-Out als stiller Konsistenz-Check (muss fuer Storage exakt passen).
            bo_p = float(p["capex_specific_input_units"]) if p is not None else np.nan
            bo_e = float(e["capex_specific_input_units"]) if e is not None else np.nan
            for csv_v, bo_v in ((cx_p, bo_p), (cx_e, bo_e)):
                if np.isfinite(csv_v) and np.isfinite(bo_v):
                    max_capex_dev = max(max_capex_dev,
                                        abs(csv_v - bo_v) / max(1.0, abs(bo_v)))
            # Falls die CSV einen Wert nicht liefert: Back-Out als Fallback.
            if not np.isfinite(cx_p):
                cx_p = bo_p
            if not np.isfinite(cx_e):
                cx_e = bo_e

            case = classify(v_p, cap_p, ceil_p, rc_p, STORAGE_BUILT_TOL) \
                if p is not None else "no_power_row"

            C_bundle = (cx_p + D * cx_e) if (np.isfinite(D) and np.isfinite(cx_p)
                                             and np.isfinite(cx_e)) else np.nan
            delta = (rc_p / (1.0 + D)) if (np.isfinite(D) and np.isfinite(rc_p)) else np.nan
            ratio_p = (delta / cx_p) if (np.isfinite(delta) and np.isfinite(cx_p)
                                         and cx_p > CEIL_ZERO) else np.nan
            ratio_e = (delta / cx_e) if (np.isfinite(delta) and np.isfinite(cx_e)
                                         and cx_e > CEIL_ZERO) else np.nan
            f_prop = (rc_p / C_bundle) if (np.isfinite(rc_p) and np.isfinite(C_bundle)
                                           and C_bundle > CEIL_ZERO) else np.nan

            placeholder = (str(tech) in STORAGE_PLACEHOLDER) or (not np.isfinite(D))
            rc_reliable = (case in ("built", "buildable_rc")) and (not placeholder)
            if case not in ("built", "buildable_rc"):
                delta = ratio_p = ratio_e = f_prop = np.nan

            rows.append({
                "set_technologies": tech, "set_location": key[1],
                "set_time_steps_yearly": key[2], "tech_type": "storage",
                "unit_power": (p["unit"] if p is not None else np.nan),
                "unit_energy": (e["unit"] if e is not None else np.nan),
                "value_power": v_p,
                "value_energy": (float(e["value"]) if e is not None else np.nan),
                "capacity_power": cap_p,
                "capacity_energy": (float(e["capacity"]) if e is not None else np.nan),
                "capacity_ceiling_power": ceil_p,
                "capacity_ceiling_energy": (float(e["capacity_ceiling"])
                                            if e is not None else np.nan),
                "vbasis_power": (p["vbasis"] if p is not None else np.nan),
                "case": case,
                "rc_mathematical": rc_p,
                "e2p": D,
                "capex_power": cx_p,
                "capex_energy": cx_e,
                "C_bundle": C_bundle,
                "RC_power": delta,
                "RC_energy": delta,
                "ratio_power_reduction": ratio_p,
                "ratio_energy_reduction": ratio_e,
                "ratio_reduction_proportional": f_prop,
                "rc_reliable": rc_reliable,
            })
        st_df = pd.DataFrame(rows).sort_values(
            ["set_technologies", "set_location", "set_time_steps_yearly"])
        f = os.path.join(out_dir, "capacity_addition_analysis_storage.csv")
        st_df.to_csv(f, index=False)
        print(f"[ok] storage     -> {os.path.basename(f)} ({len(st_df)} Zeilen)")
        print(f"     CAPEX-Quelle: Input-CSV (1:1); Cross-Check vs. Back-Out: "
              f"max. Abweichung {max_capex_dev:.2e}"
              + ("  OK" if max_capex_dev < 1e-6 else "  ** PRUEFEN (Jahr-Mapping?) **"))
        _summary(st_df, "case")
        # naheste ungebaute Speicher
        close = st_df[(st_df.case == "buildable_rc") & st_df.rc_reliable]
        if not close.empty:
            print("\n  Naheste ungebaute Speicher (kleinste ratio_energy_reduction):")
            cc = close.sort_values("ratio_energy_reduction").head(8)
            for r in cc.itertuples():
                print(f"    {r.set_technologies:20s} {r.set_location:4s} "
                      f"ratio_energy={r.ratio_energy_reduction:6.3f} "
                      f"ratio_power={r.ratio_power_reduction if np.isfinite(r.ratio_power_reduction) else float('nan'):8.3f} "
                      f"f_prop={r.ratio_reduction_proportional:6.3f}")


def _summary(df, col):
    counts = df[col].value_counts()
    print("     " + "  ".join(f"{k}={v}" for k, v in counts.items()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir", nargs="?", default=DEFAULT_OUT)
    ap.add_argument("--dataset", default=DEFAULT_DATA)
    args = ap.parse_args()
    print(f"Output : {args.out_dir}")
    print(f"Dataset: {args.dataset}\n")
    run(args.out_dir, args.dataset)
