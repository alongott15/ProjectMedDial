"""
Bias-aware prompt templates for the synthetic dialogue framework.

All prompts follow the design principle of grounding outputs in provided context
and avoiding hallucinations.
"""

from .prompt_loader import PromptLoader, get_prompt_loader

__all__ = ['PromptLoader', 'get_prompt_loader']
