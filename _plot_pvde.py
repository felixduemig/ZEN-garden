"""Diagram: incremental PV (DE, 2025) build-out vs CAPEX reduction, with the RC
tipping point marked. Reads the sweep CSV, writes to the thesis Graphs folder."""
import glob, os
import pandas as pd, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"font.family": "serif",
                     "font.serif": ["Times New Roman", "STIXGeneral", "DejaVu Serif"],
                     "mathtext.fontset": "cm", "axes.edgecolor": "#6F6F6F",
                     "font.size": 11, "xtick.labelsize": 10.5, "ytick.labelsize": 10.5})
ETH_GREEN, ETH_RED, ETH_DARK, ETH_GREY = "#627313", "#B7352D", "#1A1A1A", "#6F6F6F"
RC = 85.9  # PV DE 2025 operational RC [EUR/kW]; 17.5% of the 490 base CAPEX

parts = [pd.read_csv(f)[["reduction", "pv_de_build"]]
         for f in (glob.glob("outputs_*_sweep_pvde/sweep_pvde.csv")
                   + glob.glob("outputs_*_sweep_pvde_deep/sweep_deep.csv"))]
df = pd.concat(parts).drop_duplicates("reduction").sort_values("reduction")
EXISTING, CAP = 30.0, 250.0   # PV DE: 30 GW pre-existing, hard capacity_limit 250 GW
df["total"] = df.pv_de_build + EXISTING   # total installed = existing + new build
THESIS = "C:/Users/felix/Documents/GitHub/ZEN-garden/ST_Final_Report_Felix_Duemig/thesis/Graphs"

fig, ax = plt.subplots(figsize=(6.4, 4.0))
# shade the region below the RC where no NEW capacity is built (only the existing PV)
ax.axvspan(df.reduction.min() - 3, RC, color="#EDE7D3", alpha=0.6, zorder=0)
ax.text(df.reduction.min() + 2, 150, "no new build",
        color=ETH_GREY, fontsize=10, style="italic", rotation=90, va="center", ha="center")
# pre-installed PV: dashed line + light-grey band below it (this is NOT new build)
ax.axhspan(0, EXISTING, color="#E4E4E4", alpha=0.7, zorder=0)
ax.axhline(EXISTING, color=ETH_GREY, ls="--", lw=1.2, zorder=1)
ax.text(df.reduction.max() + 5, EXISTING, "pre-installed PV (30 GW)",
        color=ETH_GREY, fontsize=9.5, ha="right", va="bottom")
# hard capacity limit
ax.axhline(CAP, color=ETH_GREY, ls=":", lw=1.3, zorder=1)
# build-out curve (total installed capacity)
ax.plot(df.reduction, df.total, "-o", color=ETH_GREEN, mfc="white",
        mec=ETH_GREEN, lw=1.9, ms=4.5, zorder=3)
# saturation = hard cap reached; surplus exported
ax.annotate("reaches 250 GW hard cap\n(30 existing + 220 new);\nsurplus exported to AT/FR",
            xy=(485, 250), xytext=(488, 197), color=ETH_DARK, fontsize=10,
            ha="right", va="top",
            arrowprops=dict(arrowstyle="->", color=ETH_GREY, lw=1.0), zorder=4)
# RC tipping-point line
ax.axvline(RC, color=ETH_RED, ls="--", lw=1.6, zorder=2)
ax.text(RC + 5, 232, f"RC = {RC:.0f} EUR/kW\n(17.5 % of CAPEX)\ntipping point",
        color=ETH_RED, fontsize=10, va="top", ha="left")

ax.set_xlabel("CAPEX reduction applied to PV (DE, 2025)  [EUR/kW]", fontsize=11.5)
ax.set_ylabel("Total installed PV capacity, DE 2025  [GW]", fontsize=11.5)
ax.set_ylim(0, 262)
ax.set_xlim(df.reduction.min() - 3, df.reduction.max() + 8)
ax.grid(True, color="#D9D9D9", lw=0.6, zorder=1)
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
fig.tight_layout()
out = os.path.join(THESIS, "pv_de_incremental_buildout.png")
fig.savefig(out, dpi=180, bbox_inches="tight")
print("saved", out)
