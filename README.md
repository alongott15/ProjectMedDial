# Synthetic Patient-Physician Conversation Framework

A Python-based agent framework for generating synthetic medical dialogues from EHR data with light/common medical cases.

## Overview

This framework:
1. Extracts Ground Truth Medical Forms (GTMFs) from MIMIC-III EHR data
2. Restricts to light, common medical cases (cough, sore throat, headache, fever, etc.)
3. Processes EHR notes in configurable batches
4. Generates synthetic patient-physician dialogues with 3 profile variants
5. Validates dialogue naturalness using LLM judge with few-shot examples
6. Supports up to 3 iterative generation attempts per profile
7. Computes Semantic Textual Similarity (STS) between EHR and dialogue summaries
8. Stores all outputs as JSON with detailed statistics

## Architecture

### Agents

- **EHRRetrievalAgent**: Retrieves and filters EHR cases from PostgreSQL MIMIC-III
- **GTMFCreationAgent**: Extracts structured GTMFs with batch processing
- **ProfileGeneratorAgent**: Generates 3 profile types (FULL, NO_DIAGNOSIS, NO_DIAGNOSIS_NO_TREATMENT)
- **PatientAgent**: Simulates patient behavior in dialogue
- **DoctorAgent**: Simulates physician behavior in dialogue
- **DialogueOrchestratorAgent**: Manages conversation flow
- **JudgeAgent**: Evaluates dialogue naturalness with few-shot examples
- **PromptImprovementAgent**: Converts judge feedback to prompt improvements
- **EHRSummarizerAgent**: Summarizes EHR texts
- **DialogueSummarizerAgent**: Summarizes dialogues
- **STSEvaluatorAgent**: Computes semantic similarity scores
- **StatsCollectorAgent**: Collects and computes experiment statistics
- **PipelineOrchestrator**: Main orchestrator for the complete pipeline

## Setup

### Prerequisites

- Python 3.10+
- MIMIC-III dataset as CSV files
- Hugging Face API key (for accessing gpt-oss-120b)

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variable
export HUGGINGFACE_API_KEY="your-huggingface-api-key"
```

### MIMIC-III CSV Setup

1. Download MIMIC-III dataset from PhysioNet
2. Extract the following CSV files to a directory (e.g., `data/mimic3_csv/`):
   - `NOTEEVENTS.csv` - Clinical notes
   - `PATIENTS.csv` - Patient demographics
   - `ADMISSIONS.csv` - Admission information

3. Update `config/config.yaml` to point to your CSV directory:
```yaml
data_source:
  csv_dir: "data/mimic3_csv"
```

### Configuration

Edit `config/config.yaml` to customize:
- Data source (csv_dir pointing to MIMIC-III CSV files)
- Batch sizes (db_batch_size, gtmf_batch_size)
- Experiment parameters (num_admissions, profile_types)
- Light case filter terms (include_terms, exclude_terms)
- Dialogue settings (max_turns, max_attempts)
- Model configurations (gpt-oss-120b via Hugging Face)
- Judge threshold

## Usage

### Run Complete Pipeline

```bash
python pipeline/run_experiment.py
```

### Outputs

All outputs are stored as JSON in `outputs/`:
- `outputs/ehr/` - EHR cases
- `outputs/gtmf/` - Ground Truth Medical Forms
- `outputs/profiles/` - Patient profiles
- `outputs/dialogues/` - Generated dialogues
- `outputs/judge/` - Judge evaluations
- `outputs/summaries/` - EHR and dialogue summaries
- `outputs/sts/` - STS scores
- `outputs/stats/` - Statistics (per-profile and global)
- `outputs/runs/` - Run configurations

## Pipeline Stages

### Stage 1: EHR Retrieval
- Connects to MIMIC-III PostgreSQL database
- Fetches discharge summaries in batches
- Applies light case filter (include/exclude terms)
- Saves filtered cases as JSON

### Stage 2: GTMF Creation (Batched)
- Processes EHR cases in configurable batches
- Uses LLM to extract structured medical information
- Chunks long texts for better extraction
- Merges extractions from multiple chunks
- Tags cases as "LIGHT_COMMON_SYMPTOMS"

### Stage 3: Profile Generation
- Generates 3 profile variants per GTMF:
  - FULL: All information
  - NO_DIAGNOSIS: Symptoms + context only
  - NO_DIAGNOSIS_NO_TREATMENT: Symptoms + context, no diagnosis or treatment

### Stage 4: Dialogue Generation with Judge
- Generates dialogues between patient and doctor agents
- Judge evaluates naturalness using few-shot examples
- Supports up to 3 iterative attempts with feedback
- Applies prompt improvements based on judge feedback
- Saves accepted dialogues and judge evaluations

### Stage 5: Summarization and STS
- Summarizes EHR text and dialogues
- Computes semantic similarity using sentence transformers
- Saves summaries and STS scores

### Stage 6: Statistics
- Computes per-profile statistics (attempts, scores)
- Computes global statistics (success rates, STS distribution)
- Saves statistics and prints summary

## Key Features

### Light Case Filtering
- Includes common symptoms: cough, sore throat, fever, headache, runny nose, etc.
- Excludes severe cases: ICU, intubation, cardiac arrest, sepsis, etc.
- Configurable include/exclude term lists

### Batch Processing
- Configurable batch sizes for database queries and GTMF creation
- Memory-efficient processing of large datasets
- Resumable from partial progress

### LLM Judge with Few-Shot Examples
- Uses realistic dialogue examples as references
- Evaluates naturalness, medical appropriateness, progressive disclosure, safety
- Provides detailed feedback for improvement
- Supports iterative refinement (up to 3 attempts)

### Semantic Textual Similarity (STS)
- Compares EHR and dialogue summaries
- Uses sentence-transformers models
- Computes cosine similarity scores

## Statistics

The framework tracks:
- EHR cases retrieved and filtered
- GTMFs created and failed
- Profiles generated per type
- Dialogue success rates per attempt
- STS score distribution (mean, std, min, max)
- Correlations between judge scores and STS scores

## Example Configuration

```yaml
batching:
  db_batch_size: 100
  gtmf_batch_size: 32

experiment:
  num_admissions: 200
  profile_types: ["FULL", "NO_DIAGNOSIS", "NO_DIAGNOSIS_NO_TREATMENT"]

judge:
  max_attempts: 3
  threshold_score: 0.75
```

## Design Principles

- **Minimal**: No unnecessary functions, classes, or code
- **Focused**: Only essential Python packages
- **Python-only**: No frontend/backend components
- **Agent-based**: Each major task is an agent
- **Configurable**: All parameters in config.yaml
- **Resumable**: Can continue from partial progress
- **Comprehensive**: Full statistics and logging

## License

[Your License]
