from typing import Protocol, TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMProviderError(Exception):
    pass


class LLMRequest(BaseModel):
    system_prompt: str
    user_prompt: str
    temperature: float = 0.0


class LLMProvider(Protocol):
    name: str

    async def generate_structured(
        self,
        request: LLMRequest,
        output_schema: type[SchemaT],
    ) -> SchemaT: ...
