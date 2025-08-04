# Agents/ValidatorAgent_Enhanced.py
"""
MINIMAL CHANGES: Enhanced ValidatorAgent with advanced metrics integration
"""
import logging
import numpy as np

# Import the new advanced components
from Utils.medical_validator import AdvancedMedicalValidator, validate_with_advanced_metrics
from Utils.medical_knowledge_mimic import MIMICMedicalKnowledgeBase
from Utils.utils import get_db_uri

# Keep existing imports for backward compatibility
from Utils.medical_validation import validate_medical_extraction, assess_dialogue_safety

logger = logging.getLogger(__name__)

class EnhancedValidatorAgent:
    """
    MINIMAL CHANGE: Enhanced ValidatorAgent that integrates advanced validation
    while maintaining backward compatibility
    """
    
    def __init__(self, use_advanced_validation: bool = True, use_mimic_kb: bool = True):
        """
        Initialize with options for advanced validation and MIMIC knowledge base
        
        Args:
            use_advanced_validation: Whether to use advanced validation metrics
            use_mimic_kb: Whether to use MIMIC-III knowledge base
        """
        self.use_advanced_validation = use_advanced_validation
        self.use_mimic_kb = use_mimic_kb
        
        # Initialize MIMIC knowledge base if requested
        if use_mimic_kb:
            try:
                db_uri = get_db_uri()
                if db_uri:
                    self.mimic_kb = MIMICMedicalKnowledgeBase(db_uri)
                    logger.info("MIMIC-III knowledge base loaded successfully")
                else:
                    self.mimic_kb = None
                    logger.warning("Database URI not available, MIMIC-III KB disabled")
            except Exception as e:
                logger.error(f"Failed to load MIMIC-III knowledge base: {e}")
                self.mimic_kb = None
        else:
            self.mimic_kb = None
        
        # Initialize advanced validator if requested
        if use_advanced_validation:
            try:
                self.advanced_validator = AdvancedMedicalValidator(self.mimic_kb)
                logger.info("Advanced medical validator initialized")
            except Exception as e:
                logger.error(f"Failed to initialize advanced validator: {e}")
                self.advanced_validator = None
        else:
            self.advanced_validator = None
        
        # Keep backward compatibility - initialize existing validation
        self._initialize_legacy_validation()
    
    def _initialize_legacy_validation(self):
        """Initialize legacy validation for backward compatibility"""
        # This maintains the existing ValidatorAgent functionality
        try:
            from sentence_transformers import SentenceTransformer
            self.sentence_transformer = SentenceTransformer('all-MiniLM-L6-v2')
        except:
            self.sentence_transformer = None
        
        # Initialize other legacy components as needed
        logger.info("Legacy validation components initialized")
    
    def evaluate(self, ground_truth: dict, conversation_info: dict):
        """
        ENHANCED: Main evaluation method with advanced validation integration
        
        This method maintains backward compatibility while adding advanced metrics
        """
        logger.info("Starting enhanced evaluation with advanced metrics...")
        
        # Extract dialogue information
        dialogue_text = conversation_info.get('dialogue_text', 
                                            conversation_info.get('transcript', ''))
        
        if not dialogue_text:
            logger.warning("No dialogue text found for evaluation")
            return self._get_legacy_zero_scores()
        
        # MINIMAL CHANGE: Add advanced validation if available
        if self.use_advanced_validation and self.advanced_validator:
            advanced_results = self._evaluate_with_advanced_metrics(dialogue_text, ground_truth, conversation_info)
        else:
            advanced_results = {}
        
        # BACKWARD COMPATIBILITY: Run legacy validation
        legacy_results = self._evaluate_with_legacy_methods(ground_truth, conversation_info)
        
        # INTEGRATION: Combine advanced and legacy results
        combined_results = self._combine_validation_results(advanced_results, legacy_results)
        
        logger.info(f"Enhanced evaluation completed with advanced integration")
        return combined_results
    
    def _evaluate_with_advanced_metrics(self, dialogue_text: str, ground_truth: dict, 
                                   conversation_info: dict):
        """Evaluate using advanced metrics"""
        
        try:
            # Prepare clinical context from ground truth
            clinical_context = self._prepare_clinical_context(ground_truth)
            
            # Run advanced validation
            advanced_metrics = validate_with_advanced_metrics(
                dialogue_text=dialogue_text,
                reference_text=None,  # Could extract from ground truth if available
                clinical_context=clinical_context,
                mimic_knowledge_base=self.mimic_kb
            )
            
            # Convert to compatible format
            return {
                # Advanced Semantic Metrics (improved accuracy)
                'bertscore_precision': advanced_metrics.clinical_bertscore,
                'bertscore_recall': advanced_metrics.clinical_bertscore,
                'bertscore_f1': advanced_metrics.clinical_bertscore,
                
                # Advanced Medical Domain Metrics
                'medical_entity_f1': advanced_metrics.medical_entity_f1,
                'concept_precision': advanced_metrics.concept_precision,
                'concept_recall': advanced_metrics.concept_recall,
                'terminology_accuracy': advanced_metrics.terminology_accuracy,
                
                # Advanced Clinical Quality Metrics
                'clinical_completeness': advanced_metrics.clinical_completeness,
                'diagnostic_coherence': advanced_metrics.diagnostic_coherence,
                'treatment_appropriateness': advanced_metrics.treatment_appropriateness,
                'clinical_safety': advanced_metrics.clinical_safety,
                
                # Advanced Communication Metrics
                'dialogue_empathy': advanced_metrics.empathy_score,
                'dialogue_professionalism': advanced_metrics.explanation_clarity,
                'patient_centeredness': advanced_metrics.patient_centeredness,
                'information_seeking_quality': advanced_metrics.information_seeking,
                
                # Advanced Overall Quality
                'overall_advanced_score': advanced_metrics.overall_clinical_quality,
                'confidence_interval': advanced_metrics.confidence_interval,
                
                # Additional Advanced Metrics
                'clinical_bleu': advanced_metrics.clinical_bleu,
                'clinical_rouge_l': advanced_metrics.clinical_rouge_l,
                'semantic_coherence': advanced_metrics.semantic_coherence,
                
                # Quality Indicators
                'quality_indicators': advanced_metrics.quality_indicators,
                'advanced_recommendations': advanced_metrics.recommendations,
                'detailed_advanced_scores': advanced_metrics.detailed_scores
            }
            
        except Exception as e:
            logger.error(f"Advanced evaluation failed: {e}")
            return {}
    
    def _evaluate_with_legacy_methods(self, ground_truth: dict, conversation_info: dict):
        """Run legacy validation for backward compatibility"""
        
        try:
            # Extract information for legacy validation
            dialogue_text = conversation_info.get('dialogue_text', '')
            extracted_info = conversation_info.get('extracted_info', {})
            
            # Extract components for legacy validation
            symptoms = self._extract_symptoms_legacy(ground_truth, extracted_info)
            diagnoses = self._extract_diagnoses_legacy(ground_truth, extracted_info)
            treatments = self._extract_treatments_legacy(ground_truth, extracted_info)
            
            # Run legacy medical validation
            legacy_medical_validation = validate_medical_extraction(symptoms, diagnoses, treatments)
            
            # Run legacy safety assessment
            legacy_safety = assess_dialogue_safety(dialogue_text)
            
            # Calculate legacy dialogue quality (simplified)
            dialogue_naturalness = self._calculate_legacy_naturalness(dialogue_text)
            progressive_disclosure = self._calculate_legacy_progressive_disclosure(dialogue_text)
            
            return {
                # Legacy Medical Validation
                'legacy_medical_validity': legacy_medical_validation['overall_medical_validity'],
                'legacy_symptom_validity': legacy_medical_validation['symptom_validity'],
                'legacy_diagnosis_validity': legacy_medical_validation['diagnosis_validity'],
                'legacy_treatment_validity': legacy_medical_validation['treatment_validity'],
                
                # Legacy Safety
                'legacy_safety_score': legacy_safety['safety_score'],
                
                # Legacy Dialogue Quality
                'legacy_dialogue_naturalness': dialogue_naturalness,
                'legacy_progressive_disclosure': progressive_disclosure,
                
                # Legacy Overall Score
                'legacy_overall_score': (
                    legacy_medical_validation['overall_medical_validity'] * 0.4 +
                    legacy_safety['safety_score'] * 0.3 +
                    dialogue_naturalness * 0.3
                )
            }
            
        except Exception as e:
            logger.error(f"Legacy evaluation failed: {e}")
            return {}
    
    def _combine_validation_results(self, advanced_results: dict, legacy_results: dict):
        """
        INTEGRATION: Combine advanced and legacy results with intelligent weighting
        """
        
        combined = {}
        
        # Prioritize advanced results when available
        if advanced_results:
            # Use advanced metrics as primary
            combined.update(advanced_results)
            
            # Add legacy results with prefix for comparison
            for key, value in legacy_results.items():
                combined[f"legacy_{key}"] = value
            
            # Calculate hybrid scores for key metrics
            combined['hybrid_medical_quality'] = self._calculate_hybrid_medical_score(advanced_results, legacy_results)
            combined['hybrid_safety_score'] = self._calculate_hybrid_safety_score(advanced_results, legacy_results)
            combined['hybrid_overall_score'] = self._calculate_hybrid_overall_score(advanced_results, legacy_results)
            
            # Add evaluation method indicator
            combined['evaluation_method'] = 'advanced_with_legacy_comparison'
            combined['advanced_available'] = True
            
        else:
            # Fallback to legacy results
            combined.update(legacy_results)
            combined['evaluation_method'] = 'legacy_only'
            combined['advanced_available'] = False
        
        # Add MIMIC-III knowledge base status
        combined['mimic_kb_available'] = self.mimic_kb is not None
        
        # Generate evaluation summary
        combined['evaluation_summary'] = self._generate_evaluation_summary(combined)
        
        return combined
    
    def _calculate_hybrid_medical_score(self, advanced_results: dict, legacy_results: dict):
        """Calculate hybrid medical quality score"""
        
        if advanced_results and legacy_results:
            # Weight advanced more heavily (70%) but include legacy for comparison
            advanced_score = (
                advanced_results.get('medical_entity_f1', 0) * 0.3 +
                advanced_results.get('terminology_accuracy', 0) * 0.3 +
                advanced_results.get('diagnostic_coherence', 0) * 0.4
            )
            
            legacy_score = legacy_results.get('legacy_medical_validity', 0)
            
            return advanced_score * 0.7 + legacy_score * 0.3
        
        elif advanced_results:
            return (
                advanced_results.get('medical_entity_f1', 0) * 0.3 +
                advanced_results.get('terminology_accuracy', 0) * 0.3 +
                advanced_results.get('diagnostic_coherence', 0) * 0.4
            )
        
        else:
            return legacy_results.get('legacy_medical_validity', 0)
    
    def _calculate_hybrid_safety_score(self, advanced_results: dict, legacy_results: dict):
        """Calculate hybrid safety score"""
        
        if advanced_results and legacy_results:
            advanced_safety = advanced_results.get('clinical_safety', 0)
            legacy_safety = legacy_results.get('legacy_safety_score', 0)
            
            # Take the more conservative (lower) safety score
            return min(advanced_safety, legacy_safety)
        
        elif advanced_results:
            return advanced_results.get('clinical_safety', 0)
        
        else:
            return legacy_results.get('legacy_safety_score', 0)
    
    def _calculate_hybrid_overall_score(self, advanced_results: dict, legacy_results: dict):
        """Calculate hybrid overall quality score"""
        
        if advanced_results:
            return advanced_results.get('overall_advanced_score', 0)
        else:
            return legacy_results.get('legacy_overall_score', 0)
    
    def _prepare_clinical_context(self, ground_truth: dict):
        """Prepare clinical context from ground truth for advanced validation"""
        
        context = {}
        
        # Extract core medical information
        core_fields = ground_truth.get("Core_Fields", {})
        context_fields = ground_truth.get("Context_Fields", {})
        
        # Symptoms
        symptoms = []
        for symptom in core_fields.get("Symptoms", []):
            if isinstance(symptom, dict):
                symptoms.append(symptom.get("description", ""))
            else:
                symptoms.append(str(symptom))
        context['symptoms'] = symptoms
        
        # Diagnoses
        diagnoses = []
        for diagnosis in core_fields.get("Diagnoses", []):
            if isinstance(diagnosis, dict):
                diagnoses.append(diagnosis.get("primary", ""))
            else:
                diagnoses.append(str(diagnosis))
        context['diagnoses'] = diagnoses
        
        # Treatments
        treatments = []
        for treatment in core_fields.get("Treatment_Options", []):
            if isinstance(treatment, dict):
                treatments.append(treatment.get("procedure", ""))
            else:
                treatments.append(str(treatment))
        context['treatments'] = treatments
        
        # Patient demographics
        demographics = context_fields.get("Patient_Demographics", {})
        context['patient_age'] = demographics.get("Age", 0)
        context['patient_sex'] = demographics.get("Sex", "")
        
        # Medical history
        history = context_fields.get("Medical_History", {})
        if isinstance(history, dict):
            context['medical_history'] = history.get("Past_Medical_History", "")
        else:
            context['medical_history'] = str(history)
        
        return context
    
    def _generate_evaluation_summary(self, combined_results: dict):
        """Generate comprehensive evaluation summary"""
        
        summary = {
            'evaluation_method': combined_results.get('evaluation_method', 'unknown'),
            'overall_quality': self._get_overall_quality_rating(combined_results),
            'key_strengths': [],
            'improvement_areas': [],
            'safety_status': self._get_safety_status(combined_results),
            'clinical_readiness': self._get_clinical_readiness(combined_results)
        }
        
        # Identify strengths and weaknesses
        if combined_results.get('advanced_available'):
            # Use advanced metrics for analysis
            if combined_results.get('medical_entity_f1', 0) > 0.7:
                summary['key_strengths'].append('High medical entity recognition accuracy')
            
            if combined_results.get('empathy_score', 0) > 0.6:
                summary['key_strengths'].append('Strong empathetic communication')
            
            if combined_results.get('clinical_safety', 0) > 0.8:
                summary['key_strengths'].append('Good clinical safety compliance')
            
            # Improvement areas
            if combined_results.get('terminology_accuracy', 0) < 0.7:
                summary['improvement_areas'].append('Medical terminology accuracy needs improvement')
            
            if combined_results.get('diagnostic_coherence', 0) < 0.6:
                summary['improvement_areas'].append('Diagnostic reasoning coherence could be enhanced')
        
        else:
            # Use legacy metrics for analysis
            if combined_results.get('legacy_medical_validity', 0) > 0.7:
                summary['key_strengths'].append('Adequate medical content validation')
            
            if combined_results.get('legacy_safety_score', 0) > 0.8:
                summary['key_strengths'].append('Good safety compliance')
        
        return summary
    
    def _get_overall_quality_rating(self, results: dict):
        """Get overall quality rating"""
        
        if results.get('advanced_available'):
            overall_score = results.get('overall_advanced_score', 0)
        else:
            overall_score = results.get('legacy_overall_score', 0)
        
        if overall_score >= 0.85:
            return 'Excellent'
        elif overall_score >= 0.7:
            return 'Good'
        elif overall_score >= 0.55:
            return 'Fair'
        else:
            return 'Needs Improvement'
    
    def _get_safety_status(self, results: dict):
        """Get safety status"""
        
        safety_score = results.get('hybrid_safety_score', 
                                 results.get('clinical_safety', 
                                           results.get('legacy_safety_score', 0)))
        
        if safety_score >= 0.9:
            return 'Excellent'
        elif safety_score >= 0.8:
            return 'Good'
        elif safety_score >= 0.6:
            return 'Acceptable'
        else:
            return 'Needs Review'
    
    def _get_clinical_readiness(self, results: dict):
        """Assess clinical readiness"""
        
        overall_score = results.get('hybrid_overall_score', 
                                  results.get('overall_advanced_score', 
                                            results.get('legacy_overall_score', 0)))
        
        safety_score = results.get('hybrid_safety_score', 0)
        
        if overall_score >= 0.8 and safety_score >= 0.85:
            return 'Ready for clinical pilot'
        elif overall_score >= 0.65 and safety_score >= 0.7:
            return 'Suitable for supervised testing'
        elif overall_score >= 0.5:
            return 'Requires significant improvement'
        else:
            return 'Not ready for clinical use'
    
    # Legacy helper methods for backward compatibility
    def _extract_symptoms_legacy(self, ground_truth: dict, extracted_info: dict):
        """Extract symptoms for legacy validation"""
        symptoms = []
        
        # From ground truth
        gt_symptoms = ground_truth.get("Core_Fields", {}).get("Symptoms", [])
        for symptom in gt_symptoms:
            if isinstance(symptom, dict):
                desc = symptom.get("description", "").strip()
                if desc:
                    symptoms.append(desc)
        
        # From extracted info
        ext_symptoms = extracted_info.get("symptoms", [])
        symptoms.extend(ext_symptoms)
        
        return list(set(symptoms))  # Remove duplicates
    
    def _extract_diagnoses_legacy(self, ground_truth: dict, extracted_info: dict):
        """Extract diagnoses for legacy validation"""
        diagnoses = []
        
        # From ground truth
        gt_diagnoses = ground_truth.get("Core_Fields", {}).get("Diagnoses", [])
        for diagnosis in gt_diagnoses:
            if isinstance(diagnosis, dict):
                primary = diagnosis.get("primary", "").strip()
                if primary:
                    diagnoses.append(primary)
        
        # From extracted info
        ext_diagnoses = extracted_info.get("diagnoses", [])
        diagnoses.extend(ext_diagnoses)
        
        return list(set(diagnoses))
    
    def _extract_treatments_legacy(self, ground_truth: dict, extracted_info: dict):
        """Extract treatments for legacy validation"""
        treatments = []
        
        # From ground truth
        gt_treatments = ground_truth.get("Core_Fields", {}).get("Treatment_Options", [])
        for treatment in gt_treatments:
            if isinstance(treatment, dict):
                procedure = treatment.get("procedure", "").strip()
                if procedure:
                    treatments.append(procedure)
        
        # From extracted info
        ext_treatments = extracted_info.get("treatments", [])
        treatments.extend(ext_treatments)
        
        return list(set(treatments))
    
    def _calculate_legacy_naturalness(self, dialogue_text: str):
        """Calculate legacy dialogue naturalness"""
        # Simplified implementation
        natural_indicators = ['um', 'uh', 'well', 'i think', 'maybe']
        naturalness_count = sum(1 for indicator in natural_indicators 
                              if indicator in dialogue_text.lower())
        return min(1.0, naturalness_count / 10)
    
    def _calculate_legacy_progressive_disclosure(self, dialogue_text: str):
        """Calculate legacy progressive disclosure"""
        # Simplified implementation
        lines = dialogue_text.split('\n')
        patient_lines = [line for line in lines if 'patient:' in line.lower()]
        
        if len(patient_lines) < 2:
            return 0.5
        
        # Check if first response is shorter than later ones
        first_length = len(patient_lines[0].split()) if patient_lines else 0
        later_avg = sum(len(line.split()) for line in patient_lines[1:]) / max(1, len(patient_lines) - 1)
        
        if first_length <= 20 and later_avg >= first_length:
            return 0.8
        else:
            return 0.4
    
    def _get_legacy_zero_scores(self):
        """Return legacy zero scores for failed evaluation"""
        return {
            'bertscore_precision': 0.0,
            'bertscore_recall': 0.0,
            'bertscore_f1': 0.0,
            'overall_medical_coverage': 0.0,
            'dialogue_naturalness': 0.0,
            'progressive_disclosure_quality': 0.0,
            'safety_score': 0.5,
            'overall_advanced_score': 0.0,
            'evaluation_method': 'failed',
            'evaluation_summary': {
                'overall_quality': 'Failed',
                'key_strengths': [],
                'improvement_areas': ['Fix evaluation errors'],
                'safety_status': 'Unknown',
                'clinical_readiness': 'Not assessable'
            }
        }


# INTEGRATION: Simple drop-in replacement for existing ValidatorAgent
class ValidatorAgent(EnhancedValidatorAgent):
    """
    Drop-in replacement for existing ValidatorAgent with advanced enhancements
    """
    
    def __init__(self):
        # Initialize with advanced validation enabled by default
        super().__init__(use_advanced_validation=True, use_mimic_kb=True)
        logger.info("ValidatorAgent enhanced with advanced validation (backward compatible)")


# INTEGRATION: Easy configuration for different validation modes
def create_validator_agent(mode: str = 'advanced'):
    """
    Factory function to create validator with different configurations
    
    Args:
        mode: 'advanced', 'legacy', or 'hybrid'
    """
    
    if mode == 'advanced':
        return EnhancedValidatorAgent(use_advanced_validation=True, use_mimic_kb=True)
    elif mode == 'legacy':
        return EnhancedValidatorAgent(use_advanced_validation=False, use_mimic_kb=False)
    elif mode == 'hybrid':
        return EnhancedValidatorAgent(use_advanced_validation=True, use_mimic_kb=True)
    else:
        raise ValueError(f"Unknown mode: {mode}")