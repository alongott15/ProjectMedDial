"""Main Pipeline Orchestrator - Runs the complete experiment"""
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.light_case_filter import LightCaseFilter
from utils.llms_utils import LLMClient
from utils.utils import get_db_uri
from agents.ehr_retrieval import EHRRetrievalAgent
from agents.gtmf_creation import GTMFCreationAgent
from agents.profile_generator import ProfileGeneratorAgent
from agents.patient_agent import PatientAgent
from agents.doctor_agent import DoctorAgent
from agents.dialogue_orchestrator import DialogueOrchestratorAgent
from agents.judge_agent import JudgeAgent
from agents.prompt_improvement import PromptImprovementAgent
from agents.ehr_summarizer import EHRSummarizerAgent
from agents.dialogue_summarizer import DialogueSummarizerAgent
from agents.sts_evaluator import STSEvaluatorAgent
from agents.stats_collector import StatsCollectorAgent

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Main orchestrator for the synthetic conversation framework"""

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config = self.load_config(config_path)
        self.setup_logging()
        self.stats_collector = StatsCollectorAgent()
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def load_config(self, config_path: str) -> dict:
        """Load configuration from YAML"""
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config

    def setup_logging(self):
        """Setup logging configuration"""
        log_level = getattr(logging, self.config.get('logging', {}).get('level', 'INFO'))
        log_format = self.config.get('logging', {}).get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logging.basicConfig(level=log_level, format=log_format)

    def save_run_config(self):
        """Save run configuration"""
        runs_dir = Path(self.config['outputs']['runs_dir'])
        runs_dir.mkdir(parents=True, exist_ok=True)

        config_file = runs_dir / f"config_run_{self.timestamp}.json"
        with open(config_file, 'w') as f:
            json.dump(self.config, f, indent=2)

        logger.info(f"Saved run configuration to {config_file}")

    def run_stage_1_ehr_retrieval(self):
        """Stage 1: EHR Retrieval"""
        logger.info("\n" + "=" * 60)
        logger.info("STAGE 1: EHR RETRIEVAL")
        logger.info("=" * 60)

        # Initialize light case filter
        filter_config = self.config['light_case_filter']
        light_case_filter = LightCaseFilter(
            include_terms=filter_config['include_terms'],
            exclude_terms=filter_config['exclude_terms']
        )

        # Initialize EHR retrieval agent
        db_uri = get_db_uri()
        ehr_agent = EHRRetrievalAgent(
            db_uri=db_uri,
            light_case_filter=light_case_filter,
            output_dir=self.config['outputs']['ehr_dir']
        )

        # Retrieve and filter cases
        batch_size = self.config['batching']['db_batch_size']
        total_limit = self.config['experiment']['num_admissions']

        all_cases = []
        for batch in ehr_agent.retrieve_and_filter(batch_size, total_limit):
            ehr_agent.save_cases(batch)
            all_cases.extend(batch)

        self.stats_collector.update_global_stats('ehr_cases_retrieved', len(all_cases))
        self.stats_collector.update_global_stats('light_cases_passed', len(all_cases))

        logger.info(f"Stage 1 complete: Retrieved {len(all_cases)} light cases")
        return all_cases

    def run_stage_2_gtmf_creation(self, ehr_cases: list):
        """Stage 2: GTMF Creation with batch processing"""
        logger.info("\n" + "=" * 60)
        logger.info("STAGE 2: GTMF CREATION (BATCHED)")
        logger.info("=" * 60)

        # Initialize LLM client for GTMF extraction
        gtmf_model_config = self.config['models']['gtmf_extraction']
        llm_client = LLMClient(
            api_key=os.getenv(gtmf_model_config['api_key_env']),
            model_name=gtmf_model_config['model_name']
        )

        # Initialize GTMF creation agent
        gtmf_agent = GTMFCreationAgent(
            llm_client=llm_client,
            output_dir=self.config['outputs']['gtmf_dir']
        )

        # Process in batches
        batch_size = self.config['batching']['gtmf_batch_size']
        all_gtmfs = []

        for i in range(0, len(ehr_cases), batch_size):
            batch = ehr_cases[i:i + batch_size]
            logger.info(f"Processing GTMF batch {i // batch_size + 1}")

            gtmfs = gtmf_agent.create_batch(batch)
            gtmf_agent.save_batch(gtmfs)
            all_gtmfs.extend(gtmfs)

        self.stats_collector.update_global_stats('gtmfs_created', len(all_gtmfs))
        self.stats_collector.update_global_stats('gtmfs_failed', len(ehr_cases) - len(all_gtmfs))

        logger.info(f"Stage 2 complete: Created {len(all_gtmfs)} GTMFs")
        return all_gtmfs

    def run_stage_3_profile_generation(self, gtmfs: list):
        """Stage 3: Profile Generation"""
        logger.info("\n" + "=" * 60)
        logger.info("STAGE 3: PROFILE GENERATION")
        logger.info("=" * 60)

        profile_agent = ProfileGeneratorAgent(
            output_dir=self.config['outputs']['profiles_dir']
        )

        profile_types = self.config['experiment']['profile_types']
        all_profiles = profile_agent.generate_batch(gtmfs, profile_types)
        profile_agent.save_profiles(all_profiles)

        # Update stats
        profile_counts = {}
        for profile in all_profiles:
            ptype = profile['profile_type']
            profile_counts[ptype] = profile_counts.get(ptype, 0) + 1

        self.stats_collector.update_global_stats('profiles_generated', profile_counts)

        logger.info(f"Stage 3 complete: Generated {len(all_profiles)} profiles")
        return all_profiles

    def run_stage_4_dialogue_generation(self, profiles: list):
        """Stage 4: Dialogue Generation with iterative judge evaluation"""
        logger.info("\n" + "=" * 60)
        logger.info("STAGE 4: DIALOGUE GENERATION WITH JUDGE EVALUATION")
        logger.info("=" * 60)

        # Initialize LLM clients
        doctor_config = self.config['models']['dialogue_doctor']
        patient_config = self.config['models']['dialogue_patient']
        judge_config = self.config['models']['judge']

        doctor_llm = LLMClient(
            api_key=os.getenv(doctor_config['api_key_env']),
            model_name=doctor_config['model_name']
        )

        patient_llm = LLMClient(
            api_key=os.getenv(patient_config['api_key_env']),
            model_name=patient_config['model_name']
        )

        judge_llm = LLMClient(
            api_key=os.getenv(judge_config['api_key_env']),
            model_name=judge_config['model_name']
        )

        # Initialize agents
        dialogue_orchestrator = DialogueOrchestratorAgent(
            max_turns=self.config['dialogue']['max_turns']
        )

        judge_agent = JudgeAgent(
            llm_client=judge_llm,
            threshold_score=self.config['judge']['threshold_score'],
            few_shot_examples_path=self.config['judge']['few_shot_examples_path']
        )

        prompt_improver = PromptImprovementAgent()

        max_attempts = self.config['judge']['max_attempts']
        successful_dialogues = []

        # Process each profile
        for idx, profile in enumerate(profiles):
            profile_id = profile['profile_id']
            logger.info(f"\n--- Processing profile {idx + 1}/{len(profiles)}: {profile_id} ---")

            # Initialize agents for this profile
            patient_agent = PatientAgent(profile, patient_llm)
            doctor_agent = DoctorAgent(doctor_llm)

            success = False
            final_dialogue = None
            final_decision = "UNREALISTIC"
            final_score = 0.0

            # Iterative generation with judge feedback
            for attempt in range(1, max_attempts + 1):
                logger.info(f"Attempt {attempt}/{max_attempts}")

                # Generate dialogue
                dialogue, transcript = dialogue_orchestrator.generate_dialogue(patient_agent, doctor_agent)

                # Judge evaluation
                decision, score, feedback = judge_agent.evaluate_dialogue(transcript, profile)
                judge_agent.save_evaluation(profile_id, attempt, decision, score, feedback)

                logger.info(f"Judge decision: {decision} (score: {score:.2f})")

                if decision == "REALISTIC":
                    success = True
                    final_dialogue = dialogue
                    final_decision = decision
                    final_score = score
                    dialogue_orchestrator.save_dialogue(dialogue, profile_id, attempt)
                    logger.info(f"✓ Dialogue accepted on attempt {attempt}")
                    break
                else:
                    # Apply feedback for next attempt
                    if attempt < max_attempts:
                        improvement_prompt = prompt_improver.generate_improvement_prompt(feedback)
                        patient_agent.update_prompt(improvement_prompt)
                        doctor_agent.update_prompt(improvement_prompt)
                        logger.info(f"✗ Dialogue rejected, applying improvements for next attempt")

            # Record stats
            profile_stat = {
                "profile_id": profile_id,
                "profile_type": profile['profile_type'],
                "attempts_total": attempt,
                "success": success,
                "success_attempt_index": attempt if success else None,
                "final_score": final_score,
                "judge_scores": []
            }
            self.stats_collector.add_profile_stats(profile_stat)

            if success:
                successful_dialogues.append({
                    "profile": profile,
                    "dialogue": final_dialogue
                })

        logger.info(f"\nStage 4 complete: {len(successful_dialogues)}/{len(profiles)} dialogues accepted")
        return successful_dialogues

    def run_stage_5_summarization_and_sts(self, successful_dialogues: list, ehr_cases: list):
        """Stage 5: Summarization and STS Evaluation"""
        logger.info("\n" + "=" * 60)
        logger.info("STAGE 5: SUMMARIZATION AND STS EVALUATION")
        logger.info("=" * 60)

        # Initialize summarizers and STS evaluator
        summarizer_config = self.config['models']['summarizer']
        summarizer_llm = LLMClient(
            api_key=os.getenv(summarizer_config['api_key_env']),
            model_name=summarizer_config['model_name']
        )

        ehr_summarizer = EHRSummarizerAgent(summarizer_llm)
        dialogue_summarizer = DialogueSummarizerAgent(summarizer_llm)
        sts_evaluator = STSEvaluatorAgent(self.config['models']['sts']['model_name'])

        # Create lookup for EHR cases
        ehr_lookup = {case['hadm_id']: case for case in ehr_cases}

        # Process each successful dialogue
        for item in successful_dialogues:
            profile = item['profile']
            dialogue = item['dialogue']

            profile_id = profile['profile_id']
            hadm_id = profile['hadm_id']
            subject_id = profile['subject_id']

            logger.info(f"Processing {profile_id}")

            # Get corresponding EHR case
            ehr_case = ehr_lookup.get(hadm_id)
            if not ehr_case:
                logger.warning(f"No EHR case found for hadm_id {hadm_id}")
                continue

            # Generate summaries
            ehr_summary = ehr_summarizer.summarize(ehr_case)
            ehr_summarizer.save_summary(hadm_id, subject_id, ehr_summary)

            dialogue_summary = dialogue_summarizer.summarize(dialogue)
            dialogue_summarizer.save_summary(profile_id, dialogue_summary)

            # Compute STS
            sts_score = sts_evaluator.evaluate(ehr_summary, dialogue_summary, profile_id, hadm_id, subject_id)

            # Update stats
            for stat in self.stats_collector.per_profile_stats:
                if stat['profile_id'] == profile_id:
                    stat['sts_score'] = sts_score
                    break

        logger.info("Stage 5 complete: Summarization and STS evaluation done")

    def run(self):
        """Run the complete pipeline"""
        logger.info("\n" + "=" * 80)
        logger.info("STARTING SYNTHETIC PATIENT-PHYSICIAN CONVERSATION FRAMEWORK")
        logger.info("=" * 80)

        # Save run configuration
        self.save_run_config()

        try:
            # Stage 1: EHR Retrieval
            ehr_cases = self.run_stage_1_ehr_retrieval()

            # Stage 2: GTMF Creation
            gtmfs = self.run_stage_2_gtmf_creation(ehr_cases)

            # Stage 3: Profile Generation
            profiles = self.run_stage_3_profile_generation(gtmfs)

            # Stage 4: Dialogue Generation with Judge
            successful_dialogues = self.run_stage_4_dialogue_generation(profiles)

            # Stage 5: Summarization and STS
            self.run_stage_5_summarization_and_sts(successful_dialogues, ehr_cases)

            # Save statistics
            self.stats_collector.save_stats()
            self.stats_collector.print_summary()

            logger.info("\n" + "=" * 80)
            logger.info("PIPELINE COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise


def main():
    """Main entry point"""
    orchestrator = PipelineOrchestrator()
    orchestrator.run()


if __name__ == "__main__":
    main()
