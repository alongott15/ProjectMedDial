import logging
import re
from typing import Dict, List, Tuple, Set
from collections import Counter
import numpy as np

# Try to import advanced libraries with fallbacks
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except Exception:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    from bert_score import score as bert_score_calculate
    import torch
    BERT_SCORE_AVAILABLE = True
except Exception:
    BERT_SCORE_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MedicalConceptExtractor:
    """Extract and evaluate medical concepts from dialogue"""
    
    def __init__(self):
        # Medical terminology and concepts (unchanged)
        self.medical_vocabulary = {
            'symptoms': {
                'pain', 'ache', 'hurt', 'discomfort', 'sore', 'tender', 'burning', 'stinging',
                'sharp', 'dull', 'throbbing', 'cramping', 'radiating', 'shooting', 'stabbing',
                'nausea', 'nauseous', 'dizzy', 'dizziness', 'lightheaded', 'vertigo',
                'fatigue', 'tired', 'exhausted', 'weakness', 'weak', 'feeble',
                'shortness of breath', 'breathless', 'breathing difficulty', 'dyspnea',
                'cough', 'coughing', 'wheezing', 'fever', 'chills', 'sweating',
                'headache', 'migraine', 'numbness', 'tingling', 'swelling', 'swollen',
                'itching', 'itchy', 'rash', 'blurred vision', 'hearing problems'
            },
            'body_parts': {
                'head', 'neck', 'chest', 'heart', 'lung', 'abdomen', 'stomach', 'belly',
                'back', 'spine', 'shoulder', 'arm', 'elbow', 'wrist', 'hand', 'finger',
                'hip', 'leg', 'knee', 'ankle', 'foot', 'toe', 'side', 'flank',
                'throat', 'ear', 'eye', 'nose', 'mouth', 'jaw', 'brain'
            },
            'medical_terms': {
                'diagnosis', 'treatment', 'medication', 'prescription', 'therapy',
                'examination', 'test', 'scan', 'x-ray', 'blood work', 'lab results',
                'symptoms', 'condition', 'disease', 'illness', 'infection', 'inflammation',
                'chronic', 'acute', 'severe', 'mild', 'moderate', 'persistent'
            },
            'temporal_indicators': {
                'started', 'began', 'onset', 'since', 'for', 'during', 'after', 'before',
                'suddenly', 'gradually', 'recently', 'lately', 'ongoing', 'constant',
                'intermittent', 'occasional', 'frequent', 'daily', 'weekly', 'monthly'
            }
        }
        
        self.all_medical_terms = set()
        for category in self.medical_vocabulary.values():
            self.all_medical_terms.update(category)
        
        logger.info(f"Medical concept extractor initialized with {len(self.all_medical_terms)} terms")
    
    def extract_medical_concepts(self, text: str) -> Dict[str, List[str]]:
        """Extract medical concepts from text"""
        if not text:
            return {"symptoms": [], "body_parts": [], "medical_terms": [], "temporal": []}
        
        text_lower = text.lower()
        concepts = {"symptoms": [], "body_parts": [], "medical_terms": [], "temporal": []}
        
        for category, terms in self.medical_vocabulary.items():
            category_key = category if category != 'temporal_indicators' else 'temporal'
            
            for term in terms:
                if term in text_lower:
                    concepts[category_key].append(term)
        
        # Remove duplicates while preserving order
        for category in concepts:
            concepts[category] = list(dict.fromkeys(concepts[category]))
        
        return concepts
    
    def calculate_medical_concept_coverage(self, dialogue_concepts: Dict, gt_concepts: Dict) -> Dict[str, float]:
        """Calculate coverage of medical concepts"""
        coverage_scores = {}
        
        for category in ['symptoms', 'body_parts', 'medical_terms', 'temporal']:
            dialogue_set = set(dialogue_concepts.get(category, []))
            gt_set = set(gt_concepts.get(category, []))
            
            if not gt_set:
                coverage_scores[f'{category}_coverage'] = 1.0
            elif not dialogue_set:
                coverage_scores[f'{category}_coverage'] = 0.0
            else:
                intersection = dialogue_set.intersection(gt_set)
                coverage = len(intersection) / len(gt_set)
                coverage_scores[f'{category}_coverage'] = coverage
        
        # Overall medical concept coverage
        all_scores = [score for score in coverage_scores.values()]
        coverage_scores['overall_medical_coverage'] = np.mean(all_scores) if all_scores else 0.0
        
        return coverage_scores

class DialogueQualityEvaluator:
    """Evaluate dialogue-specific quality metrics with REALISTIC scoring"""
    
    def __init__(self):
        self.quality_patterns = {
            'naturalness': {
                'hesitations': ['well', 'um', 'uh', 'er', 'let me think'],
                'corrections': ['actually', 'i mean', 'that is', 'or rather'],
                'uncertainty': ['i think', 'maybe', 'perhaps', 'i\'m not sure'],
                'everyday_language': ['kind of', 'sort of', 'you know']
            },
            'empathy': {
                'acknowledgment': ['i understand', 'i see', 'i hear you'],
                'validation': ['that must be', 'i can imagine', 'that sounds'],
                'support': ['you did the right thing', 'that\'s concerning'],
                'reassurance': ['we\'ll figure this out', 'let me help']
            },
            'professionalism': {
                'systematic_inquiry': ['let me ask about', 'can you tell me'],
                'clinical_reasoning': ['based on your symptoms', 'given your symptoms'],
                'clear_communication': ['let me explain', 'what i mean is'],
                'patient_centered': ['how does that affect you', 'what\'s most concerning']
            }
        }
    
    def assess_dialogue_naturalness(self, dialogue_text: str) -> Dict[str, float]:
        """Assess dialogue naturalness with REALISTIC scoring"""
        dialogue_lower = dialogue_text.lower()
        scores = {}
        
        for quality_type, patterns in self.quality_patterns.items():
            category_scores = []
            
            for pattern_type, pattern_list in patterns.items():
                pattern_count = sum(1 for pattern in pattern_list if pattern in dialogue_lower)
                word_count = max(len(dialogue_text.split()), 1)
                
                # REALISTIC normalization
                normalized_score = min(1.0, pattern_count / max(word_count / 100, 1))
                category_scores.append(normalized_score)
            
            scores[quality_type] = np.mean(category_scores) if category_scores else 0.0
        
        # REALISTIC overall naturalness - no artificial boosting
        scores['overall_naturalness'] = np.mean(list(scores.values()))
        
        return scores
    
    def evaluate_progressive_disclosure(self, dialogue_text: str) -> float:
        """Evaluate progressive disclosure with realistic scoring"""
        lines = dialogue_text.split('\n')
        patient_lines = [line for line in lines if 'patient:' in line.lower()]
        
        if len(patient_lines) < 2:
            return 0.5  # Neutral score for short dialogues
        
        # Analyze information density progression
        word_counts = [len(line.split()) for line in patient_lines]
        
        if not word_counts:
            return 0.5
        
        first_response_length = word_counts[0]
        
        # Realistic progressive disclosure assessment
        if first_response_length > 50:  # Very long first response
            return 0.3
        elif first_response_length > 30:  # Moderately long first response
            return 0.6
        
        # Check for gradual information building
        if len(word_counts) >= 3:
            early_avg = np.mean(word_counts[:2])
            later_avg = np.mean(word_counts[2:])
            
            if early_avg <= 25 and later_avg >= early_avg:
                return 0.8
            elif early_avg <= 35:
                return 0.6
        
        return 0.5
    
    def calculate_conversation_flow(self, dialogue_text: str) -> float:
        """Calculate conversation flow quality"""
        flow_indicators = [
            'going back to', 'you mentioned', 'earlier you said',
            'so if i understand', 'it sounds like', 'what you\'re saying'
        ]
        
        flow_count = sum(1 for indicator in flow_indicators 
                        if indicator in dialogue_text.lower())
        
        lines = dialogue_text.split('\n')
        total_exchanges = max(len([line for line in lines if ':' in line]) // 2, 1)
        
        # Realistic flow scoring
        flow_score = min(0.8, 0.3 + (flow_count / max(total_exchanges / 2, 1)) * 0.5)
        
        return flow_score

class MedicalSafetyEvaluator:
    """Evaluate medical safety and appropriateness"""
    
    def __init__(self):
        self.safety_patterns = {
            'harmful_advice': [
                'ignore this', 'don\'t worry about', 'skip the', 'avoid seeing',
                'no need for', 'just wait it out'
            ],
            'inappropriate_diagnosis': [
                'you definitely have', 'it\'s certainly', 'i\'m sure it\'s',
                'without a doubt', 'absolutely certain'
            ]
        }
        
        self.safety_positive = [
            'please see a doctor', 'consult your physician', 'seek medical attention',
            'if symptoms worsen', 'follow up with', 'under medical supervision'
        ]
    
    def assess_medical_safety(self, dialogue_text: str) -> Dict[str, float]:
        """Assess medical safety with realistic scoring"""
        dialogue_lower = dialogue_text.lower()
        
        # Check for safety concerns
        safety_issues = 0
        for category, patterns in self.safety_patterns.items():
            for pattern in patterns:
                if pattern in dialogue_lower:
                    safety_issues += 1
        
        # Check for positive safety indicators
        safety_positives = sum(1 for pattern in self.safety_positive 
                              if pattern in dialogue_lower)
        
        # Realistic safety scoring
        base_safety = 0.7  # Reasonable baseline
        safety_penalty = min(0.4, safety_issues * 0.15)
        safety_bonus = min(0.3, safety_positives * 0.1)
        
        final_safety = max(0.0, min(1.0, base_safety - safety_penalty + safety_bonus))
        
        return {
            'safety_score': final_safety,
            'safety_issues_detected': safety_issues,
            'safety_positives_detected': safety_positives
        }

class ValidatorAgent:
    """
    FIXED Validator Agent with realistic scoring and proper medical validation
    """
    
    def __init__(self):
        self.medical_extractor = MedicalConceptExtractor()
        self.dialogue_evaluator = DialogueQualityEvaluator()
        self.safety_evaluator = MedicalSafetyEvaluator()
        
        # Initialize sentence transformer if available
        self.sentence_transformer = None
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.sentence_transformer = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("Sentence transformer initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize sentence transformer: {e}")
        
        self.use_bert_score = BERT_SCORE_AVAILABLE
        
        if not self.use_bert_score:
            logger.warning("BERTScore not available, using fallback semantic similarity")
        
        logger.info("FIXED ValidatorAgent initialized with realistic scoring")
    
    def calculate_bertscore_clinical(self, predicted_text: str, reference_text: str) -> Dict[str, float]:
        """Calculate BERTScore or realistic semantic similarity"""
        if not predicted_text or not reference_text:
            return {'bertscore_precision': 0.0, 'bertscore_recall': 0.0, 'bertscore_f1': 0.0}
        
        if self.use_bert_score:
            try:
                device = 'cuda' if torch.cuda.is_available() else 'cpu'
                
                P_tensor, R_tensor, F1_tensor = bert_score_calculate(
                    [predicted_text],
                    [reference_text],
                    lang="en",
                    model_type="microsoft/deberta-xlarge-mnli",
                    verbose=False,
                    device=device,
                    idf=False
                )
                
                return {
                    'bertscore_precision': P_tensor.item(),
                    'bertscore_recall': R_tensor.item(),
                    'bertscore_f1': F1_tensor.item()
                }
                
            except Exception as e:
                logger.warning(f"BERTScore calculation failed: {e}")
        
        # Fallback to realistic semantic similarity
        return self._realistic_semantic_similarity(predicted_text, reference_text)
    
    def _realistic_semantic_similarity(self, text1: str, text2: str) -> Dict[str, float]:
        """Realistic semantic similarity calculation"""
        if not text1 or not text2:
            return {'bertscore_precision': 0.0, 'bertscore_recall': 0.0, 'bertscore_f1': 0.0}
        
        if self.sentence_transformer:
            try:
                embeddings = self.sentence_transformer.encode([text1, text2])
                similarity = np.dot(embeddings[0], embeddings[1]) / (
                    np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
                )
                
                # Convert cosine similarity to precision/recall/f1 approximation
                return {
                    'bertscore_precision': max(0.0, similarity),
                    'bertscore_recall': max(0.0, similarity),
                    'bertscore_f1': max(0.0, similarity)
                }
            except Exception as e:
                logger.warning(f"Sentence transformer similarity failed: {e}")
        
        # Basic token overlap fallback
        tokens1 = set(re.findall(r'\b\w+\b', text1.lower()))
        tokens2 = set(re.findall(r'\b\w+\b', text2.lower()))
        
        if not tokens1 or not tokens2:
            precision = recall = f1 = 0.0
        else:
            intersection = tokens1.intersection(tokens2)
            precision = len(intersection) / len(tokens1)
            recall = len(intersection) / len(tokens2)
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        
        # Add small medical domain boost if medical terms are present
        medical_overlap = intersection.intersection(self.medical_extractor.all_medical_terms)
        if medical_overlap:
            boost = min(0.2, len(medical_overlap) * 0.05)
            precision = min(1.0, precision + boost)
            recall = min(1.0, recall + boost)
            f1 = min(1.0, f1 + boost)
        
        return {
            'bertscore_precision': precision,
            'bertscore_recall': recall,
            'bertscore_f1': f1
        }
    
    def evaluate(self, ground_truth: dict, conversation_info: dict) -> dict:
        """
        FIXED evaluation with realistic scoring
        """
        logger.info("Starting FIXED dialogue evaluation with realistic metrics...")
        
        # Extract dialogue text
        dialogue_text = conversation_info.get('dialogue_text', conversation_info.get('transcript', ''))
        if not dialogue_text:
            logger.warning("No dialogue text found for evaluation")
            return self._get_realistic_zero_scores()
        
        # Extract ground truth information
        gt_symptoms = self._extract_gt_symptoms(ground_truth)
        gt_text = " ".join(gt_symptoms) if gt_symptoms else "medical consultation"
        
        # Extract conversation information
        extracted_info = conversation_info.get('extracted_info', {})
        conv_symptoms = extracted_info.get('symptoms', [])
        conv_text = " ".join(conv_symptoms) if conv_symptoms else dialogue_text
        
        logger.info(f"FIXED evaluation: {len(dialogue_text.split())} words, {len(gt_symptoms)} GT symptoms")
        
        # 1. Realistic Semantic Similarity
        semantic_scores = self.calculate_bertscore_clinical(conv_text, gt_text)
        
        # 2. Medical Concept Coverage
        gt_concepts = self.medical_extractor.extract_medical_concepts(gt_text)
        dialogue_concepts = self.medical_extractor.extract_medical_concepts(dialogue_text)
        concept_scores = self.medical_extractor.calculate_medical_concept_coverage(
            dialogue_concepts, gt_concepts
        )
        
        # 3. Realistic Dialogue Quality Assessment
        dialogue_quality = self.dialogue_evaluator.assess_dialogue_naturalness(dialogue_text)
        progressive_disclosure = self.dialogue_evaluator.evaluate_progressive_disclosure(dialogue_text)
        conversation_flow = self.dialogue_evaluator.calculate_conversation_flow(dialogue_text)
        
        # 4. Medical Safety Assessment
        safety_scores = self.safety_evaluator.assess_medical_safety(dialogue_text)
        
        # Combine all scores with REALISTIC weighting
        comprehensive_scores = {
            # Semantic similarity
            **semantic_scores,
            
            # Medical domain accuracy
            **concept_scores,
            
            # Realistic dialogue quality
            'dialogue_naturalness': dialogue_quality['naturalness'],
            'dialogue_empathy': dialogue_quality['empathy'],
            'dialogue_professionalism': dialogue_quality['professionalism'],
            'progressive_disclosure_quality': progressive_disclosure,
            'conversation_flow_quality': conversation_flow,
            'overall_dialogue_quality': np.mean([
                dialogue_quality['overall_naturalness'],
                progressive_disclosure,
                conversation_flow
            ]),
            
            # Medical safety
            **safety_scores,
            
            # REALISTIC overall SOTA score calculation
            'overall_sota_score': self._calculate_realistic_overall_score(
                semantic_scores, concept_scores, dialogue_quality, 
                safety_scores, progressive_disclosure, conversation_flow
            )
        }
        
        # Add summary statistics
        comprehensive_scores['evaluation_summary'] = self._generate_evaluation_summary(comprehensive_scores)
        
        logger.info(f"FIXED evaluation completed - Overall score: {comprehensive_scores['overall_sota_score']:.3f}")
        
        return comprehensive_scores
    
    def _calculate_realistic_overall_score(self, semantic_scores: dict, concept_scores: dict, 
                                         dialogue_quality: dict, safety_scores: dict, 
                                         progressive_disclosure: float, conversation_flow: float) -> float:
        """Calculate realistic weighted overall SOTA score"""
        
        # Realistic weights
        weights = {
            'semantic_similarity': 0.25,
            'medical_concepts': 0.25,
            'dialogue_realism': 0.25,
            'medical_safety': 0.25
        }
        
        # Calculate component scores
        semantic_component = semantic_scores.get('bertscore_f1', 0.0) * weights['semantic_similarity']
        medical_component = concept_scores.get('overall_medical_coverage', 0.0) * weights['medical_concepts']
        dialogue_component = dialogue_quality.get('overall_naturalness', 0.0) * weights['dialogue_realism']
        safety_component = safety_scores.get('safety_score', 0.0) * weights['medical_safety']
        
        # Realistic overall score
        overall_score = semantic_component + medical_component + dialogue_component + safety_component
        
        return max(0.0, min(1.0, overall_score))
    
    def _extract_gt_symptoms(self, ground_truth: dict) -> List[str]:
        """Extract symptoms from ground truth profile"""
        symptoms = []
        
        gt_symptoms = ground_truth.get("Core_Fields", {}).get("Symptoms", [])
        for symptom in gt_symptoms:
            if isinstance(symptom, dict):
                desc = symptom.get("description", "").strip()
                if desc:
                    symptoms.append(desc.lower())
            elif isinstance(symptom, str) and symptom.strip():
                symptoms.append(symptom.strip().lower())
        
        return symptoms
    
    def _generate_evaluation_summary(self, scores: dict) -> dict:
        """Generate evaluation summary"""
        return {
            'top_strengths': self._identify_strengths(scores),
            'improvement_areas': self._identify_weaknesses(scores),
            'safety_status': 'GOOD' if scores.get('safety_score', 0) > 0.8 else 'ADEQUATE' if scores.get('safety_score', 0) > 0.6 else 'NEEDS_REVIEW',
            'overall_quality': self._quality_rating(scores.get('overall_sota_score', 0))
        }
    
    def _identify_strengths(self, scores: dict) -> List[str]:
        """Identify top performing areas"""
        strengths = []
        
        if scores.get('bertscore_f1', 0) > 0.6:
            strengths.append("Good semantic similarity to medical content")
        if scores.get('dialogue_naturalness', 0) > 0.5:
            strengths.append("Natural conversation flow")
        if scores.get('progressive_disclosure_quality', 0) > 0.6:
            strengths.append("Appropriate progressive information disclosure")
        if scores.get('safety_score', 0) > 0.8:
            strengths.append("High medical safety standards")
        
        return strengths[:3]
    
    def _identify_weaknesses(self, scores: dict) -> List[str]:
        """Identify areas needing improvement"""
        weaknesses = []
        
        if scores.get('bertscore_f1', 0) < 0.4:
            weaknesses.append("Improve content alignment with medical information")
        if scores.get('dialogue_naturalness', 0) < 0.4:
            weaknesses.append("Enhance conversation naturalness and flow")
        if scores.get('safety_score', 0) < 0.6:
            weaknesses.append("Address medical safety and communication concerns")
        
        return weaknesses[:2]
    
    def _quality_rating(self, overall_score: float) -> str:
        """Convert score to quality rating"""
        if overall_score >= 0.8:
            return "EXCELLENT"
        elif overall_score >= 0.65:
            return "GOOD"
        elif overall_score >= 0.5:
            return "ACCEPTABLE"
        elif overall_score >= 0.35:
            return "NEEDS_IMPROVEMENT"
        else:
            return "POOR"
    
    def _get_realistic_zero_scores(self) -> dict:
        """Return realistic zero scores for failed evaluation"""
        return {
            'bertscore_precision': 0.0,
            'bertscore_recall': 0.0,
            'bertscore_f1': 0.0,
            'overall_medical_coverage': 0.0,
            'dialogue_naturalness': 0.0,
            'progressive_disclosure_quality': 0.0,
            'safety_score': 0.5,  # Neutral assumption
            'overall_sota_score': 0.0,
            'evaluation_summary': {
                'top_strengths': [],
                'improvement_areas': ['Enhance dialogue evaluation'],
                'safety_status': 'NEEDS_REVIEW',
                'overall_quality': 'POOR'
            }
        }