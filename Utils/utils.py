import os
import logging
from datetime import datetime
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

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
