"""EHR Retrieval Agent - Retrieves and filters EHR cases from MIMIC-III CSV files"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Generator
import pandas as pd
from datetime import datetime
from utils.light_case_filter import LightCaseFilter

logger = logging.getLogger(__name__)


class EHRRetrievalAgent:
    """Retrieves EHR cases from MIMIC-III CSV files with light case filtering"""

    def __init__(self, csv_dir: str, light_case_filter: LightCaseFilter, output_dir: str = "outputs/ehr"):
        self.csv_dir = Path(csv_dir)
        self.light_case_filter = light_case_filter
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Verify CSV files exist
        self.noteevents_path = self.csv_dir / "NOTEEVENTS.csv"
        self.patients_path = self.csv_dir / "PATIENTS.csv"
        self.admissions_path = self.csv_dir / "ADMISSIONS.csv"

        if not self.noteevents_path.exists():
            raise FileNotFoundError(f"NOTEEVENTS.csv not found in {csv_dir}")
        if not self.patients_path.exists():
            raise FileNotFoundError(f"PATIENTS.csv not found in {csv_dir}")
        if not self.admissions_path.exists():
            raise FileNotFoundError(f"ADMISSIONS.csv not found in {csv_dir}")

        logger.info(f"Initialized EHRRetrievalAgent with CSV directory: {csv_dir}")

    def load_csv_data(self):
        """Load MIMIC-III CSV files"""
        logger.info("Loading MIMIC-III CSV files...")

        # Load notes
        logger.info("Loading NOTEEVENTS.csv...")
        self.notes_df = pd.read_csv(
            self.noteevents_path,
            usecols=['ROW_ID', 'SUBJECT_ID', 'HADM_ID', 'CATEGORY', 'TEXT'],
            low_memory=False
        )

        # Load patients
        logger.info("Loading PATIENTS.csv...")
        self.patients_df = pd.read_csv(
            self.patients_path,
            usecols=['SUBJECT_ID', 'GENDER', 'DOB'],
            low_memory=False
        )

        # Load admissions
        logger.info("Loading ADMISSIONS.csv...")
        self.admissions_df = pd.read_csv(
            self.admissions_path,
            usecols=['HADM_ID', 'SUBJECT_ID', 'ADMITTIME', 'DISCHTIME',
                     'RELIGION', 'MARITAL_STATUS', 'ETHNICITY', 'INSURANCE', 'ADMISSION_TYPE'],
            low_memory=False
        )

        logger.info(f"Loaded {len(self.notes_df)} notes, {len(self.patients_df)} patients, {len(self.admissions_df)} admissions")

    def calculate_age(self, dob_str: str, admit_str: str) -> int:
        """Calculate age from date of birth and admission date"""
        try:
            dob = pd.to_datetime(dob_str)
            admit = pd.to_datetime(admit_str)
            age = (admit - dob).days // 365
            return max(0, age)
        except:
            return 0

    def format_date(self, date_str: str, format_type: str = 'date') -> str:
        """Format date string"""
        try:
            date = pd.to_datetime(date_str)
            if format_type == 'date':
                return date.strftime('%Y-%m-%d')
            else:
                return date.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return "not provided"

    def retrieve_batch(self, batch_size: int, offset: int = 0) -> List[Dict]:
        """Retrieve a batch of admissions"""
        # Filter notes for discharge summaries with text
        discharge_notes = self.notes_df[
            (self.notes_df['CATEGORY'].str.contains('Discharge', case=False, na=False)) &
            (self.notes_df['TEXT'].notna()) &
            (self.notes_df['TEXT'].str.len() > 500) &
            (self.notes_df['HADM_ID'].notna())
        ].copy()

        # Apply batch offset and size
        batch_notes = discharge_notes.iloc[offset:offset + batch_size]

        if len(batch_notes) == 0:
            return []

        # Merge with admissions and patients
        merged = batch_notes.merge(
            self.admissions_df,
            on=['HADM_ID', 'SUBJECT_ID'],
            how='left'
        ).merge(
            self.patients_df,
            on='SUBJECT_ID',
            how='left'
        )

        cases = []
        for _, row in merged.iterrows():
            case = {
                'row_id': int(row['ROW_ID']) if pd.notna(row['ROW_ID']) else 0,
                'subject_id': int(row['SUBJECT_ID']) if pd.notna(row['SUBJECT_ID']) else 0,
                'hadm_id': int(row['HADM_ID']) if pd.notna(row['HADM_ID']) else 0,
                'text': str(row['TEXT']) if pd.notna(row['TEXT']) else "",
                'category': str(row['CATEGORY']) if pd.notna(row['CATEGORY']) else "",
                'demographics': {
                    'date_of_birth': self.format_date(row['DOB'], 'date'),
                    'age': self.calculate_age(row['DOB'], row['ADMITTIME']),
                    'sex': str(row['GENDER']) if pd.notna(row['GENDER']) else 'not provided',
                    'religion': str(row['RELIGION']) if pd.notna(row['RELIGION']) else 'not provided',
                    'marital_status': str(row['MARITAL_STATUS']) if pd.notna(row['MARITAL_STATUS']) else 'not provided',
                    'ethnicity': str(row['ETHNICITY']) if pd.notna(row['ETHNICITY']) else 'not provided',
                    'insurance': str(row['INSURANCE']) if pd.notna(row['INSURANCE']) else 'not provided',
                    'admission_type': str(row['ADMISSION_TYPE']) if pd.notna(row['ADMISSION_TYPE']) else 'not provided',
                    'admission_date': self.format_date(row['ADMITTIME'], 'datetime'),
                    'discharge_date': self.format_date(row['DISCHTIME'], 'datetime')
                }
            }

            # Extract chief complaint if available
            text_lower = case["text"].lower()
            chief_complaint = ""
            if "chief complaint" in text_lower:
                start_idx = text_lower.find("chief complaint")
                end_idx = text_lower.find("\n", start_idx + 100)
                if end_idx > start_idx:
                    chief_complaint = case["text"][start_idx:end_idx].strip()

            case["chief_complaint"] = chief_complaint
            cases.append(case)

        logger.info(f"Retrieved {len(cases)} cases from CSV (offset={offset})")
        return cases

    def retrieve_and_filter(self, batch_size: int, total_limit: int = None) -> Generator[List[Dict], None, None]:
        """
        Retrieve and filter EHR cases in batches

        Yields batches of filtered cases
        """
        # Load CSV data once
        self.load_csv_data()

        offset = 0
        total_retrieved = 0
        total_filtered = 0

        while True:
            # Check if we've reached the total limit
            if total_limit and total_filtered >= total_limit:
                logger.info(f"Reached total limit of {total_limit} cases")
                break

            # Retrieve batch
            raw_cases = self.retrieve_batch(batch_size, offset)
            if not raw_cases:
                logger.info("No more cases to retrieve")
                break

            # Filter cases
            filtered_cases = self.light_case_filter.filter_cases(raw_cases)

            total_retrieved += len(raw_cases)
            total_filtered += len(filtered_cases)

            logger.info(f"Batch summary: Retrieved {len(raw_cases)}, Filtered to {len(filtered_cases)} light cases")
            logger.info(f"Total so far: {total_retrieved} retrieved, {total_filtered} filtered")

            if filtered_cases:
                yield filtered_cases

            offset += batch_size

        logger.info(f"EHR retrieval complete: {total_retrieved} total retrieved, {total_filtered} light cases")

    def save_case(self, case: Dict) -> str:
        """Save a single EHR case to JSON"""
        filename = f"ehr_case_{case['subject_id']}_{case['hadm_id']}.json"
        filepath = self.output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(case, f, indent=2)

        return str(filepath)

    def save_cases(self, cases: List[Dict]) -> List[str]:
        """Save multiple EHR cases to JSON"""
        filepaths = []
        for case in cases:
            try:
                filepath = self.save_case(case)
                filepaths.append(filepath)
            except Exception as e:
                logger.error(f"Error saving case {case.get('hadm_id')}: {e}")

        logger.info(f"Saved {len(filepaths)} EHR cases to {self.output_dir}")
        return filepaths
