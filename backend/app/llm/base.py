from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pydantic import BaseModel


@dataclass(frozen=True)
class LLMResult:
    parsed: BaseModel | None
    raw_text: str
    input_tokens: int
    output_tokens: int
    model: str


@dataclass(frozen=True)
class LLMCall:
    step: str
    model: str
    system: str
    user: str
    schema: type[BaseModel] | None


@runtime_checkable
class LLMClient(Protocol):
    """The one seam every model call goes through. Tests use FakeLLM; the app uses Foundry."""

    async def complete(
        self,
        *,
        step: str,
        model: str,
        system: str,
        user: str,
        schema: type[BaseModel] | None = None,
    ) -> LLMResult: ...
