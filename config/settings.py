import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger

# Base directory paths
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"


class AgentSettings(BaseModel):
    name: str = "JARVIS"
    version: str = "2.0.0"
    max_iterations: int = 10
    timeout_seconds: int = 120
    enable_feedback_loop: bool = True
    max_self_correction_attempts: int = 3
    enable_long_term_memory: bool = True
    enable_short_term_memory: bool = True
    context_window_size: int = 10


class ToolsSettings(BaseModel):
    safe_mode: bool = True
    require_confirmation_for_destructive_actions: bool = True
    command_timeout_seconds: int = 30
    screenshot_dir: str = "data/raw/screenshots"
    downloads_dir: str = "data/raw/downloads"


class PathsSettings(BaseModel):
    data_dir: str = "data"
    raw_dir: str = "data/raw"
    processed_dir: str = "data/processed"
    vector_db_dir: str = "data/vector_db"
    logs_dir: str = "logs"


class LLMSettings(BaseModel):
    provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    default_model: str = "qwen2.5:7b"
    vision_model: str = "llava:7b"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384
    temperature: float = 0.3
    num_ctx: int = 8192
    top_p: float = 0.85


class CloudFallbackSettings(BaseModel):
    enabled: bool = False
    provider: str = "gemini"
    model_name: str = "gemini-1.5-flash"
    api_key_env: str = "GEMINI_API_KEY"


class LoggingSettings(BaseModel):
    level: str = "INFO"
    format: str = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{extra[source]: <16}</cyan> - <level>{message}</level>"
    )
    file_format: str = "[{time:YYYY-MM-DD HH:mm:ss.SSS}] [{level: <8}] [{extra[source]: <16}] {message}"
    file_path: str = "logs/jarvis-{time:YYYY-MM-DD}.log"
    rotation: str = "10 MB"
    retention: str = "7 days"
    compression: str = "zip"
    backtrace: bool = True
    diagnose: bool = True


def _load_yaml(file_path: Path) -> Dict[str, Any]:
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server / App Environment
    port: int = Field(default=8000, validation_alias="PORT")
    env: str = Field(default="development", validation_alias="NODE_ENV")

    # Optional cloud API keys from .env
    gemini_api_key: Optional[str] = Field(default=None, validation_alias="GEMINI_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, validation_alias="OPENAI_API_KEY")
    google_search_api_key: Optional[str] = Field(default=None, validation_alias="GOOGLE_SEARCH_API_KEY")
    google_search_cx: Optional[str] = Field(default=None, validation_alias="GOOGLE_SEARCH_CX")
    serper_api_key: Optional[str] = Field(default=None, validation_alias="SERPER_API_KEY")
    tavily_api_key: Optional[str] = Field(default=None, validation_alias="TAVILY_API_KEY")

    # Sub-configs populated from YAML
    agent: AgentSettings = Field(default_factory=AgentSettings)
    tools: ToolsSettings = Field(default_factory=ToolsSettings)
    paths: PathsSettings = Field(default_factory=PathsSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    cloud_fallback: CloudFallbackSettings = Field(default_factory=CloudFallbackSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    @classmethod
    def load(cls) -> "AppSettings":
        agent_yaml = _load_yaml(CONFIG_DIR / "agent_config.yaml")
        model_yaml = _load_yaml(CONFIG_DIR / "model_config.yaml")
        logging_yaml = _load_yaml(CONFIG_DIR / "logging_config.yaml")

        data: Dict[str, Any] = {}
        if "agent" in agent_yaml:
            data["agent"] = agent_yaml["agent"]
        if "tools" in agent_yaml:
            data["tools"] = agent_yaml["tools"]
        if "paths" in agent_yaml:
            data["paths"] = agent_yaml["paths"]

        if "llm" in model_yaml:
            data["llm"] = model_yaml["llm"]
        if "cloud_fallback" in model_yaml:
            data["cloud_fallback"] = model_yaml["cloud_fallback"]

        if "logging" in logging_yaml:
            data["logging"] = logging_yaml["logging"]

        # Environment variable override for ACTIVE_MODEL and NUM_CTX (from .env.example)
        active_model = os.getenv("ACTIVE_MODEL")
        if active_model:
            if "llm" not in data:
                data["llm"] = {}
            data["llm"]["default_model"] = active_model

        num_ctx = os.getenv("NUM_CTX")
        if num_ctx:
            if "llm" not in data:
                data["llm"] = {}
            try:
                data["llm"]["num_ctx"] = int(num_ctx)
            except ValueError:
                pass

        instance = cls(**data)
        instance.ensure_directories()
        return instance

    def ensure_directories(self) -> None:
        """Create required runtime folders if not present."""
        for path_str in [
            self.paths.data_dir,
            self.paths.raw_dir,
            self.paths.processed_dir,
            self.paths.vector_db_dir,
            self.paths.logs_dir,
            self.tools.screenshot_dir,
            self.tools.downloads_dir,
        ]:
            target = BASE_DIR / path_str
            target.mkdir(parents=True, exist_ok=True)


# Initialize global settings
settings = AppSettings.load()


def setup_logger():
    """Configure Loguru with format, rotation, and handlers."""
    logger.remove()

    # Console Handler
    logger.add(
        sys.stdout,
        level=settings.logging.level,
        format=settings.logging.format,
        colorize=True,
        backtrace=settings.logging.backtrace,
        diagnose=settings.logging.diagnose,
    )

    # File Handler
    log_file = BASE_DIR / settings.logging.file_path
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_file),
        level=settings.logging.level,
        format=settings.logging.file_format,
        rotation=settings.logging.rotation,
        retention=settings.logging.retention,
        compression=settings.logging.compression,
        backtrace=settings.logging.backtrace,
        diagnose=settings.logging.diagnose,
        encoding="utf-8",
    )


# Run setup logger on import
setup_logger()


def get_logger(source: str = "JARVIS"):
    """Return a contextualized logger with bound source metadata."""
    return logger.bind(source=source)
