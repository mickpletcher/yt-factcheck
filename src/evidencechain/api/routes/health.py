from fastapi import APIRouter, Request

from evidencechain.models.health import (
    HealthResponse,
    ProviderCapability,
    ProviderReadinessResponse,
)
from evidencechain.providers.base import LLMHealthCheck, SearchProviderError
from evidencechain.providers.registry import get_llm_provider, get_search_provider

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="evidencechain")


@router.get("/health/providers", response_model=list[LLMHealthCheck])
async def provider_health_check(request: Request) -> list[LLMHealthCheck]:
    provider = get_llm_provider(settings=request.app.state.settings)
    failover_providers = getattr(provider, "providers", None)
    if failover_providers is not None:
        return [await item.health_check() for item in failover_providers]
    return [await provider.health_check()]


@router.get("/health/readiness", response_model=ProviderReadinessResponse)
async def provider_readiness_check(request: Request) -> ProviderReadinessResponse:
    settings = request.app.state.settings
    capabilities: list[ProviderCapability] = []
    llm = get_llm_provider(settings=settings)
    llm_providers = getattr(llm, "providers", [llm])
    for provider in llm_providers:
        check = await provider.health_check()
        capabilities.append(
            ProviderCapability(
                provider_type="llm",
                provider=check.provider,
                configured=check.status != "unconfigured",
                healthy=check.status == "healthy",
                message=check.message,
            )
        )

    search_names = [settings.search_provider, *settings.search_failover_providers]
    seen: set[str] = set()
    for name in search_names:
        normalized = name.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        try:
            provider = get_search_provider(normalized, settings)
            capabilities.append(
                ProviderCapability(
                    provider_type="search",
                    provider=provider.name,
                    configured=True,
                    healthy=True,
                )
            )
        except SearchProviderError as error:
            capabilities.append(
                ProviderCapability(
                    provider_type="search",
                    provider=normalized,
                    configured=False,
                    healthy=False,
                    message=str(error),
                )
            )
        except ValueError as error:
            capabilities.append(
                ProviderCapability(
                    provider_type="search",
                    provider=normalized,
                    configured=False,
                    healthy=False,
                    message=str(error),
                )
            )
    return ProviderReadinessResponse(
        ready=any(item.healthy for item in capabilities if item.provider_type == "llm")
        and any(item.healthy for item in capabilities if item.provider_type == "search"),
        providers=capabilities,
    )
