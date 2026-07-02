"""Schematic of the two LP solving methods on the SAME feasible polytope:
(a) simplex walks the boundary vertices, (b) interior-point follows the central path through
the interior to a near-optimal point and crossover snaps it to the same optimum vertex. ETH style.
Dashed lines are drawn uniformly via plot('--'); every arrowhead is a solid '->' (same as crossover)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon

DARK, GREY, GREEN, LIGHT = "#1A1A1A", "#6F6F6F", "#627313", "#BFBFBF"
plt.rcParams.update({"font.family": "serif",
                     "font.serif": ["CMU Serif", "Times New Roman", "DejaVu Serif"],
                     "text.color": DARK, "savefig.facecolor": "white", "figure.facecolor": "white"})

V = np.array([[0.16, 0.55], [0.40, 0.93], [0.80, 0.88], [0.92, 0.48], [0.62, 0.13], [0.25, 0.20]])
OPT = V[5]                                       # optimum = a vertex of the shared region
chords = [(1, 4), (2, 5), (0, 3)]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.2, 3.4))


def draw_region(ax):
    ax.add_patch(Polygon(V, closed=True, fill=False, edgecolor=GREY, lw=0.9, zorder=1))
    for a, b in chords:
        ax.plot([V[a, 0], V[b, 0]], [V[a, 1], V[b, 1]], color=LIGHT, lw=0.5, zorder=1)


def head(ax, p_from, p_to, color=DARK):          # solid '->' arrowhead at p_to (same style as crossover)
    p_from, p_to = np.asarray(p_from, float), np.asarray(p_to, float)
    base = p_to - 0.05 * (p_to - p_from) / np.linalg.norm(p_to - p_from)
    ax.annotate("", xy=p_to, xytext=base, zorder=4,
                arrowprops=dict(arrowstyle="->", lw=1.7, color=color, shrinkA=0, shrinkB=0))


# ---- (a) Simplex: dashed walk along boundary vertices, arrowhead at each step ----
draw_region(ax1)
path = [2, 1, 0, 5]
ax1.plot(V[path, 0], V[path, 1], "--", color=DARK, lw=1.9, zorder=3)
for i in range(len(path) - 1):
    head(ax1, V[path[i]], V[path[i + 1]], DARK)
ax1.plot(*V[2], "o", color=GREY, ms=7, zorder=5)
ax1.plot(*OPT, "o", color=GREEN, ms=7, zorder=5)
ax1.annotate("initial feasible\nsolution", xy=V[2], xytext=(0.58, 1.04), fontsize=8.5,
             ha="center", arrowprops=dict(arrowstyle="-", lw=0.6, color=GREY))
ax1.annotate("optimum\nsolution", xy=OPT, xytext=(0.05, 0.05), fontsize=8.5,
             ha="left", arrowprops=dict(arrowstyle="-", lw=0.6, color=GREY))
ax1.set_title("(a) Simplex method", fontsize=10, pad=10)

# ---- (b) Interior-point: dashed central path + crossover to the vertex ----
draw_region(ax2)
init, near = np.array([0.62, 0.58]), np.array([0.45, 0.34])
t = np.linspace(0, 1, 60)
cx = init[0] + (near[0] - init[0]) * t + 0.10 * np.sin(np.pi * t)
cy = init[1] + (near[1] - init[1]) * t
ax2.plot(cx, cy, "--", color=DARK, lw=1.9, zorder=3)
head(ax2, (cx[-6], cy[-6]), near, DARK)
ax2.annotate("", xy=OPT, xytext=near, zorder=3,                     # crossover step onto the vertex
             arrowprops=dict(arrowstyle="->", lw=1.7, color=GREEN))
ax2.plot(*init, "o", color=GREY, ms=7, zorder=5)
ax2.plot(*near, "o", color=DARK, ms=4, zorder=5)
ax2.plot(*OPT, "o", color=GREEN, ms=7, zorder=5)
ax2.annotate("initial feasible\nsolution", xy=init, xytext=(0.74, 0.74), fontsize=8.5,
             ha="center", arrowprops=dict(arrowstyle="-", lw=0.6, color=GREY))
ax2.text(0.30, 0.31, "crossover", fontsize=8.5, ha="right", color=GREEN)
ax2.annotate("optimum\nsolution", xy=OPT, xytext=(0.05, 0.05), fontsize=8.5,
             ha="left", arrowprops=dict(arrowstyle="-", lw=0.6, color=GREY))
ax2.set_title("(b) Interior-point method", fontsize=10, pad=10)

for ax in (ax1, ax2):
    ax.set_xlim(0, 1.05); ax.set_ylim(0, 1.12); ax.set_aspect("equal"); ax.axis("off")
fig.tight_layout()
for d in ["C:/Users/felix/Documents/GitHub/ST_Final_Report_Felix_Duemig/thesis/Graphs/",
          "RC_report/"]:
    fig.savefig(d + "lp_solving_methods.png", dpi=200, bbox_inches="tight")
print("saved lp_solving_methods.png")
