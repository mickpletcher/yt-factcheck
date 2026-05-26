from pydantic import BaseModel

from evidencechain.core.config import Settings
from evidencechain.providers.base import (
    LLMProviderError,
    LLMProviderHealthStatus,
    LLMRequest,
    LLMUsage,
)
from evidencechain.providers.llm import BaseLLMProvider, FailoverLLMProvider
from evidencechain.providers.registry import get_llm_provider, register_llm_provider


class OutputSchema(BaseModel):
    value: str


class BrokenProvider(BaseLLMProvider):
    name = "broken"

    @property
    def model(self) -> str:
        return "broken-model"

    async def _generate_json(
        self,
        request: LLMRequest,
        output_schema: type[BaseModel],
    ) -> tuple[dict[str, object], LLMUsage]:
        raise LLMProviderError("failed")


class WorkingProvider(BaseLLMProvider):
    name = "working"

    @property
    def model(self) -> str:
        return "working-model"

    async def _generate_json(
        self,
        request: LLMRequest,
        output_schema: type[BaseModel],
    ) -> tuple[dict[str, object], LLMUsage]:
        return {"value": request.user_prompt}, self._usage_from_counts(10, 5)


async def test_registry_supports_custom_future_providers() -> None:
    register_llm_provider("working", WorkingProvider)
    provider = get_llm_provider("working", Settings())

    result = await provider.generate_structured(
        LLMRequest(system_prompt="system", user_prompt="ok"),
        OutputSchema,
    )

    assert result.value == "ok"
    assert provider.usage[0].total_tokens == 15


async def test_failover_tries_next_provider_after_error() -> None:
    provider = FailoverLLMProvider([BrokenProvider(Settings()), WorkingProvider(Settings())])

    result = await provider.generate_structured(
        LLMRequest(system_prompt="system", user_prompt="next"),
        OutputSchema,
    )

    assert result.value == "next"
    assert provider.name == "working"
    assert provider.usage[0].provider == "working"


def test_usage_tracks_cost_from_settings() -> None:
    settings = Settings(llm_cost_rates={"working": (1.0, 2.0)})
    provider = WorkingProvider(settings)

    usage = provider._usage_from_counts(1_000_000, 500_000)

    assert usage.cost_usd == 2.0


async def test_unconfigured_openai_health_check_is_reported_without_network_call() -> None:
    provider = get_llm_provider("openai", Settings(openai_api_key=""))

    health = await provider.health_check()

    assert health.status == LLMProviderHealthStatus.unconfigured
