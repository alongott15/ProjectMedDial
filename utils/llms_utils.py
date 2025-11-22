import logging
import os
from typing import List, Dict
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage, AssistantMessage
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class AzureAIFoundryClient:
    """Enhanced Azure AI Foundry client with improved conversation handling"""
    
    def __init__(self, model_name='gpt-4.1', temperature=0.3, max_tokens=512):
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Azure AI Foundry configuration
        self.endpoint = os.getenv("AZURE_AI_ENDPOINT")
        self.api_key = os.getenv("AZURE_AI_API_KEY")
        
        if not self.endpoint or not self.api_key:
            logger.error("Azure AI Foundry credentials not found in environment variables.")
            raise ValueError("AZURE_AI_FOUNDRY_ENDPOINT and AZURE_AI_FOUNDRY_API_KEY must be set.")
        
        try:
            self.client = ChatCompletionsClient(
                endpoint=self.endpoint,
                credential=AzureKeyCredential(self.api_key)
            )
            logger.info(f"Loaded Azure AI Foundry model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Azure AI Foundry client: {e}")
            raise

def load_gpt_model(model_name='gpt-4.1', temperature=0.3, max_tokens=512):
    """
    Load an Azure AI Foundry model.
    Requires AZURE_AI_FOUNDRY_ENDPOINT and AZURE_AI_FOUNDRY_API_KEY.
    """
    return AzureAIFoundryClient(model_name, temperature, max_tokens)

def chat_generate(llm: AzureAIFoundryClient, messages: List[Dict[str, str]]) -> str:
    """
    Enhanced chat generation with better conversation handling.
    """
    # Convert message dictionaries to Azure AI Foundry message objects
    azure_messages = []
    for msg in messages:
        if msg['role'] == 'system':
            azure_messages.append(SystemMessage(content=msg['content']))
        elif msg['role'] == 'user':
            azure_messages.append(UserMessage(content=msg['content']))
        elif msg['role'] == 'assistant':
            azure_messages.append(AssistantMessage(content=msg['content']))
        else:
            logger.warning(f"Unknown message role: {msg['role']}. Treating as user message.")
            azure_messages.append(UserMessage(content=msg['content']))
    
    logger.debug(f"[chat_generate] Sending {len(azure_messages)} messages to Azure AI Foundry")
    
    try:
        response = llm.client.complete(
            messages=azure_messages,
            model=llm.model_name,
            temperature=llm.temperature,
            max_tokens=llm.max_tokens,
            # Enhanced parameters for more realistic conversations
            top_p=0.95,
            frequency_penalty=0.1,
            presence_penalty=0.1
        )
        
        text_content = response.choices[0].message.content.strip()
        logger.debug(f"[chat_generate] Azure AI response: {text_content[:100]}...")
        return text_content
        
    except Exception as e:
        logger.error(f"Error during Azure AI Foundry invocation: {e}")
        return "[ERROR: Could not generate response from Azure AI Foundry]"