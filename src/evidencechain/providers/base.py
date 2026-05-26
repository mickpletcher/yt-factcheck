from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, TypeVar

from pydantic import BaseModel, Field

from evidencechain.models.factcheck import SearchResult

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMProviderError(Exception):
    pass


class LLMProviderConfigurationError(LLMProviderError):
    pass


class LLMProviderHealthStatus(StrEnum):
    healthy = "healthy"
    unhealthy = "unhealthy"
    unconfigured = "unconfigured"


class LLMRequest(BaseModel):
    system_prompt: str
    user_prompt: str
    temperature: float = 0.0


class LLMUsage(BaseModel):
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LLMHealthCheck(BaseModel):
    provider: str
    status: LLMProviderHealthStatus
    message: str = ""
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LLMProvider(Protocol):
    usage: list[LLMUsage]

    @property
    def name(self) -> str: ...

    async def generate_structured(
        self,
        request: LLMRequest,
        output_schema: type[SchemaT],
    ) -> SchemaT: ...

    async def health_check(self) -> LLMHealthCheck: ...


class SearchProviderError(Exception):
    pass


class SearchProviderConfigurationError(SearchProviderError):
    pass


class SearchProvider(Protocol):
    name: str

    async def search(self, query: str, count: int) -> list[SearchResult]: ...
