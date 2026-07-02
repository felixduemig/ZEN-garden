"""RC heatmaps from the classified capacity-addition analyses (ETH-styled, thesis-ready).

Standalone script — call with one output folder:

    python rc_heatmaps.py <OUTPUT_DIR> [options]

Recursively finds scenario folders that contain
    capacity_addition_analysis_{conversion,transport,storage}.csv
(written by postprocess.save_capacity_addition_classified / rc_classify_existing.py)
and builds, per (year, technology type), a heatmap of the **relative CAPEX reduction
needed to build** an unbuilt technology.

Information encoded per cell:
  * COLOUR + top number  : relative reduction needed to build [%]  (the *relative* RC)
  * bottom number (…)    : absolute reduced cost [EUR/kW]          (the *absolute* RC)
  * row label            : the technology's own CAPEX [EUR/kW]     (absolute, ~same per node)

Which RC drives colour/numbers:
  * conversion : OPERATIONAL RC  (degeneracy-robust, dispatch-anchored)
  * transport  : lifetime RC     (operational not defined for transport)
  * storage    : bundle RC       (proportional power+energy at fixed duration e2p)

Four visual states per cell:
  * real RC (case = buildable_rc, reliable) -> colour scale green(near)..red(far)
  * correctly built (case = built, RC ~ 0)  -> WHITE (excluded from the scale)
  * at limit / not buildable                -> BLACK
  * unreliable / other (breakeven, …)       -> GREY

Output (next to the CSVs):
    <scenario>/heatmaps/<year>/<techtype>/
        rc_heatmap_<techtype>_<year>.png             the heatmap
        rc_heatmap_<techtype>_<year>.csv             matrix (tech x node) of RC in %
        rc_heatmap_<techtype>_<year>_categories.csv  matrix of cases (built/blocked/…)

Options:
    --vmax 150              upper end of the colour scale in % (default 150; covers ratio>1)
    --storage-metric M      storage metric: proportional (default) | energy | power
    --no-annot             do not write numbers into the cells

No title/subtitle is drawn on the figure (it would force the PNG too wide); describe
the encoding in the LaTeX figure caption instead.
"""
import os
import json
import argparse
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize, LinearSegmentedColormap
from matplotlib.patches import Rectangle, Patch

TECH_TYPES = ("conversion", "transport", "storage")
TECH_COL = "set_technologies"
NODE_COL = "set_location"
YEAR_IDX_COL = "set_time_steps_yearly"

# ---------------------------------------------------------------------------
# Styling — serif to match the thesis (Computer Modern; Times New Roman as the
# closest installed substitute). ETH-tone colour ramp, no blue.
# ---------------------------------------------------------------------------
ETH_GREEN  = "#627313"
ETH_BRONZE = "#8E6713"
ETH_RED    = "#B7352D"
ETH_GREY   = "#6F6F6F"
ETH_DARK   = "#1A1A1A"
CAPEX_COLOR = "#4D4D4D"   # CAPEX side label (absolute) — neutral grey, distinct from %

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["CMU Serif", "Latin Modern Roman", "Times New Roman",
                   "STIXGeneral", "DejaVu Serif"],
    "mathtext.fontset": "cm",
    "text.color": ETH_DARK,
    "axes.labelcolor": ETH_DARK,
    "axes.edgecolor": ETH_GREY,
    "xtick.color": ETH_DARK,
    "ytick.color": ETH_DARK,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
})

# green (near build) -> light sand (mid) -> red (far), ETH tones
ETH_RC_CMAP = LinearSegmentedColormap.from_list(
    "eth_rc", [(0.00, ETH_GREEN), (0.50, "#EDE7D3"), (1.00, ETH_RED)])
ETH_RC_CMAP.set_over("#6F1410")        # > vmax -> dark red
ETH_RC_CMAP.set_bad((0, 0, 0, 0))      # NaN transparent (categorical overlay below)

# categorical cell colours (real RC are coloured via the colormap)
CAT_COLOR = {"built": "white", "blocked": "black", "other": "#D9D9D9"}
GRID_COLOR = "#BFBFBF"

# per-(techtype) source columns: relative metric (colour), absolute RC, own CAPEX, label
SPEC = {
    "conversion": dict(rel="ratio_reduction_operational",
                       abs="rc_capex_equivalent_operational_input_units",
                       capex="capex_specific_input_units", rc_label="operational RC"),
    "transport":  dict(rel="ratio_reduction",
                       abs="rc_capex_equivalent_input_units",
                       capex="capex_specific_input_units", rc_label="lifetime RC"),
    "storage": {  # chosen via --storage-metric
        "proportional": dict(rel="ratio_reduction_proportional", abs=None,  # = rel*C_bundle
                             capex="C_bundle", rc_label="bundle RC (proportional)"),
        "energy":       dict(rel="ratio_energy_reduction", abs="RC_energy",
                             capex="capex_energy", rc_label="energy RC"),
        "power":        dict(rel="ratio_power_reduction", abs="RC_power",
                             capex="capex_power", rc_label="power RC"),
    },
}


def categorize(case, reliable):
    """case + rc_reliable -> visual state."""
    if case == "buildable_rc" and reliable:
        return "rc"          # heatmap colour
    if case == "built":
        return "built"       # white
    if case in ("at_limit", "not_buildable"):
        return "blocked"     # black
    return "other"           # grey


def find_scenario_dirs(root):
    """All folders under root that contain at least one classified CSV."""
    hits = []
    for dirpath, _, files in os.walk(root):
        if any(f"capacity_addition_analysis_{t}.csv" in files for t in TECH_TYPES):
            hits.append(dirpath)
    return sorted(hits)


def year_map(scenario_dir):
    """(reference_year, interval) from system.json; fallback (0, 1)."""
    try:
        s = json.load(open(os.path.join(scenario_dir, "system.json")))
        return int(s.get("reference_year", 0)), int(s.get("interval_between_years", 1))
    except Exception:
        return 0, 1


def build_matrices(df, ref_year, interval):
    """{year -> (val[%], cat, absmat[EUR/kW], capex_ser[EUR/kW])}.

    Expects df to carry helper columns __rel, __abs, __capex (set in run()).
    Value/abs only for real RC cells, else NaN. Rows/cols with no informative
    cell ('rc'/'built'/'blocked') are dropped; built/blocked rows are kept.
    """
    if "__rel" not in df.columns or "case" not in df.columns:
        return {}
    d = df.copy()
    rel = d["rc_reliable"].astype(str).str.lower().isin(["true", "1"]) \
        if "rc_reliable" in d.columns else False
    d["__cat"] = [categorize(c, r) for c, r in zip(d["case"], rel)]
    # an 'rc' cell without a relative value can't be coloured -> demote to 'other'
    no_val = d["__cat"].eq("rc") & d["__rel"].isna()
    d.loc[no_val, "__cat"] = "other"
    d["__val"] = np.where(d["__cat"] == "rc", d["__rel"] * 100.0, np.nan)
    d["__absv"] = np.where(d["__cat"] == "rc", d["__abs"], np.nan)
    # installed capacity for BUILT cells (shown as a visual aid in the white cells)
    bvsrc = d["__buildval"] if "__buildval" in d.columns else np.nan
    d["__bld"] = np.where(d["__cat"] == "built", bvsrc, np.nan)
    d["__year"] = (ref_year + d[YEAR_IDX_COL].astype(int) * interval
                   if YEAR_IDX_COL in d.columns else ref_year)

    out = {}
    for yr, g in d.groupby("__year"):
        cat = g.pivot_table(index=TECH_COL, columns=NODE_COL, values="__cat",
                            aggfunc="first")
        val = g.pivot_table(index=TECH_COL, columns=NODE_COL, values="__val",
                            aggfunc="first", dropna=False)
        absm = g.pivot_table(index=TECH_COL, columns=NODE_COL, values="__absv",
                             aggfunc="first", dropna=False)
        capx = g.pivot_table(index=TECH_COL, columns=NODE_COL, values="__capex",
                             aggfunc="first", dropna=False)
        bld = g.pivot_table(index=TECH_COL, columns=NODE_COL, values="__bld",
                            aggfunc="first", dropna=False)
        cat = cat.sort_index(axis=0).sort_index(axis=1)
        val = val.reindex(index=cat.index, columns=cat.columns)
        absm = absm.reindex(index=cat.index, columns=cat.columns)
        capx = capx.reindex(index=cat.index, columns=cat.columns)
        bld = bld.reindex(index=cat.index, columns=cat.columns)
        informative = cat.isin(["rc", "built", "blocked"])
        keep_r, keep_c = informative.any(axis=1), informative.any(axis=0)
        val, cat = val.loc[keep_r, keep_c], cat.loc[keep_r, keep_c]
        absm, capx = absm.loc[keep_r, keep_c], capx.loc[keep_r, keep_c]
        bld = bld.loc[keep_r, keep_c]
        if cat.empty:
            continue
        out[int(yr)] = (val, cat, absm, capx, bld)
    return out


def _capex_label(row_vals):
    """Per-technology CAPEX string from the row's CAPEX cells (constant or a range)."""
    v = pd.Series(row_vals).dropna()
    if v.empty:
        return ""
    lo, hi = float(v.min()), float(v.max())
    if hi - lo <= max(1.0, 0.01 * hi):       # ~constant across nodes/edges
        return f"{lo:,.0f}".replace(",", " ")
    return f"{lo:,.0f}–{hi:,.0f}".replace(",", " ")  # e.g. 287-377 (transport)


def render_heatmap(val, cat, absm, capx, bld, png_path, vmax, annotate, highlight=None,
                   square=False, legend_y=-0.02):
    """Heatmap: real RC green..red, built=white (installed GW annotated), blocked=black,
    other=grey. No title (the figure caption carries the description; see run()).

    square   : force roughly square cells (aspect='equal'), for few-row maps (storage)
               that would otherwise look vertically stretched.
    legend_y : figure-fraction y of the bottom legend (more negative = larger gap to the
               'Node / edge' axis label).
    """
    data = val.values.astype(float)
    absv = absm.values.astype(float)
    bldv = bld.values.astype(float)
    cats = cat.values
    n_rows, n_cols = data.shape
    fig_w = max(5.0, 0.60 * n_cols + 2.6)
    if square:
        # size the canvas so one row of square cells fills it, leaving room for the
        # x-label and the bottom legend (cells stay ~square via aspect='equal' below)
        fig_h = 0.60 * n_rows + 1.7
    else:
        # keep single-/few-row maps (e.g. storage) from looking vertically stretched
        fig_h = max(1.9, 0.46 * n_rows + 1.35)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_facecolor("white")

    norm = Normalize(vmin=0.0, vmax=vmax, clip=False)
    im = ax.imshow(np.ma.masked_invalid(data), cmap=ETH_RC_CMAP, norm=norm,
                   aspect=("equal" if square else "auto"), zorder=2)

    # categorical cells (built / blocked / other) as solid rectangles
    for i in range(n_rows):
        for j in range(n_cols):
            if np.isfinite(data[i, j]):
                continue
            color = CAT_COLOR.get(cats[i, j], CAT_COLOR["other"])
            ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, facecolor=color,
                                   edgecolor="none", zorder=1.5))

    # y labels: technology name (line 1) + its own CAPEX (line 2, ETH blue), stacked
    ylabels = list(val.index)
    ax.set_xticks(range(n_cols)); ax.set_xticklabels(val.columns, rotation=0, fontsize=9)
    ax.set_yticks(range(n_rows)); ax.set_yticklabels([])
    for i, lab in enumerate(ylabels):
        ax.annotate(lab, xy=(0, i), xycoords=("axes fraction", "data"),
                    xytext=(-8, 5), textcoords="offset points", ha="right", va="bottom",
                    fontsize=9, color=ETH_DARK, annotation_clip=False, zorder=5)
        cstr = _capex_label(capx.iloc[i].values)
        if cstr:
            ax.annotate(f"{cstr} €/kW", xy=(0, i), xycoords=("axes fraction", "data"),
                        xytext=(-8, -6), textcoords="offset points", ha="right", va="top",
                        fontsize=6.8, color=CAPEX_COLOR, style="italic",
                        annotation_clip=False, zorder=5)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Node / edge", fontsize=10)
    ax.set_xlim(-0.5, n_cols - 0.5); ax.set_ylim(n_rows - 0.5, -0.5)
    ax.set_xticks(np.arange(-0.5, n_cols, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, n_rows, 1), minor=True)
    ax.grid(which="minor", color=GRID_COLOR, linewidth=0.7, zorder=3)
    ax.tick_params(which="minor", length=0)
    for sp in ax.spines.values():
        sp.set_edgecolor(ETH_GREY); sp.set_linewidth(0.8)

    if annotate:
        big = max(n_rows, n_cols)
        fs = 7.5 if big <= 14 else (6.5 if big <= 24 else 5.5)
        for i in range(n_rows):
            for j in range(n_cols):
                v = data[i, j]
                if not np.isfinite(v):
                    # built (white) cell -> annotate the installed capacity [GW]
                    if cats[i, j] == "built":
                        bv = bldv[i, j]
                        if np.isfinite(bv) and bv > 1e-6:
                            ax.text(j, i, f"{bv:.1f}", ha="center", va="center",
                                    fontsize=fs - 1.5, color=ETH_DARK, zorder=4)
                    continue
                rgba = ETH_RC_CMAP(norm(min(v, vmax)))
                lum = 0.299 * rgba[0] + 0.587 * rgba[1] + 0.114 * rgba[2]
                col = "white" if lum < 0.5 else ETH_DARK
                pct = f"{v:.1f}%"
                a = absv[i, j]
                astr = "" if not np.isfinite(a) else f"({a:,.1f})".replace(",", " ")
                ax.text(j, i - 0.13, pct, ha="center", va="center",
                        fontsize=fs, fontweight="bold", color=col, zorder=4)
                if astr:
                    ax.text(j, i + 0.22, astr, ha="center", va="center",
                            fontsize=fs - 1.2, color=col, zorder=4)

    # optional: outline one (technology, node) cell that was deliberately changed
    if highlight is not None:
        htech, hnode = highlight
        if htech in list(val.index) and hnode in list(val.columns):
            hi = list(val.index).index(htech)
            hj = list(val.columns).index(hnode)
            ax.add_patch(Rectangle((hj - 0.5, hi - 0.5), 1, 1, fill=False,
                                   edgecolor=ETH_DARK, linewidth=3.0, linestyle=(0, (3, 2)),
                                   zorder=6))

    cbar = fig.colorbar(im, ax=ax, fraction=0.026, pad=0.014, extend="max")
    cbar.set_label("Relative CAPEX reduction needed to build  [%]\n"
                   "bracket: absolute reduced cost [EUR/kW]", fontsize=9)
    cbar.outline.set_edgecolor(ETH_GREY); cbar.outline.set_linewidth(0.6)
    cbar.ax.tick_params(labelsize=8)

    legend = [Patch(facecolor="white", edgecolor=ETH_GREY, label="built (number = installed GW)"),
              Patch(facecolor="black", label="at limit / not buildable"),
              Patch(facecolor=CAT_COLOR["other"], edgecolor=ETH_GREY,
                    label="RC unreliable / n.a.")]
    fig.legend(handles=legend, loc="lower center", bbox_to_anchor=(0.5, legend_y),
               ncol=3, fontsize=8.5, frameon=False)
    fig.tight_layout()
    fig.savefig(png_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def run(root, vmax, storage_metric, annotate, highlight=None):
    scen_dirs = find_scenario_dirs(root)
    if not scen_dirs:
        print(f"[err] no classified CSVs found under {root}.")
        return
    for scen in scen_dirs:
        ref_year, interval = year_map(scen)
        print(f"\nScenario: {scen}  (reference_year={ref_year}, interval={interval})")
        for tt in TECH_TYPES:
            csv = os.path.join(scen, f"capacity_addition_analysis_{tt}.csv")
            if not os.path.isfile(csv):
                continue
            df = pd.read_csv(csv)
            spec = SPEC["storage"][storage_metric] if tt == "storage" else SPEC[tt]
            label = f"{tt} ({storage_metric})" if tt == "storage" else tt

            if spec["rel"] not in df.columns:
                print(f"  [{tt:11s}] missing column {spec['rel']} -> skipped")
                continue
            df["__rel"] = pd.to_numeric(df[spec["rel"]], errors="coerce")
            if spec["abs"] is None:        # storage proportional: abs = fraction * bundle CAPEX
                df["__abs"] = df["__rel"] * pd.to_numeric(df["C_bundle"], errors="coerce")
            else:
                df["__abs"] = pd.to_numeric(df[spec["abs"]], errors="coerce")
            df["__capex"] = pd.to_numeric(df[spec["capex"]], errors="coerce")
            # installed capacity for built cells (value_power for storage, value otherwise)
            bcol = "value_power" if tt == "storage" else "value"
            df["__buildval"] = pd.to_numeric(df.get(bcol, np.nan), errors="coerce")

            mats = build_matrices(df, ref_year, interval)
            if not mats:
                print(f"  [{tt:11s}] no informative cells -> skipped")
                continue
            for yr, (val, cat, absm, capx, bld) in mats.items():
                out_dir = os.path.join(scen, "heatmaps", str(yr), tt)
                os.makedirs(out_dir, exist_ok=True)
                stem = f"rc_heatmap_{tt}_{yr}"
                val.round(4).to_csv(os.path.join(out_dir, stem + ".csv"))
                cat.to_csv(os.path.join(out_dir, stem + "_categories.csv"))
                render_heatmap(val, cat, absm, capx, bld,
                               os.path.join(out_dir, stem + ".png"), vmax, annotate,
                               highlight=highlight if tt == "conversion" else None,
                               square=(tt == "storage"),
                               legend_y=(-0.16 if tt == "storage" else -0.02))
                n_rc = int(np.isfinite(val.values).sum())
                print(f"  [{tt:11s}] {yr}: {val.shape[0]} techs x {val.shape[1]} nodes, "
                      f"{n_rc} real-RC cells -> {os.path.relpath(out_dir, scen)}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="ETH-styled RC heatmaps (relative CAPEX reduction to build).")
    ap.add_argument("output_dir", help="output folder (searched recursively).")
    ap.add_argument("--vmax", type=float, default=150.0,
                    help="upper end of the colour scale in %% (default 150; covers ratio>1).")
    ap.add_argument("--storage-metric", choices=("proportional", "energy", "power"),
                    default="proportional", help="storage metric (default proportional).")
    ap.add_argument("--no-annot", action="store_true", help="no numbers in the cells.")
    args = ap.parse_args()
    run(args.output_dir, args.vmax, args.storage_metric, not args.no_annot)
