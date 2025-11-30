"""
Main pipeline for generating synthetic patient-physician conversations.

This pipeline implements the PRD requirements:
- Light case filtering from MIMIC-III
- Batched GTMF creation
- Profile generation (FULL, NO_DIAGNOSIS, NO_DIAGNOSIS_NO_TREATMENT)
- Iterative dialogue generation with LLM judge
- EHR and dialogue summarization
- STS evaluation
- Comprehensive statistics collection
"""

import logging
import time
import json
from pathlib import Path
from typing import List, Dict, Tuple
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Configuration
from config import PipelineConfig

# Data loading and filtering
from Utils.utils import fetch_notes_batched, get_db_uri
from Utils.csv_loader import fetch_notes_batched_from_csv, create_sample_csv
from Utils.light_case_filter import LightCaseFilter

# Agents
from Agents.GTMFAgent import GTMFExtractionAgent
from Agents.ProfileGeneratorAgent import ProfileGeneratorAgent
from Agents.DoctorAgent import DoctorAgent
from Agents.PatientAgent import PatientAgent
from Agents.JudgeAgent import JudgeAgent
from Agents.PromptImprovementAgent import PromptImprovementAgent
from Agents.SummarizerAgent import SummarizerAgent

# Utilities
from Utils.sts_evaluator import STSEvaluator
from Utils.stats_collector import StatsCollector
from simulation import simulate_dialogue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('synthetic_dialogue_pipeline.log')
    ]
)
logger = logging.getLogger(__name__)


class SyntheticDialoguePipeline:
    """Main pipeline orchestrator for synthetic dialogue generation."""

    def __init__(self, config: PipelineConfig):
        """
        Initialize the pipeline.

        Args:
            config: Pipeline configuration object.
        """
        self.config = config
        logger.info("Initializing Synthetic Dialogue Pipeline")

        # Create output directories
        config.create_output_directories()

        # Initialize components
        self.light_case_filter = LightCaseFilter()
        self.gtmf_agent = GTMFExtractionAgent(
            model_name=config.gtmf.model_name,
            include_llm_judge=config.gtmf.use_llm_judge,
            enable_chunking=config.gtmf.enable_chunking
        )
        self.profile_generator = ProfileGeneratorAgent()
        self.judge_agent = JudgeAgent(
            model_name=config.judge.model_name,
            temperature=config.judge.temperature,
            threshold=config.judge.threshold
        )
        self.prompt_improver = PromptImprovementAgent()
        self.summarizer = SummarizerAgent()
        self.sts_evaluator = STSEvaluator(model_name=config.sts.model_name)
        self.stats_collector = StatsCollector(output_dir=config.output.stats_dir)

        logger.info("Pipeline initialization complete")

    def run(self) -> Dict:
        """
        Run the complete pipeline.

        Returns:
            Summary dictionary with pipeline results.
        """
        logger.info("=" * 80)
        logger.info(f"STARTING PIPELINE RUN: {self.config.run_name}")
        logger.info("=" * 80)

        start_time = time.time()

        try:
            # Stage 1: EHR Retrieval with light case filtering
            logger.info("\n[STAGE 1] EHR Retrieval & Light Case Filtering")
            ehr_cases = self._retrieve_and_filter_ehr()

            if not ehr_cases:
                logger.error("No EHR cases passed light case filter. Exiting.")
                return {"error": "No valid EHR cases"}

            # Stage 2: Batched GTMF Creation
            logger.info(f"\n[STAGE 2] Batched GTMF Creation ({len(ehr_cases)} cases)")
            gtmfs = self._create_gtmfs_batched(ehr_cases)

            if not gtmfs:
                logger.error("No GTMFs created. Exiting.")
                return {"error": "No GTMFs created"}

            # Stage 3: Profile Generation
            logger.info(f"\n[STAGE 3] Profile Generation ({len(gtmfs)} GTMFs)")
            profiles = self._generate_profiles(gtmfs)

            if not profiles:
                logger.error("No profiles generated. Exiting.")
                return {"error": "No profiles generated"}

            # Stage 4-7: For each profile: Dialogue + Judge + Summaries + STS
            logger.info(f"\n[STAGE 4-7] Dialogue Generation Loop ({len(profiles)} profiles)")
            self._process_profiles(profiles, ehr_cases)

            # Stage 8: Save statistics
            logger.info("\n[STAGE 8] Saving Statistics")
            self._save_statistics()

            # Compute final summary
            elapsed_time = time.time() - start_time
            summary = self._generate_summary(elapsed_time)

            logger.info("=" * 80)
            logger.info("PIPELINE RUN COMPLETE")
            logger.info("=" * 80)

            return summary

        except Exception as e:
            logger.error(f"Pipeline failed with error: {e}", exc_info=True)
            return {"error": str(e)}

    def _retrieve_and_filter_ehr(self) -> List[Dict]:
        """Retrieve EHR cases and apply light case filter."""
        all_cases = []

        if self.config.data_source.source_type == "csv":
            logger.info(f"Loading data from CSV: {self.config.data_source.csv_file_path}")

            # Create sample CSV if it doesn't exist
            csv_path = Path(self.config.data_source.csv_file_path)
            if not csv_path.exists():
                logger.warning(f"CSV file not found: {csv_path}. Creating sample CSV...")
                create_sample_csv(str(csv_path), num_samples=10)

            # Load from CSV in batches
            for batch in fetch_notes_batched_from_csv(
                str(csv_path),
                batch_size=self.config.data_source.batch_size,
                max_total=self.config.data_source.max_total_records,
                offset=self.config.data_source.offset
            ):
                # Apply light case filter
                filtered_batch, filter_stats = self.light_case_filter.filter_batch(batch)

                all_cases.extend(filtered_batch)

                logger.info(f"  Batch: {filter_stats['passed']}/{filter_stats['total']} "
                           f"passed light case filter ({filter_stats['pass_rate']:.1%})")

        elif self.config.data_source.source_type == "database":
            logger.info("Loading data from PostgreSQL database")

            db_uri = self.config.data_source.database_url or get_db_uri()
            if not db_uri:
                raise ValueError("DATABASE_URL not configured for database source")

            engine = create_engine(db_uri)
            Session = sessionmaker(bind=engine)

            with Session() as session:
                for batch in fetch_notes_batched(
                    session,
                    batch_size=self.config.data_source.batch_size,
                    max_total=self.config.data_source.max_total_records,
                    offset=self.config.data_source.offset
                ):
                    # Convert to dictionaries
                    batch_dicts = [dict(row) for row in batch]

                    # Apply light case filter
                    filtered_batch, filter_stats = self.light_case_filter.filter_batch(batch_dicts)

                    all_cases.extend(filtered_batch)

                    logger.info(f"  Batch: {filter_stats['passed']}/{filter_stats['total']} "
                               f"passed light case filter ({filter_stats['pass_rate']:.1%})")
        else:
            raise ValueError(f"Invalid source_type: {self.config.data_source.source_type}. "
                           f"Must be 'csv' or 'database'")

        logger.info(f"Total EHR cases after filtering: {len(all_cases)}")

        # Save filtered EHR cases
        for case in all_cases:
            hadm_id = case.get('hadm_id', 'unknown')
            subject_id = case.get('subject_id', 'unknown')
            filepath = Path(self.config.output.ehr_dir) / f"ehr_case_{subject_id}_{hadm_id}.json"

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(case, f, indent=2, default=str)

        return all_cases

    def _create_gtmfs_batched(self, ehr_cases: List[Dict]) -> List[Tuple[Dict, Dict]]:
        """Create GTMFs in batches."""
        batch_size = self.config.gtmf.gtmf_batch_size
        all_gtmfs = []

        for i in range(0, len(ehr_cases), batch_size):
            batch = ehr_cases[i:i + batch_size]
            logger.info(f"  Processing GTMF batch {i//batch_size + 1} "
                       f"({len(batch)} cases)")

            results = self.gtmf_agent.extract_batch(batch, use_llm_judge=self.config.gtmf.use_llm_judge)

            for gtmf, quality_report in results:
                # Convert GTMF to dict for easier handling
                gtmf_dict = gtmf.dict() if hasattr(gtmf, 'dict') else gtmf.__dict__

                # Save GTMF
                hadm_id = gtmf_dict.get('hadm_id', 'unknown')
                subject_id = gtmf_dict.get('subject_id', 'unknown')
                filepath = Path(self.config.output.gtmf_dir) / f"gtmf_{subject_id}_{hadm_id}.json"

                output = {
                    "gtmf": gtmf_dict,
                    "quality_report": quality_report
                }

                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(output, f, indent=2, default=str)

                all_gtmfs.append((gtmf_dict, quality_report))

        logger.info(f"Total GTMFs created: {len(all_gtmfs)}")
        return all_gtmfs

    def _generate_profiles(self, gtmfs: List[Tuple[Dict, Dict]]) -> List[Dict]:
        """Generate profiles from GTMFs."""
        all_profiles = []

        for gtmf_dict, quality_report in gtmfs:
            for profile_type in self.config.profile.profile_types:
                profile = self.profile_generator.generate_profile(gtmf_dict, profile_type)

                # Validate and enhance
                is_valid, issues = self.profile_generator.validate_profile_completeness(profile)

                if not is_valid:
                    logger.warning(f"Profile validation issues: {issues}")
                    continue

                profile = self.profile_generator.enhance_profile_if_needed(profile)

                # Save profile
                profile_id = f"{profile['row_id']}_{profile['subject_id']}_{profile_type}"
                filepath = Path(self.config.output.profiles_dir) / f"profile_{profile_id}.json"

                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(profile, f, indent=2, default=str)

                all_profiles.append(profile)

        logger.info(f"Total profiles generated: {len(all_profiles)}")
        return all_profiles

    def _process_profiles(self, profiles: List[Dict], ehr_cases: List[Dict]) -> None:
        """Process each profile through dialogue generation, evaluation, and analysis."""
        for idx, profile in enumerate(profiles, 1):
            profile_id = f"{profile.get('row_id', 0)}_{profile.get('subject_id', 0)}"
            logger.info(f"\n[Profile {idx}/{len(profiles)}] ID={profile_id}")

            start_time = time.time()

            # Initialize stats
            stats = self.stats_collector.create_profile_stats(
                profile_id=profile_id,
                subject_id=profile.get('subject_id', 0),
                hadm_id=profile.get('hadm_id', 0),
                row_id=profile.get('row_id', 0),
                profile_type=profile.get('profile_type', 'UNKNOWN'),
                light_case_filter=profile.get('light_case_filter')
            )

            # Iterative dialogue generation
            success, final_dialogue, final_evaluation = self._generate_dialogue_iteratively(profile)

            # Record attempts and results
            processing_time = time.time() - start_time
            self.stats_collector.record_processing_time(profile_id, processing_time)

            if not success:
                logger.warning(f"  Failed to generate realistic dialogue for {profile_id}")
                continue

            # Summarization and STS
            self._compute_summaries_and_sts(profile, final_dialogue, ehr_cases)

            # Save final dialogue
            self._save_dialogue(profile, final_dialogue, final_evaluation)

        logger.info(f"\nCompleted processing {len(profiles)} profiles")

    def _generate_dialogue_iteratively(self, profile: Dict) -> Tuple[bool, List[Dict], Dict]:
        """Generate dialogue with iterative refinement."""
        profile_id = f"{profile.get('row_id', 0)}_{profile.get('subject_id', 0)}"
        max_attempts = self.config.dialogue.max_attempts_per_profile

        current_prompts = None  # Will use defaults initially

        for attempt in range(1, max_attempts + 1):
            logger.info(f"  Attempt {attempt}/{max_attempts}")

            # Initialize agents (with potentially improved prompts)
            doctor_agent = DoctorAgent(patient_profile=profile)
            patient_agent = PatientAgent(profile=profile)

            # Generate dialogue
            conversation, transcript = simulate_dialogue(
                doctor_agent,
                patient_agent,
                max_turns=self.config.dialogue.max_turns
            )

            # Evaluate with judge
            evaluation = self.judge_agent.evaluate_dialogue(conversation, profile, attempt)

            # Record attempt
            self.stats_collector.record_attempt(
                profile_id,
                attempt,
                evaluation['score'],
                evaluation['decision']
            )

            # Save judge evaluation
            self._save_judge_evaluation(profile, evaluation, attempt)

            if evaluation['decision'] == 'REALISTIC':
                logger.info(f"  ✓ Realistic dialogue generated on attempt {attempt}")
                return True, conversation, evaluation

            # If not realistic and attempts remain, try to improve prompts
            if attempt < max_attempts:
                logger.info(f"  Unrealistic ({evaluation['score']:.2f}), improving prompts...")
                improvements = self.prompt_improver.improve_prompts(
                    conversation,
                    evaluation,
                    current_prompts
                )
                # Note: In a full implementation, we'd apply these improvements
                # to the agents. For now, we log them.
                logger.debug(f"  Improvements: {improvements.get('summary', 'N/A')}")

        logger.warning(f"  Failed to generate realistic dialogue after {max_attempts} attempts")
        return False, [], {}

    def _compute_summaries_and_sts(self, profile: Dict, dialogue: List[Dict], ehr_cases: List[Dict]) -> None:
        """Compute EHR and dialogue summaries, then STS score."""
        profile_id = f"{profile.get('row_id', 0)}_{profile.get('subject_id', 0)}"
        hadm_id = profile.get('hadm_id')

        # Find matching EHR case
        ehr_text = None
        for case in ehr_cases:
            if case.get('hadm_id') == hadm_id:
                ehr_text = case.get('text', '')
                break

        if not ehr_text:
            logger.warning(f"  No EHR text found for {profile_id}, skipping STS")
            return

        # Summarize EHR
        ehr_summary = self.summarizer.summarize_ehr(ehr_text)

        # Summarize dialogue
        dialogue_summary = self.summarizer.summarize_dialogue(dialogue)

        # Compute STS
        sts_result = self.sts_evaluator.evaluate_ehr_dialogue_similarity(
            ehr_summary,
            dialogue_summary,
            profile_id
        )

        # Record STS score
        self.stats_collector.record_sts_score(profile_id, sts_result['sts_score'])

        # Save summaries and STS
        summaries_dir = Path(self.config.output.summaries_dir)
        (summaries_dir / f"ehr_summary_{hadm_id}.json").write_text(
            json.dumps({"summary": ehr_summary}, indent=2)
        )
        (summaries_dir / f"dialogue_summary_{profile_id}.json").write_text(
            json.dumps({"summary": dialogue_summary}, indent=2)
        )

        sts_dir = Path(self.config.output.sts_dir)
        (sts_dir / f"sts_{profile_id}.json").write_text(
            json.dumps(sts_result, indent=2)
        )

        logger.info(f"  STS score: {sts_result['sts_score']:.4f}")

    def _save_dialogue(self, profile: Dict, dialogue: List[Dict], evaluation: Dict) -> None:
        """Save final dialogue with metadata."""
        profile_id = f"{profile.get('row_id', 0)}_{profile.get('subject_id', 0)}"
        filepath = Path(self.config.output.dialogues_dir) / f"dialogue_{profile_id}.json"

        output = {
            "profile": profile,
            "dialogue": dialogue,
            "evaluation": evaluation,
            "transcript": "\n".join([f"{turn['role']}: {turn['content']}" for turn in dialogue])
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)

    def _save_judge_evaluation(self, profile: Dict, evaluation: Dict, attempt: int) -> None:
        """Save judge evaluation."""
        profile_id = f"{profile.get('row_id', 0)}_{profile.get('subject_id', 0)}"
        filepath = Path(self.config.output.judge_dir) / f"judge_eval_{profile_id}_attempt{attempt}.json"

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(evaluation, f, indent=2)

    def _save_statistics(self) -> None:
        """Save all statistics."""
        self.stats_collector.save_all_stats()
        self.stats_collector.print_summary()

    def _generate_summary(self, elapsed_time: float) -> Dict:
        """Generate pipeline run summary."""
        global_stats = self.stats_collector.compute_global_stats()

        summary = {
            "run_name": self.config.run_name,
            "elapsed_time_seconds": elapsed_time,
            "configuration": self.config.to_dict(),
            "statistics": global_stats
        }

        # Save run summary
        filepath = Path(self.config.output.runs_dir) / f"run_{self.config.run_name}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)

        return summary


def main():
    """Main entry point."""
    # Load configuration
    config_path = "config/default_config.yaml"

    if Path(config_path).exists():
        logger.info(f"Loading configuration from {config_path}")
        config = PipelineConfig.from_yaml(config_path)
    else:
        logger.info("Using default configuration")
        config = PipelineConfig()

    # Create and run pipeline
    pipeline = SyntheticDialoguePipeline(config)
    summary = pipeline.run()

    # Print summary
    if "error" not in summary:
        logger.info("\nPipeline completed successfully!")
    else:
        logger.error(f"\nPipeline failed: {summary['error']}")


if __name__ == "__main__":
    main()
