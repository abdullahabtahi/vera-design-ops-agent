"""
Generate HCAI 2x2 quadrant chart (Shneiderman 2022).
Shows where Vera sits vs. fully autonomous AI tools.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

OUT = Path(__file__).parent / "public"
OUT.mkdir(exist_ok=True)

BG      = "#0d1117"
GRID    = "#21262d"
TEXT    = "#e6edf3"
SUBTEXT = "#8b949e"
VERA_C  = "#818cf8"    # indigo — Vera's position
AUTO_C  = "#f87171"    # red — "autonomous AI" zone
SAFE_C  = "#4ade80"    # green — HCAI target zone
BORDER  = "#30363d"

fig, ax = plt.subplots(figsize=(9, 7.5), facecolor=BG)
ax.set_facecolor(BG)

# ── Quadrant shading ─────────────────────────────────────────────────────────
# Upper-right = HCAI target (green tint)
ax.fill_between([0.5, 1.0], [0.5, 0.5], [1.0, 1.0],
                color=SAFE_C, alpha=0.07, zorder=1)
# Lower-right = autonomous/risky zone (red tint)
ax.fill_between([0.5, 1.0], [0.0, 0.0], [0.5, 0.5],
                color=AUTO_C, alpha=0.07, zorder=1)

# ── Grid lines ───────────────────────────────────────────────────────────────
ax.axhline(0.5, color=BORDER, linewidth=1.0, zorder=2)
ax.axvline(0.5, color=BORDER, linewidth=1.0, zorder=2)
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)

# ── Quadrant labels ──────────────────────────────────────────────────────────
quad_kw = dict(fontsize=9, color=SUBTEXT, ha="center", va="center",
               fontstyle="italic")
ax.text(0.25, 0.75, "Manual craft\nHigh skill, low automation\n(piano, bicycling)",
        **quad_kw)
ax.text(0.25, 0.25, "Simple tasks\nLow skill, low automation",
        **quad_kw)
ax.text(0.75, 0.25, "Autonomous AI\nMachine decides, human watches\n(risky for open-ended tasks)",
        **{**quad_kw, "color": "#f87171"})
ax.text(0.75, 0.82,
        "HCAI target zone\nHigh automation + High human control",
        fontsize=9, color=SAFE_C, ha="center", va="center",
        fontstyle="italic", fontweight="semibold")

# ── Vera marker ──────────────────────────────────────────────────────────────
vera_x, vera_y = 0.80, 0.73
ax.scatter([vera_x], [vera_y], s=220, color=VERA_C, zorder=5,
           edgecolors=BG, linewidths=2)
ax.annotate(
    "Vera\nDesign Ops Agent",
    xy=(vera_x, vera_y),
    xytext=(vera_x + 0.10, vera_y - 0.12),
    fontsize=9.5, color=VERA_C, fontweight="semibold",
    arrowprops=dict(arrowstyle="-", color=VERA_C, lw=1.2),
    ha="center",
)

# ── "Other AI tools" marker ──────────────────────────────────────────────────
other_x, other_y = 0.72, 0.28
ax.scatter([other_x], [other_y], s=120, color=AUTO_C, zorder=5,
           edgecolors=BG, linewidths=2, marker="s")
ax.annotate(
    "Fully autonomous\ncritique tools",
    xy=(other_x, other_y),
    xytext=(other_x - 0.18, other_y - 0.11),
    fontsize=8.5, color=AUTO_C,
    arrowprops=dict(arrowstyle="-", color=AUTO_C, lw=1.0),
    ha="center",
)

# ── Axes labels ──────────────────────────────────────────────────────────────
ax.set_xlabel("Level of Computer Automation  →", fontsize=11,
              color=TEXT, labelpad=12)
ax.set_ylabel("←  Level of Human Control", fontsize=11,
              color=TEXT, labelpad=12)
ax.tick_params(left=False, bottom=False,
               labelleft=False, labelbottom=False)
for spine in ax.spines.values():
    spine.set_edgecolor(BORDER)
    spine.set_linewidth(0.8)

# ── Low / High labels on axes ────────────────────────────────────────────────
# X-axis: Low (left) and High (right)
ax.text(0.04, 0.03, "Low", fontsize=8.5, color=SUBTEXT,
        ha="left", va="bottom", transform=ax.transAxes)
ax.text(0.96, 0.03, "High", fontsize=8.5, color=SUBTEXT,
        ha="right", va="bottom", transform=ax.transAxes)
# Y-axis: Low (bottom) and High (top)
ax.text(0.01, 0.06, "Low", fontsize=8.5, color=SUBTEXT,
        ha="left", va="bottom", transform=ax.transAxes, rotation=90)
ax.text(0.01, 0.90, "High", fontsize=8.5, color=SUBTEXT,
        ha="left", va="top", transform=ax.transAxes, rotation=90)

ax.set_title(
    "Human-Centered AI Framework  (Shneiderman, 2022)\n"
    "Vera sits in the upper-right: high automation, full human control",
    fontsize=11, color=TEXT, pad=14, fontweight="semibold"
)

plt.tight_layout()
fig.savefig(OUT / "hcai_quadrant.png", dpi=160, bbox_inches="tight",
            facecolor=BG, edgecolor="none")
plt.close(fig)
print("✓ hcai_quadrant.png")
