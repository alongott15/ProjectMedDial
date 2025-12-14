import logging
import pandas as pd
from pathlib import Path
from Utils.markdown_gtmf import save_gtmf_markdown
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CSVDataLoader:
    def __init__(self, csv_dir: str):
        self.csv_dir = Path(csv_dir)
        if not self.csv_dir.exists():
            raise ValueError(f"CSV directory not found: {csv_dir}")

        self._noteevents = None
        self._patients = None
        self._admissions = None

    @property
    def noteevents(self) -> pd.DataFrame:
        if self._noteevents is None:
            csv_path = self.csv_dir / "NOTEEVENTS.csv"
            self._noteevents = pd.read_csv(csv_path, low_memory=False)
        return self._noteevents

    @property
    def patients(self) -> pd.DataFrame:
        if self._patients is None:
            csv_path = self.csv_dir / "PATIENTS.csv"
            self._patients = pd.read_csv(csv_path)
        return self._patients

    @property
    def admissions(self) -> pd.DataFrame:
        if self._admissions is None:
            csv_path = self.csv_dir / "ADMISSIONS.csv"
            self._admissions = pd.read_csv(csv_path)
        return self._admissions

    def fetch_notes(
        self,
        category_filter: str = "Discharge summary",
        text_filter: str = "Chief Complaint",
        limit: int = 100
    ) -> list[dict]:
        notes = self.noteevents.copy()

        if category_filter:
            notes = notes[notes['CATEGORY'].str.contains(category_filter, case=False, na=False)]

        if text_filter:
            notes = notes[notes['TEXT'].str.contains(text_filter, case=False, na=False)]

        notes = notes.head(limit)

        results = []
        for _, note_row in notes.iterrows():
            subject_id = note_row['SUBJECT_ID']
            hadm_id = note_row['HADM_ID']

            patient_row = self.patients[self.patients['SUBJECT_ID'] == subject_id]
            if patient_row.empty:
                continue
            patient_row = patient_row.iloc[0]

            admission_row = self.admissions[
                (self.admissions['SUBJECT_ID'] == subject_id) &
                (self.admissions['HADM_ID'] == hadm_id)
            ]
            if admission_row.empty:
                continue
            admission_row = admission_row.iloc[0]

            result = {
                'row_id': note_row.get('ROW_ID'),
                'subject_id': int(subject_id),
                'hadm_id': int(hadm_id),
                'text': note_row.get('TEXT', ''),
                'category': note_row.get('CATEGORY', ''),
                'gender': patient_row.get('GENDER', ''),
                'dob': patient_row.get('DOB', ''),
                'admittime': admission_row.get('ADMITTIME', ''),
                'dischtime': admission_row.get('DISCHTIME', ''),
                'religion': admission_row.get('RELIGION', ''),
                'marital_status': admission_row.get('MARITAL_STATUS', ''),
                'ethnicity': admission_row.get('ETHNICITY', ''),
                'insurance': admission_row.get('INSURANCE', ''),
                'admission_type': admission_row.get('ADMISSION_TYPE', '')
            }

            results.append(result)

        return results

    def fetch_notes_with_light_case_filter(
        self,
        category_filter: str = "Discharge summary",
        limit: int = 100,
        light_case_include_terms: list[str] = None,
        light_case_exclude_terms: list[str] = None
    ) -> list[dict]:
        from gtmf_creation import is_light_common_case

        all_notes = self.fetch_notes(
            category_filter=category_filter,
            text_filter="",
            limit=limit * 3
        )

        light_case_notes = []
        for note in all_notes:
            filter_result = is_light_common_case(note['text'])
            if filter_result['passed']:
                note['light_case_filter'] = filter_result
                light_case_notes.append(note)

            if len(light_case_notes) >= limit:
                break

        return light_case_notes


def csv_to_gtmf_workflow(csv_dir: str, output_path: str, limit: int = 50):
    from gtmf_creation import AzureAIClient, process_notes
    import json

    loader = CSVDataLoader(csv_dir)

    notes = loader.fetch_notes_with_light_case_filter(
        category_filter="Discharge summary",
        limit=limit
    )

    if not notes:
        logger.error("No light case notes found")
        return {}

    azure_client = AzureAIClient()

    output_dir = os.path.dirname(output_path) if os.path.dirname(output_path) else 'gtmf'
    quality_summary = process_notes(notes, azure_client, output_dir)

    summary_path = os.path.join(output_dir, 'processing_summary.json')
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(quality_summary, f, indent=2)

    return quality_summary


if __name__ == "__main__":
    csv_dir = "/path/to/mimic-iii/csv"
    output_path = "gtmf"

    summary = csv_to_gtmf_workflow(
        csv_dir=csv_dir,
        output_path=output_path,
        limit=50
    )

    print(f"\nGTMFs created: {summary.get('gtmfs_created', 0)}")
    print(f"Light cases: {summary.get('light_case_passed', 0)}")
