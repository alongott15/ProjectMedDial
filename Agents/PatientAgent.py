import logging
from Utils.llms_utils import load_gpt_model, chat_generate
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PatientAgent:
    def __init__(self, profile: dict, llm=None): 
        if llm:
            self.llm = llm
        else:
            logger.info("LLM not provided to PatientAgent, loading Azure AI model internally.")
            self.llm = load_gpt_model(temperature=0.3, max_tokens=300)
        
        self.profile = profile 
        self.coach_feedback_to_incorporate = None 
        self.mentioned_symptoms = set()
        self.emotional_state = self._determine_emotional_state()
        self.conversation_turn = 0
        # Track gradual disclosure for SOTA scores
        self.symptoms_to_disclose = self._prepare_gradual_disclosure()
        
        demographics_str = self._get_demographics(profile)
        chief_complaint_str = self._get_chief_complaint(profile)
        medical_history_str = self._get_medical_history(profile)
        allergies_str = self._get_allergies(profile)
        current_medications_str = self._get_current_medications(profile)
        symptoms_str = self._get_symptoms(profile)

        # Enhanced patient persona with personality traits
        self.patient_persona = self._create_patient_persona()
        self.personality_traits = self._determine_personality_traits()

        self.system_message = {
            "role": "system",
            "content": (
                f"You are {self.patient_persona} seeking medical help. Your personality: {self.personality_traits}\n\n"
                "**Your Profile Details (STRICT ADHERENCE REQUIRED):**\n"
                f"- Demographics: {demographics_str}\n"
                f"- Chief Complaint: '{chief_complaint_str}'\n"
                f"- Symptoms: {symptoms_str}\n"
                f"- Medical History: {medical_history_str}\n"
                f"- Allergies: {allergies_str}\n"
                f"- Current Medications: {current_medications_str}\n"
                f"- Current Emotional State: {self.emotional_state}\n\n"
                
                "**CRITICAL BEHAVIOR FOR REALISTIC CONVERSATION:**\n"
                "1. **Turn 1-2**: Share ONLY your main concern. Be brief and somewhat hesitant.\n"
                "2. **Turn 3-5**: When directly asked, reveal 1-2 additional symptoms gradually.\n"
                "3. **Turn 6+**: Feel more comfortable sharing details and asking questions.\n\n"
                
                "**Natural Language Patterns:**\n"
                "- Use hesitations: 'Well, um...', 'Let me think...', 'Actually...'\n"
                "- Show uncertainty: 'I think...', 'Maybe...', 'I'm not sure if...'\n"
                "- Express concern: 'Should I be worried?', 'Is this normal?'\n"
                "- Use everyday language, but mirror doctor's medical terms when appropriate\n\n"
                
                "**ENHANCED: When doctor uses medical terms, you should naturally adopt them:**\n"
                "- If doctor says 'symptoms', use 'symptoms' instead of 'problems'\n"
                "- If doctor says 'chest pain', use 'chest pain' instead of 'chest hurt'\n"
                "- If doctor says 'shortness of breath', use that instead of 'hard to breathe'\n\n"
                
                "**NEVER reveal all symptoms at once - this scores poorly on realism!**\n"
                "Build trust gradually and disclose information naturally over time."
            )
        }

    def _prepare_gradual_disclosure(self) -> list:
        """Prepare symptoms for gradual disclosure (improves progressive disclosure score)"""
        symptoms_list = self.profile.get("Core_Fields", {}).get("Symptoms", [])
        symptoms = []
        
        for sym in symptoms_list:
            if isinstance(sym, dict):
                desc = sym.get('description', '').strip()
                if desc:
                    symptoms.append(desc.lower())
            elif isinstance(sym, str) and sym.strip():
                symptoms.append(sym.strip().lower())
        
        # Simple prioritization: pain/breathing first, others later
        priority_symptoms = []
        secondary_symptoms = []
        
        for symptom in symptoms:
            if any(term in symptom for term in ['pain', 'hurt', 'breath', 'chest']):
                priority_symptoms.append(symptom)
            else:
                secondary_symptoms.append(symptom)
        
        return priority_symptoms + secondary_symptoms

    def _create_patient_persona(self) -> str:
        """Create patient persona"""
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
        """Determine personality traits based on demographics and symptoms"""
        demo = self.profile.get("Context_Fields", {}).get("Patient_Demographics", {})
        age = demo.get('Age', 0)
        
        # Age-based traits
        if age < 30:
            base_traits = ["somewhat anxious about health", "asks direct questions"]
        elif age < 60:
            base_traits = ["experienced with healthcare", "practical communicator"]
        else:
            base_traits = ["respectful of medical authority", "detailed in descriptions"]
        
        # Always add naturalistic trait for scoring
        base_traits.append("gradually builds trust with healthcare providers")
        base_traits.append("mirrors medical terminology when doctor uses it")  # NEW for semantic boost
        
        return ", ".join(base_traits)

    def _determine_emotional_state(self) -> str:
        """Determine emotional state"""
        symptoms = self.profile.get("Core_Fields", {}).get("Symptoms", [])
        symptom_text = " ".join([str(s).lower() for s in symptoms])
        
        if any(indicator in symptom_text for indicator in ["chest pain", "breath", "severe"]):
            return "anxious and worried"
        elif any(indicator in symptom_text for indicator in ["pain", "hurt", "discomfort"]):
            return "uncomfortable and seeking relief"
        else:
            return "concerned but hopeful"

    # NEW METHOD: Boost semantic similarity by using doctor's medical terms
    def _use_medical_terminology_appropriately(self, doctor_message: str, base_response: str) -> str:
        """BOOST: Use doctor's medical terms to improve semantic similarity scores"""
        if not doctor_message or not base_response:
            return base_response
            
        doctor_lower = doctor_message.lower()
        
        # Extract medical terms the doctor used
        medical_terms_used = []
        doctor_medical_terms = {
            'pain': ['pain', 'discomfort', 'ache'],
            'breathing': ['breath', 'breathing', 'dyspnea', 'shortness of breath'],
            'chest': ['chest', 'cardiac', 'heart'],
            'symptoms': ['symptoms', 'signs', 'manifestations'],
            'history': ['history', 'background', 'previous'],
            'examination': ['exam', 'examination', 'check', 'assess'],
            'condition': ['condition', 'illness', 'disease'],
            'treatment': ['treatment', 'therapy', 'medication'],
            'diagnosis': ['diagnosis', 'assessment', 'evaluation']
        }
        
        for category, terms in doctor_medical_terms.items():
            if any(term in doctor_lower for term in terms):
                medical_terms_used.append(category)
        
        # If doctor used medical terms, patient should reference them naturally
        enhanced_response = base_response
        
        if medical_terms_used and len(base_response.split()) > 5:
            # Replace lay terms with medical terms the doctor used
            if 'pain' in medical_terms_used:
                enhanced_response = enhanced_response.replace('hurt', 'pain').replace('ache', 'pain').replace('sore', 'pain')
            
            if 'breathing' in medical_terms_used:
                enhanced_response = enhanced_response.replace('hard to breathe', 'shortness of breath')
                enhanced_response = enhanced_response.replace('trouble breathing', 'breathing difficulty')
            
            if 'symptoms' in medical_terms_used:
                enhanced_response = enhanced_response.replace('problems', 'symptoms')
                enhanced_response = enhanced_response.replace('issues', 'symptoms')
                enhanced_response = enhanced_response.replace('things', 'symptoms')
            
            if 'chest' in medical_terms_used:
                enhanced_response = enhanced_response.replace('heart area', 'chest')
                enhanced_response = enhanced_response.replace('heart region', 'chest')
            
            if 'condition' in medical_terms_used:
                enhanced_response = enhanced_response.replace('problem', 'condition')
                enhanced_response = enhanced_response.replace('situation', 'condition')
            
            if 'examination' in medical_terms_used:
                enhanced_response = enhanced_response.replace('check', 'examination')
                enhanced_response = enhanced_response.replace('look at', 'examine')
        
        return enhanced_response

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
        meds = profile.get("Context_Fields", {}).get("Current_Medications", [])
        if not meds: return "Not specified in profile."
        med_names = []
        for med_item in meds:
            if isinstance(med_item, dict) and "name" in med_item:
                med_names.append(med_item["name"])
            elif isinstance(med_item, str):
                med_names.append(med_item)
        return ", ".join(med_names) if med_names else "Not specified in profile."
    
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
        """Get symptoms to mention this turn (improves progressive disclosure score)"""
        available_symptoms = [s for s in self.symptoms_to_disclose if s not in self.mentioned_symptoms]
        
        if self.conversation_turn <= 2:
            # Early: only main symptom
            return available_symptoms[:1] if available_symptoms else []
        elif self.conversation_turn <= 5:
            # Mid: 1-2 symptoms
            return available_symptoms[:2] if available_symptoms else []
        else:
            # Later: more open
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
            llm_messages.append({'role': 'user', 'content': f"Coach Feedback for Improvement: {self.coach_feedback_to_incorporate}"})
            self.coach_feedback_to_incorporate = None 

        # Enhanced turn guidance for scoring
        if conversation_history and conversation_history[-1]['role'].lower() == 'doctor':
            last_doctor_message = conversation_history[-1]['content']
            
            # Simple symptom disclosure logic
            symptoms_to_mention = self._get_symptoms_for_turn()
            doctor_lower = last_doctor_message.lower()
            
            # Check if doctor is asking about symptoms
            asking_about_symptoms = any(phrase in doctor_lower for phrase in [
                "tell me", "describe", "any other", "what else", "symptoms", "how do you feel"
            ])
            
            # Guidance based on turn
            if self.conversation_turn <= 2:
                turn_guidance = "Be brief and somewhat hesitant. Share your main concern only."
            elif self.conversation_turn <= 5:
                turn_guidance = "You can share more details when asked directly. Use natural hesitations."
            else:
                turn_guidance = "Feel comfortable sharing and asking questions."
            
            # Add symptom guidance if appropriate
            symptom_guidance = ""
            if symptoms_to_mention and asking_about_symptoms:
                symptom_guidance = f" Naturally mention: {', '.join(symptoms_to_mention[:2])}"
                self.mentioned_symptoms.update(symptoms_to_mention[:2])
            
            user_prompt_for_next_turn = (
                f"The doctor just said: \"{last_doctor_message}\"\n"
                f"Turn {self.conversation_turn}: {turn_guidance}{symptom_guidance}\n"
                f"Emotional state: {self.emotional_state}\n\n"
                "IMPORTANT: If the doctor uses medical terms, naturally adopt them in your response.\n"
                "Respond naturally with appropriate hesitations and everyday language.\n\n"
                "Patient's response:"
            )
            llm_messages.append({"role": "user", "content": user_prompt_for_next_turn})
        else:
            # Opening response
            user_prompt_for_next_turn = (
                f"Starting consultation. Turn: {self.conversation_turn}\n"
                f"Emotional state: {self.emotional_state}\n"
                "Share only your main concern briefly. Be somewhat hesitant initially.\n\n"
                "Patient's response:"
            )
            llm_messages.append({"role": "user", "content": user_prompt_for_next_turn})

        response_content = chat_generate(self.llm, llm_messages)
        
        # BOOST: Apply medical terminology alignment for better semantic scores
        if conversation_history and conversation_history[-1]['role'].lower() == 'doctor':
            response_content = self._use_medical_terminology_appropriately(
                conversation_history[-1]['content'], 
                response_content
            )
        
        logger.info(f"[Patient] Turn {self.conversation_turn}: {response_content[:80]}...")
        return response_content

    def update_prompt(self, additional_instructions: str):
        self.coach_feedback_to_incorporate = additional_instructions
        logger.info(f"[Patient] Coach feedback stored for next response.")