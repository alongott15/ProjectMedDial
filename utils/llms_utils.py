"""LLM Client utilities for Hugging Face"""
import logging
import os
from typing import List, Dict
from huggingface_hub import InferenceClient
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class LLMClient:
    """Unified LLM client for Hugging Face Inference API"""

    def __init__(self, api_key: str = None, model_name: str = "gpt-oss-120b"):
        self.api_key = api_key or os.getenv("HUGGINGFACE_API_KEY")
        self.model_name = model_name

        if not self.api_key:
            raise ValueError("Hugging Face API key must be provided via HUGGINGFACE_API_KEY environment variable")

        self.client = InferenceClient(token=self.api_key)
        logger.info(f"Initialized Hugging Face client with model: {model_name}")

    def chat_completion(self, system_message: str, user_message: str, temperature: float = 0.7, max_tokens: int = 512) -> str:
        """Generate chat completion with system and user messages"""
        try:
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ]

            response = self.client.chat_completion(
                messages=messages,
                model=self.model_name,
                temperature=temperature,
                max_tokens=max_tokens
            )

            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error in Hugging Face chat completion: {e}")
            raise

    def chat_completion_messages(self, messages: List[Dict], temperature: float = 0.7, max_tokens: int = 512) -> str:
        """Generate chat completion with a list of messages"""
        try:
            response = self.client.chat_completion(
                messages=messages,
                model=self.model_name,
                temperature=temperature,
                max_tokens=max_tokens
            )

            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error in Hugging Face chat completion: {e}")
            raise


# Legacy compatibility functions for old code
class HuggingFaceCompatClient:
    """Hugging Face-compatible client for backward compatibility"""

    def __init__(self, model_name='gpt-oss-120b', temperature=0.3, max_tokens=512):
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.api_key = os.getenv("HUGGINGFACE_API_KEY")

        if not self.api_key:
            logger.error("Hugging Face API key not found in environment variables.")
            raise ValueError("HUGGINGFACE_API_KEY must be set.")

        try:
            self.client = InferenceClient(token=self.api_key)
            logger.info(f"Loaded Hugging Face model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Hugging Face client: {e}")
            raise


def load_gpt_model(model_name='gpt-oss-120b', temperature=0.3, max_tokens=512):
    """Load a Hugging Face model (backward compatibility)"""
    return HuggingFaceCompatClient(model_name, temperature, max_tokens)


def chat_generate(llm: HuggingFaceCompatClient, messages: List[Dict[str, str]]) -> str:
    """Enhanced chat generation with Hugging Face API"""
    logger.debug(f"[chat_generate] Sending {len(messages)} messages to Hugging Face")

    try:
        response = llm.client.chat_completion(
            messages=messages,
            model=llm.model_name,
            temperature=llm.temperature,
            max_tokens=llm.max_tokens
        )

        text_content = response.choices[0].message.content.strip()
        logger.debug(f"[chat_generate] Hugging Face response: {text_content[:100]}...")
        return text_content

    except Exception as e:
        logger.error(f"Error during Hugging Face invocation: {e}")
        return "[ERROR: Could not generate response from Hugging Face]"
