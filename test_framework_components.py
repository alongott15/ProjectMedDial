"""
Test script for validating synthetic dialogue framework components.

This script tests individual components without requiring full database access.
"""

import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_prompts():
    """Test prompt loading."""
    logger.info("Testing prompt loader...")
    from prompts.prompt_loader import get_prompt_loader

    loader = get_prompt_loader()

    # Test all prompts
    prompts = {
        "base_system": loader.get_base_system_prompt(),
        "gtmf": loader.get_gtmf_extraction_prompt(),
        "patient": loader.get_patient_agent_prompt(),
        "doctor": loader.get_doctor_agent_prompt(),
        "judge": loader.get_judge_agent_prompt(),
        "ehr_summarizer": loader.get_ehr_summarizer_prompt(),
        "dialogue_summarizer": loader.get_dialogue_summarizer_prompt(),
        "prompt_improvement": loader.get_prompt_improvement_prompt()
    }

    for name, prompt in prompts.items():
        assert prompt, f"{name} prompt is empty"
        assert len(prompt) > 0, f"{name} prompt has no content"
        logger.info(f"  ✓ {name} prompt loaded ({len(prompt)} chars)")

    logger.info("✓ Prompt loading tests passed\n")


def test_light_case_filter():
    """Test light case filter."""
    logger.info("Testing light case filter...")
    from Utils.light_case_filter import LightCaseFilter

    filter_obj = LightCaseFilter()

    # Test cases
    test_cases = [
        {
            "text": "Patient presents with cough and sore throat for 3 days. Low-grade fever noted.",
            "expected": True,
            "description": "Light case with cough and sore throat"
        },
        {
            "text": "Patient admitted to ICU with septic shock. Intubated and on mechanical ventilation.",
            "expected": False,
            "description": "Severe ICU case"
        },
        {
            "text": "Chief complaint: headache and mild dizziness. No fever or other symptoms.",
            "expected": True,
            "description": "Light case with headache"
        },
        {
            "text": "Patient diagnosed with malignancy. Scheduled for surgical resection.",
            "expected": False,
            "description": "Cancer case"
        }
    ]

    for test_case in test_cases:
        passed, reason = filter_obj.filter_case(test_case["text"])
        assert passed == test_case["expected"], \
            f"Filter failed for: {test_case['description']} (expected={test_case['expected']}, got={passed})"
        logger.info(f"  ✓ {test_case['description']}: {passed} ({reason})")

    logger.info("✓ Light case filter tests passed\n")


def test_profile_generator():
    """Test profile generator."""
    logger.info("Testing profile generator...")
    from Agents.ProfileGeneratorAgent import ProfileGeneratorAgent

    agent = ProfileGeneratorAgent()

    # Mock GTMF
    mock_gtmf = {
        "row_id": 1,
        "subject_id": 12345,
        "hadm_id": 67890,
        "Core_Fields": {
            "Symptoms": [
                {"description": "cough", "onset": "3 days ago", "severity": "mild"}
            ],
            "Diagnoses": [
                {"primary": "Upper respiratory infection", "notes": "Viral"}
            ],
            "Treatment_Options": [
                {"treatment": "Rest and fluids", "details": "Symptomatic care"}
            ]
        },
        "Context_Fields": {
            "Patient_Demographics": {
                "Age": 35,
                "Sex": "Female"
            }
        },
        "Additional_Context": {
            "Chief_Complaint": "Cough and sore throat"
        }
    }

    # Test all profile types
    full_profile = agent.generate_full_profile(mock_gtmf)
    assert full_profile["profile_type"] == "FULL"
    assert len(full_profile["Core_Fields"]["Diagnoses"]) > 0
    logger.info("  ✓ FULL profile generated")

    no_dx_profile = agent.generate_no_diagnosis_profile(mock_gtmf)
    assert no_dx_profile["profile_type"] == "NO_DIAGNOSIS"
    assert len(no_dx_profile["Core_Fields"]["Diagnoses"]) == 0
    assert len(no_dx_profile["Core_Fields"]["Treatment_Options"]) > 0
    logger.info("  ✓ NO_DIAGNOSIS profile generated")

    no_dx_tx_profile = agent.generate_no_diagnosis_no_treatment_profile(mock_gtmf)
    assert no_dx_tx_profile["profile_type"] == "NO_DIAGNOSIS_NO_TREATMENT"
    assert len(no_dx_tx_profile["Core_Fields"]["Diagnoses"]) == 0
    assert len(no_dx_tx_profile["Core_Fields"]["Treatment_Options"]) == 0
    logger.info("  ✓ NO_DIAGNOSIS_NO_TREATMENT profile generated")

    logger.info("✓ Profile generator tests passed\n")


def test_stats_collector():
    """Test statistics collector."""
    logger.info("Testing stats collector...")
    from Utils.stats_collector import StatsCollector
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        collector = StatsCollector(output_dir=tmpdir)

        # Create test profiles
        for i in range(5):
            profile_id = f"test_profile_{i}"
            collector.create_profile_stats(
                profile_id=profile_id,
                subject_id=i * 100,
                hadm_id=i * 1000,
                profile_type="NO_DIAGNOSIS_NO_TREATMENT"
            )

            # Simulate attempts
            for attempt in range(1, 3):
                score = 0.5 + (attempt * 0.2)
                decision = "REALISTIC" if score >= 0.6 else "UNREALISTIC"
                collector.record_attempt(profile_id, attempt, score, decision)

            # Record STS if successful
            if collector.profile_stats[profile_id].success:
                collector.record_sts_score(profile_id, 0.75)

        # Compute global stats
        global_stats = collector.compute_global_stats()

        assert "profile_summary" in global_stats
        assert global_stats["profile_summary"]["total_profiles"] == 5
        logger.info(f"  ✓ Tracked {global_stats['profile_summary']['total_profiles']} profiles")
        logger.info(f"  ✓ Success rate: {global_stats['profile_summary']['success_rate']:.1%}")

        # Save stats
        collector.save_all_stats()
        logger.info("  ✓ Statistics saved")

    logger.info("✓ Stats collector tests passed\n")


def test_configuration():
    """Test configuration system."""
    logger.info("Testing configuration system...")
    from config import PipelineConfig, create_default_config
    import tempfile

    # Create default config
    config = create_default_config()

    assert config.run_name == "synthetic_dialogue_run"
    assert config.database.db_batch_size == 50
    assert config.judge.threshold == 0.6
    logger.info("  ✓ Default configuration created")

    # Test serialization
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = f"{tmpdir}/test_config.json"
        yaml_path = f"{tmpdir}/test_config.yaml"

        config.to_json(json_path)
        config.to_yaml(yaml_path)

        # Test deserialization
        config_from_json = PipelineConfig.from_json(json_path)
        config_from_yaml = PipelineConfig.from_yaml(yaml_path)

        assert config_from_json.run_name == config.run_name
        assert config_from_yaml.database.db_batch_size == config.database.db_batch_size

        logger.info("  ✓ Configuration serialization/deserialization works")

    logger.info("✓ Configuration tests passed\n")


def test_sts_evaluator():
    """Test STS evaluator (if sentence-transformers is available)."""
    logger.info("Testing STS evaluator...")

    try:
        from Utils.sts_evaluator import STSEvaluator

        evaluator = STSEvaluator()

        # Test similarity
        text1 = "Patient presents with cough and fever for three days."
        text2 = "The patient has had a cough and elevated temperature for 3 days."
        text3 = "Patient underwent cardiac surgery yesterday."

        score_similar = evaluator.compute_similarity(text1, text2)
        score_dissimilar = evaluator.compute_similarity(text1, text3)

        logger.info(f"  ✓ Similar texts score: {score_similar:.4f}")
        logger.info(f"  ✓ Dissimilar texts score: {score_dissimilar:.4f}")

        assert score_similar > score_dissimilar, "Similar texts should have higher score"

        logger.info("✓ STS evaluator tests passed\n")

    except ImportError as e:
        logger.warning(f"  ⚠ STS evaluator test skipped (missing dependency: {e})\n")


def main():
    """Run all tests."""
    logger.info("=" * 80)
    logger.info("SYNTHETIC DIALOGUE FRAMEWORK - COMPONENT TESTS")
    logger.info("=" * 80 + "\n")

    tests = [
        ("Prompts", test_prompts),
        ("Light Case Filter", test_light_case_filter),
        ("Profile Generator", test_profile_generator),
        ("Statistics Collector", test_stats_collector),
        ("Configuration", test_configuration),
        ("STS Evaluator", test_sts_evaluator)
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            logger.error(f"✗ {name} test failed: {e}", exc_info=True)
            failed += 1

    logger.info("=" * 80)
    logger.info(f"TEST SUMMARY: {passed} passed, {failed} failed")
    logger.info("=" * 80)

    return failed == 0


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
