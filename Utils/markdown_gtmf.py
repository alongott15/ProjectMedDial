"""
Utilities for reading and writing GTMFs in Markdown format.
Provides human-readable, version-control-friendly GTMF storage.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Any


def gtmf_to_markdown(gtmf: Dict[str, Any]) -> str:
    """
    Convert a GTMF dictionary to Markdown format.

    Args:
        gtmf: GTMF dictionary with standard fields

    Returns:
        Markdown-formatted string
    """
    lines = []

    # Title
    lines.append("# Ground Truth Medical Form (GTMF)\n")

    # Patient Information
    lines.append("## Patient Information\n")
    subject_id = gtmf.get('subject_id', 'N/A')
    hadm_id = gtmf.get('hadm_id', 'N/A')
    profile_type = gtmf.get('profile_type', 'FULL')
    lines.append(f"- **Subject ID**: {subject_id}")
    lines.append(f"- **Admission ID**: {hadm_id}")
    lines.append(f"- **Profile Type**: {profile_type}\n")

    # Demographics
    demo = gtmf.get('Context_Fields', {}).get('Patient_Demographics', {})
    if demo:
        lines.append("## Demographics\n")
        lines.append(f"- **Age**: {demo.get('Age', 'N/A')}")
        lines.append(f"- **Sex**: {demo.get('Sex', 'N/A')}\n")

    # Chief Complaint
    chief_complaint = gtmf.get('Additional_Context', {}).get('Chief_Complaint', '')
    if chief_complaint:
        lines.append("## Chief Complaint\n")
        lines.append(f"{chief_complaint}\n")

    # Symptoms
    symptoms = gtmf.get('Core_Fields', {}).get('Symptoms', [])
    if symptoms:
        lines.append("## Symptoms\n")
        for symptom in symptoms:
            if isinstance(symptom, dict):
                desc = symptom.get('description', str(symptom))
            else:
                desc = str(symptom)
            lines.append(f"- {desc}")
        lines.append("")

    # Medical History
    history = gtmf.get('Context_Fields', {}).get('Medical_History', {})
    if history:
        lines.append("## Medical History\n")
        past_history = history.get('Past_Medical_History', '')
        if past_history:
            lines.append(f"- **Past Medical History**: {past_history}")

        family_history = history.get('Family_History', '')
        if family_history:
            lines.append(f"- **Family History**: {family_history}")

        social_history = history.get('Social_History', '')
        if social_history:
            lines.append(f"- **Social History**: {social_history}")
        lines.append("")

    # Allergies
    allergies = gtmf.get('Context_Fields', {}).get('Allergies', [])
    if allergies:
        lines.append("## Allergies\n")
        allergies_str = ', '.join(allergies) if isinstance(allergies, list) else str(allergies)
        lines.append(f"{allergies_str}\n")

    # Current Medications
    meds = gtmf.get('Context_Fields', {}).get('Current_Medications', [])
    if meds:
        lines.append("## Current Medications\n")
        for med in meds:
            if isinstance(med, dict):
                med_name = med.get('name', str(med))
            else:
                med_name = str(med)
            lines.append(f"- {med_name}")
        lines.append("")

    # Lab Results
    labs = gtmf.get('lab_results', [])
    if labs:
        lines.append("## Lab Results\n")
        for lab in labs[:10]:  # Limit to first 10
            label = lab.get('label', 'Unknown')
            value = lab.get('valuenum', lab.get('value', ''))
            unit = lab.get('valueuom', '')
            lines.append(f"- {label}: {value} {unit}".strip())
        lines.append("")

    # Diagnoses (if in profile type)
    diagnoses = gtmf.get('Core_Fields', {}).get('Diagnoses', [])
    if diagnoses:
        lines.append("## Diagnoses\n")
        for diag in diagnoses:
            if isinstance(diag, dict):
                desc = diag.get('description', str(diag))
            else:
                desc = str(diag)
            lines.append(f"- {desc}")
        lines.append("")

    # Treatment Options (if in profile type)
    treatments = gtmf.get('Core_Fields', {}).get('Treatment_Options', [])
    if treatments:
        lines.append("## Treatment Options\n")
        for tx in treatments:
            if isinstance(tx, dict):
                desc = tx.get('description', str(tx))
            else:
                desc = str(tx)
            lines.append(f"- {desc}")
        lines.append("")

    # Structured Data Section
    has_structured = False
    structured_lines = ["## Structured Clinical Data\n"]

    # Structured Diagnoses
    struct_diag = gtmf.get('structured_diagnoses', [])
    if struct_diag:
        has_structured = True
        structured_lines.append("### ICD-9 Diagnoses\n")
        for diag in struct_diag[:10]:
            code = diag.get('icd9_code', '')
            desc = diag.get('description', '')
            structured_lines.append(f"- **{code}**: {desc}")
        structured_lines.append("")

    # Structured Procedures
    struct_proc = gtmf.get('structured_procedures', [])
    if struct_proc:
        has_structured = True
        structured_lines.append("### ICD-9 Procedures\n")
        for proc in struct_proc[:10]:
            code = proc.get('icd9_code', '')
            desc = proc.get('description', '')
            structured_lines.append(f"- **{code}**: {desc}")
        structured_lines.append("")

    # Structured Prescriptions
    struct_rx = gtmf.get('structured_prescriptions', [])
    if struct_rx:
        has_structured = True
        structured_lines.append("### Prescriptions\n")
        for rx in struct_rx[:15]:
            drug = rx.get('drug', '')
            dose = rx.get('dose_val_rx', '')
            structured_lines.append(f"- {drug} {dose}".strip())
        structured_lines.append("")

    if has_structured:
        lines.extend(structured_lines)

    # Metadata
    lines.append("## Metadata\n")
    case_type = gtmf.get('case_type', gtmf.get('light_case_filter', {}).get('case_type', 'UNKNOWN'))
    lines.append(f"- **Case Type**: {case_type}")

    filter_info = gtmf.get('light_case_filter', {})
    if filter_info.get('passed') is not None:
        lines.append(f"- **Light Case Filter**: {'Passed' if filter_info.get('passed') else 'Failed'}")

    lines.append("")

    return "\n".join(lines)


def markdown_to_gtmf(markdown_content: str) -> Dict[str, Any]:
    """
    Convert Markdown-formatted GTMF back to dictionary.

    Args:
        markdown_content: Markdown string

    Returns:
        GTMF dictionary
    """
    gtmf = {
        'Core_Fields': {},
        'Context_Fields': {},
        'Additional_Context': {}
    }

    lines = markdown_content.split('\n')
    current_section = None
    current_subsection = None

    for line in lines:
        line = line.strip()

        # Section headers
        if line.startswith('## '):
            current_section = line[3:].strip()
            current_subsection = None
            continue

        # Subsection headers
        if line.startswith('### '):
            current_subsection = line[4:].strip()
            continue

        # Skip empty lines and title
        if not line or line.startswith('# '):
            continue

        # Parse content based on section
        if current_section == 'Patient Information':
            if '**Subject ID**:' in line:
                gtmf['subject_id'] = _extract_value(line)
            elif '**Admission ID**:' in line:
                gtmf['hadm_id'] = _extract_value(line)
            elif '**Profile Type**:' in line:
                gtmf['profile_type'] = _extract_value(line)

        elif current_section == 'Demographics':
            if not gtmf['Context_Fields'].get('Patient_Demographics'):
                gtmf['Context_Fields']['Patient_Demographics'] = {}
            if '**Age**:' in line:
                age_str = _extract_value(line)
                try:
                    gtmf['Context_Fields']['Patient_Demographics']['Age'] = int(age_str)
                except:
                    gtmf['Context_Fields']['Patient_Demographics']['Age'] = age_str
            elif '**Sex**:' in line:
                gtmf['Context_Fields']['Patient_Demographics']['Sex'] = _extract_value(line)

        elif current_section == 'Chief Complaint':
            if not line.startswith('-'):
                if 'Additional_Context' not in gtmf:
                    gtmf['Additional_Context'] = {}
                current_complaint = gtmf['Additional_Context'].get('Chief_Complaint', '')
                gtmf['Additional_Context']['Chief_Complaint'] = (current_complaint + ' ' + line).strip()

        elif current_section == 'Symptoms':
            if line.startswith('- '):
                if 'Symptoms' not in gtmf['Core_Fields']:
                    gtmf['Core_Fields']['Symptoms'] = []
                symptom = line[2:].strip()
                gtmf['Core_Fields']['Symptoms'].append({'description': symptom})

        elif current_section == 'Medical History':
            if not gtmf['Context_Fields'].get('Medical_History'):
                gtmf['Context_Fields']['Medical_History'] = {}
            if '**Past Medical History**:' in line:
                gtmf['Context_Fields']['Medical_History']['Past_Medical_History'] = _extract_value(line)
            elif '**Family History**:' in line:
                gtmf['Context_Fields']['Medical_History']['Family_History'] = _extract_value(line)
            elif '**Social History**:' in line:
                gtmf['Context_Fields']['Medical_History']['Social_History'] = _extract_value(line)

        elif current_section == 'Allergies':
            if not line.startswith('-'):
                allergies_str = line.strip()
                gtmf['Context_Fields']['Allergies'] = [a.strip() for a in allergies_str.split(',')]

        elif current_section == 'Current Medications':
            if line.startswith('- '):
                if 'Current_Medications' not in gtmf['Context_Fields']:
                    gtmf['Context_Fields']['Current_Medications'] = []
                med = line[2:].strip()
                gtmf['Context_Fields']['Current_Medications'].append({'name': med})

        elif current_section == 'Lab Results':
            if line.startswith('- '):
                if 'lab_results' not in gtmf:
                    gtmf['lab_results'] = []
                lab_entry = _parse_lab_result(line[2:])
                if lab_entry:
                    gtmf['lab_results'].append(lab_entry)

        elif current_section == 'Diagnoses':
            if line.startswith('- '):
                if 'Diagnoses' not in gtmf['Core_Fields']:
                    gtmf['Core_Fields']['Diagnoses'] = []
                diag = line[2:].strip()
                gtmf['Core_Fields']['Diagnoses'].append({'description': diag})

        elif current_section == 'Treatment Options':
            if line.startswith('- '):
                if 'Treatment_Options' not in gtmf['Core_Fields']:
                    gtmf['Core_Fields']['Treatment_Options'] = []
                tx = line[2:].strip()
                gtmf['Core_Fields']['Treatment_Options'].append({'description': tx})

        elif current_section == 'Structured Clinical Data':
            if current_subsection == 'ICD-9 Diagnoses':
                if line.startswith('- '):
                    if 'structured_diagnoses' not in gtmf:
                        gtmf['structured_diagnoses'] = []
                    diag_entry = _parse_icd_entry(line[2:])
                    if diag_entry:
                        gtmf['structured_diagnoses'].append(diag_entry)

            elif current_subsection == 'ICD-9 Procedures':
                if line.startswith('- '):
                    if 'structured_procedures' not in gtmf:
                        gtmf['structured_procedures'] = []
                    proc_entry = _parse_icd_entry(line[2:])
                    if proc_entry:
                        gtmf['structured_procedures'].append(proc_entry)

            elif current_subsection == 'Prescriptions':
                if line.startswith('- '):
                    if 'structured_prescriptions' not in gtmf:
                        gtmf['structured_prescriptions'] = []
                    rx_entry = _parse_prescription(line[2:])
                    if rx_entry:
                        gtmf['structured_prescriptions'].append(rx_entry)

        elif current_section == 'Metadata':
            if '**Case Type**:' in line:
                gtmf['case_type'] = _extract_value(line)
            elif '**Light Case Filter**:' in line:
                passed = 'Passed' in line
                if 'light_case_filter' not in gtmf:
                    gtmf['light_case_filter'] = {}
                gtmf['light_case_filter']['passed'] = passed

    return gtmf


def _extract_value(line: str) -> str:
    """Extract value after colon."""
    parts = line.split(':', 1)
    if len(parts) > 1:
        return parts[1].strip()
    return ''


def _parse_lab_result(line: str) -> Dict[str, Any]:
    """Parse lab result line: 'WBC: 11.2 K/uL'"""
    match = re.match(r'(.+?):\s*([0-9.]+)\s*(.+)?', line)
    if match:
        return {
            'label': match.group(1).strip(),
            'valuenum': float(match.group(2)),
            'valueuom': match.group(3).strip() if match.group(3) else ''
        }
    return None


def _parse_icd_entry(line: str) -> Dict[str, Any]:
    """Parse ICD entry: '**786.2**: Cough'"""
    match = re.match(r'\*\*(.+?)\*\*:\s*(.+)', line)
    if match:
        return {
            'icd9_code': match.group(1).strip(),
            'description': match.group(2).strip()
        }
    return None


def _parse_prescription(line: str) -> Dict[str, Any]:
    """Parse prescription: 'Lisinopril 10mg'"""
    parts = line.split()
    if parts:
        return {
            'drug': parts[0],
            'dose_val_rx': ' '.join(parts[1:]) if len(parts) > 1 else ''
        }
    return None


def save_gtmf_markdown(gtmf: Dict[str, Any], output_path: str) -> None:
    """Save GTMF as Markdown file."""
    markdown_content = gtmf_to_markdown(gtmf)

    # Create directory if needed
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)


def load_gtmf_markdown(file_path: str) -> Dict[str, Any]:
    """Load GTMF from Markdown file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        markdown_content = f.read()

    return markdown_to_gtmf(markdown_content)


def load_all_gtmfs_from_directory(directory: str) -> List[Dict[str, Any]]:
    """
    Load all GTMF markdown files from a directory.

    Args:
        directory: Path to directory containing .md GTMF files

    Returns:
        List of GTMF dictionaries
    """
    gtmfs = []
    path = Path(directory)

    if not path.exists():
        return gtmfs

    for md_file in sorted(path.glob('*.md')):
        try:
            gtmf = load_gtmf_markdown(str(md_file))
            gtmfs.append(gtmf)
        except Exception as e:
            print(f"Error loading {md_file}: {e}")

    return gtmfs
