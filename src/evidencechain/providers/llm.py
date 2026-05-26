import json
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from evidencechain.core.config import Settings
from evidencechain.providers.base import (
    LLMHealthCheck,
    LLMProviderConfigurationError,
    LLMProviderError,
    LLMProviderHealthStatus,
    LLMRequest,
    LLMUsage,
    SchemaT,
)

ProviderFactory = Callable[[Settings], "BaseLLMProvider"]


class BaseLLMProvider:
    name = "base"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.usage: list[LLMUsage] = []

    @property
    def model(self) -> str:
        raise NotImplementedError

    async def generate_structured(
        self,
        request: LLMRequest,
        output_schema: type[SchemaT],
    ) -> SchemaT:
        payload, usage = await self._generate_json(request, output_schema)
        self._track_usage(usage)
        try:
            return output_schema.model_validate(payload)
        except ValidationError as error:
            message = f"{self.name} returned invalid structured output: {error}"
            raise LLMProviderError(message) from error

    async def health_check(self) -> LLMHealthCheck:
        try:
            self._validate_configuration()
        except LLMProviderConfigurationError as error:
            return LLMHealthCheck(
                provider=self.name,
                status=LLMProviderHealthStatus.unconfigured,
                message=str(error),
            )

        try:
            timeout = self.settings.llm_health_timeout_seconds
            async with httpx.AsyncClient(timeout=timeout) as client:
                await self._health_request(client)
        except (httpx.HTTPError, LLMProviderError) as error:
            return LLMHealthCheck(
                provider=self.name,
                status=LLMProviderHealthStatus.unhealthy,
                message=str(error),
            )

        return LLMHealthCheck(provider=self.name, status=LLMProviderHealthStatus.healthy)

    async def _generate_json(
        self,
        request: LLMRequest,
        output_schema: type[BaseModel],
    ) -> tuple[dict[str, Any], LLMUsage]:
        raise NotImplementedError

    async def _health_request(self, client: httpx.AsyncClient) -> None:
        raise NotImplementedError

    def _validate_configuration(self) -> None:
        return None

    def _track_usage(self, usage: LLMUsage) -> None:
        self.usage.append(usage)

    def _usage_from_counts(self, prompt_tokens: int, completion_tokens: int) -> LLMUsage:
        total_tokens = prompt_tokens + completion_tokens
        input_rate, output_rate = self.settings.llm_cost_rate(self.name, self.model)
        cost = (prompt_tokens / 1_000_000 * input_rate) + (
            completion_tokens / 1_000_000 * output_rate
        )
        return LLMUsage(
            provider=self.name,
            model=self.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=round(cost, 8),
        )

    def _usage_from_mapping(self, usage: dict[str, Any]) -> LLMUsage:
        prompt_tokens = int(
            usage.get("prompt_tokens")
            or usage.get("input_tokens")
            or usage.get("prompt_eval_count")
            or 0
        )
        completion_tokens = int(
            usage.get("completion_tokens")
            or usage.get("output_tokens")
            or usage.get("eval_count")
            or 0
        )
        total_tokens = int(usage.get("total_tokens") or prompt_tokens + completion_tokens)
        tracked = self._usage_from_counts(prompt_tokens, completion_tokens)
        tracked.total_tokens = total_tokens
        return tracked

    def _parse_json_content(self, content: str) -> dict[str, Any]:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as error:
            message = f"{self.name} returned non-JSON structured output."
            raise LLMProviderError(message) from error
        if not isinstance(payload, dict):
            raise LLMProviderError(f"{self.name} returned a JSON value instead of an object.")
        return payload


class OpenAIProvider(BaseLLMProvider):
    name = "openai"

    @property
    def model(self) -> str:
        return self.settings.openai_model

    def _validate_configuration(self) -> None:
        if not self.settings.openai_api_key:
            raise LLMProviderConfigurationError("OPENAI_API_KEY is not configured.")

    async def _generate_json(
        self,
        request: LLMRequest,
        output_schema: type[BaseModel],
    ) -> tuple[dict[str, Any], LLMUsage]:
        self._validate_configuration()
        payload = {
            "model": self.model,
            "messages": _messages(request),
            "temperature": request.temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": output_schema.__name__,
                    "schema": output_schema.model_json_schema(),
                    "strict": False,
                },
            },
        }
        data = await self._post_chat_completion(self.settings.openai_base_url, payload)
        choice = data["choices"][0]["message"]["content"]
        return self._parse_json_content(choice), self._usage_from_mapping(data.get("usage", {}))

    async def _health_request(self, client: httpx.AsyncClient) -> None:
        response = await client.get(
            f"{self.settings.openai_base_url.rstrip('/')}/models/{self.model}",
            headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
        )
        response.raise_for_status()

    async def _post_chat_completion(
        self,
        base_url: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.settings.llm_request_timeout_seconds) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
                json=payload,
            )
        return _validated_response(response, self.name)


class AnthropicProvider(BaseLLMProvider):
    name = "anthropic"

    @property
    def model(self) -> str:
        return self.settings.anthropic_model

    def _validate_configuration(self) -> None:
        if not self.settings.anthropic_api_key:
            raise LLMProviderConfigurationError("ANTHROPIC_API_KEY is not configured.")

    async def _generate_json(
        self,
        request: LLMRequest,
        output_schema: type[BaseModel],
    ) -> tuple[dict[str, Any], LLMUsage]:
        self._validate_configuration()
        payload = {
            "model": self.model,
            "max_tokens": self.settings.anthropic_max_tokens,
            "temperature": request.temperature,
            "system": _json_system_prompt(request.system_prompt, output_schema),
            "messages": [{"role": "user", "content": request.user_prompt}],
        }
        async with httpx.AsyncClient(timeout=self.settings.llm_request_timeout_seconds) as client:
            response = await client.post(
                f"{self.settings.anthropic_base_url.rstrip('/')}/messages",
                headers={
                    "x-api-key": self.settings.anthropic_api_key,
                    "anthropic-version": self.settings.anthropic_version,
                },
                json=payload,
            )
        data = _validated_response(response, self.name)
        content = _anthropic_text(data)
        return self._parse_json_content(content), self._usage_from_mapping(data.get("usage", {}))

    async def _health_request(self, client: httpx.AsyncClient) -> None:
        response = await client.post(
            f"{self.settings.anthropic_base_url.rstrip('/')}/messages",
            headers={
                "x-api-key": self.settings.anthropic_api_key,
                "anthropic-version": self.settings.anthropic_version,
            },
            json={
                "model": self.model,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ok"}],
            },
        )
        response.raise_for_status()


class OllamaProvider(BaseLLMProvider):
    name = "ollama"

    @property
    def model(self) -> str:
        return self.settings.ollama_model

    async def _generate_json(
        self,
        request: LLMRequest,
        output_schema: type[BaseModel],
    ) -> tuple[dict[str, Any], LLMUsage]:
        payload = {
            "model": self.model,
            "messages": _messages_with_schema(request, output_schema),
            "format": "json",
            "stream": False,
            "options": {"temperature": request.temperature},
        }
        async with httpx.AsyncClient(timeout=self.settings.llm_request_timeout_seconds) as client:
            response = await client.post(
                f"{self.settings.ollama_base_url.rstrip('/')}/api/chat",
                json=payload,
            )
        data = _validated_response(response, self.name)
        content = data["message"]["content"]
        return self._parse_json_content(content), self._usage_from_mapping(data)

    async def _health_request(self, client: httpx.AsyncClient) -> None:
        response = await client.get(f"{self.settings.ollama_base_url.rstrip('/')}/api/tags")
        response.raise_for_status()


class LMStudioProvider(BaseLLMProvider):
    name = "lmstudio"

    @property
    def model(self) -> str:
        return self.settings.lmstudio_model

    async def _generate_json(
        self,
        request: LLMRequest,
        output_schema: type[BaseModel],
    ) -> tuple[dict[str, Any], LLMUsage]:
        payload = {
            "model": self.model,
            "messages": _messages_with_schema(request, output_schema),
            "temperature": request.temperature,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=self.settings.llm_request_timeout_seconds) as client:
            response = await client.post(
                f"{self.settings.lmstudio_base_url.rstrip('/')}/chat/completions",
                json=payload,
            )
        data = _validated_response(response, self.name)
        choice = data["choices"][0]["message"]["content"]
        return self._parse_json_content(choice), self._usage_from_mapping(data.get("usage", {}))

    async def _health_request(self, client: httpx.AsyncClient) -> None:
        response = await client.get(f"{self.settings.lmstudio_base_url.rstrip('/')}/models")
        response.raise_for_status()


class FailoverLLMProvider:
    def __init__(self, providers: list[BaseLLMProvider]) -> None:
        if not providers:
            raise ValueError("At least one provider is required for failover.")
        self.providers = providers
        self._last_provider_name: str | None = None
        self.usage: list[LLMUsage] = []

    @property
    def name(self) -> str:
        return self._last_provider_name or self.providers[0].name

    async def generate_structured(
        self,
        request: LLMRequest,
        output_schema: type[SchemaT],
    ) -> SchemaT:
        errors: list[str] = []
        for provider in self.providers:
            usage_start = len(provider.usage)
            try:
                result = await provider.generate_structured(request, output_schema)
            except LLMProviderError as error:
                errors.append(f"{provider.name}: {error}")
                continue
            self.usage.extend(provider.usage[usage_start:])
            self._last_provider_name = provider.name
            return result
        raise LLMProviderError("All LLM providers failed. " + " | ".join(errors))

    async def health_check(self) -> LLMHealthCheck:
        checks = [await provider.health_check() for provider in self.providers]
        if any(check.status == LLMProviderHealthStatus.healthy for check in checks):
            return LLMHealthCheck(provider=self.name, status=LLMProviderHealthStatus.healthy)
        messages = "; ".join(f"{check.provider}: {check.message}" for check in checks)
        return LLMHealthCheck(
            provider=self.name,
            status=LLMProviderHealthStatus.unhealthy,
            message=messages,
        )


def _messages(request: LLMRequest) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": request.system_prompt},
        {"role": "user", "content": request.user_prompt},
    ]


def _messages_with_schema(
    request: LLMRequest,
    output_schema: type[BaseModel],
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": _json_system_prompt(request.system_prompt, output_schema),
        },
        {"role": "user", "content": request.user_prompt},
    ]


def _json_system_prompt(system_prompt: str, output_schema: type[BaseModel]) -> str:
    schema = json.dumps(output_schema.model_json_schema(), separators=(",", ":"))
    return (
        f"{system_prompt}\n\n"
        "Return only a JSON object that validates against this JSON schema:\n"
        f"{schema}"
    )


def _anthropic_text(data: dict[str, Any]) -> str:
    content = data.get("content", [])
    text_parts = [item.get("text", "") for item in content if item.get("type") == "text"]
    return "".join(text_parts)


def _validated_response(response: httpx.Response, provider_name: str) -> dict[str, Any]:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        raise LLMProviderError(f"{provider_name} request failed: {response.text}") from error
    data = response.json()
    if not isinstance(data, dict):
        raise LLMProviderError(f"{provider_name} returned an unexpected response.")
    return data
