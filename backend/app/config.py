from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAG_", env_file=".env", extra="ignore")

    app_name: str = "RagStarter"
    env: str = "dev"

    database_url: str = "sqlite+aiosqlite:///./ragstarter.db"

    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_expires_min: int = 60
    cors_origins: list[str] = ["http://localhost:3000"]
    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: str = "change-me-now"

    embed_provider: str = "fake"  # fake | openai
    embed_api_base: str = "https://api.openai.com/v1"
    embed_api_key: str = ""
    embed_model: str = "text-embedding-3-small"
    embed_dim: int = 1536
    embed_batch: int = 64

    llm_provider: str = "fake"  # fake | openai
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    vector_backend: str = "memory"  # memory | milvus
    milvus_uri: str = "http://localhost:19530"
    milvus_collection: str = "chunks_v1"

    chunk_size_tokens: int = 512
    chunk_overlap_pct: int = 10
    upload_max_mb: int = 100
    upload_allowed_ext: list[str] = [".pdf", ".txt", ".md", ".zip"]
    zip_max_entries: int = 1000
    upload_dir: str = "./data/uploads"

    rate_chat_rpm: int = 30
    rate_upload_rpm: int = 60

    retrieval_top_k: int = 8
    rrf_k: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
