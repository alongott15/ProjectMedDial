import json
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from Models.classes import GTMF
from Utils.utils import get_db_uri, format_date, build_symptom_conditions, calculate_age
import re
import os
from typing import Dict, List, Tuple
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class GTMFQualityScore:
    """Quality assessment for GTMF extraction"""
    completeness_score: float  # 0-1, how much of the note was captured
    accuracy_score: float      # 0-1, how accurate the extractions are
    consistency_score: float   # 0-1, internal consistency of extracted data
    confidence_score: float    # 0-1, model confidence in extractions
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
    """Assesses the quality of GTMF extractions using Azure AI"""
    
    def __init__(self, azure_client: AzureAIClient):
        self.azure_client = azure_client
    
    def assess_gtmf_quality(self, medical_text: str, gtmf_instance: GTMF) -> GTMFQualityScore:
        """Comprehensive quality assessment of GTMF extraction"""
        
        # Convert GTMF to dict for easier analysis
        gtmf_dict = gtmf_instance.model_dump()
        
        # Individual field assessments
        field_scores = {}
        issues = []
        recommendations = []
        
        # 1. Assess Symptoms
        symptoms_score, symptoms_issues = self._assess_symptoms(medical_text, gtmf_dict.get("Core_Fields", {}).get("Symptoms", []))
        field_scores["symptoms"] = symptoms_score
        issues.extend(symptoms_issues)
        
        # 2. Assess Diagnoses
        diagnoses_score, diagnoses_issues = self._assess_diagnoses(medical_text, gtmf_dict.get("Core_Fields", {}).get("Diagnoses", []))
        field_scores["diagnoses"] = diagnoses_score
        issues.extend(diagnoses_issues)
        
        # 3. Assess Treatments
        treatments_score, treatments_issues = self._assess_treatments(medical_text, gtmf_dict.get("Core_Fields", {}).get("Treatment_Options", []))
        field_scores["treatments"] = treatments_score
        issues.extend(treatments_issues)
        
        # 4. Assess Demographics consistency
        demographics_score, demographics_issues = self._assess_demographics(gtmf_dict.get("Context_Fields", {}).get("Patient_Demographics", {}))
        field_scores["demographics"] = demographics_score
        issues.extend(demographics_issues)
        
        # 5. Overall completeness check
        completeness_score = self._assess_completeness(medical_text, gtmf_dict)
        
        # 6. Consistency check
        consistency_score = self._assess_consistency(gtmf_dict)
        
        # 7. Azure AI-based accuracy assessment
        accuracy_score, confidence_score = self._azure_accuracy_assessment(medical_text, gtmf_dict)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(field_scores, issues)
        
        return GTMFQualityScore(
            completeness_score=completeness_score,
            accuracy_score=accuracy_score,
            consistency_score=consistency_score,
            confidence_score=confidence_score,
            field_scores=field_scores,
            issues=issues,
            recommendations=recommendations
        )
    
    def _assess_symptoms(self, text: str, symptoms: List[Dict]) -> Tuple[float, List[str]]:
        """Assess symptom extraction quality"""
        issues = []
        
        if not symptoms:
            # Check if text actually contains symptoms
            symptom_indicators = ["pain", "ache", "discomfort", "nausea", "vomiting", "fatigue", 
                                "fever", "cough", "shortness of breath", "dizzy", "headache"]
            text_lower = text.lower()
            if any(indicator in text_lower for indicator in symptom_indicators):
                issues.append("Symptoms present in text but none extracted")
                return 0.2, issues
            else:
                return 1.0, issues  # No symptoms to extract
        
        # Check for quality issues in extracted symptoms
        valid_symptoms = 0
        for symptom in symptoms:
            desc = symptom.get("description", "").strip()
            if not desc or desc == "not provided":
                issues.append("Empty or placeholder symptom description found")
                continue
            
            # Check if symptom appears in original text
            if desc.lower() not in text.lower():
                # Try partial matching
                words = desc.lower().split()
                if not any(word in text.lower() for word in words if len(word) > 3):
                    issues.append(f"Symptom '{desc}' not clearly found in original text")
                    continue
            
            valid_symptoms += 1
        
        score = valid_symptoms / len(symptoms) if symptoms else 1.0
        return score, issues
    
    def _assess_diagnoses(self, text: str, diagnoses: List[Dict]) -> Tuple[float, List[str]]:
        """Assess diagnosis extraction quality"""
        issues = []
        
        if not diagnoses:
            # Check if text contains diagnostic information
            diagnostic_indicators = ["diagnosis", "diagnosed", "condition", "disease", "syndrome"]
            if any(indicator in text.lower() for indicator in diagnostic_indicators):
                issues.append("Diagnostic information present but no diagnoses extracted")
                return 0.3, issues
            return 1.0, issues
        
        valid_diagnoses = 0
        for diagnosis in diagnoses:
            primary = diagnosis.get("primary", "").strip()
            if not primary or primary == "not provided":
                issues.append("Empty or placeholder diagnosis found")
                continue
            
            # Simple validation - check if diagnosis terms appear in text
            if primary.lower() not in text.lower():
                words = primary.lower().split()
                if not any(word in text.lower() for word in words if len(word) > 3):
                    issues.append(f"Diagnosis '{primary}' not clearly supported by text")
                    continue
            
            valid_diagnoses += 1
        
        score = valid_diagnoses / len(diagnoses) if diagnoses else 1.0
        return score, issues
    
    def _assess_treatments(self, text: str, treatments: List[Dict]) -> Tuple[float, List[str]]:
        """Assess treatment extraction quality"""
        issues = []
        
        if not treatments:
            treatment_indicators = ["treatment", "therapy", "medication", "surgery", "procedure"]
            if any(indicator in text.lower() for indicator in treatment_indicators):
                issues.append("Treatment information present but none extracted")
                return 0.3, issues
            return 1.0, issues
        
        valid_treatments = 0
        for treatment in treatments:
            procedure = treatment.get("procedure", "").strip()
            if not procedure or procedure == "not provided":
                issues.append("Empty or placeholder treatment found")
                continue
            
            if procedure.lower() not in text.lower():
                words = procedure.lower().split()
                if not any(word in text.lower() for word in words if len(word) > 3):
                    issues.append(f"Treatment '{procedure}' not clearly found in text")
                    continue
            
            valid_treatments += 1
        
        score = valid_treatments / len(treatments) if treatments else 1.0
        return score, issues
    
    def _assess_demographics(self, demographics: Dict) -> Tuple[float, List[str]]:
        """Assess demographic data consistency"""
        issues = []
        
        # Check for age consistency
        age = demographics.get("Age", 0)
        dob = demographics.get("Date_of_Birth", "")
        admission_date = demographics.get("Admission_Date", "")
        
        if age > 0 and dob != "not provided" and admission_date != "not provided":
            try:
                # Recalculate age to verify
                calculated_age = calculate_age(dob, admission_date)
                if abs(calculated_age - age) > 1:  # Allow 1 year tolerance
                    issues.append(f"Age inconsistency: stated {age}, calculated {calculated_age}")
            except:
                issues.append("Could not verify age calculation")
        
        # Check for missing critical demographics
        required_fields = ["Age", "Sex"]
        missing_fields = [field for field in required_fields 
                         if demographics.get(field, "not provided") == "not provided"]
        
        if missing_fields:
            issues.append(f"Missing required demographic fields: {', '.join(missing_fields)}")
        
        # Score based on completeness and consistency
        total_fields = len(demographics)
        filled_fields = sum(1 for v in demographics.values() 
                           if v != "not provided" and str(v).strip())
        
        completeness_ratio = filled_fields / total_fields if total_fields > 0 else 1.0
        consistency_penalty = len(issues) * 0.2
        
        score = max(0.0, completeness_ratio - consistency_penalty)
        return score, issues
    
    def _assess_completeness(self, text: str, gtmf_dict: Dict) -> float:
        """Assess overall completeness of extraction"""
        text_length = len(text.split())
        
        # Count extracted content
        core_fields = gtmf_dict.get("Core_Fields", {})
        context_fields = gtmf_dict.get("Context_Fields", {})
        
        symptom_count = len([s for s in core_fields.get("Symptoms", []) 
                           if s.get("description", "").strip() and s.get("description") != "not provided"])
        diagnosis_count = len([d for d in core_fields.get("Diagnoses", []) 
                             if d.get("primary", "").strip() and d.get("primary") != "not provided"])
        treatment_count = len([t for t in core_fields.get("Treatment_Options", []) 
                             if t.get("procedure", "").strip() and t.get("procedure") != "not provided"])
        
        # Expected content based on text length
        expected_symptoms = min(10, max(1, text_length // 200))  # Rough heuristic
        expected_diagnoses = min(5, max(1, text_length // 400))
        expected_treatments = min(5, max(1, text_length // 300))
        
        symptom_completeness = min(1.0, symptom_count / expected_symptoms)
        diagnosis_completeness = min(1.0, diagnosis_count / expected_diagnoses)
        treatment_completeness = min(1.0, treatment_count / expected_treatments)
        
        overall_completeness = (symptom_completeness + diagnosis_completeness + treatment_completeness) / 3
        return overall_completeness
    
    def _assess_consistency(self, gtmf_dict: Dict) -> float:
        """Check internal consistency of GTMF data"""
        consistency_score = 1.0
        
        # Check if symptoms align with diagnoses
        symptoms = gtmf_dict.get("Core_Fields", {}).get("Symptoms", [])
        diagnoses = gtmf_dict.get("Core_Fields", {}).get("Diagnoses", [])
        
        # Simple keyword matching for consistency
        symptom_keywords = set()
        for symptom in symptoms:
            desc = symptom.get("description", "").lower()
            symptom_keywords.update(desc.split())
        
        diagnosis_keywords = set()
        for diagnosis in diagnoses:
            primary = diagnosis.get("primary", "").lower()
            diagnosis_keywords.update(primary.split())
        
        # Check for some overlap (not perfect, but basic consistency)
        if symptom_keywords and diagnosis_keywords:
            overlap = len(symptom_keywords.intersection(diagnosis_keywords))
            if overlap == 0:
                consistency_score -= 0.2  # Penalty for no keyword overlap
        
        return max(0.0, consistency_score)
    
    def _azure_accuracy_assessment(self, text: str, gtmf_dict: Dict) -> Tuple[float, float]:
        """Use Azure AI to assess accuracy and provide confidence score"""
        
        system_message = """You are a medical information extraction quality assessor. Your task is to evaluate how accurately medical information has been extracted from clinical text."""
        
        user_message = f"""
        Assess the accuracy of this medical information extraction:
        
        Original Text (first 500 chars): {text[:500]}...
        
        Extracted Information:
        - Symptoms: {[s.get('description') for s in gtmf_dict.get('Core_Fields', {}).get('Symptoms', [])]}
        - Diagnoses: {[d.get('primary') for d in gtmf_dict.get('Core_Fields', {}).get('Diagnoses', [])]}
        - Treatments: {[t.get('procedure') for t in gtmf_dict.get('Core_Fields', {}).get('Treatment_Options', [])]}
        
        Rate the accuracy (0.0-1.0) and confidence (0.0-1.0) of these extractions.
        Respond with just two numbers separated by a space: accuracy_score confidence_score
        Example: 0.85 0.90
        """
        
        try:
            response = self.azure_client.chat_completion(system_message, user_message, temperature=0.1)
            
            # Parse scores
            numbers = re.findall(r'0\.\d+|1\.0', response)
            if len(numbers) >= 2:
                accuracy = float(numbers[0])
                confidence = float(numbers[1])
                return accuracy, confidence
            
        except Exception as e:
            logger.warning(f"Azure AI accuracy assessment failed: {e}")
        
        # Default scores if Azure AI assessment fails
        return 0.7, 0.6
    
    def _generate_recommendations(self, field_scores: Dict[str, float], issues: List[str]) -> List[str]:
        """Generate improvement recommendations based on scores and issues"""
        recommendations = []
        
        # Field-specific recommendations
        if field_scores.get("symptoms", 1.0) < 0.7:
            recommendations.append("Improve symptom extraction: use more specific medical terminology matching")
        
        if field_scores.get("diagnoses", 1.0) < 0.7:
            recommendations.append("Enhance diagnosis extraction: look for more diagnostic indicators in text")
        
        if field_scores.get("treatments", 1.0) < 0.7:
            recommendations.append("Better treatment identification: include medications and procedures")
        
        if field_scores.get("demographics", 1.0) < 0.8:
            recommendations.append("Improve demographic data validation and consistency checks")
        
        # Issue-based recommendations
        if any("not clearly found" in issue for issue in issues):
            recommendations.append("Enhance text-to-extraction matching validation")
        
        if any("Empty or placeholder" in issue for issue in issues):
            recommendations.append("Improve extraction completeness - avoid placeholder values")
        
        return recommendations

def extract_gtmf_chunked(medical_text: str, azure_client: AzureAIClient) -> Tuple[GTMF, GTMFQualityScore]:
    """
    Extract structured GTMF data with chunking and quality assessment
    """
    logger.info("Extracting GTMF from medical text with chunking and quality assessment")
    
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
        
        # Quality assessment
        assessor = GTMFQualityAssessor(azure_client)
        quality_score = assessor.assess_gtmf_quality(medical_text, structured_output)
        
        logger.info(f"GTMF extraction completed with quality scores: "
                   f"Completeness={quality_score.completeness_score:.2f}, "
                   f"Accuracy={quality_score.accuracy_score:.2f}, "
                   f"Consistency={quality_score.consistency_score:.2f}")
        
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
    """Process fetched notes with quality scoring using Azure AI"""
    logger.info("Processing fetched notes with Azure AI quality assessment")
    structured_results = []
    quality_summary = {
        "total_processed": 0,
        "high_quality": 0,  # >0.8 overall score
        "medium_quality": 0,  # 0.6-0.8 overall score
        "low_quality": 0,   # <0.6 overall score
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

            # Extract GTMF with quality assessment using Azure AI
            gtmf_instance, quality_score = extract_gtmf_chunked(row['text'], azure_client)

            # Update quality summary
            quality_summary["total_processed"] += 1
            overall_score = (quality_score.completeness_score + 
                           quality_score.accuracy_score + 
                           quality_score.consistency_score) / 3
            
            if overall_score > 0.8:
                quality_summary["high_quality"] += 1
            elif overall_score > 0.6:
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
            
            # Include quality scores in output
            result_with_quality = gtmf_instance.model_dump()
            result_with_quality["quality_assessment"] = {
                "completeness_score": quality_score.completeness_score,
                "accuracy_score": quality_score.accuracy_score,
                "consistency_score": quality_score.consistency_score,
                "confidence_score": quality_score.confidence_score,
                "overall_score": overall_score,
                "field_scores": quality_score.field_scores,
                "issues": quality_score.issues,
                "recommendations": quality_score.recommendations
            }
            
            structured_results.append(result_with_quality)
            logger.info(f"Processed note {idx} with overall quality score: {overall_score:.2f}")
            
        except Exception as e:
            logger.error(f"Error processing note at index {idx}: {e}")
            quality_summary["total_processed"] += 1
            quality_summary["low_quality"] += 1
    
    # Calculate average scores
    if structured_results:
        avg_completeness = sum(r["quality_assessment"]["completeness_score"] for r in structured_results) / len(structured_results)
        avg_accuracy = sum(r["quality_assessment"]["accuracy_score"] for r in structured_results) / len(structured_results)
        avg_consistency = sum(r["quality_assessment"]["consistency_score"] for r in structured_results) / len(structured_results)
        
        quality_summary["average_scores"] = {
            "completeness": avg_completeness,
            "accuracy": avg_accuracy,
            "consistency": avg_consistency
        }
    
    # Log quality summary
    logger.info(f"Quality Summary: {quality_summary['high_quality']} high, "
               f"{quality_summary['medium_quality']} medium, "
               f"{quality_summary['low_quality']} low quality extractions")
    
    return structured_results, quality_summary

def main():
    """Main execution with Azure AI and quality reporting"""
    logger.info("Starting GTMF extraction process with Azure AI quality assessment")
    
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
            
            # Save results with quality information
            output_path = 'gtmf/gtmf_example_azure.json'
            with open(output_path, 'w', encoding='utf-8') as outfile:
                json.dump(structured_results, outfile, indent=2)
            
            # Save quality summary
            quality_report_path = 'gtmf/quality_report_azure.json'
            with open(quality_report_path, 'w', encoding='utf-8') as outfile:
                json.dump(quality_summary, outfile, indent=2)
            
            logger.info(f"Extraction complete. Results saved to {output_path}")
            logger.info(f"Quality report saved to {quality_report_path}")
            
            # Print summary
            print(f"\n=== GTMF Azure AI Quality Summary ===")
            print(f"Total processed: {quality_summary['total_processed']}")
            print(f"High quality (>0.8): {quality_summary['high_quality']}")
            print(f"Medium quality (0.6-0.8): {quality_summary['medium_quality']}")
            print(f"Low quality (<0.6): {quality_summary['low_quality']}")
            if quality_summary.get('average_scores'):
                print(f"Average completeness: {quality_summary['average_scores']['completeness']:.2f}")
                print(f"Average accuracy: {quality_summary['average_scores']['accuracy']:.2f}")
                print(f"Average consistency: {quality_summary['average_scores']['consistency']:.2f}")
            
    except Exception as e:
        logger.error(f"Error in main execution: {e}")

if __name__ == '__main__':
    main()