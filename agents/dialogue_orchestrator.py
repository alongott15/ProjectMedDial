"""Dialogue Orchestrator Agent - Manages patient-physician conversation flow"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple
from agents.patient_agent import PatientAgent
from agents.doctor_agent import DoctorAgent

logger = logging.getLogger(__name__)


class DialogueOrchestratorAgent:
    """Orchestrates dialogue generation between patient and doctor agents"""

    def __init__(self, max_turns: int = 16, output_dir: str = "outputs/dialogues"):
        self.max_turns = max_turns
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def detect_conclusion(self, doctor_message: str) -> bool:
        """Detect if doctor has provided a conclusion"""
        keywords = [
            "based on", "my assessment", "i believe", "diagnosis", "recommend",
            "treatment plan", "next steps", "appears to be", "likely"
        ]
        return any(keyword in doctor_message.lower() for keyword in keywords)

    def detect_understanding(self, patient_message: str) -> bool:
        """Detect if patient shows understanding"""
        keywords = [
            "understand", "makes sense", "okay", "thank you", "alright",
            "got it", "i see", "sounds good", "clear"
        ]
        return any(keyword in patient_message.lower() for keyword in keywords)

    def generate_dialogue(
        self,
        patient_agent: PatientAgent,
        doctor_agent: DoctorAgent
    ) -> Tuple[List[Dict], str]:
        """
        Generate a dialogue between patient and doctor

        Returns:
            Tuple of (conversation_history, transcript_string)
        """
        conversation_history = []

        logger.info("Starting dialogue generation")

        # Doctor starts the conversation
        doctor_message = doctor_agent.respond([])
        conversation_history.append({"role": "Doctor", "content": doctor_message})
        logger.info(f"Doctor (turn 0): {doctor_message[:80]}...")

        doctor_concluded = False
        turn_count = 0

        while turn_count < self.max_turns:
            turn_count += 1

            # Patient responds
            patient_message = patient_agent.respond(conversation_history)
            conversation_history.append({"role": "Patient", "content": patient_message})
            logger.info(f"Patient (turn {turn_count}): {patient_message[:80]}...")

            # Check if patient understands after doctor conclusion
            if doctor_concluded and self.detect_understanding(patient_message):
                logger.info(f"Patient shows understanding after conclusion at turn {turn_count}")
                break

            # Doctor responds
            if turn_count >= self.max_turns:
                break

            doctor_message = doctor_agent.respond(conversation_history)
            conversation_history.append({"role": "Doctor", "content": doctor_message})
            logger.info(f"Doctor (turn {turn_count}): {doctor_message[:80]}...")

            # Check for doctor conclusion
            if not doctor_concluded and self.detect_conclusion(doctor_message):
                doctor_concluded = True
                logger.info(f"Doctor conclusion detected at turn {turn_count}")

        # Generate transcript
        transcript = "\n".join([f"{turn['role']}: {turn['content']}" for turn in conversation_history])

        logger.info(f"Dialogue generation completed: {len(conversation_history)} turns")
        return conversation_history, transcript

    def save_dialogue(self, dialogue: List[Dict], profile_id: str, attempt: int = 1) -> str:
        """Save dialogue to JSON"""
        filename = f"dialogue_{profile_id}_attempt{attempt}.json"
        filepath = self.output_dir / filename

        output = {
            "profile_id": profile_id,
            "attempt_index": attempt,
            "turns": dialogue,
            "metadata": {
                "num_turns": len(dialogue),
                "timestamp": ""
            }
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)

        logger.info(f"Saved dialogue to {filepath}")
        return str(filepath)
