from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    App settings - reads from .env file automatically.
    I used pydantic-settings because it validates types and catches
    missing config early instead of crashing at runtime.
    """

    # General
    APP_NAME: str = "AI Risk Analyst Platform"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "change-this-in-production"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    # PostgreSQL
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "airisk_db"

    # Qdrant vector database
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "risk_document_chunks"

    # LLM settings (Supports OpenRouter & OpenAI)
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    LLM_MODEL: str = "openrouter/free"

    # n8n automation
    N8N_WEBHOOK_URL: str = "http://localhost:5678/webhook/risk-analysis-report"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Cache settings so .env is only read once."""
    return Settings()


settings = get_settings()
