"""
CSV data loader for MIMIC-III-like clinical notes.

This module provides functions to read clinical note data from CSV files
instead of requiring a PostgreSQL database connection.
"""

import logging
import csv
from typing import List, Dict, Iterator, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class CSVDataLoader:
    """Loads clinical note data from CSV files."""

    def __init__(self, csv_file_path: str):
        """
        Initialize CSV data loader.

        Args:
            csv_file_path: Path to CSV file containing clinical notes.

        Expected CSV columns:
            - row_id: Unique row identifier
            - subject_id: Patient identifier
            - hadm_id: Hospital admission identifier
            - text: Clinical note text
            - category: Note category (e.g., 'Discharge Summary')
            - admittime: Admission timestamp (optional)
            - dischtime: Discharge timestamp (optional)
            - gender: Patient gender (optional)
            - dob: Date of birth (optional)
            - religion: Patient religion (optional)
            - marital_status: Marital status (optional)
            - ethnicity: Ethnicity (optional)
            - insurance: Insurance type (optional)
            - admission_type: Type of admission (optional)
        """
        self.csv_file_path = Path(csv_file_path)

        if not self.csv_file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_file_path}")

        logger.info(f"CSV data loader initialized: {csv_file_path}")

    def load_all_notes(self) -> List[Dict]:
        """
        Load all notes from CSV file.

        Returns:
            List of dictionaries, each representing a clinical note.
        """
        notes = []

        with open(self.csv_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Convert to dict and handle any missing fields
                note = dict(row)

                # Ensure required fields
                if 'row_id' not in note or 'subject_id' not in note or 'text' not in note:
                    logger.warning(f"Skipping row with missing required fields: {note.get('row_id', 'unknown')}")
                    continue

                # Convert numeric fields
                try:
                    note['row_id'] = int(note.get('row_id', 0))
                    note['subject_id'] = int(note.get('subject_id', 0))
                    note['hadm_id'] = int(note.get('hadm_id', 0)) if note.get('hadm_id') else 0
                except ValueError as e:
                    logger.warning(f"Error converting numeric fields for row {note.get('row_id')}: {e}")
                    continue

                notes.append(note)

        logger.info(f"Loaded {len(notes)} notes from CSV file")
        return notes

    def load_notes_batched(self,
                          batch_size: int = 50,
                          max_total: Optional[int] = None,
                          offset: int = 0) -> Iterator[List[Dict]]:
        """
        Load notes from CSV in batches.

        Args:
            batch_size: Number of records per batch.
            max_total: Maximum total records to load (None = all).
            offset: Starting offset for pagination.

        Yields:
            Batches of note dictionaries.
        """
        logger.info(f"Starting batched CSV load: batch_size={batch_size}, max_total={max_total}, offset={offset}")

        all_notes = self.load_all_notes()

        # Apply offset
        if offset > 0:
            all_notes = all_notes[offset:]
            logger.info(f"Applied offset {offset}, {len(all_notes)} notes remaining")

        # Apply max_total limit
        if max_total is not None:
            all_notes = all_notes[:max_total]
            logger.info(f"Applied max_total limit {max_total}, {len(all_notes)} notes to process")

        # Yield batches
        fetched_total = 0
        for i in range(0, len(all_notes), batch_size):
            batch = all_notes[i:i + batch_size]

            if not batch:
                break

            logger.info(f"Yielding batch of {len(batch)} notes (total: {fetched_total + len(batch)})")
            yield batch

            fetched_total += len(batch)

        logger.info(f"Batched CSV load completed: {fetched_total} total records yielded")


def create_sample_csv(output_path: str = "sample_mimic_notes.csv", num_samples: int = 10):
    """
    Create a sample CSV file with synthetic clinical notes for testing.

    Args:
        output_path: Path for output CSV file.
        num_samples: Number of sample notes to generate.
    """
    logger.info(f"Creating sample CSV with {num_samples} notes: {output_path}")

    sample_notes = [
        {
            "row_id": i + 1,
            "subject_id": 10000 + i,
            "hadm_id": 20000 + i,
            "text": f"Chief Complaint: {complaint}\n\nHistory of Present Illness: {hpi}\n\nAssessment: {assessment}\n\nPlan: {plan}",
            "category": "Discharge Summary",
            "admittime": "2023-01-01 10:00:00",
            "dischtime": "2023-01-03 14:00:00",
            "gender": "M" if i % 2 == 0 else "F",
            "dob": f"19{70 + i % 30}-01-01",
            "religion": "NOT SPECIFIED",
            "marital_status": "SINGLE" if i % 3 == 0 else "MARRIED",
            "ethnicity": "WHITE",
            "insurance": "Private",
            "admission_type": "ELECTIVE"
        }
        for i, (complaint, hpi, assessment, plan) in enumerate([
            ("Cough and sore throat",
             "Patient presents with 3-day history of dry cough and sore throat. No fever. Symptoms worse in morning.",
             "Likely viral upper respiratory infection. Symptoms consistent with common cold.",
             "Symptomatic treatment. Rest, fluids, and OTC pain relievers as needed. Follow up if symptoms worsen."),

            ("Headache",
             "Patient reports persistent headache for 2 days. Describes as dull, bilateral. No visual changes. Relieved slightly by acetaminophen.",
             "Tension-type headache. No red flags for secondary causes.",
             "Continue acetaminophen or ibuprofen as needed. Stress management and adequate hydration recommended."),

            ("Mild fever and fatigue",
             "Patient with low-grade fever (100.5F) and fatigue for 2 days. Reports mild body aches. No respiratory symptoms.",
             "Likely viral syndrome. Self-limited illness expected.",
             "Rest, hydration, antipyretics as needed. Return if fever persists beyond 5 days or worsens."),

            ("Runny nose and nasal congestion",
             "Patient reports 4 days of runny nose and nasal congestion. Clear discharge. No facial pain or fever.",
             "Acute rhinitis, likely viral etiology.",
             "Supportive care. Nasal saline rinses. Decongestants if needed. Symptoms should resolve in 7-10 days."),

            ("Sore throat and mild cough",
             "Patient with sore throat for 3 days, now developing mild dry cough. Denies fever. Throat appears mildly erythematous.",
             "Viral pharyngitis with secondary cough.",
             "Symptomatic relief with throat lozenges and warm liquids. Monitor for bacterial superinfection."),

            ("Cough with clear sputum",
             "Patient reports productive cough with clear sputum for 5 days. No fever, no shortness of breath. Cough worse at night.",
             "Acute bronchitis, likely viral.",
             "Supportive care. Cough suppressants at bedtime if needed. Return if develops fever or dyspnea."),

            ("Mild dizziness",
             "Patient reports occasional mild dizziness when standing quickly. No syncope. Blood pressure stable.",
             "Likely orthostatic hypotension. Benign etiology.",
             "Increase fluid intake. Rise slowly from sitting/lying. Follow up if symptoms persist or worsen."),

            ("Fatigue and malaise",
             "Patient with 3 days of generalized fatigue and malaise. No specific localizing symptoms. Appetite decreased.",
             "Nonspecific viral syndrome.",
             "Rest and supportive care. Ensure adequate nutrition and hydration. Monitor for development of specific symptoms."),

            ("Low-grade fever and chills",
             "Patient reports intermittent low-grade fever (99-100F) and chills for 2 days. No other symptoms.",
             "Early viral illness.",
             "Symptomatic treatment. Monitor temperature. Return if fever persists or develops respiratory/GI symptoms."),

            ("Mild throat pain",
             "Patient with mild throat discomfort for 2 days. Worse with swallowing. No fever. Throat mildly red.",
             "Mild pharyngitis.",
             "Warm salt water gargles. Throat lozenges. Adequate hydration. Should resolve in 3-5 days.")
        ][:num_samples])
    ]

    # Write to CSV
    fieldnames = [
        "row_id", "subject_id", "hadm_id", "text", "category",
        "admittime", "dischtime", "gender", "dob",
        "religion", "marital_status", "ethnicity", "insurance", "admission_type"
    ]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sample_notes)

    logger.info(f"Sample CSV created: {output_path}")


def fetch_notes_from_csv(csv_file_path: str) -> List[Dict]:
    """
    Fetch all notes from a CSV file.

    Args:
        csv_file_path: Path to CSV file.

    Returns:
        List of note dictionaries.
    """
    loader = CSVDataLoader(csv_file_path)
    return loader.load_all_notes()


def fetch_notes_batched_from_csv(csv_file_path: str,
                                  batch_size: int = 50,
                                  max_total: Optional[int] = None,
                                  offset: int = 0) -> Iterator[List[Dict]]:
    """
    Fetch notes from CSV file in batches.

    Args:
        csv_file_path: Path to CSV file.
        batch_size: Number of records per batch.
        max_total: Maximum total records (None = all).
        offset: Starting offset.

    Yields:
        Batches of note dictionaries.
    """
    loader = CSVDataLoader(csv_file_path)
    yield from loader.load_notes_batched(batch_size, max_total, offset)
