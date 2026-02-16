"""Configuration management for Professor."""

from typing import Any, Optional
from pathlib import Path
import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM provider settings."""

    provider: str = Field(default="anthropic", description="LLM provider to use")
    model: str = Field(
        default="claude-3-5-sonnet-20240620", description="Model name"
    )
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, ge=1)
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    requests_per_minute: int = Field(default=50, description="Rate limit")

    model_config = SettingsConfigDict(env_prefix="")


class GitHubSettings(BaseSettings):
    """GitHub integration settings."""

    token: Optional[str] = Field(default=None, alias="GITHUB_TOKEN")
    app_id: Optional[str] = Field(default=None, alias="GITHUB_APP_ID")
    app_private_key_path: Optional[str] = Field(
        default=None, alias="GITHUB_APP_PRIVATE_KEY_PATH"
    )
    webhook_secret: Optional[str] = Field(
        default=None, alias="GITHUB_WEBHOOK_SECRET"
    )
    requests_per_minute: int = Field(default=5000)

    model_config = SettingsConfigDict(env_prefix="")


class DatabaseSettings(BaseSettings):
    """Database settings."""

    url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/professor",
        alias="DATABASE_URL",
    )

    model_config = SettingsConfigDict(env_prefix="")


class RedisSettings(BaseSettings):
    """Redis settings."""

    url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    model_config = SettingsConfigDict(env_prefix="")


class APISettings(BaseSettings):
    """API server settings."""

    host: str = Field(default="0.0.0.0", alias="API_HOST")
    port: int = Field(default=8000, alias="API_PORT")
    workers: int = Field(default=4, alias="API_WORKERS")

    model_config = SettingsConfigDict(env_prefix="")


class ReviewSettings(BaseSettings):
    """Review behavior settings."""

    max_review_files: int = Field(default=50, alias="MAX_REVIEW_FILES")
    max_file_size_kb: int = Field(default=500, alias="MAX_FILE_SIZE_KB")
    timeout_seconds: int = Field(default=300, alias="REVIEW_TIMEOUT_SECONDS")

    model_config = SettingsConfigDict(env_prefix="")


class LogSettings(BaseSettings):
    """Logging settings."""

    level: str = Field(default="INFO", alias="LOG_LEVEL")
    format: str = Field(default="json", alias="LOG_FORMAT")

    model_config = SettingsConfigDict(env_prefix="")


class Settings(BaseSettings):
    """Main application settings."""

    env: str = Field(default="development", alias="PROFESSOR_ENV")
    llm: LLMSettings = Field(default_factory=LLMSettings)
    github: GitHubSettings = Field(default_factory=GitHubSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    api: APISettings = Field(default_factory=APISettings)
    review: ReviewSettings = Field(default_factory=ReviewSettings)
    log: LogSettings = Field(default_factory=LogSettings)

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @classmethod
    def from_yaml(cls, path: Path) -> "Settings":
        """Load settings from YAML file.

        Args:
            path: Path to YAML configuration file

        Returns:
            Settings instance
        """
        with open(path) as f:
            config = yaml.safe_load(f)

        return cls(**config)


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get global settings instance.

    Returns:
        Settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def set_settings(settings: Settings) -> None:
    """Set global settings instance.

    Args:
        settings: Settings to use
    """
    global _settings
    _settings = settings
