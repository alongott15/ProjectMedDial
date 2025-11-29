"""
JudgeAgent - LLM-based dialogue naturalness evaluator.

This agent evaluates synthetic doctor-patient dialogues for naturalness and realism,
using few-shot examples from reference datasets and providing feedback for improvement.
"""

import logging
import json
import re
from typing import Dict, Tuple, List, Optional
from Utils.llms_utils import AzureAIFoundryClient, load_gpt_model
from prompts.prompt_loader import get_prompt_loader

logger = logging.getLogger(__name__)


class JudgeAgent:
    """
    Evaluates dialogue naturalness using LLM with few-shot examples.

    Simpler than CoachAgent - focuses solely on naturalness and hallucination detection.
    """

    # Few-shot examples of REALISTIC medical dialogues (can be loaded from file)
    REALISTIC_EXAMPLES = [
        {
            "dialogue": """Doctor: Hello, what brings you in today?
Patient: Hi doctor, I've had this cough for about a week now, and it's not getting better.
Doctor: I see. Can you tell me more about the cough? Is it dry or are you bringing anything up?
Patient: It's mostly dry, but sometimes I cough up a little clear mucus.
Doctor: Okay. Have you had any fever, sore throat, or body aches?
Patient: I had a low fever for a couple days, and my throat was a bit sore at first.
Doctor: Any shortness of breath or chest pain?
Patient: No, nothing like that.
Doctor: Good. It sounds like you might have had a viral upper respiratory infection. Let me listen to your lungs.""",
            "reason": "Natural conversation flow, appropriate questions, patient provides relevant details."
        }
    ]

    # Example of UNREALISTIC dialogue (for contrast)
    UNREALISTIC_EXAMPLES = [
        {
            "dialogue": """Doctor: What is your problem?
Patient: I have symptoms.
Doctor: You have pneumonia and need antibiotics immediately.
Patient: Okay.
Doctor: Take amoxicillin 500mg three times daily.
Patient: Okay.""",
            "reason": "Too abrupt, diagnosis without examination, lacks natural conversation flow."
        }
    ]

    def __init__(self,
                 model_name: str = 'gpt-4.1',
                 temperature: float = 0.2,
                 max_tokens: int = 1000,
                 threshold: float = 0.6):
        """
        Initialize the JudgeAgent.

        Args:
            model_name: LLM model to use for evaluation.
            temperature: Sampling temperature (lower = more consistent).
            max_tokens: Maximum tokens for LLM response.
            threshold: Minimum score (0-1) to consider dialogue REALISTIC.
        """
        self.llm = load_gpt_model(model_name, temperature, max_tokens)
        self.threshold = threshold
        self.prompt_loader = get_prompt_loader()
        logger.info(f"JudgeAgent initialized (model={model_name}, threshold={threshold})")

    def _build_evaluation_prompt(self,
                                  dialogue: List[Dict],
                                  patient_profile: Dict) -> List[Dict]:
        """
        Build the prompt for LLM evaluation.

        Args:
            dialogue: List of dialogue turns.
            patient_profile: Patient profile dictionary.

        Returns:
            List of message dictionaries for LLM.
        """
        # Get the base judge prompt
        system_prompt = self.prompt_loader.get_judge_agent_prompt()

        # Add few-shot examples
        examples_text = "\n\nHere are examples of REALISTIC dialogues:\n\n"
        for i, example in enumerate(self.REALISTIC_EXAMPLES, 1):
            examples_text += f"Example {i}:\n{example['dialogue']}\n"
            examples_text += f"Why realistic: {example['reason']}\n\n"

        examples_text += "\nHere is an example of an UNREALISTIC dialogue:\n\n"
        for example in self.UNREALISTIC_EXAMPLES:
            examples_text += f"{example['dialogue']}\n"
            examples_text += f"Why unrealistic: {example['reason']}\n\n"

        system_prompt = system_prompt + examples_text

        # Format the dialogue to evaluate
        dialogue_text = self._format_dialogue(dialogue)

        # Format patient profile (key details only)
        profile_summary = self._summarize_profile(patient_profile)

        user_content = f"""Patient Profile:
{profile_summary}

Dialogue to Evaluate:
{dialogue_text}

Please evaluate this dialogue and provide your response in the following JSON format:
{{
  "decision": "REALISTIC" or "UNREALISTIC",
  "score": <numeric score from 0.0 to 1.0>,
  "justification": "<brief explanation>",
  "feedback_for_improvement": {{
    "patient_side": "<specific feedback for patient agent>",
    "doctor_side": "<specific feedback for doctor agent>",
    "conversation_flow": "<feedback on overall flow and structure>",
    "safety_or_clarity": "<any safety or clarity concerns>"
  }}
}}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        return messages

    def _format_dialogue(self, dialogue: List[Dict]) -> str:
        """
        Format dialogue turns into readable text.

        Args:
            dialogue: List of dialogue turns with 'role' and 'content'.

        Returns:
            Formatted dialogue string.
        """
        lines = []
        for turn in dialogue:
            role = turn.get('role', 'Unknown')
            content = turn.get('content', '')
            lines.append(f"{role}: {content}")

        return "\n".join(lines)

    def _summarize_profile(self, profile: Dict) -> str:
        """
        Create a concise summary of patient profile for evaluation.

        Args:
            profile: Patient profile dictionary.

        Returns:
            Profile summary string.
        """
        lines = []

        # Profile type
        profile_type = profile.get('profile_type', 'UNKNOWN')
        lines.append(f"Profile Type: {profile_type}")

        # Demographics
        demographics = profile.get('Context_Fields', {}).get('Patient_Demographics', {})
        age = demographics.get('Age', 'unknown')
        sex = demographics.get('Sex', 'unknown')
        lines.append(f"Demographics: {age} years old, {sex}")

        # Chief complaint
        chief_complaint = profile.get('Additional_Context', {}).get('Chief_Complaint', 'not provided')
        lines.append(f"Chief Complaint: {chief_complaint}")

        # Symptoms
        symptoms = profile.get('Core_Fields', {}).get('Symptoms', [])
        if symptoms:
            symptom_list = [s.get('description', '') for s in symptoms[:3]]  # First 3
            lines.append(f"Symptoms: {', '.join(symptom_list)}")

        # Diagnosis (if present in profile)
        diagnoses = profile.get('Core_Fields', {}).get('Diagnoses', [])
        if diagnoses:
            dx_list = [d.get('primary', '') for d in diagnoses[:2]]
            lines.append(f"Diagnosis: {', '.join(dx_list)}")

        # Treatment (if present in profile)
        treatments = profile.get('Core_Fields', {}).get('Treatment_Options', [])
        if treatments:
            tx_list = [t.get('treatment', '') for t in treatments[:2]]
            if any(tx_list):
                lines.append(f"Treatment: {', '.join(tx_list)}")

        return "\n".join(lines)

    def _parse_llm_response(self, response: str) -> Dict:
        """
        Parse LLM JSON response into evaluation dictionary.

        Args:
            response: Raw LLM response string.

        Returns:
            Evaluation dictionary with decision, score, justification, and feedback.
        """
        try:
            # Try to extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                evaluation = json.loads(json_str)

                # Validate required fields
                required_fields = ['decision', 'score', 'justification', 'feedback_for_improvement']
                if all(field in evaluation for field in required_fields):
                    return evaluation

            logger.warning("LLM response missing required fields, using fallback parsing")

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")

        # Fallback: simple heuristic parsing
        decision = "UNREALISTIC"
        if "realistic" in response.lower() and "unrealistic" not in response.lower():
            decision = "REALISTIC"

        # Try to extract a score
        score = 0.5
        score_match = re.search(r'score["\s:]+(\d+\.?\d*)', response, re.IGNORECASE)
        if score_match:
            try:
                score = float(score_match.group(1))
                if score > 1.0:  # Handle 0-10 scale
                    score = score / 10.0
            except ValueError:
                pass

        return {
            "decision": decision,
            "score": score,
            "justification": "Fallback parsing - LLM response format issue",
            "feedback_for_improvement": {
                "patient_side": "Unable to extract specific feedback",
                "doctor_side": "Unable to extract specific feedback",
                "conversation_flow": "Unable to extract specific feedback",
                "safety_or_clarity": "Unable to extract specific feedback"
            }
        }

    def evaluate_dialogue(self,
                          dialogue: List[Dict],
                          patient_profile: Dict,
                          attempt_index: int = 1) -> Dict:
        """
        Evaluate a dialogue for naturalness and realism.

        Args:
            dialogue: List of dialogue turns.
            patient_profile: Patient profile dictionary.
            attempt_index: Current generation attempt number.

        Returns:
            Evaluation dictionary with structure:
            {
                "profile_id": str,
                "attempt_index": int,
                "decision": "REALISTIC" | "UNREALISTIC",
                "score": float (0.0-1.0),
                "justification": str,
                "feedback_for_improvement": {...}
            }
        """
        profile_id = f"{patient_profile.get('row_id', 0)}_{patient_profile.get('subject_id', 0)}"
        logger.info(f"Evaluating dialogue for profile {profile_id}, attempt {attempt_index}")

        # Build evaluation prompt
        messages = self._build_evaluation_prompt(dialogue, patient_profile)

        # Get LLM evaluation
        from Utils.llms_utils import chat_generate
        response = chat_generate(self.llm, messages)

        # Parse response
        evaluation = self._parse_llm_response(response)

        # Add metadata
        evaluation["profile_id"] = profile_id
        evaluation["attempt_index"] = attempt_index

        # Ensure score is in valid range
        evaluation["score"] = max(0.0, min(1.0, evaluation["score"]))

        # Apply threshold to determine final decision
        if evaluation["score"] >= self.threshold:
            evaluation["decision"] = "REALISTIC"
        else:
            evaluation["decision"] = "UNREALISTIC"

        logger.info(f"  Judge decision: {evaluation['decision']} (score: {evaluation['score']:.2f})")

        return evaluation

    def load_few_shot_examples(self, examples_file: str) -> None:
        """
        Load few-shot examples from a JSON file.

        This allows using examples from actual medical dialogue datasets
        (e.g., MedDialog, ReMeDi) for more realistic evaluation.

        Args:
            examples_file: Path to JSON file with example dialogues.
        """
        try:
            with open(examples_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if 'realistic' in data:
                self.REALISTIC_EXAMPLES = data['realistic']
                logger.info(f"Loaded {len(self.REALISTIC_EXAMPLES)} realistic examples")

            if 'unrealistic' in data:
                self.UNREALISTIC_EXAMPLES = data['unrealistic']
                logger.info(f"Loaded {len(self.UNREALISTIC_EXAMPLES)} unrealistic examples")

        except Exception as e:
            logger.error(f"Failed to load few-shot examples from {examples_file}: {e}")
