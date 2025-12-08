"""
STSEvaluatorAgent - Computes Semantic Textual Similarity between summaries.
"""

import logging
from typing import Tuple
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class STSEvaluatorAgent:
    """
    Computes Semantic Textual Similarity (STS) between EHR and dialogue summaries.

    Uses sentence-transformers for semantic similarity scoring.
    """

    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """
        Initialize STSEvaluatorAgent.

        Args:
            model_name: Sentence transformer model name
        """
        try:
            from sentence_transformers import SentenceTransformer, util
            self.model = SentenceTransformer(model_name)
            self.util = util
            logger.info(f"STSEvaluatorAgent initialized with model: {model_name}")
        except ImportError:
            logger.error("sentence-transformers not installed. STS evaluation will not work.")
            raise ImportError("Please install sentence-transformers: pip install sentence-transformers")

    def compute_sts(self, text1: str, text2: str) -> float:
        """
        Compute STS score between two texts.

        Args:
            text1: First text (e.g., EHR summary)
            text2: Second text (e.g., dialogue summary)

        Returns:
            STS score (0.0-1.0, higher = more similar)
        """
        if not text1 or not text2:
            logger.warning("Empty text provided for STS computation")
            return 0.0

        try:
            # Encode texts
            embedding1 = self.model.encode(text1, convert_to_tensor=True)
            embedding2 = self.model.encode(text2, convert_to_tensor=True)

            # Compute cosine similarity
            similarity = self.util.pytorch_cos_sim(embedding1, embedding2).item()

            # Clamp to [0, 1]
            similarity = max(0.0, min(1.0, similarity))

            logger.info(f"STS score computed: {similarity:.3f}")
            return similarity

        except Exception as e:
            logger.error(f"Error computing STS: {e}")
            return 0.0

    def compute_sts_detailed(self, text1: str, text2: str) -> dict:
        """
        Compute detailed STS metrics.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Dict with:
                - sts_score: Overall STS score
                - text1_length: Length of text1 in words
                - text2_length: Length of text2 in words
                - embedding_similarity: Cosine similarity of embeddings
        """
        sts_score = self.compute_sts(text1, text2)

        return {
            "sts_score": sts_score,
            "text1_length": len(text1.split()),
            "text2_length": len(text2.split()),
            "embedding_similarity": sts_score
        }
