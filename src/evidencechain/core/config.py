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
    api_access_token: str = ""
    api_rate_limit_per_minute: int = 0
    transcript_chunk_max_chars: int = 1200
    transcript_chunk_overlap_segments: int = 1
    transcript_retry_attempts: int = 3
    transcript_retry_backoff_seconds: float = 0.5
    transcript_fetch_timeout_seconds: float = 20.0
    llm_provider: str = "openai"
    llm_failover_providers: list[str] = Field(default_factory=list)
    llm_request_timeout_seconds: float = 60.0
    llm_health_timeout_seconds: float = 10.0
    llm_cost_rates: dict[str, tuple[float, float]] = Field(default_factory=dict)
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    anthropic_model: str = "claude-3-5-haiku-latest"
    anthropic_version: str = "2023-06-01"
    anthropic_max_tokens: int = 4096
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    lmstudio_base_url: str = "http://localhost:1234/v1"
    lmstudio_model: str = "local-model"
    search_provider: str = "brave"
    search_failover_providers: list[str] = Field(default_factory=list)
    brave_search_api_key: str = ""
    brave_search_endpoint: str = "https://api.search.brave.com/res/v1/web/search"
    tavily_api_key: str = ""
    tavily_search_endpoint: str = "https://api.tavily.com/search"
    bing_search_api_key: str = ""
    bing_search_endpoint: str = "https://api.bing.microsoft.com/v7.0/search"
    serpapi_api_key: str = ""
    evidence_search_timeout_seconds: float = 15.0
    evidence_search_retry_attempts: int = 3
    evidence_search_retry_backoff_seconds: float = 0.5
    evidence_search_rate_limit_per_second: float = 1.0
    evidence_search_cache_ttl_seconds: int = 3600
    evidence_search_max_queries: int = 4
    evidence_search_results_per_query: int = 5
    pipeline_worker_count: int = 1
    pipeline_retry_attempts: int = 3
    pipeline_retry_backoff_seconds: float = 1.0
    report_export_dir: str = "reports"
    report_export_retention_days: int = 30
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

    @field_validator("llm_failover_providers", mode="before")
    @classmethod
    def split_failover_providers(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip().lower() for item in value.split(",") if item.strip()]
        return [item.lower() for item in value]

    @field_validator("search_failover_providers", mode="before")
    @classmethod
    def split_search_failover_providers(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip().lower() for item in value.split(",") if item.strip()]
        return [item.lower() for item in value]

    @field_validator("llm_cost_rates", mode="before")
    @classmethod
    def parse_cost_rates(
        cls,
        value: str | dict[str, tuple[float, float]],
    ) -> dict[str, tuple[float, float]]:
        if not isinstance(value, str):
            return value
        rates: dict[str, tuple[float, float]] = {}
        for item in value.split(","):
            if not item.strip():
                continue
            name, raw_rates = item.split("=", maxsplit=1)
            input_rate, output_rate = raw_rates.split(":", maxsplit=1)
            rates[name.strip().lower()] = (float(input_rate), float(output_rate))
        return rates

    def llm_cost_rate(self, provider: str, model: str) -> tuple[float, float]:
        normalized_provider = provider.lower()
        normalized_model = model.lower()
        return (
            self.llm_cost_rates.get(f"{normalized_provider}:{normalized_model}")
            or self.llm_cost_rates.get(normalized_provider)
            or (0.0, 0.0)
        )

    @property
    def sqlite_path(self) -> Path:
        prefix = "sqlite+aiosqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError("Only sqlite+aiosqlite database URLs are supported initially.")
        return Path(self.database_url.removeprefix(prefix))


@lru_cache
def get_settings() -> Settings:
    return Settings()
