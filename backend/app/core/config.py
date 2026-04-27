from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    secret_key: str = "changeme-insecure-key"
    debug: bool = True

    # SQLite default; swap to postgresql://... for production
    database_url: str = "sqlite:///./data/db.sqlite3"
    media_root: str = "./media"

    document_chunk_size: int = 1000
    document_chunk_overlap: int = 100

    embedding_provider: str = "none"
    embedding_model_name: str = "BAAI/bge-m3"

    vector_db_provider: str = "chroma"
    chroma_url: str = ""
    chroma_collection: str = "documents"

    llm_provider: str = "openai_compat"
    llm_base_url: str = "http://localhost:11434"
    llm_model: str = "exaone3.5:7.8b-instruct-q4_K_M"
    llm_api_key: str = ""
    llm_timeout_seconds: int = 30

    # Stored as comma-separated string to avoid pydantic-settings JSON-parsing list[str] from env
    cors_origins: str = "http://localhost:3000"

    def get_cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
