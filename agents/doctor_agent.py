"""Doctor Agent - Simulates physician behavior in medical dialogue"""
import logging
from typing import List, Dict
from utils.llms_utils import LLMClient

logger = logging.getLogger(__name__)


class DoctorAgent:
    """Simulates a physician conducting a medical consultation"""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.conversation_history = []
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Build system prompt for doctor agent"""
        prompt = """You are an experienced, empathetic physician conducting a medical consultation for a patient with light/common symptoms (e.g., cough, sore throat, fever, headache).

Your Approach:
1. Start with an open question to understand the patient's main concern
2. Ask focused questions about symptoms (onset, duration, severity)
3. Inquire about relevant medical history and medications
4. Show empathy and validate the patient's concerns
5. Provide a clear assessment and practical advice
6. Keep the conversation natural and patient-centered

Communication Style:
- Use clear, professional language
- Be empathetic and reassuring
- Ask one or two questions at a time
- Build on what the patient shares
- Keep responses brief (2-4 sentences typically)
- Conclude with clear guidance and advice

Remember: These are light/common cases requiring primary care advice, not emergency or complex conditions."""

        return prompt

    def respond(self, conversation_history: List[Dict]) -> str:
        """Generate doctor response to conversation"""
        messages = [{"role": "system", "content": self.system_prompt}]

        # Add conversation history
        for turn in conversation_history:
            role = "assistant" if turn["role"] == "Doctor" else "user"
            messages.append({"role": role, "content": turn["content"]})

        try:
            response = self.llm_client.chat_completion_messages(messages)
            return response
        except Exception as e:
            logger.error(f"Error generating doctor response: {e}")
            return "I understand. Let me ask you another question to help with the assessment."

    def update_prompt(self, feedback: str):
        """Update system prompt with feedback for improvement"""
        improvement_note = f"\n\nFeedback for improvement: {feedback}"
        self.system_prompt += improvement_note
        logger.info("Doctor agent prompt updated with feedback")
