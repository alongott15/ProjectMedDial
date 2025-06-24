import logging
from Utils.llms_utils import llm_generate

logger = logging.getLogger(__name__)

class CoachAgent:
    def __init__(self, llm):
        self.llm = llm
        self.base_prompt = (
            "You are a senior doctor reviewing a doctor-patient dialogue. "
            "First, decide if the dialogue is realistic or unrealistic. "
            "Then, provide constructive feedback on how to improve the realism if necessary. "
            "Your output must start with either 'Realistic:' or 'Unrealistic:' followed by your feedback. "
            "For example, if realistic, output 'Realistic: The dialogue flows naturally.'; "
            "if unrealistic, output 'Unrealistic: [feedback]'."
        )
    
    def review_dialogue(self, dialogue_text: str) -> tuple:
        """
        Reviews the dialogue and returns (label, feedback).
        The label is either "realistic" or "unrealistic" and feedback is a text explanation.
        """
        prompt = f"{self.base_prompt}\nDialogue:\n{dialogue_text}\nAnswer:"
        output = llm_generate(self.llm, prompt, role="Coach")
        logger.info(f"[Coach] Review output: {output[:100]}")
        # Expect the output to start with 'Realistic:' or 'Unrealistic:'
        if output.lower().startswith("realistic:"):
            label = "realistic"
            feedback = output[len("realistic:"):].strip()
        elif output.lower().startswith("unrealistic:"):
            label = "unrealistic"
            feedback = output[len("unrealistic:"):].strip()
        else:
            # Fallback if format is not as expected
            label = "unrealistic"
            feedback = output.strip()
        return label, feedback

    # Optionally, you can keep the generate_feedback method if you want to provide additional feedback.
    def generate_feedback(self, dialogue_text: str) -> str:
        # This method can simply call review_dialogue and return the feedback part.
        _, feedback = self.review_dialogue(dialogue_text)
        return feedback
