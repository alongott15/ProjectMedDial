"""
Light case filtering for MIMIC-III EHR data.

This module filters clinical cases to include only light, common medical conditions
and exclude severe, ICU-level, or life-threatening cases.
"""

import re
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class LightCaseFilter:
    """Filters EHR cases to include only light, common medical conditions."""

    # Common light symptoms/conditions to INCLUDE
    INCLUDE_TERMS = [
        # Respiratory
        r'\bcough\b', r'\bsore throat\b', r'\bthroat pain\b',
        r'\brunny nose\b', r'\bnasal congestion\b', r'\bstuff[y|ied] nose\b',
        r'\bsneezing\b', r'\bcongestion\b',

        # Fever/General
        r'\bfever\b', r'\blow.?grade fever\b', r'\bchills\b',
        r'\bmalaise\b', r'\bfatigue\b', r'\btired\b',

        # Head/Throat
        r'\bheadache\b', r'\bmild dizziness\b',

        # Flu/Cold
        r'\bflu.?like\b', r'\bcold symptoms\b', r'\bupper respiratory\b',
        r'\buri\b',  # Upper Respiratory Infection

        # Minor GI (optional)
        r'\bmild nausea\b', r'\bminor stomach\b',
    ]

    # Severe conditions/contexts to EXCLUDE
    EXCLUDE_TERMS = [
        # ICU/Critical
        r'\bicu\b', r'\bintubat(ed|ion)\b', r'\bmechanical ventilation\b',
        r'\bventilator\b', r'\bcardiac arrest\b', r'\bshock\b',
        r'\bresuscitation\b', r'\bcode blue\b',

        # Severe infections/sepsis
        r'\bsepsis\b', r'\bseptic\b', r'\bmulti.?organ failure\b',
        r'\bsevere sepsis\b',

        # Life-threatening
        r'\bmalignancy\b', r'\bcancer\b', r'\btumor\b',
        r'\bstroke\b', r'\bmyocardial infarction\b', r'\bmi\b',
        r'\bpulmonary embolism\b', r'\bpe\b',

        # Severe respiratory
        r'\brespiratory failure\b', r'\brespiratory distress\b',
        r'\bards\b',  # Acute Respiratory Distress Syndrome

        # Major procedures
        r'\bsurgery\b', r'\bsurgical\b', r'\boperation\b',
        r'\bpost.?op\b', r'\btransplant\b',

        # Severe conditions
        r'\brenal failure\b', r'\bheart failure\b', r'\bliver failure\b',
        r'\btrauma\b', r'\binjury\b', r'\bfracture\b',
    ]

    def __init__(self, case_insensitive: bool = True):
        """
        Initialize the light case filter.

        Args:
            case_insensitive: Whether to perform case-insensitive matching.
        """
        self.case_insensitive = case_insensitive
        flags = re.IGNORECASE if case_insensitive else 0

        self.include_patterns = [re.compile(term, flags) for term in self.INCLUDE_TERMS]
        self.exclude_patterns = [re.compile(term, flags) for term in self.EXCLUDE_TERMS]

    def filter_case(self, text: str, chief_complaint: Optional[str] = None) -> Tuple[bool, str]:
        """
        Filter a clinical case to determine if it's a light, common condition.

        Args:
            text: Main clinical note text (e.g., discharge summary).
            chief_complaint: Optional chief complaint text to prioritize.

        Returns:
            Tuple of (passed: bool, reason: str)
                - passed: True if case passes light-case filter
                - reason: Explanation of filter decision
        """
        if not text:
            return False, "Empty clinical text"

        # Combine text sources, prioritize chief complaint
        combined_text = f"{chief_complaint or ''}\n{text}"

        # First check for exclusions (severe/ICU cases)
        for pattern in self.exclude_patterns:
            match = pattern.search(combined_text)
            if match:
                return False, f"Excluded: contains severe/ICU term '{match.group()}'"

        # Then check for inclusions (light symptoms)
        matched_terms = []
        for pattern in self.include_patterns:
            match = pattern.search(combined_text)
            if match:
                matched_terms.append(match.group())

        if matched_terms:
            # Prefer chief complaint matches for the reason
            if chief_complaint:
                chief_matches = []
                for pattern in self.include_patterns:
                    match = pattern.search(chief_complaint)
                    if match:
                        chief_matches.append(match.group())

                if chief_matches:
                    terms_str = ', '.join(chief_matches[:3])
                    return True, f"Chief complaint contains: {terms_str}"

            # Fall back to general text matches
            terms_str = ', '.join(matched_terms[:3])
            return True, f"Clinical text contains: {terms_str}"

        return False, "No light/common symptoms found"

    def filter_batch(self, cases: list[Dict]) -> Tuple[list[Dict], Dict]:
        """
        Filter a batch of clinical cases.

        Args:
            cases: List of case dictionaries with 'text' and optional 'chief_complaint' fields.

        Returns:
            Tuple of (filtered_cases: list, stats: dict)
                - filtered_cases: Cases that passed the filter
                - stats: Statistics about filtering
        """
        filtered = []
        stats = {
            'total': len(cases),
            'passed': 0,
            'excluded_severe': 0,
            'excluded_no_symptoms': 0,
            'pass_rate': 0.0
        }

        for case in cases:
            text = case.get('text', '')
            chief_complaint = case.get('chief_complaint')

            passed, reason = self.filter_case(text, chief_complaint)

            if passed:
                case['light_case_filter'] = {
                    'passed': True,
                    'reason': reason
                }
                filtered.append(case)
                stats['passed'] += 1
            else:
                if 'severe' in reason.lower() or 'icu' in reason.lower():
                    stats['excluded_severe'] += 1
                else:
                    stats['excluded_no_symptoms'] += 1

                logger.debug(f"Case {case.get('hadm_id', 'unknown')} filtered: {reason}")

        stats['pass_rate'] = stats['passed'] / stats['total'] if stats['total'] > 0 else 0.0

        logger.info(f"Light case filtering: {stats['passed']}/{stats['total']} passed "
                   f"({stats['pass_rate']:.1%})")

        return filtered, stats


def create_light_case_filter() -> LightCaseFilter:
    """Create a default light case filter instance."""
    return LightCaseFilter(case_insensitive=True)
