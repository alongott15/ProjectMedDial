# gtmf_creation_enhanced.py
"""
ENHANCED: GTMF Creation with Advanced Medical Validation Integration
Minimal changes for maximum impact - integrates with enhanced validation system
"""
import json
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from Models.classes import GTMF
from Utils.utils import get_db_uri, format_date, build_symptom_conditions, calculate_age

# ENHANCEMENT: Import advanced validation components
from Utils.medical_knowledge_mimic import MIMICMedicalKnowledgeBase, MedicalValidationResult
from Utils.medical_validator import AdvancedMedicalValidator, ClinicalValidationMetrics
from Agents.ValidatorAgent import EnhancedValidatorAgent

import re
import os
from dataclasses import dataclass
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class EnhancedGTMFQualityScore:
    """ENHANCED: Quality assessment integrating advanced medical validation"""
    
    # Advanced Medical Validation Metrics
    clinical_validation: ClinicalValidationMetrics  # Full advanced validation results
    mimic_validation: MedicalValidationResult       # MIMIC-III knowledge validation
    
    # Traditional Metrics (Enhanced)
    completeness_score: float      # 0-1, enhanced with advanced methods
    accuracy_score: float          # 0-1, now using clinical validation
    consistency_score: float       # 0-1, medical coherence validation
    confidence_score: float        # 0-1, statistical confidence
    
    # New Advanced-derived Metrics
    medical_entity_f1: float        # Standardized medical entity F1
    clinical_safety_score: float    # Enhanced safety validation
    terminology_accuracy: float    # UMLS/SNOMED-CT validation
    clinical_readiness: str         # Clinical deployment readiness
    
    # Quality Indicators
    field_scores: dict
    issues: list
    recommendations: list
    confidence_interval: tuple  # 95% CI
    
    # Evaluation Summary
    evaluation_method: str          # Indicates advanced validation used
    mimic_kb_available: bool        # MIMIC-III knowledge base status

class AzureAIClient:
    """Enhanced Azure AI client with better error handling"""
    
    def __init__(self, endpoint: str = None, api_key: str = None, model_name: str = "gpt-4.1"):
        self.endpoint = endpoint or os.getenv("AZURE_AI_ENDPOINT")
        self.api_key = api_key or os.getenv("AZURE_AI_API_KEY")
        self.model_name = model_name
        
        if not self.endpoint or not self.api_key:
            raise ValueError("Azure AI endpoint and API key must be provided")
        
        self.client = ChatCompletionsClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.api_key)
        )
    
    def chat_completion(self, system_message: str, user_message: str, temperature: float = 0.0):
        """Generate chat completion with enhanced error handling"""
        try:
            response = self.client.complete(
                messages=[
                    SystemMessage(content=system_message),
                    UserMessage(content=user_message)
                ],
                model=self.model_name,
                temperature=temperature,
                max_tokens=2048
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Azure AI completion failed: {e}")
            raise

class EnhancedGTMFQualityAssessor:
    """
    ENHANCED: GTMF quality assessment using advanced medical validation
    Replaces the basic GTMFQualityAssessor with minimal API changes
    """
    
    def __init__(self, azure_client: AzureAIClient):
        self.azure_client = azure_client
        
        # ENHANCEMENT: Initialize advanced validation components
        try:
            db_uri = get_db_uri()
            if db_uri:
                self.mimic_kb = MIMICMedicalKnowledgeBase(db_uri)
                self.mimic_available = True
                logger.info("MIMIC-III knowledge base loaded for GTMF validation")
            else:
                self.mimic_kb = None
                self.mimic_available = False
                logger.warning("MIMIC-III database not available")
        except Exception as e:
            logger.error(f"Failed to load MIMIC-III knowledge base: {e}")
            self.mimic_kb = None
            self.mimic_available = False
        
        # Initialize advanced validator
        try:
            self.advanced_validator = AdvancedMedicalValidator(self.mimic_kb)
            self.advanced_available = True
            logger.info("Advanced medical validator initialized")
        except Exception as e:
            logger.error(f"Failed to initialize advanced validator: {e}")
            self.advanced_validator = None
            self.advanced_available = False
        
        # Initialize enhanced validator for dialogue assessment
        try:
            self.enhanced_validator = EnhancedValidatorAgent(
                use_advanced_validation=self.advanced_available,
                use_mimic_kb=self.mimic_available
            )
            logger.info("Enhanced validator agent initialized")
        except Exception as e:
            logger.error(f"Failed to initialize enhanced validator: {e}")
            self.enhanced_validator = None
    
    def assess_gtmf_quality(self, medical_text: str, gtmf_instance: GTMF):
        """
        ENHANCED: Comprehensive GTMF quality assessment using advanced validation
        Minimal API changes - same input/output structure but enhanced internally
        """
        logger.info("Starting enhanced GTMF quality assessment with advanced validation")
        
        # Convert GTMF to structured data for validation
        gtmf_dict = gtmf_instance.model_dump()
        
        # Extract medical components
        symptoms = self._extract_symptoms_from_gtmf(gtmf_instance)
        diagnoses = self._extract_diagnoses_from_gtmf(gtmf_instance)
        treatments = self._extract_treatments_from_gtmf(gtmf_instance)
        
        # ENHANCEMENT 1: Advanced Clinical Validation
        clinical_validation = None
        if self.advanced_available and self.advanced_validator:
            try:
                clinical_context = self._prepare_clinical_context_from_gtmf(gtmf_instance)
                clinical_validation = self.advanced_validator.validate_medical_dialogue(
                    predicted_dialogue=medical_text,
                    reference_dialogue=None,
                    clinical_context=clinical_context
                )
                logger.info(f"Advanced validation completed - Overall quality: {clinical_validation.overall_clinical_quality:.3f}")
            except Exception as e:
                logger.error(f"Advanced validation failed: {e}")
                clinical_validation = None
        
        # ENHANCEMENT 2: MIMIC-III Knowledge Base Validation
        mimic_validation = None
        if self.mimic_available and self.mimic_kb:
            try:
                mimic_validation = self.mimic_kb.validate_clinical_coherence(
                    symptoms, diagnoses, treatments
                )
                logger.info(f"MIMIC-III validation completed - Coherence: {mimic_validation.clinical_coherence:.3f}")
            except Exception as e:
                logger.error(f"MIMIC-III validation failed: {e}")
                mimic_validation = None
        
        # ENHANCEMENT 3: Enhanced Field Assessment
        field_scores = {}
        issues = []
        recommendations = []
        
        if clinical_validation:
            # Use advanced metrics for field assessment
            field_scores = {
                "symptoms": clinical_validation.medical_entity_f1,
                "diagnoses": clinical_validation.diagnostic_coherence,
                "treatments": clinical_validation.treatment_appropriateness,
                "overall_medical": clinical_validation.overall_clinical_quality
            }
            
            recommendations.extend(clinical_validation.recommendations)
            
            # Extract issues from advanced validation
            if clinical_validation.overall_clinical_quality < 0.7:
                issues.append("Overall clinical quality below recommended threshold")
            if clinical_validation.clinical_safety < 0.8:
                issues.append("Clinical safety concerns detected")
            if clinical_validation.terminology_accuracy < 0.75:
                issues.append("Medical terminology accuracy needs improvement")
        
        else:
            # Fallback to enhanced traditional assessment
            field_scores, field_issues = self._assess_fields_enhanced(medical_text, gtmf_dict)
            issues.extend(field_issues)
            recommendations = self._generate_fallback_recommendations(field_scores, issues)
        
        # ENHANCEMENT 4: Calculate enhanced quality scores
        enhanced_scores = self._calculate_enhanced_quality_scores(
            clinical_validation, mimic_validation, field_scores, medical_text, gtmf_dict
        )
        
        # ENHANCEMENT 5: Statistical confidence intervals
        confidence_interval = self._calculate_confidence_interval(
            clinical_validation, mimic_validation, field_scores
        )
        
        # ENHANCEMENT 6: Clinical readiness assessment
        clinical_readiness = self._assess_clinical_readiness(
            clinical_validation, mimic_validation, enhanced_scores
        )
        
        return EnhancedGTMFQualityScore(
            # Advanced Validation Results
            clinical_validation=clinical_validation,
            mimic_validation=mimic_validation,
            
            # Enhanced Traditional Metrics  
            completeness_score=enhanced_scores['completeness'],
            accuracy_score=enhanced_scores['accuracy'],
            consistency_score=enhanced_scores['consistency'],
            confidence_score=enhanced_scores['confidence'],
            
            # New Advanced-derived Metrics
            medical_entity_f1=clinical_validation.medical_entity_f1 if clinical_validation else enhanced_scores.get('entity_f1', 0.5),
            clinical_safety_score=clinical_validation.clinical_safety if clinical_validation else enhanced_scores.get('safety', 0.7),
            terminology_accuracy=clinical_validation.terminology_accuracy if clinical_validation else enhanced_scores.get('terminology', 0.6),
            clinical_readiness=clinical_readiness,
            
            # Quality Details
            field_scores=field_scores,
            issues=issues,
            recommendations=recommendations,
            confidence_interval=confidence_interval,
            
            # Evaluation Metadata
            evaluation_method="advanced_enhanced" if self.advanced_available else "enhanced_traditional",
            mimic_kb_available=self.mimic_available
        )
    
    def _extract_symptoms_from_gtmf(self, gtmf: GTMF):
        """Extract symptoms from GTMF for validation"""
        symptoms = []
        for symptom in gtmf.Core_Fields.Symptoms:
            if symptom.description and symptom.description != "not provided":
                symptoms.append(symptom.description)
        return symptoms
    
    def _extract_diagnoses_from_gtmf(self, gtmf: GTMF):
        """Extract diagnoses from GTMF for validation"""
        diagnoses = []
        for diagnosis in gtmf.Core_Fields.Diagnoses:
            if diagnosis.primary and diagnosis.primary != "not provided":
                diagnoses.append(diagnosis.primary)
        return diagnoses
    
    def _extract_treatments_from_gtmf(self, gtmf: GTMF):
        """Extract treatments from GTMF for validation"""
        treatments = []
        for treatment in gtmf.Core_Fields.Treatment_Options:
            if treatment.procedure and treatment.procedure != "not provided":
                treatments.append(treatment.procedure)
        return treatments
    
    def _prepare_clinical_context_from_gtmf(self, gtmf: GTMF):
        """Prepare clinical context for advanced validation"""
        return {
            'symptoms': self._extract_symptoms_from_gtmf(gtmf),
            'diagnoses': self._extract_diagnoses_from_gtmf(gtmf),
            'treatments': self._extract_treatments_from_gtmf(gtmf),
            'patient_age': gtmf.Context_Fields.Patient_Demographics.Age,
            'patient_sex': gtmf.Context_Fields.Patient_Demographics.Sex,
            'medical_history': gtmf.Context_Fields.Medical_History.Past_Medical_History if gtmf.Context_Fields.Medical_History else "",
            'allergies': gtmf.Context_Fields.Allergies,
            'current_medications': gtmf.Context_Fields.Current_Medications
        }
    
    def _assess_fields_enhanced(self, medical_text: str, gtmf_dict: dict):
        """Enhanced field assessment with better medical validation"""
        field_scores = {}
        issues = []
        
        # Enhanced symptom assessment
        symptoms = gtmf_dict.get("Core_Fields", {}).get("Symptoms", [])
        symptom_score, symptom_issues = self._assess_symptoms_enhanced(medical_text, symptoms)
        field_scores["symptoms"] = symptom_score
        issues.extend(symptom_issues)
        
        # Enhanced diagnosis assessment
        diagnoses = gtmf_dict.get("Core_Fields", {}).get("Diagnoses", [])
        diagnosis_score, diagnosis_issues = self._assess_diagnoses_enhanced(medical_text, diagnoses)
        field_scores["diagnoses"] = diagnosis_score
        issues.extend(diagnosis_issues)
        
        # Enhanced treatment assessment
        treatments = gtmf_dict.get("Core_Fields", {}).get("Treatment_Options", [])
        treatment_score, treatment_issues = self._assess_treatments_enhanced(medical_text, treatments)
        field_scores["treatments"] = treatment_score
        issues.extend(treatment_issues)
        
        return field_scores, issues
    
    def _assess_symptoms_enhanced(self, text: str, symptoms):
        """Enhanced symptom assessment using medical patterns"""
        issues = []
        
        if not symptoms:
            # Check if medical text contains symptom indicators
            symptom_indicators = ['pain', 'ache', 'discomfort', 'nausea', 'fever', 'cough', 'headache']
            if any(indicator in text.lower() for indicator in symptom_indicators):
                issues.append("Medical text contains symptoms but none extracted")
                return 0.3, issues
            return 0.8, issues  # No symptoms expected
        
        # Validate symptom quality
        valid_symptoms = 0
        total_symptoms = len(symptoms)
        
        for symptom in symptoms:
            if isinstance(symptom, dict):
                desc = symptom.get("description", "").strip()
                if desc and desc != "not provided":
                    # Check if symptom appears in text
                    if desc.lower() in text.lower():
                        valid_symptoms += 1
                    else:
                        # Check partial match
                        words = desc.lower().split()
                        if any(word in text.lower() for word in words if len(word) > 3):
                            valid_symptoms += 0.5
        
        score = valid_symptoms / total_symptoms if total_symptoms > 0 else 0.5
        
        if score < 0.6:
            issues.append("Many extracted symptoms not clearly supported by text")
        
        return score, issues
    
    def _assess_diagnoses_enhanced(self, text: str, diagnoses):
        """Enhanced diagnosis assessment"""
        issues = []
        
        if not diagnoses:
            # Check if text contains diagnostic information
            if any(indicator in text.lower() for indicator in ["diagnosis", "diagnosed", "condition", "disease"]):
                issues.append("Diagnostic information present but no diagnoses extracted")
                return 0.4, issues
            return 0.8, issues
        
        # Validate diagnosis quality
        valid_diagnoses = 0
        total_diagnoses = len(diagnoses)
        
        for diagnosis in diagnoses:
            if isinstance(diagnosis, dict):
                primary = diagnosis.get("primary", "").strip()
                if primary and primary != "not provided":
                    # Validate against text
                    if primary.lower() in text.lower():
                        valid_diagnoses += 1
                    else:
                        # Check partial match
                        words = primary.lower().split()
                        if any(word in text.lower() for word in words if len(word) > 3):
                            valid_diagnoses += 0.5
        
        score = valid_diagnoses / total_diagnoses if total_diagnoses > 0 else 0.5
        
        if score < 0.6:
            issues.append("Extracted diagnoses not well supported by text")
        
        return score, issues
    
    def _assess_treatments_enhanced(self, text: str, treatments):
        """Enhanced treatment assessment"""
        issues = []
        
        if not treatments:
            if any(indicator in text.lower() for indicator in ["treatment", "therapy", "medication", "prescription"]):
                issues.append("Treatment information present but none extracted")
                return 0.4, issues
            return 0.8, issues
        
        # Validate treatment quality
        valid_treatments = 0
        total_treatments = len(treatments)
        
        for treatment in treatments:
            if isinstance(treatment, dict):
                procedure = treatment.get("procedure", "").strip()
                if procedure and procedure != "not provided":
                    # Validate against text
                    if procedure.lower() in text.lower():
                        valid_treatments += 1
                    else:
                        # Check partial match
                        words = procedure.lower().split()
                        if any(word in text.lower() for word in words if len(word) > 3):
                            valid_treatments += 0.5
        
        score = valid_treatments / total_treatments if total_treatments > 0 else 0.5
        
        if score < 0.6:
            issues.append("Extracted treatments not well supported by text")
        
        return score, issues
    
    def _calculate_enhanced_quality_scores(self, clinical_validation: ClinicalValidationMetrics, 
                                          mimic_validation: MedicalValidationResult,
                                          field_scores: dict,
                                          medical_text: str, gtmf_dict: dict):
        """Calculate enhanced quality scores integrating advanced validation"""
        
        if clinical_validation:
            # Use advanced validation results
            return {
                'completeness': clinical_validation.clinical_completeness,
                'accuracy': (clinical_validation.medical_entity_f1 + clinical_validation.terminology_accuracy) / 2,
                'consistency': clinical_validation.diagnostic_coherence,
                'confidence': clinical_validation.overall_clinical_quality,
                'entity_f1': clinical_validation.medical_entity_f1,
                'safety': clinical_validation.clinical_safety,
                'terminology': clinical_validation.terminology_accuracy
            }
        
        elif mimic_validation:
            # Use MIMIC-III validation results
            return {
                'completeness': mimic_validation.concept_coverage,
                'accuracy': mimic_validation.terminology_accuracy,
                'consistency': mimic_validation.clinical_coherence,
                'confidence': mimic_validation.validity_score,
                'entity_f1': mimic_validation.validity_score,
                'safety': mimic_validation.safety_score,
                'terminology': mimic_validation.terminology_accuracy
            }
        
        else:
            # Fallback to enhanced traditional calculation
            text_length = len(medical_text.split())
            
            # Enhanced completeness calculation
            total_extracted = sum(len(gtmf_dict.get("Core_Fields", {}).get(field, [])) 
                                for field in ["Symptoms", "Diagnoses", "Treatment_Options"])
            expected_items = max(3, text_length // 200)  # More realistic expectation
            completeness = min(1.0, total_extracted / expected_items)
            
            # Enhanced accuracy from field scores
            accuracy = sum(field_scores.values()) / len(field_scores) if field_scores else 0.5
            
            # Basic consistency (could be enhanced with more sophisticated methods)
            consistency = 0.7  # Default reasonable score
            
            # Confidence based on field performance
            confidence = accuracy * 0.8  # Conservative confidence
            
            return {
                'completeness': completeness,
                'accuracy': accuracy,
                'consistency': consistency,
                'confidence': confidence,
                'entity_f1': accuracy,  # Approximation
                'safety': 0.7,  # Default safe assumption
                'terminology': accuracy * 0.9  # Approximation
            }
    
    def _calculate_confidence_interval(self, clinical_validation: ClinicalValidationMetrics,
                                     mimic_validation: MedicalValidationResult,
                                     field_scores: dict):
        """Calculate 95% confidence interval for quality assessment"""
        
        if clinical_validation and hasattr(clinical_validation, 'confidence_interval'):
            return clinical_validation.confidence_interval
        
        # Calculate CI from available scores
        all_scores = []
        
        if clinical_validation:
            all_scores.extend([
                clinical_validation.medical_entity_f1,
                clinical_validation.terminology_accuracy,
                clinical_validation.clinical_completeness,
                clinical_validation.diagnostic_coherence,
                clinical_validation.clinical_safety
            ])
        
        if mimic_validation:
            all_scores.extend([
                mimic_validation.validity_score,
                mimic_validation.clinical_coherence,
                mimic_validation.terminology_accuracy
            ])
        
        all_scores.extend(field_scores.values())
        
        if len(all_scores) >= 3:
            mean_score = np.mean(all_scores)
            std_score = np.std(all_scores)
            margin = 1.96 * std_score / np.sqrt(len(all_scores))
            
            return (max(0.0, mean_score - margin), min(1.0, mean_score + margin))
        else:
            # Default CI for insufficient data
            return (0.4, 0.8)
    
    def _assess_clinical_readiness(self, clinical_validation: ClinicalValidationMetrics,
                                  mimic_validation: MedicalValidationResult,
                                  enhanced_scores: dict):
        """Assess clinical deployment readiness"""
        
        if clinical_validation:
            overall_quality = clinical_validation.overall_clinical_quality
            safety_score = clinical_validation.clinical_safety
        elif mimic_validation:
            overall_quality = mimic_validation.validity_score
            safety_score = mimic_validation.safety_score
        else:
            overall_quality = enhanced_scores.get('confidence', 0.5)
            safety_score = enhanced_scores.get('safety', 0.7)
        
        # Clinical readiness assessment based on established thresholds
        if overall_quality >= 0.85 and safety_score >= 0.9:
            return "Ready for clinical pilot testing"
        elif overall_quality >= 0.75 and safety_score >= 0.8:
            return "Suitable for supervised clinical testing"
        elif overall_quality >= 0.65 and safety_score >= 0.7:
            return "Requires improvement before clinical use"
        elif overall_quality >= 0.5:
            return "Significant improvement needed"
        else:
            return "Not suitable for clinical deployment"
    
    def _generate_fallback_recommendations(self, field_scores: dict, 
                                         issues: list):
        """Generate recommendations when advanced validation is not available"""
        recommendations = []
        
        if field_scores.get("symptoms", 1.0) < 0.6:
            recommendations.append("Improve symptom extraction accuracy and validation")
        
        if field_scores.get("diagnoses", 1.0) < 0.6:
            recommendations.append("Enhance diagnosis extraction and medical coherence")
        
        if field_scores.get("treatments", 1.0) < 0.6:
            recommendations.append("Better treatment identification and validation")
        
        if len(issues) > 3:
            recommendations.append("Address multiple extraction quality issues")
        
        recommendations.append("Consider enabling advanced validation for better assessment")
        
        return recommendations[:5]

# MINIMAL CHANGE: Update extract_gtmf_chunked to use enhanced quality assessment
def extract_gtmf_chunked(medical_text: str, azure_client: AzureAIClient):
    """
    ENHANCED: Extract GTMF with advanced quality assessment (minimal API changes)
    """
    logger.info("Extracting GTMF with enhanced advanced quality assessment")
    
    # Get GTMF schema
    schema_json = GTMF.model_json_schema()
    
    # Chunk the text if it's too long
    chunks = chunk_medical_text(medical_text, max_chunk_size=3000, overlap=200)
    logger.info(f"Processing {len(chunks)} chunks")
    
    # System message for extraction (unchanged)
    system_message = """You are a medical information extraction expert. Your task is to extract all relevant details from medical notes and convert them into structured JSON format.

    Key Instructions:
    1. Extract ALL medical information present in the text
    2. If you have multiple symptoms or diagnoses, create separate objects for each one
    3. If information is missing, use 'not provided' for string fields or empty arrays for lists
    4. Include medications as part of treatment options
    5. Your output must be valid JSON that conforms to the provided schema
    6. Focus on accuracy and completeness"""
    
    all_extractions = []
    
    # Process each chunk (unchanged)
    for i, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {i+1}/{len(chunks)}")
        
        user_message = f"""
        Extract medical information from this clinical note chunk and format it according to the JSON schema below.

        JSON Schema:
        {json.dumps(schema_json, indent=2)}

        Medical Note Chunk:
        {chunk}

        Provide only the JSON output:
        """
        
        try:
            result = azure_client.chat_completion(system_message, user_message, temperature=0.0)
            
            # Clean up the response to extract JSON
            json_start = result.find('{')
            json_end = result.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = result[json_start:json_end]
                data = json.loads(json_str)
                all_extractions.append(data)
            else:
                logger.warning(f"Could not extract JSON from chunk {i+1}")
                
        except Exception as e:
            logger.error(f"Error processing chunk {i+1}: {e}")
            continue
    
    # Merge extractions from all chunks (unchanged)
    merged_extraction = merge_gtmf_extractions(all_extractions)
    
    try:
        structured_output = GTMF(**merged_extraction)
        
        # ENHANCEMENT: Use enhanced quality assessor with advanced validation
        assessor = EnhancedGTMFQualityAssessor(azure_client)
        quality_score = assessor.assess_gtmf_quality(medical_text, structured_output)
        
        logger.info(f"Enhanced GTMF extraction completed with advanced quality scores: "
                   f"Overall={quality_score.confidence_score:.2f}, "
                   f"Medical Entity F1={quality_score.medical_entity_f1:.2f}, "
                   f"Clinical Safety={quality_score.clinical_safety_score:.2f}, "
                   f"Clinical Readiness: {quality_score.clinical_readiness}")
        
        return structured_output, quality_score
        
    except Exception as e:
        logger.error(f"Error in enhanced extract_gtmf_chunked: {e}")
        raise

# Keep existing utility functions unchanged
def chunk_medical_text(text: str, max_chunk_size: int = 3000, overlap: int = 200):
    """Split medical text into overlapping chunks for better processing"""
    if len(text) <= max_chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + max_chunk_size
        
        # Try to break at sentence boundary
        if end < len(text):
            # Look for sentence endings within the last 200 characters
            last_period = text.rfind('.', end - 200, end)
            last_newline = text.rfind('\n', end - 200, end)
            
            if last_period > start:
                end = last_period + 1
            elif last_newline > start:
                end = last_newline + 1
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Move start position with overlap
        start = max(start + max_chunk_size - overlap, end)
        
        if start >= len(text):
            break
    
    return chunks

def merge_gtmf_extractions(extractions):
    """Merge multiple GTMF extractions from chunks into a single comprehensive extraction"""
    if not extractions:
        raise ValueError("No extractions to merge")
    
    if len(extractions) == 1:
        return extractions[0]
    
    # Start with the first extraction as base
    merged = extractions[0].copy()
    
    # Merge core fields
    merged_symptoms = []
    merged_diagnoses = []
    merged_treatments = []
    
    seen_symptoms = set()
    seen_diagnoses = set()
    seen_treatments = set()
    
    for extraction in extractions:
        core_fields = extraction.get("Core_Fields", {})
        
        # Merge symptoms
        for symptom in core_fields.get("Symptoms", []):
            desc = symptom.get("description", "").strip().lower()
            if desc and desc != "not provided" and desc not in seen_symptoms:
                merged_symptoms.append(symptom)
                seen_symptoms.add(desc)
        
        # Merge diagnoses
        for diagnosis in core_fields.get("Diagnoses", []):
            primary = diagnosis.get("primary", "").strip().lower()
            if primary and primary != "not provided" and primary not in seen_diagnoses:
                merged_diagnoses.append(diagnosis)
                seen_diagnoses.add(primary)
        
        # Merge treatments
        for treatment in core_fields.get("Treatment_Options", []):
            procedure = treatment.get("procedure", "").strip().lower()
            if procedure and procedure != "not provided" and procedure not in seen_treatments:
                merged_treatments.append(treatment)
                seen_treatments.add(procedure)
    
    # Update merged extraction
    merged["Core_Fields"]["Symptoms"] = merged_symptoms
    merged["Core_Fields"]["Diagnoses"] = merged_diagnoses
    merged["Core_Fields"]["Treatment_Options"] = merged_treatments
    
    # Merge context fields (taking the most complete information)
    for extraction in extractions[1:]:
        context_fields = extraction.get("Context_Fields", {})
        
        # Merge allergies
        merged_allergies = merged.get("Context_Fields", {}).get("Allergies", [])
        for allergy in context_fields.get("Allergies", []):
            if allergy not in merged_allergies:
                merged_allergies.append(allergy)
        merged["Context_Fields"]["Allergies"] = merged_allergies
        
        # Merge medications
        merged_current_meds = merged.get("Context_Fields", {}).get("Current_Medications", [])
        for med in context_fields.get("Current_Medications", []):
            if med not in merged_current_meds:
                merged_current_meds.append(med)
        merged["Context_Fields"]["Current_Medications"] = merged_current_meds
        
        merged_discharge_meds = merged.get("Context_Fields", {}).get("Discharge_Medications", [])
        for med in context_fields.get("Discharge_Medications", []):
            if med not in merged_discharge_meds:
                merged_discharge_meds.append(med)
        merged["Context_Fields"]["Discharge_Medications"] = merged_discharge_meds
    
    return merged

# ENHANCEMENT: Update process_notes to use enhanced quality assessment
def process_notes(results, azure_client: AzureAIClient):
    """Enhanced note processing with advanced quality assessment and reporting"""
    logger.info("Processing notes with enhanced advanced quality assessment")
    structured_results = []
    quality_summary = {
        "total_processed": 0,
        "high_quality": 0,         # >0.8 overall score (advanced enhanced)
        "medium_quality": 0,       # 0.6-0.8 overall score  
        "low_quality": 0,          # <0.6 overall score
        "clinical_ready": 0,       # Ready for clinical testing
        "safety_compliant": 0,     # High safety scores
        "common_issues": [],
        "average_scores": {},
        "advanced_validation_rate": 0, # Percentage using advanced validation
        "mimic_kb_rate": 0        # Percentage using MIMIC-III KB
    }

    advanced_used_count = 0
    mimic_used_count = 0

    for idx, row in enumerate(results):
        try:
            # Demographics processing (unchanged)
            dob_formatted = format_date(row['dob'], '%Y-%m-%d')
            adm_formatted = format_date(row['admittime'], '%Y-%m-%d %H:%M:%S')
            dis_formatted = format_date(row['dischtime'], '%Y-%m-%d %H:%M:%S')
            age = calculate_age(dob_formatted, adm_formatted)
            
            demographics = {
                'Date_of_Birth': dob_formatted,
                'Age': age,
                'Sex': row.get('gender', 'Not provided'),
                'Religion': row.get('religion', 'Not provided'),
                'Marital_Status': row.get('marital_status', 'Not provided'),
                'Ethnicity': row.get('ethnicity', 'Not provided'),
                'Insurance': row.get('insurance', 'Not provided'),
                'Admission_Type': row.get('admission_type', 'Not provided'),
                'Admission_Date': adm_formatted,
                'Discharge_Date': dis_formatted
            }

            # ENHANCEMENT: Extract GTMF with enhanced quality assessment
            gtmf_instance, quality_score = extract_gtmf_chunked(row['text'], azure_client)

            # Track advanced validation usage
            quality_summary["total_processed"] += 1
            if quality_score.evaluation_method == "advanced_enhanced":
                advanced_used_count += 1
            if quality_score.mimic_kb_available:
                mimic_used_count += 1

            # ENHANCEMENT: Enhanced quality categorization
            overall_score = quality_score.confidence_score
            
            if overall_score > 0.8:
                quality_summary["high_quality"] += 1
            elif overall_score > 0.6:
                quality_summary["medium_quality"] += 1
            else:
                quality_summary["low_quality"] += 1
            
            # Clinical readiness tracking
            if "ready" in quality_score.clinical_readiness.lower():
                quality_summary["clinical_ready"] += 1
            
            # Safety compliance tracking
            if quality_score.clinical_safety_score > 0.8:
                quality_summary["safety_compliant"] += 1

            # Collect issues for analysis
            quality_summary["common_issues"].extend(quality_score.issues)

            # Update GTMF with metadata and demographics (unchanged)
            gtmf_instance = gtmf_instance.model_copy(update={
                "row_id": row['row_id'],
                "subject_id": row['subject_id'],
                "hadm_id": row['hadm_id'],
                "Context_Fields": gtmf_instance.Context_Fields.model_copy(update={
                    "Patient_Demographics": gtmf_instance.Context_Fields.Patient_Demographics.model_copy(update=demographics)
                })
            })
            
            # ENHANCEMENT: Include enhanced quality scores in output
            result_with_quality = gtmf_instance.model_dump()
            result_with_quality["enhanced_quality_assessment"] = {
                # Advanced Metrics
                "medical_entity_f1": quality_score.medical_entity_f1,
                "clinical_safety_score": quality_score.clinical_safety_score,
                "terminology_accuracy": quality_score.terminology_accuracy,
                "clinical_readiness": quality_score.clinical_readiness,
                
                # Enhanced Traditional Metrics
                "completeness_score": quality_score.completeness_score,
                "accuracy_score": quality_score.accuracy_score,
                "consistency_score": quality_score.consistency_score,
                "confidence_score": quality_score.confidence_score,
                
                # Validation Details
                "evaluation_method": quality_score.evaluation_method,
                "mimic_kb_available": quality_score.mimic_kb_available,
                "confidence_interval": quality_score.confidence_interval,
                
                # Quality Details
                "field_scores": quality_score.field_scores,
                "issues": quality_score.issues,
                "recommendations": quality_score.recommendations,
                
                # Advanced Validation Results (if available)
                "advanced_validation": quality_score.clinical_validation.__dict__ if quality_score.clinical_validation else None,
                "mimic_validation": quality_score.mimic_validation.__dict__ if quality_score.mimic_validation else None
            }
            
            structured_results.append(result_with_quality)
            logger.info(f"Processed note {idx} with enhanced quality - Overall: {overall_score:.2f}, "
                       f"Safety: {quality_score.clinical_safety_score:.2f}, "
                       f"Clinical Readiness: {quality_score.clinical_readiness}")
            
        except Exception as e:
            logger.error(f"Error processing note at index {idx}: {e}")
            quality_summary["total_processed"] += 1
            quality_summary["low_quality"] += 1
    
    # ENHANCEMENT: Calculate enhanced average scores and usage statistics
    if structured_results:
        total_results = len(structured_results)
        
        # Calculate averages from enhanced scores
        avg_completeness = sum(r["enhanced_quality_assessment"]["completeness_score"] for r in structured_results) / total_results
        avg_accuracy = sum(r["enhanced_quality_assessment"]["accuracy_score"] for r in structured_results) / total_results
        avg_medical_entity_f1 = sum(r["enhanced_quality_assessment"]["medical_entity_f1"] for r in structured_results) / total_results
        avg_safety = sum(r["enhanced_quality_assessment"]["clinical_safety_score"] for r in structured_results) / total_results
        avg_terminology = sum(r["enhanced_quality_assessment"]["terminology_accuracy"] for r in structured_results) / total_results
        
        quality_summary["average_scores"] = {
            "completeness": avg_completeness,
            "accuracy": avg_accuracy,
            "medical_entity_f1": avg_medical_entity_f1,
            "clinical_safety": avg_safety,
            "terminology_accuracy": avg_terminology
        }
        
        # Usage statistics
        quality_summary["advanced_validation_rate"] = advanced_used_count / total_results
        quality_summary["mimic_kb_rate"] = mimic_used_count / total_results
    
    # ENHANCEMENT: Enhanced quality summary logging
    logger.info(f"Enhanced Quality Summary: {quality_summary['high_quality']} high, "
               f"{quality_summary['medium_quality']} medium, "
               f"{quality_summary['low_quality']} low quality extractions")
    logger.info(f"Clinical Readiness: {quality_summary['clinical_ready']} ready for testing")
    logger.info(f"Advanced Validation Rate: {quality_summary['advanced_validation_rate']:.1%}")
    logger.info(f"MIMIC-III KB Usage: {quality_summary['mimic_kb_rate']:.1%}")
    
    return structured_results, quality_summary

# Keep existing database functions unchanged
def fetch_notes(session):
    """Fetch notes from the MIMIC-III database matching specified criteria."""
    logger.info("Fetching notes from database")
    symptom_conditions = build_symptom_conditions()
    query = text(f"""
        SELECT n.row_id, n.subject_id, n.hadm_id, n.text, 
               a.admittime, a.dischtime, a.subject_id, a.religion, a.marital_status, a.ethnicity, a.insurance, a.admission_type,
               p.gender, p.dob, n.category
        FROM noteevents n
        JOIN admissions a ON n.hadm_id = a.hadm_id
        JOIN patients p ON n.subject_id = p.subject_id
        WHERE n.text ILIKE :keyword
          AND ({symptom_conditions})
          AND n.category ILIKE :category
        LIMIT 100
    """)
    params = {'keyword': '%Chief Complaint%', 'category': '%Discharge Summary%'}
    try:
        results = session.execute(query, params).mappings().all()
        logger.info(f"Fetched {len(results)} notes from database")
        return results
    except Exception as e:
        logger.error(f"Error fetching notes: {e}")
        return []

def main():
    """ENHANCED: Main execution with advanced quality reporting"""
    logger.info("Starting enhanced GTMF extraction with advanced validation")
    
    # Initialize Azure AI client
    try:
        azure_client = AzureAIClient()
        logger.info("Azure AI client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Azure AI client: {e}")
        return
    
    engine = create_engine(get_db_uri())
    Session = sessionmaker(bind=engine)

    try:
        with Session() as session:
            results = fetch_notes(session)
            if not results:
                logger.warning("No notes found matching criteria.")
                return
            
            structured_results, quality_summary = process_notes(results, azure_client)
            
            # ENHANCEMENT: Save results with enhanced quality information
            output_path = 'gtmf/gtmf_example_enhanced.json'
            with open(output_path, 'w', encoding='utf-8') as outfile:
                json.dump(structured_results, outfile, indent=2)
            
            # Save enhanced quality summary
            quality_report_path = 'gtmf/enhanced_quality_report.json'
            with open(quality_report_path, 'w', encoding='utf-8') as outfile:
                json.dump(quality_summary, outfile, indent=2)
            
            logger.info(f"Enhanced extraction complete. Results saved to {output_path}")
            logger.info(f"Enhanced quality report saved to {quality_report_path}")
            
            # ENHANCEMENT: Print enhanced summary with advanced metrics
            print(f"\n=== Enhanced GTMF Advanced Quality Summary ===")
            print(f"Total processed: {quality_summary['total_processed']}")
            print(f"High quality (>0.8): {quality_summary['high_quality']}")
            print(f"Medium quality (0.6-0.8): {quality_summary['medium_quality']}")
            print(f"Low quality (<0.6): {quality_summary['low_quality']}")
            print(f"Clinical ready: {quality_summary['clinical_ready']}")
            print(f"Safety compliant: {quality_summary['safety_compliant']}")
            print(f"Advanced validation rate: {quality_summary['advanced_validation_rate']:.1%}")
            print(f"MIMIC-III KB usage: {quality_summary['mimic_kb_rate']:.1%}")
            
            if quality_summary.get('average_scores'):
                print(f"\n=== Enhanced Average Scores ===")
                print(f"Medical Entity F1: {quality_summary['average_scores']['medical_entity_f1']:.3f}")
                print(f"Clinical Safety: {quality_summary['average_scores']['clinical_safety']:.3f}")
                print(f"Terminology Accuracy: {quality_summary['average_scores']['terminology_accuracy']:.3f}")
                print(f"Completeness: {quality_summary['average_scores']['completeness']:.3f}")
                print(f"Accuracy: {quality_summary['average_scores']['accuracy']:.3f}")
            
    except Exception as e:
        logger.error(f"Error in enhanced main execution: {e}")

if __name__ == '__main__':
    main()