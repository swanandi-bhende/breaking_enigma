"""
Application settings — loads from environment variables / .env file.
Uses pydantic-settings for validation and type coercion.

Owned by: Nisarg (Workflow Engine & Agent Orchestration)
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://adwf:adwf_dev_password@localhost:5432/adwf"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ── Redis ───────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 50

    # ── Qdrant ──────────────────────────────────────────────────────────────
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None

    # ── OpenAI ──────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # ── Application ─────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production-32-chars!!"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:3000"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False

    # ── Pipeline Config ──────────────────────────────────────────────────────
    MAX_QA_ITERATIONS: int = 3
    DEFAULT_TARGET_PLATFORM: str = "web"
    ARTIFACT_STORAGE_PATH: str = "/app/artifacts"

    # ── Optional External APIs ───────────────────────────────────────────────
    SERP_API_KEY: Optional[str] = None
    CRUNCHBASE_API_KEY: Optional[str] = None

    # ── Celery ──────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: str) -> str:
        # Accept comma-separated string; keep raw for property below
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton — call this everywhere instead of importing Settings directly."""
    return Settings()


settings: Settings = get_settings()
