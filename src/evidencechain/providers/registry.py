from evidencechain.core.config import Settings, get_settings
from evidencechain.models.factcheck import EvidenceProvider
from evidencechain.providers.base import LLMProvider, SearchProvider
from evidencechain.providers.llm import (
    AnthropicProvider,
    BaseLLMProvider,
    FailoverLLMProvider,
    LMStudioProvider,
    OllamaProvider,
    OpenAIProvider,
    ProviderFactory,
)
from evidencechain.providers.search import (
    BingSearchProvider,
    BraveSearchProvider,
    FailoverSearchProvider,
    TavilySearchProvider,
    UnconfiguredSearchProvider,
)

_LLM_PROVIDER_FACTORIES: dict[str, ProviderFactory] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
    "lmstudio": LMStudioProvider,
    "lm-studio": LMStudioProvider,
}


def register_llm_provider(name: str, factory: ProviderFactory) -> None:
    _LLM_PROVIDER_FACTORIES[name.lower()] = factory


def get_llm_provider(
    provider_name: str | None = None,
    settings: Settings | None = None,
) -> LLMProvider:
    resolved_settings = settings or get_settings()
    names = _provider_names(provider_name, resolved_settings)
    providers = [_build_llm_provider(name, resolved_settings) for name in names]
    if len(providers) == 1:
        return providers[0]
    return FailoverLLMProvider(providers)


def _provider_names(provider_name: str | None, settings: Settings) -> list[str]:
    if provider_name:
        return [item.strip().lower() for item in provider_name.split(",") if item.strip()]
    names = [settings.llm_provider.lower()]
    names.extend(name for name in settings.llm_failover_providers if name not in names)
    return names


def _build_llm_provider(name: str, settings: Settings) -> BaseLLMProvider:
    try:
        return _LLM_PROVIDER_FACTORIES[name](settings)
    except KeyError as error:
        supported = ", ".join(sorted(_LLM_PROVIDER_FACTORIES))
        message = f"Unsupported LLM provider '{name}'. Supported providers: {supported}."
        raise ValueError(message) from error


def get_search_provider(
    provider_name: str | None = None,
    settings: Settings | None = None,
) -> SearchProvider:
    resolved_settings = settings or get_settings()
    names = _search_provider_names(provider_name, resolved_settings)
    providers = [_build_search_provider(name, resolved_settings) for name in names]
    if len(providers) == 1:
        return providers[0]
    return FailoverSearchProvider(providers)


def _search_provider_names(provider_name: str | None, settings: Settings) -> list[str]:
    if provider_name:
        return [item.strip().lower() for item in provider_name.split(",") if item.strip()]
    names = [settings.search_provider.lower()]
    names.extend(name for name in settings.search_failover_providers if name not in names)
    return names


def _build_search_provider(name: str, settings: Settings) -> SearchProvider:
    try:
        provider = EvidenceProvider(name)
    except ValueError as error:
        supported = ", ".join(sorted(item.value for item in EvidenceProvider))
        message = f"Unsupported search provider '{name}'. Supported providers: {supported}."
        raise ValueError(message) from error

    if provider == EvidenceProvider.brave:
        return BraveSearchProvider(settings=settings)
    if provider == EvidenceProvider.tavily:
        return TavilySearchProvider(settings=settings)
    if provider == EvidenceProvider.bing:
        return BingSearchProvider(settings=settings)
    return UnconfiguredSearchProvider(provider=provider, settings=settings)
