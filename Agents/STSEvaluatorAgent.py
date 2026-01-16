import logging
from typing import Tuple
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class STSEvaluatorAgent:
    """
    Computes Semantic Textual Similarity (STS) between EHR and dialogue summaries.

    Uses sentence-transformers for semantic similarity scoring.
    Supports medical-specific models for improved performance on medical text.
    """

    AVAILABLE_MODELS = {
        'general': 'all-MiniLM-L6-v2',
        'medical': 'pritamdeka/S-PubMedBert-MS-MARCO',
        'biobert': 'dmis-lab/biobert-base-cased-v1.2',
        'clinical': 'emilyalsentzer/Bio_ClinicalBERT'
    }

    def __init__(self, model_name: str = 'medical'):
        """
        Initialize STSEvaluatorAgent.

        Args:
            model_name: Model name from AVAILABLE_MODELS or custom model path
                       Options: 'general', 'medical', 'biobert', 'clinical'
                       Default: 'medical' (recommended for medical text)
        """
        try:
            from sentence_transformers import SentenceTransformer, util

            # Try specified model first, fallback to general
            try:
                if model_name in self.AVAILABLE_MODELS:
                    model_path = self.AVAILABLE_MODELS[model_name]
                else:
                    model_path = model_name  # Allow custom model paths

                self.model = SentenceTransformer(model_path)
                self.model_name = model_name
                logger.info(f"STSEvaluatorAgent initialized with '{model_name}' model: {model_path}")
            except Exception as e:
                logger.warning(f"Failed to load '{model_name}' model: {e}")
                logger.info("Falling back to general model")
                self.model = SentenceTransformer(self.AVAILABLE_MODELS['general'])
                self.model_name = 'general'

            self.util = util

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
                - model_used: Name of model used
        """
        sts_score = self.compute_sts(text1, text2)

        return {
            "sts_score": sts_score,
            "text1_length": len(text1.split()),
            "text2_length": len(text2.split()),
            "embedding_similarity": sts_score,
            "model_used": self.model_name
        }

    def compute_sts_multi_model(self, text1: str, text2: str, models: list = None) -> dict:
        """
        Compute STS with multiple models for comparison.

        Args:
            text1: First text
            text2: Second text
            models: List of model names to compare. If None, uses ['general', 'medical']

        Returns:
            Dict with scores from different models:
            {
                'general': 0.65,
                'medical': 0.72,
                'best_model': 'medical',
                'best_score': 0.72
            }
        """
        if models is None:
            models = ['general', 'medical']

        try:
            from sentence_transformers import SentenceTransformer

            scores = {}
            for model_name in models:
                if model_name not in self.AVAILABLE_MODELS:
                    logger.warning(f"Model '{model_name}' not in AVAILABLE_MODELS, skipping")
                    continue

                try:
                    temp_model = SentenceTransformer(self.AVAILABLE_MODELS[model_name])
                    embedding1 = temp_model.encode(text1, convert_to_tensor=True)
                    embedding2 = temp_model.encode(text2, convert_to_tensor=True)
                    score = self.util.pytorch_cos_sim(embedding1, embedding2).item()
                    scores[model_name] = max(0.0, min(1.0, score))
                    logger.info(f"  {model_name}: {scores[model_name]:.3f}")
                except Exception as e:
                    logger.warning(f"Skipping {model_name}: {e}")

            if scores:
                best_model = max(scores.items(), key=lambda x: x[1])
                scores['best_model'] = best_model[0]
                scores['best_score'] = best_model[1]

            return scores

        except Exception as e:
            logger.error(f"Error in multi-model comparison: {e}")
            return {}
