"""
framework_diagram.py
====================
Produces a single, publication-quality figure that illustrates the complete
MedDial pipeline:

  Phase 1 — GTMF Generation
    MIMIC-III CSV  →  Light-Case Filter  →  GPT-4.1 Chunked Extraction
    →  GTMF (Core + Context + Additional)  →  gtmf/ .md files

  Phase 2 — Profile-Type Derivation
    GTMF  →  [FULL | NO_DIAGNOSIS | NO_DIAGNOSIS_NO_TREATMENT]

  Phase 3 — Iterative Dialogue Generation
    Patient & Doctor Agents  →  Simulate Dialogue
    →  DeepEval Judge (Naturalness + Profile Compliance + RAGAS Faithfulness)
    →  REALISTIC  →  save output
    →  UNREALISTIC + attempts left  →  PromptImprovement  →  retry (up to 3×)

  Phase 4 — Output & Evaluation
    Per-dialogue .md files  →  Aggregate statistics
"""

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.patheffects as pe
from pathlib import Path

OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# ── Colour palette ─────────────────────────────────────────────────────────────
C = {
    "data":     "#1565C0",   # dark blue   – data sources / storage
    "process":  "#2E7D32",   # dark green  – processing steps
    "agent":    "#6A1B9A",   # purple      – LLM agents
    "profile":  "#E65100",   # orange      – profile types
    "judge":    "#AD1457",   # deep pink   – judge / evaluation
    "output":   "#00695C",   # teal        – outputs
    "arrow":    "#37474F",   # dark grey   – arrows
    "loop":     "#B71C1C",   # red         – feedback loop
    "bg_phase": "#F5F5F5",   # light grey  – phase background
    "text_dark":"#212121",
    "text_light":"#FFFFFF",
}

FONT = "DejaVu Sans"

plt.rcParams.update({
    "font.family": FONT,
    "font.size": 9,
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.15,
})

FIG_W, FIG_H = 20, 13
fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
ax.set_xlim(0, FIG_W)
ax.set_ylim(0, FIG_H)
ax.axis("off")


# ══════════════════════════════════════════════════════════════════════════════
# Helper functions
# ══════════════════════════════════════════════════════════════════════════════

def box(ax, x, y, w, h, color, text, fontsize=9, text_color=None,
        bold=False, style="round,pad=0.1", alpha=0.92, zorder=3,
        subtext=None, subsize=7.5):
    """Draw a rounded rectangle with centred label (+ optional sub-label)."""
    tc = text_color or C["text_light"]
    patch = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle=style,
        facecolor=color, edgecolor="white",
        linewidth=1.2, alpha=alpha, zorder=zorder,
    )
    ax.add_patch(patch)
    weight = "bold" if bold else "normal"
    ty = y if subtext is None else y + h * 0.14
    ax.text(x, ty, text, ha="center", va="center",
            fontsize=fontsize, color=tc, fontweight=weight, zorder=zorder + 1,
            wrap=True)
    if subtext:
        ax.text(x, y - h * 0.22, subtext, ha="center", va="center",
                fontsize=subsize, color=tc, alpha=0.88, zorder=zorder + 1,
                style="italic")


def phase_bg(ax, x0, y0, x1, y1, label, label_color="#555555"):
    """Draw a light background rectangle labelling a pipeline phase."""
    rect = FancyBboxPatch(
        (x0, y0), x1 - x0, y1 - y0,
        boxstyle="round,pad=0.05",
        facecolor=C["bg_phase"], edgecolor="#BDBDBD",
        linewidth=1.0, alpha=0.55, zorder=1,
    )
    ax.add_patch(rect)
    ax.text((x0 + x1) / 2, y1 - 0.18, label,
            ha="center", va="top", fontsize=8.5,
            color=label_color, fontweight="bold",
            style="italic", zorder=2)


def arrow(ax, x0, y0, x1, y1, color=None, label="", lw=1.6,
          style="arc3,rad=0.0", zorder=4, label_color=None):
    color = color or C["arrow"]
    ax.annotate(
        "", xy=(x1, y1), xytext=(x0, y0),
        arrowprops=dict(
            arrowstyle="-|>",
            color=color,
            lw=lw,
            connectionstyle=style,
        ),
        zorder=zorder,
    )
    if label:
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        lc = label_color or color
        ax.text(mx, my, label, ha="center", va="center",
                fontsize=7.5, color=lc, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.15", fc="white",
                          ec=lc, lw=0.6, alpha=0.9),
                zorder=zorder + 1)


def diamond(ax, x, y, w, h, color, text, fontsize=9, zorder=3):
    """Draw a decision diamond."""
    dx, dy = w / 2, h / 2
    pts = [(x, y + dy), (x + dx, y), (x, y - dy), (x - dx, y)]
    poly = plt.Polygon(pts, closed=True,
                       facecolor=color, edgecolor="white",
                       linewidth=1.2, alpha=0.92, zorder=zorder)
    ax.add_patch(poly)
    ax.text(x, y, text, ha="center", va="center",
            fontsize=fontsize, color=C["text_light"],
            fontweight="bold", zorder=zorder + 1)


def divider(ax, x, y0, y1):
    ax.plot([x, x], [y0, y1], lw=1.2, color="#9E9E9E",
            linestyle="--", zorder=2, alpha=0.7)


# ══════════════════════════════════════════════════════════════════════════════
# Phase backgrounds
# ══════════════════════════════════════════════════════════════════════════════
PHASE_TOP    = 12.55
PHASE_BOTTOM =  0.35

phase_bg(ax, 0.20,  PHASE_BOTTOM, 4.55,  PHASE_TOP, "Phase 1 · GTMF Generation")
phase_bg(ax, 4.65,  PHASE_BOTTOM, 8.10,  PHASE_TOP, "Phase 2 · Profile Derivation")
phase_bg(ax, 8.20,  PHASE_BOTTOM, 15.75, PHASE_TOP, "Phase 3 · Dialogue Generation")
phase_bg(ax, 15.85, PHASE_BOTTOM, 19.80, PHASE_TOP, "Phase 4 · Output & Evaluation")

divider(ax, 4.60,  PHASE_BOTTOM, PHASE_TOP)
divider(ax, 8.15,  PHASE_BOTTOM, PHASE_TOP)
divider(ax, 15.80, PHASE_BOTTOM, PHASE_TOP)


# ══════════════════════════════════════════════════════════════════════════════
# Phase 1 — GTMF Generation
#   Column x ≈ 2.35
# ══════════════════════════════════════════════════════════════════════════════
P1X = 2.35

# MIMIC-III source
box(ax, P1X, 11.90, 3.60, 0.80, C["data"],
    "MIMIC-III EHR Database", fontsize=9.5, bold=True,
    subtext="Discharge Summaries (CSV)")

arrow(ax, P1X, 11.50, P1X, 10.85)

# Light-case filter
box(ax, P1X, 10.55, 3.40, 0.78, C["process"],
    "Light-Case Filter", fontsize=9,
    subtext="50+ symptom terms · exclude ICU/severe")

arrow(ax, P1X, 10.16, P1X, 9.52, label="passed")

# Text chunker
box(ax, P1X, 9.22, 3.40, 0.75, C["process"],
    "Text Chunker", fontsize=9,
    subtext="3000-char chunks · 200-char overlap")

arrow(ax, P1X, 8.85, P1X, 8.25)

# GPT-4.1 extraction
box(ax, P1X, 7.90, 3.40, 0.82, C["agent"],
    "GPT-4.1 Extraction Agent", fontsize=9, bold=True,
    subtext="Structured JSON · bias-aware prompt")

arrow(ax, P1X, 7.49, P1X, 6.92)

# Merge chunks
box(ax, P1X, 6.62, 3.40, 0.75, C["process"],
    "Chunk Merger", fontsize=9,
    subtext="Deduplicate symptoms / diagnoses / treatments")

arrow(ax, P1X, 6.25, P1X, 5.50)

# GTMF structured block — drawn as a stacked card
box(ax, P1X, 5.12, 3.60, 0.95, C["data"],
    "GTMF Record", fontsize=9.5, bold=True,
    subtext="subject_id · hadm_id · case_type")

# Three GTMF sub-fields inside a nested box
GTMF_fields = [
    ("Core Fields",       "Symptoms · Diagnoses\nTreatment_Options",    3.95),
    ("Context Fields",    "Demographics · Med History\nAllergies · Meds", 3.05),
    ("Additional Context","Chief Complaint",                              2.20),
]
for title, sub, fy in GTMF_fields:
    box(ax, P1X, fy, 3.20, 0.68, C["data"],
        title, fontsize=8.0, bold=True,
        subtext=sub, subsize=7.0, alpha=0.80)
    if fy < 3.9:
        arrow(ax, P1X, fy + 0.34, P1X, fy - 0.34 + 0.68, color="#90A4AE")

# bracket / brace showing three sub-fields belong to GTMF
ax.annotate("", xy=(P1X - 1.80, 1.88), xytext=(P1X - 1.80, 4.62),
            arrowprops=dict(arrowstyle="-", color="#78909C", lw=1.0))

arrow(ax, P1X, 4.61, P1X, 4.35)  # Core → link above
arrow(ax, P1X, 1.88, P1X, 1.60)  # bottom sub-field → gtmf/ storage

# Storage
box(ax, P1X, 1.28, 3.20, 0.60, C["data"],
    "gtmf/  · per-case .md files", fontsize=8.5,
    subtext="Resume-aware · skip if exists")


# ══════════════════════════════════════════════════════════════════════════════
# Phase 2 — Profile-Type Derivation
#   Column x ≈ 6.35
# ══════════════════════════════════════════════════════════════════════════════
P2X = 6.35

arrow(ax, 4.15, 6.62, P2X - 1.05, 6.62)   # GTMF → generate_all_profile_types

box(ax, P2X, 6.62, 2.80, 0.80, C["process"],
    "generate_all_profile_types()", fontsize=8.5, bold=True,
    subtext="Utils/partial_profile.py")

# Three profile output boxes at different heights
PROFILE_Y = [9.70, 6.62, 3.55]
PROFILE_COLORS = [C["profile"]] * 3
PROFILE_TITLES = ["FULL", "NO_DIAGNOSIS", "NO_DIAGNOSIS\nNO_TREATMENT"]
PROFILE_SUBS = [
    "Symptoms · Diagnoses\n· Treatment_Options",
    "Symptoms only\n(Diagnoses removed)",
    "Symptoms only\n(Diagnoses + Treatments\nremoved)",
]

arrow(ax, P2X, 7.02, P2X, 8.10, color=C["profile"])   # up → FULL
arrow(ax, P2X, 6.22, P2X, 5.10, color=C["profile"])   # down → NO_DIAG_NO_TREAT

for py, ptitle, psub in zip(PROFILE_Y, PROFILE_TITLES, PROFILE_SUBS):
    box(ax, P2X, py, 2.80, 0.90 if "\n" in psub else 0.80,
        C["profile"], ptitle,
        fontsize=9, bold=True, subtext=psub, subsize=7.5)

# sub-labels
ax.text(P2X + 1.55, 9.70, "profile_type =\n\"FULL\"",
        fontsize=7.0, color=C["profile"], va="center", ha="left")
ax.text(P2X + 1.55, 6.62, "profile_type =\n\"NO_DIAGNOSIS\"",
        fontsize=7.0, color=C["profile"], va="center", ha="left")
ax.text(P2X + 1.55, 3.55, "profile_type =\n\"NO_DIAGNOSIS\n_NO_TREATMENT\"",
        fontsize=7.0, color=C["profile"], va="center", ha="left")


# ══════════════════════════════════════════════════════════════════════════════
# Phase 3 — Iterative Dialogue Generation
#   Main lane x ≈ 11.0 – 15.5
# ══════════════════════════════════════════════════════════════════════════════

# Three arrows (one per profile type) merge into a single lane
MERGE_X = 8.75
DIAL_X   = 11.00

for py in PROFILE_Y:
    arrow(ax, P2X + 1.40, py, MERGE_X - 0.05, py, color=C["profile"])

# Merge node
box(ax, MERGE_X, 6.62, 0.80, 5.30, C["process"],
    "Per\nprofile\ntype\nloop", fontsize=7.5, bold=False,
    style="round,pad=0.05", alpha=0.70)

arrow(ax, MERGE_X + 0.40, 6.62, DIAL_X - 1.10, 6.62, color=C["arrow"])

# ── Attempt loop box ───────────────────────────────────────────────────────────
loop_x0, loop_x1 = 9.50, 15.45
loop_y0, loop_y1 = 2.80, 11.60
loop_rect = FancyBboxPatch(
    (loop_x0, loop_y0), loop_x1 - loop_x0, loop_y1 - loop_y0,
    boxstyle="round,pad=0.12",
    facecolor="#FFF8E1", edgecolor=C["loop"],
    linewidth=1.5, alpha=0.45, zorder=1,
)
ax.add_patch(loop_rect)
ax.text((loop_x0 + loop_x1) / 2, loop_y1 - 0.14,
        "Iterative Generation Loop  (max 3 attempts)",
        ha="center", va="top", fontsize=8.5,
        color=C["loop"], fontweight="bold", style="italic", zorder=2)

# Patient Agent
box(ax, DIAL_X, 10.20, 2.60, 0.85, C["agent"],
    "Patient Agent", fontsize=9.5, bold=True,
    subtext="Profile-constrained · bias-aware\nresponse generation")

# Doctor Agent
box(ax, DIAL_X + 3.20, 10.20, 2.60, 0.85, C["agent"],
    "Doctor Agent", fontsize=9.5, bold=True,
    subtext="Progressive questioning\nhistory-aware")

# Double-headed conversation arrow
ax.annotate("", xy=(DIAL_X + 1.87, 10.20), xytext=(DIAL_X + 1.33, 10.20),
            arrowprops=dict(arrowstyle="<->", color=C["arrow"], lw=1.6), zorder=4)
ax.text(DIAL_X + 1.60, 10.52, "turns", ha="center", va="bottom",
        fontsize=7.5, color=C["arrow"])

# simulate_dialogue
box(ax, DIAL_X + 1.60, 8.80, 4.10, 0.85, C["process"],
    "simulate_dialogue()", fontsize=9, bold=True,
    subtext="max_turns=30 · loop detection · confusion limit")

# Arrows: agents → simulate
arrow(ax, DIAL_X,        9.78, DIAL_X + 0.55, 9.22)
arrow(ax, DIAL_X + 3.20, 9.78, DIAL_X + 2.65, 9.22)

arrow(ax, DIAL_X + 1.60, 8.37, DIAL_X + 1.60, 7.72)

# Conversation transcript box
box(ax, DIAL_X + 1.60, 7.42, 4.10, 0.75, C["process"],
    "Conversation Transcript", fontsize=9,
    subtext="Doctor & Patient turns · formatted text")

arrow(ax, DIAL_X + 1.60, 7.04, DIAL_X + 1.60, 6.42)

# DeepEval Judge
box(ax, DIAL_X + 1.60, 6.10, 4.30, 0.82, C["judge"],
    "DeepEval Judge Agent", fontsize=9.5, bold=True,
    subtext="GPT-4.1  ·  GEval metrics  ·  RAGAS faithfulness")

# Sub-score boxes (below judge, side by side)
SUB_Y = 4.90
SUB_W = 1.22
SUB_SPACING = 1.36
SUB_XS = [DIAL_X + 0.25, DIAL_X + 1.61, DIAL_X + 2.97]
SUB_LABELS = ["Naturalness\n(×0.4)", "Profile\nCompliance\n(×0.3)", "RAGAS\nFaithfulness\n(×0.3)"]

for sx, sl in zip(SUB_XS, SUB_LABELS):
    box(ax, sx, SUB_Y, SUB_W, 0.88, C["judge"],
        sl, fontsize=7.5, bold=False, alpha=0.75)
    arrow(ax, DIAL_X + 1.60, 5.69, sx, SUB_Y + 0.44,
          color=C["judge"], lw=1.2)

# Combined score arrow
arrow(ax, DIAL_X + 1.60, 4.46, DIAL_X + 1.60, 3.95, color=C["judge"])

# Decision diamond
diamond(ax, DIAL_X + 1.60, 3.58, 2.50, 0.72, C["judge"],
        "Score ≥ 0.70?", fontsize=8.5)

# YES → right (to output phase)
arrow(ax, DIAL_X + 2.85, 3.58, 15.65, 3.58, color="#2E7D32", lw=1.8, label="YES")

# NO → check attempts
arrow(ax, DIAL_X + 1.60, 3.22, DIAL_X + 1.60, 2.54, color=C["loop"], lw=1.6, label="NO")

# "Attempts left?" secondary diamond — placed under the loop box
box(ax, DIAL_X + 1.60, 2.20, 2.50, 0.55, C["loop"],
    "Attempts remaining?", fontsize=8, bold=False, alpha=0.85)

# NO → give up (goes right to output as failed)
arrow(ax, DIAL_X + 2.85, 2.20, 15.65, 2.20, color=C["loop"], lw=1.4, label="NO — best kept")

# YES → PromptImprovement
arrow(ax, DIAL_X + 1.60, 1.92, DIAL_X + 1.60, 1.48, color=C["process"], lw=1.6, label="YES")

# PromptImprovement Agent
box(ax, DIAL_X + 1.60, 1.20, 4.20, 0.60, C["agent"],
    "PromptImprovement Agent", fontsize=9, bold=True,
    subtext="Judge feedback → refined patient/doctor prompts")

# Loop-back arrow (goes left, up, back into agents)
ax.annotate("", xy=(DIAL_X - 0.50, 10.20),
            xytext=(DIAL_X - 0.50, 1.20),
            arrowprops=dict(arrowstyle="-|>", color=C["loop"], lw=1.8,
                            connectionstyle="arc3,rad=0.0"), zorder=5)
ax.plot([DIAL_X + 1.60 - 2.10, DIAL_X - 0.50],
        [1.20, 1.20], color=C["loop"], lw=1.8, zorder=5)
ax.text(DIAL_X - 0.68, 6.0, "retry with\nimproved\nprompts",
        ha="right", va="center", fontsize=7.5,
        color=C["loop"], fontweight="bold", rotation=90)


# ══════════════════════════════════════════════════════════════════════════════
# Phase 4 — Output & Evaluation
#   Column x ≈ 17.80
# ══════════════════════════════════════════════════════════════════════════════
P4X = 17.80

# Dialogue .md output
box(ax, P4X, 3.58, 3.30, 0.95, C["output"],
    "Dialogue .md Output", fontsize=9.5, bold=True,
    subtext="Transcript · scores · attempts\nprocessing_time · turn count")

arrow(ax, P4X, 4.06, P4X, 5.20, color=C["output"])

# Evaluation scores summary
box(ax, P4X, 5.52, 3.30, 0.82, C["output"],
    "Per-Dialogue Scores", fontsize=9,
    subtext="judge_score · naturalness\nprofile_compliance · RAGAS faithfulness")

arrow(ax, P4X, 5.93, P4X, 6.90, color=C["output"])

# Global stats
box(ax, P4X, 7.22, 3.30, 0.82, C["output"],
    "Aggregate Statistics", fontsize=9, bold=True,
    subtext="Realism rate · attempt distribution\nmean scores · processing times")

arrow(ax, P4X, 7.63, P4X, 8.50, color=C["output"])

# Paper figures
box(ax, P4X, 8.82, 3.30, 0.82, C["output"],
    "Research Paper Figures", fontsize=9,
    subtext="analysis/figures/ · 8 PDFs\nLaTeX summary table")

# Arrow from YES decision to output
# already drawn above to x=15.65 at y=3.58 and y=2.20

# Connector from 15.65 up to output box
ax.plot([15.65, 15.65], [2.20, 3.58], color="#2E7D32", lw=1.8, zorder=4)
ax.annotate("", xy=(P4X - 1.65, 3.58), xytext=(15.65, 3.58),
            arrowprops=dict(arrowstyle="-|>", color="#2E7D32", lw=1.8), zorder=4)

# Failed path from "best kept"
ax.plot([15.65, 16.35], [2.20, 2.20], color=C["loop"], lw=1.4, zorder=4)
ax.plot([16.35, 16.35], [2.20, 3.10], color=C["loop"], lw=1.4, zorder=4)
ax.annotate("", xy=(P4X - 1.65, 3.10), xytext=(16.35, 3.10),
            arrowprops=dict(arrowstyle="-|>", color=C["loop"], lw=1.4), zorder=4)


# ══════════════════════════════════════════════════════════════════════════════
# Title & legend
# ══════════════════════════════════════════════════════════════════════════════
ax.text(FIG_W / 2, FIG_H - 0.28,
        "MedDial Framework: End-to-End Pipeline for Synthetic Medical Dialogue Generation",
        ha="center", va="top", fontsize=14, fontweight="bold",
        color=C["text_dark"], zorder=10)

legend_items = [
    (C["data"],    "Data / Storage"),
    (C["process"], "Processing Step"),
    (C["agent"],   "LLM Agent (GPT-4.1)"),
    (C["profile"], "Profile Type"),
    (C["judge"],   "Evaluation / Judge"),
    (C["output"],  "Output / Results"),
    (C["loop"],    "Feedback / Retry Loop"),
]
handles = [mpatches.Patch(color=c, label=l) for c, l in legend_items]
ax.legend(handles=handles, loc="lower center",
          bbox_to_anchor=(0.5, -0.002),
          ncol=len(legend_items), fontsize=8.5,
          frameon=True, framealpha=0.9,
          edgecolor="#BDBDBD", handlelength=1.4, handleheight=0.9)


# ══════════════════════════════════════════════════════════════════════════════
# Save
# ══════════════════════════════════════════════════════════════════════════════
out_pdf = OUT / "framework_diagram.pdf"
out_png = OUT / "framework_diagram.png"
plt.savefig(out_pdf)
plt.savefig(out_png, dpi=300)
print(f"Saved:\n  {out_pdf}\n  {out_png}")
plt.close()
