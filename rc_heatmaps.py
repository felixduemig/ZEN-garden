"""RC-Heatmaps aus den klassifizierten Capacity-Addition-Analysen.

Eigenstaendiges Skript — manuell mit einem Output-Ordner aufrufen:

    python rc_heatmaps.py <OUTPUT_DIR> [Optionen]

Sucht rekursiv nach Szenario-Ordnern, die
    capacity_addition_analysis_{conversion,transport,storage}.csv
enthalten (erzeugt von postprocess.save_capacity_addition_classified bzw.
rc_classify_existing.py), und baut je (Jahr, Technologieart) eine Heatmap der
**prozentual noetigen CAPEX-Senkung zum Zubau**.

Vier visuelle Zustaende pro Zelle:
  * echte RC (case = buildable_rc, zuverlaessig) -> Heatmap gruen (wenig) .. rot (viel)
  * korrekt zugebaut (case = built, rc ~ 0)       -> WEISS  (fliesst NICHT in die Skala)
  * nicht baubar / am Limit (at_limit/not_buildable) -> SCHWARZ
  * unzuverlaessig / sonstiges (breakeven, blocked_profitable, Placeholder-Storage) -> GRAU

Achsen: Technologien von oben nach unten, Knoten von links nach rechts.

Ausgabe-Ordnerstruktur (neben den CSVs):
    <scenario>/heatmaps/<year>/<techtype>/
        rc_heatmap_<techtype>_<year>.png             visualisierte Heatmap
        rc_heatmap_<techtype>_<year>.csv             Matrix (tech × node) der RC in %
        rc_heatmap_<techtype>_<year>_categories.csv  Matrix der Faelle (built/blocked/…)

Optionen:
    --vmax 100              oberes Ende der Farbskala in % (Default 100; rot ab hier)
    --storage-metric M      Storage-Kennzahl: proportional (Default) | energy | power
    --no-annot             keine Zahlen in die RC-Zellen schreiben
"""
import os
import json
import argparse
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.patches import Rectangle, Patch

TECH_TYPES = ("conversion", "transport", "storage")
TECH_COL = "set_technologies"
NODE_COL = "set_location"
YEAR_IDX_COL = "set_time_steps_yearly"

# Kennzahl-Spalte je Technologieart (Anteil; wird *100 zu Prozent)
METRIC = {
    "conversion": "ratio_reduction",
    "transport": "ratio_reduction",
    "storage": {  # waehlbar via --storage-metric
        "proportional": "ratio_reduction_proportional",
        "energy": "ratio_energy_reduction",
        "power": "ratio_power_reduction",
    },
}

# kategorische Zellfarben (echte RC werden ueber die Colormap gefaerbt)
CAT_COLOR = {"built": "white", "blocked": "black", "other": "0.7"}
GRID_COLOR = "0.75"


def categorize(case, reliable):
    """case + rc_reliable -> visueller Zustand."""
    if case == "buildable_rc" and reliable:
        return "rc"          # Heatmap-Farbe
    if case == "built":
        return "built"       # weiss
    if case in ("at_limit", "not_buildable"):
        return "blocked"     # schwarz
    return "other"           # grau


def find_scenario_dirs(root):
    """Alle Ordner unter root, die mind. eine klassifizierte CSV enthalten."""
    hits = []
    for dirpath, _, files in os.walk(root):
        if any(f"capacity_addition_analysis_{t}.csv" in files for t in TECH_TYPES):
            hits.append(dirpath)
    return sorted(hits)


def year_map(scenario_dir):
    """(reference_year, interval) aus system.json; Fallback (0, 1)."""
    try:
        s = json.load(open(os.path.join(scenario_dir, "system.json")))
        return int(s.get("reference_year", 0)), int(s.get("interval_between_years", 1))
    except Exception:
        return 0, 1


def build_matrices(df, metric_col, ref_year, interval):
    """{year -> (value_mat[%], cat_mat)} — value nur fuer echte RC, sonst NaN.

    Zeilen/Spalten ohne jede informative Zelle (nur 'other'/leer) werden entfernt;
    built/blocked-Zeilen bleiben erhalten (sollen ja farblich erscheinen).
    """
    if metric_col not in df.columns or "case" not in df.columns:
        return {}
    d = df.copy()
    rel = d["rc_reliable"].astype(str).str.lower().isin(["true", "1"]) \
        if "rc_reliable" in d.columns else False
    d["__cat"] = [categorize(c, r) for c, r in zip(d["case"], rel)]
    d["__val"] = np.where(d["__cat"] == "rc", d[metric_col] * 100.0, np.nan)
    d["__year"] = (ref_year + d[YEAR_IDX_COL].astype(int) * interval
                   if YEAR_IDX_COL in d.columns else ref_year)

    out = {}
    for yr, g in d.groupby("__year"):
        # Kategorie-Matrix als VOLLES Gitter (jede Zelle hat eine Kategorie);
        # Werte-Matrix mit dropna=False, damit built-/blocked-Techs (Wert = NaN)
        # nicht verloren gehen, und an das Gitter angeglichen.
        cat = g.pivot_table(index=TECH_COL, columns=NODE_COL, values="__cat",
                            aggfunc="first")
        val = g.pivot_table(index=TECH_COL, columns=NODE_COL, values="__val",
                            aggfunc="first", dropna=False)
        cat = cat.sort_index(axis=0).sort_index(axis=1)
        val = val.reindex(index=cat.index, columns=cat.columns)
        # informativ = echte RC ODER built ODER blocked (reine 'other'-Zeilen raus)
        informative = cat.isin(["rc", "built", "blocked"])
        keep_r, keep_c = informative.any(axis=1), informative.any(axis=0)
        val, cat = val.loc[keep_r, keep_c], cat.loc[keep_r, keep_c]
        if cat.empty:
            continue
        out[int(yr)] = (val, cat)
    return out


def render_heatmap(val, cat, title, png_path, vmax, annotate):
    """Heatmap: echte RC gruen..rot, built=weiss, blocked=schwarz, other=grau."""
    data = val.values.astype(float)
    cats = cat.values
    n_rows, n_cols = data.shape
    fig_w = max(6.0, 0.55 * n_cols + 4.0)
    fig_h = max(3.5, 0.42 * n_rows + 2.2)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_facecolor("white")

    cmap = plt.cm.RdYlGn_r.copy()
    cmap.set_over("#5c0000")     # > vmax -> dunkelrot
    cmap.set_bad((0, 0, 0, 0))   # NaN transparent (kategorische Overlays darunter)
    norm = Normalize(vmin=0.0, vmax=vmax, clip=False)
    im = ax.imshow(np.ma.masked_invalid(data), cmap=cmap, norm=norm, aspect="auto",
                   zorder=2)

    # kategorische Zellen als Rechtecke (built/blocked/other)
    for i in range(n_rows):
        for j in range(n_cols):
            if np.isfinite(data[i, j]):
                continue
            color = CAT_COLOR.get(cats[i, j], CAT_COLOR["other"])
            ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, facecolor=color,
                                   edgecolor="none", zorder=1.5))

    ax.set_xticks(range(n_cols)); ax.set_xticklabels(val.columns, rotation=90, fontsize=7)
    ax.set_yticks(range(n_rows)); ax.set_yticklabels(val.index, fontsize=7)
    ax.set_xlabel("Knoten"); ax.set_ylabel("Technologie")
    ax.set_xlim(-0.5, n_cols - 0.5); ax.set_ylim(n_rows - 0.5, -0.5)
    ax.set_xticks(np.arange(-0.5, n_cols, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, n_rows, 1), minor=True)
    ax.grid(which="minor", color=GRID_COLOR, linewidth=0.6, zorder=3)
    ax.tick_params(which="minor", length=0)

    if annotate:
        fs = 7 if max(n_rows, n_cols) <= 20 else (6 if max(n_rows, n_cols) <= 40 else 5)
        for i in range(n_rows):
            for j in range(n_cols):
                v = data[i, j]
                if not np.isfinite(v):
                    continue
                rgba = cmap(norm(min(v, vmax)))
                lum = 0.299 * rgba[0] + 0.587 * rgba[1] + 0.114 * rgba[2]
                txt = f"{v:.0f}" if v >= 10 else f"{v:.1f}"
                ax.text(j, i, txt, ha="center", va="center", fontsize=fs, zorder=4,
                        color="white" if lum < 0.5 else "black")

    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.012, extend="max")
    cbar.set_label("echte RC: noetige CAPEX-Senkung zum Zubau [%]")
    legend = [Patch(facecolor="white", edgecolor="0.5", label="korrekt zugebaut"),
              Patch(facecolor="black", label="nicht baubar / am Limit"),
              Patch(facecolor="0.7", label="RC unzuverlaessig / sonstiges")]
    fig.legend(handles=legend, loc="lower center", bbox_to_anchor=(0.5, -0.02),
               ncol=3, fontsize=8, frameon=False)
    ax.set_title(title, fontsize=11, pad=10)
    fig.tight_layout()
    fig.savefig(png_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def run(root, vmax, storage_metric, annotate):
    scen_dirs = find_scenario_dirs(root)
    if not scen_dirs:
        print(f"[err] keine klassifizierten CSVs unter {root} gefunden.")
        return
    for scen in scen_dirs:
        ref_year, interval = year_map(scen)
        print(f"\nSzenario: {scen}  (reference_year={ref_year}, interval={interval})")
        for tt in TECH_TYPES:
            csv = os.path.join(scen, f"capacity_addition_analysis_{tt}.csv")
            if not os.path.isfile(csv):
                continue
            df = pd.read_csv(csv)
            if tt == "storage":
                metric_col = METRIC["storage"][storage_metric]
                label = f"{tt} ({storage_metric})"
            else:
                metric_col = METRIC[tt]
                label = tt
            mats = build_matrices(df, metric_col, ref_year, interval)
            if not mats:
                print(f"  [{tt:11s}] keine informativen Zellen -> uebersprungen")
                continue
            for yr, (val, cat) in mats.items():
                out_dir = os.path.join(scen, "heatmaps", str(yr), tt)
                os.makedirs(out_dir, exist_ok=True)
                stem = f"rc_heatmap_{tt}_{yr}"
                val.round(4).to_csv(os.path.join(out_dir, stem + ".csv"))
                cat.to_csv(os.path.join(out_dir, stem + "_categories.csv"))
                title = (f"Noetige CAPEX-Senkung zum Zubau [%] — {label} — {yr}\n"
                         f"gruen = nah am Bau, rot = weit weg (Skala 0–{vmax:g} %); "
                         f"weiss = zugebaut, schwarz = nicht baubar")
                render_heatmap(val, cat, title, os.path.join(out_dir, stem + ".png"),
                               vmax, annotate)
                n_rc = int(np.isfinite(val.values).sum())
                print(f"  [{tt:11s}] {yr}: {val.shape[0]} Techs × {val.shape[1]} Knoten, "
                      f"{n_rc} echte-RC-Zellen -> {os.path.relpath(out_dir, scen)}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="RC-Heatmaps der noetigen CAPEX-Senkung.")
    ap.add_argument("output_dir", help="Output-Ordner (wird rekursiv durchsucht).")
    ap.add_argument("--vmax", type=float, default=100.0,
                    help="oberes Ende der Farbskala in %% (Default 100).")
    ap.add_argument("--storage-metric", choices=("proportional", "energy", "power"),
                    default="proportional", help="Storage-Kennzahl (Default proportional).")
    ap.add_argument("--no-annot", action="store_true", help="keine Zahlen in den Zellen.")
    args = ap.parse_args()
    run(args.output_dir, args.vmax, args.storage_metric, not args.no_annot)
