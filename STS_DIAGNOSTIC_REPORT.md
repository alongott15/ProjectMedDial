# STS Score Diagnostic Report

## Executive Summary

**Critical Finding**: The current STS (Semantic Textual Similarity) scores are **artificially inflated** (0.93-0.97) and do not accurately reflect the information retention in the synthetic dialogues.

**Expected Range**: Based on IMPLEMENTATION_PLAN.md, baseline STS was 0.54 with a goal to reach >0.65

**Current Reality**: All dialogues show STS scores >0.93, which is unrealistic given the information gaps

---

## Root Cause Analysis

### Issue 1: Embedding Model Over-Emphasizes Shared Content

The current STS calculation uses **cosine similarity** of sentence embeddings, which focuses on shared content rather than penalizing missing information.

#### Example: Profile 10096_182988 (NO_DIAGNOSIS type)

**EHR Summary includes**:
- ✓ Symptoms: chest pain, nausea, fatigue, near-syncope, diaphoresis
- ✓ Clinical findings: hypotensive (SBP 50s), bradycardic (HR 20-30), complete heart block
- ✓ **Diagnosis**: "ST-elevation myocardial infarction (STEMI) with complete heart block"
- ✓ **Treatment**: "cardiac catheterization, Cypher stent to RCA, dual antiplatelet therapy"
- ✓ EKG: "3-4 mm ST elevation in II, III, AvF with ST depressions anterolaterally"

**Dialogue Summary includes**:
- ✓ Symptoms: chest pain, nausea, sweating, fatigue, near-fainting (similar wording)
- ✗ Clinical findings: NOT mentioned
- ✗ **Diagnosis**: NOT mentioned (by design for NO_DIAGNOSIS profile)
- ✗ **Treatment**: NOT mentioned (only "recommended EKG and blood tests")
- ✗ EKG findings: NOT mentioned
- ✗ Medical history: "No relevant past medical history... mentioned"

**Current STS Score**: **0.968** ❌ (Way too high!)

**Expected STS Score**: Should be **~0.40-0.55** given ~50% of critical information is missing

---

### Issue 2: Profile Types Not Considered in STS Calculation

The three profile types have fundamentally different expectations for information disclosure:

| Profile Type | Expected STS Range | Reasoning |
|--------------|-------------------|-----------|
| **FULL** | 0.70-0.85 | Dialogue should include symptoms, diagnosis, and treatment |
| **NO_DIAGNOSIS** | 0.50-0.65 | Dialogue should include symptoms and treatment, but NOT diagnosis |
| **NO_DIAGNOSIS_NO_TREATMENT** | 0.40-0.55 | Dialogue should only include symptoms |

**Current Reality**: All profile types show STS >0.93, making the metric meaningless for distinguishing information retention quality.

---

### Issue 3: Structural Similarity Inflates Scores

Both EHR and dialogue summaries follow similar templates:

```
"The patient [is/presented with] [symptoms]...
[History]... [Assessment]... [Treatment/Plan]..."
```

This structural similarity causes high embedding similarity even when content is fundamentally different.

---

## Evidence from Dataset

### Sample Analysis (20 dialogues examined)

| Profile Type | Min STS | Max STS | Mean STS | Expected Mean |
|--------------|---------|---------|----------|---------------|
| FULL | 0.945 | 0.974 | 0.962 | 0.75 |
| NO_DIAGNOSIS | 0.938 | 0.976 | 0.965 | 0.58 |
| NO_DIAGNOSIS_NO_TREATMENT | 0.957 | 0.978 | 0.968 | 0.48 |

**Observation**: NO_DIAGNOSIS_NO_TREATMENT profiles (which intentionally omit the most information) have the HIGHEST average STS scores. This is backwards!

---

## Why This Matters

### 1. Quality Assessment Is Unreliable
- Cannot distinguish between good and poor information retention
- High STS scores mask significant information gaps
- Milestone 3 of IMPLEMENTATION_PLAN cannot be properly evaluated

### 2. Profile Type Comparison Is Invalid
- Cannot compare quality across FULL vs NO_DIAGNOSIS vs NO_DIAGNOSIS_NO_TREATMENT
- All profile types appear equally "good" despite intentional information restrictions

### 3. Research Validity
- Published STS scores would be misleading
- Dataset quality cannot be objectively assessed
- Comparisons with other synthetic dialogue datasets would be invalid

---

## Proposed Solutions

### Solution 1: Multi-Component STS Score (Recommended)

Replace single STS score with component-wise similarity:

```python
{
    "overall_sts": 0.65,
    "components": {
        "symptoms": 0.92,        # High - symptoms well captured
        "medical_history": 0.45, # Low - history not mentioned
        "diagnosis": 0.15,       # Very low - diagnosis not in dialogue
        "treatment": 0.60,       # Moderate - some treatment mentioned
        "clinical_findings": 0.30 # Low - EKG results not mentioned
    },
    "information_coverage": 0.48,  # Percentage of EHR info captured
    "weighted_sts": 0.58           # Weighted by component importance
}
```

**Advantages**:
- Identifies exactly what information is missing
- Profile type appropriate (FULL should score high on all components, NO_DIAGNOSIS should score low on diagnosis)
- More actionable for improving dialogue quality

### Solution 2: Profile-Type-Aware STS

Calculate expected information overlap based on profile type:

```python
def compute_profile_aware_sts(ehr_summary, dialogue_summary, profile_type):
    # Extract expected vs actual information
    expected_coverage = {
        "FULL": ["symptoms", "diagnosis", "treatment", "history"],
        "NO_DIAGNOSIS": ["symptoms", "treatment", "history"],
        "NO_DIAGNOSIS_NO_TREATMENT": ["symptoms", "history"]
    }

    # Only penalize for information that SHOULD be present
    actual_coverage = extract_information_categories(dialogue_summary)

    missing_required = set(expected_coverage[profile_type]) - actual_coverage
    missing_penalty = len(missing_required) * 0.15

    # Compute base STS
    base_sts = compute_embedding_similarity(ehr_summary, dialogue_summary)

    # Apply coverage penalty
    adjusted_sts = max(0, base_sts - missing_penalty)

    return adjusted_sts
```

**Advantages**:
- Single score remains simple to interpret
- Profile type appropriate by design
- Backward compatible with existing infrastructure

### Solution 3: Dual Scoring System

Keep current STS for structural similarity, add Information Retention Score:

```python
{
    "semantic_similarity": 0.965,     # Current cosine similarity (high due to structure)
    "information_retention": 0.52,    # New metric for content completeness
    "combined_score": 0.68            # Weighted average for overall quality
}
```

**Information Retention Calculation**:
- Extract key medical facts from EHR summary (symptoms, diagnosis, treatment, findings)
- Check presence/absence of each fact in dialogue summary
- Score = (facts_present / facts_expected_for_profile_type)

---

## Recommended Action Plan

### Phase 1: Implement Component-Wise STS (Week 1)
1. Create `Agents/ImprovedSTSEvaluatorAgent.py` with component extraction
2. Update `dialogue_generation_framework.py` to use new evaluator
3. Test on sample of 50 dialogues
4. Validate scores make intuitive sense

### Phase 2: Recalculate All Scores (Week 2)
1. Create script to recalculate STS for all existing dialogues
2. Update dialogue markdown files with new scores
3. Regenerate `global_stats.json` and `per_profile_stats.json`
4. Create before/after comparison report

### Phase 3: Validation & Analysis (Week 3)
1. Validate new scores correlate with manual quality assessment
2. Confirm profile types show expected score distributions
3. Identify actual low-quality dialogues (not masked by inflated scores)
4. Generate visualizations for paper

---

## Technical Implementation Notes

### For Component Extraction

Use keyword-based extraction with medical NER:
```python
COMPONENTS = {
    "symptoms": ["pain", "nausea", "fatigue", "dyspnea", "chest pain", ...],
    "diagnosis": ["diagnosis", "STEMI", "myocardial infarction", "heart block", ...],
    "treatment": ["catheterization", "stent", "aspirin", "medication", "prescribed", ...],
    "findings": ["EKG", "blood pressure", "heart rate", "hypotensive", ...]
}

def extract_component_facts(text, component_type):
    """Extract medical facts for a specific component."""
    facts = []
    doc = nlp(text)  # Use spaCy or similar NER

    # Extract entities and keywords
    for ent in doc.ents:
        if ent.label_ in MEDICAL_ENTITY_TYPES[component_type]:
            facts.append(ent.text.lower())

    return set(facts)
```

### For Profile-Type-Aware Calculation

```python
def compute_profile_adjusted_sts(ehr_sum, dialogue_sum, profile_type):
    """Compute STS adjusted for profile type expectations."""

    # Extract facts from both summaries
    ehr_facts = extract_all_facts(ehr_sum)
    dialogue_facts = extract_all_facts(dialogue_sum)

    # Determine expected facts based on profile type
    expected_fact_types = PROFILE_TYPE_EXPECTATIONS[profile_type]

    # Filter to only expected facts
    relevant_ehr_facts = {f for f in ehr_facts if f.type in expected_fact_types}
    relevant_dialogue_facts = {f for f in dialogue_facts if f.type in expected_fact_types}

    # Calculate overlap
    overlap = len(relevant_ehr_facts & relevant_dialogue_facts)
    total_expected = len(relevant_ehr_facts)

    # Information retention component (0-1)
    info_retention = overlap / total_expected if total_expected > 0 else 0

    # Semantic similarity component (existing method)
    semantic_sim = compute_embedding_similarity(ehr_sum, dialogue_sum)

    # Weighted combination (60% semantic, 40% info retention)
    final_score = 0.6 * semantic_sim + 0.4 * info_retention

    return {
        "overall_score": final_score,
        "semantic_similarity": semantic_sim,
        "information_retention": info_retention,
        "facts_expected": total_expected,
        "facts_captured": overlap,
        "coverage_percentage": (overlap / total_expected * 100) if total_expected > 0 else 0
    }
```

---

## Validation Criteria

New STS scores should satisfy:

1. **Profile Type Ordering**: FULL > NO_DIAGNOSIS > NO_DIAGNOSIS_NO_TREATMENT
2. **Reasonable Range**: Scores between 0.40-0.85 (not 0.93-0.97)
3. **Correlation with Quality**: Low STS should identify dialogues with information gaps
4. **Distribution**: Scores should follow roughly normal distribution, not all clustered at 0.96+
5. **Interpretability**: Score should predict what information is missing

---

## Impact Assessment

### If Implemented
- ✓ Accurate quality assessment of synthetic dialogues
- ✓ Valid comparison across profile types
- ✓ Identification of actual quality issues to fix
- ✓ Research validity and reproducibility
- ✓ Actionable insights for improving dialogue generation

### If Not Implemented
- ✗ STS scores remain meaningless
- ✗ Cannot complete Milestone 3 evaluation
- ✗ Quality issues masked by inflated scores
- ✗ Research conclusions potentially invalid
- ✗ Cannot identify what needs improvement

---

## Conclusion

The current STS scores are **technically correct** (accurate cosine similarity of embeddings) but **functionally useless** (don't measure what we care about: information retention).

**Recommendation**: Implement Solution 1 (Component-Wise STS) as it provides the most actionable insights and properly handles profile type differences.

**Timeline**: 2-3 weeks to implement, test, and recalculate all scores.

**Priority**: **HIGH** - This blocks accurate evaluation of Milestone 3 and threatens research validity.

---

*Report generated: 2026-01-19*
*Dataset: ProjectMedDial with 1269 realistic dialogues across 498 profiles*
*Current STS range: 0.929-0.978 (artificially high)*
*Expected STS range: 0.40-0.80 (realistic with variation)*
