"""Application settings, loaded once from the environment."""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "AI Knowledge Base API"
    debug: bool = False

    # Database
    database_url: str = "postgresql+psycopg://kb:kb@localhost:5432/knowledge_base"

    # Auth
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # LLM
    gemini_api_key: str = ""
    gemini_chat_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768

    # Deployment mode
    #
    # Whether POST /documents/{id}/process hands embedding to a background task
    # (true) or runs it inline (false). Defaults to inline because that is
    # correct everywhere: serverless platforms freeze the process once a
    # response is sent, so a deferred task would never finish. Long-running
    # hosts (Render, Docker) can opt in to deferring. Either way POST /upload
    # returns immediately, so status is always observable.
    defer_embedding: bool = False
    # Schema creation on startup is wasteful on serverless, where every cold
    # start would re-run it. Disable it there and create the schema once.
    auto_init_db: bool = True

    # Uploads / RAG
    max_upload_mb: int = 10
    chunk_size: int = 1000
    chunk_overlap: int = 150
    retrieval_top_k: int = 6

    # CORS — accepts a comma-separated string from the environment. NoDecode
    # stops pydantic-settings from trying to JSON-parse it first, so the
    # validator below sees the raw string.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("database_url", mode="after")
    @classmethod
    def _use_psycopg_driver(cls, value: str) -> str:
        """Pin the psycopg (v3) driver on the connection URL.

        Hosted providers hand out `postgres://` or `postgresql://`, which
        SQLAlchemy resolves to psycopg2 — a driver this project doesn't install.
        Rewriting the scheme means a provider's URL can be used verbatim.
        """
        for prefix in ("postgresql://", "postgres://"):
            if value.startswith(prefix):
                return f"postgresql+psycopg://{value[len(prefix):]}"
        return value

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def llm_configured(self) -> bool:
        return bool(self.gemini_api_key)


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so the environment is parsed exactly once."""
    return Settings()


settings = get_settings()
