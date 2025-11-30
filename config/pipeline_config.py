"""
Pipeline configuration for the synthetic patient-physician conversation framework.

This module defines configuration parameters for all stages of the pipeline.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional
import json
import yaml
from pathlib import Path


@dataclass
class DataSourceConfig:
    """Data source configuration (CSV or Database)."""
    source_type: str = "csv"  # "csv" or "database"
    csv_file_path: Optional[str] = "sample_mimic_notes.csv"  # Path to CSV file
    database_url: Optional[str] = None  # PostgreSQL connection string
    batch_size: int = 50
    max_total_records: Optional[int] = None
    offset: int = 0


@dataclass
class GTMFConfig:
    """GTMF extraction configuration."""
    gtmf_batch_size: int = 20
    use_llm_judge: bool = True
    enable_chunking: bool = True
    model_name: str = "gpt-4"


@dataclass
class ProfileConfig:
    """Profile generation configuration."""
    profile_types: List[str] = field(default_factory=lambda: ["NO_DIAGNOSIS_NO_TREATMENT"])
    # Options: "FULL", "NO_DIAGNOSIS", "NO_DIAGNOSIS_NO_TREATMENT"


@dataclass
class DialogueConfig:
    """Dialogue generation configuration."""
    max_turns: int = 16
    max_attempts_per_profile: int = 3
    max_processing_time: float = 300.0  # seconds
    model_name: str = "gpt-4.1"
    temperature: float = 0.3


@dataclass
class JudgeConfig:
    """Judge agent configuration."""
    model_name: str = "gpt-4.1"
    temperature: float = 0.2
    threshold: float = 0.6  # Minimum score for REALISTIC
    max_tokens: int = 1000


@dataclass
class STSConfig:
    """STS evaluation configuration."""
    model_name: str = "all-MiniLM-L6-v2"
    # Alternative for medical domain: "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb"


@dataclass
class OutputConfig:
    """Output configuration."""
    base_dir: str = "outputs"
    ehr_dir: str = "outputs/ehr"
    gtmf_dir: str = "outputs/gtmf"
    profiles_dir: str = "outputs/profiles"
    dialogues_dir: str = "outputs/dialogues"
    judge_dir: str = "outputs/judge"
    summaries_dir: str = "outputs/summaries"
    sts_dir: str = "outputs/sts"
    stats_dir: str = "outputs/stats"
    runs_dir: str = "outputs/runs"
    create_dirs: bool = True


@dataclass
class PipelineConfig:
    """Complete pipeline configuration."""
    run_name: str = "synthetic_dialogue_run"
    data_source: DataSourceConfig = field(default_factory=DataSourceConfig)
    gtmf: GTMFConfig = field(default_factory=GTMFConfig)
    profile: ProfileConfig = field(default_factory=ProfileConfig)
    dialogue: DialogueConfig = field(default_factory=DialogueConfig)
    judge: JudgeConfig = field(default_factory=JudgeConfig)
    sts: STSConfig = field(default_factory=STSConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return asdict(self)

    def to_json(self, filepath: str) -> None:
        """Save configuration to JSON file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)

    def to_yaml(self, filepath: str) -> None:
        """Save configuration to YAML file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)

    @classmethod
    def from_dict(cls, config_dict: dict) -> 'PipelineConfig':
        """Load configuration from dictionary."""
        # Support both 'data_source' (new) and 'database' (old) for backward compatibility
        data_source_config = config_dict.get('data_source', config_dict.get('database', {}))

        return cls(
            run_name=config_dict.get('run_name', 'synthetic_dialogue_run'),
            data_source=DataSourceConfig(**data_source_config),
            gtmf=GTMFConfig(**config_dict.get('gtmf', {})),
            profile=ProfileConfig(**config_dict.get('profile', {})),
            dialogue=DialogueConfig(**config_dict.get('dialogue', {})),
            judge=JudgeConfig(**config_dict.get('judge', {})),
            sts=STSConfig(**config_dict.get('sts', {})),
            output=OutputConfig(**config_dict.get('output', {}))
        )

    @classmethod
    def from_json(cls, filepath: str) -> 'PipelineConfig':
        """Load configuration from JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            config_dict = json.load(f)
        return cls.from_dict(config_dict)

    @classmethod
    def from_yaml(cls, filepath: str) -> 'PipelineConfig':
        """Load configuration from YAML file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            config_dict = yaml.safe_load(f)
        return cls.from_dict(config_dict)

    def create_output_directories(self) -> None:
        """Create all output directories."""
        if not self.output.create_dirs:
            return

        directories = [
            self.output.base_dir,
            self.output.ehr_dir,
            self.output.gtmf_dir,
            self.output.profiles_dir,
            self.output.dialogues_dir,
            self.output.judge_dir,
            self.output.summaries_dir,
            self.output.sts_dir,
            self.output.stats_dir,
            self.output.runs_dir
        ]

        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)


def create_default_config() -> PipelineConfig:
    """Create a default pipeline configuration."""
    return PipelineConfig()


def save_default_config_yaml(filepath: str = "config/default_config.yaml") -> None:
    """Save default configuration to YAML file."""
    config = create_default_config()
    config.to_yaml(filepath)


def save_default_config_json(filepath: str = "config/default_config.json") -> None:
    """Save default configuration to JSON file."""
    config = create_default_config()
    config.to_json(filepath)
