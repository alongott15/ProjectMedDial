"""Profile Generator Agent - Generates patient profiles from GTMFs"""
import json
import logging
import uuid
from pathlib import Path
from typing import List, Dict
from Models.classes import GTMF

logger = logging.getLogger(__name__)


class ProfileGeneratorAgent:
    """Generates patient profiles from GTMFs with 3 variants"""

    PROFILE_TYPES = ["FULL", "NO_DIAGNOSIS", "NO_DIAGNOSIS_NO_TREATMENT"]

    def __init__(self, output_dir: str = "outputs/profiles"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_full_profile(self, gtmf: GTMF) -> Dict:
        """Generate FULL profile with all information"""
        gtmf_dict = gtmf.model_dump()

        profile = {
            "profile_id": str(uuid.uuid4()),
            "profile_type": "FULL",
            "gtmf_id": f"{gtmf.subject_id}_{gtmf.hadm_id}",
            "subject_id": gtmf.subject_id,
            "hadm_id": gtmf.hadm_id,
            "case_type": gtmf_dict.get("case_type", "LIGHT_COMMON_SYMPTOMS"),
            "profile_content": {
                "Core_Fields": gtmf_dict.get("Core_Fields", {}),
                "Context_Fields": gtmf_dict.get("Context_Fields", {}),
                "Additional_Context": gtmf_dict.get("Additional_Context", {})
            }
        }

        return profile

    def generate_no_diagnosis_profile(self, gtmf: GTMF) -> Dict:
        """Generate NO_DIAGNOSIS profile without diagnoses"""
        gtmf_dict = gtmf.model_dump()

        # Remove diagnoses
        core_fields = gtmf_dict.get("Core_Fields", {}).copy()
        core_fields["Diagnoses"] = []

        profile = {
            "profile_id": str(uuid.uuid4()),
            "profile_type": "NO_DIAGNOSIS",
            "gtmf_id": f"{gtmf.subject_id}_{gtmf.hadm_id}",
            "subject_id": gtmf.subject_id,
            "hadm_id": gtmf.hadm_id,
            "case_type": gtmf_dict.get("case_type", "LIGHT_COMMON_SYMPTOMS"),
            "profile_content": {
                "Core_Fields": core_fields,
                "Context_Fields": gtmf_dict.get("Context_Fields", {}),
                "Additional_Context": gtmf_dict.get("Additional_Context", {})
            }
        }

        return profile

    def generate_no_diagnosis_no_treatment_profile(self, gtmf: GTMF) -> Dict:
        """Generate NO_DIAGNOSIS_NO_TREATMENT profile with only symptoms and context"""
        gtmf_dict = gtmf.model_dump()

        # Remove diagnoses and treatments
        core_fields = gtmf_dict.get("Core_Fields", {}).copy()
        core_fields["Diagnoses"] = []
        core_fields["Treatment_Options"] = []

        profile = {
            "profile_id": str(uuid.uuid4()),
            "profile_type": "NO_DIAGNOSIS_NO_TREATMENT",
            "gtmf_id": f"{gtmf.subject_id}_{gtmf.hadm_id}",
            "subject_id": gtmf.subject_id,
            "hadm_id": gtmf.hadm_id,
            "case_type": gtmf_dict.get("case_type", "LIGHT_COMMON_SYMPTOMS"),
            "profile_content": {
                "Core_Fields": core_fields,
                "Context_Fields": gtmf_dict.get("Context_Fields", {}),
                "Additional_Context": gtmf_dict.get("Additional_Context", {})
            }
        }

        return profile

    def generate_profiles(self, gtmf: GTMF, profile_types: List[str] = None) -> List[Dict]:
        """
        Generate all requested profile variants from a GTMF

        Args:
            gtmf: GTMF instance
            profile_types: List of profile types to generate (default: all 3 types)

        Returns:
            List of profile dictionaries
        """
        if profile_types is None:
            profile_types = self.PROFILE_TYPES

        profiles = []

        for profile_type in profile_types:
            if profile_type == "FULL":
                profile = self.generate_full_profile(gtmf)
            elif profile_type == "NO_DIAGNOSIS":
                profile = self.generate_no_diagnosis_profile(gtmf)
            elif profile_type == "NO_DIAGNOSIS_NO_TREATMENT":
                profile = self.generate_no_diagnosis_no_treatment_profile(gtmf)
            else:
                logger.warning(f"Unknown profile type: {profile_type}")
                continue

            profiles.append(profile)
            logger.info(f"Generated {profile_type} profile for GTMF {gtmf.hadm_id}")

        return profiles

    def generate_batch(self, gtmfs: List[GTMF], profile_types: List[str] = None) -> List[Dict]:
        """Generate profiles for a batch of GTMFs"""
        all_profiles = []

        for gtmf in gtmfs:
            try:
                profiles = self.generate_profiles(gtmf, profile_types)
                all_profiles.extend(profiles)
            except Exception as e:
                logger.error(f"Error generating profiles for GTMF {gtmf.hadm_id}: {e}")

        logger.info(f"Generated {len(all_profiles)} profiles from {len(gtmfs)} GTMFs")
        return all_profiles

    def save_profile(self, profile: Dict) -> str:
        """Save a single profile to JSON"""
        filename = f"profile_{profile['profile_id']}.json"
        filepath = self.output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(profile, f, indent=2)

        return str(filepath)

    def save_profiles(self, profiles: List[Dict]) -> List[str]:
        """Save multiple profiles to JSON"""
        filepaths = []
        for profile in profiles:
            try:
                filepath = self.save_profile(profile)
                filepaths.append(filepath)
            except Exception as e:
                logger.error(f"Error saving profile {profile.get('profile_id')}: {e}")

        logger.info(f"Saved {len(filepaths)} profiles to {self.output_dir}")
        return filepaths
