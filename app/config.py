"""Application configuration management."""

from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = Field(
        default="sqlite:///./teckochecker.db", description="Database connection URL"
    )

    # Security
    secret_key: str = Field(..., description="Secret key for encryption (required)")

    # Polling configuration
    default_poll_interval: int = Field(
        default=120, ge=30, le=3600, description="Default polling interval in seconds"
    )
    min_poll_interval: int = Field(
        default=30, description="Minimum allowed polling interval in seconds"
    )
    max_poll_interval: int = Field(
        default=3600, description="Maximum allowed polling interval in seconds"
    )
    max_retries: int = Field(default=3, description="Maximum retry attempts for failed operations")
    retry_delay: int = Field(default=60, description="Delay between retries in seconds")

    # API configuration
    api_host: str = Field(default="0.0.0.0", description="API host to bind to")
    api_port: int = Field(default=8000, description="API port to bind to")
    api_title: str = Field(default="TeckoChecker API", description="API title for documentation")
    api_version: str = Field(default="0.9.0", description="API version")
    api_description: str = Field(
        default="Polling orchestration system for monitoring asynchronous jobs",
        description="API description",
    )

    # CORS configuration
    cors_origins: list[str] = Field(default=["*"], description="Allowed CORS origins")
    cors_allow_credentials: bool = Field(
        default=True, description="Allow credentials in CORS requests"
    )
    cors_allow_methods: list[str] = Field(
        default=["*"], description="Allowed HTTP methods for CORS"
    )
    cors_allow_headers: list[str] = Field(default=["*"], description="Allowed headers for CORS")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Optional[str] = Field(
        default=None, description="Log file path (if None, logs to console only)"
    )

    # Application
    debug: bool = Field(default=False, description="Enable debug mode")
    environment: str = Field(default="development", description="Application environment")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Global settings instance
settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global settings
    if settings is None:
        settings = Settings()
    return settings


def load_settings() -> Settings:
    """Load settings from environment variables."""
    global settings
    settings = Settings()
    return settings
