"""Dialogue Summarizer Agent - Generates concise summaries of dialogues"""
import json
import logging
from pathlib import Path
from typing import Dict, List
from utils.llms_utils import LLMClient

logger = logging.getLogger(__name__)


class DialogueSummarizerAgent:
    """Summarizes dialogue for STS evaluation"""

    def __init__(self, llm_client: LLMClient, output_dir: str = "outputs/summaries"):
        self.llm_client = llm_client
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def summarize(self, dialogue: List[Dict]) -> str:
        """Generate a concise summary of dialogue"""
        if not dialogue:
            return "No dialogue available"

        # Convert dialogue to text
        transcript = "\n".join([f"{turn['role']}: {turn['content']}" for turn in dialogue])

        system_message = """You are a medical dialogue summarization expert. Generate concise summaries of patient-physician conversations focusing on key medical content."""

        user_message = f"""Summarize the following medical dialogue, focusing on:
- Symptoms discussed
- Diagnostic reasoning mentioned
- Treatments or advice provided

Dialogue:
{transcript}

Provide a concise summary (2-4 sentences)."""

        try:
            summary = self.llm_client.chat_completion(system_message, user_message, temperature=0.0)
            logger.info("Generated dialogue summary")
            return summary.strip()
        except Exception as e:
            logger.error(f"Error summarizing dialogue: {e}")
            return "Summary generation failed"

    def save_summary(self, profile_id: str, summary: str) -> str:
        """Save dialogue summary to JSON"""
        filename = f"dialogue_summary_{profile_id}.json"
        filepath = self.output_dir / filename

        output = {
            "profile_id": profile_id,
            "dialogue_summary_text": summary,
            "metadata": {
                "model": "Azure AI",
                "timestamp": ""
            }
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)

        logger.info(f"Saved dialogue summary to {filepath}")
        return str(filepath)
