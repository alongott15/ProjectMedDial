#!/usr/bin/env python3
"""
Keyword-based STS Evaluator (no embeddings required).

This provides component-wise analysis and profile-type awareness
without needing to download embedding models.
"""

import logging
import re
from typing import Dict, List, Set, Tuple
from collections import Counter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KeywordBasedSTSEvaluator:
    """
    STS evaluator using keyword matching and text analysis.
    Works without embedding models - uses lexical and semantic overlap.
    """

    # Medical term keywords for component extraction
    SYMPTOM_KEYWORDS = {
        'pain', 'chest pain', 'ache', 'nausea', 'vomiting', 'fatigue', 'tired', 'weakness',
        'dyspnea', 'shortness of breath', 'sob', 'breathing', 'cough', 'fever', 'chills',
        'dizziness', 'lightheaded', 'syncope', 'faint', 'sweat', 'sweating', 'diaphoresis',
        'palpitations', 'discomfort', 'pressure', 'tightness', 'cramping', 'burning',
        'radiating', 'radiation', 'headache', 'confusion', 'numbness', 'tingling',
        'swelling', 'edema', 'rash', 'itching', 'diarrhea', 'constipation', 'bleeding',
        'discharge', 'urinary', 'frequency', 'urgency', 'difficulty', 'appetite loss',
        'epigastric', 'substernal', 'exertion', 'activity', 'rest'
    }

    DIAGNOSIS_KEYWORDS = {
        'diagnosis', 'diagnosed', 'condition', 'disease', 'syndrome', 'disorder',
        'myocardial infarction', 'stemi', 'nstemi', 'mi', 'heart attack', 'stroke',
        'pneumonia', 'copd', 'asthma', 'diabetes', 'hypertension', 'infection',
        'fracture', 'blockage', 'heart block', 'complete heart block', 'arrhythmia',
        'failure', 'insufficiency', 'ischemia', 'infarction', 'embolism', 'thrombosis',
        'angina', 'coronary artery disease', 'cad', 'chf', 'congestive heart failure',
        'acute coronary syndrome', 'acs', 'st-elevation', 'non-q wave',
        'cardiac', 'cardiomyopathy', 'ischemic cardiomyopathy'
    }

    TREATMENT_KEYWORDS = {
        'treatment', 'treated', 'therapy', 'medication', 'medicine', 'prescribed', 'prescription',
        'aspirin', 'clopidogrel', 'plavix', 'statin', 'lipitor', 'beta blocker', 'metoprolol',
        'coreg', 'ace inhibitor', 'altace', 'antibiotic', 'anticoagulant', 'heparin',
        'warfarin', 'insulin', 'metformin', 'surgery', 'procedure', 'operation',
        'catheterization', 'cath', 'cardiac catheterization', 'angioplasty', 'stent',
        'cypher stent', 'bypass', 'cabg', 'pci', 'intubation', 'ventilation', 'oxygen',
        'iv', 'intravenous', 'infusion', 'drip', 'bolus', 'dose', 'administration',
        'antiplatelet', 'dual antiplatelet', 'thrombolytic', 'nitrate', 'nitroglycerin',
        'isordil', 'morphine', 'atropine', 'epinephrine', 'intervention',
        'revascularization', 'balloon pump', 'intra-aortic balloon', 'pantoprazole',
        'nexium', 'creon', 'hydrochlorothiazide', 'folic acid'
    }

    FINDING_KEYWORDS = {
        'ekg', 'ecg', 'electrocardiogram', 'st elevation', 'st depression', 'st-elevation',
        'q wave', 'blood pressure', 'bp', 'hypotensive', 'hypertensive', 'heart rate',
        'hr', 'bradycardia', 'tachycardia', 'bradycardic', 'tachycardic', 'pulse',
        'oxygen saturation', 'spo2', 'respiratory rate', 'temperature', 'labs',
        'laboratory', 'troponin', 'cardiac enzymes', 'creatinine', 'bun', 'glucose',
        'white blood cell', 'wbc', 'hemoglobin', 'hematocrit', 'platelet', 'inr',
        'x-ray', 'ct scan', 'mri', 'ultrasound', 'echo', 'echocardiogram',
        'catheterization findings', 'angiogram', 'stenosis', 'occlusion', 'lesion',
        'ejection fraction', 'lvef', 'vital signs', 'normalized', 'stabilized',
        'mm st elevation', 'mm st depression', 'lad', 'rca', 'left circumflex',
        'right coronary artery', 'left anterior descending', 'om1', 'om2',
        'mid-lad', 'distal lad', 'multivessel', 'multi-vessel'
    }

    HISTORY_KEYWORDS = {
        'history', 'past medical history', 'pmh', 'previous', 'prior', 'chronic',
        'known', 'diagnosed with', 'hypertension', 'diabetes', 'hyperlipidemia',
        'smoking', 'smoker', 'tobacco', 'alcohol', 'family history', 'medication',
        'taking', 'allergy', 'allergic', 'gerd', 'reflux', 'surgery', 'procedure',
        'billroth', 'hysterectomy', 'appendectomy', 'anemia', 'no known drug allergies'
    }

    PROFILE_TYPE_COMPONENTS = {
        'FULL': ['symptoms', 'diagnosis', 'treatment', 'findings', 'history'],
        'NO_DIAGNOSIS': ['symptoms', 'treatment', 'findings', 'history'],
        'NO_DIAGNOSIS_NO_TREATMENT': ['symptoms', 'findings', 'history']
    }

    def __init__(self):
        """Initialize keyword-based evaluator."""
        logger.info("KeywordBasedSTSEvaluator initialized (no embeddings)")

    def extract_keywords(self, text: str, keyword_set: Set[str]) -> Set[str]:
        """Extract keywords from text."""
        text_lower = text.lower()
        found = set()

        # Sort by length (longest first) to match multi-word phrases first
        for keyword in sorted(keyword_set, key=len, reverse=True):
            if ' ' in keyword:  # Multi-word phrase
                if keyword in text_lower:
                    found.add(keyword)
                    # Remove matched phrase to avoid partial re-matches
                    text_lower = text_lower.replace(keyword, ' ')
            else:  # Single word
                if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
                    found.add(keyword)

        return found

    def extract_component_facts(self, text: str, component_type: str) -> Set[str]:
        """Extract facts for a specific component."""
        keyword_map = {
            'symptoms': self.SYMPTOM_KEYWORDS,
            'diagnosis': self.DIAGNOSIS_KEYWORDS,
            'treatment': self.TREATMENT_KEYWORDS,
            'findings': self.FINDING_KEYWORDS,
            'history': self.HISTORY_KEYWORDS
        }

        keyword_set = keyword_map.get(component_type, set())
        return self.extract_keywords(text, keyword_set)

    def compute_lexical_similarity(self, text1: str, text2: str) -> float:
        """
        Compute lexical similarity using word overlap (Jaccard similarity).
        """
        # Tokenize and normalize
        words1 = set(re.findall(r'\b\w+\b', text1.lower()))
        words2 = set(re.findall(r'\b\w+\b', text2.lower()))

        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'is', 'are', 'was', 'were',
                      'been', 'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                      'would', 'could', 'should', 'may', 'might', 'can', 'to', 'of', 'in',
                      'on', 'at', 'by', 'for', 'with', 'from', 'as', 'that', 'this'}

        words1 = words1 - stop_words
        words2 = words2 - stop_words

        # Compute Jaccard similarity
        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def compute_component_similarity(self, ehr_facts: Set[str], dialogue_facts: Set[str]) -> Dict:
        """Compute precision, recall, F1 for a component."""
        if not ehr_facts and not dialogue_facts:
            return {'precision': 1.0, 'recall': 1.0, 'f1': 1.0, 'overlap': 0}

        if not ehr_facts:
            return {'precision': 0.0, 'recall': 1.0, 'f1': 0.0, 'overlap': 0}

        overlap = len(ehr_facts & dialogue_facts)
        precision = overlap / len(dialogue_facts) if dialogue_facts else 0.0
        recall = overlap / len(ehr_facts) if ehr_facts else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        return {
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'overlap': overlap
        }

    def compute_improved_sts(self, ehr_summary: str, dialogue_summary: str,
                            profile_type: str = 'FULL') -> Dict:
        """
        Compute improved STS with component analysis.
        """
        logger.info(f"Computing keyword-based STS for profile type: {profile_type}")

        # 1. Compute baseline lexical similarity
        lexical_sim = self.compute_lexical_similarity(ehr_summary, dialogue_summary)
        logger.info(f"  Lexical similarity: {lexical_sim:.3f}")

        # 2. Extract component facts
        component_analysis = {}
        for component in ['symptoms', 'diagnosis', 'treatment', 'findings', 'history']:
            ehr_facts = self.extract_component_facts(ehr_summary, component)
            dialogue_facts = self.extract_component_facts(dialogue_summary, component)

            similarity = self.compute_component_similarity(ehr_facts, dialogue_facts)

            component_analysis[component] = {
                'ehr_facts_count': len(ehr_facts),
                'dialogue_facts_count': len(dialogue_facts),
                'overlap_count': similarity['overlap'],
                'recall': similarity['recall'],
                'precision': similarity['precision'],
                'f1': similarity['f1']
            }

            logger.info(f"  {component}: Recall={similarity['recall']:.2f}, "
                       f"EHR={len(ehr_facts)}, Dialogue={len(dialogue_facts)}, "
                       f"Overlap={similarity['overlap']}")

        # 3. Compute profile-aware score
        expected_components = self.PROFILE_TYPE_COMPONENTS.get(profile_type,
                                                               self.PROFILE_TYPE_COMPONENTS['FULL'])

        component_weights = {
            'symptoms': 0.35,
            'diagnosis': 0.25,
            'treatment': 0.20,
            'findings': 0.15,
            'history': 0.05
        }

        weighted_score = 0.0
        total_weight = 0.0
        missing_components = []

        for component in expected_components:
            weight = component_weights[component]
            recall = component_analysis[component]['recall']

            weighted_score += weight * recall
            total_weight += weight

            if recall < 0.3:
                missing_components.append({
                    'component': component,
                    'recall': recall,
                    'ehr_facts': component_analysis[component]['ehr_facts_count'],
                    'captured': component_analysis[component]['overlap_count']
                })

        profile_aware_score = weighted_score / total_weight if total_weight > 0 else 0.0

        # 4. Information retention
        total_expected = sum(component_analysis[c]['ehr_facts_count'] for c in expected_components)
        total_captured = sum(component_analysis[c]['overlap_count'] for c in expected_components)
        info_retention = total_captured / total_expected if total_expected > 0 else 0.0

        # 5. Overall score (blend lexical + component-based)
        overall_score = 0.3 * lexical_sim + 0.7 * profile_aware_score

        logger.info(f"  Profile-aware score: {profile_aware_score:.3f}")
        logger.info(f"  Information retention: {info_retention:.3f}")
        logger.info(f"  Overall score: {overall_score:.3f}")

        return {
            'overall_score': round(overall_score, 4),
            'lexical_similarity': round(lexical_sim, 4),
            'profile_aware_score': round(profile_aware_score, 4),
            'information_retention': round(info_retention, 4),
            'profile_type': profile_type,
            'expected_components': expected_components,
            'components': component_analysis,
            'missing_components': missing_components,
            'total_expected_facts': total_expected,
            'total_captured_facts': total_captured,
            'coverage_percentage': round(info_retention * 100, 1)
        }

    def compute_sts(self, ehr_summary: str, dialogue_summary: str,
                   profile_type: str = 'FULL') -> float:
        """Return overall score only."""
        result = self.compute_improved_sts(ehr_summary, dialogue_summary, profile_type)
        return result['overall_score']

    def compute_sts_detailed(self, ehr_summary: str, dialogue_summary: str,
                            profile_type: str = 'FULL') -> Dict:
        """Alias for compatibility."""
        return self.compute_improved_sts(ehr_summary, dialogue_summary, profile_type)


if __name__ == '__main__':
    logger.info("Testing KeywordBasedSTSEvaluator...")

    ehr = """The patient is a 75-year-old male presenting with chest pain.
    He experienced nausea, fatigue, and substernal chest pain lasting 15–30 minutes.
    On EMS arrival, he was hypotensive (SBP 50s), bradycardic (HR 20–30) in complete heart block.
    EKG showed 3–4 mm ST elevation. The documented diagnosis was ST-elevation myocardial
    infarction (STEMI) with complete heart block. He underwent cardiac catheterization and
    placement of a Cypher stent to the RCA. Treatment included dual antiplatelet therapy
    (aspirin and clopidogrel), heparin infusion."""

    dialogue = """The patient presented with chest pain. The pain is in the middle of the chest,
    rated 6 out of 10. Associated symptoms include nausea, sweating, and fatigue with activity.
    The doctor noted chest discomfort, nausea, and sweating raise concern for cardiac causes.
    The doctor recommended evaluation with an EKG and blood tests."""

    evaluator = KeywordBasedSTSEvaluator()

    print("\n" + "="*80)
    print("FULL Profile")
    print("="*80)
    result = evaluator.compute_improved_sts(ehr, dialogue, 'FULL')
    print(f"Overall: {result['overall_score']:.3f}")
    print(f"Info Retention: {result['information_retention']:.3f}")
    print(f"Missing: {[c['component'] for c in result['missing_components']]}")

    print("\n" + "="*80)
    print("NO_DIAGNOSIS Profile")
    print("="*80)
    result = evaluator.compute_improved_sts(ehr, dialogue, 'NO_DIAGNOSIS')
    print(f"Overall: {result['overall_score']:.3f}")
    print(f"Info Retention: {result['information_retention']:.3f}")

    print("\n✅ Test complete!")
