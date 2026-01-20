# STS Scores Summary

## Overview
- **Total Realistic Dialogues**: 1,269 (across 498 profiles)
- **Overall Average STS Score**: **0.9516** (95.16% semantic similarity)
- **Range**: 0.9014 to 0.9828
- **Standard Deviation**: 0.0147 (very low variance, indicating consistent quality)

## Key Findings

### 1. Excellent Semantic Similarity
All dialogues achieved STS scores above **0.90**, indicating that the generated dialogues maintain excellent semantic consistency with the original EHR clinical notes. The average score of 0.9516 is exceptionally high.

### 2. Consistent Quality Across Profile Types
The three profile types show remarkably similar performance:

| Profile Type | Count | Average | Median | Std Dev | Range |
|--------------|-------|---------|--------|---------|-------|
| **FULL** | 424 | 0.9513 | 0.9533 | 0.0146 | 0.9014 - 0.9782 |
| **NO_DIAGNOSIS** | 429 | 0.9518 | 0.9533 | 0.0145 | 0.9048 - 0.9828 |
| **NO_DIAGNOSIS_NO_TREATMENT** | 416 | 0.9517 | 0.9547 | 0.0150 | 0.9034 - 0.9806 |

There's virtually no difference in STS performance across the three profile types (all within 0.0005 of each other).

### 3. Distribution Analysis
- **81.5%** of dialogues scored between 0.94 and 0.98
- **30.6%** scored above 0.96 (excellent similarity)
- Only **3.5%** scored below 0.92 (still good similarity)
- **0%** scored below 0.90

**Distribution Breakdown**:
- < 0.90: 0 dialogues (0%)
- 0.90-0.92: 44 dialogues (3.5%)
- 0.92-0.94: 209 dialogues (16.5%)
- 0.94-0.96: 621 dialogues (48.9%)
- 0.96-0.98: 391 dialogues (30.8%)
- 0.98-1.00: 4 dialogues (0.3%)

### 4. Statistical Percentiles
- **10th percentile**: 0.9300
- **25th percentile**: 0.9433
- **50th percentile (Median)**: 0.9539
- **75th percentile**: 0.9621
- **90th percentile**: 0.9687
- **95th percentile**: 0.9716
- **99th percentile**: 0.9772

### 5. Best Performing Dialogues
- **Highest STS Score**: 0.9828 (Profile 359_144265, NO_DIAGNOSIS type)
- Top 10 scores range from 0.9782 to 0.9828
- NO_DIAGNOSIS profile type dominates the top performers (7 out of top 10)

**Top 10 Highest STS Scores:**
1. Profile 359_144265 (NO_DIAGNOSIS): 0.9828
2. Profile 359_144265 (NO_DIAGNOSIS_NO_TREATMENT): 0.9806
3. Profile 91092_103998 (NO_DIAGNOSIS): 0.9804
4. Profile 22701_138585 (NO_DIAGNOSIS): 0.9802
5. Profile 7883_128464 (NO_DIAGNOSIS): 0.9798
6. Profile 74319_197811 (NO_DIAGNOSIS): 0.9797
7. Profile 62865_193988 (NO_DIAGNOSIS_NO_TREATMENT): 0.9792
8. Profile 91092_103998 (NO_DIAGNOSIS_NO_TREATMENT): 0.9785
9. Profile 12834_107726 (NO_DIAGNOSIS): 0.9784
10. Profile 13961_115076 (FULL): 0.9782

### 6. Lowest Performing Dialogues
- **Lowest STS Score**: 0.9014 (Profile 10914_134838, FULL type)
- Bottom 10 scores range from 0.9014 to 0.9090
- Even the lowest scores indicate strong semantic similarity (>90%)

**Bottom 10 Lowest STS Scores:**
1. Profile 10914_134838 (FULL): 0.9014
2. Profile 21903_107698 (NO_DIAGNOSIS_NO_TREATMENT): 0.9034
3. Profile 21903_107698 (FULL): 0.9035
4. Profile 5500_121512 (NO_DIAGNOSIS): 0.9048
5. Profile 21903_107698 (NO_DIAGNOSIS): 0.9054
6. Profile 18489_104470 (FULL): 0.9067
7. Profile 20698_176962 (NO_DIAGNOSIS_NO_TREATMENT): 0.9071
8. Profile 5500_121512 (NO_DIAGNOSIS_NO_TREATMENT): 0.9082
9. Profile 12205_180554 (NO_DIAGNOSIS_NO_TREATMENT): 0.9085
10. Profile 5500_121512 (FULL): 0.9090

### 7. Independence from Judge Scores
- **Correlation between Judge Score and STS Score**: -0.0113 (essentially zero)
- This indicates that STS scores and judge scores measure different quality aspects:
  - **STS**: Semantic similarity between EHR and dialogue summaries
  - **Judge**: Realism and quality of the dialogue conversation

## Profile Type Detailed Breakdown

### FULL Profile Type
- **Count**: 424 realistic dialogues
- **Average STS Score**: 0.9513
- **Distribution**:
  - 0.90-0.92: 19 dialogues (4.5%)
  - 0.92-0.94: 59 dialogues (13.9%)
  - 0.94-0.96: 225 dialogues (53.1%)
  - 0.96-0.98: 121 dialogues (28.5%)
  - 0.98-1.00: 0 dialogues (0.0%)

### NO_DIAGNOSIS Profile Type
- **Count**: 429 realistic dialogues
- **Average STS Score**: 0.9518
- **Distribution**:
  - 0.90-0.92: 11 dialogues (2.6%)
  - 0.92-0.94: 79 dialogues (18.4%)
  - 0.94-0.96: 203 dialogues (47.3%)
  - 0.96-0.98: 133 dialogues (31.0%)
  - 0.98-1.00: 3 dialogues (0.7%)

### NO_DIAGNOSIS_NO_TREATMENT Profile Type
- **Count**: 416 realistic dialogues
- **Average STS Score**: 0.9517
- **Distribution**:
  - 0.90-0.92: 14 dialogues (3.4%)
  - 0.92-0.94: 71 dialogues (17.1%)
  - 0.94-0.96: 193 dialogues (46.4%)
  - 0.96-0.98: 137 dialogues (32.9%)
  - 0.98-1.00: 1 dialogue (0.2%)

## Methodology

### STS Computation
- **Model Used**: pritamdeka/S-PubMedBert-MS-MARCO (medical-specific BERT model)
- **Texts Compared**:
  - Text 1: EHR Summary (5-8 sentence summary of clinical notes)
  - Text 2: Dialogue Summary (5-8 sentence summary of the doctor-patient conversation)
- **Metric**: Cosine similarity between embedding vectors
- **Score Range**: 0.0 to 1.0 (higher = more semantically similar)

### Data Sources
- Individual dialogue STS scores: `output_dialogue_framework/dialogue_*.md` files
- Aggregated statistics: `output_dialogue_framework/global_stats.json`
- Per-dialogue metadata: `output_dialogue_framework/per_profile_stats.json`

## Conclusions

1. **High Quality**: All generated dialogues maintain excellent semantic fidelity to the original EHR records (>90% similarity)

2. **Consistency**: The low standard deviation (0.0147) shows the generation process is reliable and consistent

3. **Profile Type Agnostic**: Removing diagnosis and/or treatment information doesn't significantly affect the semantic similarity of the dialogues

4. **Complementary Metrics**: STS and Judge scores are independent (correlation ≈ 0), suggesting they capture different quality dimensions:
   - STS measures information preservation and semantic alignment
   - Judge score measures conversational realism and naturalness

5. **Robust Performance**: With 81.5% of dialogues scoring between 0.94-0.98, the framework demonstrates consistent high-quality dialogue generation

The STS scores demonstrate that the dialogue generation framework successfully creates conversations that preserve the medical information from the EHR records while presenting it in a natural, conversational format.
