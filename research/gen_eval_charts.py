"""
Generate eval result visualizations for the Vera README.
Outputs two PNGs to research/public/:
  - eval_radar.png    — radar chart: 8 rubric scores, Case 1 vs Case 2
  - eval_summary.png  — horizontal bar: Route B + Route A overview scores
"""

import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
from pathlib import Path

OUT = Path(__file__).parent / "public"
OUT.mkdir(exist_ok=True)

# ── Palette (matches dark GitHub + Vera design language) ─────────────────────
BG       = "#0d1117"
GRID     = "#21262d"
CASE1_C  = "#818cf8"   # indigo-400
CASE2_C  = "#38bdf8"   # sky-400
THRESH_C = "#f59e0b"   # amber-400  (threshold line)
TEXT     = "#e6edf3"
SUBTEXT  = "#8b949e"
PASS_C   = "#4ade80"   # green-400
FAIL_C   = "#f87171"   # red-400

# ── 1. RADAR CHART ────────────────────────────────────────────────────────────

labels = [
    "Critique\nStructure",
    "Rule\nCitations",
    "Actionable\nFixes",
    "Visual\nGrounding",
    "No Fatal\nErrors",
    "Headline\nFirst",
    "Priority\nVerdict",
    "Impact\nBefore Rules",
]
case1 = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
case2 = [1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0]

N = len(labels)
angles = [n / float(N) * 2 * math.pi for n in range(N)]
angles += angles[:1]  # close the polygon

c1 = case1 + case1[:1]
c2 = case2 + case2[:1]

fig = plt.figure(figsize=(10, 10), facecolor=BG)
ax  = fig.add_subplot(111, polar=True, facecolor=BG)
# Reserve space at bottom for legend
fig.subplots_adjust(bottom=0.22, top=0.88)

# Grid rings
for r in [0.25, 0.5, 0.75, 1.0]:
    ring_angles = np.linspace(0, 2 * math.pi, 200)
    ax.plot(ring_angles, [r] * 200,
            color=GRID, linewidth=0.8, linestyle="--", zorder=1)
    ax.text(math.pi / 2, r + 0.04, f"{r:.2f}",
            ha="center", va="bottom", fontsize=7.5,
            color=SUBTEXT, fontfamily="monospace")

# Spoke lines
for angle in angles[:-1]:
    ax.plot([angle, angle], [0, 1], color=GRID, linewidth=0.8, zorder=1)

# Threshold ring at 0.7 (Route A threshold)
thresh_angles = np.linspace(0, 2 * math.pi, 200)
ax.plot(thresh_angles, [0.7] * 200,
        color=THRESH_C, linewidth=1.5, linestyle=":", zorder=2, alpha=0.8)
ax.text(math.pi * 0.08, 0.74, "threshold 0.7",
        ha="left", va="bottom", fontsize=7.5,
        color=THRESH_C, fontfamily="monospace")

# Case 1 — perfect
ax.plot(angles, c1, color=CASE1_C, linewidth=2.2, zorder=4)
ax.fill(angles, c1, color=CASE1_C, alpha=0.18, zorder=3)

# Case 2 — one rubric failed
ax.plot(angles, c2, color=CASE2_C, linewidth=2.2, zorder=4, linestyle="--")
ax.fill(angles, c2, color=CASE2_C, alpha=0.12, zorder=3)

# Dot markers
ax.scatter(angles[:-1], case1, s=55, color=CASE1_C, zorder=5, edgecolors=BG, linewidths=1.2)
ax.scatter(angles[:-1], case2, s=55, color=CASE2_C, zorder=5, edgecolors=BG, linewidths=1.2)

# Labels — extra pad so they don't crowd the chart edge
ax.set_xticks(angles[:-1])
ax.set_xticklabels(labels, size=9.5, color=TEXT, fontfamily="sans-serif")
ax.tick_params(axis="x", pad=18)
ax.set_yticklabels([])
ax.set_ylim(0, 1.2)
ax.spines["polar"].set_visible(False)

# Legend — placed in figure coords below the polar axes
leg = [
    mpatches.Patch(facecolor=CASE1_C, alpha=0.7,
                   label="Case 1 — ClimatePulse dashboard  (1.0 / 1.0)"),
    mpatches.Patch(facecolor=CASE2_C, alpha=0.7,
                   label="Case 2 — minimal context run  (0.875 / 1.0)"),
    mpatches.Patch(facecolor=THRESH_C, alpha=0.7,
                   label="Pass threshold  (0.7)"),
]
fig.legend(handles=leg, loc="lower center", bbox_to_anchor=(0.5, 0.02),
           ncol=1, fontsize=9, frameon=False,
           labelcolor=TEXT, handlelength=1.4, handleheight=1.2)

fig.suptitle(
    "Route A — Figma Critique Pipeline\nRubric Scores  (LLM-as-Judge · Gemini)",
    fontsize=13, color=TEXT, fontweight="semibold", y=0.97
)

fig.savefig(OUT / "eval_radar.png", dpi=160, bbox_inches="tight",
            facecolor=BG, edgecolor="none")
plt.close(fig)
print("✓ eval_radar.png")


# ── 2. SUMMARY BAR CHART ─────────────────────────────────────────────────────

metrics = [
    ("Route B  ·  UX Knowledge\n7 test cases",            0.833, 0.80),
    ("Route A  ·  Figma Critique  (Case 1)\nClimatePulse dashboard",  1.000, 0.70),
    ("Route A  ·  Figma Critique  (Case 2)\nMinimal-context run",     0.875, 0.70),
]

fig2, ax2 = plt.subplots(figsize=(9, 4.2), facecolor=BG)
ax2.set_facecolor(BG)

bar_colors = [CASE1_C, CASE1_C, CASE2_C]
labels_y   = [m[0] for m in metrics]
scores     = [m[1] for m in metrics]
thresholds = [m[2] for m in metrics]

y_pos = np.arange(len(metrics))
bars  = ax2.barh(y_pos, scores, height=0.45,
                 color=bar_colors, alpha=0.85, zorder=3)

# Threshold tick marks
for i, (_, score, thresh) in enumerate(metrics):
    ax2.plot([thresh, thresh], [i - 0.3, i + 0.3],
             color=THRESH_C, linewidth=2, zorder=5)

# Score labels
for bar, score in zip(bars, scores):
    ax2.text(bar.get_width() - 0.015, bar.get_y() + bar.get_height() / 2,
             f"{score:.3f}", va="center", ha="right",
             fontsize=11.5, color=BG, fontfamily="monospace", fontweight="bold")

# Pass badges
for i, (_, score, thresh) in enumerate(metrics):
    status  = "✓ PASS" if score >= thresh else "✗ FAIL"
    s_color = PASS_C if score >= thresh else FAIL_C
    ax2.text(1.02, i, status, va="center", ha="left",
             fontsize=10, color=s_color, fontfamily="monospace", fontweight="bold")

# Grid
ax2.set_xlim(0, 1.0)
ax2.set_xticks([0, 0.25, 0.5, 0.7, 0.75, 0.8, 1.0])
ax2.set_xticklabels(["0", "0.25", "0.5", "0.7", "0.75", "0.8", "1.0"],
                    fontsize=8.5, color=SUBTEXT, fontfamily="monospace")
ax2.xaxis.grid(True, color=GRID, linewidth=0.8, zorder=0)
ax2.set_axisbelow(True)

ax2.set_yticks(y_pos)
ax2.set_yticklabels(labels_y, fontsize=9.5, color=TEXT)
ax2.tick_params(axis="y", length=0, pad=8)

for spine in ax2.spines.values():
    spine.set_visible(False)
ax2.tick_params(axis="x", colors=SUBTEXT, length=3)

ax2.set_xlabel("rubric_based_final_response_quality_v1  score",
               fontsize=9, color=SUBTEXT, labelpad=10)
ax2.set_title(
    "ADK Eval Results  ·  Vera — Design Ops Agent\nLLM-as-Judge  ·  Gemini  ·  binary rubric mean",
    fontsize=11.5, color=TEXT, pad=14, fontweight="semibold"
)

# Threshold legend
ax2.plot([], [], color=THRESH_C, linewidth=2, label="Pass threshold")
ax2.legend(loc="lower right", fontsize=8.5, frameon=False, labelcolor=TEXT)

plt.tight_layout()
fig2.savefig(OUT / "eval_summary.png", dpi=160, bbox_inches="tight",
             facecolor=BG, edgecolor="none")
plt.close(fig2)
print("✓ eval_summary.png")
