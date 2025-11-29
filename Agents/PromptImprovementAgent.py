"""
PromptImprovementAgent - Improves dialogue generation prompts based on judge feedback.

This agent analyzes judge feedback and suggests targeted improvements to doctor and
patient agent prompts while maintaining all bias-aware and grounding constraints.
"""

import logging
import json
import re
from typing import Dict, List
from Utils.llms_utils import load_gpt_model, chat_generate
from prompts.prompt_loader import get_prompt_loader

logger = logging.getLogger(__name__)


class PromptImprovementAgent:
    """
    Suggests prompt improvements based on judge feedback.

    Maintains all safety and anti-hallucination constraints while improving
    dialogue quality through targeted adjustments.
    """

    def __init__(self,
                 model_name: str = 'gpt-4.1',
                 temperature: float = 0.3,
                 max_tokens: int = 800):
        """
        Initialize the PromptImprovementAgent.

        Args:
            model_name: LLM model to use.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens for response.
        """
        self.llm = load_gpt_model(model_name, temperature, max_tokens)
        self.prompt_loader = get_prompt_loader()
        logger.info(f"PromptImprovementAgent initialized (model={model_name})")

    def _build_improvement_prompt(self,
                                   dialogue: List[Dict],
                                   judge_evaluation: Dict,
                                   current_prompts: Dict) -> List[Dict]:
        """
        Build the prompt for LLM to suggest improvements.

        Args:
            dialogue: The dialogue that was evaluated.
            judge_evaluation: Judge's evaluation with feedback.
            current_prompts: Current prompts being used (doctor, patient).

        Returns:
            List of message dictionaries for LLM.
        """
        system_prompt = self.prompt_loader.get_prompt_improvement_prompt()

        # Format dialogue
        dialogue_text = "\n".join([
            f"{turn.get('role', 'Unknown')}: {turn.get('content', '')}"
            for turn in dialogue
        ])

        # Extract feedback
        feedback = judge_evaluation.get('feedback_for_improvement', {})
        decision = judge_evaluation.get('decision', 'UNREALISTIC')
        score = judge_evaluation.get('score', 0.0)
        justification = judge_evaluation.get('justification', '')

        user_content = f"""Previous Dialogue:
{dialogue_text}

Judge Evaluation:
- Decision: {decision}
- Score: {score:.2f}
- Justification: {justification}

Specific Feedback:
- Patient side: {feedback.get('patient_side', 'N/A')}
- Doctor side: {feedback.get('doctor_side', 'N/A')}
- Conversation flow: {feedback.get('conversation_flow', 'N/A')}
- Safety/Clarity: {feedback.get('safety_or_clarity', 'N/A')}

Current Prompts:
Doctor: {current_prompts.get('doctor', 'N/A')}
Patient: {current_prompts.get('patient', 'N/A')}

Based on this evaluation, suggest small, targeted improvements to the prompts.
Remember to maintain all bias-aware and anti-hallucination constraints.

Provide your response as a JSON object with this structure:
{{
  "doctor_prompt_adjustments": {{
    "add_instructions": ["instruction 1", "instruction 2"],
    "emphasis_points": ["point 1", "point 2"]
  }},
  "patient_prompt_adjustments": {{
    "add_instructions": ["instruction 1", "instruction 2"],
    "emphasis_points": ["point 1", "point 2"]
  }},
  "conversation_parameters": {{
    "suggested_max_turns": <number>,
    "suggested_adjustments": "brief description"
  }},
  "summary": "Brief summary of key improvements"
}}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        return messages

    def _parse_improvement_response(self, response: str) -> Dict:
        """
        Parse LLM response into improvement suggestions.

        Args:
            response: Raw LLM response.

        Returns:
            Dictionary of improvement suggestions.
        """
        try:
            # Try to extract JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                improvements = json.loads(json_str)
                return improvements

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse improvement response as JSON: {e}")

        # Fallback: return empty improvements
        return {
            "doctor_prompt_adjustments": {
                "add_instructions": [],
                "emphasis_points": []
            },
            "patient_prompt_adjustments": {
                "add_instructions": [],
                "emphasis_points": []
            },
            "conversation_parameters": {
                "suggested_adjustments": "Unable to parse specific suggestions"
            },
            "summary": "Fallback: Unable to parse LLM response"
        }

    def improve_prompts(self,
                       dialogue: List[Dict],
                       judge_evaluation: Dict,
                       current_prompts: Dict = None) -> Dict:
        """
        Generate prompt improvement suggestions based on judge feedback.

        Args:
            dialogue: The dialogue that was evaluated.
            judge_evaluation: Judge's evaluation dictionary.
            current_prompts: Current prompts being used (optional).
                           If not provided, uses base prompts.

        Returns:
            Dictionary of improvement suggestions.
        """
        if current_prompts is None:
            current_prompts = {
                'doctor': self.prompt_loader.get_doctor_agent_prompt(),
                'patient': self.prompt_loader.get_patient_agent_prompt()
            }

        logger.info("Generating prompt improvements based on judge feedback")

        # Build improvement prompt
        messages = self._build_improvement_prompt(dialogue, judge_evaluation, current_prompts)

        # Get LLM suggestions
        response = chat_generate(self.llm, messages)

        # Parse improvements
        improvements = self._parse_improvement_response(response)

        logger.info(f"  Improvement summary: {improvements.get('summary', 'N/A')}")

        return improvements

    def apply_improvements(self,
                          base_prompts: Dict,
                          improvements: Dict) -> Dict:
        """
        Apply improvement suggestions to base prompts.

        This creates new prompt variants while preserving the core bias-aware
        and anti-hallucination instructions.

        Args:
            base_prompts: Base prompts dictionary (doctor, patient).
            improvements: Improvement suggestions from improve_prompts().

        Returns:
            Updated prompts dictionary.
        """
        updated_prompts = {
            'doctor': base_prompts.get('doctor', ''),
            'patient': base_prompts.get('patient', '')
        }

        # Apply doctor adjustments
        doctor_adj = improvements.get('doctor_prompt_adjustments', {})
        if doctor_adj.get('add_instructions'):
            additions = "\n\nAdditional guidance:\n" + "\n".join([
                f"- {instr}" for instr in doctor_adj['add_instructions']
            ])
            updated_prompts['doctor'] += additions

        if doctor_adj.get('emphasis_points'):
            emphasis = "\n\nImportant reminders:\n" + "\n".join([
                f"- {point}" for point in doctor_adj['emphasis_points']
            ])
            updated_prompts['doctor'] += emphasis

        # Apply patient adjustments
        patient_adj = improvements.get('patient_prompt_adjustments', {})
        if patient_adj.get('add_instructions'):
            additions = "\n\nAdditional guidance:\n" + "\n".join([
                f"- {instr}" for instr in patient_adj['add_instructions']
            ])
            updated_prompts['patient'] += additions

        if patient_adj.get('emphasis_points'):
            emphasis = "\n\nImportant reminders:\n" + "\n".join([
                f"- {point}" for point in patient_adj['emphasis_points']
            ])
            updated_prompts['patient'] += emphasis

        logger.info("Applied improvements to prompts")

        return updated_prompts

    def get_conversation_adjustments(self, improvements: Dict) -> Dict:
        """
        Extract conversation-level adjustments from improvements.

        Args:
            improvements: Improvement suggestions dictionary.

        Returns:
            Dictionary of conversation parameter adjustments.
        """
        conv_params = improvements.get('conversation_parameters', {})

        adjustments = {
            'max_turns': conv_params.get('suggested_max_turns'),
            'description': conv_params.get('suggested_adjustments', '')
        }

        return adjustments
