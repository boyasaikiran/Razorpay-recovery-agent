"""
Centralized application configuration.

All configuration is loaded from environment variables (see .env.example
at the repo root). Never hardcode secrets here.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App ---
    app_name: str = "recovery-orchestrator"
    app_env: str = "development"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    # --- CORS ---
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    # --- Database (Phase 2) ---
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/recovery_orchestrator"
    database_url_async: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/recovery_orchestrator"

    # --- Razorpay (Phase 4) ---
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    razorpay_mode: str = "simulated"

    # --- LLM (Phase 6) ---
    llm_provider: str = "anthropic"
    llm_api_key: str = ""
    llm_model: str = ""

    # --- Security ---
    app_secret_key: str = "change-me-in-production"
    api_key: str = ""
    rate_limit_enabled: bool = True
    rate_limit_simulate_events_per_minute: int = 300
    rate_limit_evaluation_per_minute: int = 10

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — read once per process."""
    return Settings()
