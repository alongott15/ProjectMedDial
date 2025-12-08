"""
DialogueSummarizerAgent - Summarizes dialogues for STS evaluation.
"""

import logging
from typing import List, Dict
from Utils.llms_utils import load_gpt_model, chat_generate
from Utils.bias_aware_prompts import DIALOGUE_SUMMARIZER_PROMPT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DialogueSummarizerAgent:
    """
    Summarizes doctor-patient dialogues using bias-aware prompts.

    Only reports what was actually said in the conversation.
    """

    def __init__(self, llm=None):
        """
        Initialize DialogueSummarizerAgent.

        Args:
            llm: Language model client (if None, will load default)
        """
        if llm:
            self.llm = llm
        else:
            logger.info("Loading LLM for DialogueSummarizerAgent")
            self.llm = load_gpt_model(temperature=0.1, max_tokens=400)

    def summarize(self, dialogue: List[Dict], transcript: str = None) -> str:
        """
        Summarize dialogue.

        Args:
            dialogue: List of dialogue turns (dicts with 'role' and 'content')
            transcript: Optional pre-formatted transcript string

        Returns:
            Summary string (5-8 sentences)
        """
        logger.info("Summarizing dialogue...")

        # Format dialogue if not provided
        if transcript is None:
            transcript_lines = []
            for turn in dialogue:
                role = turn.get('role', 'Unknown')
                content = turn.get('content', '')
                transcript_lines.append(f"{role}: {content}")
            transcript = "\n".join(transcript_lines)

        # Build prompt
        messages = [
            {"role": "system", "content": DIALOGUE_SUMMARIZER_PROMPT},
            {"role": "user", "content": f"""Dialogue:

{transcript}

Provide a concise summary (5-8 sentences) reporting only what was said:
- Symptoms discussed
- Doctor's questions and assessments
- Advice or recommendations given

Summary:"""}
        ]

        try:
            summary = chat_generate(self.llm, messages)
            logger.info(f"Dialogue summary generated: {len(summary)} characters")
            return summary.strip()

        except Exception as e:
            logger.error(f"Error summarizing dialogue: {e}")
            return "Unable to generate summary"
