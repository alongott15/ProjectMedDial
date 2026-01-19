#!/usr/bin/env python3
"""
Generate comprehensive comparison report for STS score recalculation.

This script creates a detailed report comparing old vs new STS scores.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import statistics

def generate_comparison_report(results_file: str):
    """
    Generate comprehensive comparison report from recalculation results.
    """
    # Load results
    with open(results_file, 'r') as f:
        data = json.load(f)

    metadata = data['metadata']
    results = data['results']

    # Generate report
    report = []
    report.append("="*100)
    report.append("STS SCORE RECALCULATION - COMPREHENSIVE COMPARISON REPORT")
    report.append("="*100)
    report.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Data file: {results_file}")
    report.append(f"Timestamp: {metadata['timestamp']}")
    report.append(f"\n{'='*100}\n")

    # Executive Summary
    report.append("EXECUTIVE SUMMARY")
    report.append("="*100)
    report.append(f"\nTotal dialogues processed: {metadata['processed']}")
    report.append(f"Skipped (missing data): {metadata['skipped']}")
    report.append(f"Errors: {metadata['errors']}")

    if not results:
        report.append("\n⚠️  No results to analyze!")
        return '\n'.join(report)

    # Overall statistics
    old_scores = [r['old_sts'] for r in results]
    new_scores = [r['new_sts'] for r in results]
    differences = [r['difference'] for r in results]
    retentions = [r['information_retention'] for r in results]

    report.append(f"\n{'Old STS Scores':<30} Mean: {statistics.mean(old_scores):.4f}  "
                 f"Median: {statistics.median(old_scores):.4f}  "
                 f"StdDev: {statistics.stdev(old_scores):.4f}")
    report.append(f"{'  Range:':<30} [{min(old_scores):.4f}, {max(old_scores):.4f}]")

    report.append(f"\n{'New STS Scores':<30} Mean: {statistics.mean(new_scores):.4f}  "
                 f"Median: {statistics.median(new_scores):.4f}  "
                 f"StdDev: {statistics.stdev(new_scores):.4f}")
    report.append(f"{'  Range:':<30} [{min(new_scores):.4f}, {max(new_scores):.4f}]")

    report.append(f"\n{'Change in Scores':<30} Mean: {statistics.mean(differences):+.4f}  "
                 f"Median: {statistics.median(differences):+.4f}")
    report.append(f"{'  Range:':<30} [{min(differences):+.4f}, {max(differences):+.4f}]")

    report.append(f"\n{'Information Retention':<30} Mean: {statistics.mean(retentions):.4f}  "
                 f"Median: {statistics.median(retentions):.4f}")
    report.append(f"{'  Range:':<30} [{min(retentions):.4f}, {max(retentions):.4f}]")

    # Analysis by profile type
    report.append(f"\n{'='*100}\n")
    report.append("ANALYSIS BY PROFILE TYPE")
    report.append("="*100)

    by_type = defaultdict(list)
    for r in results:
        by_type[r['profile_type']].append(r)

    for ptype in sorted(by_type.keys()):
        type_results = by_type[ptype]
        report.append(f"\n{ptype} ({len(type_results)} dialogues)")
        report.append("-" * 100)

        old = [r['old_sts'] for r in type_results]
        new = [r['new_sts'] for r in type_results]
        diff = [r['difference'] for r in type_results]
        ret = [r['information_retention'] for r in type_results]

        report.append(f"  Old STS:     Mean={statistics.mean(old):.4f}  "
                     f"Median={statistics.median(old):.4f}  "
                     f"Range=[{min(old):.4f}, {max(old):.4f}]")
        report.append(f"  New STS:     Mean={statistics.mean(new):.4f}  "
                     f"Median={statistics.median(new):.4f}  "
                     f"Range=[{min(new):.4f}, {max(new):.4f}]")
        report.append(f"  Change:      Mean={statistics.mean(diff):+.4f}  "
                     f"Median={statistics.median(diff):+.4f}")
        report.append(f"  Retention:   Mean={statistics.mean(ret):.4f}  "
                     f"Coverage={statistics.mean(ret)*100:.1f}%")

        # Component analysis
        all_components = defaultdict(list)
        for r in type_results:
            for comp, scores in r['component_scores'].items():
                all_components[comp].append(scores['recall'])

        report.append(f"\n  Component Recall Scores:")
        for comp in ['symptoms', 'diagnosis', 'treatment', 'findings', 'history']:
            if comp in all_components:
                recalls = all_components[comp]
                report.append(f"    {comp:<15} Mean={statistics.mean(recalls):.3f}  "
                             f"Median={statistics.median(recalls):.3f}")

    # Score distributions
    report.append(f"\n{'='*100}\n")
    report.append("SCORE DISTRIBUTIONS")
    report.append("="*100)

    def create_histogram(scores, title, bins=10):
        """Create ASCII histogram."""
        min_score = 0.0
        max_score = 1.0
        bin_width = (max_score - min_score) / bins
        bin_counts = [0] * bins

        for score in scores:
            bin_idx = min(int((score - min_score) / bin_width), bins - 1)
            bin_counts[bin_idx] += 1

        max_count = max(bin_counts) if bin_counts else 1
        lines = [f"\n{title}"]
        lines.append("-" * 80)

        for i, count in enumerate(bin_counts):
            bin_start = min_score + i * bin_width
            bin_end = bin_start + bin_width
            bar_length = int((count / max_count) * 50) if max_count > 0 else 0
            bar = '█' * bar_length
            lines.append(f"  [{bin_start:.2f}-{bin_end:.2f}): {bar} {count}")

        return '\n'.join(lines)

    report.append(create_histogram(old_scores, "Old STS Score Distribution"))
    report.append(create_histogram(new_scores, "New STS Score Distribution"))

    # Quality tiers
    report.append(f"\n{'='*100}\n")
    report.append("QUALITY TIERS (New STS)")
    report.append("="*100)

    tiers = {
        'Excellent (0.70-1.00)': [r for r in results if r['new_sts'] >= 0.70],
        'Good (0.55-0.69)': [r for r in results if 0.55 <= r['new_sts'] < 0.70],
        'Moderate (0.40-0.54)': [r for r in results if 0.40 <= r['new_sts'] < 0.55],
        'Fair (0.25-0.39)': [r for r in results if 0.25 <= r['new_sts'] < 0.40],
        'Poor (<0.25)': [r for r in results if r['new_sts'] < 0.25]
    }

    for tier_name, tier_results in tiers.items():
        count = len(tier_results)
        percentage = (count / len(results) * 100) if results else 0
        report.append(f"\n{tier_name:<30} {count:>4} dialogues ({percentage:>5.1f}%)")

        if count > 0:
            # Show profile type breakdown
            type_counts = defaultdict(int)
            for r in tier_results:
                type_counts[r['profile_type']] += 1

            for ptype in sorted(type_counts.keys()):
                report.append(f"  {ptype:<25} {type_counts[ptype]:>4}")

    # Most common missing components
    report.append(f"\n{'='*100}\n")
    report.append("MISSING COMPONENTS ANALYSIS")
    report.append("="*100)

    missing_counts = defaultdict(int)
    for r in results:
        for missing in r['missing_components']:
            missing_counts[missing['component']] += 1

    report.append(f"\nMost Frequently Missing Components:")
    for comp, count in sorted(missing_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / len(results) * 100) if results else 0
        report.append(f"  {comp:<20} {count:>4} dialogues ({percentage:>5.1f}%)")

    # Examples of significant changes
    report.append(f"\n{'='*100}\n")
    report.append("EXAMPLES OF SIGNIFICANT CHANGES")
    report.append("="*100)

    # Largest decreases
    largest_decreases = sorted(results, key=lambda x: x['difference'])[:10]
    report.append(f"\nTop 10 Largest Decreases (Most Overestimated):")
    report.append(f"{'File':<60} {'Old':<8} {'New':<8} {'Change':<8} {'Type':<10}")
    report.append("-" * 100)
    for r in largest_decreases:
        report.append(f"{r['file']:<60} {r['old_sts']:<8.3f} {r['new_sts']:<8.3f} "
                     f"{r['difference']:<8.3f} {r['profile_type']:<10}")

    # Smallest decreases (most accurate originally)
    smallest_decreases = sorted(results, key=lambda x: x['difference'], reverse=True)[:10]
    report.append(f"\nTop 10 Smallest Decreases (Most Accurate Originally):")
    report.append(f"{'File':<60} {'Old':<8} {'New':<8} {'Change':<8} {'Type':<10}")
    report.append("-" * 100)
    for r in smallest_decreases:
        report.append(f"{r['file']:<60} {r['old_sts']:<8.3f} {r['new_sts']:<8.3f} "
                     f"{r['difference']:<8.3f} {r['profile_type']:<10}")

    # Best information retention
    best_retention = sorted(results, key=lambda x: x['information_retention'], reverse=True)[:10]
    report.append(f"\nTop 10 Best Information Retention:")
    report.append(f"{'File':<60} {'New STS':<8} {'Retention':<10} {'Type':<10}")
    report.append("-" * 100)
    for r in best_retention:
        report.append(f"{r['file']:<60} {r['new_sts']:<8.3f} "
                     f"{r['information_retention']:<10.3f} {r['profile_type']:<10}")

    # Worst information retention
    worst_retention = sorted(results, key=lambda x: x['information_retention'])[:10]
    report.append(f"\nTop 10 Worst Information Retention:")
    report.append(f"{'File':<60} {'New STS':<8} {'Retention':<10} {'Type':<10}")
    report.append("-" * 100)
    for r in worst_retention:
        report.append(f"{r['file']:<60} {r['new_sts']:<8.3f} "
                     f"{r['information_retention']:<10.3f} {r['profile_type']:<10}")

    # Key findings
    report.append(f"\n{'='*100}\n")
    report.append("KEY FINDINGS")
    report.append("="*100)

    report.append(f"\n1. MAGNITUDE OF OVERESTIMATION")
    report.append(f"   - Average decrease: {abs(statistics.mean(differences)):.3f} ({abs(statistics.mean(differences))*100:.1f} percentage points)")
    report.append(f"   - This confirms the original scores were artificially inflated")

    report.append(f"\n2. PROFILE TYPE COMPARISON")
    type_means = {ptype: statistics.mean([r['new_sts'] for r in by_type[ptype]])
                  for ptype in by_type.keys()}
    sorted_types = sorted(type_means.items(), key=lambda x: x[1], reverse=True)
    for ptype, mean in sorted_types:
        report.append(f"   - {ptype}: {mean:.3f}")

    report.append(f"\n3. INFORMATION RETENTION")
    avg_retention = statistics.mean(retentions)
    report.append(f"   - Average retention: {avg_retention:.3f} ({avg_retention*100:.1f}% of expected facts captured)")
    poor_retention = len([r for r in results if r['information_retention'] < 0.3])
    report.append(f"   - Dialogues with <30% retention: {poor_retention} ({poor_retention/len(results)*100:.1f}%)")

    report.append(f"\n4. MISSING COMPONENTS")
    report.append(f"   - Most commonly missing: {max(missing_counts.items(), key=lambda x: x[1])[0]}")

    report.append(f"\n{'='*100}\n")
    report.append("END OF REPORT")
    report.append("="*100)

    return '\n'.join(report)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        # Find most recent results file
        output_dir = Path('output_dialogue_framework')
        results_files = sorted(output_dir.glob('sts_recalculation_results_*.json'))

        if not results_files:
            print("Error: No results files found!")
            print("Usage: python generate_comparison_report.py <results_file.json>")
            sys.exit(1)

        results_file = str(results_files[-1])
        print(f"Using most recent results file: {results_file}")
    else:
        results_file = sys.argv[1]

    # Generate report
    print(f"\nGenerating comparison report from: {results_file}\n")
    report = generate_comparison_report(results_file)

    # Print to console
    print(report)

    # Save to file
    report_file = results_file.replace('.json', '_REPORT.txt')
    with open(report_file, 'w') as f:
        f.write(report)

    print(f"\n✅ Report saved to: {report_file}")
