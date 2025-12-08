# Synthetic Patient-Physician Conversation Framework

## Overview

This framework implements the PRD requirements for generating and evaluating synthetic medical dialogues with light, common medical cases. The framework uses:

- **Light case filtering**: Focuses on common symptoms (cough, sore throat, headache, fever, etc.)
- **Three profile types**: FULL, NO_DIAGNOSIS, NO_DIAGNOSIS_NO_TREATMENT
- **LLM Judge**: Naturalness validation instead of complex multi-metric systems
- **Iterative generation**: Up to 3 attempts per dialogue with feedback-driven improvement
- **STS evaluation**: Semantic similarity between EHR and dialogue summaries
- **Bias-aware prompting**: Reduces hallucinations across all agents

## Architecture

### New Agents

1. **JudgeAgent** (`Agents/JudgeAgent.py`)
   - Evaluates dialogue naturalness and groundedness
   - Provides decision (REALISTIC/UNREALISTIC) and score (0.0-1.0)
   - Gives actionable feedback for improvement

2. **PromptImprovementAgent** (`Agents/PromptImprovementAgent.py`)
   - Translates judge feedback into improved prompts
   - Maintains bias-aware constraints
   - Focuses on stylistic/structural improvements

3. **EHRSummarizerAgent** (`Agents/EHRSummarizerAgent.py`)
   - Summarizes clinical notes (5-8 sentences)
   - Only includes information present in the text

4. **DialogueSummarizerAgent** (`Agents/DialogueSummarizerAgent.py`)
   - Summarizes doctor-patient dialogues
   - Reports only what was actually said

5. **STSEvaluatorAgent** (`Agents/STSEvaluatorAgent.py`)
   - Computes semantic textual similarity
   - Uses sentence-transformers models

### Extended Utilities

1. **bias_aware_prompts.py** (`Utils/bias_aware_prompts.py`)
   - Shared prompt templates for all agents
   - Ensures consistent grounding and anti-hallucination instructions

2. **partial_profile.py** (extended)
   - Now supports three profile types
   - `generate_partial_profiles(profile, type)` for single type
   - `generate_all_profile_types(profile)` for all three

3. **csv_data_loader.py** (`Utils/csv_data_loader.py`)
   - Alternative to SQL database access
   - Loads MIMIC-III data from CSV files
   - Includes light case filtering

### Extended Core Files

1. **gtmf_creation.py** (extended)
   - Light case filtering with `is_light_common_case()`
   - Expanded light case terms (50+ symptom indicators)
   - Batched processing support
   - Tags GTMFs with `case_type: "LIGHT_COMMON_SYMPTOMS"`

2. **dialogue_generation_framework.py** (new main script)
   - Complete pipeline implementation
   - Iterative dialogue generation with JudgeAgent
   - Prompt improvement feedback loop
   - STS evaluation
   - Comprehensive statistics

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create `.env` file:

```
AZURE_AI_ENDPOINT=your_endpoint
AZURE_AI_API_KEY=your_key
DATABASE_URL=postgresql://user:pass@host:port/mimic  # Optional if using CSV
```

### 3. Generate GTMFs (Light Cases)

#### Option A: From PostgreSQL Database

```bash
python gtmf_creation.py
```

This will:
- Fetch clinical notes from MIMIC-III database
- Apply light case filter
- Extract GTMFs with chunking
- Save to `gtmf/gtmf_example_minimal_enhanced.json`

#### Option B: From CSV Files

```python
from Utils.csv_data_loader import csv_to_gtmf_workflow

results, summary = csv_to_gtmf_workflow(
    csv_dir="/path/to/mimic-iii/csv",
    output_path="gtmf/gtmf_from_csv.json",
    limit=50,
    batch_size=10
)
```

### 4. Generate Dialogues

```bash
python dialogue_generation_framework.py
```

This will:
- Load light case GTMFs
- Generate partial profiles (default: NO_DIAGNOSIS_NO_TREATMENT)
- Run iterative dialogue generation (up to 3 attempts)
- Evaluate with JudgeAgent
- Compute STS scores
- Save results to `output_dialogue_framework/`

## Usage Examples

### Basic Pipeline

```python
from dialogue_generation_framework import DialogueGenerationPipeline

# Initialize pipeline
pipeline = DialogueGenerationPipeline(
    max_attempts=3,
    max_turns=16,
    judge_threshold=0.70,
    output_dir="output_dialogue_framework"
)

# Load GTMFs
import json
with open("gtmf/gtmf_example_minimal_enhanced.json") as f:
    gtmf_data = json.load(f)

# Run pipeline
stats = pipeline.run_pipeline(
    gtmf_data=gtmf_data[:10],
    profile_types=["NO_DIAGNOSIS_NO_TREATMENT"]
)
```

### Processing Single Profile

```python
# Process one profile through complete pipeline
result = pipeline.process_profile(
    full_profile=gtmf_data[0],
    ehr_text=original_note_text,  # Optional
    profile_type="FULL"
)

# Access results
print(f"Success: {result['success']}")
print(f"Best attempt: {result['best_attempt']}/3")
print(f"Judge score: {result['judge_evaluation']['score']}")
print(f"STS score: {result['sts_evaluation']['sts_score']}")
```

### Custom Judge Threshold

```python
from Agents.JudgeAgent import JudgeAgent

# Create judge with custom threshold
judge = JudgeAgent(threshold=0.75)

# Evaluate dialogue
evaluation = judge.evaluate_dialogue(
    dialogue=conversation_turns,
    patient_profile=full_profile,
    dialogue_transcript=formatted_transcript
)

print(evaluation['decision'])  # REALISTIC or UNREALISTIC
print(evaluation['score'])      # 0.0-1.0
print(evaluation['feedback_for_improvement'])
```

### Using Different Profile Types

```python
from Utils.partial_profile import generate_partial_profiles

# Generate specific profile type
profile_full = generate_partial_profiles(gtmf, "FULL")
profile_no_dx = generate_partial_profiles(gtmf, "NO_DIAGNOSIS")
profile_minimal = generate_partial_profiles(gtmf, "NO_DIAGNOSIS_NO_TREATMENT")

# Or generate all three at once
all_profiles = generate_all_profile_types(gtmf)
```

### CSV Data Loading

```python
from Utils.csv_data_loader import CSVDataLoader

# Initialize loader
loader = CSVDataLoader(csv_dir="/path/to/mimic-iii/csv")

# Fetch light case notes
notes = loader.fetch_notes_with_light_case_filter(
    category_filter="Discharge summary",
    limit=100
)

# Notes are already joined with patient and admission data
for note in notes:
    print(f"Subject: {note['subject_id']}, Age: {note['gender']}")
    print(f"Text: {note['text'][:200]}...")
```

## Output Structure

### Per-Dialogue Output

Each dialogue is saved to `output_dialogue_framework/dialogue_{profile_id}.json`:

```json
{
  "profile_id": "12345_67890",
  "subject_id": 12345,
  "hadm_id": 67890,
  "profile_type": "NO_DIAGNOSIS_NO_TREATMENT",
  "success": true,
  "best_attempt": 2,
  "total_attempts": 2,
  "attempts_summary": [
    {
      "attempt": 1,
      "success": false,
      "score": 0.65,
      "decision": "UNREALISTIC"
    },
    {
      "attempt": 2,
      "success": true,
      "score": 0.78,
      "decision": "REALISTIC"
    }
  ],
  "dialogue": [...],
  "transcript": "Doctor: Hello...\nPatient: Hi...",
  "judge_evaluation": {
    "decision": "REALISTIC",
    "score": 0.78,
    "justification": "...",
    "feedback_for_improvement": {...}
  },
  "ehr_summary": "62 year old male with cough...",
  "dialogue_summary": "Patient reports cough and sore throat...",
  "sts_evaluation": {
    "sts_score": 0.82,
    "text1_length": 45,
    "text2_length": 52
  },
  "processing_time": 28.3,
  "dialogue_stats": {
    "turn_count": 12,
    "word_count": 450,
    "doctor_turns": 6,
    "patient_turns": 6
  }
}
```

### Global Statistics

Saved to `output_dialogue_framework/global_stats.json`:

```json
{
  "total_profiles": 10,
  "total_dialogues_attempted": 10,
  "successful_dialogues": 8,
  "failed_dialogues": 2,
  "by_profile_type": {
    "NO_DIAGNOSIS_NO_TREATMENT": {
      "success": 8,
      "fail": 2
    }
  },
  "attempt_distribution": {
    "1": 5,
    "2": 2,
    "3": 1
  },
  "avg_judge_score": 0.76,
  "avg_sts_score": 0.79,
  "avg_processing_time": 32.1
}
```

## Configuration Options

### Light Case Filter

Customize in `gtmf_creation.py`:

```python
LIGHT_CASE_INCLUDE_TERMS = [
    "cough", "sore throat", "headache", ...
]

LIGHT_CASE_EXCLUDE_TERMS = [
    "icu", "intubated", "cardiac arrest", ...
]
```

### Pipeline Parameters

```python
pipeline = DialogueGenerationPipeline(
    max_attempts=3,           # Max dialogue generation attempts
    max_turns=16,             # Max turns per dialogue
    judge_threshold=0.70,     # Score threshold for REALISTIC
    output_dir="output_dir"   # Where to save results
)
```

### Dialogue Simulation

```python
conversation, transcript = simulate_dialogue(
    doctor_agent,
    patient_agent,
    max_turns=16,
    consecutive_confusion_limit=2,
    loop_detection_window=4
)
```

## Bias-Aware Prompting

All agents use bias-aware prompts from `Utils/bias_aware_prompts.py`. Key principles:

1. **Grounding**: Only use information from provided context
2. **Uncertainty**: Say "unknown" instead of guessing
3. **Conservative**: Avoid unsupported diagnoses/treatments
4. **No hallucination**: Don't introduce new facts
5. **Research only**: Not for clinical decision-making

Example (Patient Agent):

```
You simulate a patient with a light, common medical issue.

You may express typical symptoms only if they exist in the provided profile.

If the profile does not specify a detail, you can say you are not sure
instead of making it up.
```

## Extending the Framework

### Add New Profile Type

In `Utils/partial_profile.py`:

```python
def generate_partial_profiles(full_profile, profile_type):
    if profile_type == "CUSTOM_TYPE":
        profile = copy.deepcopy(full_profile)
        # Apply custom filtering
        profile["profile_type"] = "CUSTOM_TYPE"
        return profile
```

### Custom Few-Shot Examples for Judge

```python
judge = JudgeAgent()

examples = [
    "Doctor: Hello, how can I help?\nPatient: I have a cough...",
    "Doctor: Tell me about your symptoms...\nPatient: Well, um..."
]

judge.set_few_shot_examples(examples)
```

### Custom STS Model

```python
sts_evaluator = STSEvaluatorAgent(
    model_name='all-mpnet-base-v2'  # Different sentence transformer
)
```

## Troubleshooting

### No Light Cases Found

- Check `LIGHT_CASE_INCLUDE_TERMS` and `LIGHT_CASE_EXCLUDE_TERMS`
- Verify your MIMIC-III data contains discharge summaries
- Try expanding the symptom list

### Low Judge Scores

- Reduce `judge_threshold` from 0.70 to 0.60
- Increase `max_attempts` to give more chances
- Check dialogue logs for issues (too short, repetitive, etc.)

### STS Import Error

```bash
pip install sentence-transformers
```

### CSV Loading Issues

- Ensure CSV files are named: NOTEEVENTS.csv, PATIENTS.csv, ADMISSIONS.csv
- Check column names match MIMIC-III format (uppercase)
- Verify sufficient memory for large CSV files

## Performance Notes

- Each dialogue takes ~30-60 seconds (3 attempts max)
- GTMF extraction: ~10-15 seconds per note with chunking
- STS computation: ~1 second per pair
- Expect ~70-80% success rate with default threshold

## License

This project has no license.
