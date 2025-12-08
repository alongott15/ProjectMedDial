def generate_partial_profiles(full_profile: dict, profile_type: str = "NO_DIAGNOSIS_NO_TREATMENT") -> dict:
    """
    Create partial profiles by omitting some fields (e.g., diagnoses or treatments)
    from the full GTMF.

    Args:
        full_profile: Complete GTMF profile
        profile_type: One of "FULL", "NO_DIAGNOSIS", "NO_DIAGNOSIS_NO_TREATMENT"

    Returns:
        A single profile dict with specified fields omitted
    """
    import copy

    if profile_type == "FULL":
        # Return complete profile with all fields
        profile = copy.deepcopy(full_profile)
        profile["profile_type"] = "FULL"
        return profile

    elif profile_type == "NO_DIAGNOSIS":
        # Profile with only diagnoses omitted
        profile = copy.deepcopy(full_profile)
        if "Core_Fields" in profile and "Diagnoses" in profile["Core_Fields"]:
            profile["Core_Fields"]["Diagnoses"] = []
        profile["profile_type"] = "NO_DIAGNOSIS"
        return profile

    else:  # NO_DIAGNOSIS_NO_TREATMENT (default)
        # Profile with both diagnoses and treatments omitted
        profile = copy.deepcopy(full_profile)
        if "Core_Fields" in profile:
            profile["Core_Fields"]["Diagnoses"] = []
            profile["Core_Fields"]["Treatment_Options"] = []
        profile["profile_type"] = "NO_DIAGNOSIS_NO_TREATMENT"
        return profile


def generate_all_profile_types(full_profile: dict) -> list:
    """
    Generate all three profile types from a full GTMF.

    Args:
        full_profile: Complete GTMF profile

    Returns:
        List of three profiles: [FULL, NO_DIAGNOSIS, NO_DIAGNOSIS_NO_TREATMENT]
    """
    return [
        generate_partial_profiles(full_profile, "FULL"),
        generate_partial_profiles(full_profile, "NO_DIAGNOSIS"),
        generate_partial_profiles(full_profile, "NO_DIAGNOSIS_NO_TREATMENT")
    ]