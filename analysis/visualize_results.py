"""
visualize_results.py
====================
Parses all dialogue .md files in output_dialogue_framework/, computes statistics,
and produces publication-quality figures + a LaTeX summary table.

Outputs are written to:  analysis/figures/
"""

import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats as scipy_stats

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DIALOGUE_DIR = ROOT / "output_dialogue_framework"
FIG_DIR = Path(__file__).resolve().parent / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# ── Style ──────────────────────────────────────────────────────────────────────
PROFILE_ORDER = ["FULL", "NO_DIAGNOSIS", "NO_DIAGNOSIS_NO_TREATMENT"]
PROFILE_LABELS = {
    "FULL": "Full",
    "NO_DIAGNOSIS": "No Diagnosis",
    "NO_DIAGNOSIS_NO_TREATMENT": "No Diag. + No Treat.",
}
PALETTE = {"FULL": "#2196F3", "NO_DIAGNOSIS": "#FF9800", "NO_DIAGNOSIS_NO_TREATMENT": "#4CAF50"}
COLORS = [PALETTE[p] for p in PROFILE_ORDER]

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.1,
})


# ── Parser ─────────────────────────────────────────────────────────────────────

def _float(text, pattern, default=np.nan):
    m = re.search(pattern, text)
    return float(m.group(1)) if m else default

def _int(text, pattern, default=np.nan):
    m = re.search(pattern, text)
    return int(m.group(1)) if m else default

def _bool(text, pattern):
    m = re.search(pattern, text)
    if not m:
        return np.nan
    return m.group(1).strip().lower() == "true"


def parse_file(path: Path) -> dict:
    t = path.read_text(encoding="utf-8")

    profile_type_match = re.search(r"\*\*Profile Type\*\*:\s*(\S+)", t)
    profile_type = profile_type_match.group(1) if profile_type_match else "UNKNOWN"

    # Normalise the profile-compliance row label (it varies by type)
    naturalness = _float(t, r"\|\s*Naturalness\s*\|\s*([\d.]+)\s*\|")
    compliance_m = re.search(
        r"\|\s*Profile Compliance[^|]*\|\s*([\d.]+)\s*\|", t
    )
    compliance = float(compliance_m.group(1)) if compliance_m else np.nan
    faithfulness = _float(t, r"\|\s*RAGAS Faithfulness\s*\|\s*([\d.]+)\s*\|")

    return {
        "file": path.name,
        "profile_type": profile_type,
        "success": _bool(t, r"\*\*Success\*\*:\s*(True|False)"),
        "is_realistic": _bool(t, r"\*\*Is Realistic\*\*:\s*(True|False)"),
        "total_attempts": _int(t, r"\*\*Total Attempts\*\*:\s*(\d+)"),
        "best_attempt": _int(t, r"\*\*Best Attempt\*\*:\s*(\d+)"),
        "judge_score": _float(t, r"\*\*Score\*\*:\s*([\d.]+)"),
        "naturalness": naturalness,
        "profile_compliance": compliance,
        "ragas_faithfulness": faithfulness,
        "turn_count": _int(t, r"\*\*Turn Count\*\*:\s*(\d+)"),
        "word_count": _int(t, r"\*\*Word Count\*\*:\s*(\d+)"),
        "doctor_turns": _int(t, r"\*\*Doctor Turns\*\*:\s*(\d+)"),
        "patient_turns": _int(t, r"\*\*Patient Turns\*\*:\s*(\d+)"),
        "processing_time": _float(t, r"\*\*Processing Time\*\*:\s*([\d.]+)s"),
    }


def load_data() -> pd.DataFrame:
    records = [parse_file(p) for p in sorted(DIALOGUE_DIR.glob("dialogue_*.md"))]
    df = pd.DataFrame(records)
    df["profile_type"] = pd.Categorical(df["profile_type"], categories=PROFILE_ORDER, ordered=True)
    df["profile_label"] = df["profile_type"].map(PROFILE_LABELS)
    return df


# ── Figure helpers ─────────────────────────────────────────────────────────────

def savefig(name: str):
    path = FIG_DIR / name
    plt.savefig(path)
    print(f"  Saved {path.relative_to(ROOT)}")
    plt.close()


# ── Figure 1: Overall judge-score distributions by profile type ────────────────

def fig_score_distributions(df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    data = [df.loc[df["profile_type"] == pt, "judge_score"].dropna().values
            for pt in PROFILE_ORDER]
    labels = [PROFILE_LABELS[p] for p in PROFILE_ORDER]

    parts = ax.violinplot(data, positions=[1, 2, 3], widths=0.6,
                          showmedians=False, showextrema=False)
    for pc, col in zip(parts["bodies"], COLORS):
        pc.set_facecolor(col)
        pc.set_alpha(0.55)

    bp = ax.boxplot(data, positions=[1, 2, 3], widths=0.18,
                    patch_artist=True, notch=False,
                    medianprops=dict(color="black", linewidth=2),
                    whiskerprops=dict(linewidth=1.2),
                    capprops=dict(linewidth=1.2),
                    flierprops=dict(marker="o", markersize=3, alpha=0.5))
    for patch, col in zip(bp["boxes"], COLORS):
        patch.set_facecolor(col)
        patch.set_alpha(0.85)

    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(labels)
    ax.set_ylabel("Judge Score")
    ax.set_title("Judge Score Distribution by Profile Type")
    ax.set_ylim(0, 1.05)
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.2f"))
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    # Annotate medians
    for i, d in enumerate(data, 1):
        if len(d):
            med = np.median(d)
            ax.text(i + 0.13, med, f"{med:.3f}", va="center", fontsize=8.5, color="black")

    savefig("fig1_score_distributions.pdf")


# ── Figure 2: Sub-score comparison across profile types ───────────────────────

def fig_subscores(df: pd.DataFrame):
    sub_metrics = ["naturalness", "profile_compliance", "ragas_faithfulness"]
    sub_labels = ["Naturalness", "Profile\nCompliance", "RAGAS\nFaithfulness"]

    fig, axes = plt.subplots(1, 3, figsize=(12, 4.5), sharey=True)
    fig.suptitle("Sub-Score Distributions by Profile Type", y=1.01)

    for ax, metric, label in zip(axes, sub_metrics, sub_labels):
        data = [df.loc[df["profile_type"] == pt, metric].dropna().values
                for pt in PROFILE_ORDER]
        bp = ax.boxplot(data, patch_artist=True, notch=False,
                        medianprops=dict(color="black", linewidth=2),
                        whiskerprops=dict(linewidth=1.2),
                        capprops=dict(linewidth=1.2),
                        flierprops=dict(marker="o", markersize=3, alpha=0.5))
        for patch, col in zip(bp["boxes"], COLORS):
            patch.set_facecolor(col)
            patch.set_alpha(0.85)
        ax.set_xticks([1, 2, 3])
        ax.set_xticklabels([PROFILE_LABELS[p] for p in PROFILE_ORDER],
                           rotation=15, ha="right")
        ax.set_title(label)
        ax.set_ylim(-0.05, 1.08)
        ax.grid(axis="y", linestyle="--", alpha=0.4)

    axes[0].set_ylabel("Score")
    legend_patches = [mpatches.Patch(color=PALETTE[p], label=PROFILE_LABELS[p])
                      for p in PROFILE_ORDER]
    fig.legend(handles=legend_patches, loc="lower center", ncol=3,
               bbox_to_anchor=(0.5, -0.08), frameon=False)
    savefig("fig2_subscores.pdf")


# ── Figure 3: Realism rate and attempts ───────────────────────────────────────

def fig_realism_and_attempts(df: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    # 3a: Realism rate by profile type
    ax = axes[0]
    rates = df.groupby("profile_type", observed=True)["is_realistic"].mean() * 100
    bars = ax.bar([PROFILE_LABELS[p] for p in PROFILE_ORDER],
                  [rates.get(p, 0) for p in PROFILE_ORDER],
                  color=COLORS, edgecolor="white", linewidth=0.8, width=0.55)
    for bar, rate in zip(bars, [rates.get(p, 0) for p in PROFILE_ORDER]):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                f"{rate:.1f}%", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_ylim(0, 112)
    ax.set_ylabel("Realism Rate (%)")
    ax.set_title("(a) Realism Rate by Profile Type")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.tick_params(axis="x")

    # 3b: Attempts distribution
    ax = axes[1]
    attempt_counts = df["total_attempts"].value_counts().sort_index()
    bars2 = ax.bar(attempt_counts.index.astype(str),
                   attempt_counts.values,
                   color="#607D8B", edgecolor="white", linewidth=0.8, width=0.5)
    for bar, count in zip(bars2, attempt_counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1,
                str(count), ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_xlabel("Number of Generation Attempts")
    ax.set_ylabel("Number of Dialogues")
    ax.set_title("(b) Generation Attempts Distribution")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    fig.tight_layout()
    savefig("fig3_realism_attempts.pdf")


# ── Figure 4: Dialogue length statistics ──────────────────────────────────────

def fig_dialogue_length(df: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    fig.suptitle("Dialogue Length by Profile Type")

    for ax, metric, ylabel, title_letter in zip(
        axes,
        ["word_count", "turn_count"],
        ["Word Count", "Turn Count"],
        ["(a)", "(b)"],
    ):
        data = [df.loc[df["profile_type"] == pt, metric].dropna().values
                for pt in PROFILE_ORDER]
        parts = ax.violinplot(data, positions=[1, 2, 3], widths=0.65,
                              showmedians=False, showextrema=False)
        for pc, col in zip(parts["bodies"], COLORS):
            pc.set_facecolor(col)
            pc.set_alpha(0.5)
        bp = ax.boxplot(data, positions=[1, 2, 3], widths=0.18,
                        patch_artist=True, notch=False,
                        medianprops=dict(color="black", linewidth=2),
                        whiskerprops=dict(linewidth=1.2),
                        capprops=dict(linewidth=1.2),
                        flierprops=dict(marker="o", markersize=3, alpha=0.45))
        for patch, col in zip(bp["boxes"], COLORS):
            patch.set_facecolor(col)
            patch.set_alpha(0.85)
        ax.set_xticks([1, 2, 3])
        ax.set_xticklabels([PROFILE_LABELS[p] for p in PROFILE_ORDER],
                           rotation=12, ha="right")
        ax.set_ylabel(ylabel)
        ax.set_title(f"{title_letter} {ylabel}")
        ax.grid(axis="y", linestyle="--", alpha=0.4)

    savefig("fig4_dialogue_length.pdf")


# ── Figure 5: Correlation heatmap ─────────────────────────────────────────────

def fig_correlation(df: pd.DataFrame):
    cols = {
        "judge_score": "Judge Score",
        "naturalness": "Naturalness",
        "profile_compliance": "Profile Compliance",
        "ragas_faithfulness": "RAGAS Faithfulness",
        "word_count": "Word Count",
        "turn_count": "Turn Count",
        "processing_time": "Processing Time",
    }
    sub = df[list(cols.keys())].rename(columns=cols)
    corr = sub.corr(method="pearson")

    fig, ax = plt.subplots(figsize=(8, 6.5))
    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
    sns.heatmap(
        corr, ax=ax, annot=True, fmt=".2f", cmap="RdYlGn",
        vmin=-1, vmax=1, linewidths=0.5,
        annot_kws={"size": 9},
        cbar_kws={"shrink": 0.8},
    )
    ax.set_title("Pearson Correlation Matrix")
    fig.tight_layout()
    savefig("fig5_correlation.pdf")


# ── Figure 6: Radar chart — mean sub-scores per profile type ──────────────────

def fig_radar(df: pd.DataFrame):
    categories = ["Naturalness", "Profile\nCompliance", "RAGAS\nFaithfulness"]
    n = len(categories)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]   # close polygon

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw={"polar": True})

    for pt, col in zip(PROFILE_ORDER, COLORS):
        sub = df[df["profile_type"] == pt]
        values = [
            sub["naturalness"].mean(),
            sub["profile_compliance"].mean(),
            sub["ragas_faithfulness"].mean(),
        ]
        values += values[:1]
        ax.plot(angles, values, "o-", linewidth=2, color=col, label=PROFILE_LABELS[pt])
        ax.fill(angles, values, alpha=0.12, color=col)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, size=11)
    ax.set_ylim(0, 1.0)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], size=8)
    ax.set_title("Mean Sub-Scores per Profile Type", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1))
    savefig("fig6_radar.pdf")


# ── Figure 7: Processing time distribution ────────────────────────────────────

def fig_processing_time(df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(8, 4))
    for pt, col in zip(PROFILE_ORDER, COLORS):
        vals = df.loc[df["profile_type"] == pt, "processing_time"].dropna()
        ax.hist(vals, bins=25, alpha=0.55, color=col,
                label=PROFILE_LABELS[pt], edgecolor="white", linewidth=0.3)
    ax.set_xlabel("Processing Time (s)")
    ax.set_ylabel("Count")
    ax.set_title("Processing Time Distribution by Profile Type")
    ax.legend(frameon=False)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    savefig("fig7_processing_time.pdf")


# ── Figure 8: Score by is_realistic flag ──────────────────────────────────────

def fig_realistic_vs_unrealistic(df: pd.DataFrame):
    """Scatter of naturalness vs. profile compliance, coloured by realism."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    for ax, (xc, yc, xl, yl) in zip(axes, [
        ("naturalness", "profile_compliance", "Naturalness", "Profile Compliance"),
        ("naturalness", "ragas_faithfulness", "Naturalness", "RAGAS Faithfulness"),
    ]):
        for is_r, col, lbl in [(True, "#2196F3", "Realistic"), (False, "#E53935", "Unrealistic")]:
            sub = df[df["is_realistic"] == is_r]
            ax.scatter(sub[xc], sub[yc], c=col, alpha=0.4, s=28,
                       label=lbl, edgecolors="none")
        ax.set_xlabel(xl)
        ax.set_ylabel(yl)
        ax.set_xlim(-0.05, 1.08)
        ax.set_ylim(-0.05, 1.08)
        ax.grid(linestyle="--", alpha=0.3)

    axes[0].set_title("(a) Naturalness vs. Profile Compliance")
    axes[1].set_title("(b) Naturalness vs. RAGAS Faithfulness")
    axes[0].legend(frameon=False)
    fig.suptitle("Sub-Score Scatter: Realistic vs. Unrealistic Dialogues")
    fig.tight_layout()
    savefig("fig8_realistic_scatter.pdf")


# ── Summary statistics table (console + LaTeX) ────────────────────────────────

METRICS = {
    "judge_score": "Judge Score",
    "naturalness": "Naturalness",
    "profile_compliance": "Profile Compliance",
    "ragas_faithfulness": "RAGAS Faithfulness",
    "word_count": "Word Count",
    "turn_count": "Turn Count",
    "processing_time": "Processing Time (s)",
}


def build_summary_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for pt in PROFILE_ORDER + ["ALL"]:
        sub = df if pt == "ALL" else df[df["profile_type"] == pt]
        label = "Overall" if pt == "ALL" else PROFILE_LABELS[pt]
        n = len(sub)
        realistic = sub["is_realistic"].sum()
        row = {
            "Profile": label,
            "N": n,
            "Realistic (%)": f"{realistic} ({100*realistic/n:.1f}%)" if n else "—",
        }
        for col, name in METRICS.items():
            vals = sub[col].dropna()
            if len(vals):
                row[name] = f"{vals.mean():.3f} ± {vals.std():.3f}"
            else:
                row[name] = "—"
        rows.append(row)
    return pd.DataFrame(rows).set_index("Profile")


def print_summary(df: pd.DataFrame):
    tbl = build_summary_table(df)
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS  (mean ± std)")
    print("=" * 80)
    with pd.option_context("display.max_columns", None, "display.width", 200,
                           "display.max_colwidth", 30):
        print(tbl.to_string())

    # LaTeX table
    latex_path = FIG_DIR / "summary_table.tex"
    tbl.reset_index(inplace=False).to_latex(
        latex_path, index=True, escape=True,
        caption="Summary statistics (mean ± std) per profile type.",
        label="tab:summary",
    )
    print(f"\n  LaTeX table → {latex_path.relative_to(ROOT)}")


def print_significance_tests(df: pd.DataFrame):
    """Kruskal–Wallis H-test across the three profile types for each metric."""
    print("\n" + "=" * 80)
    print("KRUSKAL–WALLIS H-TESTS (profile-type differences)")
    print("=" * 80)
    for col, name in METRICS.items():
        groups = [df.loc[df["profile_type"] == pt, col].dropna().values
                  for pt in PROFILE_ORDER]
        if all(len(g) > 1 for g in groups):
            h, p = scipy_stats.kruskal(*groups)
            sig = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else "ns"))
            print(f"  {name:<28}  H={h:7.3f}  p={p:.4f}  {sig}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print(f"Loading dialogue files from {DIALOGUE_DIR} …")
    df = load_data()
    print(f"  Loaded {len(df)} files  "
          f"({df['is_realistic'].sum()} realistic, "
          f"{(~df['is_realistic']).sum()} unrealistic)")

    print("\nGenerating figures …")
    fig_score_distributions(df)
    fig_subscores(df)
    fig_realism_and_attempts(df)
    fig_dialogue_length(df)
    fig_correlation(df)
    fig_radar(df)
    fig_processing_time(df)
    fig_realistic_vs_unrealistic(df)

    print_summary(df)
    print_significance_tests(df)
    print(f"\nAll figures saved to {FIG_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
