from fastapi import APIRouter

from evidencechain.models.health import HealthResponse
from evidencechain.providers.base import LLMHealthCheck
from evidencechain.providers.registry import get_llm_provider

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="evidencechain")


@router.get("/health/providers", response_model=list[LLMHealthCheck])
async def provider_health_check() -> list[LLMHealthCheck]:
    provider = get_llm_provider()
    failover_providers = getattr(provider, "providers", None)
    if failover_providers is not None:
        return [await item.health_check() for item in failover_providers]
    return [await provider.health_check()]
