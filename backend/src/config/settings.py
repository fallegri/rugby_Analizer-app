"""Application configuration using pydantic-settings."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Rugby Analyzer"
    app_version: str = "0.1.0"
    debug: bool = True
    production: bool = False
    log_level: str = "INFO"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"]
    )

    # AI Provider Configuration
    default_ai_provider: str = "nvidia"

    # NVIDIA
    nvidia_api_key: Optional[str] = None
    nvidia_model: str = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"

    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4"
    openai_base_url: str = "https://api.openai.com/v1"

    # Claude (Anthropic)
    claude_api_key: Optional[str] = None
    claude_model: str = "claude-3-5-sonnet-20241022"
    claude_base_url: str = "https://api.anthropic.com/v1"

    # Gemini (Google)
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-pro"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    # Ollama (Local)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"

    # File Upload
    upload_dir: str = "uploads"
    max_file_size_mb: int = 500

    # Database
    database_url: str = "sqlite+aiosqlite:///./rugby_analyzer.db"

    # Redis (optional)
    redis_url: Optional[str] = None

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    # Authentication
    secret_key: str = "dev-secret-key-change-in-production"
    api_key_header: str = "X-API-Key"

    # WebSocket
    ws_heartbeat_interval: int = 30


_DEFAULT_SECRET_KEY = "dev-secret-key-change-in-production"


def validate_settings(settings: "Settings") -> None:
    """Validate settings at startup.

    Only enforces secret key validation when PRODUCTION=true is explicitly set.
    For local development the app starts freely without any .env configuration;
    API keys are configured from the UI at runtime.

    Raises:
        RuntimeError: If running in production mode with default secret key.
    """
    if settings.production and settings.secret_key == _DEFAULT_SECRET_KEY:
        raise RuntimeError(
            "SECURITY ERROR: Cannot run in production mode (PRODUCTION=true) with the "
            "default secret key. Set a secure SECRET_KEY environment variable."
        )


def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
