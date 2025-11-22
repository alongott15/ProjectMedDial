"""Patient Agent - Simulates patient behavior in medical dialogue"""
import logging
from typing import List, Dict
from utils.llms_utils import LLMClient

logger = logging.getLogger(__name__)


class PatientAgent:
    """Simulates a patient with light/common symptoms"""

    def __init__(self, profile: Dict, llm_client: LLMClient):
        self.profile = profile
        self.llm_client = llm_client
        self.conversation_history = []
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Build system prompt for patient agent"""
        profile_content = self.profile.get("profile_content", {})
        core_fields = profile_content.get("Core_Fields", {})
        context_fields = profile_content.get("Context_Fields", {})
        additional_context = profile_content.get("Additional_Context", {})

        # Demographics
        demographics = context_fields.get("Patient_Demographics", {})
        age = demographics.get("Age", "unknown")
        sex = demographics.get("Sex", "unknown")

        # Chief complaint
        chief_complaint = additional_context.get("Chief_Complaint", "general illness")

        # Symptoms
        symptoms = core_fields.get("Symptoms", [])
        symptoms_list = [s.get("description", "") for s in symptoms if isinstance(s, dict)]
        symptoms_str = ", ".join(symptoms_list) if symptoms_list else "general discomfort"

        # Medical history
        medical_history = context_fields.get("Medical_History", {}).get("Past_Medical_History", "none reported")

        prompt = f"""You are a patient seeking medical help for a light/common illness.

Your Information:
- Age: {age}, Sex: {sex}
- Chief Complaint: {chief_complaint}
- Symptoms: {symptoms_str}
- Medical History: {medical_history}

Behavior Guidelines:
1. Start with your main concern, then reveal details gradually as the doctor asks
2. Use natural, everyday language
3. Show appropriate concern for your symptoms
4. Only mention symptoms from your profile above
5. Be honest and cooperative with the doctor
6. Keep responses brief and natural (2-4 sentences)

Respond as this patient would in a real medical consultation."""

        return prompt

    def respond(self, conversation_history: List[Dict]) -> str:
        """Generate patient response to conversation"""
        messages = [{"role": "system", "content": self.system_prompt}]

        # Add conversation history
        for turn in conversation_history:
            role = "assistant" if turn["role"] == "Patient" else "user"
            messages.append({"role": role, "content": turn["content"]})

        try:
            response = self.llm_client.chat_completion_messages(messages)
            return response
        except Exception as e:
            logger.error(f"Error generating patient response: {e}")
            return "I'm sorry, I'm having trouble expressing myself right now."

    def update_prompt(self, feedback: str):
        """Update system prompt with feedback for improvement"""
        improvement_note = f"\n\nFeedback for improvement: {feedback}"
        self.system_prompt += improvement_note
        logger.info("Patient agent prompt updated with feedback")
