import os
import logging
from datetime import datetime
from sqlalchemy import text
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# List of common symptoms
COMMON_SYMPTOMS = [
    'headache', 'fever', 'cough', 'chest pain', 'shortness of breath', 
    'nausea', 'vomiting', 'dizziness', 'abdominal pain', 'fatigue',
    'sore throat', 'diarrhea', 'constipation', 'back pain', 'joint pain',
    'rash', 'swelling', 'weight loss', 'weight gain', 'insomnia',
    'anxiety', 'depression', 'confusion', 'blurred vision', 
    'loss of appetite', 'palpitations', 'sweating', 'chills', 'tingling'
]

def get_db_uri() -> str:
    """
    Retrieve the database URI from environment variables.
    
    Returns:
        str: The database connection URL.
    """
    uri = os.getenv('DATABASE_URL')
    if not uri:
        logger.error("DATABASE_URL not set in environment variables")
    else:
        logger.info("DATABASE_URL successfully retrieved")
    return uri

def format_date(dt, fmt: str) -> str:
    """
    Format a datetime object as a string.
    
    Args:
        dt: A datetime object or a value convertible to a string.
        fmt (str): The format string (e.g., '%Y-%m-%d').
    
    Returns:
        str: Formatted date string or a default message.
    """
    formatted = dt.strftime(fmt) if hasattr(dt, 'strftime') else str(dt or 'Not provided')
    logger.debug(f"Formatted date: {formatted}")
    return formatted

def build_symptom_conditions() -> str:
    """
    Construct a SQL condition string for filtering notes based on common symptoms.
    
    Returns:
        str: A condition string with OR concatenated ILIKE clauses.
    """
    condition = " OR ".join([f"n.text ILIKE '%{symptom}%'" for symptom in COMMON_SYMPTOMS])
    logger.debug(f"Symptom conditions: {condition}")
    return condition

def calculate_age(birth_date_str: str, admission_date_str: str) -> int:
    """
    Calculate the age of the patient at admission.
    
    Args:
        birth_date_str (str): Birth date in '%Y-%m-%d' format.
        admission_date_str (str): Admission date in '%Y-%m-%d %H:%M:%S' format.
    
    Returns:
        int: Patient age at admission.
    """
    try:
        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d')
        admission_date = datetime.strptime(admission_date_str, '%Y-%m-%d %H:%M:%S')
        age = admission_date.year - birth_date.year
        if (admission_date.month, admission_date.day) < (birth_date.month, birth_date.day):
            age -= 1
        logger.info(f"Calculated age: {age} (Birth: {birth_date_str}, Admission: {admission_date_str})")
        return age
    except Exception as e:
        logger.error(f"Error calculating age: {e}")
        return -1
    
def fetch_notes(session):
    """
    Fetch notes from the MIMIC-III database matching specified criteria.
    
    Args:
        session: An active SQLAlchemy session.
    
    Returns:
        list: List of dictionary-mapped rows from the database.
    """
    logger.info("Fetching notes from database")
    symptom_conditions = build_symptom_conditions()
    # Fixed query: ensure proper comma separation between columns.
    query = text(f"""
        SELECT n.row_id, n.subject_id, n.hadm_id, n.text, 
               a.admittime, a.dischtime, a.subject_id, a.religion, a.marital_status, a.ethnicity, a.insurance, a.admission_type,
               p.gender, p.dob, n.category
        FROM noteevents n
        JOIN admissions a ON n.hadm_id = a.hadm_id
        JOIN patients p ON n.subject_id = p.subject_id
        WHERE n.text ILIKE :keyword
          AND ({symptom_conditions})
          AND n.category ILIKE :category
        LIMIT 5
    """)
    params = {'keyword': '%Chief Complaint%', 'category': '%Discharge Summary%'}
    try:
        results = session.execute(query, params).mappings().all()
        logger.info(f"Fetched {len(results)} notes from database")
        return results
    except Exception as e:
        logger.error(f"Error fetching notes: {e}")
        return []
