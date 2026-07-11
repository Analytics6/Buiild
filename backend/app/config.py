from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI / LLM
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    embeddings_provider: Literal["openai", "local"] = "openai"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = True

    # Database
    database_url: str = ""
    db_path: Path = Field(default=PROJECT_ROOT / "data" / "app.db")

    # ChromaDB
    chroma_persist_dir: Path = Field(default=PROJECT_ROOT / "data" / "chroma")
    chroma_collection: str = "complaints"
    data_dir: Path = Field(default=PROJECT_ROOT / "data" / "complaints")

    # Security
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    # Sessions
    session_ttl_seconds: int = 86400
    session_refresh_ttl_seconds: int = 604800

    # Cache TTL
    cache_ttl_seconds: int = 3600
    embedding_cache_ttl_seconds: int = 86400
    rag_cache_ttl_seconds: int = 1800

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # LangSmith tracing
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "complaint-rag"

    valid_roles: tuple[str, ...] = ("admin", "manager", "analyst", "support")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("redis_enabled", mode="before")
    @classmethod
    def parse_bool(cls, value: str | bool) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("1", "true", "yes")

    @property
    def use_postgres(self) -> bool:
        return self.database_url.startswith(("postgresql://", "postgres://"))

    @property
    def sqlite_path(self) -> Path:
        return self.db_path


@lru_cache
def get_settings() -> Settings:
    return Settings()
