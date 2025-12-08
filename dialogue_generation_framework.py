"""
Main dialogue generation script implementing the PRD requirements.

Features:
- Light case GTMF processing
- Three profile types (FULL, NO_DIAGNOSIS, NO_DIAGNOSIS_NO_TREATMENT)
- Iterative dialogue generation (up to 3 attempts)
- JudgeAgent for naturalness validation
- PromptImprovementAgent for feedback
- EHR and dialogue summarization
- STS evaluation
- Comprehensive statistics
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Tuple

from Utils.partial_profile import generate_partial_profiles
from Agents.PatientAgent import PatientAgent
from Agents.DoctorAgent import DoctorAgent
from Agents.JudgeAgent import JudgeAgent
from Agents.PromptImprovementAgent import PromptImprovementAgent
from Agents.EHRSummarizerAgent import EHRSummarizerAgent
from Agents.DialogueSummarizerAgent import DialogueSummarizerAgent
from Agents.STSEvaluatorAgent import STSEvaluatorAgent
from simulation import simulate_dialogue

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DialogueGenerationPipeline:
    """
    Pipeline for generating and evaluating synthetic patient-physician dialogues.
    """

    def __init__(
        self,
        max_attempts: int = 3,
        max_turns: int = 16,
        judge_threshold: float = 0.70,
        output_dir: str = "output_dialogue_framework"
    ):
        """
        Initialize the dialogue generation pipeline.

        Args:
            max_attempts: Maximum dialogue generation attempts per profile
            max_turns: Maximum turns per dialogue
            judge_threshold: Score threshold for realistic decision
            output_dir: Output directory for results
        """
        self.max_attempts = max_attempts
        self.max_turns = max_turns
        self.judge_threshold = judge_threshold
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Initialize agents
        logger.info("Initializing pipeline agents...")
        self.judge_agent = JudgeAgent(threshold=judge_threshold)
        self.prompt_improvement_agent = PromptImprovementAgent()
        self.ehr_summarizer = EHRSummarizerAgent()
        self.dialogue_summarizer = DialogueSummarizerAgent()
        self.sts_evaluator = STSEvaluatorAgent()

        logger.info("Pipeline initialized successfully")

    def generate_dialogue_with_iterations(
        self,
        patient_profile: dict,
        full_profile: dict,
        ehr_text: str = None
    ) -> Dict:
        """
        Generate dialogue with iterative improvement.

        Args:
            patient_profile: Partial profile for agents
            full_profile: Complete profile for evaluation
            ehr_text: Original EHR text for summarization

        Returns:
            Dict with dialogue, evaluation, summaries, and stats
        """
        profile_id = f"{patient_profile.get('subject_id', 'unknown')}_{patient_profile.get('hadm_id', 'unknown')}"
        logger.info(f"\n{'='*60}")
        logger.info(f"Generating dialogue for profile: {profile_id}")
        logger.info(f"Profile type: {patient_profile.get('profile_type', 'UNKNOWN')}")

        # Track attempt history
        attempts = []
        best_dialogue = None
        best_score = 0.0
        best_attempt_idx = -1

        # Initialize agents
        doctor_agent = DoctorAgent(patient_profile=patient_profile)
        patient_agent = PatientAgent(profile=patient_profile)

        for attempt_idx in range(self.max_attempts):
            logger.info(f"  Attempt {attempt_idx + 1}/{self.max_attempts}")
            attempt_start = time.time()

            try:
                # Generate dialogue
                conversation, transcript = simulate_dialogue(
                    doctor_agent, patient_agent,
                    max_turns=self.max_turns,
                    consecutive_confusion_limit=2,
                    loop_detection_window=4
                )

                if not conversation or len(conversation) < 4:
                    logger.warning(f"  Dialogue too short: {len(conversation)} turns")
                    attempts.append({
                        "attempt": attempt_idx + 1,
                        "success": False,
                        "reason": "Dialogue too short",
                        "turns": len(conversation) if conversation else 0
                    })
                    continue

                # Evaluate with JudgeAgent
                logger.info(f"  Evaluating with JudgeAgent...")
                judge_result = self.judge_agent.evaluate_dialogue(
                    conversation, full_profile, transcript
                )

                attempt_time = time.time() - attempt_start

                # Record attempt
                attempt_record = {
                    "attempt": attempt_idx + 1,
                    "success": judge_result['decision'] == "REALISTIC",
                    "score": judge_result['score'],
                    "decision": judge_result['decision'],
                    "justification": judge_result['justification'],
                    "turns": len(conversation),
                    "time_seconds": attempt_time
                }
                attempts.append(attempt_record)

                logger.info(f"  Result: {judge_result['decision']} (score: {judge_result['score']:.3f})")

                # Track best dialogue
                if judge_result['score'] > best_score:
                    best_score = judge_result['score']
                    best_dialogue = {
                        "conversation": conversation,
                        "transcript": transcript,
                        "judge_result": judge_result
                    }
                    best_attempt_idx = attempt_idx + 1

                # Check if successful
                if judge_result['decision'] == "REALISTIC":
                    logger.info(f"  ✓ Dialogue accepted on attempt {attempt_idx + 1}")
                    break

                # If not successful and not last attempt, improve prompts
                if attempt_idx < self.max_attempts - 1:
                    logger.info(f"  Generating improvements for next attempt...")
                    improvements = self.prompt_improvement_agent.improve_prompts(
                        judge_result, conversation
                    )

                    # Apply improvements (simple feedback injection)
                    doctor_agent.update_prompt(improvements.get('doctor_improvements', ''))
                    patient_agent.update_prompt(improvements.get('patient_improvements', ''))
                    logger.info(f"  Prompts updated for attempt {attempt_idx + 2}")

            except Exception as e:
                logger.error(f"  Error in attempt {attempt_idx + 1}: {e}", exc_info=True)
                attempts.append({
                    "attempt": attempt_idx + 1,
                    "success": False,
                    "reason": f"Error: {str(e)}",
                    "turns": 0
                })

        # Return best result
        if best_dialogue:
            return {
                "success": True,
                "profile_id": profile_id,
                "best_attempt": best_attempt_idx,
                "attempts_summary": attempts,
                "dialogue": best_dialogue['conversation'],
                "transcript": best_dialogue['transcript'],
                "judge_evaluation": best_dialogue['judge_result']
            }
        else:
            logger.error(f"  ✗ Failed to generate acceptable dialogue after {self.max_attempts} attempts")
            return {
                "success": False,
                "profile_id": profile_id,
                "attempts_summary": attempts,
                "dialogue": None,
                "transcript": None
            }

    def process_profile(
        self,
        full_profile: dict,
        ehr_text: str = None,
        profile_type: str = "NO_DIAGNOSIS_NO_TREATMENT"
    ) -> Dict:
        """
        Process a single profile through the complete pipeline.

        Args:
            full_profile: Complete GTMF profile
            ehr_text: Original EHR text (for summarization)
            profile_type: Type of partial profile to generate

        Returns:
            Complete result dict with dialogue, summaries, STS, and stats
        """
        profile_id = f"{full_profile.get('subject_id', 'unknown')}_{full_profile.get('hadm_id', 'unknown')}"
        logger.info(f"\n{'='*80}")
        logger.info(f"Processing profile {profile_id} (type: {profile_type})")

        start_time = time.time()

        # Generate partial profile
        partial_profile = generate_partial_profiles(full_profile, profile_type)

        # Generate dialogue with iterations
        dialogue_result = self.generate_dialogue_with_iterations(
            partial_profile, full_profile, ehr_text
        )

        if not dialogue_result['success']:
            return {
                "profile_id": profile_id,
                "success": False,
                "attempts": dialogue_result['attempts_summary'],
                "processing_time": time.time() - start_time
            }

        # Summarize EHR
        logger.info(f"  Generating EHR summary...")
        ehr_summary = "No EHR text provided"
        if ehr_text:
            ehr_summary = self.ehr_summarizer.summarize(
                ehr_text,
                metadata=full_profile.get('Context_Fields', {})
            )

        # Summarize dialogue
        logger.info(f"  Generating dialogue summary...")
        dialogue_summary = self.dialogue_summarizer.summarize(
            dialogue_result['dialogue'],
            dialogue_result['transcript']
        )

        # Compute STS
        logger.info(f"  Computing STS between summaries...")
        sts_result = self.sts_evaluator.compute_sts_detailed(
            ehr_summary, dialogue_summary
        )

        processing_time = time.time() - start_time

        # Compile complete result
        result = {
            "profile_id": profile_id,
            "subject_id": full_profile.get('subject_id'),
            "hadm_id": full_profile.get('hadm_id'),
            "profile_type": profile_type,
            "success": True,
            "best_attempt": dialogue_result['best_attempt'],
            "total_attempts": len(dialogue_result['attempts_summary']),
            "attempts_summary": dialogue_result['attempts_summary'],
            "dialogue": dialogue_result['dialogue'],
            "transcript": dialogue_result['transcript'],
            "judge_evaluation": dialogue_result['judge_evaluation'],
            "ehr_summary": ehr_summary,
            "dialogue_summary": dialogue_summary,
            "sts_evaluation": sts_result,
            "processing_time": processing_time,
            "dialogue_stats": {
                "turn_count": len(dialogue_result['dialogue']),
                "word_count": len(dialogue_result['transcript'].split()),
                "doctor_turns": len([t for t in dialogue_result['dialogue'] if t.get('role') == 'Doctor']),
                "patient_turns": len([t for t in dialogue_result['dialogue'] if t.get('role') == 'Patient'])
            }
        }

        # Save individual result
        output_path = self.output_dir / f"dialogue_{profile_id}.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
        logger.info(f"  ✓ Saved result to {output_path}")

        return result

    def run_pipeline(
        self,
        gtmf_data: List[dict],
        ehr_texts: Dict[str, str] = None,
        profile_types: List[str] = None
    ) -> Dict:
        """
        Run the complete pipeline on multiple profiles.

        Args:
            gtmf_data: List of GTMF profiles
            ehr_texts: Optional dict mapping profile_id to EHR text
            profile_types: List of profile types to generate (default: all three)

        Returns:
            Global statistics and summary
        """
        if profile_types is None:
            profile_types = ["FULL", "NO_DIAGNOSIS", "NO_DIAGNOSIS_NO_TREATMENT"]

        logger.info(f"\n{'='*80}")
        logger.info(f"Starting pipeline with {len(gtmf_data)} profiles")
        logger.info(f"Profile types: {profile_types}")
        logger.info(f"Max attempts per dialogue: {self.max_attempts}")
        logger.info(f"Judge threshold: {self.judge_threshold}")

        ehr_texts = ehr_texts or {}
        all_results = []
        stats = {
            "total_profiles": len(gtmf_data),
            "total_dialogues_attempted": 0,
            "successful_dialogues": 0,
            "failed_dialogues": 0,
            "by_profile_type": {pt: {"success": 0, "fail": 0} for pt in profile_types},
            "attempt_distribution": {1: 0, 2: 0, 3: 0},
            "judge_scores": [],
            "sts_scores": [],
            "processing_times": []
        }

        # Process each profile
        for idx, full_profile in enumerate(gtmf_data):
            profile_id = f"{full_profile.get('subject_id', 'unknown')}_{full_profile.get('hadm_id', 'unknown')}"

            # Get EHR text if available
            ehr_text = ehr_texts.get(profile_id)

            # Process with first profile type (can extend to process all types)
            profile_type = profile_types[0]  # Use first type for now

            try:
                result = self.process_profile(full_profile, ehr_text, profile_type)
                all_results.append(result)

                # Update stats
                stats["total_dialogues_attempted"] += 1
                if result['success']:
                    stats["successful_dialogues"] += 1
                    stats["by_profile_type"][profile_type]["success"] += 1
                    stats["attempt_distribution"][result['best_attempt']] += 1
                    stats["judge_scores"].append(result['judge_evaluation']['score'])
                    stats["sts_scores"].append(result['sts_evaluation']['sts_score'])
                    stats["processing_times"].append(result['processing_time'])
                else:
                    stats["failed_dialogues"] += 1
                    stats["by_profile_type"][profile_type]["fail"] += 1

            except Exception as e:
                logger.error(f"Error processing profile {profile_id}: {e}", exc_info=True)
                stats["failed_dialogues"] += 1

        # Compute aggregate stats
        if stats["judge_scores"]:
            stats["avg_judge_score"] = sum(stats["judge_scores"]) / len(stats["judge_scores"])
            stats["avg_sts_score"] = sum(stats["sts_scores"]) / len(stats["sts_scores"])
            stats["avg_processing_time"] = sum(stats["processing_times"]) / len(stats["processing_times"])

        # Save global stats
        stats_path = self.output_dir / "global_stats.json"
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2)

        # Save per-profile stats
        per_profile_stats = [
            {
                "profile_id": r.get('profile_id'),
                "success": r.get('success'),
                "attempts": r.get('total_attempts'),
                "best_attempt": r.get('best_attempt'),
                "judge_score": r.get('judge_evaluation', {}).get('score'),
                "sts_score": r.get('sts_evaluation', {}).get('sts_score'),
                "processing_time": r.get('processing_time')
            }
            for r in all_results if r.get('success')
        ]
        per_profile_path = self.output_dir / "per_profile_stats.json"
        with open(per_profile_path, 'w', encoding='utf-8') as f:
            json.dump(per_profile_stats, f, indent=2)

        logger.info(f"\n{'='*80}")
        logger.info("PIPELINE SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"Total profiles: {stats['total_profiles']}")
        logger.info(f"Successful dialogues: {stats['successful_dialogues']}")
        logger.info(f"Failed dialogues: {stats['failed_dialogues']}")
        logger.info(f"Success rate: {stats['successful_dialogues']/stats['total_dialogues_attempted']:.1%}")
        if stats.get('avg_judge_score'):
            logger.info(f"Average judge score: {stats['avg_judge_score']:.3f}")
            logger.info(f"Average STS score: {stats['avg_sts_score']:.3f}")
            logger.info(f"Average processing time: {stats['avg_processing_time']:.1f}s")

        return stats


def main():
    """Main entry point."""
    logger.info("Starting Synthetic Patient-Physician Conversation Framework")

    # Load GTMF data (light cases only)
    gtmf_path = "gtmf/gtmf_example_minimal_enhanced.json"  # Use light-case filtered GTMFs

    if not os.path.exists(gtmf_path):
        logger.error(f"GTMF file not found: {gtmf_path}")
        logger.info("Please run gtmf_creation.py first to generate light-case GTMFs")
        return

    with open(gtmf_path, 'r', encoding='utf-8') as f:
        gtmf_data = json.load(f)

    logger.info(f"Loaded {len(gtmf_data)} GTMF profiles")

    # Filter for light cases
    light_case_profiles = [
        p for p in gtmf_data
        if p.get('light_case_filter', {}).get('passed', False)
    ]
    logger.info(f"Found {len(light_case_profiles)} light case profiles")

    if not light_case_profiles:
        logger.warning("No light case profiles found. Using all profiles.")
        light_case_profiles = gtmf_data[:10]  # Use first 10 as fallback

    # Initialize pipeline
    pipeline = DialogueGenerationPipeline(
        max_attempts=3,
        max_turns=16,
        judge_threshold=0.70,
        output_dir="output_dialogue_framework"
    )

    # Run pipeline (process first 5 profiles as example)
    stats = pipeline.run_pipeline(
        gtmf_data=light_case_profiles[:5],
        profile_types=["NO_DIAGNOSIS_NO_TREATMENT"]  # Can extend to all three types
    )

    logger.info("\n✓ Pipeline completed successfully!")
    logger.info(f"Results saved to: {pipeline.output_dir}")


if __name__ == "__main__":
    main()
