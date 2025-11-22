"""GTMF Creation Agent - Extracts structured GTMFs from EHR cases with batch processing"""
import json
import logging
import re
from pathlib import Path
from typing import List, Dict
from Models.classes import GTMF
from utils.llms_utils import LLMClient

logger = logging.getLogger(__name__)


class GTMFCreationAgent:
    """Creates Ground Truth Medical Forms from EHR cases with batch processing"""

    def __init__(self, llm_client: LLMClient, output_dir: str = "outputs/gtmf"):
        self.llm_client = llm_client
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def chunk_text(self, text: str, max_chunk_size: int = 3000, overlap: int = 200) -> List[str]:
        """Split text into overlapping chunks"""
        if len(text) <= max_chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + max_chunk_size

            if end < len(text):
                last_period = text.rfind('.', end - 200, end)
                last_newline = text.rfind('\n', end - 200, end)
                if last_period > start:
                    end = last_period + 1
                elif last_newline > start:
                    end = last_newline + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = max(start + max_chunk_size - overlap, end)
            if start >= len(text):
                break

        return chunks

    def clean_json_response(self, text: str) -> str:
        """Clean LLM response to extract valid JSON"""
        text = re.sub(r'```[a-z]*\n?', '', text)
        text = re.sub(r'```', '', text)

        prefixes = ['Here is the JSON:', 'JSON:', 'Response:', 'Output:', 'Result:']
        for prefix in prefixes:
            if text.strip().startswith(prefix):
                text = text.strip()[len(prefix):].strip()

        text = re.sub(r',(\s*[}\]])', r'\1', text)
        return text.strip()

    def extract_json_from_response(self, response: str) -> Dict:
        """Extract JSON from LLM response with fallback strategies"""
        cleaned = self.clean_json_response(response)

        # Find JSON boundaries
        json_start = -1
        json_end = -1
        brace_count = 0

        for idx, char in enumerate(cleaned):
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
            json_str = cleaned[json_start:json_end]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error: {e}")

        return {}

    def create_gtmf_from_chunk(self, chunk: str) -> Dict:
        """Extract GTMF data from a single text chunk"""
        schema_json = GTMF.model_json_schema()

        system_message = """You are a medical information extraction expert. Extract all relevant medical information from the clinical note and convert it to structured JSON format.

CRITICAL: Output ONLY valid JSON - no explanations, no markdown, no code blocks.

Instructions:
1. Extract ALL medical information present in the text
2. Create separate objects for each symptom, diagnosis, and treatment
3. Use 'not provided' for missing string fields or empty arrays for missing lists
4. Focus on light/common symptoms (cough, sore throat, fever, headache, etc.)
5. Your output must be valid JSON conforming to the schema

Always start with { and end with }"""

        user_message = f"""Extract medical information from this clinical note chunk and format according to the JSON schema.

IMPORTANT: Respond with ONLY the JSON object, no other text.

JSON Schema:
{json.dumps(schema_json, indent=2)}

Medical Note Chunk:
{chunk}

JSON Output:"""

        try:
            response = self.llm_client.chat_completion(system_message, user_message, temperature=0.0)
            return self.extract_json_from_response(response)
        except Exception as e:
            logger.error(f"Error extracting GTMF from chunk: {e}")
            return {}

    def merge_gtmf_extractions(self, extractions: List[Dict]) -> Dict:
        """Merge multiple GTMF extractions from chunks"""
        if not extractions:
            raise ValueError("No extractions to merge")

        if len(extractions) == 1:
            return extractions[0]

        merged = extractions[0].copy()

        # Track seen items to avoid duplicates
        seen_symptoms = set()
        seen_diagnoses = set()
        seen_treatments = set()

        merged_symptoms = []
        merged_diagnoses = []
        merged_treatments = []

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

        merged["Core_Fields"]["Symptoms"] = merged_symptoms
        merged["Core_Fields"]["Diagnoses"] = merged_diagnoses
        merged["Core_Fields"]["Treatment_Options"] = merged_treatments

        return merged

    def create_gtmf(self, ehr_case: Dict) -> GTMF:
        """Create GTMF from an EHR case"""
        text = ehr_case.get("text", "")
        if not text:
            raise ValueError("EHR case has no text")

        logger.info(f"Creating GTMF for case {ehr_case.get('hadm_id')}")

        # Chunk the text
        chunks = self.chunk_text(text)
        logger.info(f"Processing {len(chunks)} chunks")

        # Extract from each chunk
        extractions = []
        for i, chunk in enumerate(chunks):
            extraction = self.create_gtmf_from_chunk(chunk)
            if extraction:
                extractions.append(extraction)
                logger.debug(f"Chunk {i+1}/{len(chunks)} extracted successfully")

        if not extractions:
            raise ValueError("No valid extractions obtained")

        # Merge extractions
        merged = self.merge_gtmf_extractions(extractions)

        # Add demographics
        demographics = ehr_case.get("demographics", {})
        if "Context_Fields" not in merged:
            merged["Context_Fields"] = {}
        if "Patient_Demographics" not in merged["Context_Fields"]:
            merged["Context_Fields"]["Patient_Demographics"] = {}

        merged["Context_Fields"]["Patient_Demographics"].update({
            "Date_of_Birth": demographics.get("date_of_birth", "not provided"),
            "Age": demographics.get("age", 0),
            "Sex": demographics.get("sex", "not provided"),
            "Religion": demographics.get("religion", "not provided"),
            "Marital_Status": demographics.get("marital_status", "not provided"),
            "Ethnicity": demographics.get("ethnicity", "not provided"),
            "Insurance": demographics.get("insurance", "not provided"),
            "Admission_Type": demographics.get("admission_type", "not provided"),
            "Admission_Date": demographics.get("admission_date", "not provided"),
            "Discharge_Date": demographics.get("discharge_date", "not provided")
        })

        # Add chief complaint
        if "Additional_Context" not in merged:
            merged["Additional_Context"] = {}
        merged["Additional_Context"]["Chief_Complaint"] = ehr_case.get("chief_complaint", "not provided")

        # Add metadata
        merged["row_id"] = ehr_case.get("row_id", 0)
        merged["subject_id"] = ehr_case.get("subject_id", 0)
        merged["hadm_id"] = ehr_case.get("hadm_id", 0)
        merged["case_type"] = "LIGHT_COMMON_SYMPTOMS"

        # Create GTMF instance
        gtmf = GTMF(**merged)
        logger.info(f"GTMF created for case {ehr_case.get('hadm_id')}")

        return gtmf

    def create_batch(self, ehr_cases: List[Dict]) -> List[GTMF]:
        """Create GTMFs for a batch of EHR cases"""
        gtmfs = []

        for ehr_case in ehr_cases:
            try:
                gtmf = self.create_gtmf(ehr_case)
                gtmfs.append(gtmf)
            except Exception as e:
                logger.error(f"Error creating GTMF for case {ehr_case.get('hadm_id')}: {e}")

        logger.info(f"Created {len(gtmfs)} GTMFs from batch of {len(ehr_cases)} cases")
        return gtmfs

    def save_gtmf(self, gtmf: GTMF) -> str:
        """Save a single GTMF to JSON"""
        filename = f"gtmf_{gtmf.subject_id}_{gtmf.hadm_id}.json"
        filepath = self.output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(gtmf.model_dump(), f, indent=2)

        return str(filepath)

    def save_batch(self, gtmfs: List[GTMF]) -> List[str]:
        """Save multiple GTMFs to JSON"""
        filepaths = []
        for gtmf in gtmfs:
            try:
                filepath = self.save_gtmf(gtmf)
                filepaths.append(filepath)
            except Exception as e:
                logger.error(f"Error saving GTMF {gtmf.hadm_id}: {e}")

        logger.info(f"Saved {len(filepaths)} GTMFs to {self.output_dir}")
        return filepaths
