"""EHR Summarizer Agent - Generates concise summaries of EHR texts"""
import json
import logging
from pathlib import Path
from typing import Dict
from utils.llms_utils import LLMClient

logger = logging.getLogger(__name__)


class EHRSummarizerAgent:
    """Summarizes EHR text for STS evaluation"""

    def __init__(self, llm_client: LLMClient, output_dir: str = "outputs/summaries"):
        self.llm_client = llm_client
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def summarize(self, ehr_case: Dict) -> str:
        """Generate a concise summary of EHR case"""
        text = ehr_case.get("text", "")
        if not text:
            return "No EHR text available"

        # Use first 2000 characters to avoid token limits
        text_excerpt = text[:2000]

        system_message = """You are a medical summarization expert. Generate concise summaries of clinical notes focusing on key medical information."""

        user_message = f"""Summarize the following clinical note, focusing on:
- Main complaint and symptoms
- Primary diagnosis (if mentioned)
- Key treatments or recommendations

Clinical Note Excerpt:
{text_excerpt}

Provide a concise summary (2-4 sentences)."""

        try:
            summary = self.llm_client.chat_completion(system_message, user_message, temperature=0.0)
            logger.info(f"Generated EHR summary for case {ehr_case.get('hadm_id')}")
            return summary.strip()
        except Exception as e:
            logger.error(f"Error summarizing EHR: {e}")
            return "Summary generation failed"

    def save_summary(self, hadm_id: int, subject_id: int, summary: str) -> str:
        """Save EHR summary to JSON"""
        filename = f"ehr_summary_{hadm_id}.json"
        filepath = self.output_dir / filename

        output = {
            "subject_id": subject_id,
            "hadm_id": hadm_id,
            "ehr_summary_text": summary,
            "metadata": {
                "model": "Azure AI",
                "timestamp": ""
            }
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)

        logger.info(f"Saved EHR summary to {filepath}")
        return str(filepath)
