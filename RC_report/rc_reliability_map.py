"""Reliability map for the Crystal Ball conversion RCs — ETH-styled, same look as the
RC heatmap, but the COLOUR encodes how trustworthy the RC is (not the RC value).

Signal = clean-vs-perturbed operational swing |ratio_C - ratio_B| (percentage points):
the degeneracy fingerprint (low swing = unique dual = reliable; high swing = degenerate
scarcity vertex = RC is an optimistic lower bound). Validated separation: PV 0.4pp,
wind 0.09pp (PASS) vs nuclear 9.4pp, electrolysis 5.0pp (FAIL).

Rows = conversion techs sorted by reliability (most reliable on top), cols = 28 nodes.
Cell states: buildable_rc+reliable -> green(reliable)..red(degenerate) by swing;
built -> white; at_limit/not_buildable -> black; breakeven/other -> grey.
The 17 ground-truth ±1% cases are overlaid (o = PASS, x = FAIL) for calibration.

CAVEAT (drawn in the caption): the swing catches *scarcity-vertex degeneracy* but NOT
*constraint-pinning* (coal_to_cement_fuel@SK has a near-zero swing yet FAILS because its
build is fixed by the fuel-for-cement demand). So green = "no degeneracy detected",
not a guarantee.

    python RC_report/rc_reliability_map.py
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize, LinearSegmentedColormap
from matplotlib.patches import Rectangle, Patch

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNC = os.path.join(BASE, "outputs_CB_overnight", "runC", "Crystal_Ball",
                    "capacity_addition_analysis_conversion.csv")
RUNB = os.path.join(BASE, "outputs_CB_overnight", "runB", "Crystal_Ball",
                    "capacity_addition_analysis_conversion.csv")
OUT = os.path.join(BASE, "RC_report", "rc_reliability_map.png")
VMAX = 4.0   # pp; >=VMAX saturates to dark red

ETH_GREEN, ETH_RED, ETH_GREY, ETH_DARK = "#627313", "#B7352D", "#6F6F6F", "#1A1A1A"
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["CMU Serif", "Latin Modern Roman", "Times New Roman", "DejaVu Serif"],
    "mathtext.fontset": "cm", "text.color": ETH_DARK, "axes.labelcolor": ETH_DARK,
    "axes.edgecolor": ETH_GREY, "xtick.color": ETH_DARK, "ytick.color": ETH_DARK,
    "figure.facecolor": "white", "savefig.facecolor": "white",
})
CMAP = LinearSegmentedColormap.from_list(
    "eth_rel", [(0.0, ETH_GREEN), (0.5, "#EDE7D3"), (1.0, ETH_RED)])
CMAP.set_over("#6F1410")
CMAP.set_bad((0, 0, 0, 0))
CAT_COLOR = {"built": "white", "blocked": "black", "other": "#D9D9D9"}
GRID = "#BFBFBF"

# ground-truth +-1% cases (cb_rc_validation_collected.md)
PASS = {("photovoltaics","CZ"),("photovoltaics","NO"),("photovoltaics","SE"),
        ("wind_onshore","NO"),("wind_onshore","CH"),("wind_offshore","FR"),
        ("wind_offshore","SE"),("run-of-river_hydro","SK"),("run-of-river_hydro","SE"),
        ("reservoir_hydro","CH"),("reservoir_hydro","SE"),("heat_pump_DH","SE"),
        ("methanol_from_hydrogen","BG"),("natural_gas_turbine_CCS","ES"),("nuclear","FR")}
FAIL = {("electrolysis","FI"),("nuclear","ES"),("coal_to_cement_fuel","SK")}


def categorize(case, reliable):
    if case == "buildable_rc" and reliable:
        return "rc"
    if case == "built":
        return "built"
    if case in ("at_limit", "not_buildable"):
        return "blocked"
    return "other"


def main():
    C = pd.read_csv(RUNC)
    B = pd.read_csv(RUNB)
    key = ["set_technologies", "set_location", "set_time_steps_yearly"]
    m = C.merge(B[key + ["ratio_reduction_operational"]], on=key, suffixes=("_C", "_B"))
    m = m[m.set_time_steps_yearly == 0].copy()
    m["swing"] = (m["ratio_reduction_operational_C"] - m["ratio_reduction_operational_B"]).abs() * 100
    rel = m["rc_reliable"].astype(str).str.lower().isin(["true", "1"])
    m["__cat"] = [categorize(c, r) for c, r in zip(m["case"], rel)]
    m.loc[m["__cat"].eq("rc") & m["swing"].isna(), "__cat"] = "other"
    m["__val"] = np.where(m["__cat"] == "rc", m["swing"], np.nan)
    m["__bld"] = np.where(m["__cat"] == "built", m["value"], np.nan)

    cat = m.pivot_table(index="set_technologies", columns="set_location",
                        values="__cat", aggfunc="first")
    val = m.pivot_table(index="set_technologies", columns="set_location",
                        values="__val", aggfunc="first", dropna=False).reindex(
                        index=cat.index, columns=cat.columns)
    bld = m.pivot_table(index="set_technologies", columns="set_location",
                        values="__bld", aggfunc="first", dropna=False).reindex(
                        index=cat.index, columns=cat.columns)
    informative = cat.isin(["rc", "built", "blocked"])
    cat = cat.loc[informative.any(axis=1), informative.any(axis=0)]
    val = val.reindex(index=cat.index, columns=cat.columns)
    bld = bld.reindex(index=cat.index, columns=cat.columns)

    # sort techs by reliability: median swing over their buildable cells (reliable on top);
    # techs with no buildable cell go to the bottom
    med = val.median(axis=1)
    order = med.fillna(np.inf).sort_values(kind="mergesort").index
    cat, val, bld = cat.loc[order], val.loc[order], bld.loc[order]
    nodes = list(cat.columns)
    techs = list(cat.index)
    nr, nc = len(techs), len(nodes)

    fig_w = max(7.0, 0.42 * nc + 4.2)
    fig_h = max(4.0, 0.30 * nr + 1.6)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_facecolor("white")
    norm = Normalize(0.0, VMAX, clip=False)
    data = val.values.astype(float)
    ax.imshow(np.ma.masked_invalid(data), cmap=CMAP, norm=norm, aspect="auto", zorder=2)
    cats = cat.values
    for i in range(nr):
        for j in range(nc):
            if np.isfinite(data[i, j]):
                continue
            ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1,
                         facecolor=CAT_COLOR.get(cats[i, j], CAT_COLOR["other"]),
                         edgecolor="none", zorder=1.5))
    # ground-truth markers
    for i, t in enumerate(techs):
        for j, n in enumerate(nodes):
            if (t, n) in PASS:
                ax.scatter(j, i, marker="o", s=26, facecolors="none",
                           edgecolors=ETH_DARK, linewidths=1.3, zorder=5)
            elif (t, n) in FAIL:
                ax.scatter(j, i, marker="x", s=30, color=ETH_DARK, linewidths=1.6, zorder=5)

    ax.set_xticks(range(nc)); ax.set_xticklabels(nodes, rotation=0, fontsize=7.5)
    ax.set_yticks(range(nr)); ax.set_yticklabels(techs, fontsize=7.0)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Node", fontsize=10)
    ax.set_xlim(-0.5, nc - 0.5); ax.set_ylim(nr - 0.5, -0.5)
    ax.set_xticks(np.arange(-0.5, nc, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, nr, 1), minor=True)
    ax.grid(which="minor", color=GRID, linewidth=0.5, zorder=3)
    ax.tick_params(which="minor", length=0)
    for sp in ax.spines.values():
        sp.set_edgecolor(ETH_GREY); sp.set_linewidth(0.8)

    sm = plt.cm.ScalarMappable(cmap=CMAP, norm=norm)
    cbar = fig.colorbar(sm, ax=ax, fraction=0.022, pad=0.012, extend="max")
    cbar.set_label("Clean–perturbed swing  [pp]   (low = reliable RC)", fontsize=9)
    cbar.ax.tick_params(labelsize=8)
    legend = [Patch(facecolor=ETH_GREEN, label="reliable (unique dual)"),
              Patch(facecolor=ETH_RED, label="degenerate (RC = lower bound)"),
              Patch(facecolor="white", edgecolor=ETH_GREY, label="built"),
              Patch(facecolor="black", label="at limit / not buildable"),
              Patch(facecolor=CAT_COLOR["other"], edgecolor=ETH_GREY, label="other / n.a."),
              plt.Line2D([], [], marker="o", markerfacecolor="none", markeredgecolor=ETH_DARK,
                         linestyle="none", label="validated PASS"),
              plt.Line2D([], [], marker="x", color=ETH_DARK, linestyle="none",
                         label="validated FAIL")]
    fig.legend(handles=legend, loc="lower center", bbox_to_anchor=(0.5, -0.015),
               ncol=4, fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(OUT, dpi=170, bbox_inches="tight")
    plt.close(fig)
    nrel = int((data < 1).sum()); ndeg = int((data >= VMAX).sum())
    print(f"map -> {OUT}  ({nr} techs x {nc} nodes; "
          f"{int(np.isfinite(data).sum())} RC cells, {nrel} clearly-reliable, {ndeg} clearly-degenerate)")


if __name__ == "__main__":
    main()
