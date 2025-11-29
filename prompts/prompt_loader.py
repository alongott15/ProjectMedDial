"""
Prompt loading utilities for bias-aware, hallucination-resistant prompts.

This module provides a centralized way to load and combine prompt templates
for all agents in the synthetic dialogue framework.
"""

from pathlib import Path
from typing import Dict


class PromptLoader:
    """Loads and combines bias-aware prompt templates."""

    def __init__(self, prompts_dir: Path = None):
        """
        Initialize the prompt loader.

        Args:
            prompts_dir: Directory containing prompt template files.
                        Defaults to the 'prompts' directory in the project root.
        """
        if prompts_dir is None:
            self.prompts_dir = Path(__file__).parent
        else:
            self.prompts_dir = Path(prompts_dir)

        self._cache: Dict[str, str] = {}

    def _load_file(self, filename: str) -> str:
        """Load a prompt template file."""
        if filename not in self._cache:
            filepath = self.prompts_dir / filename
            with open(filepath, 'r', encoding='utf-8') as f:
                self._cache[filename] = f.read().strip()
        return self._cache[filename]

    def get_base_system_prompt(self) -> str:
        """Get the base system prompt used across all agents."""
        return self._load_file('base_system_prompt.txt')

    def get_gtmf_extraction_prompt(self) -> str:
        """Get the full GTMF extraction prompt."""
        base = self.get_base_system_prompt()
        task = self._load_file('gtmf_extraction_prompt.txt')
        return f"{base}\n\n{task}"

    def get_patient_agent_prompt(self) -> str:
        """Get the full patient agent prompt."""
        base = self.get_base_system_prompt()
        task = self._load_file('patient_agent_prompt.txt')
        return f"{base}\n\n{task}"

    def get_doctor_agent_prompt(self) -> str:
        """Get the full doctor agent prompt."""
        base = self.get_base_system_prompt()
        task = self._load_file('doctor_agent_prompt.txt')
        return f"{base}\n\n{task}"

    def get_judge_agent_prompt(self) -> str:
        """Get the full judge agent prompt."""
        base = self.get_base_system_prompt()
        task = self._load_file('judge_agent_prompt.txt')
        return f"{base}\n\n{task}"

    def get_ehr_summarizer_prompt(self) -> str:
        """Get the full EHR summarizer prompt."""
        base = self.get_base_system_prompt()
        task = self._load_file('ehr_summarizer_prompt.txt')
        return f"{base}\n\n{task}"

    def get_dialogue_summarizer_prompt(self) -> str:
        """Get the full dialogue summarizer prompt."""
        base = self.get_base_system_prompt()
        task = self._load_file('dialogue_summarizer_prompt.txt')
        return f"{base}\n\n{task}"

    def get_prompt_improvement_prompt(self) -> str:
        """Get the full prompt improvement agent prompt."""
        base = self.get_base_system_prompt()
        task = self._load_file('prompt_improvement_prompt.txt')
        return f"{base}\n\n{task}"


# Global instance for easy access
_global_loader = None


def get_prompt_loader() -> PromptLoader:
    """Get the global prompt loader instance."""
    global _global_loader
    if _global_loader is None:
        _global_loader = PromptLoader()
    return _global_loader
