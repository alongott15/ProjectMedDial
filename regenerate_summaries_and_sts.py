#!/usr/bin/env python3
"""
Regenerate summaries and STS scores for existing dialogues.

This script:
1. Loads existing dialogue markdown files
2. Regenerates EHR summaries using enhanced prompts
3. Regenerates dialogue summaries using enhanced prompts
4. Computes STS scores using medical-specific embedding models
5. Updates dialogue markdown files with new summaries and STS scores
6. Generates comparison report (old vs new STS scores)

Usage:
    python regenerate_summaries_and_sts.py
    python regenerate_summaries_and_sts.py --model medical
    python regenerate_summaries_and_sts.py --output-dir output_dialogue_framework
"""

import json
import logging
import os
import argparse
from pathlib import Path
import time

from Utils.csv_data_loader import CSVDataLoader
from Utils.markdown_gtmf import load_all_gtmfs_from_directory
from Agents.EHRSummarizerAgent import EHRSummarizerAgent
from Agents.DialogueSummarizerAgent import DialogueSummarizerAgent
from Agents.STSEvaluatorAgent import STSEvaluatorAgent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_dialogue_from_markdown(file_path: str) -> dict:
    """
    Load dialogue information from markdown file.

    Args:
        file_path: Path to dialogue markdown file

    Returns:
        Dict with dialogue info, or None if parsing fails
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract key information
        result = {
            'file_path': file_path,
            'content': content
        }

        # Parse profile ID from filename (e.g., dialogue_10145_135661_FULL.md)
        filename = Path(file_path).stem
        parts = filename.replace('dialogue_', '').split('_')

        if len(parts) >= 2:
            result['subject_id'] = int(parts[0])
            result['hadm_id'] = int(parts[1])
            result['profile_id'] = f"{parts[0]}_{parts[1]}"

        if len(parts) >= 3:
            result['profile_type'] = parts[2]
        else:
            result['profile_type'] = 'UNKNOWN'

        # Extract dialogue transcript
        transcript_start = content.find('## Dialogue Transcript')
        if transcript_start != -1:
            transcript_end = content.find('\n##', transcript_start + 1)
            if transcript_end == -1:
                transcript_end = len(content)

            transcript_section = content[transcript_start:transcript_end]
            # Remove the header
            transcript_lines = transcript_section.split('\n')[2:]  # Skip header and blank line
            result['transcript'] = '\n'.join(transcript_lines).strip()
        else:
            logger.warning(f"No transcript found in {file_path}")
            return None

        # Extract existing STS score if present
        sts_section = content.find('## STS Evaluation')
        if sts_section != -1:
            sts_line_start = content.find('- **STS Score**:', sts_section)
            if sts_line_start != -1:
                sts_line_end = content.find('\n', sts_line_start)
                sts_line = content[sts_line_start:sts_line_end]
                try:
                    old_sts = float(sts_line.split(':')[1].strip())
                    result['old_sts_score'] = old_sts
                except:
                    result['old_sts_score'] = None

        return result

    except Exception as e:
        logger.error(f"Error loading dialogue from {file_path}: {e}")
        return None


def update_markdown_with_summaries(file_path: str, ehr_summary: str, dialogue_summary: str, sts_result: dict):
    """
    Update dialogue markdown file with new summaries and STS score.

    Args:
        file_path: Path to dialogue markdown file
        ehr_summary: New EHR summary
        dialogue_summary: New dialogue summary
        sts_result: STS evaluation result dict
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find or create EHR Summary section
        ehr_section_start = content.find('## EHR Summary')
        if ehr_section_start != -1:
            # Replace existing
            ehr_section_end = content.find('\n##', ehr_section_start + 1)
            if ehr_section_end == -1:
                ehr_section_end = len(content)

            new_ehr_section = f"## EHR Summary\n\n{ehr_summary}\n\n"
            content = content[:ehr_section_start] + new_ehr_section + content[ehr_section_end:]
        else:
            # Add new section before STS Evaluation
            sts_section = content.find('## STS Evaluation')
            if sts_section != -1:
                new_ehr_section = f"\n## EHR Summary\n\n{ehr_summary}\n\n"
                content = content[:sts_section] + new_ehr_section + content[sts_section:]
            else:
                # Add at the end
                content += f"\n## EHR Summary\n\n{ehr_summary}\n\n"

        # Find or create Dialogue Summary section
        dialogue_section_start = content.find('## Dialogue Summary')
        if dialogue_section_start != -1:
            # Replace existing
            dialogue_section_end = content.find('\n##', dialogue_section_start + 1)
            if dialogue_section_end == -1:
                dialogue_section_end = len(content)

            new_dialogue_section = f"## Dialogue Summary\n\n{dialogue_summary}\n\n"
            content = content[:dialogue_section_start] + new_dialogue_section + content[dialogue_section_end:]
        else:
            # Add new section before STS Evaluation
            sts_section = content.find('## STS Evaluation')
            if sts_section != -1:
                new_dialogue_section = f"\n## Dialogue Summary\n\n{dialogue_summary}\n\n"
                content = content[:sts_section] + new_dialogue_section + content[sts_section:]
            else:
                # Add at the end
                content += f"\n## Dialogue Summary\n\n{dialogue_summary}\n\n"

        # Find or create STS Evaluation section
        sts_section_start = content.find('## STS Evaluation')
        if sts_section_start != -1:
            # Replace existing
            sts_section_end = content.find('\n##', sts_section_start + 1)
            if sts_section_end == -1:
                sts_section_end = len(content)

            new_sts_section = f"""## STS Evaluation

- **STS Score**: {sts_result['sts_score']:.3f}
- **Model Used**: {sts_result.get('model_used', 'unknown')}
- **Text1 Length**: {sts_result.get('text1_length', 0)} words
- **Text2 Length**: {sts_result.get('text2_length', 0)} words

"""
            content = content[:sts_section_start] + new_sts_section + content[sts_section_end:]
        else:
            # Add at the end
            new_sts_section = f"""
## STS Evaluation

- **STS Score**: {sts_result['sts_score']:.3f}
- **Model Used**: {sts_result.get('model_used', 'unknown')}
- **Text1 Length**: {sts_result.get('text1_length', 0)} words
- **Text2 Length**: {sts_result.get('text2_length', 0)} words

"""
            content += new_sts_section

        # Write updated content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"Updated {Path(file_path).name} with new summaries and STS score")

    except Exception as e:
        logger.error(f"Error updating {file_path}: {e}")


def main():
    parser = argparse.ArgumentParser(description='Regenerate summaries and STS scores for existing dialogues')
    parser.add_argument('--output-dir', type=str, default='output_dialogue_framework',
                        help='Directory containing dialogue markdown files')
    parser.add_argument('--gtmf-dir', type=str, default='gtmf',
                        help='Directory containing GTMF markdown files')
    parser.add_argument('--model', type=str, default='medical',
                        choices=['general', 'medical', 'biobert', 'clinical'],
                        help='STS model to use (default: medical)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of dialogues to process (for testing)')

    args = parser.parse_args()

    logger.info("="*80)
    logger.info("Regenerating Summaries and STS Scores")
    logger.info("="*80)
    logger.info(f"Output directory: {args.output_dir}")
    logger.info(f"GTMF directory: {args.gtmf_dir}")
    logger.info(f"STS model: {args.model}")

    # Check if directories exist
    if not os.path.exists(args.output_dir):
        logger.error(f"Output directory not found: {args.output_dir}")
        return

    # Initialize agents
    logger.info("\nInitializing agents...")
    ehr_summarizer = EHRSummarizerAgent()
    dialogue_summarizer = DialogueSummarizerAgent()
    sts_evaluator = STSEvaluatorAgent(model_name=args.model)

    # Load CSV data for EHR text
    mimic_csv_dir = os.getenv("MIMIC_CSV_DIR", None)
    csv_loader = None
    if mimic_csv_dir and os.path.exists(mimic_csv_dir):
        logger.info(f"Loading MIMIC-III CSV data from {mimic_csv_dir}")
        csv_loader = CSVDataLoader(mimic_csv_dir)
    else:
        logger.warning("MIMIC_CSV_DIR not set. Will skip EHR summaries.")

    # Load GTMF data for metadata
    logger.info(f"\nLoading GTMFs from {args.gtmf_dir}...")
    gtmf_data = {}
    if os.path.exists(args.gtmf_dir):
        gtmf_list = load_all_gtmfs_from_directory(args.gtmf_dir)
        for gtmf in gtmf_list:
            profile_id = f"{gtmf.get('subject_id')}_{gtmf.get('hadm_id')}"
            gtmf_data[profile_id] = gtmf
        logger.info(f"Loaded {len(gtmf_data)} GTMF profiles")
    else:
        logger.warning(f"GTMF directory not found: {args.gtmf_dir}")

    # Find all dialogue markdown files
    dialogue_files = list(Path(args.output_dir).glob('dialogue_*.md'))
    logger.info(f"\nFound {len(dialogue_files)} dialogue files")

    if args.limit:
        dialogue_files = dialogue_files[:args.limit]
        logger.info(f"Processing only first {args.limit} files (limit specified)")

    # Process each dialogue
    stats = {
        'total': len(dialogue_files),
        'processed': 0,
        'failed': 0,
        'sts_improved': 0,
        'sts_decreased': 0,
        'sts_unchanged': 0,
        'old_sts_scores': [],
        'new_sts_scores': [],
        'improvements': []
    }

    logger.info("\n" + "="*80)
    logger.info("Processing dialogues...")
    logger.info("="*80)

    for idx, dialogue_file in enumerate(dialogue_files):
        logger.info(f"\n[{idx+1}/{len(dialogue_files)}] Processing {dialogue_file.name}...")

        try:
            # Load dialogue
            dialogue_info = load_dialogue_from_markdown(str(dialogue_file))
            if not dialogue_info:
                logger.warning(f"Failed to load dialogue from {dialogue_file.name}")
                stats['failed'] += 1
                continue

            profile_id = dialogue_info.get('profile_id')
            subject_id = dialogue_info.get('subject_id')
            hadm_id = dialogue_info.get('hadm_id')

            # Get EHR text
            ehr_text = None
            if csv_loader and subject_id and hadm_id:
                ehr_text = csv_loader.fetch_note_by_ids(subject_id, hadm_id)

            # Get GTMF metadata
            gtmf = gtmf_data.get(profile_id, {})
            metadata = gtmf.get('Context_Fields', {})

            # Generate EHR summary
            if ehr_text:
                logger.info("  Generating EHR summary...")
                ehr_summary = ehr_summarizer.summarize(ehr_text, metadata)
            else:
                logger.warning("  No EHR text available, using placeholder")
                ehr_summary = "EHR text not available"

            time.sleep(0.5)  # Rate limiting

            # Generate dialogue summary
            logger.info("  Generating dialogue summary...")
            dialogue_summary = dialogue_summarizer.summarize(
                dialogue=None,
                transcript=dialogue_info['transcript']
            )

            time.sleep(0.5)  # Rate limiting

            # Compute STS score
            logger.info("  Computing STS score...")
            sts_result = sts_evaluator.compute_sts_detailed(ehr_summary, dialogue_summary)
            new_sts_score = sts_result['sts_score']

            # Update markdown file
            update_markdown_with_summaries(
                str(dialogue_file),
                ehr_summary,
                dialogue_summary,
                sts_result
            )

            # Track statistics
            stats['processed'] += 1
            stats['new_sts_scores'].append(new_sts_score)

            old_sts_score = dialogue_info.get('old_sts_score')
            if old_sts_score is not None:
                stats['old_sts_scores'].append(old_sts_score)
                improvement = new_sts_score - old_sts_score

                if improvement > 0.01:
                    stats['sts_improved'] += 1
                    stats['improvements'].append({
                        'file': dialogue_file.name,
                        'old': old_sts_score,
                        'new': new_sts_score,
                        'improvement': improvement
                    })
                elif improvement < -0.01:
                    stats['sts_decreased'] += 1
                else:
                    stats['sts_unchanged'] += 1

                logger.info(f"  STS: {old_sts_score:.3f} → {new_sts_score:.3f} (Δ {improvement:+.3f})")
            else:
                logger.info(f"  STS: {new_sts_score:.3f} (new)")

            time.sleep(1)  # Rate limiting between dialogues

        except Exception as e:
            logger.error(f"Error processing {dialogue_file.name}: {e}", exc_info=True)
            stats['failed'] += 1

    # Generate summary report
    logger.info("\n" + "="*80)
    logger.info("SUMMARY REPORT")
    logger.info("="*80)
    logger.info(f"Total dialogues: {stats['total']}")
    logger.info(f"Processed: {stats['processed']}")
    logger.info(f"Failed: {stats['failed']}")

    if stats['new_sts_scores']:
        avg_new_sts = sum(stats['new_sts_scores']) / len(stats['new_sts_scores'])
        logger.info(f"\nNew STS scores:")
        logger.info(f"  Average: {avg_new_sts:.3f}")
        logger.info(f"  Min: {min(stats['new_sts_scores']):.3f}")
        logger.info(f"  Max: {max(stats['new_sts_scores']):.3f}")

    if stats['old_sts_scores']:
        avg_old_sts = sum(stats['old_sts_scores']) / len(stats['old_sts_scores'])
        avg_new_sts_comparable = sum(stats['new_sts_scores'][:len(stats['old_sts_scores'])]) / len(stats['old_sts_scores'])

        logger.info(f"\nComparison (dialogues with previous STS):")
        logger.info(f"  Old average: {avg_old_sts:.3f}")
        logger.info(f"  New average: {avg_new_sts_comparable:.3f}")
        logger.info(f"  Overall improvement: {avg_new_sts_comparable - avg_old_sts:+.3f}")
        logger.info(f"\n  Improved: {stats['sts_improved']}")
        logger.info(f"  Decreased: {stats['sts_decreased']}")
        logger.info(f"  Unchanged: {stats['sts_unchanged']}")

        if stats['improvements']:
            logger.info(f"\nTop 5 improvements:")
            top_improvements = sorted(stats['improvements'], key=lambda x: x['improvement'], reverse=True)[:5]
            for imp in top_improvements:
                logger.info(f"  {imp['file']}: {imp['old']:.3f} → {imp['new']:.3f} (+{imp['improvement']:.3f})")

    # Save detailed report
    report_path = Path(args.output_dir) / 'sts_regeneration_report.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    logger.info(f"\nDetailed report saved to: {report_path}")

    logger.info("\nRegeneration complete!")


if __name__ == "__main__":
    main()
