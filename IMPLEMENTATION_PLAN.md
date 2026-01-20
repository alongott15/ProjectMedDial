# Implementation Plan: Dataset Expansion and Quality Improvements

## Overview
This document outlines the implementation strategy to achieve three key milestones:
1. Expand dataset from 95 to 300 patient profiles
2. Evaluate all three profile information disclosure levels
3. Improve Semantic Textual Similarity (STS) scores from 0.54 to >0.65

---

## Milestone 1: Expand Dataset to 300 Patient Profiles

### Current State
- **Current**: 95 patient profiles from MIMIC-III
- **Target**: 300 patient profiles
- **Current file**: `gtmf_creation.py` with `limit=100` parameter

### Implementation Steps

#### 1.1 Add Function to Skip Existing GTMFs
**File**: `gtmf_creation.py`

**NEW: Add before `process_notes` function**:
```python
def get_existing_gtmf_ids(output_dir: str = 'gtmf') -> set:
    """
    Get set of (subject_id, hadm_id) tuples for existing GTMFs.

    Returns:
        Set of tuples (subject_id, hadm_id) that already exist
    """
    existing_ids = set()

    if not os.path.exists(output_dir):
        return existing_ids

    for filename in os.listdir(output_dir):
        if filename.startswith('gtmf_') and filename.endswith('.md'):
            # Parse filename: gtmf_10145_135661.md
            parts = filename.replace('gtmf_', '').replace('.md', '').split('_')
            if len(parts) == 2:
                try:
                    subject_id = int(parts[0])
                    hadm_id = int(parts[1])
                    existing_ids.add((subject_id, hadm_id))
                except ValueError:
                    continue

    logger.info(f"Found {len(existing_ids)} existing GTMF profiles")
    return existing_ids
```

#### 1.2 Modify GTMF Creation Script to Skip Existing
**File**: `gtmf_creation.py`

**Changes to `process_notes` function**:
```python
def process_notes(results, azure_client: AzureAIClient, output_dir: str = 'gtmf'):
    os.makedirs(output_dir, exist_ok=True)

    # CRITICAL: Load existing GTMFs to avoid regeneration
    existing_ids = get_existing_gtmf_ids(output_dir)
    logger.info(f"Skipping {len(existing_ids)} existing profiles")

    quality_summary = {
        "total_processed": 0,
        "skipped_existing": 0,  # NEW
        "json_parse_failures": 0,
        "light_case_passed": 0,
        "light_case_failed": 0,
        "gtmfs_created": 0
    }

    for idx, row in enumerate(results):
        try:
            # CRITICAL: Skip if already exists
            subject_id = row['subject_id']
            hadm_id = row['hadm_id']

            if (subject_id, hadm_id) in existing_ids:
                logger.info(f"  Skipping existing profile: {subject_id}_{hadm_id}")
                quality_summary["skipped_existing"] += 1
                continue

            light_case_result = is_light_common_case(row['text'])
            if not light_case_result['passed']:
                quality_summary["light_case_failed"] += 1
                continue
            # ... rest of processing
```

**Changes to `main` function** (Line 415):
```python
# Fetch more notes to reach target after skipping existing
results = loader.fetch_notes_with_light_case_filter(
    category_filter="Discharge summary",
    limit=800,  # Increased to ensure we get 300 total after filtering
    offset=0    # Start from beginning but will skip existing
)
```

**Rationale**:
- Preserves existing 95 GTMFs (no regeneration)
- Only creates NEW profiles
- Target: 95 existing + ~205 new = 300 total
- Setting limit=800 ensures enough candidates after filtering and skipping
- Conservative estimate accounts for light case filtering removing ~50% of cases

#### 1.3 Add Progress Tracking
**Enhancement**: Add progress indicators during batch processing

```python
# Add to process_notes function
for idx, row in enumerate(results):
    if idx % 50 == 0:
        logger.info(f"Progress: {idx}/{len(results)} notes processed")
        logger.info(f"  GTMFs created so far: {quality_summary['gtmfs_created']}")
```

#### 1.4 Add Checkpoint System
**Enhancement**: Save progress periodically to avoid reprocessing

```python
# Add checkpoint functionality
def save_checkpoint(idx, quality_summary):
    checkpoint_path = os.path.join(output_dir, 'checkpoint.json')
    with open(checkpoint_path, 'w') as f:
        json.dump({'last_index': idx, 'summary': quality_summary}, f)

def load_checkpoint(output_dir):
    checkpoint_path = os.path.join(output_dir, 'checkpoint.json')
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, 'r') as f:
            return json.load(f)
    return None
```

**Expected Outcome**:
- 300+ total patient profiles (95 existing + ~205 new)
- **CRITICAL**: Existing 95 profiles are preserved (NOT regenerated)
- Only new profiles created, skipping any that already exist
- Diverse symptom combinations and demographics
- Improved statistical power for analysis
- Checkpoint recovery in case of interruption

---

## Milestone 2: Evaluate All Profile Information Disclosure Levels

### Current State
- **Current**: Only NO_DIAGNOSIS_NO_TREATMENT tested (default)
- **Infrastructure**: Already exists (`partial_profile.py`)
- **Profile types**: FULL, NO_DIAGNOSIS, NO_DIAGNOSIS_NO_TREATMENT

### Profile Types Explained

| Profile Type | Symptoms | Diagnosis | Treatment | Use Case |
|--------------|----------|-----------|-----------|----------|
| FULL | ✓ | ✓ | ✓ | Simulates patient with known diagnosis |
| NO_DIAGNOSIS | ✓ | ✗ | ✓ | Patient knows symptoms & treatment, not diagnosis |
| NO_DIAGNOSIS_NO_TREATMENT | ✓ | ✗ | ✗ | Most realistic - patient only knows symptoms |

### Implementation Steps

#### 2.1 Modify Pipeline to Process All Profile Types
**File**: `dialogue_generation_framework.py`

**Current behavior** (Line 319):
```python
profile_type = profile_types[0]  # Only processes first type
```

**New implementation**:
```python
# Process each profile with ALL profile types
for profile_type in profile_types:
    try:
        result = self.process_profile(full_profile, ehr_text, profile_type)
        all_results.append(result)
        # ... stats tracking
    except Exception as e:
        logger.error(f"Error processing {profile_id} ({profile_type}): {e}")
```

**Impact**: Each profile generates 3 dialogues (one per type)

#### 2.2 Update Stats Tracking
**Enhancement**: Track stats separately by profile type

```python
stats = {
    "total_profiles": len(gtmf_data),
    "total_dialogues_attempted": 0,  # Will be profiles * 3
    "by_profile_type": {
        "FULL": {
            "success": 0,
            "fail": 0,
            "realistic": 0,
            "avg_judge_score": 0,
            "avg_sts_score": 0
        },
        "NO_DIAGNOSIS": {
            "success": 0,
            "fail": 0,
            "realistic": 0,
            "avg_judge_score": 0,
            "avg_sts_score": 0
        },
        "NO_DIAGNOSIS_NO_TREATMENT": {
            "success": 0,
            "fail": 0,
            "realistic": 0,
            "avg_judge_score": 0,
            "avg_sts_score": 0
        }
    }
}
```

#### 2.3 Update Output File Naming
**Enhancement**: Distinguish dialogues by profile type

```python
# Line 268: Update filename
output_path = self.output_dir / f"dialogue_{profile_id}_{profile_type}.md"
```

#### 2.4 Create Comparative Analysis Tool
**New file**: `analyze_profile_types.py`

```python
def compare_profile_types(output_dir):
    """
    Compare dialogue quality across profile types.

    Metrics:
    - Judge scores by profile type
    - STS scores by profile type
    - Question strategies (how does doctor adapt?)
    - Diagnostic reasoning patterns
    - Naturalness ratings
    """
    # Load all dialogues
    # Group by profile type
    # Compute comparative statistics
    # Generate visualization
    pass
```

**Expected Outcomes**:
1. Quantitative comparison of dialogue quality across profile types
2. Identification of which profile type produces most realistic dialogues
3. Analysis of how doctor's questioning strategy changes
4. Insights into diagnostic reasoning without diagnosis information

---

## Milestone 3: Improve Semantic Textual Similarity Scores

### Current State
- **Current average**: 0.54 (moderate)
- **Target**: >0.65 (good)
- **Problem**: 39.73% of dialogues have STS < 0.5 (information loss)

### Root Cause Analysis

#### Issue 1: Inconsistent Information Extraction
- EHR summaries may emphasize different aspects than dialogue summaries
- Lack of explicit focus on key medical facts

#### Issue 2: Generic Embedding Model
- `all-MiniLM-L6-v2` is general-purpose, not medical-specific
- May not capture medical semantic relationships well

#### Issue 3: Summarization Prompt Ambiguity
- Current prompts are general
- No explicit alignment guidance

### Implementation Steps

#### 3.1 Enhance EHRSummarizerAgent Prompt
**File**: `Utils/bias_aware_prompts.py`

**Current prompt** (Line 90-102):
```python
EHR_SUMMARIZER_PROMPT = BASE_SYSTEM_PROMPT + """

Summarize the following clinical note for a light, common medical case.
...
Keep the summary short (5–8 sentences)."""
```

**Enhanced prompt**:
```python
EHR_SUMMARIZER_PROMPT = BASE_SYSTEM_PROMPT + """

Summarize the following clinical note for a light, common medical case.

CRITICAL FOCUS AREAS (include in this specific order):
1. **Chief Complaint**: The primary reason for the visit (1 sentence)
2. **Symptom Details**: Specific symptoms with characteristics
   (severity, duration, triggers, alleviating factors) (2-3 sentences)
3. **Relevant History**: Pertinent medical history, medications, allergies (1 sentence)
4. **Clinical Findings**: Physical exam or test results if documented (1 sentence)
5. **Assessment**: Documented diagnosis or clinical impression (1 sentence)
6. **Treatment Plan**: Specific treatments, medications, or recommendations (1-2 sentences)

FORMAT REQUIREMENTS:
- Use consistent medical terminology (e.g., "dyspnea" AND "shortness of breath")
- Include specific details (numbers, dates, measurements when present)
- Link symptoms to diagnoses explicitly when documented
- Total: 5-8 sentences covering all focus areas that apply

Example structure:
"The patient is a [age]-year-old [sex] presenting with [chief complaint].
[Detailed symptoms]. [Relevant history]. [Clinical findings].
The documented diagnosis was [diagnosis]. Treatment included [specific treatments]."

Do not infer information not in the text. If a focus area is not documented, skip it.

Summary:"""
```

**Rationale**:
- Structured extraction ensures consistency
- Specific focus areas align with dialogue content
- Explicit ordering improves parallelism with dialogue summaries

#### 3.2 Enhance DialogueSummarizerAgent Prompt
**File**: `Utils/bias_aware_prompts.py`

**Current prompt** (Line 105-117):
```python
DIALOGUE_SUMMARIZER_PROMPT = BASE_SYSTEM_PROMPT + """

Summarize the following doctor–patient dialogue.
...
Keep the summary short (5–8 sentences)."""
```

**Enhanced prompt**:
```python
DIALOGUE_SUMMARIZER_PROMPT = BASE_SYSTEM_PROMPT + """

Summarize the following doctor–patient dialogue.

CRITICAL FOCUS AREAS (extract in this specific order to match EHR summary format):
1. **Chief Complaint**: What the patient came in for (1 sentence)
2. **Symptom Details**: All symptoms discussed with specific characteristics
   (severity, duration, triggers, what makes better/worse) (2-3 sentences)
3. **Relevant History**: Any medical history, medications, or allergies mentioned (1 sentence)
4. **Clinical Findings**: Any physical findings the doctor noted or patient described (1 sentence)
5. **Assessment**: Doctor's assessment or working diagnosis if stated (1 sentence)
6. **Treatment Plan**: Doctor's specific advice, recommendations, or treatments (1-2 sentences)

FORMAT REQUIREMENTS:
- Mirror medical terminology used in conversation
- Include ALL symptoms patient mentioned (don't omit any)
- Include specific details (timing, severity scales, specific characteristics)
- Connect symptoms to assessment when doctor provides one
- Use similar phrasing to EHR summaries (e.g., "presented with" for chief complaint)
- Total: 5-8 sentences covering all focus areas discussed

Example structure:
"The patient presented with [chief complaint]. [All symptoms with details].
[History mentioned]. [Doctor's assessment/reasoning]. The doctor recommended [specific advice]."

IMPORTANT: Only report what was explicitly discussed. Do not infer or add information.

Summary:"""
```

**Rationale**:
- Parallel structure to EHR summary improves alignment
- Explicit instruction to include ALL symptoms reduces information loss
- Medical terminology guidance improves term matching

#### 3.3 Implement Medical-Specific Embedding Models
**File**: `Agents/STSEvaluatorAgent.py`

**Current**: Uses `all-MiniLM-L6-v2` (general-purpose)

**Enhancement**: Add medical-specific models with fallback

```python
class STSEvaluatorAgent:
    """
    Computes Semantic Textual Similarity with medical-specific models.
    """

    AVAILABLE_MODELS = {
        'general': 'all-MiniLM-L6-v2',
        'medical': 'pritamdeka/S-PubMedBert-MS-MARCO',
        'biobert': 'dmis-lab/biobert-base-cased-v1.2',
        'clinical': 'emilyalsentzer/Bio_ClinicalBERT'
    }

    def __init__(self, model_name: str = 'medical'):
        """
        Initialize with specified model.

        Args:
            model_name: 'general', 'medical', 'biobert', or 'clinical'
        """
        try:
            from sentence_transformers import SentenceTransformer, util

            # Try medical model first, fallback to general
            try:
                model_path = self.AVAILABLE_MODELS.get(model_name, 'medical')
                self.model = SentenceTransformer(model_path)
                self.model_name = model_name
                logger.info(f"Loaded {model_name} model: {model_path}")
            except Exception as e:
                logger.warning(f"Failed to load {model_name} model: {e}")
                logger.info("Falling back to general model")
                self.model = SentenceTransformer(self.AVAILABLE_MODELS['general'])
                self.model_name = 'general'

            self.util = util

        except ImportError:
            logger.error("sentence-transformers not installed")
            raise ImportError("pip install sentence-transformers")

    def compute_sts_multi_model(self, text1: str, text2: str) -> dict:
        """
        Compute STS with multiple models for comparison.

        Returns dict with scores from different models.
        """
        scores = {}
        for model_name in ['general', 'medical']:
            try:
                temp_model = SentenceTransformer(self.AVAILABLE_MODELS[model_name])
                embedding1 = temp_model.encode(text1, convert_to_tensor=True)
                embedding2 = temp_model.encode(text2, convert_to_tensor=True)
                score = self.util.pytorch_cos_sim(embedding1, embedding2).item()
                scores[model_name] = max(0.0, min(1.0, score))
            except Exception as e:
                logger.warning(f"Skipping {model_name}: {e}")

        return scores
```

**Rationale**:
- Medical-specific models better understand clinical terminology
- Multiple model comparison provides robust evaluation
- Fallback ensures system continues working

#### 3.4 Create STS Analysis Tool
**New file**: `analyze_low_sts_dialogues.py`

```python
#!/usr/bin/env python3
"""
Analyze dialogues with low STS scores to identify information loss patterns.
"""

import json
import os
from pathlib import Path
from collections import defaultdict
import pandas as pd

def analyze_low_sts_dialogues(output_dir='output_dialogue_framework', threshold=0.5):
    """
    Identify patterns in low-STS dialogues.

    Analysis:
    1. Load all dialogue results
    2. Filter STS < threshold
    3. Compare EHR vs dialogue summaries
    4. Identify missing information categories
    5. Generate report
    """

    # Load per-profile stats
    stats_path = Path(output_dir) / 'per_profile_stats.json'
    with open(stats_path, 'r') as f:
        stats = json.load(f)

    # Filter low STS scores
    low_sts = [s for s in stats if s.get('sts_score') and s['sts_score'] < threshold]

    logger.info(f"Found {len(low_sts)} dialogues with STS < {threshold}")
    logger.info(f"Percentage: {len(low_sts)/len(stats)*100:.1f}%")

    # Analyze patterns
    patterns = {
        'missing_symptoms': 0,
        'missing_diagnosis': 0,
        'missing_treatment': 0,
        'terminology_mismatch': 0,
        'incomplete_symptom_details': 0
    }

    for profile_stat in low_sts:
        profile_id = profile_stat['profile_id']

        # Load full dialogue markdown
        dialogue_path = Path(output_dir) / f"dialogue_{profile_id}.md"
        if not dialogue_path.exists():
            continue

        # Parse markdown to extract summaries
        with open(dialogue_path, 'r') as f:
            content = f.read()

        # Extract EHR and dialogue summaries
        ehr_summary = extract_section(content, '## EHR Summary')
        dialogue_summary = extract_section(content, '## Dialogue Summary')

        # Analyze differences
        ehr_terms = set(extract_medical_terms(ehr_summary))
        dialogue_terms = set(extract_medical_terms(dialogue_summary))

        missing_terms = ehr_terms - dialogue_terms

        # Categorize missing information
        if any(term in symptom_keywords for term in missing_terms):
            patterns['missing_symptoms'] += 1
        if any(term in diagnosis_keywords for term in missing_terms):
            patterns['missing_diagnosis'] += 1
        if any(term in treatment_keywords for term in missing_terms):
            patterns['missing_treatment'] += 1

    # Generate report
    report = {
        'total_low_sts': len(low_sts),
        'percentage': len(low_sts)/len(stats)*100,
        'patterns': patterns,
        'recommendations': generate_recommendations(patterns)
    }

    # Save report
    report_path = Path(output_dir) / 'low_sts_analysis_report.json'
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)

    print("\n=== Low STS Analysis Report ===")
    print(f"Total dialogues analyzed: {len(stats)}")
    print(f"Low STS dialogues (< {threshold}): {len(low_sts)} ({report['percentage']:.1f}%)")
    print("\nIdentified Patterns:")
    for pattern, count in patterns.items():
        print(f"  - {pattern}: {count}")
    print("\nRecommendations:")
    for rec in report['recommendations']:
        print(f"  - {rec}")

    return report

def extract_medical_terms(text):
    """Extract key medical terms from text."""
    # Simple keyword extraction (can be enhanced with NER)
    keywords = []
    for word in text.lower().split():
        if word in medical_term_dict:
            keywords.append(word)
    return keywords

def generate_recommendations(patterns):
    """Generate improvement recommendations based on patterns."""
    recs = []

    if patterns['missing_symptoms'] > patterns['total_low_sts'] * 0.3:
        recs.append("Improve PatientAgent to disclose all symptoms from profile")

    if patterns['missing_diagnosis'] > patterns['total_low_sts'] * 0.2:
        recs.append("Enhance DoctorAgent to verbalize diagnostic reasoning")

    if patterns['missing_treatment'] > patterns['total_low_sts'] * 0.2:
        recs.append("Ensure DoctorAgent provides specific treatment recommendations")

    if patterns['terminology_mismatch'] > patterns['total_low_sts'] * 0.4:
        recs.append("Improve summarizers to use consistent medical terminology")

    if patterns['incomplete_symptom_details'] > patterns['total_low_sts'] * 0.3:
        recs.append("Enhance dialogue summarizer to capture symptom details")

    return recs

if __name__ == '__main__':
    analyze_low_sts_dialogues()
```

**Expected Outcome**:
- Identification of specific information loss patterns
- Targeted recommendations for improvement
- Data-driven insights into STS improvement strategies

#### 3.5 Create Prompt Testing Framework
**New file**: `test_summarizer_prompts.py`

```python
#!/usr/bin/env python3
"""
Test different summarizer prompt variations to optimize STS scores.
"""

import json
from Agents.EHRSummarizerAgent import EHRSummarizerAgent
from Agents.DialogueSummarizerAgent import DialogueSummarizerAgent
from Agents.STSEvaluatorAgent import STSEvaluatorAgent

def test_prompt_variations():
    """
    Test different prompt formulations and measure STS improvements.
    """

    # Load sample dialogues
    sample_profiles = load_sample_profiles(n=10)

    # Test different prompt variants
    prompt_variants = {
        'baseline': 'current prompts',
        'structured': 'enhanced structured prompts',
        'medical_terms': 'medical terminology focus',
        'exhaustive': 'include all details instruction'
    }

    results = defaultdict(list)

    for variant_name, variant_desc in prompt_variants.items():
        logger.info(f"Testing variant: {variant_name}")

        # Apply prompt variant
        ehr_agent = EHRSummarizerAgent(prompt_variant=variant_name)
        dialogue_agent = DialogueSummarizerAgent(prompt_variant=variant_name)
        sts_agent = STSEvaluatorAgent()

        for profile in sample_profiles:
            ehr_summary = ehr_agent.summarize(profile['ehr_text'])
            dialogue_summary = dialogue_agent.summarize(profile['dialogue'])

            sts_score = sts_agent.compute_sts(ehr_summary, dialogue_summary)
            results[variant_name].append(sts_score)

    # Compare results
    comparison = {}
    for variant, scores in results.items():
        comparison[variant] = {
            'mean': np.mean(scores),
            'median': np.median(scores),
            'std': np.std(scores),
            'min': np.min(scores),
            'max': np.max(scores)
        }

    # Print results
    print("\n=== Prompt Variant Comparison ===")
    for variant, stats in comparison.items():
        print(f"\n{variant}:")
        print(f"  Mean STS: {stats['mean']:.3f}")
        print(f"  Median: {stats['median']:.3f}")
        print(f"  Std Dev: {stats['std']:.3f}")
        print(f"  Range: [{stats['min']:.3f}, {stats['max']:.3f}]")

    # Identify best variant
    best_variant = max(comparison.items(), key=lambda x: x[1]['mean'])
    print(f"\nBest variant: {best_variant[0]} (mean STS: {best_variant[1]['mean']:.3f})")

    return comparison

if __name__ == '__main__':
    test_prompt_variations()
```

---

## Implementation Timeline

### Phase 1: Dataset Expansion (Week 1)
- [ ] Add `get_existing_gtmf_ids()` function to skip existing profiles
- [ ] Modify `gtmf_creation.py` to fetch 800 notes and skip existing 95
- [ ] Add progress tracking and checkpoint system
- [ ] Run GTMF generation (expect 95 existing + ~205 new = 300 total)
- [ ] Validate quality and diversity of new profiles
- [ ] **CRITICAL**: Verify existing 95 profiles were NOT regenerated

### Phase 2: Profile Type Evaluation (Week 2)
- [ ] Modify `dialogue_generation_framework.py` to process all profile types
- [ ] Update stats tracking for profile type comparison
- [ ] Run dialogue generation for all profiles × 3 types = ~900 dialogues
- [ ] Create `analyze_profile_types.py` comparison tool
- [ ] Generate comparative analysis report

### Phase 3: STS Improvement (Week 3-4)
- [ ] Enhance EHR summarizer prompt (structured format)
- [ ] Enhance dialogue summarizer prompt (parallel structure)
- [ ] Implement medical-specific embedding models
- [ ] Create `analyze_low_sts_dialogues.py` tool
- [ ] Run analysis on current dialogues
- [ ] Create `test_summarizer_prompts.py` testing framework
- [ ] Test prompt variations and select best
- [ ] Re-run dialogue generation with improved prompts
- [ ] Measure STS improvement (target >0.65)

### Phase 4: Validation & Documentation (Week 5)
- [ ] Validate all three milestones achieved
- [ ] Generate comprehensive evaluation report
- [ ] Update documentation with findings
- [ ] Create visualizations for research paper
- [ ] Prepare dataset for publication

---

## Success Criteria

### Milestone 1: Dataset Expansion
✓ 300+ total patient profiles (95 existing preserved + ~205 new generated)
✓ **CRITICAL**: Existing 95 profiles NOT regenerated (verified by checking file timestamps)
✓ Diverse symptom combinations (>50 unique chief complaints)
✓ Balanced demographics (age, sex distribution)
✓ All new profiles pass light case filtering

### Milestone 2: Profile Type Evaluation
✓ 900+ dialogues generated (300 profiles × 3 types)
✓ Comparative statistics by profile type
✓ Analysis of doctor questioning strategies
✓ Identification of optimal profile type for realistic dialogues

### Milestone 3: STS Improvement
✓ Average STS score >0.65 (from 0.54)
✓ <20% of dialogues with STS <0.5 (from 39.73%)
✓ Identified and addressed information loss patterns
✓ Medical-specific embeddings improve performance

---

## Risk Mitigation

### Risk 1: API Rate Limits
- **Mitigation**: Add rate limiting, checkpointing, resume capability
- **Fallback**: Batch processing over multiple days

### Risk 2: Low-Quality Profiles After Expansion
- **Mitigation**: Validate sample of new profiles manually
- **Fallback**: Adjust LIGHT_CASE filtering criteria

### Risk 3: STS Improvement Insufficient
- **Mitigation**: Iterative prompt testing, multiple embedding models
- **Fallback**: Hybrid scoring (judge + STS + manual review)

### Risk 4: Processing Time for 900 Dialogues
- **Mitigation**: Parallel processing where possible, run overnight
- **Estimate**: ~50 seconds/dialogue × 900 = ~12.5 hours

---

## Monitoring & Metrics

### Key Metrics to Track
1. **Dataset Expansion**
   - Number of profiles fetched vs. passing light case filter
   - Symptom diversity (unique symptoms count)
   - Demographic distribution

2. **Profile Type Comparison**
   - Judge scores by type (mean, median, distribution)
   - STS scores by type
   - Dialogue lengths by type
   - Question strategies (open-ended vs. specific)

3. **STS Improvement**
   - Before/after STS score distribution
   - Low STS dialogue percentage
   - Model comparison (general vs. medical embeddings)
   - Information retention by category (symptoms, diagnosis, treatment)

---

## File Modifications Summary

### Files to Modify
1. `gtmf_creation.py` - Add skip-existing function, increase limit to 800, add checkpointing
   - **CRITICAL**: Preserves existing 95 profiles, only creates new ones
   - Fetch limit increased to 800 to ensure 300 total after filtering
2. `dialogue_generation_framework.py` - Process all profile types (FULL, NO_DIAGNOSIS, NO_DIAGNOSIS_NO_TREATMENT)
3. `Utils/bias_aware_prompts.py` - Enhanced summarizer prompts with structured 6-focus-area format
4. `Agents/STSEvaluatorAgent.py` - Add medical-specific embedding models (S-PubMedBert, Bio_ClinicalBERT)

### New Files to Create
1. `analyze_profile_types.py` - Profile type comparison
2. `analyze_low_sts_dialogues.py` - STS analysis tool
3. `test_summarizer_prompts.py` - Prompt testing framework
4. `IMPLEMENTATION_PLAN.md` - This document

---

## Next Steps
1. Review and approve implementation plan
2. Begin Phase 1: Dataset expansion
3. Commit changes with detailed documentation
4. Run validation tests after each phase
5. Generate final evaluation report

---

## Questions & Considerations
- Should we parallelize dialogue generation across multiple processes?
- Do we need manual quality validation for a sample of new dialogues?
- Should we experiment with other medical embedding models (e.g., Bio_ClinicalBERT)?
- How should we weight judge score vs. STS score in overall quality assessment?
