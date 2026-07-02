import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

C = pd.read_csv("outputs_CB_overnight/runC/Crystal_Ball/capacity_addition_analysis_conversion.csv")
B = pd.read_csv("outputs_CB_overnight/runB/Crystal_Ball/capacity_addition_analysis_conversion.csv")
m = C.merge(B[["set_technologies", "set_location", "ratio_reduction_operational"]],
            on=["set_technologies", "set_location"], suffixes=("", "_B"))
m["swing"] = (m["ratio_reduction_operational_B"] - m["ratio_reduction_operational"]).abs() * 100
sw = {(r.set_technologies, r.set_location): r.swing for _, r in m.iterrows()}

P = [("photovoltaics","CZ"),("photovoltaics","NO"),("photovoltaics","SE"),("wind_onshore","NO"),("wind_onshore","CH"),("wind_offshore","FR"),("wind_offshore","SE"),("run-of-river_hydro","SK"),("run-of-river_hydro","SE"),("reservoir_hydro","CH"),("reservoir_hydro","SE"),("heat_pump_DH","SE"),("methanol_from_hydrogen","BG"),("natural_gas_turbine_CCS","ES"),("nuclear","FR"),("photovoltaics","SK"),("photovoltaics","FI"),("electrolysis","CH"),("reservoir_hydro","NO"),("reservoir_hydro","CZ"),("reservoir_hydro","FR"),("run-of-river_hydro","BG"),("run-of-river_hydro","CH"),("run-of-river_hydro","CZ"),("heat_pump_DH","ES"),("heat_pump_DH","FR"),("heat_pump_DH","BG"),("heat_pump_DH","DE"),("DAC","SE"),("wind_onshore","BG"),("methanol_from_hydrogen","DE"),("electrode_boiler","DE"),("fuel_cell","ES"),("SMR_CCS","DE"),("coal_to_cement_fuel","CZ"),("natural_gas_boiler","DE"),("methanol_from_hydrogen","SK"),("DAC","NO"),("run-of-river_hydro","FR"),("methanol_from_hydrogen","CH"),("heat_pump_DH","FI"),("electrode_boiler","SK")]
F = [("nuclear","ES"),("electrolysis","FI"),("coal_to_cement_fuel","SK"),("natural_gas_turbine","NO"),("natural_gas_turbine_CCS","BG"),("natural_gas_turbine_CCS","SK"),("natural_gas_turbine_CCS","CZ"),("SMR_CCS","ES"),("coal_to_cement_fuel","CH"),("SMR_CCS","CH"),("SMR","SK"),("haber_bosch","SE"),("natural_gas_turbine_CCS","FR"),("nuclear","FI"),("SMR_CCS","SK"),("SMR_CCS","SE"),("methanol_from_hydrogen","CZ"),("natural_gas_turbine","BG"),("natural_gas_turbine_CCS","FI"),("SMR_CCS","FI"),("DAC","FR")]
GREEN, RED, DARK, GREY = "#627313", "#B7352D", "#1A1A1A", "#6F6F6F"  # ETH CI green / red / grey
plt.rcParams.update({"font.family":"serif","font.serif":["CMU Serif","Times New Roman","DejaVu Serif"],
                     "text.color":DARK,"axes.edgecolor":GREY,"savefig.facecolor":"white","figure.facecolor":"white"})
THR = 1.0
TG = "C:/Users/felix/Documents/GitHub/ST_Final_Report_Felix_Duemig/thesis/Graphs/"

# ---- 1) strip plot ----
rng = np.random.default_rng(3)
def xy(cs): return np.array([max(sw.get(c, np.nan), 0.04) for c in cs]), rng.uniform(-0.7, 0.7, len(cs))
fig, ax = plt.subplots(figsize=(9.2, 2.4))
xp, yp = xy(P); xf, yf = xy(F)
ax.axvline(THR, ls="--", color="#9A9A9A", lw=1.1, zorder=1)  # grey dashed; "flag at 1 pp" label added manually
ax.scatter(xp, yp, s=55, c=GREEN, edgecolors="white", linewidths=0.7, zorder=3, label="PASS (n=%d)" % len(P))
ax.scatter(xf, yf, s=55, c=RED, edgecolors="white", linewidths=0.7, zorder=3, label="FAIL (n=%d)" % len(F))
ax.axhline(0, color=GREY, lw=0.6, zorder=1)
# tech labels / threshold caption are added manually by the author
ax.set_xscale("symlog", linthresh=1); ax.set_xlim(0, 140); ax.set_ylim(-1.1, 1.1); ax.set_yticks([])
ax.set_xlabel("perturbation swing  [percentage points]", fontsize=10)
for s in ["left", "right", "top"]: ax.spines[s].set_visible(False)
ax.set_xticks([0, 1, 5, 10, 30, 100]); ax.set_xticklabels(["0", "1", "5", "10", "30", "100"])
ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.2), ncol=2, frameon=False, fontsize=9)
fig.tight_layout(); fig.savefig(TG + "cb_swing_stripplot.png", dpi=200, bbox_inches="tight")
fig.savefig("RC_report/cb_swing_stripplot.png", dpi=200, bbox_inches="tight"); plt.close(fig)

# ---- 2) confusion matrix at THR=1 ----
swP = np.array([sw.get(c, 0) for c in P]); swF = np.array([sw.get(c, 0) for c in F])
TP = int((swF >= THR).sum()); FN = int((swF < THR).sum()); FP = int((swP >= THR).sum()); TN = int((swP < THR).sum())
fig, ax = plt.subplots(figsize=(5.6, 3.5)); ax.set_xlim(0, 2); ax.set_ylim(0, 2); ax.axis("off")
GREENL, REDL = "#E3EAD2", "#F0D6D3"
cells = [(0,1,TP,GREENL,"correct (detected)"),(1,1,FP,REDL,"Type I error\n(false positive)"),
         (0,0,FN,REDL,"Type II error\n(false negative)"),(1,0,TN,GREENL,"correct (trusted)")]
for cx, cy, val, col, lab in cells:
    ax.add_patch(Rectangle((cx, cy), 1, 1, facecolor=col, edgecolor=DARK, lw=1.0))
    ax.text(cx+0.5, cy+0.62, str(val), ha="center", va="center", fontsize=24, fontweight="bold", color=DARK)
    ax.text(cx+0.5, cy+0.22, lab, ha="center", va="center", fontsize=10, color="#555")
ax.text(0.5, 2.13, "actually FAIL\n(unreliable)", ha="center", fontsize=9, color=DARK)
ax.text(1.5, 2.13, "actually PASS\n(reliable)", ha="center", fontsize=9, color=DARK)
ax.text(-0.06, 1.5, "flagged\n(>= 1 pp)", ha="right", va="center", fontsize=9, color=DARK)
ax.text(-0.06, 0.5, "not flagged\n(< 1 pp)", ha="right", va="center", fontsize=9, color=DARK)
ax.text(1.0, -0.3, "n = %d     precision = %.2f     recall = %.2f" % (len(P)+len(F), TP/(TP+FP), TP/(TP+FN)),
        ha="center", fontsize=9, color=DARK)
fig.savefig(TG + "cb_confusion_matrix.png", dpi=200, bbox_inches="tight")
fig.savefig("RC_report/cb_confusion_matrix.png", dpi=200, bbox_inches="tight"); plt.close(fig)
print("THR=%.0f: TP=%d FP=%d FN=%d TN=%d  precision=%.2f recall=%.2f" % (THR, TP, FP, FN, TN, TP/(TP+FP), TP/(TP+FN)))
print("saved stripplot + confusion_matrix")
