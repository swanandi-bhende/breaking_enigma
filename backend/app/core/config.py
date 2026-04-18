from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str = (
        "postgresql+asyncpg://adwf:adwf_dev_password@localhost:5432/adwf"
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 50

    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None

    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    SECRET_KEY: str = "your-32-char-secret-key-change-in-production"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:3000"

    LOG_LEVEL: str = "INFO"

    MAX_QA_ITERATIONS: int = 3
    DEFAULT_TARGET_PLATFORM: str = "web"
    ARTIFACT_STORAGE_PATH: str = "./artifacts"

    SERP_API_KEY: Optional[str] = None
    CRUNCHBASE_API_KEY: Optional[str] = None

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
