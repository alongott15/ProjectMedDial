import json
import logging
import os
import time
from Utils.partial_profile import generate_partial_profiles
from Agents.PatientAgent import PatientAgent
from Agents.DoctorAgent import DoctorAgent
from Agents.CoachAgent import CoachAgent
from Agents.SummarizerAgent import SummarizerAgent
from Agents.ValidatorAgent import ValidatorAgent  # Updated import
from simulation import simulate_dialogue

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_sota_quality_score_from_feedback(feedback: str) -> float:
    """Extract numerical quality score from SOTA coach feedback"""
    import re
    
    # Look for SOTA score patterns in feedback
    sota_score_patterns = [
        r'Overall SOTA Score[:\s]*(\d+\.\d+)',
        r'overall_sota_score[:\s]*(\d+\.\d+)',
        r'SOTA.*?Score[:\s]*(\d+\.\d+)',
        r'Combined Score.*?(\d+\.\d+)',
        r'Score: (\d+\.\d+)'
    ]
    
    for pattern in sota_score_patterns:
        match = re.search(pattern, feedback, re.IGNORECASE)
        if match:
            try:
                score = float(match.group(1))
                # Ensure score is in valid range
                return max(0.0, min(1.0, score))
            except ValueError:
                continue
    
    # Look for quality rating and convert to score
    quality_ratings = {
        'excellent': 0.90,
        'very good': 0.85,
        'good': 0.75,
        'acceptable': 0.65,
        'needs_improvement': 0.45,
        'poor': 0.25,
        'failed': 0.10
    }
    
    feedback_lower = feedback.lower()
    for rating, score in quality_ratings.items():
        if rating in feedback_lower:
            return score
    
    # Enhanced pattern matching for SOTA metrics
    if "realistic" in feedback_lower and "unrealistic" not in feedback_lower:
        # Look for specific metric scores to estimate overall quality
        metric_patterns = [
            r'semantic.*?(\d+\.\d+)',
            r'naturalness.*?(\d+\.\d+)',
            r'safety.*?(\d+\.\d+)',
            r'progressive.*?(\d+\.\d+)'
        ]
        
        scores = []
        for pattern in metric_patterns:
            match = re.search(pattern, feedback_lower)
            if match:
                try:
                    score = float(match.group(1))
                    scores.append(score)
                except ValueError:
                    continue
        
        if scores:
            return min(1.0, sum(scores) / len(scores))
        else:
            return 0.78  # Default good score for realistic dialogue
    
    elif "unrealistic" in feedback_lower:
        return 0.35  # Lower score for unrealistic dialogue
    
    # Default fallback
    return 0.50

def validate_profile_completeness(profile: dict) -> tuple[bool, list]:
    """Validate that profile has necessary components for realistic dialogue"""
    issues = []
    
    # Check for essential components
    core_fields = profile.get("Core_Fields", {})
    context_fields = profile.get("Context_Fields", {})
    additional_context = profile.get("Additional_Context", {})
    
    # Validate symptoms
    symptoms = core_fields.get("Symptoms", [])
    if not symptoms:
        issues.append("No symptoms specified - dialogue may lack medical substance")
    else:
        valid_symptoms = [s for s in symptoms if isinstance(s, dict) and s.get("description", "").strip()]
        if not valid_symptoms:
            issues.append("No valid symptom descriptions found")
    
    # Validate demographics
    demographics = context_fields.get("Patient_Demographics", {})
    if not demographics.get("Age") or demographics.get("Age", 0) == 0:
        issues.append("Missing or invalid patient age")
    if not demographics.get("Sex") or demographics.get("Sex") == "not provided":
        issues.append("Missing patient sex/gender")
    
    # Validate chief complaint
    chief_complaint = additional_context.get("Chief_Complaint", "")
    if not chief_complaint or chief_complaint == "not provided":
        issues.append("Missing chief complaint - patient may lack clear reason for visit")
    
    # Profile is valid if it has at least symptoms and basic demographics
    is_valid = (len(valid_symptoms) > 0 if 'valid_symptoms' in locals() else False) and \
               demographics.get("Age", 0) > 0
    
    return is_valid, issues

def enhance_profile_if_needed(profile: dict) -> dict:
    """Enhance profile with defaults if critical information is missing"""
    enhanced_profile = profile.copy()
    
    # Ensure chief complaint exists
    if not enhanced_profile.get("Additional_Context", {}).get("Chief_Complaint") or \
       enhanced_profile.get("Additional_Context", {}).get("Chief_Complaint") == "not provided":
        
        # Generate chief complaint from first symptom
        symptoms = enhanced_profile.get("Core_Fields", {}).get("Symptoms", [])
        if symptoms and isinstance(symptoms[0], dict):
            symptom_desc = symptoms[0].get("description", "")
            if symptom_desc:
                if "Additional_Context" not in enhanced_profile:
                    enhanced_profile["Additional_Context"] = {}
                enhanced_profile["Additional_Context"]["Chief_Complaint"] = f"Experiencing {symptom_desc.lower()}"
    
    return enhanced_profile

def main():
    logger.info("Starting enhanced dialogue generation pipeline with SOTA evaluation system")
    
    # Load ground truth data
    with open("gtmf/gtmf_example_azure.json", "r", encoding="utf-8") as infile:
        gt_data = json.load(infile)
    
    if not gt_data:
        logger.error("No GTMF data loaded. Exiting.")
        return
    
    # Select subset for processing
    full_profiles = gt_data[20:40]  # Process 20 profiles
    logger.info(f"Processing {len(full_profiles)} profiles with SOTA evaluation system")

    # Generate partial profiles
    partial_profile_objects = []
    
    for idx, full_profile_dict in enumerate(full_profiles):
        partial_profile_dict = generate_partial_profiles(full_profile_dict)
        
        # Validate and enhance profile
        is_valid, validation_issues = validate_profile_completeness(partial_profile_dict)
        if validation_issues:
            logger.warning(f"Profile validation issues for {partial_profile_dict.get('row_id')}: {validation_issues}")
        
        if not is_valid:
            logger.warning(f"Skipping invalid profile {partial_profile_dict.get('row_id')}")
            continue
            
        enhanced_profile = enhance_profile_if_needed(partial_profile_dict)
        partial_profile_objects.append(enhanced_profile)
    
    logger.info(f"Valid profiles for processing: {len(partial_profile_objects)}")
    
    # Initialize SOTA evaluation pipeline
    logger.info("🚀 Initializing SOTA evaluation pipeline...")
    
    try:
        summarizer_agent = SummarizerAgent()
        validator_agent = ValidatorAgent()  # New SOTA validator
        coach_agent = CoachAgent(
            summarizer_agent=summarizer_agent,
            validator_agent=validator_agent,  # SOTA validator integration
            sota_realism_threshold=0.75  # Adjusted threshold for SOTA metrics
        )
        logger.info("✅ SOTA evaluation system initialized successfully!")
    except Exception as e:
        logger.error(f"Failed to initialize SOTA evaluation system: {e}")
        return
    
    # Configuration
    max_cycles = 3
    max_processing_time = 300  # 5 minutes per dialogue
    
    # Process each profile
    successful_dialogues = 0
    failed_dialogues = 0
    quality_scores = []
    sota_metrics_summary = {
        'semantic_scores': [],
        'naturalness_scores': [],
        'safety_scores': [],
        'progressive_disclosure_scores': [],
        'overall_sota_scores': []
    }
    
    for idx, current_partial_profile in enumerate(partial_profile_objects):
        start_time = time.time()
        current_full_profile = full_profiles[idx] if idx < len(full_profiles) else None
        
        if not current_full_profile:
            logger.error(f"Could not find matching full profile for index {idx}. Skipping.")
            continue

        profile_id = f"{current_partial_profile.get('row_id')}_{current_partial_profile.get('subject_id')}"
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing profile {idx+1}/{len(partial_profile_objects)}: ID={profile_id}")
        logger.info(f"Symptoms: {len(current_partial_profile.get('Core_Fields', {}).get('Symptoms', []))}")
        logger.info(f"Chief Complaint: {current_partial_profile.get('Additional_Context', {}).get('Chief_Complaint', 'Not specified')}")
        
        # Initialize agents for this profile
        try:
            doctor_agent = DoctorAgent(patient_profile=current_partial_profile)
            patient_agent = PatientAgent(profile=current_partial_profile)
        except Exception as e:
            logger.error(f"Failed to initialize agents for profile {profile_id}: {e}")
            failed_dialogues += 1
            continue
        
        cycle = 0
        realistic_label = "unrealistic"
        final_conversation = None
        final_transcript = ""
        feedback_from_coach = "No review performed."
        final_quality_score = 0.0
        final_sota_metrics = {}

        # Enhanced dialogue generation loop with SOTA evaluation
        while realistic_label != "realistic" and cycle < max_cycles:
            cycle_start = time.time()
            logger.info(f"  🔄 SOTA dialogue attempt {cycle+1}/{max_cycles}")
            
            # Check for timeout
            if time.time() - start_time > max_processing_time:
                logger.warning(f"  ⏰ Processing timeout reached for profile {profile_id}")
                break
            
            try:
                # Generate dialogue
                conversation, transcript = simulate_dialogue(
                    doctor_agent, patient_agent,
                    max_turns=16,
                    consecutive_confusion_limit=2,
                    loop_detection_window=4
                )
                
                if not conversation or len(conversation) < 4:
                    logger.warning(f"  Generated dialogue too short (turns: {len(conversation)})")
                    cycle += 1
                    continue
                
                # SOTA coaching review with enhanced evaluation
                logger.info(f"  🔬 Running SOTA evaluation...")
                realistic_label, feedback_from_coach = coach_agent.review_dialogue(
                    transcript, current_full_profile
                )
                
                # Extract quality score from SOTA feedback
                quality_score = extract_sota_quality_score_from_feedback(feedback_from_coach)
                
                # Extract SOTA metrics for tracking
                sota_metrics = extract_sota_metrics_from_feedback(feedback_from_coach)
                
                logger.info(f"  📊 Cycle {cycle+1} result: {realistic_label} (SOTA Score: {quality_score:.3f})")
                logger.info(f"  📈 Key SOTA metrics: Semantic={sota_metrics.get('semantic', 0):.2f}, "
                           f"Naturalness={sota_metrics.get('naturalness', 0):.2f}, "
                           f"Safety={sota_metrics.get('safety', 0):.2f}")
                logger.info(f"  💬 Dialogue: {len(conversation)} turns, {len(transcript.split())} words")
                
                if realistic_label == "realistic":
                    final_conversation = conversation
                    final_transcript = transcript
                    final_quality_score = quality_score
                    final_sota_metrics = sota_metrics
                    logger.info(f"  ✅ Dialogue accepted as realistic with SOTA score {quality_score:.3f}")
                    break
                else:
                    # Enhanced feedback incorporation with SOTA insights
                    if cycle < max_cycles - 1:  # Don't update on last cycle
                        # Extract specific improvement areas from SOTA feedback
                        improvement_focus = extract_improvement_focus_from_sota_feedback(feedback_from_coach)
                        enhanced_feedback = f"{feedback_from_coach}\n\nFocus on: {improvement_focus}"
                        
                        doctor_agent.update_prompt(enhanced_feedback)
                        patient_agent.update_prompt(enhanced_feedback)
                        logger.info(f"  🔧 Agents updated with SOTA-based improvement guidance")
                    
                cycle += 1
                
            except Exception as e:
                logger.error(f"  ❌ Error during SOTA dialogue cycle {cycle+1}: {e}", exc_info=True)
                cycle += 1
                continue
        
        processing_time = time.time() - start_time
        
        # Final assessment and save with SOTA metrics
        if realistic_label == "realistic" and final_conversation:
            try:
                # Generate summary and annotations
                clinical_note, structured_annotations = summarizer_agent.summarize_and_annotate(final_transcript)
                
                # Prepare enhanced result with SOTA metrics
                result = {
                    "partial_profile": current_full_profile,
                    "dialogue": final_conversation,
                    "transcript": final_transcript,
                    "clinical_note": clinical_note,
                    "annotations": structured_annotations,
                    "sota_evaluation": {
                        "coach_feedback": feedback_from_coach,
                        "quality_score": final_quality_score,
                        "sota_metrics": final_sota_metrics,
                        "evaluation_method": "SOTA_multi_metric"
                    },
                    "refinement_cycles": cycle,
                    "processing_time": processing_time,
                    "dialogue_stats": {
                        "turn_count": len(final_conversation),
                        "word_count": len(final_transcript.split()),
                        "doctor_turns": len([t for t in final_conversation if t.get('role') == 'Doctor']),
                        "patient_turns": len([t for t in final_conversation if t.get('role') == 'Patient'])
                    }
                }
                
                # Save result
                os.makedirs("output_sota", exist_ok=True)
                output_path = f"output_sota/dialogue_output_{profile_id}.json"
                with open(output_path, "w", encoding="utf-8") as outfile:
                    json.dump(result, outfile, indent=2)
                
                successful_dialogues += 1
                quality_scores.append(final_quality_score)
                
                # Track SOTA metrics for summary
                sota_metrics_summary['semantic_scores'].append(final_sota_metrics.get('semantic', 0))
                sota_metrics_summary['naturalness_scores'].append(final_sota_metrics.get('naturalness', 0))
                sota_metrics_summary['safety_scores'].append(final_sota_metrics.get('safety', 0))
                sota_metrics_summary['progressive_disclosure_scores'].append(final_sota_metrics.get('progressive_disclosure', 0))
                sota_metrics_summary['overall_sota_scores'].append(final_quality_score)
                
                logger.info(f"  ✅ Success! Saved SOTA-evaluated dialogue to {output_path}")
                
            except Exception as e:
                logger.error(f"  ❌ Error during summarization/saving for {profile_id}: {e}")
                failed_dialogues += 1
        else:
            logger.error(f"  ❌ Failed to generate realistic dialogue for {profile_id} after {cycle} cycles")
            failed_dialogues += 1
    
    # Enhanced final summary with SOTA metrics
    logger.info(f"\n{'='*60}")
    logger.info("SOTA DIALOGUE GENERATION SUMMARY")
    logger.info(f"{'='*60}")
    
    total_processed = successful_dialogues + failed_dialogues
    logger.info(f"Total profiles processed: {total_processed}")
    logger.info(f"Successful dialogues: {successful_dialogues}")
    logger.info(f"Failed dialogues: {failed_dialogues}")
    logger.info(f"Success rate: {successful_dialogues/total_processed:.1%}" if total_processed > 0 else "Success rate: 0%")
    
    if quality_scores:
        avg_quality = sum(quality_scores) / len(quality_scores)
        high_quality = len([q for q in quality_scores if q >= 0.85])
        medium_quality = len([q for q in quality_scores if 0.7 <= q < 0.85])
        low_quality = len([q for q in quality_scores if q < 0.7])
        
        logger.info(f"\n🎯 SOTA Quality Assessment:")
        logger.info(f"Average SOTA score: {avg_quality:.3f}")
        logger.info(f"Quality distribution:")
        logger.info(f"  Excellent (≥0.85): {high_quality}")
        logger.info(f"  Good (0.7-0.85): {medium_quality}")
        logger.info(f"  Needs improvement (<0.7): {low_quality}")
        
        # SOTA metrics breakdown
        if sota_metrics_summary['overall_sota_scores']:
            logger.info(f"\n📊 SOTA Metrics Breakdown:")
            for metric, scores in sota_metrics_summary.items():
                if scores:
                    avg_score = sum(scores) / len(scores)
                    logger.info(f"  {metric.replace('_', ' ').title()}: {avg_score:.3f}")
    
    logger.info("\n🚀 SOTA dialogue generation pipeline completed successfully!")
    logger.info("✨ Key improvements over traditional F1-based evaluation:")
    logger.info("  • Better correlation with human expert judgment")
    logger.info("  • Medical safety assessment integration")
    logger.info("  • Progressive disclosure quality evaluation")
    logger.info("  • Natural conversation flow assessment")
    logger.info("  • Comprehensive dialogue realism scoring")

def extract_sota_metrics_from_feedback(feedback: str) -> dict:
    """Extract individual SOTA metrics from feedback for tracking"""
    import re
    
    metrics = {
        'semantic': 0.0,
        'naturalness': 0.0,
        'safety': 0.0,
        'progressive_disclosure': 0.0,
        'medical_coverage': 0.0,
        'clinical_reasoning': 0.0
    }
    
    # Pattern matching for SOTA metrics
    patterns = {
        'semantic': r'(?:semantic|bertscore).*?(\d+\.\d+)',
        'naturalness': r'naturalness.*?(\d+\.\d+)',
        'safety': r'safety.*?(\d+\.\d+)',
        'progressive_disclosure': r'progressive.*?disclosure.*?(\d+\.\d+)',
        'medical_coverage': r'medical.*?coverage.*?(\d+\.\d+)',
        'clinical_reasoning': r'clinical.*?reasoning.*?(\d+\.\d+)'
    }
    
    feedback_lower = feedback.lower()
    
    for metric, pattern in patterns.items():
        match = re.search(pattern, feedback_lower)
        if match:
            try:
                metrics[metric] = float(match.group(1))
            except ValueError:
                pass
    
    return metrics

def extract_improvement_focus_from_sota_feedback(feedback: str) -> str:
    """Extract specific improvement focus from SOTA feedback"""
    
    # Look for priority improvements section
    if "priority improvements" in feedback.lower():
        lines = feedback.split('\n')
        for i, line in enumerate(lines):
            if "priority improvements" in line.lower():
                # Extract next few lines as improvement focus
                improvements = []
                for j in range(i+1, min(i+4, len(lines))):
                    if lines[j].strip() and ('•' in lines[j] or '🔹' in lines[j]):
                        improvements.append(lines[j].strip())
                if improvements:
                    return '; '.join(improvements[:2])  # Top 2 improvements
    
    # Fallback to general improvement areas
    improvement_keywords = {
        'progressive disclosure': 'gradual symptom revelation',
        'naturalness': 'conversation flow and empathy',
        'safety': 'medical safety and appropriateness',
        'semantic': 'medical content alignment',
        'empathy': 'doctor empathy and responsiveness'
    }
    
    feedback_lower = feedback.lower()
    for keyword, focus in improvement_keywords.items():
        if keyword in feedback_lower and ('improve' in feedback_lower or 'enhance' in feedback_lower):
            return focus
    
    return "natural dialogue flow and medical appropriateness"

if __name__ == "__main__":
    main()