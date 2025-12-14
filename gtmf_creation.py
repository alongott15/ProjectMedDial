import json
import logging
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from Models.classes import GTMF
from Utils.utils import format_date, calculate_age
from Utils.bias_aware_prompts import GTMF_CREATION_PROMPT
from Utils.markdown_gtmf import save_gtmf_markdown
import re
import os
from typing import Dict, List, Tuple
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Light case filter configuration (expanded for more light cases)
LIGHT_CASE_INCLUDE_TERMS = [
    # Respiratory symptoms
    "cough", "sore throat", "throat pain", "runny nose", "nasal congestion",
    "upper respiratory", "cold symptoms", "flu-like", "sneezing", "stuffy nose",
    "post-nasal drip", "scratchy throat", "hoarse voice", "mild shortness of breath",
    # Head symptoms
    "headache", "mild dizziness", "sinus pressure", "sinus pain", "earache",
    "ear pain", "pressure in head", "tension headache", "migraine",
    # Fever and systemic
    "low-grade fever", "low grade fever", "mild fever", "chills", "malaise",
    "fatigue", "tiredness", "weakness", "body aches", "muscle aches",
    # GI (mild)
    "nausea", "upset stomach", "mild abdominal pain", "diarrhea", "constipation",
    "heartburn", "indigestion", "loss of appetite",
    # Musculoskeletal
    "back pain", "neck pain", "joint pain", "minor pain", "muscle soreness",
    "stiffness", "sprain", "strain",
    # Skin/minor issues
    "rash", "skin irritation", "itching", "minor wound", "bruise",
    # General
    "not feeling well", "under the weather", "viral illness", "viral infection",
    "common cold", "seasonal allergies", "allergy symptoms"
]

LIGHT_CASE_EXCLUDE_TERMS = [
    "icu", "intubated", "cardiac arrest", "shock", "sepsis", "septic",
    "mechanical ventilation", "multi organ failure", "multiorgan failure",
    "malignancy", "cancer", "metastatic", "critical", "life-threatening",
    "severe", "acute respiratory distress", "ards", "transplant",
    "dialysis", "cardiac surgery", "trauma", "hemorrhage", "stroke"
]


def is_light_common_case(note_text: str, chief_complaint: str = "") -> dict:
    """
    Determine if a case is a light, common medical case.

    Args:
        note_text: Clinical note text
        chief_complaint: Chief complaint if available

    Returns:
        Dict with 'passed' (bool) and 'reason' (str)
    """
    text_lower = note_text.lower()
    cc_lower = chief_complaint.lower() if chief_complaint else ""
    combined_text = text_lower + " " + cc_lower

    # Check for exclusion terms (severe cases)
    for term in LIGHT_CASE_EXCLUDE_TERMS:
        if term in combined_text:
            return {
                "passed": False,
                "reason": f"Contains severe/ICU indicator: '{term}'"
            }

    # Check for inclusion terms (light symptoms)
    matched_terms = []
    for term in LIGHT_CASE_INCLUDE_TERMS:
        if term in combined_text:
            matched_terms.append(term)

    if matched_terms:
        return {
            "passed": True,
            "reason": f"Contains light symptoms: {', '.join(matched_terms[:3])}"
        }
    else:
        return {
            "passed": False,
            "reason": "No light/common symptoms detected"
        }

# MINIMAL ADDITION: Robust JSON parsing functions (essential fix)
def aggressive_json_clean(text: str) -> str:
    """Aggressively clean text to extract valid JSON"""
    # Remove markdown code blocks
    text = re.sub(r'```[a-z]*\n?', '', text)
    text = re.sub(r'```', '', text)
    
    # Remove common prefixes
    prefixes = ['Here is the JSON:', 'JSON:', 'Response:', 'Output:', 'Result:']
    for prefix in prefixes:
        if text.strip().startswith(prefix):
            text = text.strip()[len(prefix):].strip()
    
    # Fix common JSON issues
    text = re.sub(r'\n+', ' ', text)  # Replace multiple newlines with space
    text = re.sub(r'\t+', ' ', text)  # Replace tabs with space
    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
    
    # Remove trailing commas
    text = re.sub(r',(\s*[}\]])', r'\1', text)
    
    return text.strip()

def safe_json_parse_object(json_str: str, field_name: str = "") -> dict:
    """Safely parse JSON object with fallback strategies"""
    if not json_str or json_str.strip() in ['', '{}']:
        return {}
    
    try:
        result = json.loads(json_str)
        if isinstance(result, dict):
            return result
        return {}
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse error for {field_name}: {e}")
        
        # Try to fix and re-parse
        try:
            cleaned = json_str.strip()
            
            # Ensure proper object formatting
            if not cleaned.startswith('{'):
                cleaned = '{' + cleaned
            if not cleaned.endswith('}'):
                cleaned = cleaned + '}'
            
            # Fix common issues
            cleaned = re.sub(r'(?<!\\)"(?=[^",\]\}]*")', '\\"', cleaned)
            cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)
            
            result = json.loads(cleaned)
            if isinstance(result, dict):
                return result
                    
        except Exception as fix_error:
            logger.warning(f"Failed to fix JSON for {field_name}: {fix_error}")
        
        # Return minimal valid structure if all parsing fails
        return {
            "Core_Fields": {
                "Symptoms": [],
                "Diagnoses": [],
                "Treatment_Options": []
            },
            "Context_Fields": {
                "Patient_Demographics": {
                    "Date_of_Birth": "not provided",
                    "Age": 0,
                    "Sex": "not provided",
                    "Religion": "not provided",
                    "Marital_Status": "not provided",
                    "Ethnicity": "not provided",
                    "Insurance": "not provided",
                    "Admission_Type": "not provided",
                    "Admission_Date": "not provided",
                    "Discharge_Date": "not provided"
                },
                "Medical_History": {"Past_Medical_History": "not provided"},
                "Allergies": [],
                "Current_Medications": [],
                "Discharge_Medications": []
            },
            "Additional_Context": {"Chief_Complaint": "not provided"}
        }

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

def extract_gtmf_chunked(medical_text: str, azure_client: AzureAIClient) -> GTMF:
    """
    Extract structured GTMF data with chunking
    """
    logger.info("Extracting GTMF from medical text with chunking")
    
    # Get GTMF schema
    schema_json = GTMF.model_json_schema()
    
    # Chunk the text if it's too long
    chunks = chunk_medical_text(medical_text, max_chunk_size=3000, overlap=200)
    logger.info(f"Processing {len(chunks)} chunks")
    
    # Use bias-aware prompt for GTMF extraction
    system_message = GTMF_CREATION_PROMPT + """

    CRITICAL: Output ONLY valid JSON - no explanations, no markdown, no code blocks.
    Always start your response directly with the opening brace { and end with closing brace }"""
    
    all_extractions = []
    
    # Process each chunk with ENHANCED JSON parsing
    for i, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {i+1}/{len(chunks)}")
        
        user_message = f"""
        Extract medical information from this clinical note chunk and format it according to the JSON schema below.
        
        IMPORTANT: Respond with ONLY the JSON object, no other text.

        JSON Schema:
        {json.dumps(schema_json, indent=2)}

        Medical Note Chunk:
        {chunk}

        JSON Output:
        """
        
        try:
            result = azure_client.chat_completion(system_message, user_message, temperature=0.0)
            logger.debug(f"Raw LLM response for chunk {i+1}: {result[:200]}...")
            
            # ENHANCED JSON PARSING: Clean and parse the response
            cleaned_result = aggressive_json_clean(result)
            
            # Enhanced JSON boundary detection
            json_start = -1
            json_end = -1
            brace_count = 0
            
            for idx, char in enumerate(cleaned_result):
                if char == '{':
                    if json_start == -1:
                        json_start = idx
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and json_start != -1:
                        json_end = idx + 1
                        break
            
            if json_start >= 0 and json_end > json_start:
                json_str = cleaned_result[json_start:json_end]
                data = safe_json_parse_object(json_str, f"chunk_{i+1}")
                
                if data and data != {}:
                    all_extractions.append(data)
                    logger.info(f"Successfully parsed JSON from chunk {i+1}")
                else:
                    logger.warning(f"Empty or invalid JSON from chunk {i+1}, skipping")
            else:
                logger.warning(f"Could not find valid JSON boundaries in chunk {i+1}")
                
        except Exception as e:
            logger.error(f"Error processing chunk {i+1}: {e}")
            continue
    
    if not all_extractions:
        logger.error("No valid extractions obtained from any chunks")
        # Create minimal valid extraction
        minimal_extraction = safe_json_parse_object("", "minimal_fallback")
        all_extractions = [minimal_extraction]
    
    # Merge extractions from all chunks
    merged_extraction = merge_gtmf_extractions(all_extractions)
    
    try:
        structured_output = GTMF(**merged_extraction)
        logger.info(f"GTMF extraction completed successfully")
        return structured_output

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

def process_notes(results, azure_client: AzureAIClient, batch_size: int = None):
    """
    Process fetched notes with quality scoring using Azure AI.

    Args:
        results: Database query results
        azure_client: Azure AI client for GTMF extraction
        batch_size: If specified, process notes in batches of this size

    Returns:
        Tuple of (structured_results, quality_summary)
    """
    logger.info("Processing fetched notes with Azure AI")
    structured_results = []
    quality_summary = {
        "total_processed": 0,
        "json_parse_failures": 0,
        # Light case filtering stats
        "light_case_passed": 0,
        "light_case_failed": 0
    }

    # Batch processing if batch_size specified
    if batch_size and batch_size > 0:
        total_batches = (len(results) + batch_size - 1) // batch_size
        logger.info(f"Processing {len(results)} notes in {total_batches} batches of size {batch_size}")
    else:
        logger.info(f"Processing {len(results)} notes without batching")

    for idx, row in enumerate(results):
        try:
            # Apply light case filter first
            light_case_result = is_light_common_case(row['text'])
            if not light_case_result['passed']:
                logger.info(f"Note {idx} filtered out: {light_case_result['reason']}")
                quality_summary["light_case_failed"] += 1
                continue
            else:
                logger.info(f"Note {idx} passed light case filter: {light_case_result['reason']}")
                quality_summary["light_case_passed"] += 1

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

            # Extract GTMF using Azure AI
            gtmf_instance = extract_gtmf_chunked(row['text'], azure_client)

            # Update quality summary
            quality_summary["total_processed"] += 1

            # Update GTMF with metadata and demographics
            gtmf_instance = gtmf_instance.model_copy(update={
                "row_id": row['row_id'],
                "subject_id": row['subject_id'],
                "hadm_id": row['hadm_id'],
                "Context_Fields": gtmf_instance.Context_Fields.model_copy(update={
                    "Patient_Demographics": gtmf_instance.Context_Fields.Patient_Demographics.model_copy(update=demographics)
                })
            })

            # Prepare output
            result = gtmf_instance.model_dump()

            # Enrich with structured data from MIMIC-III tables if available
            if 'structured_data' in row:
                structured = row['structured_data']

                # Add ICD diagnoses (structured diagnoses supplement LLM-extracted ones)
                if structured.get('diagnoses'):
                    result['structured_diagnoses'] = structured['diagnoses']

                # Add ICD procedures
                if structured.get('procedures'):
                    result['structured_procedures'] = structured['procedures']

                # Add prescriptions/medications
                if structured.get('prescriptions'):
                    result['structured_prescriptions'] = structured['prescriptions']

                # Add lab results for DoctorAgent to reference
                if structured.get('lab_results'):
                    result['lab_results'] = structured['lab_results']

            # Add light case filter result
            result["light_case_filter"] = light_case_result
            result["case_type"] = "LIGHT_COMMON_SYMPTOMS"

            structured_results.append(result)
            logger.info(f"Processed note {idx} successfully")
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed for note at index {idx}: {e}")
            quality_summary["json_parse_failures"] += 1
            quality_summary["total_processed"] += 1
        except Exception as e:
            logger.error(f"Error processing note at index {idx}: {e}")
            quality_summary["total_processed"] += 1

    # Log summary
    logger.info(f"Processing summary: {quality_summary['total_processed']} notes processed, "
               f"{len(structured_results)} GTMFs created")
    logger.info(f"Light case filter: {quality_summary['light_case_passed']} passed, "
               f"{quality_summary['light_case_failed']} filtered out")
    logger.info(f"JSON parse failures: {quality_summary['json_parse_failures']}")
    
    return structured_results, quality_summary

def main():
    """Main execution with Azure AI using CSV data only"""
    logger.info("Starting GTMF extraction process from CSV data")

    # Initialize Azure AI client
    try:
        azure_client = AzureAIClient()
        logger.info("Azure AI client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Azure AI client: {e}")
        return

    # CSV directory path - REQUIRED
    csv_dir = os.getenv("MIMIC_CSV_DIR")

    if not csv_dir:
        logger.error("MIMIC_CSV_DIR environment variable not set!")
        logger.info("Please set MIMIC_CSV_DIR in your .env file")
        logger.info("Example: MIMIC_CSV_DIR=/path/to/mimic-iii/csv")
        return

    if not os.path.exists(csv_dir):
        logger.error(f"CSV directory not found: {csv_dir}")
        logger.info("Please verify the path in MIMIC_CSV_DIR environment variable")
        return

    # Load from CSV
    try:
        from Utils.csv_data_loader import CSVDataLoader
        loader = CSVDataLoader(csv_dir)
        results = loader.fetch_notes_with_light_case_filter(
            category_filter="Discharge summary",
            limit=100
        )
        if not results:
            logger.warning("No light case notes found in CSV.")
            return
        logger.info(f"Loaded {len(results)} notes from CSV")
    except Exception as e:
        logger.error(f"Error loading CSV data: {e}")
        return

    try:
        # Process notes
        structured_results, summary = process_notes(results, azure_client, batch_size=50)

        # Save results as Markdown files
        output_dir = 'gtmf'
        os.makedirs(output_dir, exist_ok=True)

        logger.info(f"Saving {len(structured_results)} GTMFs as Markdown files...")
        for idx, gtmf in enumerate(structured_results):
            subject_id = gtmf.get('subject_id', f'unknown_{idx}')
            hadm_id = gtmf.get('hadm_id', idx)
            filename = f"gtmf_{subject_id}_{hadm_id}.md"
            output_path = os.path.join(output_dir, filename)
            save_gtmf_markdown(gtmf, output_path)

        # Save summary
        summary_path = 'gtmf/processing_summary.json'
        with open(summary_path, 'w', encoding='utf-8') as outfile:
            json.dump(summary, outfile, indent=2)

        logger.info(f"Extraction complete. {len(structured_results)} GTMFs saved to {output_dir}/ as Markdown files")
        logger.info(f"Summary saved to {summary_path}")

        # Print summary
        print(f"\n=== GTMF Processing Summary ===")
        print(f"Total processed: {summary['total_processed']}")
        print(f"GTMFs created: {len(structured_results)}")
        print(f"Light cases passed: {summary['light_case_passed']}")
        print(f"Light cases filtered: {summary['light_case_failed']}")
        print(f"JSON parse failures: {summary['json_parse_failures']}")

    except Exception as e:
        logger.error(f"Error in main execution: {e}")

if __name__ == '__main__':
    main()