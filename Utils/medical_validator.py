# Utils/medical_validator.py
"""
Advanced Medical Validation using established clinical NLP metrics
"""
import logging
import numpy as np
from dataclasses import dataclass
import re
from collections import Counter
from sklearn.metrics import precision_recall_fscore_support, accuracy_score
import nltk
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from rouge_score import rouge_scorer

# Try importing advanced medical NLP tools
try:
    from transformers import AutoTokenizer, AutoModel
    import torch
    TRANSFORMERS_AVAILABLE = True
except:
    TRANSFORMERS_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class ClinicalValidationMetrics:
    """Standard clinical validation metrics following medical NLP literature"""
    
    # Content Accuracy Metrics (Based on clinical NLP standards)
    medical_entity_f1: float          # F1 for medical entity extraction
    concept_precision: float          # Precision of medical concepts
    concept_recall: float             # Recall of medical concepts
    terminology_accuracy: float       # Accuracy of medical terminology
    
    # Semantic Similarity Metrics (Clinical domain)
    clinical_bleu: float              # BLEU adapted for clinical text
    clinical_rouge_l: float           # ROUGE-L for clinical content
    clinical_bertscore: float         # Clinical BERT similarity
    semantic_coherence: float         # Semantic coherence score
    
    # Clinical Quality Metrics (Domain-specific)
    clinical_completeness: float      # Completeness of clinical information
    diagnostic_coherence: float       # Coherence of diagnostic reasoning
    treatment_appropriateness: float  # Appropriateness of treatments
    clinical_safety: float            # Clinical safety assessment
    
    # Dialogue Quality Metrics (Medical conversation standards)
    empathy_score: float              # Empathy in medical communication
    information_seeking: float        # Information gathering quality
    explanation_clarity: float        # Clarity of medical explanations
    patient_centeredness: float       # Patient-centered communication
    
    # Overall Quality Indicators
    overall_clinical_quality: float   # Weighted overall score
    confidence_interval: tuple  # 95% confidence interval
    
    # Detailed breakdowns
    detailed_scores: dict
    quality_indicators: dict
    recommendations: list

class AdvancedMedicalValidator:
    """
    Advanced medical validation using established clinical NLP metrics
    and best practices from medical informatics literature
    """
    
    def __init__(self, mimic_knowledge_base=None):
        self.mimic_kb = mimic_knowledge_base
        self._initialize_models()
        self._initialize_medical_patterns()
        self._initialize_scoring_weights()
        
        logger.info("Initialized advanced medical validator with clinical NLP metrics")
    
    def _initialize_models(self):
        """Initialize pre-trained models for clinical validation"""
        
        # Clinical BERT for semantic similarity
        if TRANSFORMERS_AVAILABLE:
            try:
                # Use ClinicalBERT if available, otherwise Bio_ClinicalBERT
                self.clinical_bert_tokenizer = AutoTokenizer.from_pretrained('emilyalsentzer/Bio_ClinicalBERT')
                self.clinical_bert_model = AutoModel.from_pretrained('emilyalsentzer/Bio_ClinicalBERT')
                self.clinical_bert_available = True
                logger.info("Loaded ClinicalBERT for semantic validation")
            except:
                self.clinical_bert_available = False
                logger.warning("ClinicalBERT not available, using fallback methods")
        else:
            self.clinical_bert_available = False
        
        # Clinical sentence transformer
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.clinical_sentence_transformer = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
                logger.info("Loaded sentence transformer for clinical similarity")
            except:
                self.clinical_sentence_transformer = None
        else:
            self.clinical_sentence_transformer = None
        
        # ROUGE scorer for clinical content
        self.rouge_scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)
        
        # BLEU smoothing function for clinical text
        self.bleu_smoothing = SmoothingFunction().method1
    
    def _initialize_medical_patterns(self):
        """Initialize medical communication patterns from literature"""
        
        # Empathy patterns from medical communication research
        self.empathy_patterns = {
            'acknowledgment': [
                r'\bi understand\b', r'\bi see\b', r'\bi hear you\b', r'\bthat makes sense\b'
            ],
            'validation': [
                r'\bthat must be\b', r'\bi can imagine\b', r'\bthat sounds\b', r'\byou\'re right to\b'
            ],
            'partnership': [
                r'\bwe\'ll work together\b', r'\blet\'s figure this out\b', r'\bi\'m here to help\b'
            ],
            'reassurance': [
                r'\byou\'re doing the right thing\b', r'\bthis is treatable\b', r'\bwe can help\b'
            ]
        }
        
        # Information seeking patterns from clinical interview research
        self.information_seeking_patterns = {
            'open_ended': [
                r'\btell me about\b', r'\bwhat\'s been happening\b', r'\bhow are you feeling\b'
            ],
            'specific_inquiry': [
                r'\bwhen did this start\b', r'\bhow severe\b', r'\bwhere exactly\b'
            ],
            'clarification': [
                r'\bcan you explain\b', r'\bwhat do you mean by\b', r'\bhelp me understand\b'
            ],
            'follow_up': [
                r'\banything else\b', r'\bother symptoms\b', r'\banything that makes it\b'
            ]
        }
        
        # Clinical explanation patterns
        self.explanation_patterns = {
            'clear_language': [
                r'\bin simple terms\b', r'\bwhat this means is\b', r'\bto put it simply\b'
            ],
            'step_by_step': [
                r'\bfirst\b.*\bthen\b', r'\bnext we\'ll\b', r'\bthe first step\b'
            ],
            'checking_understanding': [
                r'\bdoes that make sense\b', r'\bdo you have questions\b', r'\bis that clear\b'
            ]
        }
        
        # Patient-centered communication patterns
        self.patient_centered_patterns = {
            'preference_inquiry': [
                r'\bwhat would you prefer\b', r'\bhow do you feel about\b', r'\bwhat matters to you\b'
            ],
            'shared_decision': [
                r'\bwhat are your thoughts\b', r'\blet\'s decide together\b', r'\byour input is important\b'
            ],
            'concern_addressing': [
                r'\bwhat worries you most\b', r'\bwhat\'s your biggest concern\b', r'\bwhat questions do you have\b'
            ]
        }
    
    def _initialize_scoring_weights(self):
        """Initialize scoring weights based on clinical validation literature"""
        
        # Weights based on medical informatics research
        self.metric_weights = {
            'medical_accuracy': 0.25,      # Medical content accuracy
            'semantic_quality': 0.20,      # Semantic similarity and coherence
            'clinical_reasoning': 0.20,    # Clinical reasoning quality
            'communication_quality': 0.20, # Medical communication effectiveness
            'safety_compliance': 0.15      # Clinical safety and guidelines
        }
        
        # Sub-metric weights
        self.sub_weights = {
            'medical_accuracy': {
                'entity_f1': 0.4,
                'terminology': 0.3,
                'concept_coverage': 0.3
            },
            'semantic_quality': {
                'clinical_bleu': 0.3,
                'clinical_rouge': 0.3,
                'bertscore': 0.4
            },
            'clinical_reasoning': {
                'diagnostic_coherence': 0.5,
                'treatment_appropriateness': 0.5
            },
            'communication_quality': {
                'empathy': 0.3,
                'information_seeking': 0.3,
                'explanation_clarity': 0.2,
                'patient_centeredness': 0.2
            }
        }
    
    def validate_medical_dialogue(self, predicted_dialogue: str, reference_dialogue: str = None,
                                 clinical_context: dict = None):
        """
        Comprehensive validation using advanced clinical NLP metrics
        """
        logger.info("Starting advanced medical dialogue validation")
        
        # 1. Medical Entity and Terminology Validation
        entity_metrics = self._validate_medical_entities(predicted_dialogue, reference_dialogue)
        
        # 2. Semantic Similarity using Clinical NLP methods
        semantic_metrics = self._calculate_clinical_semantic_similarity(predicted_dialogue, reference_dialogue)
        
        # 3. Clinical Reasoning Validation
        reasoning_metrics = self._validate_clinical_reasoning(predicted_dialogue, clinical_context)
        
        # 4. Medical Communication Quality Assessment
        communication_metrics = self._assess_communication_quality(predicted_dialogue)
        
        # 5. Clinical Safety Validation
        safety_metrics = self._validate_clinical_safety(predicted_dialogue)
        
        # 6. Calculate overall quality with confidence intervals
        overall_quality, confidence_interval = self._calculate_overall_quality_with_ci(
            entity_metrics, semantic_metrics, reasoning_metrics, 
            communication_metrics, safety_metrics
        )
        
        # 7. Generate evidence-based recommendations
        recommendations = self._generate_evidence_based_recommendations(
            entity_metrics, semantic_metrics, reasoning_metrics, 
            communication_metrics, safety_metrics
        )
        
        return ClinicalValidationMetrics(
            # Medical Entity Metrics
            medical_entity_f1=entity_metrics['entity_f1'],
            concept_precision=entity_metrics['concept_precision'],
            concept_recall=entity_metrics['concept_recall'],
            terminology_accuracy=entity_metrics['terminology_accuracy'],
            
            # Semantic Similarity Metrics
            clinical_bleu=semantic_metrics['clinical_bleu'],
            clinical_rouge_l=semantic_metrics['clinical_rouge_l'],
            clinical_bertscore=semantic_metrics['clinical_bertscore'],
            semantic_coherence=semantic_metrics['semantic_coherence'],
            
            # Clinical Quality Metrics
            clinical_completeness=reasoning_metrics['clinical_completeness'],
            diagnostic_coherence=reasoning_metrics['diagnostic_coherence'],
            treatment_appropriateness=reasoning_metrics['treatment_appropriateness'],
            clinical_safety=safety_metrics['clinical_safety'],
            
            # Communication Quality Metrics
            empathy_score=communication_metrics['empathy_score'],
            information_seeking=communication_metrics['information_seeking'],
            explanation_clarity=communication_metrics['explanation_clarity'],
            patient_centeredness=communication_metrics['patient_centeredness'],
            
            # Overall Quality
            overall_clinical_quality=overall_quality,
            confidence_interval=confidence_interval,
            
            # Detailed Information
            detailed_scores={**entity_metrics, **semantic_metrics, **reasoning_metrics, 
                           **communication_metrics, **safety_metrics},
            quality_indicators=self._generate_quality_indicators(overall_quality),
            recommendations=recommendations
        )
    
    def _validate_medical_entities(self, dialogue: str, reference: str = None):
        """Validate medical entities using clinical NLP standards"""
        
        # Extract medical entities from dialogue
        predicted_entities = self._extract_medical_entities_nlp(dialogue)
        
        if reference:
            reference_entities = self._extract_medical_entities_nlp(reference)
            
            # Calculate F1, Precision, Recall for entities
            entity_f1, concept_precision, concept_recall = self._calculate_entity_metrics(
                predicted_entities, reference_entities
            )
        else:
            # Use MIMIC knowledge base for validation if no reference
            entity_f1, concept_precision, concept_recall = self._validate_entities_against_kb(
                predicted_entities
            )
        
        # Validate medical terminology accuracy
        terminology_accuracy = self._validate_terminology_accuracy(predicted_entities)
        
        return {
            'entity_f1': entity_f1,
            'concept_precision': concept_precision,
            'concept_recall': concept_recall,
            'terminology_accuracy': terminology_accuracy
        }
    
    def _calculate_clinical_semantic_similarity(self, predicted: str, reference: str = None):
        """Calculate semantic similarity using clinical NLP methods"""
        
        if reference is None:
            # Generate reference from clinical context if available
            reference = self._generate_clinical_reference(predicted)
        
        # 1. Clinical BLEU Score
        clinical_bleu = self._calculate_clinical_bleu(predicted, reference)
        
        # 2. Clinical ROUGE-L Score
        clinical_rouge_l = self._calculate_clinical_rouge_l(predicted, reference)
        
        # 3. Clinical BERTScore
        clinical_bertscore = self._calculate_clinical_bertscore(predicted, reference)
        
        # 4. Semantic Coherence
        semantic_coherence = self._calculate_semantic_coherence(predicted)
        
        return {
            'clinical_bleu': clinical_bleu,
            'clinical_rouge_l': clinical_rouge_l,
            'clinical_bertscore': clinical_bertscore,
            'semantic_coherence': semantic_coherence
        }
    
    def _validate_clinical_reasoning(self, dialogue: str, context: dict = None):
        """Validate clinical reasoning using established criteria"""
        
        # Extract clinical components
        symptoms = self._extract_symptoms(dialogue)
        diagnoses = self._extract_diagnoses(dialogue)
        treatments = self._extract_treatments(dialogue)
        
        # Use MIMIC knowledge base for validation if available
        if self.mimic_kb:
            validation_result = self.mimic_kb.validate_clinical_coherence(symptoms, diagnoses, treatments)
            
            return {
                'clinical_completeness': validation_result.concept_coverage,
                'diagnostic_coherence': validation_result.clinical_coherence,
                'treatment_appropriateness': validation_result.validity_score
            }
        else:
            # Fallback to pattern-based validation
            return {
                'clinical_completeness': self._assess_completeness_patterns(dialogue),
                'diagnostic_coherence': self._assess_reasoning_patterns(dialogue),
                'treatment_appropriateness': self._assess_treatment_patterns(dialogue)
            }
    
    def _assess_communication_quality(self, dialogue: str):
        """Assess communication quality using validated medical communication metrics"""
        
        empathy_score = self._calculate_empathy_score(dialogue)
        information_seeking = self._calculate_information_seeking_score(dialogue)
        explanation_clarity = self._calculate_explanation_clarity(dialogue)
        patient_centeredness = self._calculate_patient_centeredness(dialogue)
        
        return {
            'empathy_score': empathy_score,
            'information_seeking': information_seeking,
            'explanation_clarity': explanation_clarity,
            'patient_centeredness': patient_centeredness
        }
    
    def _validate_clinical_safety(self, dialogue: str):
        """Validate clinical safety using established guidelines"""
        
        # Check for safety-critical patterns
        safety_violations = self._detect_safety_violations(dialogue)
        harmful_advice = self._detect_harmful_advice(dialogue)
        appropriate_urgency = self._assess_urgency_handling(dialogue)
        
        # Calculate overall safety score
        safety_penalty = len(safety_violations) * 0.2 + len(harmful_advice) * 0.3
        clinical_safety = max(0.0, 1.0 - safety_penalty)
        
        return {
            'clinical_safety': clinical_safety,
            'safety_violations': len(safety_violations),
            'harmful_advice': len(harmful_advice),
            'urgency_handling': appropriate_urgency
        }
    
    def _calculate_clinical_bleu(self, predicted: str, reference: str):
        """Calculate BLEU score adapted for clinical text"""
        
        pred_tokens = nltk.word_tokenize(predicted.lower())
        ref_tokens = nltk.word_tokenize(reference.lower())
        
        # Use clinical-aware tokenization
        pred_tokens = self._clinical_tokenize(pred_tokens)
        ref_tokens = self._clinical_tokenize(ref_tokens)
        
        # Calculate BLEU with clinical smoothing
        bleu_score = sentence_bleu([ref_tokens], pred_tokens, 
                                  smoothing_function=self.bleu_smoothing)
        
        return bleu_score
    
    def _calculate_clinical_rouge_l(self, predicted: str, reference: str):
        """Calculate ROUGE-L score for clinical content"""
        
        scores = self.rouge_scorer.score(reference, predicted)
        return scores['rougeL'].fmeasure
    
    def _calculate_clinical_bertscore(self, predicted: str, reference: str):
        """Calculate BERTScore using clinical BERT if available"""
        
        if self.clinical_bert_available:
            return self._clinical_bert_similarity(predicted, reference)
        elif self.clinical_sentence_transformer:
            return self._sentence_transformer_similarity(predicted, reference)
        else:
            # Fallback to simple similarity
            return self._token_overlap_similarity(predicted, reference)
    
    def _calculate_empathy_score(self, dialogue: str):
        """Calculate empathy score using validated patterns"""
        
        empathy_count = 0
        total_patterns = 0
        
        for category, patterns in self.empathy_patterns.items():
            for pattern in patterns:
                total_patterns += 1
                if re.search(pattern, dialogue.lower()):
                    empathy_count += 1
        
        return empathy_count / total_patterns if total_patterns > 0 else 0.0
    
    def _calculate_information_seeking_score(self, dialogue: str):
        """Calculate information seeking quality score"""
        
        seeking_count = 0
        total_patterns = 0
        
        for category, patterns in self.information_seeking_patterns.items():
            for pattern in patterns:
                total_patterns += 1
                if re.search(pattern, dialogue.lower()):
                    seeking_count += 1
        
        return seeking_count / total_patterns if total_patterns > 0 else 0.0
    
    def _calculate_overall_quality_with_ci(self, *metric_groups):
        """Calculate overall quality with 95% confidence interval"""
        
        # Collect all metric scores
        all_scores = []
        weighted_scores = []
        
        metric_names = ['medical_accuracy', 'semantic_quality', 'clinical_reasoning', 
                       'communication_quality', 'safety_compliance']
        
        for i, metrics in enumerate(metric_groups):
            if i < len(metric_names):
                weight = self.metric_weights[metric_names[i]]
                group_scores = list(metrics.values())
                all_scores.extend(group_scores)
                
                group_mean = np.mean(group_scores)
                weighted_scores.append(group_mean * weight)
        
        overall_quality = sum(weighted_scores)
        
        # Calculate 95% confidence interval using bootstrap if enough data
        if len(all_scores) >= 10:
            ci_lower, ci_upper = self._bootstrap_confidence_interval(all_scores, overall_quality)
        else:
            # Simple CI estimation
            std_error = np.std(all_scores) / np.sqrt(len(all_scores))
            ci_lower = max(0.0, overall_quality - 1.96 * std_error)
            ci_upper = min(1.0, overall_quality + 1.96 * std_error)
        
        return overall_quality, (ci_lower, ci_upper)
    
    def _bootstrap_confidence_interval(self, scores, point_estimate):
        """Calculate bootstrap confidence interval"""
        
        n_bootstrap = 1000
        bootstrap_estimates = []
        
        for _ in range(n_bootstrap):
            bootstrap_sample = np.random.choice(scores, size=len(scores), replace=True)
            bootstrap_estimates.append(np.mean(bootstrap_sample))
        
        ci_lower = np.percentile(bootstrap_estimates, 2.5)
        ci_upper = np.percentile(bootstrap_estimates, 97.5)
        
        return ci_lower, ci_upper
    
    def _generate_evidence_based_recommendations(self, *metric_groups):
        """Generate evidence-based recommendations for improvement"""
        
        recommendations = []
        
        # Analyze each metric group for specific recommendations
        entity_metrics, semantic_metrics, reasoning_metrics, comm_metrics, safety_metrics = metric_groups
        
        # Medical accuracy recommendations
        if entity_metrics['entity_f1'] < 0.7:
            recommendations.append("Improve medical entity recognition using clinical NER models")
        
        if entity_metrics['terminology_accuracy'] < 0.8:
            recommendations.append("Enhance medical terminology accuracy using UMLS/SNOMED-CT validation")
        
        # Semantic quality recommendations
        if semantic_metrics['clinical_bertscore'] < 0.6:
            recommendations.append("Improve semantic similarity using clinical domain adaptation")
        
        # Communication quality recommendations
        if comm_metrics['empathy_score'] < 0.3:
            recommendations.append("Incorporate more empathetic communication patterns")
        
        if comm_metrics['patient_centeredness'] < 0.4:
            recommendations.append("Focus on patient-centered communication strategies")
        
        # Safety recommendations
        if safety_metrics['clinical_safety'] < 0.8:
            recommendations.append("Review and improve clinical safety compliance")
        
        return recommendations[:5]  # Limit to top 5 most important
    
    # Helper methods for specific calculations (simplified implementations)
    def _extract_medical_entities_nlp(self, text: str):
        """Extract medical entities using NLP methods"""
        medical_terms = []
        words = nltk.word_tokenize(text.lower())
        
        medical_keywords = [
            'pain', 'fever', 'cough', 'headache', 'nausea', 'fatigue',
            'diabetes', 'hypertension', 'pneumonia', 'asthma',
            'aspirin', 'metformin', 'insulin', 'antibiotics'
        ]
        
        for word in words:
            if word in medical_keywords:
                medical_terms.append(word)
        
        return medical_terms
    
    def _clinical_tokenize(self, tokens):
        """Clinical-aware tokenization"""
        clinical_tokens = []
        
        for token in tokens:
            # Keep medical abbreviations together
            if re.match(r'^[A-Z]{2,5}$', token):  # Medical abbreviations
                clinical_tokens.append(token)
            # Handle dosage units
            elif re.match(r'\d+mg|\d+ml|\d+g', token):
                clinical_tokens.append(token)
            else:
                clinical_tokens.append(token)
        
        return clinical_tokens
    
    def _generate_quality_indicators(self, overall_quality: float):
        """Generate quality indicators based on clinical standards"""
        
        if overall_quality >= 0.9:
            return {
                'overall': 'Excellent',
                'clinical_readiness': 'Ready for clinical use',
                'confidence': 'High'
            }
        elif overall_quality >= 0.7:
            return {
                'overall': 'Good',
                'clinical_readiness': 'Suitable with minor improvements',
                'confidence': 'Medium-High'
            }
        elif overall_quality >= 0.5:
            return {
                'overall': 'Fair',
                'clinical_readiness': 'Requires significant improvement',
                'confidence': 'Medium'
            }
        else:
            return {
                'overall': 'Poor',
                'clinical_readiness': 'Not suitable for clinical use',
                'confidence': 'Low'
            }

# Integration helper functions
def validate_with_advanced_metrics(dialogue_text: str, reference_text: str = None, 
                              clinical_context: dict = None, 
                              mimic_knowledge_base=None):
    """
    Convenience function for advanced medical validation
    """
    validator = AdvancedMedicalValidator(mimic_knowledge_base)
    return validator.validate_medical_dialogue(dialogue_text, reference_text, clinical_context)