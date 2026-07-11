"""Application configuration.

Reads from environment variables / a local `.env` file via pydantic-settings.
No business logic lives here — only config surface used to wire the app together.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings, sourced from env / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Groq is used ONLY to translate finished structured results into natural
    # language (Phase 6). It never calculates, detects, scores, or decides.
    groq_api_key: str = ""
    # Verify the exact model name on the Groq dashboard (models change over time).
    groq_model: str = "llama-3.3-70b-versatile"
    # Keep the demo snappy: a short timeout and a single retry, else fall back.
    groq_timeout_seconds: float = 8.0
    groq_max_retries: int = 1

    # SQLite for the prototype.
    database_url: str = "sqlite:///./prohoripay.db"

    # Comma-separated list of allowed CORS origins.
    cors_origins: str = "http://localhost:3000,https://prohoripay-v1.vercel.app"

    @property
    def cors_origins_list(self) -> list[str]:
        """CORS origins as a clean list, split from the comma-separated env value."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
