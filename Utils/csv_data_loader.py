"""
CSV Data Loader - Alternative to SQL database access.

Provides functions to load MIMIC-III data from CSV files instead of PostgreSQL.
"""

import logging
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CSVDataLoader:
    """
    Load MIMIC-III data from CSV files.

    Expected CSV files:
    - NOTEEVENTS.csv: Clinical notes
    - PATIENTS.csv: Patient demographics
    - ADMISSIONS.csv: Admission records
    - DIAGNOSES_ICD.csv: ICD diagnosis codes
    - PROCEDURES_ICD.csv: ICD procedure codes
    - PRESCRIPTIONS.csv: Medication prescriptions
    - LABEVENTS.csv: Laboratory test results
    - D_ICD_DIAGNOSES.csv: Diagnosis code descriptions
    - D_ICD_PROCEDURES.csv: Procedure code descriptions
    - D_LABITEMS.csv: Lab item descriptions
    """

    def __init__(self, csv_dir: str):
        """
        Initialize CSV data loader.

        Args:
            csv_dir: Directory containing MIMIC-III CSV files
        """
        self.csv_dir = Path(csv_dir)
        if not self.csv_dir.exists():
            raise ValueError(f"CSV directory not found: {csv_dir}")

        logger.info(f"CSV data loader initialized with directory: {csv_dir}")

        # Lazy loading of dataframes - core tables
        self._noteevents = None
        self._patients = None
        self._admissions = None

        # Lazy loading - structured clinical data
        self._diagnoses_icd = None
        self._procedures_icd = None
        self._prescriptions = None
        self._labevents = None

        # Lazy loading - dictionary tables
        self._d_icd_diagnoses = None
        self._d_icd_procedures = None
        self._d_labitems = None

    @property
    def noteevents(self) -> pd.DataFrame:
        """Load NOTEEVENTS.csv if not already loaded."""
        if self._noteevents is None:
            csv_path = self.csv_dir / "NOTEEVENTS.csv"
            logger.info(f"Loading NOTEEVENTS from {csv_path}")
            self._noteevents = pd.read_csv(csv_path, low_memory=False)
            logger.info(f"Loaded {len(self._noteevents)} note records")
        return self._noteevents

    @property
    def patients(self) -> pd.DataFrame:
        """Load PATIENTS.csv if not already loaded."""
        if self._patients is None:
            csv_path = self.csv_dir / "PATIENTS.csv"
            logger.info(f"Loading PATIENTS from {csv_path}")
            self._patients = pd.read_csv(csv_path)
            logger.info(f"Loaded {len(self._patients)} patient records")
        return self._patients

    @property
    def admissions(self) -> pd.DataFrame:
        """Load ADMISSIONS.csv if not already loaded."""
        if self._admissions is None:
            csv_path = self.csv_dir / "ADMISSIONS.csv"
            logger.info(f"Loading ADMISSIONS from {csv_path}")
            self._admissions = pd.read_csv(csv_path)
            logger.info(f"Loaded {len(self._admissions)} admission records")
        return self._admissions

    @property
    def diagnoses_icd(self) -> pd.DataFrame:
        """Load DIAGNOSES_ICD.csv if not already loaded."""
        if self._diagnoses_icd is None:
            csv_path = self.csv_dir / "DIAGNOSES_ICD.csv"
            if csv_path.exists():
                logger.info(f"Loading DIAGNOSES_ICD from {csv_path}")
                self._diagnoses_icd = pd.read_csv(csv_path)
                logger.info(f"Loaded {len(self._diagnoses_icd)} diagnosis records")
            else:
                logger.warning(f"DIAGNOSES_ICD.csv not found, skipping")
                self._diagnoses_icd = pd.DataFrame()
        return self._diagnoses_icd

    @property
    def procedures_icd(self) -> pd.DataFrame:
        """Load PROCEDURES_ICD.csv if not already loaded."""
        if self._procedures_icd is None:
            csv_path = self.csv_dir / "PROCEDURES_ICD.csv"
            if csv_path.exists():
                logger.info(f"Loading PROCEDURES_ICD from {csv_path}")
                self._procedures_icd = pd.read_csv(csv_path)
                logger.info(f"Loaded {len(self._procedures_icd)} procedure records")
            else:
                logger.warning(f"PROCEDURES_ICD.csv not found, skipping")
                self._procedures_icd = pd.DataFrame()
        return self._procedures_icd

    @property
    def prescriptions(self) -> pd.DataFrame:
        """Load PRESCRIPTIONS.csv if not already loaded."""
        if self._prescriptions is None:
            csv_path = self.csv_dir / "PRESCRIPTIONS.csv"
            if csv_path.exists():
                logger.info(f"Loading PRESCRIPTIONS from {csv_path}")
                self._prescriptions = pd.read_csv(csv_path, low_memory=False)
                logger.info(f"Loaded {len(self._prescriptions)} prescription records")
            else:
                logger.warning(f"PRESCRIPTIONS.csv not found, skipping")
                self._prescriptions = pd.DataFrame()
        return self._prescriptions

    @property
    def labevents(self) -> pd.DataFrame:
        """Load LABEVENTS.csv if not already loaded."""
        if self._labevents is None:
            csv_path = self.csv_dir / "LABEVENTS.csv"
            if csv_path.exists():
                logger.info(f"Loading LABEVENTS from {csv_path}")
                # Only load necessary columns to save memory
                self._labevents = pd.read_csv(
                    csv_path,
                    usecols=['SUBJECT_ID', 'HADM_ID', 'ITEMID', 'VALUENUM', 'VALUEUOM', 'FLAG'],
                    low_memory=False
                )
                logger.info(f"Loaded {len(self._labevents)} lab event records")
            else:
                logger.warning(f"LABEVENTS.csv not found, skipping")
                self._labevents = pd.DataFrame()
        return self._labevents

    @property
    def d_icd_diagnoses(self) -> pd.DataFrame:
        """Load D_ICD_DIAGNOSES.csv if not already loaded."""
        if self._d_icd_diagnoses is None:
            csv_path = self.csv_dir / "D_ICD_DIAGNOSES.csv"
            if csv_path.exists():
                logger.info(f"Loading D_ICD_DIAGNOSES from {csv_path}")
                self._d_icd_diagnoses = pd.read_csv(csv_path)
                logger.info(f"Loaded {len(self._d_icd_diagnoses)} diagnosis definitions")
            else:
                logger.warning(f"D_ICD_DIAGNOSES.csv not found, skipping")
                self._d_icd_diagnoses = pd.DataFrame()
        return self._d_icd_diagnoses

    @property
    def d_icd_procedures(self) -> pd.DataFrame:
        """Load D_ICD_PROCEDURES.csv if not already loaded."""
        if self._d_icd_procedures is None:
            csv_path = self.csv_dir / "D_ICD_PROCEDURES.csv"
            if csv_path.exists():
                logger.info(f"Loading D_ICD_PROCEDURES from {csv_path}")
                self._d_icd_procedures = pd.read_csv(csv_path)
                logger.info(f"Loaded {len(self._d_icd_procedures)} procedure definitions")
            else:
                logger.warning(f"D_ICD_PROCEDURES.csv not found, skipping")
                self._d_icd_procedures = pd.DataFrame()
        return self._d_icd_procedures

    @property
    def d_labitems(self) -> pd.DataFrame:
        """Load D_LABITEMS.csv if not already loaded."""
        if self._d_labitems is None:
            csv_path = self.csv_dir / "D_LABITEMS.csv"
            if csv_path.exists():
                logger.info(f"Loading D_LABITEMS from {csv_path}")
                self._d_labitems = pd.read_csv(csv_path)
                logger.info(f"Loaded {len(self._d_labitems)} lab item definitions")
            else:
                logger.warning(f"D_LABITEMS.csv not found, skipping")
                self._d_labitems = pd.DataFrame()
        return self._d_labitems

    def get_structured_data_for_admission(self, subject_id: int, hadm_id: int) -> Dict:
        """
        Fetch all structured clinical data for a specific admission.

        Args:
            subject_id: Patient subject ID
            hadm_id: Hospital admission ID

        Returns:
            Dict with diagnoses, procedures, prescriptions, and lab results
        """
        structured_data = {
            'diagnoses': [],
            'procedures': [],
            'prescriptions': [],
            'lab_results': []
        }

        # Fetch ICD diagnoses
        if not self.diagnoses_icd.empty:
            diag_codes = self.diagnoses_icd[
                (self.diagnoses_icd['SUBJECT_ID'] == subject_id) &
                (self.diagnoses_icd['HADM_ID'] == hadm_id)
            ]

            for _, diag in diag_codes.iterrows():
                icd_code = diag.get('ICD9_CODE', '')
                # Get description from dictionary
                desc_row = self.d_icd_diagnoses[self.d_icd_diagnoses['ICD9_CODE'] == icd_code]
                description = desc_row.iloc[0]['LONG_TITLE'] if not desc_row.empty else icd_code

                structured_data['diagnoses'].append({
                    'icd9_code': icd_code,
                    'description': description,
                    'seq_num': int(diag.get('SEQ_NUM', 0))
                })

        # Fetch ICD procedures
        if not self.procedures_icd.empty:
            proc_codes = self.procedures_icd[
                (self.procedures_icd['SUBJECT_ID'] == subject_id) &
                (self.procedures_icd['HADM_ID'] == hadm_id)
            ]

            for _, proc in proc_codes.iterrows():
                icd_code = proc.get('ICD9_CODE', '')
                # Get description from dictionary
                desc_row = self.d_icd_procedures[self.d_icd_procedures['ICD9_CODE'] == icd_code]
                description = desc_row.iloc[0]['LONG_TITLE'] if not desc_row.empty else icd_code

                structured_data['procedures'].append({
                    'icd9_code': icd_code,
                    'description': description,
                    'seq_num': int(proc.get('SEQ_NUM', 0))
                })

        # Fetch prescriptions
        if not self.prescriptions.empty:
            meds = self.prescriptions[
                (self.prescriptions['SUBJECT_ID'] == subject_id) &
                (self.prescriptions['HADM_ID'] == hadm_id)
            ]

            for _, med in meds.iterrows():
                structured_data['prescriptions'].append({
                    'drug': med.get('DRUG', ''),
                    'drug_name_generic': med.get('DRUG_NAME_GENERIC', ''),
                    'dose_val_rx': med.get('DOSE_VAL_RX', ''),
                    'dose_unit_rx': med.get('DOSE_UNIT_RX', ''),
                    'route': med.get('ROUTE', '')
                })

        # Fetch lab results (limit to 20 most recent)
        if not self.labevents.empty and not self.d_labitems.empty:
            labs = self.labevents[
                (self.labevents['SUBJECT_ID'] == subject_id) &
                (self.labevents['HADM_ID'] == hadm_id) &
                (self.labevents['VALUENUM'].notna())
            ].head(20)

            for _, lab in labs.iterrows():
                itemid = lab.get('ITEMID')
                # Get lab item description
                item_row = self.d_labitems[self.d_labitems['ITEMID'] == itemid]
                label = item_row.iloc[0]['LABEL'] if not item_row.empty else f'Item {itemid}'

                structured_data['lab_results'].append({
                    'label': label,
                    'value': float(lab.get('VALUENUM', 0)),
                    'unit': lab.get('VALUEUOM', ''),
                    'flag': lab.get('FLAG', '')
                })

        logger.debug(f"Fetched structured data for admission {hadm_id}: "
                    f"{len(structured_data['diagnoses'])} diagnoses, "
                    f"{len(structured_data['procedures'])} procedures, "
                    f"{len(structured_data['prescriptions'])} prescriptions, "
                    f"{len(structured_data['lab_results'])} lab results")

        return structured_data

    def fetch_notes(
        self,
        category_filter: str = "Discharge summary",
        text_filter: str = "Chief Complaint",
        limit: int = 100,
        include_structured_data: bool = True
    ) -> List[Dict]:
        """
        Fetch notes matching criteria (similar to SQL query).

        Args:
            category_filter: Note category to filter by
            text_filter: Text pattern to search in note text
            limit: Maximum number of notes to return
            include_structured_data: If True, include diagnoses, procedures, prescriptions, and lab results

        Returns:
            List of dicts with note data joined with patient and admission info plus structured clinical data
        """
        logger.info(f"Fetching notes with category='{category_filter}', text_contains='{text_filter}'")

        # Filter notes
        notes = self.noteevents.copy()

        # Apply category filter
        if category_filter:
            notes = notes[notes['CATEGORY'].str.contains(category_filter, case=False, na=False)]

        # Apply text filter
        if text_filter:
            notes = notes[notes['TEXT'].str.contains(text_filter, case=False, na=False)]

        # Limit results
        notes = notes.head(limit)

        logger.info(f"Found {len(notes)} matching notes")

        # Join with patients and admissions
        results = []
        for _, note_row in notes.iterrows():
            subject_id = note_row['SUBJECT_ID']
            hadm_id = note_row['HADM_ID']

            # Get patient info
            patient_row = self.patients[self.patients['SUBJECT_ID'] == subject_id]
            if patient_row.empty:
                continue
            patient_row = patient_row.iloc[0]

            # Get admission info
            admission_row = self.admissions[
                (self.admissions['SUBJECT_ID'] == subject_id) &
                (self.admissions['HADM_ID'] == hadm_id)
            ]
            if admission_row.empty:
                continue
            admission_row = admission_row.iloc[0]

            # Combine data
            result = {
                'row_id': note_row.get('ROW_ID'),
                'subject_id': int(subject_id),
                'hadm_id': int(hadm_id),
                'text': note_row.get('TEXT', ''),
                'category': note_row.get('CATEGORY', ''),
                # Patient data
                'gender': patient_row.get('GENDER', ''),
                'dob': patient_row.get('DOB', ''),
                # Admission data
                'admittime': admission_row.get('ADMITTIME', ''),
                'dischtime': admission_row.get('DISCHTIME', ''),
                'religion': admission_row.get('RELIGION', ''),
                'marital_status': admission_row.get('MARITAL_STATUS', ''),
                'ethnicity': admission_row.get('ETHNICITY', ''),
                'insurance': admission_row.get('INSURANCE', ''),
                'admission_type': admission_row.get('ADMISSION_TYPE', '')
            }

            # Add structured clinical data if requested
            if include_structured_data:
                structured_data = self.get_structured_data_for_admission(subject_id, hadm_id)
                result['structured_data'] = structured_data

            results.append(result)

        logger.info(f"Returning {len(results)} complete records")
        return results

    def fetch_notes_with_light_case_filter(
        self,
        category_filter: str = "Discharge summary",
        limit: int = 100,
        light_case_include_terms: List[str] = None,
        light_case_exclude_terms: List[str] = None,
        include_structured_data: bool = True
    ) -> List[Dict]:
        """
        Fetch notes and apply light case filtering.

        Args:
            category_filter: Note category to filter by
            limit: Maximum number of notes to return
            light_case_include_terms: Terms that indicate light cases
            light_case_exclude_terms: Terms that indicate severe cases
            include_structured_data: If True, include diagnoses, procedures, prescriptions, and lab results

        Returns:
            List of dicts with note data (light cases only) plus structured clinical data
        """
        from gtmf_creation import LIGHT_CASE_INCLUDE_TERMS, LIGHT_CASE_EXCLUDE_TERMS, is_light_common_case

        # Use defaults if not provided
        if light_case_include_terms is None:
            light_case_include_terms = LIGHT_CASE_INCLUDE_TERMS
        if light_case_exclude_terms is None:
            light_case_exclude_terms = LIGHT_CASE_EXCLUDE_TERMS

        # Fetch all matching notes
        all_notes = self.fetch_notes(
            category_filter=category_filter,
            text_filter="",  # No text filter, we'll apply light case filter instead
            limit=limit * 3,  # Fetch more since we'll filter out many
            include_structured_data=include_structured_data
        )

        # Apply light case filter
        light_case_notes = []
        for note in all_notes:
            filter_result = is_light_common_case(note['text'])
            if filter_result['passed']:
                note['light_case_filter'] = filter_result
                light_case_notes.append(note)

            if len(light_case_notes) >= limit:
                break

        logger.info(f"Found {len(light_case_notes)} light case notes out of {len(all_notes)} total")
        return light_case_notes


def csv_to_gtmf_workflow(
    csv_dir: str,
    output_path: str,
    limit: int = 50,
    batch_size: int = 10
):
    """
    Complete workflow: Load CSV data -> Extract GTMFs -> Save results.

    Args:
        csv_dir: Directory with MIMIC-III CSV files
        output_path: Where to save GTMF JSON results
        limit: Max number of notes to process
        batch_size: Batch size for GTMF extraction

    Returns:
        Tuple of (structured_results, quality_summary)
    """
    from gtmf_creation import AzureAIClient, process_notes

    logger.info("Starting CSV to GTMF workflow")

    # Load CSV data
    loader = CSVDataLoader(csv_dir)

    # Fetch light case notes
    notes = loader.fetch_notes_with_light_case_filter(
        category_filter="Discharge summary",
        limit=limit
    )

    if not notes:
        logger.error("No light case notes found")
        return [], {}

    # Initialize Azure AI client
    azure_client = AzureAIClient()

    # Process notes to create GTMFs
    structured_results, quality_summary = process_notes(
        notes,
        azure_client,
        batch_size=batch_size
    )

    # Save results
    import json
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(structured_results, f, indent=2)

    logger.info(f"Saved {len(structured_results)} GTMFs to {output_path}")

    # Save quality summary
    summary_path = output_path.replace('.json', '_quality_summary.json')
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(quality_summary, f, indent=2)

    logger.info(f"Saved quality summary to {summary_path}")

    return structured_results, quality_summary


if __name__ == "__main__":
    # Example usage
    csv_dir = "/path/to/mimic-iii/csv"  # Update this path
    output_path = "gtmf/gtmf_from_csv.json"

    # Run workflow
    results, summary = csv_to_gtmf_workflow(
        csv_dir=csv_dir,
        output_path=output_path,
        limit=50,
        batch_size=10
    )

    print(f"\nProcessed {len(results)} notes")
    print(f"Light cases: {summary.get('light_case_passed', 0)}")
    print(f"High quality: {summary.get('high_quality', 0)}")
