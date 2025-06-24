def generate_partial_profiles(full_profile: dict) -> list:
    """
    Create partial profiles by omitting some fields (e.g., diagnoses or treatments)
    from the full GTMF.
    """
    
    """# Profile with diagnoses omitted
    profile_no_dx = full_profile.copy()
    if "Core_Fields" in profile_no_dx and "Diagnoses" in profile_no_dx["Core_Fields"]:
        profile_no_dx["Core_Fields"]["Diagnoses"] = []
    profiles.append(profile_no_dx)
    
    # Profile with treatments omitted
    profile_no_tx = full_profile.copy()
    if "Core_Fields" in profile_no_tx and "Treatment_Options" in profile_no_tx["Core_Fields"]:
        profile_no_tx["Core_Fields"]["Treatment_Options"] = []
    profiles.append(profile_no_tx)"""
    
    # Profile with both diagnoses and treatments omitted
    profile_no_dx_tx = full_profile.copy()
    if "Core_Fields" in profile_no_dx_tx:
        profile_no_dx_tx["Core_Fields"]["Diagnoses"] = []
        profile_no_dx_tx["Core_Fields"]["Treatment_Options"] = []
    
    return profile_no_dx_tx