import json
import logging
from typing import List
from Utils.llms_utils import load_gpt_model, chat_generate
from Models.labels import RemediLabelDetail # Ensure this path is correct

logger = logging.getLogger(__name__)

PATIENT_INTENTS = ["Informing", "Inquiring", "Chitchat", "QA", "Others"]
DOCTOR_ACTIONS = ["Recommendation", "Diagnosis", "Informing", "Inquiring", "Chitchat", "QA", "Others"]
SLOTS = [
    "Temperature", "Dose", "Degree", "Frequency", "Effect", "Medical-place", 
    "Time", "Department", "Disease-history", "Medicine-category", "Check_item", 
    "Pathogeny", "Side-effect", "Range-body", "Precaution", "Other", "Disease", 
    "Treatment", "Medicine", "Symptom"
]

class RemediNLUAnnotatorAgent:
    def __init__(self, llm=None):
        if llm:
            self.llm = llm
        else:
            self.llm = load_gpt_model(model_name='gpt-4.1', temperature=0.1, max_tokens=1024)
        
        # Alternative approach if main prompt still fails
        self.simple_system_prompt = (
            "Medical dialogue annotation using ReMeDi framework. "
            f"Patient intents: {', '.join(PATIENT_INTENTS)}. "
            f"Doctor actions: {', '.join(DOCTOR_ACTIONS)}. "
            f"Slots: {', '.join(SLOTS)}."
        )
        
        self.base_system_prompt = (
            "As a medical conversation analyst, identify key information in doctor-patient dialogues. "
            "Label each utterance according to the ReMeDi annotation schema.\n\n"
            "Patient utterances - use label_type 'intent':\n"
            f"{', '.join(PATIENT_INTENTS)}\n\n"
            "Doctor utterances - use label_type 'action':\n"
            f"{', '.join(DOCTOR_ACTIONS)}\n\n"
            "Medical slots available:\n"
            f"{', '.join(SLOTS)}\n\n"
            "Output format (JSON array):\n"
            "[{\"label_type\": \"intent\", \"type_name\": \"Informing\", \"slot\": \"Symptom\", \"value\": \"headache\"}]\n\n"
            "Empty array for non-medical content: []"
        )

    def _construct_user_prompt(self, utterance_text: str, role: str) -> str:
        return (
            f"Speaker: {role}\n"
            f"Text: \"{utterance_text}\"\n\n"
            "JSON annotations:"
        )

    def annotate_utterance(self, utterance_text: str, role: str) -> List[RemediLabelDetail]:
        if not utterance_text.strip():
            return []

        user_prompt = self._construct_user_prompt(utterance_text, role)
        
        # Try the main prompt first, fallback to simpler version if needed
        messages = [
            {"role": "system", "content": self.base_system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            raw_output = chat_generate(self.llm, messages)
        except Exception as e:
            if "content_filter" in str(e) or "jailbreak" in str(e):
                logger.warning(f"Content filter triggered, trying simpler prompt: {e}")
                # Fallback to simpler system prompt
                messages = [
                    {"role": "system", "content": self.simple_system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                raw_output = chat_generate(self.llm, messages)
            else:
                raise e

        logger.debug(f"Raw LLM output for NLU annotation: {raw_output}")

        extracted_labels = []
        try:
            json_output = json.loads(raw_output)
            if isinstance(json_output, list):
                for label_dict in json_output:
                    try:
                        # value_main and value_subordinate are removed from RemediLabelDetail
                        extracted_labels.append(RemediLabelDetail(**label_dict))
                    except Exception as e: 
                        logger.warning(f"Could not validate ReMeDi label item: {label_dict}. Error: {e}")
            else:
                logger.warning(f"LLM output for ReMeDi annotation was not a list: {json_output}")
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from LLM for ReMeDi annotation. Output: {raw_output}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during ReMeDi annotation parsing: {e}. Output: {raw_output}")
            
        return extracted_labels