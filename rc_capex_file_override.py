"""Wiederverwendbare per-(tech, node, year) CAPEX-Override-Mechanik via Daten-CSV.

Robuste Alternative zum In-Memory-`rc_capex_override`: der Wert wird in die capex-
Input-CSV der Technologie geschrieben (den Pfad, den das Modell zuverlaessig liest),
das Modell laeuft, danach wird die Original-CSV byte-genau wiederhergestellt — auch
bei Fehlern.

Verwendung (Kontextmanager):

    from rc_capex_file_override import capex_file_override, read_capex

    overrides = [
        {"tech": "nuclear", "node": "NL", "year": 2050, "value": 4500.0},     # Euro/kW
        {"tech": "battery", "node": "CH", "year": 2050,
         "capacity_type": "power", "value": 70.0},                            # Euro/kW
    ]
    with capex_file_override(dataset_path, overrides):
        run(config=..., dataset=dataset_path, folder_output=...)
    # Datensatz ist hier wieder im Originalzustand

`value` ist in den NATIVEN capex-Input-Einheiten der Technologie (wie die bestehende
CSV / der attributes.json-default_value): Euro/kW (power), Euro/kWh (storage energy),
oder was der Referenzcarrier vorgibt (z.B. Euro/(tCO2eq/hour) bei CCS). Mit
`read_capex(...)` holt man den aktuellen Effektivwert (z.B. fuer eine relative Aenderung).

Funktionsweise: year-only- bzw. attributes-only-Parameter werden zu einer vollen
node x year-CSV expandiert, in der NUR die Zielzellen ersetzt sind; alle anderen
Knoten/Jahre behalten ihren Originalwert. node x year-CSVs werden direkt an der Zelle
geaendert.
"""
import os
import json
from contextlib import contextmanager

import pandas as pd

BAK = ".rcoverride_bak"   # Suffix der temporaeren Sicherung


# ---------------------------------------------------------------------------
# Dataset-Helfer
# ---------------------------------------------------------------------------
def _nodes(dataset):
    """Modell-Knoten: bevorzugt system.json set_nodes, sonst energy_system/set_nodes.csv."""
    try:
        s = json.load(open(os.path.join(dataset, "system.json")))
        n = s.get("set_nodes")
        if n:
            return sorted(str(x) for x in n)
    except Exception:
        pass
    try:
        f = os.path.join(dataset, "energy_system", "set_nodes.csv")
        return sorted(pd.read_csv(f)["node"].astype(str).unique())
    except Exception:
        return []


def _reference_years(dataset):
    """Voller Jahresbereich: aus einer conversion-capex-CSV, sonst aus system.json."""
    base = os.path.join(dataset, "set_technologies", "set_conversion_technologies")
    for dp, _, files in os.walk(base):
        for f in files:
            if f.startswith("capex_specific_conversion") and f.endswith(".csv"):
                try:
                    d = pd.read_csv(os.path.join(dp, f))
                    if "year" in d.columns:
                        return sorted(int(y) for y in d["year"].unique())
                except Exception:
                    pass
    # Fallback (z.B. Toy ohne capex-CSVs): aus system.json ableiten
    try:
        s = json.load(open(os.path.join(dataset, "system.json")))
        ry = int(s.get("reference_year", 0))
        iv = int(s.get("interval_between_years", 1)) or 1
        ny = int(s.get("optimized_years", 1))
        if ny >= 1:
            return [ry + i * iv for i in range(ny)]
    except Exception:
        pass
    return []


def _tech_folder(dataset, tech):
    base = os.path.join(dataset, "set_technologies")
    for dp, _, files in os.walk(base):
        if os.path.basename(dp) == tech and "attributes.json" in files:
            return dp
    return None


def _capex_meta(dataset, tech, capacity_type):
    """(folder, param_name, csv_path); param_name ist auch der Default-Werte-Spaltenname."""
    folder = _tech_folder(dataset, tech)
    if folder is None:
        return None
    if "set_storage_technologies" in folder:
        name = ("capex_specific_storage_energy" if capacity_type == "energy"
                else "capex_specific_storage")
    elif "set_transport_technologies" in folder:
        name = "capex_specific_transport"
    else:  # conversion incl. retrofitting
        name = "capex_specific_conversion"
    return folder, name, os.path.join(folder, name + ".csv")


def _attr_default(folder, akey):
    try:
        a = json.load(open(os.path.join(folder, "attributes.json")))
        return float(a.get(akey, {}).get("default_value"))
    except Exception:
        return float("nan")


def _valcol(orig, akey):
    """Werte-Spalte = Nicht-Index-Spalte (Name variiert: param- ODER tech-benannt)."""
    if orig is None:
        return akey
    nonidx = [c for c in orig.columns if c not in ("node", "year")]
    return nonidx[0] if nonidx else akey


def _effective(orig, valcol, default, node, year):
    """Original-Effektivwert fuer (node, year) in Input-Einheiten."""
    if orig is None:
        return default
    cols = orig.columns
    sub = orig
    if "year" in cols:
        sub = sub[sub["year"] == int(year)]
    if "node" in cols:
        sub = sub[sub["node"].astype(str) == str(node)]
    if len(sub):
        return float(sub[valcol].iloc[0])
    if "year" in cols:                       # node nicht gelistet -> Jahreswert
        s2 = orig[orig["year"] == int(year)]
        if len(s2):
            return float(s2[valcol].iloc[0])
    return default


# ---------------------------------------------------------------------------
# Oeffentliche API
# ---------------------------------------------------------------------------
def read_capex(dataset, tech, node, year, capacity_type=None):
    """Aktueller Effektivwert des capex in NATIVEN Input-Einheiten (oder NaN)."""
    meta = _capex_meta(dataset, tech, capacity_type)
    if meta is None:
        return float("nan")
    folder, akey, path = meta
    orig = pd.read_csv(path) if os.path.isfile(path) else None
    return _effective(orig, _valcol(orig, akey), _attr_default(folder, akey), node, year)


def restore_leftover_swaps(dataset):
    """Stellt evtl. liegengebliebene Sicherungen wieder her (Crash-Schutz)."""
    base = os.path.join(dataset, "set_technologies")
    for dp, _, files in os.walk(base):
        for f in files:
            if f.endswith(BAK):
                bak = os.path.join(dp, f)
                path = bak[:-len(BAK)]
                if os.path.isfile(path):
                    os.remove(path)
                os.rename(bak, path)


def _build_grid(folder, akey, path, cells, nodes, ref_years):
    """Volle node x year-CSV; `cells` = {(node, year) -> value} ueberschreibt Zielzellen."""
    orig = pd.read_csv(path) if os.path.isfile(path) else None
    valcol = _valcol(orig, akey)
    default = _attr_default(folder, akey)
    years = (sorted(int(y) for y in orig["year"].unique())
             if (orig is not None and "year" in orig.columns) else list(ref_years))
    years = sorted(set(years) | {y for (_, y) in cells})
    node_list = sorted(set(map(str, nodes)) | {n for (n, _) in cells})
    rows = []
    for n in node_list:
        for y in years:
            v = cells.get((n, y))
            rows.append({"node": n, "year": y,
                         valcol: (v if v is not None else _effective(orig, valcol, default, n, y))})
    return pd.DataFrame(rows)


@contextmanager
def capex_file_override(dataset, overrides, restore_leftover=True):
    """Kontextmanager: setzt die capex-CSVs fuer `overrides`, danach Wiederherstellung.

    overrides: Liste von {"tech", "node", "year", "value"[, "capacity_type"]}.
    Mehrere Overrides auf dieselbe CSV werden gebuendelt. Leere Liste = No-op.
    """
    if restore_leftover:
        restore_leftover_swaps(dataset)
    overrides = list(overrides or [])
    if not overrides:
        yield
        return

    nodes = _nodes(dataset)
    ref_years = _reference_years(dataset)
    # nach Ziel-CSV gruppieren
    groups = {}  # path -> [folder, akey, {(node, year): value}]
    for ov in overrides:
        meta = _capex_meta(dataset, ov["tech"], ov.get("capacity_type"))
        if meta is None:
            raise RuntimeError(f"capex_file_override: Ordner fuer '{ov['tech']}' nicht gefunden")
        folder, akey, path = meta
        g = groups.setdefault(path, [folder, akey, {}])
        g[2][(str(ov["node"]), int(ov["year"]))] = float(ov["value"])

    swapped = []  # (path, bak)
    try:
        for path, (folder, akey, cells) in groups.items():
            bak = path + BAK
            new_df = _build_grid(folder, akey, path, cells, nodes, ref_years)
            if os.path.isfile(bak):
                os.remove(bak)
            if os.path.isfile(path):
                os.rename(path, bak)          # Original byte-genau sichern
            new_df.to_csv(path, index=False)
            swapped.append((path, bak))
        yield
    finally:
        for path, bak in swapped:
            if os.path.isfile(path):
                os.remove(path)
            if os.path.isfile(bak):
                os.rename(bak, path)
