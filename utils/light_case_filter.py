"""Light Case Filter - Filters for common, non-severe medical cases"""
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class LightCaseFilter:
    """Filters EHR cases to include only light, common medical complaints"""

    def __init__(self, include_terms: List[str], exclude_terms: List[str]):
        self.include_terms = [term.lower() for term in include_terms]
        self.exclude_terms = [term.lower() for term in exclude_terms]

    def filter_case(self, text: str, chief_complaint: str = "") -> Dict:
        """
        Filter a single case to determine if it meets light case criteria

        Returns dict with 'passed' (bool) and 'reason' (str)
        """
        text_lower = text.lower()
        complaint_lower = chief_complaint.lower()
        combined_text = f"{text_lower} {complaint_lower}"

        # Check for exclusion terms first (severe/ICU cases)
        for exclude_term in self.exclude_terms:
            if exclude_term in combined_text:
                return {
                    "passed": False,
                    "reason": f"Contains severe/exclusion term: '{exclude_term}'"
                }

        # Check for inclusion terms (light symptoms)
        for include_term in self.include_terms:
            if include_term in combined_text:
                return {
                    "passed": True,
                    "reason": f"Contains light symptom: '{include_term}'"
                }

        # No inclusion terms found
        return {
            "passed": False,
            "reason": "No light/common symptoms found"
        }

    def filter_cases(self, cases: List[Dict]) -> List[Dict]:
        """
        Filter multiple cases

        Returns list of cases that passed the filter, with filter metadata added
        """
        filtered_cases = []

        for case in cases:
            text = case.get("text", "")
            chief_complaint = case.get("chief_complaint", "")

            filter_result = self.filter_case(text, chief_complaint)

            if filter_result["passed"]:
                case["light_case_filter"] = filter_result
                filtered_cases.append(case)
            else:
                logger.debug(f"Case {case.get('hadm_id')} filtered out: {filter_result['reason']}")

        logger.info(f"Filtered {len(cases)} cases to {len(filtered_cases)} light cases")
        return filtered_cases
