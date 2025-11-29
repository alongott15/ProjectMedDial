"""
ProfileGeneratorAgent - Creates profile variants from GTMF data.

This agent generates three types of patient profiles from Ground Truth Medical Forms:
1. FULL - Complete profile with all fields
2. NO_DIAGNOSIS - Profile without diagnosis information
3. NO_DIAGNOSIS_NO_TREATMENT - Profile with only symptoms and context
"""

import logging
from typing import Dict, List, Literal
import copy

logger = logging.getLogger(__name__)

ProfileType = Literal["FULL", "NO_DIAGNOSIS", "NO_DIAGNOSIS_NO_TREATMENT"]


class ProfileGeneratorAgent:
    """Generates different profile variants from GTMF data for dialogue generation."""

    def __init__(self):
        """Initialize the ProfileGeneratorAgent."""
        logger.info("ProfileGeneratorAgent initialized")

    def generate_full_profile(self, gtmf: Dict) -> Dict:
        """
        Generate a FULL profile from GTMF (no modifications).

        Args:
            gtmf: Ground Truth Medical Form dictionary.

        Returns:
            Profile dictionary with profile_type='FULL'.
        """
        profile = copy.deepcopy(gtmf)
        profile["profile_type"] = "FULL"
        logger.debug(f"Generated FULL profile for subject_id={gtmf.get('subject_id')}")
        return profile

    def generate_no_diagnosis_profile(self, gtmf: Dict) -> Dict:
        """
        Generate a NO_DIAGNOSIS profile (diagnosis removed, treatment kept).

        Args:
            gtmf: Ground Truth Medical Form dictionary.

        Returns:
            Profile dictionary with profile_type='NO_DIAGNOSIS'.
        """
        profile = copy.deepcopy(gtmf)

        # Remove diagnoses
        if "Core_Fields" in profile and "Diagnoses" in profile["Core_Fields"]:
            profile["Core_Fields"]["Diagnoses"] = []

        profile["profile_type"] = "NO_DIAGNOSIS"
        logger.debug(f"Generated NO_DIAGNOSIS profile for subject_id={gtmf.get('subject_id')}")
        return profile

    def generate_no_diagnosis_no_treatment_profile(self, gtmf: Dict) -> Dict:
        """
        Generate a NO_DIAGNOSIS_NO_TREATMENT profile (only symptoms + context).

        Args:
            gtmf: Ground Truth Medical Form dictionary.

        Returns:
            Profile dictionary with profile_type='NO_DIAGNOSIS_NO_TREATMENT'.
        """
        profile = copy.deepcopy(gtmf)

        # Remove both diagnoses and treatments
        if "Core_Fields" in profile:
            profile["Core_Fields"]["Diagnoses"] = []
            profile["Core_Fields"]["Treatment_Options"] = []

        profile["profile_type"] = "NO_DIAGNOSIS_NO_TREATMENT"
        logger.debug(f"Generated NO_DIAGNOSIS_NO_TREATMENT profile for subject_id={gtmf.get('subject_id')}")
        return profile

    def generate_profile(self, gtmf: Dict, profile_type: ProfileType) -> Dict:
        """
        Generate a specific profile type from GTMF.

        Args:
            gtmf: Ground Truth Medical Form dictionary.
            profile_type: Type of profile to generate.

        Returns:
            Profile dictionary with appropriate fields based on type.

        Raises:
            ValueError: If profile_type is invalid.
        """
        if profile_type == "FULL":
            return self.generate_full_profile(gtmf)
        elif profile_type == "NO_DIAGNOSIS":
            return self.generate_no_diagnosis_profile(gtmf)
        elif profile_type == "NO_DIAGNOSIS_NO_TREATMENT":
            return self.generate_no_diagnosis_no_treatment_profile(gtmf)
        else:
            raise ValueError(f"Invalid profile_type: {profile_type}")

    def generate_all_profiles(self, gtmf: Dict) -> List[Dict]:
        """
        Generate all three profile variants from a single GTMF.

        Args:
            gtmf: Ground Truth Medical Form dictionary.

        Returns:
            List of three profile dictionaries (FULL, NO_DIAGNOSIS, NO_DIAGNOSIS_NO_TREATMENT).
        """
        profiles = [
            self.generate_full_profile(gtmf),
            self.generate_no_diagnosis_profile(gtmf),
            self.generate_no_diagnosis_no_treatment_profile(gtmf)
        ]

        logger.info(f"Generated {len(profiles)} profile variants for subject_id={gtmf.get('subject_id')}")
        return profiles

    def validate_profile_completeness(self, profile: Dict) -> tuple[bool, List[str]]:
        """
        Validate that profile has necessary components for realistic dialogue.

        Args:
            profile: Profile dictionary to validate.

        Returns:
            Tuple of (is_valid: bool, issues: List[str]).
        """
        issues = []

        # Check for essential components
        core_fields = profile.get("Core_Fields", {})
        context_fields = profile.get("Context_Fields", {})
        additional_context = profile.get("Additional_Context", {})

        # Validate symptoms
        symptoms = core_fields.get("Symptoms", [])
        if not symptoms:
            issues.append("No symptoms present")
        elif not isinstance(symptoms, list):
            issues.append("Symptoms field is not a list")

        # Validate demographics
        demographics = context_fields.get("Patient_Demographics", {})
        if not demographics:
            issues.append("No patient demographics")
        else:
            if demographics.get("Age", 0) <= 0:
                issues.append("Invalid or missing age")
            if not demographics.get("Sex") or demographics.get("Sex") == "not provided":
                issues.append("Missing gender/sex information")

        # Validate chief complaint
        chief_complaint = additional_context.get("Chief_Complaint", "")
        if not chief_complaint or chief_complaint == "not provided":
            issues.append("Missing chief complaint")

        is_valid = len(issues) == 0
        return is_valid, issues

    def enhance_profile_if_needed(self, profile: Dict) -> Dict:
        """
        Enhance profile with defaults if critical information is missing.

        Args:
            profile: Profile dictionary to enhance.

        Returns:
            Enhanced profile dictionary.
        """
        enhanced_profile = copy.deepcopy(profile)

        # Ensure chief complaint exists
        if not enhanced_profile.get("Additional_Context", {}).get("Chief_Complaint") or \
           enhanced_profile.get("Additional_Context", {}).get("Chief_Complaint") == "not provided":

            # Generate chief complaint from first symptom
            symptoms = enhanced_profile.get("Core_Fields", {}).get("Symptoms", [])
            if symptoms and isinstance(symptoms[0], dict):
                symptom_desc = symptoms[0].get("description", "")
                if symptom_desc:
                    if "Additional_Context" not in enhanced_profile:
                        enhanced_profile["Additional_Context"] = {}
                    enhanced_profile["Additional_Context"]["Chief_Complaint"] = \
                        f"Experiencing {symptom_desc.lower()}"
                    logger.info(f"Enhanced profile with generated chief complaint")

        return enhanced_profile


# Backward compatibility function (replaces Utils/partial_profile.py)
def generate_partial_profiles(full_profile: dict) -> dict:
    """
    Create partial profile (NO_DIAGNOSIS_NO_TREATMENT variant) from full GTMF.

    This function maintains backward compatibility with the existing codebase.

    Args:
        full_profile: Full GTMF dictionary.

    Returns:
        Partial profile dictionary.
    """
    agent = ProfileGeneratorAgent()
    return agent.generate_no_diagnosis_no_treatment_profile(full_profile)
