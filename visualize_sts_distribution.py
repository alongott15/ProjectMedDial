#!/usr/bin/env python3
"""
Script to visualize STS score distribution.
"""

import json
from pathlib import Path
from collections import Counter


def create_histogram(scores, bins=20):
    """Create a text-based histogram."""
    min_score = min(scores)
    max_score = max(scores)
    bin_width = (max_score - min_score) / bins

    # Create bins
    bin_counts = [0] * bins
    for score in scores:
        bin_idx = min(int((score - min_score) / bin_width), bins - 1)
        bin_counts[bin_idx] += 1

    # Find max count for scaling
    max_count = max(bin_counts)
    scale = 50 / max_count if max_count > 0 else 1

    print("\nSTS Score Distribution:")
    print("=" * 70)

    for i, count in enumerate(bin_counts):
        bin_start = min_score + i * bin_width
        bin_end = bin_start + bin_width
        bar_length = int(count * scale)
        bar = "█" * bar_length
        print(f"{bin_start:.3f}-{bin_end:.3f} | {bar} {count}")

    print("=" * 70)


def main():
    output_dir = Path('/home/user/ProjectMedDial/output_dialogue_framework')

    # Load per-profile stats
    with open(output_dir / 'per_profile_stats.json', 'r') as f:
        per_profile_stats = json.load(f)

    # Extract all STS scores
    all_scores = []
    by_type = {}

    for profile in per_profile_stats:
        sts_score = profile.get('sts_score')
        profile_type = profile.get('profile_type', 'UNKNOWN')
        is_realistic = profile.get('is_realistic', False)

        if sts_score is not None and is_realistic:
            all_scores.append(sts_score)
            if profile_type not in by_type:
                by_type[profile_type] = []
            by_type[profile_type].append(sts_score)

    # Overall histogram
    create_histogram(all_scores, bins=20)

    # Score ranges
    print("\nScore Range Breakdown:")
    print("=" * 70)
    ranges = [
        (0.90, 0.91, "0.90-0.91"),
        (0.91, 0.92, "0.91-0.92"),
        (0.92, 0.93, "0.92-0.93"),
        (0.93, 0.94, "0.93-0.94"),
        (0.94, 0.95, "0.94-0.95"),
        (0.95, 0.96, "0.95-0.96"),
        (0.96, 0.97, "0.96-0.97"),
        (0.97, 0.98, "0.97-0.98"),
        (0.98, 0.99, "0.98-0.99"),
    ]

    for low, high, label in ranges:
        count = sum(1 for s in all_scores if low <= s < high)
        pct = (count / len(all_scores)) * 100
        bar = "█" * int(pct)
        print(f"{label}: {count:4d} ({pct:5.1f}%) {bar}")

    print("=" * 70)

    # Comparison by profile type
    print("\nComparison by Profile Type:")
    print("=" * 70)
    for ptype in sorted(by_type.keys()):
        scores = by_type[ptype]
        avg = sum(scores) / len(scores)
        print(f"\n{ptype} (n={len(scores)}, mean={avg:.4f}):")
        create_histogram(scores, bins=15)


if __name__ == "__main__":
    main()
