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

    # Groq is used only for natural-language explanations in a later phase.
    # Placeholder here so the value is wired now; unused in Phase 0.
    groq_api_key: str = ""

    # SQLite for the prototype.
    database_url: str = "sqlite:///./prohoripay.db"

    # Comma-separated list of allowed CORS origins.
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        """CORS origins as a clean list, split from the comma-separated env value."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
