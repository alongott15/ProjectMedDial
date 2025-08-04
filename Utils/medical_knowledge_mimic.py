# Utils/medical_knowledge_mimic.py
"""
Enhanced Medical Knowledge Base using MIMIC-III structured data and medical ontologies
"""
import logging
import pandas as pd
from sqlalchemy import create_engine, text
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)

@dataclass
class MedicalValidationResult:
    """Standard medical validation result structure"""
    validity_score: float  # 0-1
    concept_coverage: float  # 0-1
    terminology_accuracy: float  # 0-1
    clinical_coherence: float  # 0-1
    safety_score: float  # 0-1
    detailed_scores: dict
    issues: list
    suggestions: list

class MIMICMedicalKnowledgeBase:
    """Enhanced medical knowledge base using MIMIC-III structured data"""
    
    def __init__(self, db_uri: str):
        self.engine = create_engine(db_uri)
        self._load_mimic_knowledge()
        self._load_medical_ontologies()
        
    def _load_mimic_knowledge(self):
        """Load structured medical knowledge from MIMIC-III"""
        logger.info("Loading MIMIC-III medical knowledge base...")
        
        # Load ICD-9 diagnoses with frequency
        self.icd9_diagnoses = self._load_icd9_knowledge()
        
        # Load procedures with co-occurrence patterns
        self.procedures = self._load_procedure_knowledge()
        
        # Load medications with indications
        self.medications = self._load_medication_knowledge()
        
        # Load symptom-diagnosis associations from clinical notes
        self.symptom_diagnosis_patterns = self._extract_clinical_patterns()
        
        logger.info(f"Loaded {len(self.icd9_diagnoses)} diagnoses, "
                   f"{len(self.procedures)} procedures, "
                   f"{len(self.medications)} medications")
    
    def _load_icd9_knowledge(self):
        """Load ICD-9 diagnosis codes with clinical context from MIMIC-III"""
        query = text("""
            SELECT 
                d.icd9_code,
                d.short_title,
                d.long_title,
                COUNT(*) as frequency,
                AVG(CASE WHEN a.hospital_expire_flag = 1 THEN 1.0 ELSE 0.0 END) as mortality_rate
            FROM diagnoses_icd diag
            JOIN d_icd_diagnoses d ON diag.icd9_code = d.icd9_code
            JOIN admissions a ON diag.hadm_id = a.hadm_id
            GROUP BY d.icd9_code, d.short_title, d.long_title
            HAVING COUNT(*) >= 10
            ORDER BY frequency DESC
        """)
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(query)
                diagnoses = {}
                for row in result:
                    diagnoses[row.icd9_code] = {
                        'short_title': row.short_title,
                        'long_title': row.long_title,
                        'frequency': row.frequency,
                        'mortality_rate': float(row.mortality_rate),
                        'severity': 'high' if row.mortality_rate > 0.1 else 'medium' if row.mortality_rate > 0.05 else 'low'
                    }
                return diagnoses
        except Exception as e:
            logger.error(f"Error loading ICD-9 knowledge: {e}")
            return {}
    
    def _load_medication_knowledge(self):
        """Load medication knowledge with clinical context"""
        query = text("""
            SELECT 
                di.label,
                COUNT(DISTINCT p.hadm_id) as prescription_count,
                AVG(EXTRACT(EPOCH FROM (p.enddate - p.startdate))/86400) as avg_duration_days,
                COUNT(DISTINCT diag.icd9_code) as indication_diversity
            FROM prescriptions p
            JOIN d_items di ON p.drug_name_generic = di.label
            LEFT JOIN diagnoses_icd diag ON p.hadm_id = diag.hadm_id
            WHERE p.drug_name_generic IS NOT NULL
            GROUP BY di.label
            HAVING COUNT(DISTINCT p.hadm_id) >= 50
            ORDER BY prescription_count DESC
            LIMIT 1000
        """)
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(query)
                medications = {}
                for row in result:
                    medications[row.drug.lower()] = {
                        'prescription_count': row.prescription_count,
                        'avg_duration_days': float(row.avg_duration_days or 0),
                        'indication_diversity': row.indication_diversity,
                        'category': self._classify_medication(row.drug)
                    }
                return medications
        except Exception as e:
            logger.error(f"Error loading medication knowledge: {e}")
            return {}
    
    def _load_procedure_knowledge(self):
        """Load procedure knowledge from MIMIC-III"""
        query = text("""
            SELECT 
                d.icd9_code,
                d.short_title,
                d.long_title,
                COUNT(*) as frequency
            FROM procedures_icd p
            JOIN d_icd_procedures d ON p.icd9_code = d.icd9_code
            GROUP BY d.icd9_code, d.short_title, d.long_title
            HAVING COUNT(*) >= 5
            ORDER BY frequency DESC
        """)
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(query)
                procedures = {}
                for row in result:
                    procedures[row.icd9_code] = {
                        'short_title': row.short_title,
                        'long_title': row.long_title,
                        'frequency': row.frequency,
                        'invasiveness': self._classify_procedure_invasiveness(row.short_title)
                    }
                return procedures
        except Exception as e:
            logger.error(f"Error loading procedure knowledge: {e}")
            return {}
    
    def _extract_clinical_patterns(self):
        """Extract symptom-diagnosis patterns from clinical notes"""
        # This would be implemented with more sophisticated NLP
        # For now, return common patterns from medical literature
        return {
            'chest_pain': ['myocardial_infarction', 'angina', 'pulmonary_embolism', 'gerd'],
            'shortness_of_breath': ['heart_failure', 'asthma', 'copd', 'pneumonia'],
            'abdominal_pain': ['appendicitis', 'cholecystitis', 'peptic_ulcer', 'gastritis'],
            'headache': ['migraine', 'tension_headache', 'hypertension', 'meningitis']
        }
    
    def _load_medical_ontologies(self):
        """Load medical ontologies (simplified version)"""
        # In production, would load from UMLS, SNOMED-CT, etc.
        self.umls_concepts = self._load_simplified_umls()
        self.drug_interactions = self._load_drug_interactions()
        
    def _load_simplified_umls(self):
        """Simplified UMLS concept mapping"""
        return {
            'symptoms': {
                'chest pain', 'dyspnea', 'shortness of breath', 'abdominal pain',
                'headache', 'nausea', 'vomiting', 'fever', 'fatigue', 'dizziness'
            },
            'diseases': {
                'myocardial infarction', 'heart failure', 'pneumonia', 'asthma',
                'diabetes mellitus', 'hypertension', 'copd', 'stroke'
            },
            'medications': {
                'aspirin', 'metoprolol', 'lisinopril', 'atorvastatin', 'metformin',
                'albuterol', 'furosemide', 'warfarin', 'insulin'
            }
        }
    
    def _load_drug_interactions(self):
        """Load known drug-drug interactions"""
        return {
            'warfarin': ['aspirin', 'ibuprofen', 'amiodarone'],
            'digoxin': ['quinidine', 'verapamil', 'amiodarone'],
            'metformin': ['contrast agents', 'alcohol'],
            'ace_inhibitors': ['potassium', 'spironolactone']
        }
    
    def _classify_medication(self, drug_name: str):
        """Classify medication by therapeutic category"""
        drug_lower = drug_name.lower()
        
        if any(term in drug_lower for term in ['aspirin', 'ibuprofen', 'acetaminophen']):
            return 'analgesic'
        elif any(term in drug_lower for term in ['lisinopril', 'metoprolol', 'amlodipine']):
            return 'cardiovascular'
        elif any(term in drug_lower for term in ['metformin', 'insulin']):
            return 'antidiabetic'
        elif any(term in drug_lower for term in ['albuterol', 'prednisone']):
            return 'respiratory'
        else:
            return 'other'
    
    def _classify_procedure_invasiveness(self, procedure_title: str):
        """Classify procedure invasiveness level"""
        title_lower = procedure_title.lower()
        
        if any(term in title_lower for term in ['surgery', 'incision', 'transplant']):
            return 'highly_invasive'
        elif any(term in title_lower for term in ['catheter', 'biopsy', 'endoscopy']):
            return 'moderately_invasive'
        else:
            return 'minimally_invasive'
    
    def validate_clinical_coherence(self, symptoms, diagnoses, treatments):
        """
        Validate clinical coherence using MIMIC-III knowledge base
        """
        issues = []
        suggestions = []
        detailed_scores = {}
        
        # 1. Validate symptom-diagnosis coherence
        symptom_diagnosis_score = self._validate_symptom_diagnosis_coherence(symptoms, diagnoses)
        detailed_scores['symptom_diagnosis_coherence'] = symptom_diagnosis_score
        
        # 2. Validate diagnosis-treatment appropriateness
        treatment_appropriateness = self._validate_treatment_appropriateness(diagnoses, treatments)
        detailed_scores['treatment_appropriateness'] = treatment_appropriateness
        
        # 3. Check for drug interactions
        interaction_safety = self._check_drug_interactions(treatments)
        detailed_scores['drug_safety'] = interaction_safety
        
        # 4. Validate medical terminology
        terminology_score = self._validate_medical_terminology(symptoms + diagnoses + treatments)
        detailed_scores['terminology_accuracy'] = terminology_score
        
        # 5. Calculate concept coverage using MIMIC-III frequencies
        concept_coverage = self._calculate_concept_coverage(diagnoses)
        detailed_scores['concept_coverage'] = concept_coverage
        
        # Calculate overall scores
        clinical_coherence = (symptom_diagnosis_score + treatment_appropriateness) / 2
        safety_score = min(interaction_safety, 1.0)
        validity_score = sum(detailed_scores.values()) / len(detailed_scores)
        
        return MedicalValidationResult(
            validity_score=validity_score,
            concept_coverage=concept_coverage,
            terminology_accuracy=terminology_score,
            clinical_coherence=clinical_coherence,
            safety_score=safety_score,
            detailed_scores=detailed_scores,
            issues=issues,
            suggestions=suggestions
        )
    
    def _validate_symptom_diagnosis_coherence(self, symptoms, diagnoses):
        """Validate symptom-diagnosis relationships using clinical patterns"""
        if not symptoms or not diagnoses:
            return 0.5
        
        coherence_scores = []
        
        for symptom in symptoms:
            symptom_clean = symptom.lower().replace(' ', '_')
            if symptom_clean in self.symptom_diagnosis_patterns:
                expected_diagnoses = self.symptom_diagnosis_patterns[symptom_clean]
                
                # Check if any diagnosis matches expected patterns
                match_found = False
                for diagnosis in diagnoses:
                    if any(exp_diag in diagnosis.lower() for exp_diag in expected_diagnoses):
                        match_found = True
                        break
                
                coherence_scores.append(1.0 if match_found else 0.3)
            else:
                coherence_scores.append(0.7)  # Neutral for unknown symptoms
        
        return sum(coherence_scores) / len(coherence_scores) if coherence_scores else 0.5
    
    def _validate_treatment_appropriateness(self, diagnoses, treatments):
        """Validate treatment appropriateness for given diagnoses"""
        if not diagnoses or not treatments:
            return 0.5
        
        # Simplified treatment validation using medication categories
        appropriateness_scores = []
        
        for treatment in treatments:
            if treatment.lower() in self.medications:
                med_info = self.medications[treatment.lower()]
                # Higher scores for more frequently prescribed medications
                frequency_score = min(1.0, med_info['prescription_count'] / 1000)
                appropriateness_scores.append(frequency_score)
            else:
                appropriateness_scores.append(0.4)  # Lower score for unknown treatments
        
        return sum(appropriateness_scores) / len(appropriateness_scores) if appropriateness_scores else 0.5
    
    def _check_drug_interactions(self, treatments):
        """Check for dangerous drug interactions"""
        if len(treatments) < 2:
            return 1.0
        
        interaction_penalties = 0
        total_pairs = 0
        
        for i, drug1 in enumerate(treatments):
            for drug2 in treatments[i+1:]:
                total_pairs += 1
                
                drug1_clean = drug1.lower()
                drug2_clean = drug2.lower()
                
                # Check for known interactions
                for drug, interactions in self.drug_interactions.items():
                    if drug in drug1_clean and any(inter in drug2_clean for inter in interactions):
                        interaction_penalties += 1
                    elif drug in drug2_clean and any(inter in drug1_clean for inter in interactions):
                        interaction_penalties += 1
        
        if total_pairs == 0:
            return 1.0
        
        safety_score = 1.0 - (interaction_penalties / total_pairs)
        return max(0.0, safety_score)
    
    def _validate_medical_terminology(self, terms):
        """Validate medical terminology using UMLS concepts"""
        if not terms:
            return 1.0
        
        valid_terms = 0
        
        for term in terms:
            term_clean = term.lower()
            
            # Check against UMLS concepts
            is_valid = False
            for category, concepts in self.umls_concepts.items():
                if any(concept in term_clean for concept in concepts):
                    is_valid = True
                    break
            
            if is_valid:
                valid_terms += 1
        
        return valid_terms / len(terms)
    
    def _calculate_concept_coverage(self, diagnoses):
        """Calculate concept coverage based on MIMIC-III diagnosis frequencies"""
        if not diagnoses:
            return 0.0
        
        coverage_scores = []
        
        for diagnosis in diagnoses:
            # Find matching ICD-9 codes
            best_match_frequency = 0
            
            for icd_code, diag_info in self.icd9_diagnoses.items():
                if (diagnosis.lower() in diag_info['short_title'].lower() or 
                    diagnosis.lower() in diag_info['long_title'].lower()):
                    best_match_frequency = max(best_match_frequency, diag_info['frequency'])
            
            # Convert frequency to coverage score (log scale)
            if best_match_frequency > 0:
                import math
                coverage_score = min(1.0, math.log10(best_match_frequency) / 4)  # Normalize to 0-1
                coverage_scores.append(coverage_score)
            else:
                coverage_scores.append(0.1)  # Low score for unrecognized diagnoses
        
        return sum(coverage_scores) / len(coverage_scores)