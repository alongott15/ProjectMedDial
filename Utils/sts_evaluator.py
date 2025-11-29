"""
STS (Semantic Textual Similarity) Evaluator.

This module computes semantic similarity between EHR summaries and dialogue summaries
using sentence transformer models.
"""

import logging
from typing import Dict, Tuple, Optional
import numpy as np

logger = logging.getLogger(__name__)


class STSEvaluator:
    """
    Computes Semantic Textual Similarity between text pairs.

    Uses sentence transformer models for embedding-based similarity.
    """

    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """
        Initialize the STS Evaluator.

        Args:
            model_name: Sentence transformer model to use.
                       Defaults to 'all-MiniLM-L6-v2' (fast, lightweight).
                       For medical domain, consider 'pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb'.
        """
        self.model_name = model_name
        self.model = None
        self._load_model()

    def _load_model(self):
        """Load the sentence transformer model."""
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Loaded STS model: {self.model_name}")

        except ImportError:
            logger.error(
                "sentence-transformers library not found. "
                "Install with: pip install sentence-transformers"
            )
            self.model = None

        except Exception as e:
            logger.error(f"Failed to load STS model {self.model_name}: {e}")
            self.model = None

    def compute_similarity(self, text1: str, text2: str) -> float:
        """
        Compute cosine similarity between two texts.

        Args:
            text1: First text (e.g., EHR summary).
            text2: Second text (e.g., dialogue summary).

        Returns:
            Similarity score (0.0 to 1.0), or -1.0 if model not available.
        """
        if not self.model:
            logger.warning("STS model not available, returning -1.0")
            return -1.0

        if not text1 or not text2:
            logger.warning("Empty text provided for similarity computation")
            return 0.0

        try:
            # Generate embeddings
            embeddings = self.model.encode([text1, text2], convert_to_numpy=True)

            # Compute cosine similarity
            from sklearn.metrics.pairwise import cosine_similarity
            similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]

            # Ensure result is in valid range
            similarity = max(0.0, min(1.0, float(similarity)))

            logger.debug(f"Computed STS score: {similarity:.4f}")
            return similarity

        except ImportError:
            logger.error("scikit-learn not found. Install with: pip install scikit-learn")
            return -1.0

        except Exception as e:
            logger.error(f"Error computing similarity: {e}")
            return -1.0

    def compute_detailed_similarity(self, text1: str, text2: str) -> Dict:
        """
        Compute detailed similarity metrics.

        Args:
            text1: First text.
            text2: Second text.

        Returns:
            Dictionary with detailed metrics:
            {
                "cosine_similarity": float,
                "text1_length": int,
                "text2_length": int,
                "length_ratio": float
            }
        """
        cosine_sim = self.compute_similarity(text1, text2)

        len1 = len(text1.split()) if text1 else 0
        len2 = len(text2.split()) if text2 else 0
        length_ratio = min(len1, len2) / max(len1, len2) if max(len1, len2) > 0 else 0.0

        return {
            "cosine_similarity": cosine_sim,
            "text1_length": len1,
            "text2_length": len2,
            "length_ratio": length_ratio
        }

    def evaluate_ehr_dialogue_similarity(self,
                                         ehr_summary: str,
                                         dialogue_summary: str,
                                         profile_id: str = None) -> Dict:
        """
        Evaluate similarity between EHR and dialogue summaries.

        This is the main method for the pipeline, producing the output
        format specified in the PRD.

        Args:
            ehr_summary: Summary of the EHR clinical note.
            dialogue_summary: Summary of the synthetic dialogue.
            profile_id: Optional profile identifier.

        Returns:
            STS evaluation dictionary:
            {
                "profile_id": str,
                "ehr_summary_length": int,
                "dialogue_summary_length": int,
                "sts_score": float,
                "length_ratio": float,
                "model_used": str
            }
        """
        logger.info(f"Evaluating EHR-dialogue similarity for profile {profile_id}")

        detailed = self.compute_detailed_similarity(ehr_summary, dialogue_summary)

        result = {
            "profile_id": profile_id or "unknown",
            "ehr_summary_length": detailed["text1_length"],
            "dialogue_summary_length": detailed["text2_length"],
            "sts_score": detailed["cosine_similarity"],
            "length_ratio": detailed["length_ratio"],
            "model_used": self.model_name
        }

        logger.info(f"  STS score: {result['sts_score']:.4f}")

        return result


# Factory function
def create_sts_evaluator(model_name: str = 'all-MiniLM-L6-v2') -> STSEvaluator:
    """
    Create an STS evaluator instance.

    Args:
        model_name: Sentence transformer model name.

    Returns:
        STSEvaluator instance.
    """
    return STSEvaluator(model_name=model_name)
