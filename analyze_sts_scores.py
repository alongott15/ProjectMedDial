#!/usr/bin/env python3
"""
Script to analyze and summarize STS scores from the dialogue generation.
"""

import json
import statistics
from pathlib import Path
from typing import Dict, List, Any


def load_json(filepath: Path) -> Dict:
    """Load JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)


def percentile(data: List[float], p: float) -> float:
    """Calculate percentile of a list."""
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100
    f = int(k)
    c = k - f
    if f + 1 < len(sorted_data):
        return sorted_data[f] + c * (sorted_data[f + 1] - sorted_data[f])
    return sorted_data[f]


def calculate_stats(scores: List[float]) -> Dict[str, float]:
    """Calculate statistics for a list of scores."""
    if not scores:
        return {}

    return {
        'count': len(scores),
        'mean': statistics.mean(scores),
        'median': statistics.median(scores),
        'std': statistics.stdev(scores) if len(scores) > 1 else 0.0,
        'min': min(scores),
        'max': max(scores),
        'q25': percentile(scores, 25),
        'q75': percentile(scores, 75)
    }


def analyze_sts_scores():
    """Analyze STS scores from the project data."""

    output_dir = Path('/home/user/ProjectMedDial/output_dialogue_framework')

    print("=" * 80)
    print("STS SCORES SUMMARY - ProjectMedDial")
    print("=" * 80)
    print()

    # Load per-profile stats to get individual STS scores
    per_profile_stats = load_json(output_dir / 'per_profile_stats.json')

    # Extract STS scores by profile type
    sts_by_type = {}

    all_sts_scores = []
    realistic_dialogues = 0
    non_realistic_dialogues = 0

    for profile in per_profile_stats:
        profile_type = profile.get('profile_type', 'UNKNOWN')
        sts_score = profile.get('sts_score')
        is_realistic = profile.get('is_realistic', False)

        if is_realistic:
            realistic_dialogues += 1
        else:
            non_realistic_dialogues += 1

        # Only process realistic dialogues with valid STS scores
        if sts_score is not None and is_realistic:
            all_sts_scores.append(sts_score)
            if profile_type not in sts_by_type:
                sts_by_type[profile_type] = []
            sts_by_type[profile_type].append(sts_score)

    # Load global stats
    global_stats = load_json(output_dir / 'global_stats.json')

    # Load regeneration report if it exists
    regen_report_path = output_dir / 'sts_regeneration_report.json'
    regen_report = None
    if regen_report_path.exists():
        regen_report = load_json(regen_report_path)

    # Print overall statistics
    print("📊 OVERALL STATISTICS")
    print("-" * 80)
    print(f"Total Profiles: {global_stats['total_profiles']}")
    print(f"Total Dialogues Attempted: {global_stats['total_dialogues_attempted']}")
    print(f"Successful Dialogues: {global_stats['successful_dialogues']}")
    print(f"Failed Dialogues: {global_stats['failed_dialogues']}")
    print(f"Realistic Dialogues (with STS): {realistic_dialogues}")
    print(f"Non-Realistic Dialogues (no STS): {non_realistic_dialogues}")
    print()

    # Print STS statistics for all realistic dialogues
    print("📈 STS SCORES - ALL REALISTIC DIALOGUES")
    print("-" * 80)
    all_stats = calculate_stats(all_sts_scores)
    print(f"Count: {all_stats['count']}")
    print(f"Mean: {all_stats['mean']:.4f}")
    print(f"Median: {all_stats['median']:.4f}")
    print(f"Std Dev: {all_stats['std']:.4f}")
    print(f"Min: {all_stats['min']:.4f}")
    print(f"Max: {all_stats['max']:.4f}")
    print(f"25th Percentile: {all_stats['q25']:.4f}")
    print(f"75th Percentile: {all_stats['q75']:.4f}")
    print()

    # Print STS statistics by profile type
    print("📊 STS SCORES BY PROFILE TYPE")
    print("-" * 80)
    for profile_type, scores in sts_by_type.items():
        if scores:
            stats = calculate_stats(scores)
            print(f"\n{profile_type}:")
            print(f"  Count: {stats['count']}")
            print(f"  Mean: {stats['mean']:.4f}")
            print(f"  Median: {stats['median']:.4f}")
            print(f"  Std Dev: {stats['std']:.4f}")
            print(f"  Min: {stats['min']:.4f}")
            print(f"  Max: {stats['max']:.4f}")
            print(f"  Range: [{stats['q25']:.4f} - {stats['q75']:.4f}] (IQR)")
    print()

    # Print regeneration report summary if available
    if regen_report:
        print("🔄 STS REGENERATION REPORT")
        print("-" * 80)
        print(f"Total Processed: {regen_report['total']}")
        print(f"Successfully Processed: {regen_report['processed']}")
        print(f"Failed: {regen_report['failed']}")
        print(f"STS Improved: {regen_report['sts_improved']}")
        print(f"STS Decreased: {regen_report['sts_decreased']}")
        print(f"STS Unchanged: {regen_report['sts_unchanged']}")
        print()

        # Calculate old vs new score statistics
        if 'old_sts_scores' in regen_report and 'new_sts_scores' in regen_report:
            old_stats = calculate_stats(regen_report['old_sts_scores'])
            new_stats = calculate_stats(regen_report['new_sts_scores'])

            print("Old STS Scores:")
            print(f"  Mean: {old_stats['mean']:.4f}")
            print(f"  Median: {old_stats['median']:.4f}")
            print(f"  Range: [{old_stats['min']:.4f} - {old_stats['max']:.4f}]")
            print()
            print("New STS Scores:")
            print(f"  Mean: {new_stats['mean']:.4f}")
            print(f"  Median: {new_stats['median']:.4f}")
            print(f"  Range: [{new_stats['min']:.4f} - {new_stats['max']:.4f}]")
            print()
            print(f"Mean Change: {new_stats['mean'] - old_stats['mean']:+.4f}")
            print(f"Median Change: {new_stats['median'] - old_stats['median']:+.4f}")
            print()

        # Show top improvements
        if 'improvements' in regen_report and regen_report['improvements']:
            print("Top 10 Improvements:")
            sorted_improvements = sorted(
                regen_report['improvements'],
                key=lambda x: x['improvement'],
                reverse=True
            )[:10]
            for i, imp in enumerate(sorted_improvements, 1):
                print(f"  {i}. {imp['file']}: {imp['old']:.4f} → {imp['new']:.4f} "
                      f"({imp['improvement']:+.4f})")
            print()

        # Show top decreases
        if 'improvements' in regen_report:
            all_changes = regen_report['improvements']
            sorted_decreases = sorted(all_changes, key=lambda x: x['improvement'])[:10]
            print("Top 10 Decreases:")
            for i, dec in enumerate(sorted_decreases, 1):
                print(f"  {i}. {dec['file']}: {dec['old']:.4f} → {dec['new']:.4f} "
                      f"({dec['improvement']:+.4f})")

    print()
    print("=" * 80)
    print("Analysis complete!")
    print("=" * 80)


if __name__ == "__main__":
    analyze_sts_scores()
