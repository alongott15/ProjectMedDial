"""Prompt Improvement Agent - Converts judge feedback into prompt improvements"""
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class PromptImprovementAgent:
    """Converts judge feedback into actionable prompt improvements"""

    def extract_improvement_areas(self, feedback: str) -> Dict[str, str]:
        """Extract specific improvement areas from judge feedback"""
        improvements = {
            "patient": "",
            "doctor": "",
            "flow": "",
            "safety": ""
        }

        lines = feedback.split('\n')

        current_section = None
        for line in lines:
            line_lower = line.lower().strip()

            if 'patient' in line_lower and ':' in line:
                current_section = "patient"
                improvements["patient"] = line.split(':', 1)[1].strip()
            elif 'doctor' in line_lower and ':' in line:
                current_section = "doctor"
                improvements["doctor"] = line.split(':', 1)[1].strip()
            elif 'flow' in line_lower and ':' in line:
                current_section = "flow"
                improvements["flow"] = line.split(':', 1)[1].strip()
            elif 'safety' in line_lower and ':' in line:
                current_section = "safety"
                improvements["safety"] = line.split(':', 1)[1].strip()
            elif current_section and line.strip():
                improvements[current_section] += " " + line.strip()

        return improvements

    def generate_improvement_prompt(self, feedback: str) -> str:
        """Generate an improvement prompt from judge feedback"""
        improvements = self.extract_improvement_areas(feedback)

        prompt_additions = []

        if improvements["patient"]:
            prompt_additions.append(f"Patient improvement needed: {improvements['patient']}")

        if improvements["doctor"]:
            prompt_additions.append(f"Doctor improvement needed: {improvements['doctor']}")

        if improvements["flow"]:
            prompt_additions.append(f"Conversation flow improvement: {improvements['flow']}")

        if improvements["safety"]:
            prompt_additions.append(f"Safety/clarity improvement: {improvements['safety']}")

        if not prompt_additions:
            prompt_additions.append("Focus on more natural conversation flow and appropriate medical dialogue.")

        improvement_prompt = "\n".join(prompt_additions)
        logger.info(f"Generated improvement prompt with {len(prompt_additions)} areas")

        return improvement_prompt
