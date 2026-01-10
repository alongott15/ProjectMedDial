import logging
import random
from Utils.llms_utils import load_gpt_model, chat_generate
from Utils.bias_aware_prompts import BASE_SYSTEM_PROMPT
from Utils.conversation_variety import (
    get_doctor_acknowledgment, get_doctor_empathy, get_doctor_transition,
    get_doctor_reflection_start, should_doctor_summarize,
    should_doctor_explain_reasoning, get_symptom_follow_up_question,
    DOCTOR_CLINICAL_REASONING, DOCTOR_EDUCATIONAL_PHRASES
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DoctorAgent:
    def __init__(self, patient_profile: dict = None):
        self.llm = load_gpt_model(temperature=0.5, max_tokens=300)  # Increased for more natural variation
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
                "2. Listen to patient's chief complaint and explore key symptoms with focused follow-up questions\n"
                "3. PRIORITIZE the most important questions - quality over quantity\n"
                "4. After 6-8 exchanges, if you have enough information, provide assessment and conclude\n"
                "5. Show empathy naturally and contextually (not every turn)\n"
                "6. Provide education and clinical reasoning - explain WHY you're asking certain questions\n"
                "7. Occasionally summarize what you've heard to show active listening\n"
                "8. Keep questions appropriate for a light, common condition (not severe/ICU-level)\n\n"

                "**COMMUNICATION GUIDELINES - NATURAL CONVERSATION:**\n"
                "- Vary your response style - don't start every response with 'Thank you' or 'I understand'\n"
                "- Sometimes acknowledge briefly ('I see', 'Okay'), sometimes just continue directly\n"
                "- Ask follow-up questions to explore symptoms in depth (severity, duration, triggers, alleviating factors)\n"
                "- Build on what patient shares naturally\n"
                "- Reference earlier parts of conversation when relevant\n"
                "- Use transitional phrases: 'Let me ask about...', 'Tell me more about...'\n"
                "- Occasionally explain your clinical thinking: 'Based on what you're describing...'\n"
                "- Provide brief education when appropriate: 'What often happens with this is...'\n\n"

                "**PROVIDE CLINICAL VALUE:**\n"
                "- Explain likely mechanisms or causes in simple terms when appropriate\n"
                "- Educate about warning signs to watch for\n"
                "- Offer reassurance when findings suggest common, benign issues\n"
                "- Provide practical self-care advice beyond just 'see your doctor'\n"
                "- Help patient understand connections between symptoms\n\n"

                "**AVOID REPETITION:**\n"
                "- Don't ask about the same symptom multiple times unless seeking clarification\n"
                "- Vary your phrasing and approach\n"
                "- Don't repeat the same symptoms back to the patient every turn\n"
                "- Progress the conversation forward\n\n"

                "**CRITICAL GROUNDING RULES:**\n"
                "- Base your questions and assessment ONLY on what the patient tells you in the conversation\n"
                "- Do not assume or invent symptoms, test results, or history not mentioned\n"
                "- If you're unsure about something, ask the patient directly\n"
                "- Do not escalate a light case to severe diagnoses without strong evidence from conversation\n"
                "- Stay focused on light, common conditions (cough, sore throat, headache, mild fever, etc.)\n"
            )
        }


    def _detect_patient_emotion(self, patient_message: str) -> str:
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
        if turn_count <= 3:
            self.conversation_phase = "opening"
        elif turn_count <= 8:
            self.conversation_phase = "exploration"
        elif turn_count <= 11:
            self.conversation_phase = "synthesis"
        else:
            self.conversation_phase = "conclusion"

    def _track_clinical_findings(self, conversation_history: list):
        if not conversation_history:
            return

        recent_patient_responses = [
            msg['content'].lower() for msg in conversation_history[-4:]
            if msg.get('role', '').lower() == 'patient'
        ]

        for response in recent_patient_responses:
            for symptom in self.key_symptoms:
                if symptom.lower() in response and symptom not in self.discussed_symptoms:
                    self.discussed_symptoms.add(symptom)

    def respond(self, conversation_history: list) -> str:
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
            phase_guidance = "Explore symptoms in depth with FOCUSED follow-up questions (severity, duration, triggers). Prioritize the most relevant questions."
            # Suggest clinical depth
            if should_doctor_summarize(self.conversation_turn, len(self.discussed_symptoms)):
                phase_guidance += " Consider briefly summarizing what you've learned so far."
            # Encourage conclusion if sufficient coverage
            if self.conversation_turn >= 6 and len(self.discussed_symptoms) >= 2:
                phase_guidance += " You may have enough information to provide an assessment - consider moving to conclusion if key symptoms are covered."
        elif self.conversation_phase == "synthesis":
            phase_guidance = "Summarize findings and form clinical assessment. Explain your reasoning. PREPARE TO CONCLUDE."
            if should_doctor_explain_reasoning(self.conversation_turn, self.conversation_phase):
                phase_guidance += " Share your clinical thinking with the patient in simple terms."
        else:
            phase_guidance = "Provide clear assessment, practical advice, and warning signs. CONCLUDE the consultation naturally."

        # Track symptom exploration with follow-up suggestions
        remaining_symptoms = [s for s in self.key_symptoms if s not in self.discussed_symptoms]
        symptom_hint = ""
        if remaining_symptoms and self.conversation_turn <= 10:
            # Provide specific follow-up question suggestion
            first_symptom = remaining_symptoms[0]
            follow_up = get_symptom_follow_up_question(first_symptom)
            symptom_hint = f"Unexplored symptoms: {', '.join(remaining_symptoms[:2])}. Example follow-up: '{follow_up}'"
        elif self.discussed_symptoms and self.conversation_turn <= 8:
            # Suggest deeper exploration of discussed symptoms
            symptom_hint = "Ask deeper follow-up questions about symptoms already mentioned (severity, duration, what makes it better/worse)."

        # Enhanced prompt with variety and clinical depth guidance
        user_prompt_for_next_turn = (
            f"**Turn {self.conversation_turn} - {self.conversation_phase.title()} Phase**\n"
            f"Guidance: {phase_guidance}\n"
            f"{symptom_hint}\n\n"

            "**Response guidelines:**\n"
            "1. VARY your opening - don't always start with 'Thank you' or 'I understand'\n"
            "   - Options: 'I see', 'Okay', 'Let me ask about...', or just continue directly\n"
            "2. Ask focused questions OR provide clinical insight/education (depending on phase)\n"
            "3. Show empathy contextually (not every turn) when patient expresses distress\n"
            "4. Build on previous answers - explore symptoms in depth\n"
            "5. If in synthesis/conclusion phase, explain your clinical reasoning in simple terms\n"
            "6. Avoid repeating the same symptoms back to patient\n"
            "7. Provide practical value - education, reassurance, or actionable advice\n\n"

            "Doctor's response:"
        )

        llm_messages.append({"role": "user", "content": user_prompt_for_next_turn})

        response_content = chat_generate(self.llm, llm_messages)

        logger.info(f"[Doctor] Turn {self.conversation_turn} ({self.conversation_phase}): {response_content[:80]}...")
        return response_content
    
    def update_prompt(self, additional_instructions: str):
        self.coach_feedback_to_incorporate = additional_instructions
        logger.info("[Doctor] Coach feedback stored for next response.")