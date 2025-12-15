import logging
import json
from typing import Dict
from Utils.llms_utils import load_gpt_model, chat_generate
from Utils.bias_aware_prompts import PROMPT_IMPROVEMENT_PROMPT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PromptImprovementAgent:
    """
    Translates judge feedback into actionable prompt improvements.

    Maintains bias-aware constraints while adjusting stylistic/structural aspects.
    """

    def __init__(self, llm=None):
        """
        Initialize PromptImprovementAgent.

        Args:
            llm: Language model client (if None, will load default)
        """
        if llm:
            self.llm = llm
        else:
            logger.info("Loading LLM for PromptImprovementAgent")
            self.llm = load_gpt_model(temperature=0.3, max_tokens=600)

    def improve_prompts(
        self,
        judge_feedback: Dict,
        dialogue: list,
        current_prompts: Dict = None
    ) -> Dict:
        """
        Generate improved prompts based on judge feedback.

        Args:
            judge_feedback: Feedback dict from JudgeAgent
            dialogue: The dialogue that was evaluated
            current_prompts: Optional current prompt config

        Returns:
            Dict with improvement suggestions:
                - patient_improvements: str
                - doctor_improvements: str
                - general_improvements: str
        """
        logger.info("Generating prompt improvements from judge feedback...")

        # Extract key feedback points
        patient_feedback = judge_feedback.get('feedback_for_improvement', {}).get('patient_side', '')
        doctor_feedback = judge_feedback.get('feedback_for_improvement', {}).get('doctor_side', '')
        flow_feedback = judge_feedback.get('feedback_for_improvement', {}).get('conversation_flow', '')
        score = judge_feedback.get('score', 0.0)

        # Build improvement prompt
        messages = [
            {"role": "system", "content": PROMPT_IMPROVEMENT_PROMPT},
            {"role": "user", "content": self._build_improvement_request(
                judge_feedback, dialogue, patient_feedback, doctor_feedback, flow_feedback
            )}
        ]

        try:
            response = chat_generate(self.llm, messages)
            improvements = self._parse_improvements(response)
            logger.info("Generated prompt improvements successfully")
            return improvements

        except Exception as e:
            logger.error(f"Error generating improvements: {e}")
            # Return generic improvements
            return self._fallback_improvements(judge_feedback)

    def _build_improvement_request(
        self,
        judge_feedback: Dict,
        dialogue: list,
        patient_feedback: str,
        doctor_feedback: str,
        flow_feedback: str
    ) -> str:
        """Build the improvement request prompt."""
        dialogue_snippet = "\n".join([
            f"{turn['role']}: {turn['content'][:100]}..."
            for turn in dialogue[:4]
        ])

        request = f"""Judge Evaluation Results:
- Score: {judge_feedback.get('score', 0.0):.2f}
- Decision: {judge_feedback.get('decision', 'UNREALISTIC')}
- Justification: {judge_feedback.get('justification', 'N/A')}

Specific Feedback:
- Patient Side: {patient_feedback}
- Doctor Side: {doctor_feedback}
- Conversation Flow: {flow_feedback}

Dialogue Sample (first 4 turns):
{dialogue_snippet}

Based on this feedback, provide specific improvements for:
1. Patient agent prompts/behavior
2. Doctor agent prompts/behavior
3. Overall dialogue orchestration

IMPORTANT: Maintain all bias-aware and grounding constraints. Only adjust stylistic and structural elements.

Provide your response in JSON format:
{{
  "patient_improvements": "Specific suggestions for patient agent",
  "doctor_improvements": "Specific suggestions for doctor agent",
  "general_improvements": "General dialogue improvements"
}}"""

        return request

    def _parse_improvements(self, response: str) -> Dict:
        """Parse LLM response into improvement dict."""
        try:
            # Try JSON parsing
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                improvements = json.loads(json_match.group(0))
                return {
                    "patient_improvements": improvements.get('patient_improvements', ''),
                    "doctor_improvements": improvements.get('doctor_improvements', ''),
                    "general_improvements": improvements.get('general_improvements', '')
                }
        except:
            logger.warning("Failed to parse improvements as JSON, using text extraction")

        # Fallback: extract sections from text
        patient_imp = self._extract_section(response, ['patient', 'patient agent', 'patient side'])
        doctor_imp = self._extract_section(response, ['doctor', 'doctor agent', 'physician'])
        general_imp = self._extract_section(response, ['general', 'overall', 'dialogue'])

        return {
            "patient_improvements": patient_imp or "Be more natural and gradual in symptom disclosure",
            "doctor_improvements": doctor_imp or "Ask more focused, empathetic questions",
            "general_improvements": general_imp or "Improve natural conversation flow"
        }

    def _extract_section(self, text: str, keywords: list) -> str:
        """Extract section from text based on keywords."""
        text_lower = text.lower()
        for keyword in keywords:
            idx = text_lower.find(keyword)
            if idx >= 0:
                # Extract next 150 characters
                section = text[idx:idx+200]
                return section.strip()
        return ""

    def _fallback_improvements(self, judge_feedback: Dict) -> Dict:
        """Generate fallback improvements based on score."""
        score = judge_feedback.get('score', 0.0)

        if score < 0.4:
            return {
                "patient_improvements": "Ensure patient only mentions symptoms from their profile. Use more natural, hesitant language initially.",
                "doctor_improvements": "Start with warmer greeting. Ask more open-ended questions. Show empathy to patient concerns.",
                "general_improvements": "Build trust gradually. Avoid medical jargon early. Ensure natural turn-taking."
            }
        elif score < 0.7:
            return {
                "patient_improvements": "Reveal symptoms more gradually across turns. Add natural hesitations and uncertainty.",
                "doctor_improvements": "Reference earlier patient statements. Use transitions between questions. Show more empathy.",
                "general_improvements": "Improve conversation flow and continuity. Make dialogue feel more natural."
            }
        else:
            return {
                "patient_improvements": "Minor refinements to naturalness and timing of disclosures.",
                "doctor_improvements": "Fine-tune empathy and question pacing.",
                "general_improvements": "Small improvements to overall flow and realism."
            }
