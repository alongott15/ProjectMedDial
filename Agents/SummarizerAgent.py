import logging
import re
import json
from typing import Dict, List, Tuple, Set
from Utils.llms_utils import load_gpt_model, chat_generate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedSymptomExtractor:
    """Advanced symptom extraction engine with medical domain expertise"""
    
    def __init__(self):
        # Comprehensive medical terminology mappings
        self.symptom_vocabulary = {
            # Pain-related terms
            'pain': {
                'variations': ['pain', 'ache', 'aching', 'hurt', 'hurting', 'sore', 'soreness', 
                              'discomfort', 'uncomfortable', 'tender', 'tenderness'],
                'descriptors': ['sharp', 'dull', 'throbbing', 'burning', 'stabbing', 'cramping', 
                               'radiating', 'shooting', 'gnawing', 'crushing'],
                'severity': ['mild', 'moderate', 'severe', 'excruciating', 'unbearable', 'slight', 
                            'terrible', 'awful', 'bad', 'intense']
            },
            
            # Body systems and locations
            'body_locations': {
                'head': ['head', 'headache', 'skull', 'temple', 'forehead'],
                'chest': ['chest', 'heart', 'cardiac', 'sternum', 'ribs'],
                'abdomen': ['abdomen', 'abdominal', 'stomach', 'belly', 'gut', 'tummy'],
                'back': ['back', 'spine', 'lumbar', 'lower back', 'upper back'],
                'extremities': ['arm', 'leg', 'hand', 'foot', 'knee', 'ankle', 'wrist', 'shoulder']
            },
            
            # Common symptoms
            'systemic_symptoms': {
                'respiratory': ['shortness of breath', 'dyspnea', 'breathless', 'breathing difficulty', 
                               'breath', 'wheezing', 'cough', 'coughing'],
                'neurological': ['dizziness', 'dizzy', 'lightheaded', 'vertigo', 'headache', 
                                'numbness', 'tingling', 'weakness', 'fatigue'],
                'gastrointestinal': ['nausea', 'nauseous', 'vomiting', 'throwing up', 'sick to stomach',
                                    'bloating', 'constipation', 'diarrhea'],
                'constitutional': ['fever', 'chills', 'sweating', 'night sweats', 'weight loss',
                                  'appetite loss', 'tired', 'fatigue', 'weakness']
            }
        }
        
        # Common symptom patterns and their medical equivalents
        self.symptom_patterns = {
            r'chest pain|chest discomfort|heart pain': 'chest pain',
            r'short of breath|shortness of breath|breathing difficulty|trouble breathing|hard to breathe|breathless': 'shortness of breath',
            r'head pain|headache|head ache|skull pain': 'headache',
            r'stomach pain|belly pain|abdominal pain|gut pain|tummy ache': 'abdominal pain',
            r'back pain|spine pain|lower back pain|upper back pain': 'back pain',
            r'feeling sick|nauseous|queasy|sick to stomach': 'nausea',
            r'throwing up|vomiting|puking': 'vomiting',
            r'dizzy|dizziness|lightheaded|vertigo': 'dizziness',
            r'tired|fatigue|exhausted|worn out|drained': 'fatigue',
            r'weak|weakness|feeble': 'weakness',
            r'fever|high temperature|hot|burning up': 'fever',
            r'numbness|numb|tingling|pins and needles': 'numbness',
        }
        
        # NEW: Diagnosis and treatment pattern recognition
        self.diagnosis_patterns = {
            r'diagnosed with|diagnosis of|you have|suffering from|condition is|looks like|appears to be|seems to be': 'diagnosis_indicator',
            r'gastritis|pneumonia|bronchitis|diabetes|hypertension|infection|influenza|migraine|arthritis': 'common_diagnosis',
            r'acute|chronic|mild|severe|moderate|early stage|advanced': 'diagnosis_modifier'
        }
        
        self.treatment_patterns = {
            r'prescribe|recommend|suggest|treatment|therapy|medication|medicine|take|start': 'treatment_indicator',
            r'antibiotics|painkillers|ibuprofen|acetaminophen|rest|surgery|physical therapy': 'treatment_type',
            r'follow up|come back|monitor|check back|return in': 'follow_up_care'
        }
        
        logger.info("Enhanced Symptom Extractor initialized with comprehensive medical vocabulary")
    
    def extract_symptoms_from_text(self, text: str) -> List[str]:
        """Extract symptoms from dialogue text using advanced NLP and medical knowledge"""
        if not text:
            return []
        
        # FIXED: Ensure text is string
        if not isinstance(text, str):
            text = str(text)
        
        text_lower = text.lower().strip()
        extracted_symptoms = set()
        
        # Method 1: Pattern-based extraction
        pattern_symptoms = self._extract_with_patterns(text_lower)
        extracted_symptoms.update(pattern_symptoms)
        
        # Method 2: Medical vocabulary matching
        vocab_symptoms = self._extract_with_vocabulary(text_lower)
        extracted_symptoms.update(vocab_symptoms)
        
        # Method 3: Context-aware extraction
        context_symptoms = self._extract_with_context(text_lower)
        extracted_symptoms.update(context_symptoms)
        
        # Clean and normalize
        normalized_symptoms = self._normalize_symptoms(list(extracted_symptoms))
        
        logger.debug(f"Extracted symptoms: {normalized_symptoms}")
        return normalized_symptoms
    
    def extract_diagnoses_from_text(self, text: str) -> List[str]:
        """Extract diagnoses from dialogue text"""
        if not text or not isinstance(text, str):
            return []
        
        text_lower = text.lower()
        diagnoses = set()
        
        # Look for diagnosis patterns
        diagnosis_indicators = [
            r'diagnosed with\s+([^.,;]+)',
            r'diagnosis of\s+([^.,;]+)',
            r'you have\s+([^.,;]+)',
            r'suffering from\s+([^.,;]+)',
            r'condition is\s+([^.,;]+)',
            r'looks like\s+([^.,;]+)',
            r'appears to be\s+([^.,;]+)',
            r'seems to be\s+([^.,;]+)',
            r'likely\s+([^.,;]+)',
            r'probably\s+([^.,;]+)'
        ]
        
        for pattern in diagnosis_indicators:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                potential_diagnosis = match.group(1).strip()
                if self._is_valid_diagnosis(potential_diagnosis):
                    diagnoses.add(potential_diagnosis)
        
        return list(diagnoses)
    
    def extract_treatments_from_text(self, text: str) -> List[str]:
        """Extract treatments from dialogue text"""
        if not text or not isinstance(text, str):
            return []
        
        text_lower = text.lower()
        treatments = set()
        
        # Look for treatment patterns
        treatment_indicators = [
            r'prescribe\s+([^.,;]+)',
            r'recommend\s+([^.,;]+)',
            r'suggest\s+([^.,;]+)',
            r'treatment with\s+([^.,;]+)',
            r'therapy\s+([^.,;]+)',
            r'take\s+([^.,;]+)',
            r'start\s+([^.,;]+)',
            r'medication\s+([^.,;]+)',
            r'medicine\s+([^.,;]+)'
        ]
        
        for pattern in treatment_indicators:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                potential_treatment = match.group(1).strip()
                if self._is_valid_treatment(potential_treatment):
                    treatments.add(potential_treatment)
        
        # Also look for specific medications and treatments
        specific_treatments = [
            'antibiotics', 'painkillers', 'ibuprofen', 'acetaminophen', 'rest', 
            'surgery', 'physical therapy', 'bed rest', 'exercise', 'diet changes'
        ]
        
        for treatment in specific_treatments:
            if treatment in text_lower:
                treatments.add(treatment)
        
        return list(treatments)
    
    def _is_valid_diagnosis(self, text: str) -> bool:
        """Validate if extracted text is a legitimate diagnosis"""
        if not text or len(text) < 3 or len(text) > 100:
            return False
        
        # Skip common non-diagnosis words
        skip_words = {
            'the', 'and', 'but', 'for', 'with', 'have', 'been', 'that', 'this',
            'when', 'where', 'what', 'how', 'why', 'doctor', 'patient', 'said',
            'going', 'doing', 'feeling', 'looking', 'thinking'
        }
        
        if text.strip() in skip_words:
            return False
        
        # Check for medical condition keywords
        condition_keywords = {
            'syndrome', 'disease', 'disorder', 'condition', 'infection', 'inflammation',
            'itis', 'osis', 'pathy', 'emia', 'uria', 'algia', 'gastritis', 'pneumonia'
        }
        
        return any(keyword in text for keyword in condition_keywords) or len(text.split()) <= 4
    
    def _is_valid_treatment(self, text: str) -> bool:
        """Validate if extracted text is a legitimate treatment"""
        if not text or len(text) < 3 or len(text) > 100:
            return False
        
        # Skip common non-treatment words
        skip_words = {
            'the', 'and', 'but', 'for', 'with', 'have', 'been', 'that', 'this',
            'when', 'where', 'what', 'how', 'why', 'doctor', 'patient', 'said'
        }
        
        if text.strip() in skip_words:
            return False
        
        # Check for treatment keywords
        treatment_keywords = {
            'mg', 'tablet', 'capsule', 'dose', 'daily', 'twice', 'times', 'therapy',
            'treatment', 'medication', 'drug', 'pill', 'injection', 'surgery', 'rest'
        }
        
        return any(keyword in text for keyword in treatment_keywords) or len(text.split()) <= 3
    
    def _extract_with_patterns(self, text: str) -> List[str]:
        """Extract symptoms using regex patterns"""
        symptoms = []
        
        for pattern, symptom_name in self.symptom_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                symptoms.append(symptom_name)
        
        return symptoms
    
    def _extract_with_vocabulary(self, text: str) -> List[str]:
        """Extract symptoms using medical vocabulary matching"""
        symptoms = []
        
        # Pain-related symptoms
        for pain_var in self.symptom_vocabulary['pain']['variations']:
            if pain_var in text:
                # Look for location context
                for location, location_terms in self.symptom_vocabulary['body_locations'].items():
                    for loc_term in location_terms:
                        if loc_term in text:
                            symptoms.append(f"{location} pain")
                            break
                    if f"{location} pain" in symptoms:
                        break
                else:
                    symptoms.append("pain")
        
        # Systemic symptoms
        for system, symptom_list in self.symptom_vocabulary['systemic_symptoms'].items():
            for symptom in symptom_list:
                if symptom in text:
                    symptoms.append(symptom)
        
        return symptoms
    
    def _extract_with_context(self, text: str) -> List[str]:
        """Extract symptoms using contextual analysis"""
        symptoms = []
        
        # Look for symptom-indicating phrases
        symptom_indicators = [
            r'experiencing\s+(\w+(?:\s+\w+)*)',
            r'having\s+(\w+(?:\s+\w+)*)',
            r'feeling\s+(\w+(?:\s+\w+)*)',
            r'been\s+(\w+(?:\s+\w+)*)',
        ]
        
        for pattern in symptom_indicators:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                potential_symptom = match.group(1).strip()
                if self._is_valid_symptom(potential_symptom):
                    symptoms.append(potential_symptom)
        
        return symptoms
    
    def _is_valid_symptom(self, text: str) -> bool:
        """Validate if extracted text is a legitimate symptom"""
        text_lower = text.lower().strip()
        
        # Skip very short or very long phrases
        if len(text_lower) < 3 or len(text_lower) > 50:
            return False
        
        # Skip common non-symptom words
        non_symptom_words = {
            'the', 'and', 'but', 'for', 'with', 'have', 'been', 'that', 'this',
            'when', 'where', 'what', 'how', 'why', 'doctor', 'patient', 'said'
        }
        
        if text_lower in non_symptom_words:
            return False
        
        # Check if it contains symptom-related keywords
        symptom_keywords = {
            'pain', 'ache', 'hurt', 'sore', 'discomfort', 'nausea', 'dizzy', 
            'tired', 'weak', 'fever', 'cough', 'breath', 'sick', 'swollen'
        }
        
        return any(keyword in text_lower for keyword in symptom_keywords)
    
    def _normalize_symptoms(self, symptoms: List[str]) -> List[str]:
        """Normalize and clean symptom descriptions"""
        normalized = []
        
        for symptom in symptoms:
            # FIXED: Ensure symptom is string
            if not isinstance(symptom, str):
                symptom = str(symptom)
                
            # Clean up the symptom text
            clean_symptom = symptom.strip().lower()
            clean_symptom = re.sub(r'\s+', ' ', clean_symptom)  # Multiple spaces to single
            clean_symptom = re.sub(r'[^\w\s]', '', clean_symptom)  # Remove punctuation
            
            # Apply normalization rules
            if clean_symptom:
                # Map variations to standard terms
                if any(word in clean_symptom for word in ['chest', 'heart']):
                    if any(word in clean_symptom for word in ['pain', 'ache', 'hurt', 'discomfort']):
                        clean_symptom = 'chest pain'
                
                elif any(word in clean_symptom for word in ['head', 'skull']):
                    if any(word in clean_symptom for word in ['pain', 'ache', 'hurt']):
                        clean_symptom = 'headache'
                
                elif any(word in clean_symptom for word in ['stomach', 'belly', 'abdomen']):
                    if any(word in clean_symptom for word in ['pain', 'ache', 'hurt']):
                        clean_symptom = 'abdominal pain'
                
                normalized.append(clean_symptom)
        
        # Remove duplicates while preserving order
        seen = set()
        result = []
        for symptom in normalized:
            if symptom not in seen:
                seen.add(symptom)
                result.append(symptom)
        
        return result

class SummarizerAgent:
    """Enhanced SummarizerAgent with robust JSON parsing and better extraction"""
    
    def __init__(self, llm=None):
        # Initialize LLM
        if llm:
            self.llm = llm
        else:
            self.llm = load_gpt_model(
                model_name='gpt-4.1',
                temperature=0.1,  # Lower temperature for more consistent JSON
                max_tokens=800
            )
        
        # Initialize enhanced symptom extractor
        self.symptom_extractor = EnhancedSymptomExtractor()
        
        # Create specialized system message for medical summarization
        self.system_message = {
            "role": "system",
            "content": (
                "You are a medical AI assistant specialized in extracting clinical information "
                "from doctor-patient dialogues. You must return ONLY valid JSON.\n\n"
                
                "**EXTRACTION REQUIREMENTS:**\n"
                "1. Extract ALL symptoms mentioned by the patient\n"
                "2. Extract any diagnoses or assessments made by the doctor\n"
                "3. Extract any treatments, medications, or recommendations given\n"
                "4. Create a brief clinical summary\n\n"
                
                "**CRITICAL: Return ONLY valid JSON in this exact format:**\n"
                "{\n"
                "  \"symptoms\": [\"list of symptoms\"],\n"
                "  \"diagnoses\": [\"list of diagnoses or assessments\"],\n"
                "  \"treatments\": [\"list of treatments or recommendations\"],\n"
                "  \"summary\": \"brief clinical summary\"\n"
                "}\n\n"
                
                "**IMPORTANT RULES:**\n"
                "- Use double quotes only\n"
                "- No trailing commas\n"
                "- Keep entries concise\n"
                "- Return ONLY the JSON object, no other text\n"
                "- If no items found for a category, use empty array: []"
            )
        }
        
        logger.info("Enhanced SummarizerAgent initialized with robust JSON parsing")
    
    def summarize_and_annotate(self, dialogue_text: str) -> Tuple[str, Dict]:
        """
        Enhanced summarization with robust JSON parsing and better extraction
        """
        if not dialogue_text or not dialogue_text.strip():
            return "No dialogue content provided.", {"symptoms": [], "diagnoses": [], "treatments": []}
        
        # FIXED: Ensure dialogue_text is string
        if not isinstance(dialogue_text, str):
            dialogue_text = str(dialogue_text)
        
        logger.info("Starting robust extraction and summarization...")
        
        try:
            # Method 1: Advanced pattern-based extraction
            pattern_symptoms = self.symptom_extractor.extract_symptoms_from_text(dialogue_text)
            pattern_diagnoses = self.symptom_extractor.extract_diagnoses_from_text(dialogue_text)
            pattern_treatments = self.symptom_extractor.extract_treatments_from_text(dialogue_text)
            
            # Method 2: LLM-based extraction with robust JSON handling
            llm_symptoms, llm_diagnoses, llm_treatments, llm_summary = self._robust_llm_extraction(dialogue_text)
            
            # Method 3: Combine and validate results
            combined_symptoms = self._combine_and_deduplicate(pattern_symptoms, llm_symptoms)
            combined_diagnoses = self._combine_and_deduplicate(pattern_diagnoses, llm_diagnoses)
            combined_treatments = self._combine_and_deduplicate(pattern_treatments, llm_treatments)
            
            # Create comprehensive annotations
            final_annotations = {
                "symptoms": combined_symptoms,
                "diagnoses": combined_diagnoses,
                "treatments": combined_treatments
            }
            
            # Generate enhanced summary
            enhanced_summary = self._generate_robust_summary(dialogue_text, final_annotations, llm_summary)
            
            logger.info(f"Robust extraction completed - Symptoms: {len(combined_symptoms)}, "
                       f"Diagnoses: {len(combined_diagnoses)}, "
                       f"Treatments: {len(combined_treatments)}")
            
            return enhanced_summary, final_annotations
            
        except Exception as e:
            logger.error(f"Error in robust summarization: {e}")
            # ROBUST FALLBACK
            try:
                fallback_symptoms = self.symptom_extractor.extract_symptoms_from_text(dialogue_text)
                fallback_diagnoses = self.symptom_extractor.extract_diagnoses_from_text(dialogue_text)
                fallback_treatments = self.symptom_extractor.extract_treatments_from_text(dialogue_text)
            except Exception as inner_e:
                logger.error(f"Fallback extraction also failed: {inner_e}")
                fallback_symptoms = []
                fallback_diagnoses = []
                fallback_treatments = []
                
            fallback_annotations = {
                "symptoms": fallback_symptoms,
                "diagnoses": fallback_diagnoses,
                "treatments": fallback_treatments
            }
            fallback_summary = self._generate_fallback_summary(dialogue_text, fallback_annotations)
            
            return fallback_summary, fallback_annotations
    
    def _robust_llm_extraction(self, dialogue_text: str) -> Tuple[List[str], List[str], List[str], str]:
        """Use LLM with robust JSON parsing for enhanced extraction"""
        
        # Create focused extraction prompt
        extraction_prompt = (
            f"Extract information from this medical dialogue and return ONLY valid JSON:\n\n"
            f"DIALOGUE:\n{dialogue_text}\n\n"
            f"Return ONLY this JSON format with actual extracted data:\n"
            f"{{\n"
            f"  \"symptoms\": [\"symptom1\", \"symptom2\"],\n"
            f"  \"diagnoses\": [\"diagnosis1\", \"diagnosis2\"],\n"
            f"  \"treatments\": [\"treatment1\", \"treatment2\"],\n"
            f"  \"summary\": \"clinical summary\"\n"
            f"}}"
        )
        
        # Construct LLM messages
        messages = [
            self.system_message,
            {"role": "user", "content": extraction_prompt}
        ]
        
        try:
            # Get LLM response
            response = chat_generate(self.llm, messages)
            
            # Parse JSON response with robust handling
            annotations = self._robust_json_parsing(response)
            
            symptoms = self._safe_list_extract(annotations, "symptoms")
            diagnoses = self._safe_list_extract(annotations, "diagnoses")
            treatments = self._safe_list_extract(annotations, "treatments")
            summary = self._safe_string_extract(annotations, "summary")
            
            return symptoms, diagnoses, treatments, summary
            
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
            return [], [], [], "Clinical dialogue summary."
    
    def _robust_json_parsing(self, response: str) -> Dict:
        """Robust JSON parsing with multiple fallback strategies"""
        if not response:
            return {"symptoms": [], "diagnoses": [], "treatments": [], "summary": ""}
        
        # Strategy 1: Try direct JSON parsing
        try:
            # Find JSON boundaries
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_text = response[json_start:json_end]
                
                # Clean common JSON issues
                json_text = self._clean_json_text(json_text)
                
                parsed = json.loads(json_text)
                
                # Validate structure
                if isinstance(parsed, dict):
                    return {
                        "symptoms": self._safe_list_extract(parsed, "symptoms"),
                        "diagnoses": self._safe_list_extract(parsed, "diagnoses"),
                        "treatments": self._safe_list_extract(parsed, "treatments"),
                        "summary": self._safe_string_extract(parsed, "summary")
                    }
        
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing failed: {e}")
        
        # Strategy 2: Manual parsing with regex
        try:
            return self._manual_json_parsing(response)
        except Exception as e:
            logger.warning(f"Manual parsing failed: {e}")
        
        # Strategy 3: Return empty structure
        return {"symptoms": [], "diagnoses": [], "treatments": [], "summary": ""}
    
    def _clean_json_text(self, json_text: str) -> str:
        """Clean common JSON formatting issues"""
        # Remove trailing commas before closing brackets/braces
        json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
        
        # Fix single quotes to double quotes
        json_text = re.sub(r"'([^']*)':", r'"\1":', json_text)
        json_text = re.sub(r':\s*\'([^\']*?)\'', r': "\1"', json_text)
        
        # Remove comments
        json_text = re.sub(r'//.*$', '', json_text, flags=re.MULTILINE)
        
        # Remove extra whitespace
        json_text = re.sub(r'\s+', ' ', json_text)
        
        return json_text.strip()
    
    def _manual_json_parsing(self, response: str) -> Dict:
        """Manual parsing when JSON parsing fails"""
        result = {"symptoms": [], "diagnoses": [], "treatments": [], "summary": ""}
        
        # Extract arrays using regex
        patterns = {
            'symptoms': r'"symptoms"\s*:\s*\[(.*?)\]',
            'diagnoses': r'"diagnoses"\s*:\s*\[(.*?)\]',
            'treatments': r'"treatments"\s*:\s*\[(.*?)\]',
            'summary': r'"summary"\s*:\s*"([^"]*)"'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                if key == 'summary':
                    result[key] = match.group(1).strip()
                else:
                    # Extract array items
                    items_text = match.group(1)
                    items = re.findall(r'"([^"]*)"', items_text)
                    result[key] = [item.strip() for item in items if item.strip()]
        
        return result
    
    def _safe_list_extract(self, data: Dict, key: str) -> List[str]:
        """Safely extract list from dictionary"""
        if not isinstance(data, dict):
            return []
        
        value = data.get(key, [])
        
        if isinstance(value, list):
            # Clean and filter list items
            cleaned = []
            for item in value:
                if item is not None:
                    item_str = str(item).strip()
                    if item_str and len(item_str) > 1:  # Filter out single characters
                        cleaned.append(item_str)
            return cleaned
        elif isinstance(value, str):
            # If single string, return as list
            return [value.strip()] if value.strip() else []
        else:
            return []
    
    def _safe_string_extract(self, data: Dict, key: str) -> str:
        """Safely extract string from dictionary"""
        if not isinstance(data, dict):
            return ""
        
        value = data.get(key, "")
        return str(value).strip() if value is not None else ""
    
    def _combine_and_deduplicate(self, list1: List[str], list2: List[str]) -> List[str]:
        """Combine two lists and remove duplicates while preserving order"""
        seen = set()
        combined = []
        
        # Add items from both lists
        for item_list in [list1, list2]:
            for item in item_list:
                if item and isinstance(item, str):
                    item_clean = item.strip().lower()
                    if item_clean and item_clean not in seen and len(item_clean) > 2:
                        seen.add(item_clean)
                        combined.append(item.strip())
        
        return combined
    
    def _generate_robust_summary(self, dialogue_text: str, annotations: Dict, llm_summary: str) -> str:
        """Generate robust clinical summary"""
        
        symptoms = annotations.get("symptoms", [])
        diagnoses = annotations.get("diagnoses", [])
        treatments = annotations.get("treatments", [])
        
        summary_parts = []
        
        # Patient presentation
        if symptoms:
            summary_parts.append(f"Patient presents with: {', '.join(symptoms[:5])}")  # Limit to first 5
        else:
            summary_parts.append("Patient consultation regarding health concerns")
        
        # Clinical assessment
        if diagnoses:
            summary_parts.append(f"Assessment: {', '.join(diagnoses[:3])}")  # Limit to first 3
        
        # Treatment plan
        if treatments:
            summary_parts.append(f"Plan: {', '.join(treatments[:3])}")  # Limit to first 3
        
        # Use LLM summary if available and reasonable
        if llm_summary and len(llm_summary) > 20 and len(llm_summary) < 500:
            summary_parts.append(f"Clinical note: {llm_summary}")
        
        # Quality note
        summary_parts.append(f"Extracted: {len(symptoms)} symptoms, {len(diagnoses)} diagnoses, {len(treatments)} treatments")
        
        return ". ".join(summary_parts) + "."
    
    def _generate_fallback_summary(self, dialogue_text: str, annotations: Dict) -> str:
        """Generate fallback summary when LLM extraction fails"""
        
        symptoms = annotations.get("symptoms", [])
        diagnoses = annotations.get("diagnoses", [])
        treatments = annotations.get("treatments", [])
        
        if symptoms:
            return f"Medical consultation. Patient symptoms: {', '.join(symptoms[:3])}. Diagnoses: {', '.join(diagnoses[:2]) if diagnoses else 'None extracted'}. Treatments: {', '.join(treatments[:2]) if treatments else 'None extracted'}."
        else:
            return f"Medical consultation documented. Dialogue length: {len(dialogue_text.split())} words. Clinical information extraction attempted."