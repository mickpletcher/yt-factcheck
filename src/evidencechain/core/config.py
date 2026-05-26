from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "EvidenceChain"
    app_env: str = "development"
    app_debug: bool = False
    log_level: str = "INFO"
    database_url: str = "sqlite+aiosqlite:///./storage/evidencechain.db"
    transcript_chunk_max_chars: int = 1200
    transcript_chunk_overlap_segments: int = 1
    transcript_retry_attempts: int = 3
    transcript_retry_backoff_seconds: float = 0.5
    transcript_fetch_timeout_seconds: float = 20.0
    llm_provider: str = "openai"
    openai_model: str = "gpt-4.1-mini"
    anthropic_model: str = "claude-3-5-haiku-latest"
    ollama_model: str = "llama3.1"
    search_provider: str = "brave"
    brave_search_api_key: str = ""
    brave_search_endpoint: str = "https://api.search.brave.com/res/v1/web/search"
    tavily_api_key: str = ""
    bing_search_api_key: str = ""
    serpapi_api_key: str = ""
    evidence_search_timeout_seconds: float = 15.0
    evidence_search_retry_attempts: int = 3
    evidence_search_retry_backoff_seconds: float = 0.5
    evidence_search_rate_limit_per_second: float = 1.0
    evidence_search_cache_ttl_seconds: int = 3600
    evidence_search_max_queries: int = 4
    evidence_search_results_per_query: int = 5
    trusted_source_domains: list[str] = Field(
        default_factory=lambda: [
            "nih.gov",
            "cdc.gov",
            "who.int",
            "edu",
            "gov",
            "nature.com",
            "science.org",
            "reuters.com",
            "apnews.com",
            "bbc.com",
        ]
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.upper()

    @field_validator("trusted_source_domains", mode="before")
    @classmethod
    def split_domains(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def sqlite_path(self) -> Path:
        prefix = "sqlite+aiosqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError("Only sqlite+aiosqlite database URLs are supported initially.")
        return Path(self.database_url.removeprefix(prefix))


@lru_cache
def get_settings() -> Settings:
    return Settings()
