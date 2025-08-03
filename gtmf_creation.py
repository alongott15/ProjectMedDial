import json
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from Models.classes import GTMF
from Utils.utils import get_db_uri, format_date, build_symptom_conditions, calculate_age
from Utils.medical_validation import validate_medical_extraction, assess_dialogue_safety, MedicalConceptValidator
import re
import os
from typing import Dict, List, Tuple
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class GTMFQualityScore:
    """FIXED: Realistic quality assessment for GTMF extraction"""
    completeness_score: float  # 0-1, how much of the note was captured
    accuracy_score: float      # 0-1, how accurate the extractions are
    consistency_score: float   # 0-1, internal consistency of extracted data
    confidence_score: float    # 0-1, model confidence in extractions
    medical_validity: float    # 0-1, medical concept validity
    safety_score: float        # 0-1, medical safety assessment
    field_scores: Dict[str, float]  # Individual field quality scores
    issues: List[str]          # List of identified issues
    recommendations: List[str]  # Improvement recommendations

class AzureAIClient:
    """Azure AI client wrapper for GTMF extraction"""
    
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
    
    def chat_completion(self, system_message: str, user_message: str, temperature: float = 0.0) -> str:
        """Generate chat completion using Azure AI"""
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

def chunk_medical_text(text: str, max_chunk_size: int = 3000, overlap: int = 200) -> List[str]:
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

class GTMFQualityAssessor:
    """FIXED: Realistic GTMF extraction quality assessment"""
    
    def __init__(self, azure_client: AzureAIClient):
        self.azure_client = azure_client
        self.medical_validator = MedicalConceptValidator()
    
    def assess_gtmf_quality(self, medical_text: str, gtmf_instance: GTMF) -> GTMFQualityScore:
        """FIXED: Realistic quality assessment of GTMF extraction"""
        
        # Convert GTMF to dict for easier analysis
        gtmf_dict = gtmf_instance.model_dump()
        
        # Extract medical data for validation
        symptoms = [s.description for s in gtmf_instance.Core_Fields.Symptoms if s.description and s.description != "not provided"]
        diagnoses = [d.primary for d in gtmf_instance.Core_Fields.Diagnoses if d.primary and d.primary != "not provided"]
        treatments = [t.procedure for t in gtmf_instance.Core_Fields.Treatment_Options if t.procedure and t.procedure != "not provided"]
        
        # 1. MEDICAL VALIDITY using medical validation utils
        medical_validation = validate_medical_extraction(symptoms, diagnoses, treatments)
        medical_validity_score = medical_validation['overall_medical_validity']
        
        # 2. MEDICAL SAFETY assessment
        safety_assessment = assess_dialogue_safety(medical_text)
        safety_score = safety_assessment['safety_score']
        
        # 3. REALISTIC field assessments
        field_scores = {}
        issues = []
        
        # Assess symptoms realistically
        symptoms_score, symptoms_issues = self._assess_symptoms_realistic(medical_text, symptoms)
        field_scores["symptoms"] = symptoms_score
        issues.extend(symptoms_issues)
        
        # Assess diagnoses realistically
        diagnoses_score, diagnoses_issues = self._assess_diagnoses_realistic(medical_text, diagnoses)
        field_scores["diagnoses"] = diagnoses_score
        issues.extend(diagnoses_issues)
        
        # Assess treatments realistically
        treatments_score, treatments_issues = self._assess_treatments_realistic(medical_text, treatments)
        field_scores["treatments"] = treatments_score
        issues.extend(treatments_issues)
        
        # 4. REALISTIC completeness assessment
        completeness_score = self._assess_completeness_realistic(medical_text, gtmf_dict)
        
        # 5. REALISTIC consistency assessment
        consistency_score = self._assess_consistency_realistic(symptoms, diagnoses)
        
        # 6. REALISTIC accuracy assessment (no more inflated Azure AI scores)
        accuracy_score = self._calculate_realistic_accuracy(field_scores, medical_validity_score)
        
        # 7. REALISTIC confidence score
        confidence_score = self._calculate_realistic_confidence(field_scores, issues)
        
        # Generate realistic recommendations
        recommendations = self._generate_realistic_recommendations(field_scores, issues, medical_validation)
        
        return GTMFQualityScore(
            completeness_score=completeness_score,
            accuracy_score=accuracy_score,
            consistency_score=consistency_score,
            confidence_score=confidence_score,
            medical_validity=medical_validity_score,
            safety_score=safety_score,
            field_scores=field_scores,
            issues=issues,
            recommendations=recommendations
        )
    
    def _assess_symptoms_realistic(self, text: str, symptoms: List[str]) -> Tuple[float, List[str]]:
        """REALISTIC symptom assessment"""
        issues = []
        
        if not symptoms:
            # Check if text actually contains symptoms
            medical_entities = self.medical_validator.extract_medical_entities(text)
            if medical_entities['symptoms']:
                issues.append("Symptoms present in text but none extracted")
                return 0.3, issues  # Realistic penalty
            else:
                return 0.8, issues  # Realistic score when no symptoms exist
        
        # Validate symptoms using medical validator
        validation = self.medical_validator.validate_medical_terms(symptoms, 'symptoms')
        
        # Check text coverage
        symptoms_found_in_text = 0
        for symptom in symptoms:
            if symptom.lower() in text.lower():
                symptoms_found_in_text += 1
            else:
                # Check partial match
                words = symptom.lower().split()
                if any(word in text.lower() for word in words if len(word) > 3):
                    symptoms_found_in_text += 0.5
        
        text_coverage = symptoms_found_in_text / len(symptoms) if symptoms else 0.0
        
        # REALISTIC scoring
        score = (validation['validity_score'] * 0.6 + text_coverage * 0.4)
        
        if validation['invalid_terms']:
            issues.append(f"Invalid medical terms: {', '.join(validation['invalid_terms'][:3])}")
        
        if text_coverage < 0.5:
            issues.append("Many symptoms not clearly found in original text")
        
        return score, issues
    
    def _assess_diagnoses_realistic(self, text: str, diagnoses: List[str]) -> Tuple[float, List[str]]:
        """REALISTIC diagnosis assessment"""
        issues = []
        
        if not diagnoses:
            # Check if text contains diagnostic information
            if any(indicator in text.lower() for indicator in ["diagnosis", "diagnosed", "condition"]):
                issues.append("Diagnostic information present but no diagnoses extracted")
                return 0.4, issues
            return 0.8, issues
        
        # Validate diagnoses using medical validator
        validation = self.medical_validator.validate_medical_terms(diagnoses, 'diagnoses')
        
        # Check text coverage
        diagnoses_found_in_text = 0
        for diagnosis in diagnoses:
            if diagnosis.lower() in text.lower():
                diagnoses_found_in_text += 1
            else:
                # Check partial match
                words = diagnosis.lower().split()
                if any(word in text.lower() for word in words if len(word) > 3):
                    diagnoses_found_in_text += 0.5
        
        text_coverage = diagnoses_found_in_text / len(diagnoses) if diagnoses else 0.0
        
        # REALISTIC scoring
        score = (validation['validity_score'] * 0.7 + text_coverage * 0.3)
        
        if validation['invalid_terms']:
            issues.append(f"Invalid diagnoses: {', '.join(validation['invalid_terms'][:3])}")
        
        return score, issues
    
    def _assess_treatments_realistic(self, text: str, treatments: List[str]) -> Tuple[float, List[str]]:
        """REALISTIC treatment assessment"""
        issues = []
        
        if not treatments:
            if any(indicator in text.lower() for indicator in ["treatment", "therapy", "medication"]):
                issues.append("Treatment information present but none extracted")
                return 0.4, issues
            return 0.8, issues
        
        # Validate treatments using medical validator
        validation = self.medical_validator.validate_medical_terms(treatments, 'treatments')
        
        # Check text coverage
        treatments_found_in_text = 0
        for treatment in treatments:
            if treatment.lower() in text.lower():
                treatments_found_in_text += 1
            else:
                # Check partial match
                words = treatment.lower().split()
                if any(word in text.lower() for word in words if len(word) > 3):
                    treatments_found_in_text += 0.5
        
        text_coverage = treatments_found_in_text / len(treatments) if treatments else 0.0
        
        # REALISTIC scoring
        score = (validation['validity_score'] * 0.7 + text_coverage * 0.3)
        
        if validation['invalid_terms']:
            issues.append(f"Invalid treatments: {', '.join(validation['invalid_terms'][:3])}")
        
        return score, issues
    
    def _assess_completeness_realistic(self, text: str, gtmf_dict: Dict) -> float:
        """REALISTIC completeness assessment"""
        text_length = len(text.split())
        
        # Count extracted content
        core_fields = gtmf_dict.get("Core_Fields", {})
        
        symptom_count = len([s for s in core_fields.get("Symptoms", []) 
                           if s.get("description", "").strip() and s.get("description") != "not provided"])
        diagnosis_count = len([d for d in core_fields.get("Diagnoses", []) 
                             if d.get("primary", "").strip() and d.get("primary") != "not provided"])
        treatment_count = len([t for t in core_fields.get("Treatment_Options", []) 
                             if t.get("procedure", "").strip() and t.get("procedure") != "not provided"])
        
        # REALISTIC expected content based on text length
        if text_length < 200:
            expected_items = 2
        elif text_length < 500:
            expected_items = 4
        elif text_length < 1000:
            expected_items = 6
        else:
            expected_items = 8
        
        actual_items = symptom_count + diagnosis_count + treatment_count
        
        # REALISTIC completeness calculation
        completeness = min(1.0, actual_items / expected_items)
        
        # Bonus for having items in each category (realistic medical notes should have variety)
        category_bonus = 0.0
        if symptom_count > 0 and diagnosis_count > 0:
            category_bonus += 0.1
        if treatment_count > 0:
            category_bonus += 0.05
        
        return min(1.0, completeness + category_bonus)
    
    def _assess_consistency_realistic(self, symptoms: List[str], diagnoses: List[str]) -> float:
        """REALISTIC consistency assessment using medical validator"""
        if not symptoms or not diagnoses:
            return 0.7  # Neutral score when data is missing
        
        # Use medical validator for consistency assessment
        consistency_result = self.medical_validator.assess_medical_consistency(symptoms, diagnoses)
        return consistency_result['consistency_score']
    
    def _calculate_realistic_accuracy(self, field_scores: Dict[str, float], medical_validity: float) -> float:
        """REALISTIC accuracy calculation"""
        # Weight field scores realistically
        symptom_weight = 0.4
        diagnosis_weight = 0.4
        treatment_weight = 0.2
        
        field_accuracy = (
            field_scores.get("symptoms", 0.5) * symptom_weight +
            field_scores.get("diagnoses", 0.5) * diagnosis_weight +
            field_scores.get("treatments", 0.5) * treatment_weight
        )
        
        # Combine with medical validity
        accuracy = (field_accuracy * 0.7 + medical_validity * 0.3)
        
        return accuracy
    
    def _calculate_realistic_confidence(self, field_scores: Dict[str, float], issues: List[str]) -> float:
        """REALISTIC confidence calculation"""
        # Base confidence from field scores
        avg_field_score = sum(field_scores.values()) / len(field_scores) if field_scores else 0.5
        
        # Penalty for issues
        issue_penalty = min(0.3, len(issues) * 0.1)
        
        confidence = max(0.1, avg_field_score - issue_penalty)
        
        return confidence
    
    def _generate_realistic_recommendations(self, field_scores: Dict[str, float], issues: List[str], 
                                          medical_validation: Dict[str, float]) -> List[str]:
        """Generate realistic improvement recommendations"""
        recommendations = []
        
        # Field-specific recommendations
        if field_scores.get("symptoms", 1.0) < 0.6:
            recommendations.append("Improve symptom extraction accuracy and medical terminology")
        
        if field_scores.get("diagnoses", 1.0) < 0.6:
            recommendations.append("Enhance diagnosis extraction and validation")
        
        if field_scores.get("treatments", 1.0) < 0.6:
            recommendations.append("Better treatment and medication identification")
        
        # Medical validity recommendations
        if medical_validation['overall_medical_validity'] < 0.7:
            recommendations.append("Improve medical concept validation and consistency")
        
        # Issue-based recommendations
        if len(issues) > 3:
            recommendations.append("Address multiple extraction issues for better quality")
        
        # Safety recommendations
        if any("safety" in issue.lower() for issue in issues):
            recommendations.append("Review and improve medical safety compliance")
        
        return recommendations[:5]  # Limit to top 5 recommendations

def extract_gtmf_chunked(medical_text: str, azure_client: AzureAIClient) -> Tuple[GTMF, GTMFQualityScore]:
    """
    FIXED: Extract structured GTMF data with realistic quality assessment
    """
    logger.info("Extracting GTMF from medical text with realistic quality assessment")
    
    # Get GTMF schema
    schema_json = GTMF.model_json_schema()
    
    # Chunk the text if it's too long
    chunks = chunk_medical_text(medical_text, max_chunk_size=3000, overlap=200)
    logger.info(f"Processing {len(chunks)} chunks")
    
    # System message for extraction
    system_message = """You are a medical information extraction expert. Your task is to extract all relevant details from medical notes and convert them into structured JSON format.

    Key Instructions:
    1. Extract ALL medical information present in the text
    2. If you have multiple symptoms or diagnoses, create separate objects for each one
    3. If information is missing, use 'not provided' for string fields or empty arrays for lists
    4. Include medications as part of treatment options
    5. Your output must be valid JSON that conforms to the provided schema
    6. Focus on accuracy and completeness"""
    
    all_extractions = []
    
    # Process each chunk
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
    
    # Merge extractions from all chunks
    merged_extraction = merge_gtmf_extractions(all_extractions)
    
    try:
        structured_output = GTMF(**merged_extraction)
        
        # REALISTIC quality assessment
        assessor = GTMFQualityAssessor(azure_client)
        quality_score = assessor.assess_gtmf_quality(medical_text, structured_output)
        
        logger.info(f"GTMF extraction completed with REALISTIC quality scores: "
                   f"Completeness={quality_score.completeness_score:.2f}, "
                   f"Accuracy={quality_score.accuracy_score:.2f}, "
                   f"Medical Validity={quality_score.medical_validity:.2f}, "
                   f"Safety={quality_score.safety_score:.2f}")
        
        return structured_output, quality_score
        
    except Exception as e:
        logger.error(f"Error in extract_gtmf_chunked: {e}")
        raise

def merge_gtmf_extractions(extractions: List[Dict]) -> Dict:
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

def process_notes(results, azure_client: AzureAIClient):
    """FIXED: Process fetched notes with realistic quality scoring"""
    logger.info("Processing fetched notes with REALISTIC quality assessment")
    structured_results = []
    quality_summary = {
        "total_processed": 0,
        "high_quality": 0,     # >0.7 overall score (realistic)
        "medium_quality": 0,   # 0.5-0.7 overall score
        "low_quality": 0,      # <0.5 overall score
        "common_issues": [],
        "average_scores": {}
    }

    for idx, row in enumerate(results):
        try:
            # Demographics processing
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

            # Extract GTMF with REALISTIC quality assessment
            gtmf_instance, quality_score = extract_gtmf_chunked(row['text'], azure_client)

            # Update quality summary with REALISTIC scoring
            quality_summary["total_processed"] += 1
            overall_score = (quality_score.completeness_score + 
                           quality_score.accuracy_score + 
                           quality_score.medical_validity + 
                           quality_score.safety_score) / 4
            
            # REALISTIC quality thresholds
            if overall_score > 0.7:
                quality_summary["high_quality"] += 1
            elif overall_score > 0.5:
                quality_summary["medium_quality"] += 1
            else:
                quality_summary["low_quality"] += 1
            
            quality_summary["common_issues"].extend(quality_score.issues)

            # Update GTMF with metadata and demographics
            gtmf_instance = gtmf_instance.model_copy(update={
                "row_id": row['row_id'],
                "subject_id": row['subject_id'],
                "hadm_id": row['hadm_id'],
                "Context_Fields": gtmf_instance.Context_Fields.model_copy(update={
                    "Patient_Demographics": gtmf_instance.Context_Fields.Patient_Demographics.model_copy(update=demographics)
                })
            })
            
            # Include REALISTIC quality scores in output
            result_with_quality = gtmf_instance.model_dump()
            result_with_quality["quality_assessment"] = {
                "completeness_score": quality_score.completeness_score,
                "accuracy_score": quality_score.accuracy_score,
                "consistency_score": quality_score.consistency_score,
                "confidence_score": quality_score.confidence_score,
                "medical_validity": quality_score.medical_validity,
                "safety_score": quality_score.safety_score,
                "overall_score": overall_score,
                "field_scores": quality_score.field_scores,
                "issues": quality_score.issues,
                "recommendations": quality_score.recommendations
            }
            
            structured_results.append(result_with_quality)
            logger.info(f"Processed note {idx} with REALISTIC overall quality score: {overall_score:.2f}")
            
        except Exception as e:
            logger.error(f"Error processing note at index {idx}: {e}")
            quality_summary["total_processed"] += 1
            quality_summary["low_quality"] += 1
    
    # Calculate average scores
    if structured_results:
        avg_completeness = sum(r["quality_assessment"]["completeness_score"] for r in structured_results) / len(structured_results)
        avg_accuracy = sum(r["quality_assessment"]["accuracy_score"] for r in structured_results) / len(structured_results)
        avg_medical_validity = sum(r["quality_assessment"]["medical_validity"] for r in structured_results) / len(structured_results)
        avg_safety = sum(r["quality_assessment"]["safety_score"] for r in structured_results) / len(structured_results)
        
        quality_summary["average_scores"] = {
            "completeness": avg_completeness,
            "accuracy": avg_accuracy,
            "medical_validity": avg_medical_validity,
            "safety": avg_safety
        }
    
    # Log REALISTIC quality summary
    logger.info(f"REALISTIC Quality Summary: {quality_summary['high_quality']} high, "
               f"{quality_summary['medium_quality']} medium, "
               f"{quality_summary['low_quality']} low quality extractions")
    
    return structured_results, quality_summary

def main():
    """Main execution with REALISTIC Azure AI quality reporting"""
    logger.info("Starting GTMF extraction process with REALISTIC quality assessment")
    
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
            
            # Save results with REALISTIC quality information
            output_path = 'gtmf/gtmf_example_azure.json'
            with open(output_path, 'w', encoding='utf-8') as outfile:
                json.dump(structured_results, outfile, indent=2)
            
            # Save REALISTIC quality summary
            quality_report_path = 'gtmf/quality_report_azure.json'
            with open(quality_report_path, 'w', encoding='utf-8') as outfile:
                json.dump(quality_summary, outfile, indent=2)
            
            logger.info(f"Extraction complete. Results saved to {output_path}")
            logger.info(f"REALISTIC quality report saved to {quality_report_path}")
            
            # Print REALISTIC summary
            print(f"\n=== GTMF Azure AI REALISTIC Quality Summary ===")
            print(f"Total processed: {quality_summary['total_processed']}")
            print(f"High quality (>0.7): {quality_summary['high_quality']}")
            print(f"Medium quality (0.5-0.7): {quality_summary['medium_quality']}")
            print(f"Low quality (<0.5): {quality_summary['low_quality']}")
            if quality_summary.get('average_scores'):
                print(f"Average completeness: {quality_summary['average_scores']['completeness']:.2f}")
                print(f"Average accuracy: {quality_summary['average_scores']['accuracy']:.2f}")
                print(f"Average medical validity: {quality_summary['average_scores']['medical_validity']:.2f}")
                print(f"Average safety: {quality_summary['average_scores']['safety']:.2f}")
            
    except Exception as e:
        logger.error(f"Error in main execution: {e}")

if __name__ == '__main__':
    main()