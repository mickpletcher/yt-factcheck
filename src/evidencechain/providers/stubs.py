from evidencechain.core.config import Settings
from evidencechain.providers.base import LLMProviderError, LLMRequest, SchemaT


class OpenAIProvider:
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate_structured(
        self,
        request: LLMRequest,
        output_schema: type[SchemaT],
    ) -> SchemaT:
        raise LLMProviderError("OpenAI provider transport is not implemented until prompt 08.")


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate_structured(
        self,
        request: LLMRequest,
        output_schema: type[SchemaT],
    ) -> SchemaT:
        raise LLMProviderError("Anthropic provider transport is not implemented until prompt 08.")


class OllamaProvider:
    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate_structured(
        self,
        request: LLMRequest,
        output_schema: type[SchemaT],
    ) -> SchemaT:
        raise LLMProviderError("Ollama provider transport is not implemented until prompt 08.")
