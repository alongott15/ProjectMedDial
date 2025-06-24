# utils/gtmf_extractor.py
import json
import logging
from typing import List, Optional
from pydantic import ValidationError
from Models.classes import Symptom, Diagnosis, TreatmentOption, MedicalHistory, Medication, AdditionalContext
from Utils.llms_utils import chat_generate

logger = logging.getLogger(__name__)

def _parse_llm_json_list(output: str, model: type) -> List:
    """Parse a JSON list from LLM output into a list of Pydantic model instances."""
    items: List = []
    if not output or output.startswith("[ERROR"):
        logger.warning(f"No output or error from LLM: {output}")
        return items
    try:
        json_start = output.find('[')
        json_end = output.rfind(']')
        if json_start != -1 and json_end != -1:
            json_str = output[json_start:json_end+1].strip()
            raw_list = json.loads(json_str)
            if isinstance(raw_list, list):
                for item in raw_list:
                    try:
                        items.append(model(**item))  # validate via Pydantic model
                    except (ValidationError, TypeError) as e:
                        logger.warning(f"Skipping invalid item {item}: {e}")
            else:
                logger.warning("Output JSON is not a list")
        else:
            logger.warning("JSON list boundaries not found in output")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decoding failed for {model.__name__}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error parsing list for {model.__name__}: {e}", exc_info=True)
    return items

def _parse_llm_json_object(output: str, model: type) -> Optional[object]:
    """Parse a JSON object from LLM output into a Pydantic model instance."""
    if not output or output.startswith("[ERROR"):
        logger.warning(f"No output or error from LLM: {output}")
        return None
    try:
        json_start = output.find('{')
        json_end = output.rfind('}')
        if json_start != -1 and json_end != -1:
            json_str = output[json_start:json_end+1].strip()
            return model.model_validate_json(json_str)  # Pydantic parsing
        else:
            logger.warning("JSON object boundaries not found in output")
    except (json.JSONDecodeError, ValidationError) as e:
        logger.error(f"Parsing failed for {model.__name__}: {e}")
    return None

# Field-specific extraction using role-specific prompting:
def extract_symptoms(note_text: str, llm) -> List[Symptom]:
    """Use LLM to extract symptoms (with attributes) from a clinical note."""
    prompt = (
        "You are a medical information extractor. Read the following clinical note and list all patient symptoms. "
        "For each symptom, provide its description, onset, duration, and severity (use 'not provided' if unspecified). "
        "Format the output as a JSON list of objects: "
        "[{\"description\": \"...\", \"onset\": \"...\", \"duration\": \"...\", \"severity\": \"...\"}]"
    )
    messages = [{"role": "user", "content": f"{prompt}\nNote:\n```{note_text}```"}]
    raw = chat_generate(llm, messages)
    symptoms = _parse_llm_json_list(raw, Symptom)
    logger.info(f"Extracted {len(symptoms)} symptoms")
    return symptoms

def extract_diagnoses(note_text: str, llm) -> List[Diagnosis]:
    """Use LLM to extract diagnoses from a clinical note."""
    prompt = (
        "Extract all diagnoses from the following clinical note. "
        "Format as JSON list of {\"primary\": \"diagnosis name\", \"notes\": \"additional notes\"}. "
        "Use \"not provided\" if notes are missing."
    )
    messages = [{"role": "user", "content": f"{prompt}\nNote:\n```{note_text}```"}]
    raw = chat_generate(llm, messages)
    diagnoses = _parse_llm_json_list(raw, Diagnosis)
    logger.info(f"Extracted {len(diagnoses)} diagnoses")
    return diagnoses

def extract_treatments(note_text: str, llm) -> List[TreatmentOption]:
    """Use LLM to extract treatments (procedures and medications) from a note."""
    med_schema = json.dumps(Medication.model_json_schema(), indent=2)  # for guidance
    prompt = (
        "Extract all treatments or procedures from the note, including associated medications. "
        "Format as JSON list of objects: "
        "{\"procedure\": \"...\", \"details\": \"...\", \"medications\": [{\"name\": \"...\", \"purpose\": \"...\", \"dosage\": \"...\", \"frequency\": \"...\"}, ...]} . "
        f"Adhere to this medication schema: {med_schema}. Use 'not provided' where applicable."
    )
    messages = [{"role": "user", "content": f"{prompt}\nNote:\n```{note_text}```"}]
    raw = chat_generate(llm, messages)
    treatments = _parse_llm_json_list(raw, TreatmentOption)
    logger.info(f"Extracted {len(treatments)} treatment options")
    return treatments

def extract_history(note_text: str, llm) -> MedicalHistory:
    """Use LLM to extract a summarized medical history from the note."""
    prompt = (
        "Extract the patient's past medical history from the note. "
        "Output as JSON object: {\"Past_Medical_History\": \"...\"}, or 'not provided' if absent."
    )
    messages = [{"role": "user", "content": f"{prompt}\nNote:\n```{note_text}```"}]
    raw = chat_generate(llm, messages)
    history = _parse_llm_json_object(raw, MedicalHistory)
    if not history:
        history = MedicalHistory(Past_Medical_History="not provided")
    return history

def extract_allergies(note_text: str, llm) -> List[str]:
    """Use LLM to extract any patient allergies mentioned."""
    prompt = (
        "List all patient allergies mentioned in the note as a JSON list of strings. "
        "If none or 'no known allergies' mentioned, return an empty JSON list []."
    )
    messages = [{"role": "user", "content": f"{prompt}\nNote:\n```{note_text}```"}]
    raw = chat_generate(llm, messages)
    allergies: List[str] = []
    if raw and raw.strip().startswith('['):
        # Attempt to parse list directly
        try:
            allergies = json.loads(raw.strip())
            allergies = [str(item) for item in allergies if item]  # ensure strings
        except json.JSONDecodeError:
            logger.warning("Failed to parse allergies list from LLM output")
    else:
        logger.warning("No allergies output or wrong format")
    return allergies