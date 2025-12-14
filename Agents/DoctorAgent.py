import logging
from Utils.llms_utils import load_gpt_model, chat_generate
from Utils.bias_aware_prompts import BASE_SYSTEM_PROMPT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DoctorAgent:
    def __init__(self, patient_profile: dict = None):
        self.llm = load_gpt_model(temperature=0.3, max_tokens=250)
        self.patient_profile = patient_profile
        self.coach_feedback_to_incorporate = None
        self.conversation_phase = "opening"
        self.discussed_symptoms = set()
        self.conversation_turn = 0
        self.last_patient_emotion = "neutral"

        # Extract demographics and profile information
        demographics_info = "Not specified"
        available_data_summary = []

        if patient_profile:
            # Demographics
            demo = patient_profile.get("Context_Fields", {}).get("Patient_Demographics", {})
            if demo:
                demographics_info = (
                    f"Age: {demo.get('Age', 'Not provided')}, "
                    f"Sex: {demo.get('Sex', 'Not provided')}"
                )

            # Check what data is available
            if patient_profile.get("Core_Fields", {}).get("Symptoms"):
                available_data_summary.append("symptoms reported in profile")
            if patient_profile.get("Context_Fields", {}).get("Medical_History"):
                available_data_summary.append("medical history")
            if patient_profile.get("Context_Fields", {}).get("Allergies"):
                available_data_summary.append("allergy information")

        # Extract key symptoms for guidance
        self.key_symptoms = []
        if patient_profile:
            symptoms = patient_profile.get("Core_Fields", {}).get("Symptoms", [])
            for symptom in symptoms:
                if isinstance(symptom, dict):
                    desc = symptom.get("description", "").strip()
                    if desc:
                        self.key_symptoms.append(desc.lower())

        data_available = ", ".join(available_data_summary) if available_data_summary else "limited patient data"

        self.system_message = {
            "role": "system",
            "content": (
                f"{BASE_SYSTEM_PROMPT}\n\n"

                "**YOUR ROLE:**\n"
                f"You are a primary care physician conducting a consultation for a patient with a light, common medical issue.\n"
                f"Patient demographics: {demographics_info}\n"
                f"Available patient data: {data_available}\n\n"

                "**CONSULTATION APPROACH FOR LIGHT CASES:**\n"
                "1. Start with a warm greeting and open-ended question (e.g., 'How have you been feeling lately?')\n"
                "2. Listen to patient's chief complaint and explore symptoms systematically\n"
                "3. Ask focused follow-up questions based on what they share\n"
                "4. Show empathy and acknowledge patient concerns naturally\n"
                "5. Keep questions appropriate for a light, common condition (not severe/ICU-level)\n"
                "6. When ready, provide assessment and recommendations based on conversation\n\n"

                "**COMMUNICATION GUIDELINES:**\n"
                "- Keep responses concise (1-3 sentences)\n"
                "- Ask ONE clear question per turn\n"
                "- Use professional but accessible medical language\n"
                "- Build on what patient shares: 'You mentioned X, can you tell me more about...'\n"
                "- Reference earlier parts of conversation when relevant\n"
                "- Show empathy when patient expresses concern or discomfort\n\n"

                "**CRITICAL GROUNDING RULES:**\n"
                "- Base your questions and assessment ONLY on what the patient tells you in the conversation\n"
                "- Do not assume or invent symptoms, test results, or history not mentioned\n"
                "- If you're unsure about something, ask the patient directly\n"
                "- Do not escalate a light case to severe diagnoses without strong evidence from conversation\n"
                "- Stay focused on light, common conditions (cough, sore throat, headache, mild fever, etc.)\n"
            )
        }


    def _detect_patient_emotion(self, patient_message: str) -> str:
        """Detect patient emotion for empathetic responses"""
        message_lower = patient_message.lower()

        if any(word in message_lower for word in ['worried', 'scared', 'afraid', 'concerned', 'anxious']):
            return "anxious"
        elif any(word in message_lower for word in ['frustrated', 'annoyed', 'tired of']):
            return "frustrated"
        elif any(word in message_lower for word in ['hurts', 'painful', 'terrible', 'awful']):
            return "in_pain"
        elif any(word in message_lower for word in ['confused', 'don\'t understand', 'unclear']):
            return "confused"
        else:
            return "neutral"

    def _update_conversation_phase(self, turn_count: int, conversation_history: list):
        """Update conversation phase based on turn count"""
        if turn_count <= 3:
            self.conversation_phase = "opening"
        elif turn_count <= 8:
            self.conversation_phase = "exploration"
        elif turn_count <= 11:
            self.conversation_phase = "synthesis"
        else:
            self.conversation_phase = "conclusion"

    def _track_clinical_findings(self, conversation_history: list):
        """Track what clinical information we've gathered"""
        if not conversation_history:
            return
        
        # Track symptoms mentioned
        recent_patient_responses = [
            msg['content'].lower() for msg in conversation_history[-4:] 
            if msg.get('role', '').lower() == 'patient'
        ]
        
        for response in recent_patient_responses:
            for symptom in self.key_symptoms:
                if symptom.lower() in response and symptom not in self.discussed_symptoms:
                    self.discussed_symptoms.add(symptom)
                    logger.info(f"[Doctor] Noted symptom discussed: {symptom}")

    def respond(self, conversation_history: list) -> str:
        """Generate doctor's response in conversation."""
        self.conversation_turn += 1

        llm_messages = [self.system_message]

        for message in conversation_history:
            if message['role'].lower() == 'doctor':
                llm_messages.append({'role': 'assistant', 'content': message['content']})
            elif message['role'].lower() == 'patient':
                llm_messages.append({'role': 'user', 'content': message['content']})

        if self.coach_feedback_to_incorporate:
            llm_messages.append({'role': 'user', 'content': f"Feedback for improvement: {self.coach_feedback_to_incorporate}"})
            self.coach_feedback_to_incorporate = None

        # Update conversation tracking
        self._update_conversation_phase(self.conversation_turn, conversation_history)
        self._track_clinical_findings(conversation_history)

        # Detect patient emotion for empathetic responses
        if conversation_history and conversation_history[-1].get('role', '').lower() == 'patient':
            last_patient_message = conversation_history[-1]['content']
            self.last_patient_emotion = self._detect_patient_emotion(last_patient_message)

        # Phase-specific guidance for natural conversation flow
        if self.conversation_phase == "opening":
            phase_guidance = "Greet patient warmly and ask open-ended question about their chief concern."
        elif self.conversation_phase == "exploration":
            phase_guidance = "Ask focused follow-up questions based on what patient shared."
        elif self.conversation_phase == "synthesis":
            phase_guidance = "Begin summarizing findings and forming clinical assessment."
        else:
            phase_guidance = "Provide assessment and recommendations based on conversation."

        # Track symptom exploration
        remaining_symptoms = [s for s in self.key_symptoms if s not in self.discussed_symptoms]
        symptom_hint = ""
        if remaining_symptoms and self.conversation_turn <= 10:
            symptom_hint = f"Consider exploring: {', '.join(remaining_symptoms[:2])}"

        # Simple, grounded prompt focusing on natural conversation
        user_prompt_for_next_turn = (
            f"**Turn {self.conversation_turn} - {self.conversation_phase.title()} Phase**\n"
            f"Guidance: {phase_guidance}\n"
            f"{symptom_hint}\n\n"

            "**Response guidelines:**\n"
            "1. Keep response concise (1-3 sentences)\n"
            "2. Ask ONE clear, focused question\n"
            "3. Show empathy if patient expressed concern or discomfort\n"
            "4. Build on what patient has shared in conversation\n"
            "5. Use clear, professional medical language\n"
            "6. Stay focused on light, common conditions\n\n"

            "Doctor's response:"
        )

        llm_messages.append({"role": "user", "content": user_prompt_for_next_turn})

        response_content = chat_generate(self.llm, llm_messages)

        logger.info(f"[Doctor] Turn {self.conversation_turn} ({self.conversation_phase}): {response_content[:80]}...")
        return response_content
    
    def update_prompt(self, additional_instructions: str):
        self.coach_feedback_to_incorporate = additional_instructions
        logger.info("[Doctor] Coach feedback stored for next response.")