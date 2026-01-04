import logging
from Utils.llms_utils import load_gpt_model, chat_generate
from Utils.bias_aware_prompts import BASE_SYSTEM_PROMPT
import random
from Utils.conversation_variety import (
    PatientPersonality, get_patient_hesitation, get_patient_response_starter,
    should_use_filler_words, PATIENT_WORRY_EXPRESSIONS
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PatientAgent:
    def __init__(self, profile: dict, llm=None):
        if llm:
            self.llm = llm
        else:
            logger.info("LLM not provided to PatientAgent, loading Azure AI model internally.")
            self.llm = load_gpt_model(temperature=0.6, max_tokens=300)  # Increased for personality variation

        self.profile = profile
        self.coach_feedback_to_incorporate = None
        self.mentioned_symptoms = set()
        self.emotional_state = self._determine_emotional_state()
        self.conversation_turn = 0
        # Track symptoms for gradual, natural disclosure
        self.symptoms_to_disclose = self._prepare_gradual_disclosure()
        
        demographics_str = self._get_demographics(profile)
        chief_complaint_str = self._get_chief_complaint(profile)
        medical_history_str = self._get_medical_history(profile)
        allergies_str = self._get_allergies(profile)
        current_medications_str = self._get_current_medications(profile)
        symptoms_str = self._get_symptoms(profile)
        lab_tests_str = self._get_lab_tests(profile)

        # Enhanced patient persona with personality traits
        self.patient_persona = self._create_patient_persona()
        self.personality_traits = self._determine_personality_traits()

        # Get demographic info for personality modeling
        demo = self.profile.get("Context_Fields", {}).get("Patient_Demographics", {})
        age = demo.get('Age', 50)
        sex = demo.get('Sex', 'Unknown')

        # Get personality-based communication traits
        self.personality_profile = PatientPersonality.get_personality_traits(age, sex)
        self.age_language = PatientPersonality.get_age_appropriate_language(age)

        # Create age-appropriate communication style description
        age_style_desc = self._get_age_communication_style(age)

        self.system_message = {
            "role": "system",
            "content": (
                f"{BASE_SYSTEM_PROMPT}\n\n"

                "**YOUR ROLE:**\n"
                f"You are {self.patient_persona} with a light, common medical issue seeking help.\n"
                f"Emotional state: {self.emotional_state}\n"
                f"Communication style: {age_style_desc}\n\n"

                "**YOUR PROFILE (STRICT - ONLY USE INFORMATION BELOW):**\n"
                f"- Demographics: {demographics_str}\n"
                f"- Chief Complaint: {chief_complaint_str}\n"
                f"- Symptoms you're experiencing: {symptoms_str}\n"
                f"- Medical History: {medical_history_str}\n"
                f"- Allergies: {allergies_str}\n"
                f"- Current Medications: {current_medications_str}\n"
                f"- Recent Lab Tests: {lab_tests_str}\n\n"

                "**CRITICAL GROUNDING RULES:**\n"
                "1. ONLY discuss symptoms listed in your profile above\n"
                "2. If doctor asks about symptoms NOT in your profile, say you haven't experienced them\n"
                "3. Do NOT invent new symptoms, test results, or medical history\n"
                "4. If you don't know a detail (exact duration, specific time), say you're not sure or don't remember\n"
                "5. This is a LIGHT, COMMON condition - don't describe severe/emergency symptoms\n\n"

                "**NATURAL CONVERSATION BEHAVIOR:**\n"
                "- **Turn 1-2**: Share only your main concern briefly, with some initial hesitation\n"
                "- **Turn 3-5**: When asked, reveal 1-2 additional symptoms gradually\n"
                "- **Turn 6+**: Feel more comfortable - less hesitation, more direct answers\n\n"

                "**COMMUNICATION STYLE - VARY YOUR RESPONSES:**\n"
                "- Use everyday language initially: 'my chest hurts', 'hard to breathe'\n"
                "- Mirror doctor's medical terms when they use them: if doctor says 'symptoms', start using 'symptoms'\n"
                "- **IMPORTANT**: Don't start every response with 'Um...' or 'Well...'\n"
                "  - Use hesitations ONLY when actually uncertain or uncomfortable (not every turn)\n"
                "  - When answering clear questions, respond more directly\n"
                "  - Vary between: direct answer, brief hesitation, no hesitation\n"
                "- Express uncertainty contextually: 'I think...', 'Maybe...', 'I'm not sure if...'\n"
                "- Don't ask 'Should I be worried?' repeatedly - vary your concerns\n"
                "- Keep responses brief and natural (1-3 sentences typically)\n"
                "- Let your personality come through based on your age and background\n"
            )
        }

    def _get_age_communication_style(self, age: int) -> str:
        """Get age-appropriate communication style description"""
        if age < 30:
            return "Direct and casual, may use modern expressions, asks questions freely"
        elif age < 60:
            return "Balanced and clear, practical communication, experienced with healthcare"
        else:
            return "Respectful and detailed, may have some recall hesitation, values doctor's guidance"

    def _prepare_gradual_disclosure(self) -> list:
        symptoms_list = self.profile.get("Core_Fields", {}).get("Symptoms", [])
        symptoms = []

        for sym in symptoms_list:
            if isinstance(sym, dict):
                desc = sym.get('description', '').strip()
                if desc:
                    symptoms.append(desc.lower())
            elif isinstance(sym, str) and sym.strip():
                symptoms.append(sym.strip().lower())

        priority_symptoms = []
        secondary_symptoms = []

        for symptom in symptoms:
            if any(term in symptom for term in ['pain', 'hurt', 'breath', 'chest']):
                priority_symptoms.append(symptom)
            else:
                secondary_symptoms.append(symptom)

        return priority_symptoms + secondary_symptoms

    def _create_patient_persona(self) -> str:
        demo = self.profile.get("Context_Fields", {}).get("Patient_Demographics", {})
        age = demo.get('Age', 0)
        sex = demo.get('Sex', 'person')

        if age < 30:
            age_desc = "young adult"
        elif age < 60:
            age_desc = "middle-aged person"
        else:
            age_desc = "older adult"

        return f"a {age_desc} {sex.lower()} patient"

    def _determine_personality_traits(self) -> str:
        demo = self.profile.get("Context_Fields", {}).get("Patient_Demographics", {})
        age = demo.get('Age', 0)

        if age < 30:
            base_traits = ["somewhat anxious about health", "asks direct questions"]
        elif age < 60:
            base_traits = ["experienced with healthcare", "practical communicator"]
        else:
            base_traits = ["respectful of medical authority", "detailed in descriptions"]

        return ", ".join(base_traits)

    def _determine_emotional_state(self) -> str:
        symptoms = self.profile.get("Core_Fields", {}).get("Symptoms", [])
        symptom_text = " ".join([str(s).lower() for s in symptoms])

        if any(indicator in symptom_text for indicator in ["chest pain", "breath", "severe"]):
            return "anxious and worried"
        elif any(indicator in symptom_text for indicator in ["pain", "hurt", "discomfort"]):
            return "uncomfortable and seeking relief"
        else:
            return "concerned but hopeful"

    def _get_demographics(self, profile: dict) -> str:
        demo = profile.get("Context_Fields", {}).get("Patient_Demographics", {})
        if not demo: return "Not specified in profile."
        return f"Age: {demo.get('Age', 'N/A')}, Sex: {demo.get('Sex', 'N/A')}"

    def _get_chief_complaint(self, profile: dict) -> str:
        return profile.get("Additional_Context", {}).get("Chief_Complaint", "Not specified in profile.")

    def _get_medical_history(self, profile: dict) -> str:
        history_data = profile.get("Context_Fields", {}).get("Medical_History", {})
        if isinstance(history_data, dict):
            return history_data.get("Past_Medical_History", "Not specified in profile.")
        return "Not specified in profile."

    def _get_allergies(self, profile: dict) -> str:
        allergies = profile.get("Context_Fields", {}).get("Allergies", [])
        return ", ".join(allergies) if allergies else "None known or not specified in profile."

    def _get_current_medications(self, profile: dict) -> str:
        """
        Get current medications from profile (GTMF-extracted).
        """
        meds = profile.get("Context_Fields", {}).get("Current_Medications", [])
        if not meds:
            return "Not specified in profile."

        med_names = []
        for med_item in meds:
            if isinstance(med_item, dict) and "name" in med_item:
                med_names.append(med_item["name"])
            elif isinstance(med_item, str):
                med_names.append(med_item)
        return ", ".join(med_names) if med_names else "Not specified in profile."

    def _get_lab_tests(self, profile: dict) -> str:
        return "No specific lab test information available in profile."

    def _get_symptoms(self, profile: dict) -> str:
        symptoms_list = profile.get("Core_Fields", {}).get("Symptoms", [])
        if not symptoms_list: return "No specific symptoms listed in profile to discuss."
        
        symptom_details = []
        for sym_item in symptoms_list:
            if isinstance(sym_item, dict):
                desc = sym_item.get('description')
                if not desc: continue
                symptom_details.append(desc)
            elif isinstance(sym_item, str):
                 symptom_details.append(sym_item)
        return "; ".join(symptom_details) if symptom_details else "No specific symptoms listed in profile to discuss."

    def _get_symptoms_for_turn(self) -> list:
        available_symptoms = [s for s in self.symptoms_to_disclose if s not in self.mentioned_symptoms]

        if self.conversation_turn <= 2:
            return available_symptoms[:1] if available_symptoms else []
        elif self.conversation_turn <= 5:
            return available_symptoms[:2] if available_symptoms else []
        else:
            return available_symptoms[:3] if available_symptoms else []

    def respond(self, conversation_history: list) -> str:
        self.conversation_turn += 1

        llm_messages = [self.system_message]
        for message in conversation_history:
            if message['role'].lower() == 'patient':
                llm_messages.append({'role': 'assistant', 'content': message['content']})
            elif message['role'].lower() == 'doctor':
                llm_messages.append({'role': 'user', 'content': message['content']})

        if self.coach_feedback_to_incorporate:
            llm_messages.append({'role': 'user', 'content': f"Feedback for improvement: {self.coach_feedback_to_incorporate}"})
            self.coach_feedback_to_incorporate = None

        # Determine what symptoms can be mentioned this turn (gradual disclosure)
        symptoms_to_mention = self._get_symptoms_for_turn()

        if conversation_history and conversation_history[-1]['role'].lower() == 'doctor':
            last_doctor_message = conversation_history[-1]['content']
            doctor_lower = last_doctor_message.lower()

            # Check if doctor is asking about symptoms
            asking_about_symptoms = any(phrase in doctor_lower for phrase in [
                "tell me", "describe", "any other", "what else", "symptoms", "how do you feel",
                "experiencing", "happening"
            ])

            # Turn-based guidance for natural conversation with personality
            if self.conversation_turn <= 2:
                turn_guidance = "Brief and slightly hesitant initially. Share only your main concern. Don't overuse 'Um...' or 'Well...'."
            elif self.conversation_turn <= 5:
                turn_guidance = "Share more details when asked. Hesitate only when genuinely uncertain, not every response."
            else:
                turn_guidance = "Feel comfortable - be more direct and less hesitant. Answer questions clearly."

            # Symptom disclosure hint
            symptom_hint = ""
            if symptoms_to_mention and asking_about_symptoms:
                symptom_hint = f"Can mention if relevant: {', '.join(symptoms_to_mention[:2])}"
                self.mentioned_symptoms.update(symptoms_to_mention[:2])

            # Determine response style based on personality and turn
            hesitation_guidance = ""
            if self.conversation_turn <= 2:
                hesitation_guidance = "You may use a brief hesitation if uncertain."
            elif self.conversation_turn > 5:
                hesitation_guidance = "You're more comfortable now - answer more directly, less hesitation."
            else:
                hesitation_guidance = "Use hesitation only when genuinely uncertain about the answer."

            user_prompt_for_next_turn = (
                f"Turn {self.conversation_turn}\n"
                f"Doctor said: \"{last_doctor_message}\"\n"
                f"Guidance: {turn_guidance}\n"
                f"{hesitation_guidance}\n"
                f"{symptom_hint}\n\n"

                "**Response guidelines:**\n"
                "1. Keep response brief and natural (1-3 sentences)\n"
                "2. VARY your response style - don't start every response with 'Um...' or 'Well...'\n"
                "   - If doctor asks a clear question, answer directly\n"
                "   - Use hesitation ONLY when uncertain or uncomfortable\n"
                "3. Use everyday language, but mirror doctor's medical terms when appropriate\n"
                "4. ONLY discuss symptoms from your profile\n"
                "5. If asked about symptoms you DON'T have, say you haven't experienced them\n"
                "6. Don't repeat 'Should I be worried?' every turn - vary your concerns\n\n"

                "Patient's response:"
            )
            llm_messages.append({"role": "user", "content": user_prompt_for_next_turn})
        else:
            # Opening response
            user_prompt_for_next_turn = (
                f"Turn {self.conversation_turn} - Starting consultation\n"
                "Share only your main concern briefly. Be somewhat hesitant initially.\n\n"
                "Patient's response:"
            )
            llm_messages.append({"role": "user", "content": user_prompt_for_next_turn})

        response_content = chat_generate(self.llm, llm_messages)

        logger.info(f"[Patient] Turn {self.conversation_turn}: {response_content[:80]}...")
        return response_content

    def update_prompt(self, additional_instructions: str):
        self.coach_feedback_to_incorporate = additional_instructions
        logger.info(f"[Patient] Coach feedback stored for next response.")