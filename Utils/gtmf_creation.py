import json
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from utils import get_db_uri, format_date, calculate_age

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleGroundTruthGenerator:
    def __init__(self, db_session):
        self.session = db_session
    
    def generate_gt_profile(self, subject_id: int, hadm_id: int) -> dict:
        """Generate simple ground truth profile from structured data"""
        
        profile = {
            "subject_id": subject_id,
            "hadm_id": hadm_id,
            "diagnoses": self._get_diagnoses(hadm_id),
            "treatments": self._get_treatments(hadm_id),
            "medications": self._get_medications(hadm_id),
            "demographics": self._get_demographics(subject_id, hadm_id),
            "symptoms": self._get_symptoms(hadm_id)
        }
        
        return profile
    
    def _execute_query_safely(self, query, params):
        """Execute query with proper error handling"""
        try:
            result = self.session.execute(query, params).mappings().all()
            return result
        except Exception as e:
            logger.warning(f"Query failed: {e}")
            # Rollback the transaction to clear the error state
            self.session.rollback()
            return []
    
    def _execute_query_single_safely(self, query, params):
        """Execute query expecting single result with proper error handling"""
        try:
            result = self.session.execute(query, params).mappings().first()
            return result
        except Exception as e:
            logger.warning(f"Query failed: {e}")
            # Rollback the transaction to clear the error state
            self.session.rollback()
            return None
    
    def _get_diagnoses(self, hadm_id: int):
        """Get diagnosis names"""
        diagnoses = []
        
        query = text("""
            SELECT DISTINCT d.long_title
            FROM diagnoses_icd di
            JOIN d_icd_diagnoses d ON di.icd9_code = d.icd9_code
            WHERE di.hadm_id = :hadm_id
            AND d.long_title IS NOT NULL
        """)
        
        results = self._execute_query_safely(query, {"hadm_id": hadm_id})
        
        for result in results:
            if result["long_title"]:
                diagnoses.append({"name": result["long_title"]})
        
        return diagnoses
    
    def _get_treatments(self, hadm_id: int):
        """Get treatment names"""
        treatments = []
        
        query = text("""
            SELECT DISTINCT d.long_title
            FROM procedures_icd pi
            JOIN d_icd_procedures d ON pi.icd9_code = d.icd9_code
            WHERE pi.hadm_id = :hadm_id
            AND d.long_title IS NOT NULL
        """)
        
        results = self._execute_query_safely(query, {"hadm_id": hadm_id})
        
        for result in results:
            if result["long_title"]:
                treatments.append({"name": result["long_title"]})
        
        return treatments
    
    def _get_medications(self, hadm_id: int):
        """Get medication names"""
        medications = []
        
        query = text("""
            SELECT DISTINCT drug
            FROM prescriptions
            WHERE hadm_id = :hadm_id
            AND drug IS NOT NULL
            AND drug NOT ILIKE '%sodium chloride%'
            AND drug NOT ILIKE '%dextrose%'
            AND drug NOT ILIKE '%flush%'
        """)
        
        results = self._execute_query_safely(query, {"hadm_id": hadm_id})
        
        for result in results:
            if result["drug"]:
                medications.append({"name": result["drug"]})
        
        return medications
    
    def _get_demographics(self, subject_id: int, hadm_id: int):
        """Get demographics"""
        demographics = {}
        
        query = text("""
            SELECT p.gender, p.dob, a.admittime, a.dischtime,
                   a.insurance, a.ethnicity, a.admission_type
            FROM patients p
            JOIN admissions a ON p.subject_id = a.subject_id
            WHERE p.subject_id = :subject_id AND a.hadm_id = :hadm_id
        """)
        
        result = self._execute_query_single_safely(query, {
            "subject_id": subject_id,
            "hadm_id": hadm_id
        })
        
        if result:
            try:
                dob_formatted = format_date(result['dob'], '%Y-%m-%d')
                adm_formatted = format_date(result['admittime'], '%Y-%m-%d %H:%M:%S')
                age = calculate_age(dob_formatted, adm_formatted)
                
                demographics = {
                    "age": age,
                    "gender": result['gender'] or "not provided",
                    "ethnicity": result['ethnicity'] or "not provided",
                    "insurance": result['insurance'] or "not provided",
                    "admission_type": result['admission_type'] or "not provided"
                }
            except Exception as e:
                logger.warning(f"Error processing demographics data: {e}")
                demographics = {
                    "age": 0,
                    "gender": "not provided",
                    "ethnicity": "not provided",
                    "insurance": "not provided",
                    "admission_type": "not provided"
                }
        
        return demographics
    
    def _get_symptoms(self, hadm_id: int):
        """Get symptoms from chart events"""
        symptoms = []
        
        query = text("""
            SELECT DISTINCT d.label, c.value
            FROM chartevents c
            JOIN d_items d ON c.itemid = d.itemid
            WHERE c.hadm_id = :hadm_id
            AND c.value IS NOT NULL
            AND c.value != ''
            AND (d.label ILIKE '%pain%' OR d.label ILIKE '%nausea%' OR 
                 d.label ILIKE '%fever%' OR d.label ILIKE '%cough%')
            LIMIT 10
        """)
        
        results = self._execute_query_safely(query, {"hadm_id": hadm_id})
        
        for result in results:
            if result["label"] and result["value"]:
                symptoms.append({
                    "description": f"{result['label']}: {result['value']}"
                })
        
        return symptoms

def generate_gt_profiles(session, patient_list: list, output_file: str = None):
    """Generate ground truth profiles for multiple patients with proper error handling"""
    
    generator = SimpleGroundTruthGenerator(session)
    profiles = []
    
    logger.info(f"Generating GT profiles for {len(patient_list)} patients")
    
    for i, (subject_id, hadm_id) in enumerate(patient_list):
        try:
            # Create a savepoint before processing each patient
            savepoint = session.begin_nested()
            
            try:
                profile = generator.generate_gt_profile(subject_id, hadm_id)
                profiles.append(profile)
                savepoint.commit()
                logger.info(f"Generated profile {i+1}/{len(patient_list)}")
                
            except Exception as e:
                logger.error(f"Error generating profile for patient {subject_id}, {hadm_id}: {e}")
                savepoint.rollback()
                continue
                
        except Exception as e:
            logger.error(f"Transaction error for patient {subject_id}, {hadm_id}: {e}")
            # Roll back the entire session and continue
            session.rollback()
            continue
    
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(profiles, f, indent=2)
        logger.info(f"GT profiles saved to {output_file}")
    
    return profiles

def get_patients(session, limit: int = 30):
    """Get patients with data"""
    
    query = text("""
        SELECT DISTINCT p.subject_id, a.hadm_id
        FROM patients p
        JOIN admissions a ON p.subject_id = a.subject_id
        JOIN diagnoses_icd di ON a.hadm_id = di.hadm_id
        JOIN prescriptions pr ON a.hadm_id = pr.hadm_id
        WHERE p.dob IS NOT NULL
        AND a.admittime IS NOT NULL
        LIMIT :limit
    """)
    
    try:
        results = session.execute(query, {"limit": limit}).mappings().all()
        patient_list = [(row["subject_id"], row["hadm_id"]) for row in results]
        logger.info(f"Found {len(patient_list)} patients")
        return patient_list
        
    except Exception as e:
        logger.error(f"Error fetching patients: {e}")
        session.rollback()
        return []

def main():
    logger.info("Starting GT profile generation")
    
    engine = create_engine(get_db_uri())
    Session = sessionmaker(bind=engine)
    
    try:
        with Session() as session:
            patients = get_patients(session, limit=20)
            
            if not patients:
                logger.error("No patients found")
                return
            
            profiles = generate_gt_profiles(
                session, 
                patients, 
                output_file='gt_profiles.json'
            )
            
            print(f"\n=== GT Profile Generation Complete ===")
            print(f"Generated {len(profiles)} profiles")
            print(f"Saved to: gt_profiles.json")
            
            if profiles:
                sample = profiles[0]
                print(f"\nSample counts:")
                print(f"- Diagnoses: {len(sample['diagnoses'])}")
                print(f"- Treatments: {len(sample['treatments'])}")
                print(f"- Medications: {len(sample['medications'])}")
                print(f"- Symptoms: {len(sample['symptoms'])}")
                
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == '__main__':
    main()