from evidencechain.core.config import Settings, get_settings
from evidencechain.models.factcheck import EvidenceProvider
from evidencechain.providers.base import LLMProvider, SearchProvider
from evidencechain.providers.search import BraveSearchProvider, UnconfiguredSearchProvider
from evidencechain.providers.stubs import AnthropicProvider, OllamaProvider, OpenAIProvider


def get_llm_provider(
    provider_name: str | None = None,
    settings: Settings | None = None,
) -> LLMProvider:
    resolved_settings = settings or get_settings()
    name = provider_name or resolved_settings.llm_provider

    providers: dict[str, LLMProvider] = {
        "openai": OpenAIProvider(settings=resolved_settings),
        "anthropic": AnthropicProvider(settings=resolved_settings),
        "ollama": OllamaProvider(settings=resolved_settings),
    }
    try:
        return providers[name.lower()]
    except KeyError as error:
        supported = ", ".join(sorted(providers))
        message = f"Unsupported LLM provider '{name}'. Supported providers: {supported}."
        raise ValueError(message) from error


def get_search_provider(
    provider_name: str | None = None,
    settings: Settings | None = None,
) -> SearchProvider:
    resolved_settings = settings or get_settings()
    name = (provider_name or resolved_settings.search_provider).lower()

    try:
        provider = EvidenceProvider(name)
    except ValueError as error:
        supported = ", ".join(sorted(item.value for item in EvidenceProvider))
        message = f"Unsupported search provider '{name}'. Supported providers: {supported}."
        raise ValueError(message) from error

    if provider == EvidenceProvider.brave:
        return BraveSearchProvider(settings=resolved_settings)
    return UnconfiguredSearchProvider(provider=provider, settings=resolved_settings)
