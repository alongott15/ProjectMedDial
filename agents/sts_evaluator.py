"""STS Evaluator Agent - Computes semantic textual similarity"""
import json
import logging
from pathlib import Path
from typing import Dict
from sentence_transformers import SentenceTransformer
import torch

logger = logging.getLogger(__name__)


class STSEvaluatorAgent:
    """Evaluates semantic textual similarity between EHR and dialogue summaries"""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", output_dir: str = "outputs/sts"):
        self.model_name = model_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Load STS model
        try:
            self.model = SentenceTransformer(model_name)
            logger.info(f"Loaded STS model: {model_name}")
        except Exception as e:
            logger.error(f"Error loading STS model: {e}")
            self.model = None

    def compute_similarity(self, text1: str, text2: str) -> float:
        """Compute semantic similarity between two texts"""
        if not self.model:
            logger.error("STS model not loaded")
            return 0.0

        if not text1 or not text2:
            logger.warning("Empty text provided for STS")
            return 0.0

        try:
            # Encode texts
            embeddings = self.model.encode([text1, text2], convert_to_tensor=True)

            # Compute cosine similarity
            similarity = torch.nn.functional.cosine_similarity(
                embeddings[0].unsqueeze(0),
                embeddings[1].unsqueeze(0)
            )

            score = similarity.item()
            logger.info(f"Computed STS score: {score:.4f}")
            return score

        except Exception as e:
            logger.error(f"Error computing STS: {e}")
            return 0.0

    def evaluate(self, ehr_summary: str, dialogue_summary: str, profile_id: str, hadm_id: int, subject_id: int) -> float:
        """
        Evaluate similarity and save results

        Returns STS score
        """
        score = self.compute_similarity(ehr_summary, dialogue_summary)

        # Save results
        self.save_results(profile_id, hadm_id, subject_id, score)

        return score

    def save_results(self, profile_id: str, hadm_id: int, subject_id: int, score: float) -> str:
        """Save STS results to JSON"""
        filename = f"sts_{profile_id}.json"
        filepath = self.output_dir / filename

        output = {
            "profile_id": profile_id,
            "subject_id": subject_id,
            "hadm_id": hadm_id,
            "sts_score": score,
            "model": self.model_name,
            "metadata": {
                "timestamp": "",
                "extra": {}
            }
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)

        logger.info(f"Saved STS results to {filepath}")
        return str(filepath)
