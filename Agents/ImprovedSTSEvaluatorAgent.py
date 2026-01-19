#!/usr/bin/env python3
"""
Improved STS Evaluator with component-wise analysis and profile-type awareness.

This addresses the issue of artificially inflated STS scores by:
1. Breaking down similarity into components (symptoms, diagnosis, treatment, etc.)
2. Adjusting expectations based on profile type
3. Computing information retention metrics
"""

import logging
import re
from typing import Dict, List, Set, Tuple
from Agents.STSEvaluatorAgent import STSEvaluatorAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImprovedSTSEvaluatorAgent:
    """
    Enhanced STS evaluator that provides component-wise analysis and
    profile-type-aware scoring.
    """

    # Medical term keywords for component extraction
    SYMPTOM_KEYWORDS = {
        'pain', 'chest pain', 'ache', 'nausea', 'vomiting', 'fatigue', 'tired', 'weakness',
        'dyspnea', 'shortness of breath', 'sob', 'breathing', 'cough', 'fever', 'chills',
        'dizziness', 'lightheaded', 'syncope', 'faint', 'sweat', 'sweating', 'diaphoresis',
        'palpitations', 'discomfort', 'pressure', 'tightness', 'cramping', 'burning',
        'radiating', 'radiation', 'headache', 'confusion', 'numbness', 'tingling',
        'swelling', 'edema', 'rash', 'itching', 'diarrhea', 'constipation', 'bleeding',
        'discharge', 'urinary', 'frequency', 'urgency', 'difficulty', 'appetite loss'
    }

    DIAGNOSIS_KEYWORDS = {
        'diagnosis', 'diagnosed', 'condition', 'disease', 'syndrome', 'disorder',
        'myocardial infarction', 'stemi', 'nstemi', 'mi', 'heart attack', 'stroke',
        'pneumonia', 'copd', 'asthma', 'diabetes', 'hypertension', 'infection',
        'fracture', 'blockage', 'heart block', 'arrhythmia', 'failure', 'insufficiency',
        'ischemia', 'infarction', 'embolism', 'thrombosis', 'angina', 'coronary artery disease',
        'cad', 'chf', 'congestive heart failure', 'acute coronary syndrome', 'acs'
    }

    TREATMENT_KEYWORDS = {
        'treatment', 'treated', 'therapy', 'medication', 'medicine', 'prescribed', 'prescription',
        'aspirin', 'clopidogrel', 'plavix', 'statin', 'beta blocker', 'ace inhibitor',
        'antibiotic', 'anticoagulant', 'heparin', 'warfarin', 'insulin', 'metformin',
        'surgery', 'procedure', 'operation', 'catheterization', 'cath', 'angioplasty',
        'stent', 'bypass', 'cabg', 'pci', 'intubation', 'ventilation', 'oxygen',
        'iv', 'intravenous', 'infusion', 'drip', 'bolus', 'dose', 'administration',
        'antiplatelet', 'thrombolytic', 'nitrate', 'nitroglycerin', 'morphine',
        'atropine', 'epinephrine', 'intervention', 'revascularization'
    }

    FINDING_KEYWORDS = {
        'ekg', 'ecg', 'electrocardiogram', 'st elevation', 'st depression', 'q wave',
        'blood pressure', 'bp', 'hypotensive', 'hypertensive', 'heart rate', 'hr',
        'bradycardia', 'tachycardia', 'bradycardic', 'tachycardic', 'pulse', 'oxygen saturation',
        'spo2', 'respiratory rate', 'temperature', 'labs', 'laboratory', 'troponin',
        'cardiac enzymes', 'creatinine', 'bun', 'glucose', 'white blood cell', 'wbc',
        'hemoglobin', 'hematocrit', 'platelet', 'inr', 'x-ray', 'ct scan', 'mri',
        'ultrasound', 'echo', 'echocardiogram', 'catheterization findings', 'angiogram',
        'stenosis', 'occlusion', 'lesion', 'ejection fraction', 'lvef'
    }

    HISTORY_KEYWORDS = {
        'history', 'past medical history', 'pmh', 'previous', 'prior', 'chronic',
        'known', 'diagnosed with', 'hypertension', 'diabetes', 'hyperlipidemia',
        'smoking', 'smoker', 'tobacco', 'alcohol', 'family history', 'medication',
        'taking', 'allergy', 'allergic', 'gerd', 'reflux', 'surgery', 'procedure'
    }

    # Profile type expectations
    PROFILE_TYPE_COMPONENTS = {
        'FULL': ['symptoms', 'diagnosis', 'treatment', 'findings', 'history'],
        'NO_DIAGNOSIS': ['symptoms', 'treatment', 'findings', 'history'],
        'NO_DIAGNOSIS_NO_TREATMENT': ['symptoms', 'findings', 'history']
    }

    def __init__(self, model_name: str = 'medical'):
        """
        Initialize improved STS evaluator.

        Args:
            model_name: Embedding model to use ('general', 'medical', etc.)
        """
        self.base_evaluator = STSEvaluatorAgent(model_name=model_name)
        logger.info("ImprovedSTSEvaluatorAgent initialized")

    def extract_component_facts(self, text: str, component_type: str) -> Set[str]:
        """
        Extract facts/keywords for a specific component from text.

        Args:
            text: Text to analyze
            component_type: 'symptoms', 'diagnosis', 'treatment', 'findings', or 'history'

        Returns:
            Set of found keywords/phrases
        """
        text_lower = text.lower()
        found_facts = set()

        # Get appropriate keyword set
        keyword_set_map = {
            'symptoms': self.SYMPTOM_KEYWORDS,
            'diagnosis': self.DIAGNOSIS_KEYWORDS,
            'treatment': self.TREATMENT_KEYWORDS,
            'findings': self.FINDING_KEYWORDS,
            'history': self.HISTORY_KEYWORDS
        }

        keyword_set = keyword_set_map.get(component_type, set())

        # Check for multi-word phrases first (more specific)
        for keyword in sorted(keyword_set, key=lambda x: len(x), reverse=True):
            if ' ' in keyword:  # Multi-word phrase
                if keyword in text_lower:
                    found_facts.add(keyword)
            else:  # Single word
                # Use word boundaries for single words to avoid partial matches
                if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
                    found_facts.add(keyword)

        return found_facts

    def compute_component_similarity(self, ehr_facts: Set[str], dialogue_facts: Set[str]) -> Dict[str, float]:
        """
        Compute similarity metrics for a component.

        Args:
            ehr_facts: Facts extracted from EHR summary
            dialogue_facts: Facts extracted from dialogue summary

        Returns:
            Dict with precision, recall, and f1 scores
        """
        if not ehr_facts:
            return {'precision': 1.0, 'recall': 1.0, 'f1': 1.0, 'overlap': 0}

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
        Compute improved STS with component analysis and profile-type awareness.

        Args:
            ehr_summary: EHR summary text
            dialogue_summary: Dialogue summary text
            profile_type: 'FULL', 'NO_DIAGNOSIS', or 'NO_DIAGNOSIS_NO_TREATMENT'

        Returns:
            Dict with comprehensive STS analysis including:
            - overall_score: Profile-aware adjusted score
            - original_sts: Original cosine similarity score
            - components: Component-wise scores
            - information_retention: Percentage of expected info captured
            - missing_components: What's missing from dialogue
        """
        logger.info(f"Computing improved STS for profile type: {profile_type}")

        # 1. Get original embedding-based STS
        original_sts = self.base_evaluator.compute_sts(ehr_summary, dialogue_summary)
        logger.info(f"  Original STS (cosine similarity): {original_sts:.3f}")

        # 2. Extract component facts from both summaries
        component_analysis = {}
        for component in ['symptoms', 'diagnosis', 'treatment', 'findings', 'history']:
            ehr_facts = self.extract_component_facts(ehr_summary, component)
            dialogue_facts = self.extract_component_facts(dialogue_summary, component)

            similarity = self.compute_component_similarity(ehr_facts, dialogue_facts)

            component_analysis[component] = {
                'ehr_facts_count': len(ehr_facts),
                'dialogue_facts_count': len(dialogue_facts),
                'overlap_count': similarity['overlap'],
                'recall': similarity['recall'],  # What fraction of EHR info is in dialogue
                'precision': similarity['precision'],  # What fraction of dialogue info is from EHR
                'f1': similarity['f1']
            }

            logger.info(f"  {component}: Recall={similarity['recall']:.2f}, "
                       f"EHR facts={len(ehr_facts)}, Dialogue facts={len(dialogue_facts)}, "
                       f"Overlap={similarity['overlap']}")

        # 3. Compute profile-type-aware score
        expected_components = self.PROFILE_TYPE_COMPONENTS.get(profile_type, self.PROFILE_TYPE_COMPONENTS['FULL'])

        # Calculate weighted score based on component importance
        component_weights = {
            'symptoms': 0.35,      # Most important - always expected
            'diagnosis': 0.25,     # Important for FULL profile
            'treatment': 0.20,     # Important for FULL and NO_DIAGNOSIS
            'findings': 0.15,      # Moderate importance
            'history': 0.05        # Least important (often not discussed)
        }

        weighted_score = 0.0
        total_weight = 0.0
        missing_components = []

        for component in expected_components:
            weight = component_weights[component]
            recall = component_analysis[component]['recall']

            weighted_score += weight * recall
            total_weight += weight

            # Identify missing components (low recall)
            if recall < 0.3:
                missing_components.append({
                    'component': component,
                    'recall': recall,
                    'ehr_facts': component_analysis[component]['ehr_facts_count'],
                    'captured': component_analysis[component]['overlap_count']
                })

        # Normalize weighted score
        profile_aware_score = weighted_score / total_weight if total_weight > 0 else 0.0

        # 4. Compute information retention percentage
        total_expected_facts = sum(component_analysis[c]['ehr_facts_count'] for c in expected_components)
        total_captured_facts = sum(component_analysis[c]['overlap_count'] for c in expected_components)
        information_retention = total_captured_facts / total_expected_facts if total_expected_facts > 0 else 0.0

        # 5. Compute hybrid score (blend original STS with profile-aware score)
        # 40% original embedding similarity + 60% component-based score
        overall_score = 0.4 * original_sts + 0.6 * profile_aware_score

        logger.info(f"  Profile-aware score: {profile_aware_score:.3f}")
        logger.info(f"  Information retention: {information_retention:.3f}")
        logger.info(f"  Overall hybrid score: {overall_score:.3f}")

        return {
            'overall_score': round(overall_score, 4),
            'original_sts': round(original_sts, 4),
            'profile_aware_score': round(profile_aware_score, 4),
            'information_retention': round(information_retention, 4),
            'profile_type': profile_type,
            'expected_components': expected_components,
            'components': component_analysis,
            'missing_components': missing_components,
            'total_expected_facts': total_expected_facts,
            'total_captured_facts': total_captured_facts,
            'coverage_percentage': round(information_retention * 100, 1)
        }

    def compute_sts_detailed(self, ehr_summary: str, dialogue_summary: str,
                            profile_type: str = 'FULL') -> Dict:
        """
        Alias for compute_improved_sts to maintain API compatibility.
        """
        return self.compute_improved_sts(ehr_summary, dialogue_summary, profile_type)

    def compute_sts(self, ehr_summary: str, dialogue_summary: str,
                   profile_type: str = 'FULL') -> float:
        """
        Compute STS score (returns overall_score only).

        Args:
            ehr_summary: EHR summary text
            dialogue_summary: Dialogue summary text
            profile_type: Profile type for adjusted scoring

        Returns:
            Overall STS score (float)
        """
        result = self.compute_improved_sts(ehr_summary, dialogue_summary, profile_type)
        return result['overall_score']


if __name__ == '__main__':
    # Test the improved evaluator
    import sys

    logger.info("Testing ImprovedSTSEvaluatorAgent...")

    # Example test case
    ehr_summary = """The patient is a 75-year-old male presenting with chest pain.
    He experienced nausea, fatigue, epigastric discomfort, and substernal chest pain
    lasting 15–30 minutes. On EMS arrival, he was found to be hypotensive (SBP in the 50s),
    bradycardic (HR 20–30) in complete heart block. EKG showed 3–4 mm ST elevation.
    The documented diagnosis was ST-elevation myocardial infarction (STEMI) with complete
    heart block. He underwent cardiac catheterization and placement of a stent to the RCA.
    Treatment included dual antiplatelet therapy (aspirin and clopidogrel), heparin infusion."""

    dialogue_summary = """The patient presented with chest pain as the chief complaint.
    The pain is located in the middle of the chest, rated 6 out of 10 in severity.
    Associated symptoms include nausea, sweating, fatigue with activity, and one episode
    of near-fainting with low blood pressure. The doctor noted that the combination of
    chest discomfort, nausea, sweating, fatigue, and near-syncope raises concern for
    possible cardiac causes. The doctor recommended further evaluation with an EKG and
    blood tests to rule out heart-related causes."""

    evaluator = ImprovedSTSEvaluatorAgent()

    print("\n" + "="*80)
    print("Testing FULL Profile Type")
    print("="*80)
    result_full = evaluator.compute_improved_sts(ehr_summary, dialogue_summary, 'FULL')
    print(f"\nOriginal STS: {result_full['original_sts']:.3f}")
    print(f"Improved STS: {result_full['overall_score']:.3f}")
    print(f"Information Retention: {result_full['information_retention']:.3f}")
    print(f"Missing components: {len(result_full['missing_components'])}")

    print("\n" + "="*80)
    print("Testing NO_DIAGNOSIS Profile Type")
    print("="*80)
    result_no_diag = evaluator.compute_improved_sts(ehr_summary, dialogue_summary, 'NO_DIAGNOSIS')
    print(f"\nOriginal STS: {result_no_diag['original_sts']:.3f}")
    print(f"Improved STS: {result_no_diag['overall_score']:.3f}")
    print(f"Information Retention: {result_no_diag['information_retention']:.3f}")

    print("\n✅ Test complete!")
