"""EHR Retrieval Agent - Retrieves and filters EHR cases from MIMIC-III"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from utils.light_case_filter import LightCaseFilter
from utils.utils import format_date, calculate_age

logger = logging.getLogger(__name__)


class EHRRetrievalAgent:
    """Retrieves EHR cases from PostgreSQL MIMIC-III database with light case filtering"""

    def __init__(self, db_uri: str, light_case_filter: LightCaseFilter, output_dir: str = "outputs/ehr"):
        self.db_uri = db_uri
        self.light_case_filter = light_case_filter
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(db_uri)
        self.Session = sessionmaker(bind=self.engine)

    def retrieve_batch(self, batch_size: int, offset: int = 0) -> List[Dict]:
        """Retrieve a batch of admissions from the database"""
        query = text("""
            SELECT
                n.row_id, n.subject_id, n.hadm_id, n.text, n.category,
                a.admittime, a.dischtime, a.religion, a.marital_status,
                a.ethnicity, a.insurance, a.admission_type,
                p.gender, p.dob
            FROM noteevents n
            JOIN admissions a ON n.hadm_id = a.hadm_id
            JOIN patients p ON n.subject_id = p.subject_id
            WHERE n.text IS NOT NULL
              AND n.category ILIKE '%Discharge%'
              AND LENGTH(n.text) > 500
            ORDER BY n.hadm_id
            LIMIT :limit OFFSET :offset
        """)

        try:
            with self.Session() as session:
                results = session.execute(query, {"limit": batch_size, "offset": offset}).mappings().all()
                logger.info(f"Retrieved {len(results)} cases from database (offset={offset})")
                return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error retrieving batch from database: {e}")
            return []

    def process_case(self, row: Dict) -> Dict:
        """Process a single EHR case"""
        dob_formatted = format_date(row.get('dob'), '%Y-%m-%d')
        adm_formatted = format_date(row.get('admittime'), '%Y-%m-%d %H:%M:%S')
        dis_formatted = format_date(row.get('dischtime'), '%Y-%m-%d %H:%M:%S')
        age = calculate_age(dob_formatted, adm_formatted)

        case = {
            "row_id": row.get('row_id'),
            "subject_id": row.get('subject_id'),
            "hadm_id": row.get('hadm_id'),
            "text": row.get('text'),
            "category": row.get('category'),
            "demographics": {
                "date_of_birth": dob_formatted,
                "age": age,
                "sex": row.get('gender', 'not provided'),
                "religion": row.get('religion', 'not provided'),
                "marital_status": row.get('marital_status', 'not provided'),
                "ethnicity": row.get('ethnicity', 'not provided'),
                "insurance": row.get('insurance', 'not provided'),
                "admission_type": row.get('admission_type', 'not provided'),
                "admission_date": adm_formatted,
                "discharge_date": dis_formatted
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

        return case

    def retrieve_and_filter(self, batch_size: int, total_limit: int = None) -> Generator[List[Dict], None, None]:
        """
        Retrieve and filter EHR cases in batches

        Yields batches of filtered cases
        """
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

            # Process and filter cases
            processed_cases = [self.process_case(row) for row in raw_cases]
            filtered_cases = self.light_case_filter.filter_cases(processed_cases)

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
