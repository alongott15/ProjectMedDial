# CSV Usage Guide - Synthetic Dialogue Framework

## Overview

The synthetic patient-physician conversation framework supports two data sources:
1. **CSV files** (default, recommended for getting started)
2. **PostgreSQL database** (for production with MIMIC-III)

This guide covers CSV file usage.

## Quick Start with CSV

### 1. Using the Sample CSV

The framework automatically creates a sample CSV with 10 clinical notes if none exists:

```bash
# Run with default configuration (uses sample CSV)
python synthetic_dialogue_pipeline.py
```

The sample CSV (`sample_mimic_notes.csv`) contains realistic light-case clinical notes with:
- Cough and sore throat
- Headache
- Mild fever and fatigue
- Runny nose and nasal congestion
- Other common symptoms

### 2. Using Your Own CSV

#### CSV Format Requirements

Your CSV file must include these columns:

**Required:**
- `row_id` - Unique row identifier (integer)
- `subject_id` - Patient identifier (integer)
- `hadm_id` - Hospital admission identifier (integer)
- `text` - Full clinical note text (string)

**Optional:**
- `category` - Note category (e.g., "Discharge Summary")
- `admittime` - Admission timestamp
- `dischtime` - Discharge timestamp
- `gender` - Patient gender (M/F)
- `dob` - Date of birth
- `religion` - Patient religion
- `marital_status` - Marital status
- `ethnicity` - Ethnicity
- `insurance` - Insurance type
- `admission_type` - Type of admission

#### Example CSV Structure

```csv
row_id,subject_id,hadm_id,text,category,gender
1,10001,20001,"Chief Complaint: Cough and sore throat...","Discharge Summary","F"
2,10002,20002,"Chief Complaint: Headache...","Discharge Summary","M"
```

### 3. Configuration

Edit `config/default_config.yaml`:

```yaml
data_source:
  source_type: csv  # Use CSV files
  csv_file_path: my_clinical_notes.csv  # Your CSV file path
  batch_size: 50
  max_total_records: null  # Process all records
  offset: 0
```

Or create a custom config file:

```yaml
# my_config.yaml
run_name: my_csv_run

data_source:
  source_type: csv
  csv_file_path: /path/to/my/notes.csv
  batch_size: 20
  max_total_records: 100  # Process first 100 records
  offset: 0

# ... rest of configuration
```

## Creating CSV Files

### From MIMIC-III Database

If you have access to MIMIC-III in PostgreSQL, you can export to CSV:

```python
import pandas as pd
from sqlalchemy import create_engine

# Connect to MIMIC-III
engine = create_engine('postgresql://user:pass@host:port/mimic')

# Query clinical notes
query = """
    SELECT
        n.row_id,
        n.subject_id,
        n.hadm_id,
        n.text,
        n.category,
        a.admittime,
        a.dischtime,
        p.gender,
        p.dob,
        a.religion,
        a.marital_status,
        a.ethnicity,
        a.insurance,
        a.admission_type
    FROM noteevents n
    JOIN admissions a ON n.hadm_id = a.hadm_id
    JOIN patients p ON n.subject_id = p.subject_id
    WHERE n.category IN ('Discharge summary', 'Discharge Summary')
    LIMIT 1000
"""

df = pd.read_sql(query, engine)
df.to_csv('mimic_notes.csv', index=False)
```

### Programmatically

Use the provided utility function:

```python
from Utils.csv_loader import create_sample_csv

# Create sample with 50 notes
create_sample_csv('my_sample.csv', num_samples=50)
```

## Switching Between CSV and Database

### CSV Mode (Default)

```yaml
data_source:
  source_type: csv
  csv_file_path: sample_mimic_notes.csv
  batch_size: 50
```

### Database Mode

```yaml
data_source:
  source_type: database
  database_url: postgresql://user:password@host:port/mimic
  batch_size: 50
```

Or use environment variable:

```bash
export DATABASE_URL=postgresql://user:password@host:port/mimic
```

```yaml
data_source:
  source_type: database
  database_url: null  # Will use DATABASE_URL environment variable
  batch_size: 50
```

## CSV Data Validation

The CSV loader performs automatic validation:

1. **Required fields check**: Skips rows missing `row_id`, `subject_id`, or `text`
2. **Type conversion**: Converts numeric fields to integers
3. **Logging**: Warns about any problematic rows

Check logs for validation messages:

```
INFO - Loaded 95 notes from CSV file
WARNING - Skipping row with missing required fields: unknown
```

## Light Case Filtering with CSV

The light case filter works identically with CSV and database sources:

```python
# Automatically applied in pipeline
# Looks for light symptoms: cough, sore throat, fever, headache
# Excludes severe cases: ICU, sepsis, surgery, malignancy
```

View filtering results in logs:

```
INFO - Batch: 8/10 passed light case filter (80.0%)
INFO - Total EHR cases after filtering: 42
```

## Batch Processing with CSV

Configure batch sizes for memory management:

```yaml
data_source:
  batch_size: 50  # Load 50 notes at a time from CSV

gtmf:
  gtmf_batch_size: 20  # Process 20 GTMFs at a time
```

## Example Workflows

### Workflow 1: Test with Sample Data

```bash
# Use default sample CSV (10 notes)
python synthetic_dialogue_pipeline.py

# Check outputs
ls outputs/dialogues/
```

### Workflow 2: Process Custom CSV

```bash
# 1. Create config
cat > my_config.yaml <<EOF
run_name: my_test_run
data_source:
  source_type: csv
  csv_file_path: my_notes.csv
  batch_size: 20
  max_total_records: 50
EOF

# 2. Update pipeline to use config
# Edit synthetic_dialogue_pipeline.py main() function:
# config = PipelineConfig.from_yaml('my_config.yaml')

# 3. Run
python synthetic_dialogue_pipeline.py
```

### Workflow 3: Large CSV with Offset

Process a large CSV in chunks:

```yaml
# First run: records 0-100
data_source:
  csv_file_path: large_file.csv
  max_total_records: 100
  offset: 0
```

```yaml
# Second run: records 100-200
data_source:
  csv_file_path: large_file.csv
  max_total_records: 100
  offset: 100
```

## CSV File Best Practices

### 1. Text Formatting

Ensure clinical note text is properly escaped:

```csv
row_id,text
1,"Patient presents with cough.

History: 3-day duration.

Plan: Symptomatic treatment."
```

### 2. File Size

For large CSV files:
- Use batch processing (`batch_size: 50`)
- Set `max_total_records` to process incrementally
- Use `offset` for resumable processing

### 3. Character Encoding

Always use UTF-8 encoding:

```python
df.to_csv('notes.csv', index=False, encoding='utf-8')
```

### 4. Missing Data

Use empty strings for missing optional fields:

```csv
row_id,subject_id,text,religion,insurance
1,10001,"Note text...","","Private"
```

## Troubleshooting

### CSV File Not Found

```
WARNING - CSV file not found: sample_mimic_notes.csv. Creating sample CSV...
```

**Solution:** Sample CSV is automatically created. Or provide your own CSV path.

### Invalid CSV Format

```
WARNING - Skipping row with missing required fields: 42
```

**Solution:** Ensure `row_id`, `subject_id`, `hadm_id`, and `text` columns exist.

### Type Conversion Errors

```
WARNING - Error converting numeric fields for row 5: invalid literal for int()
```

**Solution:** Ensure `row_id`, `subject_id`, `hadm_id` contain numeric values.

### Empty CSV Results

```
INFO - Loaded 0 notes from CSV file
```

**Solution:** Check CSV file path and content. Verify file is not empty.

## Performance Considerations

### Memory Usage

CSV mode loads batches into memory:
- **Small files (<1000 notes)**: Use default `batch_size: 50`
- **Medium files (1000-10000)**: Use `batch_size: 20`
- **Large files (>10000)**: Use `batch_size: 10` and `max_total_records`

### Processing Speed

CSV is typically faster than database for:
- Small to medium datasets
- Testing and development
- Offline processing

Database is better for:
- Very large datasets (>100,000 records)
- Real-time production systems
- Complex filtering queries

## Complete Example

```python
# custom_csv_pipeline.py
from config import PipelineConfig, DataSourceConfig
from synthetic_dialogue_pipeline import SyntheticDialoguePipeline

# Create custom configuration
config = PipelineConfig(
    run_name="my_csv_experiment",
    data_source=DataSourceConfig(
        source_type="csv",
        csv_file_path="my_clinical_notes.csv",
        batch_size=25,
        max_total_records=100
    )
)

# Run pipeline
pipeline = SyntheticDialoguePipeline(config)
results = pipeline.run()

print(f"Processed {results['statistics']['profile_summary']['total_profiles']} profiles")
```

## Summary

**CSV mode advantages:**
- ✅ No database setup required
- ✅ Easy to get started
- ✅ Portable data files
- ✅ Simple testing and development
- ✅ Works offline

**When to use CSV:**
- Testing the framework
- Small to medium datasets
- Sharing data between systems
- No database access available

**When to use Database:**
- Large MIMIC-III datasets
- Production deployments
- Complex SQL filtering
- Real-time data access

For most users, **CSV mode is recommended** to get started quickly!
