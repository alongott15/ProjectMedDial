"""LLM Client utilities for OpenAI API"""
import logging
import os
from typing import List, Dict
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class LLMClient:
    """Unified LLM client for OpenAI API"""

    def __init__(self, api_key: str = None, model_name: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model_name

        if not self.api_key:
            raise ValueError("OpenAI API key must be provided via OPENAI_API_KEY environment variable")

        self.client = OpenAI(api_key=self.api_key)
        logger.info(f"Initialized OpenAI client with model: {model_name}")

    def chat_completion(self, system_message: str, user_message: str, temperature: float = 0.7, max_tokens: int = 512) -> str:
        """Generate chat completion with system and user messages"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error in chat completion: {e}")
            raise

    def chat_completion_messages(self, messages: List[Dict], temperature: float = 0.7, max_tokens: int = 512) -> str:
        """Generate chat completion with a list of messages"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error in chat completion: {e}")
            raise


# Legacy compatibility functions for old code
class OpenAICompatClient:
    """OpenAI-compatible client for backward compatibility"""

    def __init__(self, model_name='gpt-4o', temperature=0.3, max_tokens=512):
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.api_key = os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            logger.error("OpenAI API key not found in environment variables.")
            raise ValueError("OPENAI_API_KEY must be set.")

        try:
            self.client = OpenAI(api_key=self.api_key)
            logger.info(f"Loaded OpenAI model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise


def load_gpt_model(model_name='gpt-4o', temperature=0.3, max_tokens=512):
    """Load an OpenAI model (backward compatibility)"""
    return OpenAICompatClient(model_name, temperature, max_tokens)


def chat_generate(llm: OpenAICompatClient, messages: List[Dict[str, str]]) -> str:
    """Enhanced chat generation with OpenAI API"""
    logger.debug(f"[chat_generate] Sending {len(messages)} messages to OpenAI")

    try:
        response = llm.client.chat.completions.create(
            model=llm.model_name,
            messages=messages,
            temperature=llm.temperature,
            max_tokens=llm.max_tokens,
            top_p=0.95,
            frequency_penalty=0.1,
            presence_penalty=0.1
        )

        text_content = response.choices[0].message.content.strip()
        logger.debug(f"[chat_generate] OpenAI response: {text_content[:100]}...")
        return text_content

    except Exception as e:
        logger.error(f"Error during OpenAI invocation: {e}")
        return "[ERROR: Could not generate response from OpenAI]"
