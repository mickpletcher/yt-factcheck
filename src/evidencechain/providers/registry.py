from evidencechain.core.config import Settings, get_settings
from evidencechain.providers.base import LLMProvider
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
