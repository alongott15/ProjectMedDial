"""
framework_diagram.py
====================
Publication-quality pipeline diagram for the MedDial framework.
Saved as framework_diagram.pdf + framework_diagram.png (300 DPI).
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from pathlib import Path

OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# ── Colours ────────────────────────────────────────────────────────────────────
C = {
    "data":       "#1565C0",  # dark blue   – data / records
    "process":    "#2E7D32",  # dark green  – processing steps
    "agent":      "#6A1B9A",  # purple      – LLM agents
    "profile":    "#E65100",  # orange      – profile types
    "judge":      "#AD1457",  # deep pink   – evaluation
    "output":     "#00695C",  # teal        – final output
    "arrow":      "#37474F",  # dark grey   – neutral arrows
    "loop":       "#B71C1C",  # red         – feedback loop
    "bg_phase":   "#F5F5F5",  # light grey  – phase backgrounds
    "text_light": "#FFFFFF",
    "text_dark":  "#212121",
}

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size":   9,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.15,
})

FIG_W, FIG_H = 20, 14
fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
ax.set_xlim(0, FIG_W)
ax.set_ylim(0, FIG_H)
ax.axis("off")


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def box(x, y, w, h, color, title, sub=None,
        fontsize=9.5, subsize=8.0, bold=False, alpha=0.93, zorder=3):
    patch = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.12",
        facecolor=color, edgecolor="white",
        linewidth=1.4, alpha=alpha, zorder=zorder,
    )
    ax.add_patch(patch)
    ty = y if sub is None else y + h * 0.16
    ax.text(x, ty, title, ha="center", va="center",
            fontsize=fontsize, color=C["text_light"],
            fontweight="bold" if bold else "normal", zorder=zorder + 1)
    if sub:
        ax.text(x, y - h * 0.24, sub, ha="center", va="center",
                fontsize=subsize, color=C["text_light"],
                alpha=0.90, style="italic", zorder=zorder + 1)


def arrow(x0, y0, x1, y1, color=None, label="", lw=1.7,
          conn="arc3,rad=0.0", zorder=5):
    color = color or C["arrow"]
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw,
                                connectionstyle=conn),
                zorder=zorder)
    if label:
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        ax.text(mx, my, label, ha="center", va="center",
                fontsize=8.0, color=color, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.18", fc="white",
                          ec=color, lw=0.7, alpha=0.95),
                zorder=zorder + 1)


def diamond(x, y, w, h, color, text, fontsize=9, zorder=4):
    dx, dy = w / 2, h / 2
    pts = [(x, y + dy), (x + dx, y), (x, y - dy), (x - dx, y)]
    poly = plt.Polygon(pts, closed=True,
                       facecolor=color, edgecolor="white",
                       linewidth=1.4, alpha=0.93, zorder=zorder)
    ax.add_patch(poly)
    ax.text(x, y, text, ha="center", va="center",
            fontsize=fontsize, color=C["text_light"],
            fontweight="bold", zorder=zorder + 1)


def phase_bg(x0, y0, x1, y1, label):
    patch = FancyBboxPatch(
        (x0, y0), x1 - x0, y1 - y0,
        boxstyle="round,pad=0.05",
        facecolor=C["bg_phase"], edgecolor="#BDBDBD",
        linewidth=1.0, alpha=0.55, zorder=1,
    )
    ax.add_patch(patch)
    ax.text((x0 + x1) / 2, y1 - 0.14, label,
            ha="center", va="top", fontsize=9.0,
            color="#424242", fontweight="bold", style="italic", zorder=2)


def vline(x, y0, y1, color, lw=1.7):
    ax.plot([x, x], [y0, y1], color=color, lw=lw, zorder=5)


def hline(x0, x1, y, color, lw=1.7):
    ax.plot([x0, x1], [y, y], color=color, lw=lw, zorder=5)


# ══════════════════════════════════════════════════════════════════════════════
# Phase backgrounds  (bottom=0.40, top=13.30)
# ══════════════════════════════════════════════════════════════════════════════
PT, PB = 13.30, 0.40

phase_bg(0.15,  PB, 5.05,  PT, "Phase 1 · GTMF Generation")
phase_bg(5.15,  PB, 9.05,  PT, "Phase 2 · Profile Derivation")
phase_bg(9.15,  PB, 19.85, PT, "Phase 3 · Dialogue Generation")

for xd in (5.10, 9.10):
    ax.plot([xd, xd], [PB, PT], lw=1.2, color="#9E9E9E",
            linestyle="--", alpha=0.7, zorder=2)


# ══════════════════════════════════════════════════════════════════════════════
# Phase 1 — GTMF Generation   (centre x = 2.60)
# ══════════════════════════════════════════════════════════════════════════════
P1X = 2.60
BW  = 3.80   # box width for phase 1

# MIMIC-III
box(P1X, 12.30, BW, 0.90, C["data"],
    "MIMIC-III EHR Database", bold=True,
    sub="Clinical Discharge Summaries")

arrow(P1X, 11.85, P1X, 11.20)

# Light-case filter
box(P1X, 10.85, BW, 0.90, C["process"],
    "Light-Case Filter",
    sub="50+ symptom terms · exclude ICU / severe")

arrow(P1X, 10.40, P1X, 9.75, label="passed")

# GPT-4.1 extraction  (chunking folded into subtext)
box(P1X, 9.35, BW, 1.00, C["agent"],
    "GPT-4.1 Extraction Agent", bold=True,
    sub="3k-char chunked · structured JSON · bias-aware")

arrow(P1X, 8.85, P1X, 8.10)

# GTMF Record  (fields shown inline)
box(P1X, 7.50, BW, 1.20, C["data"],
    "GTMF Record", bold=True,
    sub="Core: Symptoms · Diagnoses · Treatments\n"
        "Context: Demographics · History · Medications",
    subsize=7.8)

# Horizontal arrow from GTMF → Phase 2 function
arrow(P1X + BW / 2, 7.50, 5.15, 7.50, color=C["data"])


# ══════════════════════════════════════════════════════════════════════════════
# Phase 2 — Profile Derivation   (centre x = 7.10)
# ══════════════════════════════════════════════════════════════════════════════
P2X  = 7.10
PBW  = 3.20   # profile box width

# generate_all_profile_types()  – drawn first so profile boxes appear on top
box(P2X, 7.50, PBW, 0.80, C["process"],
    "generate_all_profile_types()", bold=True,
    sub="Utils/partial_profile.py", subsize=7.5)

# Arrows from function up to FULL and down to NO_DIAG_NO_TREAT
arrow(P2X, 7.50 + 0.40, P2X, 10.55, color=C["profile"])
arrow(P2X, 7.50 - 0.40, P2X, 5.05,  color=C["profile"])

# Profile boxes
PROFILES = [
    (10.90, "FULL",                   "Symptoms · Diagnoses\n· Treatment Options"),
    ( 7.50, "NO_DIAGNOSIS",           "Diagnoses removed"),
    ( 4.20, "NO_DIAGNOSIS\n_NO_TREATMENT", "Diagnoses + Treatments\nremoved"),
]

for py, ptitle, psub in PROFILES:
    h = 1.10 if "\n" in ptitle else 0.95
    box(P2X, py, PBW, h, C["profile"],
        ptitle, bold=True, sub=psub, subsize=7.8)


# ══════════════════════════════════════════════════════════════════════════════
# Phase 3 — Iterative Dialogue Generation
# ══════════════════════════════════════════════════════════════════════════════

# ── Iteration loop background ─────────────────────────────────────────────────
LX0, LX1 = 9.30, 15.80
LY0, LY1 = 1.40, 13.00

loop_patch = FancyBboxPatch(
    (LX0, LY0), LX1 - LX0, LY1 - LY0,
    boxstyle="round,pad=0.10",
    facecolor="#FFF8E1", edgecolor=C["loop"],
    linewidth=1.8, alpha=0.40, zorder=1,
)
ax.add_patch(loop_patch)
ax.text((LX0 + LX1) / 2, LY1 - 0.16,
        "Iterative Generation Loop  (max 3 attempts)",
        ha="center", va="top", fontsize=9.0,
        color=C["loop"], fontweight="bold", style="italic", zorder=2)

# ── Arrows: profile boxes → loop ─────────────────────────────────────────────
for py, _, _ in PROFILES:
    arrow(P2X + PBW / 2, py, LX0, py, color=C["profile"])

# ── Agents (side by side at top of loop) ─────────────────────────────────────
PAT_X, DOC_X = 10.70, 14.40
AGENT_Y = 12.00
ABW, ABH = 2.90, 0.95

box(PAT_X, AGENT_Y, ABW, ABH, C["agent"],
    "Patient Agent", bold=True,
    sub="Profile-constrained · bias-aware")

box(DOC_X, AGENT_Y, ABW, ABH, C["agent"],
    "Doctor Agent", bold=True,
    sub="Progressive questioning")

# Double-headed arrow between agents
CX = (PAT_X + DOC_X) / 2
ax.annotate("", xy=(DOC_X - ABW / 2 - 0.08, AGENT_Y),
            xytext=(PAT_X + ABW / 2 + 0.08, AGENT_Y),
            arrowprops=dict(arrowstyle="<->", color=C["arrow"], lw=1.8),
            zorder=5)
ax.text(CX, AGENT_Y + 0.40, "multi-turn conversation",
        ha="center", va="bottom", fontsize=8.0, color=C["arrow"])

# ── simulate_dialogue() ───────────────────────────────────────────────────────
SIM_Y = 10.30
SIM_X = CX
SBW   = 4.60

box(SIM_X, SIM_Y, SBW, 0.95, C["process"],
    "simulate_dialogue()", bold=True,
    sub="Loop detection · confusion limit · max turns=30")

arrow(PAT_X, AGENT_Y - ABH / 2, SIM_X - SBW * 0.28, SIM_Y + 0.48,
      color=C["arrow"], conn="arc3,rad=0.1")
arrow(DOC_X, AGENT_Y - ABH / 2, SIM_X + SBW * 0.28, SIM_Y + 0.48,
      color=C["arrow"], conn="arc3,rad=-0.1")

# ── DeepEval Judge ───────────────────────────────────────────────────────────
JUDGE_Y = 8.35
JBW     = 4.80

arrow(SIM_X, SIM_Y - 0.48, SIM_X, JUDGE_Y + 0.50)

box(SIM_X, JUDGE_Y, JBW, 0.95, C["judge"],
    "DeepEval Judge Agent", bold=True,
    sub="GPT-4.1  ·  GEval metrics  ·  RAGAS faithfulness")

# ── Sub-scores ───────────────────────────────────────────────────────────────
SUB_Y  = 6.55
SUB_W  = 1.35
SUB_H  = 0.90
SUB_XS = [SIM_X - 1.60, SIM_X, SIM_X + 1.60]
SUB_LABELS = [
    "Naturalness\n(× 0.4)",
    "Profile\nCompliance\n(× 0.3)",
    "RAGAS\nFaithfulness\n(× 0.3)",
]

for sx, sl in zip(SUB_XS, SUB_LABELS):
    arrow(SIM_X, JUDGE_Y - 0.48, sx, SUB_Y + SUB_H / 2,
          color=C["judge"], lw=1.3)
    box(sx, SUB_Y, SUB_W, SUB_H, C["judge"], sl,
        fontsize=8.0, alpha=0.80)

# ── Combined score → diamond ──────────────────────────────────────────────────
DIAM_Y = 4.80
arrow(SIM_X, SUB_Y - SUB_H / 2, SIM_X, DIAM_Y + 0.44,
      color=C["judge"], label="combined score")

diamond(SIM_X, DIAM_Y, 2.70, 0.85, C["judge"], "Score ≥ 0.70?")

# ── PromptImprovement (NO path) ───────────────────────────────────────────────
IMP_Y = 2.80
IMP_X = SIM_X
IBW   = 4.60

arrow(SIM_X, DIAM_Y - 0.43, IMP_X, IMP_Y + 0.45,
      color=C["loop"], lw=1.8, label="NO")

box(IMP_X, IMP_Y, IBW, 0.90, C["agent"],
    "Prompt Improvement Agent", bold=True,
    sub="Judge feedback → refined prompts")

# Loop-back arrow: left side, up to agents
LOOP_BACK_X = LX0 + 0.22
hline(IMP_X - IBW / 2, LOOP_BACK_X, IMP_Y, C["loop"])
vline(LOOP_BACK_X, IMP_Y, AGENT_Y, C["loop"])
arrow(LOOP_BACK_X, AGENT_Y, PAT_X - ABW / 2, AGENT_Y,
      color=C["loop"], lw=1.8)
ax.text(LOOP_BACK_X - 0.12, (IMP_Y + AGENT_Y) / 2,
        "retry", ha="right", va="center",
        fontsize=8.0, color=C["loop"], fontweight="bold", rotation=90)

# ── Generated Dialogue  (YES path, terminal) ──────────────────────────────────
GEN_X = 18.00
GEN_Y = DIAM_Y
GBW   = 3.50
GBH   = 1.30

arrow(SIM_X + 2.70 / 2, DIAM_Y, GEN_X - GBW / 2, DIAM_Y,
      color=C["output"], lw=2.2, label="YES")

box(GEN_X, GEN_Y, GBW, GBH, C["output"],
    "Generated Dialogue", bold=True,
    sub="Doctor–Patient conversation\nJudge score · profile type · turn count",
    subsize=8.0)


# ══════════════════════════════════════════════════════════════════════════════
# Title & legend
# ══════════════════════════════════════════════════════════════════════════════
ax.text(FIG_W / 2, FIG_H - 0.22,
        "MedDial: End-to-End Pipeline for Synthetic Medical Dialogue Generation",
        ha="center", va="top", fontsize=14, fontweight="bold",
        color=C["text_dark"], zorder=10)

legend_items = [
    (C["data"],    "Data / Record"),
    (C["process"], "Processing Step"),
    (C["agent"],   "LLM Agent (GPT-4.1)"),
    (C["profile"], "Profile Type"),
    (C["judge"],   "Evaluation / Judge"),
    (C["output"],  "Generated Dialogue"),
    (C["loop"],    "Feedback / Retry Loop"),
]
handles = [mpatches.Patch(color=c, label=l) for c, l in legend_items]
ax.legend(handles=handles, loc="lower center",
          bbox_to_anchor=(0.5, 0.0),
          ncol=len(legend_items), fontsize=8.5,
          frameon=True, framealpha=0.92,
          edgecolor="#BDBDBD", handlelength=1.4, handleheight=0.95)


# ══════════════════════════════════════════════════════════════════════════════
# Save
# ══════════════════════════════════════════════════════════════════════════════
out_pdf = OUT / "framework_diagram.pdf"
out_png = OUT / "framework_diagram.png"
plt.savefig(out_pdf)
plt.savefig(out_png, dpi=300)
print(f"Saved:\n  {out_pdf}\n  {out_png}")
plt.close()
