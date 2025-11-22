"""Judge Agent - Evaluates dialogue naturalness with few-shot examples"""
import json
import logging
from pathlib import Path
from typing import Dict, Tuple
from utils.llms_utils import LLMClient

logger = logging.getLogger(__name__)


class JudgeAgent:
    """LLM-based judge for evaluating dialogue naturalness and realism"""

    def __init__(
        self,
        llm_client: LLMClient,
        few_shot_examples_path: str = "config/few_shot_dialogues.json",
        threshold_score: float = 0.75,
        output_dir: str = "outputs/judge"
    ):
        self.llm_client = llm_client
        self.threshold_score = threshold_score
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Load few-shot examples
        self.few_shot_examples = self._load_few_shot_examples(few_shot_examples_path)

    def _load_few_shot_examples(self, path: str) -> Dict:
        """Load few-shot dialogue examples"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                examples = json.load(f)
            logger.info(f"Loaded {len(examples.get('realistic_examples', []))} few-shot examples")
            return examples
        except Exception as e:
            logger.warning(f"Could not load few-shot examples: {e}")
            return {"realistic_examples": [], "unrealistic_examples": []}

    def _format_few_shot_examples(self) -> str:
        """Format few-shot examples for the prompt"""
        formatted = "**REALISTIC DIALOGUE EXAMPLES:**\n\n"

        for i, example in enumerate(self.few_shot_examples.get("realistic_examples", [])[:3], 1):
            formatted += f"Example {i}:\n"
            for turn in example["dialogue"][:8]:  # Show first 8 turns
                formatted += f"{turn['role']}: {turn['text']}\n"
            formatted += "\n"

        return formatted

    def evaluate_dialogue(
        self,
        dialogue: str,
        profile_context: Dict = None
    ) -> Tuple[str, float, str]:
        """
        Evaluate dialogue naturalness and realism

        Returns:
            Tuple of (decision, score, feedback)
            - decision: "REALISTIC" or "UNREALISTIC"
            - score: float between 0.0 and 1.0
            - feedback: str with detailed feedback
        """
        few_shot_text = self._format_few_shot_examples()

        case_type = "light/common medical symptoms"
        if profile_context:
            case_type = profile_context.get("case_type", "light/common medical symptoms")

        system_message = """You are an expert medical dialogue evaluator. Your task is to assess the naturalness and realism of patient-physician conversations.

Use the provided REALISTIC examples as references for what constitutes natural, realistic medical dialogue."""

        user_message = f"""{few_shot_text}

**DIALOGUE TO EVALUATE:**

{dialogue}

**EVALUATION CRITERIA:**

1. **Naturalness (0.0-1.0):**
   - Does the conversation flow naturally?
   - Are the questions and responses appropriate?
   - Does it sound like a real medical consultation?

2. **Medical Appropriateness (0.0-1.0):**
   - Is the doctor's approach professional and systematic?
   - Are the questions clinically relevant?
   - Is the advice appropriate for {case_type}?

3. **Progressive Disclosure (0.0-1.0):**
   - Does the patient reveal information gradually?
   - Is there natural back-and-forth?
   - Avoid unrealistic information dumps?

4. **Safety and Clarity (0.0-1.0):**
   - Is the advice safe and appropriate?
   - Are explanations clear?
   - Is there proper conclusion?

**PROVIDE YOUR EVALUATION:**

Overall Score (0.0-1.0):
Decision (REALISTIC or UNREALISTIC):
Justification:

**FEEDBACK FOR IMPROVEMENT:**
- Patient behavior:
- Doctor behavior:
- Conversation flow:
- Safety/clarity issues:

Format your response as:
SCORE: [0.0-1.0]
DECISION: [REALISTIC/UNREALISTIC]
JUSTIFICATION: [Your detailed justification]
FEEDBACK:
Patient: [feedback]
Doctor: [feedback]
Flow: [feedback]
Safety: [feedback]"""

        try:
            response = self.llm_client.chat_completion(system_message, user_message, temperature=0.0)
            decision, score, feedback = self._parse_judge_response(response)
            return decision, score, feedback
        except Exception as e:
            logger.error(f"Error in judge evaluation: {e}")
            return "UNREALISTIC", 0.0, "Evaluation failed"

    def _parse_judge_response(self, response: str) -> Tuple[str, float, str]:
        """Parse judge's response to extract decision, score, and feedback"""
        lines = response.split('\n')

        score = 0.0
        decision = "UNREALISTIC"
        feedback = response

        for line in lines:
            line_lower = line.lower().strip()

            # Extract score
            if line_lower.startswith('score:'):
                try:
                    score_str = line.split(':', 1)[1].strip()
                    score = float(score_str)
                except:
                    pass

            # Extract decision
            if line_lower.startswith('decision:'):
                decision_str = line.split(':', 1)[1].strip().upper()
                if 'REALISTIC' in decision_str:
                    decision = "REALISTIC"
                else:
                    decision = "UNREALISTIC"

        # Override decision based on threshold
        if score >= self.threshold_score:
            decision = "REALISTIC"
        else:
            decision = "UNREALISTIC"

        logger.info(f"Judge evaluation: {decision} (score: {score:.2f})")
        return decision, score, feedback

    def save_evaluation(
        self,
        profile_id: str,
        attempt: int,
        decision: str,
        score: float,
        feedback: str
    ) -> str:
        """Save judge evaluation to JSON"""
        filename = f"judge_eval_{profile_id}_attempt{attempt}.json"
        filepath = self.output_dir / filename

        output = {
            "profile_id": profile_id,
            "attempt_index": attempt,
            "decision": decision,
            "score": score,
            "justification": feedback,
            "feedback_for_improvement": {
                "patient_side": "",
                "doctor_side": "",
                "conversation_flow": "",
                "safety_or_clarity": ""
            }
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)

        logger.info(f"Saved judge evaluation to {filepath}")
        return str(filepath)
