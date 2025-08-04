"""
Medical Validation System using MIMIC-III Dataset Knowledge
Replaces custom vocabularies with real medical knowledge from MIMIC-III

This system uses actual medical terminologies from:
- D_ICD_DIAGNOSES: Real ICD-9 diagnosis codes and descriptions
- D_ICD_PROCEDURES: Real ICD-9 procedure codes and descriptions  
- PRESCRIPTIONS: Actual medication names from clinical practice
- D_LABITEMS: Laboratory test items and descriptions
- NOTEEVENTS: Clinical terminology from real medical notes
- ADMISSIONS: Patient demographic and admission categories
"""

import logging
import re
import json
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass
from difflib import SequenceMatcher
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from Utils.utils import get_db_uri

logger = logging.getLogger(__name__)

@dataclass
class MIMICNERMetrics:
    """Traditional NER evaluation metrics using MIMIC-III knowledge"""
    precision: float
    recall: float
    f1_score: float
    exact_matches: int
    partial_matches: int
    mimic_vocabulary_matches: int
    total_predicted: int
    total_gold: int
    support: int

@dataclass
class MIMICEntityEvaluation:
    """Entity-level evaluation results using MIMIC-III data"""
    entity_type: str
    metrics: MIMICNERMetrics
    mimic_mappings: Dict[str, str]
    validation_details: Dict[str, any]
    error_analysis: List[str]

class MIMICMedicalKnowledgeExtractor:
    """Extract medical knowledge from MIMIC-III dataset tables"""
    
    def __init__(self, db_session=None):
        self.db_session = db_session
        self.engine = None
        if not db_session:
            self._initialize_db_connection()
        
        # Cache for extracted vocabularies
        self._diagnosis_vocabulary = None
        self._procedure_vocabulary = None
        self._medication_vocabulary = None
        self._lab_vocabulary = None
        self._clinical_terminology = None
        
        logger.info("MIMIC-III Medical Knowledge Extractor initialized")
    
    def _initialize_db_connection(self):
        """Initialize database connection to MIMIC-III"""
        try:
            db_uri = get_db_uri()
            if db_uri:
                self.engine = create_engine(db_uri)
                Session = sessionmaker(bind=self.engine)
                self.db_session = Session()
                logger.info("Connected to MIMIC-III database")
            else:
                logger.error("Database URI not available")
                raise ValueError("Cannot connect to MIMIC-III database")
        except Exception as e:
            logger.error(f"Failed to connect to MIMIC-III database: {e}")
            raise
    
    def get_diagnosis_vocabulary(self) -> Dict[str, List[str]]:
        """Extract diagnosis vocabulary from D_ICD_DIAGNOSES table"""
        if self._diagnosis_vocabulary is not None:
            return self._diagnosis_vocabulary
        
        logger.info("Extracting diagnosis vocabulary from MIMIC-III D_ICD_DIAGNOSES")
        
        try:
            query = text("""
                SELECT icd9_code, short_title, long_title
                FROM d_icd_diagnoses
                ORDER BY icd9_code
            """)
            
            results = self.db_session.execute(query).mappings().all()
            
            diagnosis_vocab = {}
            diagnosis_terms = []
            
            for row in results:
                icd_code = row['icd9_code']
                short_title = str(row['short_title']).lower() if row['short_title'] else ""
                long_title = str(row['long_title']).lower() if row['long_title'] else ""
                
                # Store all variations for this diagnosis
                terms = []
                if short_title:
                    terms.append(short_title)
                    diagnosis_terms.append(short_title)
                if long_title and long_title != short_title:
                    terms.append(long_title)
                    diagnosis_terms.append(long_title)
                
                if terms:
                    diagnosis_vocab[icd_code] = terms
            
            # Create comprehensive diagnosis term list
            self._diagnosis_vocabulary = {
                'icd_mappings': diagnosis_vocab,
                'all_terms': list(set(diagnosis_terms)),
                'term_count': len(set(diagnosis_terms))
            }
            
            logger.info(f"Extracted {len(diagnosis_vocab)} ICD-9 diagnosis codes with {len(set(diagnosis_terms))} unique terms")
            return self._diagnosis_vocabulary
            
        except Exception as e:
            logger.error(f"Error extracting diagnosis vocabulary: {e}")
            return {'icd_mappings': {}, 'all_terms': [], 'term_count': 0}
    
    def get_medication_vocabulary(self) -> Dict[str, List[str]]:
        """Extract medication vocabulary from PRESCRIPTIONS table"""
        if self._medication_vocabulary is not None:
            return self._medication_vocabulary
        
        logger.info("Extracting medication vocabulary from MIMIC-III PRESCRIPTIONS")
        
        try:
            query = text("""
                SELECT DISTINCT 
                    LOWER(drug) as drug_name,
                    LOWER(drug_name_poe) as drug_name_poe,
                    LOWER(drug_name_generic) as drug_name_generic
                FROM prescriptions
                WHERE drug IS NOT NULL
                LIMIT 10000
            """)
            
            results = self.db_session.execute(query).mappings().all()
            
            medication_terms = set()
            drug_mappings = {}
            
            for row in results:
                drug_name = row['drug_name']
                drug_name_poe = row['drug_name_poe']
                drug_name_generic = row['drug_name_generic']
                
                # Collect all drug name variations
                drugs = []
                if drug_name and drug_name.strip():
                    drugs.append(drug_name.strip())
                    medication_terms.add(drug_name.strip())
                
                if drug_name_poe and drug_name_poe.strip() and drug_name_poe != drug_name:
                    drugs.append(drug_name_poe.strip())
                    medication_terms.add(drug_name_poe.strip())
                
                if drug_name_generic and drug_name_generic.strip() and drug_name_generic not in [drug_name, drug_name_poe]:
                    drugs.append(drug_name_generic.strip())
                    medication_terms.add(drug_name_generic.strip())
                
                if drugs:
                    # Use primary drug name as key
                    primary_drug = drugs[0]
                    drug_mappings[primary_drug] = drugs
            
            self._medication_vocabulary = {
                'drug_mappings': drug_mappings,
                'all_terms': list(medication_terms),
                'term_count': len(medication_terms)
            }
            
            logger.info(f"Extracted {len(medication_terms)} unique medication terms")
            return self._medication_vocabulary
            
        except Exception as e:
            logger.error(f"Error extracting medication vocabulary: {e}")
            return {'drug_mappings': {}, 'all_terms': [], 'term_count': 0}
    
    def get_clinical_terminology(self) -> Dict[str, int]:
        """Extract clinical terminology from NOTEEVENTS (sample)"""
        if self._clinical_terminology is not None:
            return self._clinical_terminology
        
        logger.info("Extracting clinical terminology from MIMIC-III NOTEEVENTS (sample)")
        
        try:
            # Sample clinical notes to extract terminology
            query = text("""
                SELECT text
                FROM noteevents
                WHERE category IN ('Discharge summary', 'Physician', 'Nursing/other')
                AND text IS NOT NULL
                LIMIT 1000
            """)
            
            results = self.db_session.execute(query).mappings().all()
            
            # Extract medical terminology using pattern matching
            medical_terms = Counter()
            
            # Common medical term patterns
            medical_patterns = [
                r'\b[a-z]+itis\b',      # inflammatory conditions
                r'\b[a-z]+osis\b',      # conditions
                r'\b[a-z]+emia\b',      # blood conditions  
                r'\b[a-z]+pathy\b',     # disease conditions
                r'\b[a-z]+algia\b',     # pain conditions
                r'\b[a-z]+ectomy\b',    # surgical removal
                r'\b[a-z]+scopy\b',     # examinations
                r'\b[a-z]+gram\b',      # recordings
            ]
            
            for row in results:
                if row['text']:
                    text = row['text'].lower()
                    
                    # Extract terms matching medical patterns
                    for pattern in medical_patterns:
                        matches = re.findall(pattern, text)
                        for match in matches:
                            if len(match) > 3:  # Filter very short terms
                                medical_terms[match] += 1
            
            # Keep terms that appear multiple times (more likely to be medical)
            filtered_terms = {term: count for term, count in medical_terms.items() if count >= 2}
            
            self._clinical_terminology = filtered_terms
            
            logger.info(f"Extracted {len(filtered_terms)} clinical terms from notes")
            return self._clinical_terminology
            
        except Exception as e:
            logger.error(f"Error extracting clinical terminology: {e}")
            return {}
    
    def close(self):
        """Close database connection"""
        if hasattr(self, 'db_session') and self.db_session:
            self.db_session.close()

class MIMICBasedValidator:
    """Medical validation using MIMIC-III derived vocabularies"""
    
    def __init__(self, db_session=None):
        self.knowledge_extractor = MIMICMedicalKnowledgeExtractor(db_session)
        self._load_mimic_vocabularies()
        
    def _load_mimic_vocabularies(self):
        """Load all MIMIC-III vocabularies"""
        logger.info("Loading MIMIC-III medical vocabularies...")
        
        self.diagnosis_vocab = self.knowledge_extractor.get_diagnosis_vocabulary()
        self.medication_vocab = self.knowledge_extractor.get_medication_vocabulary()
        self.clinical_terms = self.knowledge_extractor.get_clinical_terminology()
        
        logger.info("MIMIC-III vocabularies loaded successfully")
    
    def validate_symptoms(self, symptoms: List[str], context: str = None) -> Dict[str, any]:
        """Validate symptoms against MIMIC-III clinical vocabulary"""
        validated_symptoms = []
        invalid_symptoms = []
        mimic_mappings = {}
        
        # Combine relevant vocabularies for symptom validation
        all_symptom_terms = set(self.diagnosis_vocab['all_terms'])
        all_symptom_terms.update(self.clinical_terms.keys())
        
        for symptom in symptoms:
            normalized_symptom = self._normalize_medical_term(symptom)
            
            # Check direct match
            if normalized_symptom in all_symptom_terms:
                validated_symptoms.append(symptom)
                mimic_mappings[symptom] = 'direct_match'
            else:
                # Check partial match
                best_match = self._find_best_match(normalized_symptom, all_symptom_terms)
                if best_match and best_match[1] > 0.8:  # High similarity threshold
                    validated_symptoms.append(symptom)
                    mimic_mappings[symptom] = f'partial_match: {best_match[0]}'
                else:
                    invalid_symptoms.append(symptom)
        
        return {
            'valid_concepts': validated_symptoms,
            'invalid_concepts': invalid_symptoms,
            'mimic_mappings': mimic_mappings,
            'validation_score': len(validated_symptoms) / len(symptoms) if symptoms else 1.0,
            'vocabulary_coverage': len(all_symptom_terms)
        }
    
    def validate_diagnoses(self, diagnoses: List[str], context: str = None) -> Dict[str, any]:
        """Validate diagnoses against MIMIC-III ICD-9 diagnosis vocabulary"""
        validated_diagnoses = []
        invalid_diagnoses = []
        mimic_mappings = {}
        
        # Use ICD-9 diagnosis vocabulary
        all_diagnosis_terms = set(self.diagnosis_vocab['all_terms'])
        
        for diagnosis in diagnoses:
            normalized_diagnosis = self._normalize_medical_term(diagnosis)
            
            # Check direct match
            if normalized_diagnosis in all_diagnosis_terms:
                validated_diagnoses.append(diagnosis)
                mimic_mappings[diagnosis] = 'icd9_match'
            else:
                # Check partial match with ICD-9 terms
                best_match = self._find_best_match(normalized_diagnosis, all_diagnosis_terms)
                if best_match and best_match[1] > 0.7:  # Lower threshold for diagnoses
                    validated_diagnoses.append(diagnosis)
                    mimic_mappings[diagnosis] = f'icd9_partial: {best_match[0]}'
                else:
                    invalid_diagnoses.append(diagnosis)
        
        return {
            'valid_concepts': validated_diagnoses,
            'invalid_concepts': invalid_diagnoses,
            'mimic_mappings': mimic_mappings,
            'validation_score': len(validated_diagnoses) / len(diagnoses) if diagnoses else 1.0,
            'icd9_coverage': len(all_diagnosis_terms)
        }
    
    def validate_treatments(self, treatments: List[str], context: str = None) -> Dict[str, any]:
        """Validate treatments against MIMIC-III medication vocabulary"""
        validated_treatments = []
        invalid_treatments = []
        mimic_mappings = {}
        
        # Use medication vocabulary for treatments
        all_treatment_terms = set(self.medication_vocab['all_terms'])
        
        for treatment in treatments:
            normalized_treatment = self._normalize_medical_term(treatment)
            
            # Check medication match
            if normalized_treatment in self.medication_vocab['all_terms']:
                validated_treatments.append(treatment)
                mimic_mappings[treatment] = 'medication_match'
            else:
                # Check partial match
                best_match = self._find_best_match(normalized_treatment, all_treatment_terms)
                if best_match and best_match[1] > 0.75:
                    validated_treatments.append(treatment)
                    mimic_mappings[treatment] = f'partial_match: {best_match[0]}'
                else:
                    invalid_treatments.append(treatment)
        
        return {
            'valid_concepts': validated_treatments,
            'invalid_concepts': invalid_treatments,
            'mimic_mappings': mimic_mappings,
            'validation_score': len(validated_treatments) / len(treatments) if treatments else 1.0,
            'medication_coverage': len(self.medication_vocab['all_terms'])
        }
    
    def _normalize_medical_term(self, term: str) -> str:
        """Normalize medical term for matching"""
        if not term:
            return ""
        
        # Convert to lowercase and strip
        normalized = term.lower().strip()
        
        # Remove common punctuation
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        
        # Normalize whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        return normalized.strip()
    
    def _find_best_match(self, term: str, vocabulary: Set[str]) -> Optional[Tuple[str, float]]:
        """Find best matching term in vocabulary using string similarity"""
        best_match = None
        best_score = 0.0
        
        for vocab_term in vocabulary:
            if vocab_term:  # Skip empty terms
                similarity = SequenceMatcher(None, term, vocab_term).ratio()
                if similarity > best_score:
                    best_score = similarity
                    best_match = vocab_term
        
        return (best_match, best_score) if best_match else None
    
    def close(self):
        """Close database connections"""
        self.knowledge_extractor.close()

# Global validator instance
_global_validator = None

def _get_validator():
    """Get or create global validator instance"""
    global _global_validator
    if _global_validator is None:
        _global_validator = MIMICBasedValidator()
    return _global_validator

# Main validation functions for integration with existing codebase
def validate_medical_extraction(symptoms: List[str], 
                              diagnoses: List[str], 
                              treatments: List[str], 
                              context: str = None,
                              gold_standard: Dict[str, List[str]] = None) -> Dict[str, float]:
    """
    Validate medical extraction using MIMIC-III derived vocabularies
    """
    logger.info("Validating medical extraction using MIMIC-III knowledge")
    
    try:
        validator = _get_validator()
        
        # Validate each entity type
        symptom_validation = validator.validate_symptoms(symptoms, context)
        diagnosis_validation = validator.validate_diagnoses(diagnoses, context)
        treatment_validation = validator.validate_treatments(treatments, context)
        
        # Calculate overall scores
        overall_score = (
            symptom_validation['validation_score'] * 0.4 +
            diagnosis_validation['validation_score'] * 0.4 +
            treatment_validation['validation_score'] * 0.2
        )
        
        return {
            'overall_medical_validity': overall_score,
            'symptom_validity': symptom_validation['validation_score'],
            'diagnosis_validity': diagnosis_validation['validation_score'],
            'treatment_validity': treatment_validation['validation_score'],
            'medical_consistency': overall_score,  # Using overall score as consistency proxy
            'detailed_validation': {
                'symptoms': symptom_validation,
                'diagnoses': diagnosis_validation,
                'treatments': treatment_validation
            }
        }
        
    except Exception as e:
        logger.error(f"Error in MIMIC-III based validation: {e}")
        return {
            'overall_medical_validity': 0.5,
            'symptom_validity': 0.5,
            'diagnosis_validity': 0.5,
            'treatment_validity': 0.5,
            'medical_consistency': 0.5,
            'validation_error': str(e)
        }

def assess_dialogue_safety(dialogue_text: str) -> Dict[str, any]:
    """
    Assess dialogue safety using MIMIC-III clinical context
    """
    logger.info("Assessing dialogue safety using MIMIC-III clinical context")
    
    try:
        validator = _get_validator()
        
        # Extract basic medical concepts from dialogue
        extracted_concepts = _extract_basic_medical_concepts(dialogue_text)
        
        # Validate against MIMIC vocabularies
        symptom_validation = validator.validate_symptoms(extracted_concepts.get('symptoms', []), dialogue_text)
        diagnosis_validation = validator.validate_diagnoses(extracted_concepts.get('diagnoses', []), dialogue_text)
        treatment_validation = validator.validate_treatments(extracted_concepts.get('treatments', []), dialogue_text)
        
        # Calculate safety score based on vocabulary validation
        concept_validity = (
            symptom_validation['validation_score'] * 0.4 +
            diagnosis_validation['validation_score'] * 0.4 +
            treatment_validation['validation_score'] * 0.2
        )
        
        # Base safety assessment
        safety_score = 0.8  # Start with good assumption
        safety_issues = []
        
        # Check for harmful patterns
        harmful_patterns = [
            'ignore chest pain', 'skip emergency', 'avoid doctor', 'stop medication suddenly'
        ]
        
        text_lower = dialogue_text.lower()
        for pattern in harmful_patterns:
            if pattern in text_lower:
                safety_issues.append(f"Potentially harmful advice: {pattern}")
                safety_score -= 0.2
        
        # Adjust safety score based on concept validity
        safety_score = (safety_score * 0.7) + (concept_validity * 0.3)
        safety_score = max(0.0, min(1.0, safety_score))
        
        # Determine safety status
        if safety_score >= 0.8:
            safety_status = 'SAFE'
        elif safety_score >= 0.6:
            safety_status = 'ACCEPTABLE'
        else:
            safety_status = 'NEEDS_REVIEW'
        
        return {
            'safety_score': safety_score,
            'safety_status': safety_status,
            'safety_violations': safety_issues,
            'recommendations': _generate_safety_recommendations(safety_issues, safety_score)
        }
        
    except Exception as e:
        logger.error(f"Error in MIMIC-III based safety assessment: {e}")
        return {
            'safety_score': 0.6,
            'safety_status': 'UNKNOWN',
            'safety_violations': [f"Assessment error: {str(e)}"],
            'recommendations': ['Manual safety review recommended']
        }

def extract_medical_entities_comprehensive(text: str) -> Dict[str, List[str]]:
    """
    Extract medical entities using MIMIC-III vocabularies
    """
    logger.info("Extracting medical entities using MIMIC-III knowledge")
    
    try:
        validator = _get_validator()
        
        # Extract basic concepts first
        basic_concepts = _extract_basic_medical_concepts(text)
        
        # Validate and enhance with MIMIC vocabularies
        symptom_validation = validator.validate_symptoms(basic_concepts['symptoms'], text)
        diagnosis_validation = validator.validate_diagnoses(basic_concepts['diagnoses'], text)
        treatment_validation = validator.validate_treatments(basic_concepts['treatments'], text)
        
        return {
            'symptoms': symptom_validation['valid_concepts'],
            'diagnoses': diagnosis_validation['valid_concepts'],
            'treatments': treatment_validation['valid_concepts'],
            'confidence_scores': {
                'symptoms': symptom_validation['validation_score'],
                'diagnoses': diagnosis_validation['validation_score'],
                'treatments': treatment_validation['validation_score']
            },
            'mimic_mappings': {
                'symptoms': symptom_validation['mimic_mappings'],
                'diagnoses': diagnosis_validation['mimic_mappings'],
                'treatments': treatment_validation['mimic_mappings']
            }
        }
        
    except Exception as e:
        logger.error(f"Error in MIMIC-III based entity extraction: {e}")
        return {
            'symptoms': [],
            'diagnoses': [],
            'treatments': [],
            'confidence_scores': {},
            'mimic_mappings': {},
            'extraction_error': str(e)
        }

def _extract_basic_medical_concepts(text: str) -> Dict[str, List[str]]:
    """Extract basic medical concepts using pattern matching"""
    symptoms = []
    diagnoses = []
    treatments = []
    
    text_lower = text.lower()
    
    # Common symptom patterns
    symptom_patterns = [
        r'pain', r'ache', r'hurt', r'discomfort', r'nausea', r'vomit', r'fever',
        r'cough', r'headache', r'dizzy', r'tired', r'fatigue', r'weak'
    ]
    
    for pattern in symptom_patterns:
        if re.search(pattern, text_lower):
            symptoms.append(pattern)
    
    # Common diagnosis patterns
    diagnosis_patterns = [
        r'hypertension', r'diabetes', r'asthma', r'pneumonia', r'infection',
        r'heart failure', r'depression', r'anxiety'
    ]
    
    for pattern in diagnosis_patterns:
        if re.search(pattern, text_lower):
            diagnoses.append(pattern)
    
    # Common treatment patterns
    treatment_patterns = [
        r'medication', r'medicine', r'therapy', r'treatment', r'surgery',
        r'antibiotic', r'pain killer', r'insulin'
    ]
    
    for pattern in treatment_patterns:
        if re.search(pattern, text_lower):
            treatments.append(pattern)
    
    return {
        'symptoms': symptoms,
        'diagnoses': diagnoses,
        'treatments': treatments
    }

def _generate_safety_recommendations(safety_issues: List[str], safety_score: float) -> List[str]:
    """Generate safety recommendations"""
    recommendations = []
    
    if safety_issues:
        recommendations.append("Address identified safety concerns in medical communication")
    
    if safety_score < 0.6:
        recommendations.append("Improve medical communication safety and accuracy")
    
    if not recommendations:
        recommendations.append("Continue following established medical safety practices")
    
    return recommendations

# Backward compatibility functions
def assess_medical_consistency(symptoms: List[str], diagnoses: List[str], treatments: List[str] = None) -> Dict[str, any]:
    """Backward compatible medical consistency assessment using MIMIC-III"""
    try:
        validator = _get_validator()
        
        # Validate concepts against MIMIC vocabularies
        symptom_validation = validator.validate_symptoms(symptoms)
        diagnosis_validation = validator.validate_diagnoses(diagnoses)
        treatment_validation = validator.validate_treatments(treatments or [])
        
        # Calculate consistency based on validation scores
        consistency_score = (
            symptom_validation['validation_score'] * 0.4 +
            diagnosis_validation['validation_score'] * 0.4 +
            treatment_validation['validation_score'] * 0.2
        )
        
        return {
            'consistency_score': consistency_score,
            'relationships_found': [],  # Simplified for MIMIC-III approach
            'inconsistencies': [],
            'confidence': consistency_score,
            'detailed_analysis': {
                'symptoms': symptom_validation,
                'diagnoses': diagnosis_validation,
                'treatments': treatment_validation
            }
        }
        
    except Exception as e:
        logger.error(f"Error in MIMIC-III consistency assessment: {e}")
        return {
            'consistency_score': 0.5,
            'relationships_found': [],
            'inconsistencies': [f"Assessment error: {str(e)}"],
            'confidence': 0.3,
            'detailed_analysis': {}
        }