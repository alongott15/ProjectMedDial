#!/usr/bin/env python3
"""
Recalculate STS scores for all dialogues using the improved method.

This script:
1. Loads all existing dialogue markdown files
2. Extracts EHR and dialogue summaries
3. Recalculates STS using ImprovedSTSEvaluatorAgent
4. Generates comparison report (old vs new scores)
5. Saves detailed results for analysis
"""

import os
import sys
import json
import re
import logging
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from Agents.KeywordBasedSTSEvaluator import KeywordBasedSTSEvaluator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_summaries_and_metadata(file_path: Path) -> dict:
    """Extract summaries, current STS, and metadata from dialogue markdown file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract profile type
    profile_type_match = re.search(r'\*\*Profile Type\*\*:\s*(\S+)', content)
    profile_type = profile_type_match.group(1) if profile_type_match else 'FULL'

    # Extract EHR Summary
    ehr_match = re.search(r'## EHR Summary\n\n(.*?)\n\n##', content, re.DOTALL)
    ehr_summary = ehr_match.group(1).strip() if ehr_match else None

    # Extract Dialogue Summary
    dialogue_match = re.search(r'## Dialogue Summary\n\n(.*?)\n\n##', content, re.DOTALL)
    dialogue_summary = dialogue_match.group(1).strip() if dialogue_match else None

    # Extract current STS score
    sts_match = re.search(r'\*\*STS Score\*\*:\s*([\d.]+)', content)
    current_sts = float(sts_match.group(1)) if sts_match else None

    # Extract profile ID
    profile_id_match = re.search(r'dialogue_(\d+_\d+)(?:_\w+)?\.md', file_path.name)
    profile_id = profile_id_match.group(1) if profile_id_match else None

    # Extract judge score
    judge_match = re.search(r'\*\*Score\*\*:\s*([\d.]+)', content)
    judge_score = float(judge_match.group(1)) if judge_match else None

    # Extract is_realistic
    realistic_match = re.search(r'\*\*Is Realistic\*\*:\s*(\w+)', content)
    is_realistic = realistic_match.group(1) == 'True' if realistic_match else None

    return {
        'file_path': file_path,
        'profile_id': profile_id,
        'profile_type': profile_type,
        'ehr_summary': ehr_summary,
        'dialogue_summary': dialogue_summary,
        'current_sts': current_sts,
        'judge_score': judge_score,
        'is_realistic': is_realistic
    }


def recalculate_all_sts_scores(output_dir: str = 'output_dialogue_framework',
                               sample_size: int = None):
    """
    Recalculate STS scores for all dialogues.

    Args:
        output_dir: Directory containing dialogue markdown files
        sample_size: If specified, only process this many files (for testing)
    """
    output_path = Path(output_dir)

    logger.info("="*80)
    logger.info("STS SCORE RECALCULATION")
    logger.info("="*80)
    logger.info(f"Output directory: {output_path}")
    logger.info(f"Timestamp: {datetime.now()}")

    # Initialize improved STS evaluator
    logger.info("\n" + "="*80)
    logger.info("Initializing Keyword-Based STS Evaluator...")
    logger.info("="*80)
    evaluator = KeywordBasedSTSEvaluator()

    # Find all dialogue markdown files
    dialogue_files = sorted(output_path.glob('dialogue_*.md'))
    total_files = len(dialogue_files)

    if sample_size:
        dialogue_files = dialogue_files[:sample_size]
        logger.info(f"SAMPLE MODE: Processing {sample_size} of {total_files} files")
    else:
        logger.info(f"FULL MODE: Processing all {total_files} files")

    # Track results
    results = []
    skipped = []
    errors = []

    # Statistics by profile type
    stats_by_type = defaultdict(lambda: {
        'count': 0,
        'old_scores': [],
        'new_scores': [],
        'improvements': [],
        'degradations': []
    })

    logger.info("\n" + "="*80)
    logger.info("Processing Dialogues...")
    logger.info("="*80)

    for i, file_path in enumerate(dialogue_files):
        if (i + 1) % 10 == 0 or i == 0:
            logger.info(f"\n[{i+1}/{len(dialogue_files)}] Processing: {file_path.name}")
        else:
            logger.info(f"[{i+1}/{len(dialogue_files)}] {file_path.name}")

        try:
            # Extract data from markdown file
            data = extract_summaries_and_metadata(file_path)

            # Skip if missing required data
            if not data['ehr_summary'] or not data['dialogue_summary']:
                logger.warning(f"  ⚠️  Skipping - missing summaries")
                skipped.append({
                    'file': file_path.name,
                    'reason': 'missing_summaries'
                })
                continue

            if data['current_sts'] is None:
                logger.warning(f"  ⚠️  Skipping - no current STS score")
                skipped.append({
                    'file': file_path.name,
                    'reason': 'no_current_sts'
                })
                continue

            # Recalculate STS using improved method
            new_sts_result = evaluator.compute_improved_sts(
                data['ehr_summary'],
                data['dialogue_summary'],
                data['profile_type']
            )

            old_score = data['current_sts']
            new_score = new_sts_result['overall_score']
            difference = new_score - old_score

            # Log results
            logger.info(f"  Profile Type: {data['profile_type']}")
            logger.info(f"  Old STS: {old_score:.4f}")
            logger.info(f"  New STS: {new_score:.4f}")
            logger.info(f"  Difference: {difference:+.4f}")
            logger.info(f"  Info Retention: {new_sts_result['information_retention']:.4f}")

            if len(new_sts_result['missing_components']) > 0:
                missing = ', '.join([c['component'] for c in new_sts_result['missing_components']])
                logger.info(f"  Missing: {missing}")

            # Store result
            result = {
                'file': file_path.name,
                'profile_id': data['profile_id'],
                'profile_type': data['profile_type'],
                'judge_score': data['judge_score'],
                'is_realistic': data['is_realistic'],
                'old_sts': old_score,
                'new_sts': new_score,
                'difference': difference,
                'lexical_similarity': new_sts_result.get('lexical_similarity', new_sts_result.get('original_sts', 0)),
                'profile_aware_score': new_sts_result['profile_aware_score'],
                'information_retention': new_sts_result['information_retention'],
                'coverage_percentage': new_sts_result['coverage_percentage'],
                'total_expected_facts': new_sts_result['total_expected_facts'],
                'total_captured_facts': new_sts_result['total_captured_facts'],
                'missing_components': new_sts_result['missing_components'],
                'component_scores': {
                    comp: {
                        'recall': new_sts_result['components'][comp]['recall'],
                        'ehr_facts': new_sts_result['components'][comp]['ehr_facts_count'],
                        'dialogue_facts': new_sts_result['components'][comp]['dialogue_facts_count'],
                        'overlap': new_sts_result['components'][comp]['overlap_count']
                    }
                    for comp in new_sts_result['components']
                }
            }
            results.append(result)

            # Update statistics by profile type
            ptype = data['profile_type']
            stats_by_type[ptype]['count'] += 1
            stats_by_type[ptype]['old_scores'].append(old_score)
            stats_by_type[ptype]['new_scores'].append(new_score)

            if difference > 0:
                stats_by_type[ptype]['improvements'].append(difference)
            elif difference < 0:
                stats_by_type[ptype]['degradations'].append(abs(difference))

        except Exception as e:
            logger.error(f"  ❌ Error processing {file_path.name}: {e}")
            errors.append({
                'file': file_path.name,
                'error': str(e)
            })
            continue

    # Generate summary statistics
    logger.info("\n" + "="*80)
    logger.info("SUMMARY STATISTICS")
    logger.info("="*80)

    if results:
        all_old = [r['old_sts'] for r in results]
        all_new = [r['new_sts'] for r in results]
        all_diff = [r['difference'] for r in results]
        all_retention = [r['information_retention'] for r in results]

        logger.info(f"\n📊 Overall Statistics ({len(results)} dialogues)")
        logger.info(f"  {'Old STS:':<25} Mean={sum(all_old)/len(all_old):.4f}, "
                   f"Min={min(all_old):.4f}, Max={max(all_old):.4f}")
        logger.info(f"  {'New STS:':<25} Mean={sum(all_new)/len(all_new):.4f}, "
                   f"Min={min(all_new):.4f}, Max={max(all_new):.4f}")
        logger.info(f"  {'Difference:':<25} Mean={sum(all_diff)/len(all_diff):+.4f}, "
                   f"Range=[{min(all_diff):+.4f}, {max(all_diff):+.4f}]")
        logger.info(f"  {'Information Retention:':<25} Mean={sum(all_retention)/len(all_retention):.4f}")

        # Statistics by profile type
        logger.info("\n📊 Statistics by Profile Type")
        for ptype in sorted(stats_by_type.keys()):
            stats = stats_by_type[ptype]
            if stats['count'] > 0:
                old_mean = sum(stats['old_scores']) / stats['count']
                new_mean = sum(stats['new_scores']) / stats['count']
                logger.info(f"\n  {ptype} ({stats['count']} dialogues):")
                logger.info(f"    Old STS: {old_mean:.4f}")
                logger.info(f"    New STS: {new_mean:.4f}")
                logger.info(f"    Change: {(new_mean - old_mean):+.4f}")

        # Identify significant changes
        large_decreases = [r for r in results if r['difference'] < -0.2]
        large_increases = [r for r in results if r['difference'] > 0.1]

        if large_decreases:
            logger.info(f"\n⚠️  {len(large_decreases)} dialogues with large decreases (>0.2):")
            for r in large_decreases[:5]:
                logger.info(f"    {r['file']}: {r['old_sts']:.3f} → {r['new_sts']:.3f}")

        if large_increases:
            logger.info(f"\n✅ {len(large_increases)} dialogues with increases (>0.1):")
            for r in large_increases[:5]:
                logger.info(f"    {r['file']}: {r['old_sts']:.3f} → {r['new_sts']:.3f}")

    if skipped:
        logger.info(f"\n⏭️  Skipped: {len(skipped)} files")

    if errors:
        logger.info(f"\n❌ Errors: {len(errors)} files")

    # Save detailed results to JSON
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_file = output_path / f'sts_recalculation_results_{timestamp}.json'

    output_data = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'total_files': total_files,
            'processed': len(results),
            'skipped': len(skipped),
            'errors': len(errors),
            'sample_mode': sample_size is not None,
            'sample_size': sample_size
        },
        'summary': {
            'overall': {
                'count': len(results),
                'old_sts_mean': sum(r['old_sts'] for r in results) / len(results) if results else 0,
                'new_sts_mean': sum(r['new_sts'] for r in results) / len(results) if results else 0,
                'mean_difference': sum(r['difference'] for r in results) / len(results) if results else 0,
                'mean_retention': sum(r['information_retention'] for r in results) / len(results) if results else 0
            },
            'by_profile_type': {
                ptype: {
                    'count': stats['count'],
                    'old_sts_mean': sum(stats['old_scores']) / stats['count'] if stats['count'] > 0 else 0,
                    'new_sts_mean': sum(stats['new_scores']) / stats['count'] if stats['count'] > 0 else 0
                }
                for ptype, stats in stats_by_type.items()
            }
        },
        'results': results,
        'skipped': skipped,
        'errors': errors
    }

    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)

    logger.info(f"\n💾 Detailed results saved to: {results_file}")

    return results, stats_by_type


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Recalculate STS scores for all dialogues')
    parser.add_argument('--sample', type=int, default=None,
                       help='Process only N files (for testing)')
    parser.add_argument('--output-dir', type=str, default='output_dialogue_framework',
                       help='Output directory containing dialogue files')

    args = parser.parse_args()

    if args.sample:
        logger.info(f"\n🧪 Running in SAMPLE MODE - processing {args.sample} files")
    else:
        logger.info(f"\n🚀 Running in FULL MODE - processing all files")

    results, stats = recalculate_all_sts_scores(
        output_dir=args.output_dir,
        sample_size=args.sample
    )

    logger.info("\n" + "="*80)
    logger.info("✅ RECALCULATION COMPLETE!")
    logger.info("="*80)
