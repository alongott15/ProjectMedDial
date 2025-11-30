# Synthetic Patient-Physician Conversation Framework

## Overview

This framework generates realistic synthetic patient-physician dialogues from clinical EHR data. It implements:

- **Flexible data sources** - Works with CSV files (default) or PostgreSQL database
- **Light case filtering** - Focuses on common, non-severe medical conditions
- **Batched GTMF creation** - Scalable extraction of medical forms from EHR notes
- **LLM-based judge** - Evaluates dialogue naturalness with iterative improvement
- **Profile variants** - Generates multiple profile types (FULL, NO_DIAGNOSIS, NO_DIAGNOSIS_NO_TREATMENT)
- **STS evaluation** - Measures semantic similarity between EHR and dialogue summaries
- **Bias-aware prompting** - Reduces hallucinations throughout the pipeline
- **Comprehensive statistics** - Tracks success rates, attempts, scores, and more

## Data Sources

The framework supports two data sources:

1. **CSV Files (Default)** - Easy to get started, no database required
   - Sample CSV included with 10 realistic clinical notes
   - Ideal for testing, development, and small-medium datasets
   - See [CSV Usage Guide](CSV_USAGE_GUIDE.md) for details

2. **PostgreSQL Database** - For production with large MIMIC-III datasets
   - Direct database connectivity
   - Efficient for very large datasets
   - Complex SQL filtering support

## Architecture

### Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. EHR Retrieval & Light Case Filtering                        │
│    - Fetch from MIMIC-III (batched)                            │
│    - Filter for light/common cases                             │
│    - Output: ehr_case_*.json                                   │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Batched GTMF Creation                                       │
│    - Extract structured medical forms                          │
│    - LLM judge quality assessment (optional)                   │
│    - Output: gtmf_*.json                                       │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. Profile Generation                                          │
│    - Create profile variants                                   │
│    - Validate and enhance profiles                             │
│    - Output: profile_*.json                                    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Iterative Dialogue Generation (max 3 attempts)             │
│    - Doctor + Patient agents simulate conversation             │
│    - Judge evaluates naturalness                               │
│    - Prompt improvement if unrealistic                          │
│    - Output: dialogue_*.json, judge_eval_*.json                │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5-6. Summarization                                              │
│    - EHR summary (bias-aware)                                  │
│    - Dialogue summary (bias-aware)                             │
│    - Output: ehr_summary_*.json, dialogue_summary_*.json       │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 7. STS Evaluation                                              │
│    - Semantic similarity between summaries                      │
│    - Output: sts_*.json                                        │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 8. Statistics Collection                                       │
│    - Per-profile stats                                         │
│    - Global aggregates                                         │
│    - Output: per_profile_stats.json, global_stats.json         │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

#### Agents
- **GTMFExtractionAgent** - Extracts Ground Truth Medical Forms from EHR notes
- **ProfileGeneratorAgent** - Creates profile variants for dialogue generation
- **DoctorAgent** - Simulates physician in conversation
- **PatientAgent** - Simulates patient in conversation
- **JudgeAgent** - Evaluates dialogue naturalness (LLM-based)
- **PromptImprovementAgent** - Improves prompts based on judge feedback
- **SummarizerAgent** - Creates summaries of EHR notes and dialogues

#### Utilities
- **LightCaseFilter** - Filters for common/light medical cases
- **STSEvaluator** - Computes semantic textual similarity
- **StatsCollector** - Tracks and aggregates pipeline statistics

#### Prompts
- **Bias-aware base prompt** - Shared across all agents to reduce hallucinations
- **Agent-specific prompts** - Specialized instructions for each agent type

## Installation

### Requirements

```bash
# Python 3.10+
pip install -r requirements.txt
```

#### Required Packages

```
# Core
pydantic>=2.0
python-dotenv
sqlalchemy
psycopg2-binary

# Azure AI
azure-ai-inference
azure-core

# NLP/ML
sentence-transformers
scikit-learn

# Configuration
pyyaml

# Testing (optional)
pytest
```

### Environment Setup

Create a `.env` file:

```bash
# Azure AI Foundry (Required)
AZURE_AI_ENDPOINT=<your_endpoint>
AZURE_AI_API_KEY=<your_api_key>

# Database (Optional - only if using database source)
DATABASE_URL=postgresql://user:password@host:port/mimic
```

## Usage

### Quick Start (CSV Mode - No Database Required)

```bash
# Run with default configuration (uses sample CSV)
python synthetic_dialogue_pipeline.py

# Sample CSV is automatically created if it doesn't exist
# Contains 10 realistic clinical notes with light symptoms
```

### Quick Start (Database Mode)

```bash
# 1. Set DATABASE_URL environment variable
export DATABASE_URL=postgresql://user:password@host:port/mimic

# 2. Update config to use database
# Edit config/default_config.yaml:
# data_source:
#   source_type: database

# 3. Run pipeline
python synthetic_dialogue_pipeline.py
```

### Custom Configuration

```bash
# 1. Copy default config
cp config/default_config.yaml config/my_config.yaml

# 2. Edit my_config.yaml with your parameters

# 3. Run with custom config
# (Update the config_path in main() function)
python synthetic_dialogue_pipeline.py
```

### Configuration Options

See `config/default_config.yaml` for all options. Key parameters:

```yaml
data_source:
  source_type: csv  # "csv" or "database"
  csv_file_path: sample_mimic_notes.csv  # CSV file path (if csv)
  database_url: null  # PostgreSQL URL (if database)
  batch_size: 50  # EHR records per batch
  max_total_records: null  # null = all records

gtmf:
  gtmf_batch_size: 20  # GTMF processing batch size
  use_llm_judge: true

profile:
  profile_types:
    - NO_DIAGNOSIS_NO_TREATMENT  # Profile variants to generate

dialogue:
  max_turns: 16
  max_attempts_per_profile: 3  # Iterative refinement attempts

judge:
  threshold: 0.6  # Minimum score for realistic dialogue

sts:
  model_name: all-MiniLM-L6-v2  # Sentence transformer model
```

For detailed CSV usage, see [CSV Usage Guide](CSV_USAGE_GUIDE.md).

## Output Structure

```
outputs/
├── ehr/                    # Filtered EHR cases
│   └── ehr_case_<id>.json
├── gtmf/                   # Ground Truth Medical Forms
│   └── gtmf_<id>.json
├── profiles/               # Generated profiles
│   └── profile_<id>_<type>.json
├── dialogues/              # Final dialogues
│   └── dialogue_<id>.json
├── judge/                  # Judge evaluations
│   └── judge_eval_<id>_attempt<n>.json
├── summaries/              # EHR and dialogue summaries
│   ├── ehr_summary_<id>.json
│   └── dialogue_summary_<id>.json
├── sts/                    # STS evaluation results
│   └── sts_<id>.json
├── stats/                  # Statistics
│   ├── per_profile_stats.json
│   └── global_stats.json
└── runs/                   # Run summaries
    └── run_<name>.json
```

## Bias-Aware Prompting

All LLM calls use bias-aware prompts that:

- **Ground outputs** in provided context only
- **Acknowledge uncertainty** when information is missing
- **Avoid hallucinations** by not inventing diagnoses, treatments, or facts
- **Use neutral language** and avoid stereotypes
- **Emphasize research context** (not for clinical use)

Example base prompt (shared across all agents):

```
You are an AI assistant used in a research setting to simulate and analyze light medical cases.

You must base all your outputs only on the information provided in the input context
(EHR text, structured profile, or dialogue history).

If a relevant detail is not present in the input, you must say that it is not specified
or unknown, rather than guessing or inventing information.

Do not introduce new diagnoses, medications, test results, or patient attributes that
are not explicitly or implicitly supported by the context.

[...additional constraints...]
```

## Light Case Filtering

The framework focuses on **light, common medical cases** such as:

**Include:**
- Cough, sore throat, runny nose, nasal congestion
- Low-grade fever, chills, malaise, fatigue
- Headache, mild dizziness
- Flu-like symptoms, upper respiratory infections

**Exclude:**
- ICU-level cases (intubation, ventilation, cardiac arrest)
- Severe infections (sepsis, multi-organ failure)
- Life-threatening conditions (stroke, MI, malignancy)
- Major procedures (surgery, transplant)

## Statistics & Monitoring

The pipeline tracks:

- **Per-profile metrics**: attempts, success, judge scores, STS scores, processing time
- **Global aggregates**: success rate, average attempts, score distributions
- **Filter statistics**: light case filter pass rates
- **Timing**: average processing time per profile, total pipeline duration

View statistics:

```bash
# Automatically printed at end of run
# Also saved to outputs/stats/
cat outputs/stats/global_stats.json
```

## Extending the Framework

### Adding a New Agent

```python
from prompts.prompt_loader import get_prompt_loader

class MyCustomAgent:
    def __init__(self):
        prompt_loader = get_prompt_loader()
        self.system_prompt = prompt_loader.get_base_system_prompt()
        # Add agent-specific instructions
        self.system_prompt += "\n\nMy custom instructions..."
```

### Adding a New Profile Type

Edit `Agents/ProfileGeneratorAgent.py`:

```python
def generate_my_custom_profile(self, gtmf: Dict) -> Dict:
    profile = copy.deepcopy(gtmf)
    # Custom modifications...
    profile["profile_type"] = "MY_CUSTOM_TYPE"
    return profile
```

Update config:

```yaml
profile:
  profile_types:
    - MY_CUSTOM_TYPE
```

### Adding Few-Shot Examples for Judge

Create a JSON file with examples:

```json
{
  "realistic": [
    {
      "dialogue": "Doctor: Hello...\nPatient: Hi doctor...",
      "reason": "Natural conversation flow..."
    }
  ],
  "unrealistic": [
    {
      "dialogue": "...",
      "reason": "..."
    }
  ]
}
```

Load in pipeline:

```python
judge_agent.load_few_shot_examples("examples/medical_dialogues.json")
```

## Troubleshooting

### Common Issues

**Database connection errors:**
```bash
# Verify DATABASE_URL is set correctly
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL -c "SELECT COUNT(*) FROM noteevents;"
```

**Azure AI errors:**
```bash
# Verify credentials
echo $AZURE_AI_ENDPOINT
echo $AZURE_AI_API_KEY

# Check model availability
```

**Out of memory:**
```yaml
# Reduce batch sizes in config
database:
  db_batch_size: 10  # Reduce from 50
gtmf:
  gtmf_batch_size: 5  # Reduce from 20
```

**No cases pass light filter:**
```python
# Check filter settings in Utils/light_case_filter.py
# Adjust INCLUDE_TERMS and EXCLUDE_TERMS as needed
```

## Citation

If you use this framework, please cite:

```
[Your citation information]
```

## License

[Your license information]

## Contributing

[Contribution guidelines]

## Contact

[Contact information]
