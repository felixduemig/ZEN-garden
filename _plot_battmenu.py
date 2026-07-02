"""Diagram: battery distance-to-build vs duration (e2p menu 2/4/8 h), one line per node.
Shows the longer-duration option is closest to build and the RCs stay clean."""
import os
import pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"font.family": "serif",
                     "font.serif": ["Times New Roman", "STIXGeneral", "DejaVu Serif"],
                     "mathtext.fontset": "cm", "axes.edgecolor": "#6F6F6F"})
COLORS = {"IT": "#627313", "FR": "#8E6713", "CH": "#B7352D", "AT": "#A30774", "DE": "#2D2D2D"}
DUR = {"battery_2h": 2, "battery_4h": 4, "battery_8h": 8}
THESIS = "C:/Users/felix/Documents/GitHub/ZEN-garden/ST_Final_Report_Felix_Duemig/thesis/Graphs"

st = pd.read_csv("outputs_showcase_battmenu/6_showcase_countries_battmenu/"
                 "capacity_addition_analysis_storage.csv")
st = st[st.set_time_steps_yearly == 0].copy()
st["dur"] = st.set_technologies.map(DUR)
st["pct"] = st.ratio_reduction_proportional * 100

fig, ax = plt.subplots(figsize=(6.0, 4.0))
for node in ["IT", "FR", "CH", "AT", "DE"]:
    d = st[st.set_location == node].sort_values("dur")
    ax.plot(d.dur, d.pct, "-o", color=COLORS[node], mfc="white", mec=COLORS[node],
            lw=1.8, ms=6, label=node)
ax.set_xticks([2, 4, 8])
ax.set_xlabel("Battery duration (energy-to-power ratio)  [h]", fontsize=10)
ax.set_ylabel("Relative CAPEX reduction to build  [%]", fontsize=10)
ax.grid(True, color="#D9D9D9", lw=0.6)
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
ax.legend(title="node", fontsize=8.5, title_fontsize=8.5, frameon=False, ncol=5,
          loc="upper center", bbox_to_anchor=(0.5, 1.10))
fig.tight_layout()
out = os.path.join(THESIS, "battery_duration_rc.png")
fig.savefig(out, dpi=180, bbox_inches="tight")
print("saved", out)
