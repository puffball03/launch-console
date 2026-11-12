import anthropic
from pydantic import BaseModel

from app.config import Settings
from app.llm.base import LLMResult

# Errors worth one more try: timeouts, dropped connections, rate limits and 5xx.
# Auth, bad-request and not-found errors fail the same way every time.
TRANSIENT = (
    TimeoutError,
    anthropic.APITimeoutError,
    anthropic.APIConnectionError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
)

# Non-streaming default from the SDK guidance; leaves room for adaptive thinking.
MAX_TOKENS = 16000


class FoundryClient:
    """The real LLMClient: Claude on Microsoft Foundry through the anthropic SDK.

    `sdk` is an `anthropic.AsyncAnthropicFoundry` (see `from_settings`), or a stub in tests.
    With a schema it uses structured outputs (`messages.parse`) and returns the parsed model;
    the pipeline steps still validate it in code. Errors propagate for the guard to retry.
    """

    @staticmethod
    def is_retryable(exc: BaseException) -> bool:
        return isinstance(exc, TRANSIENT)

    @classmethod
    def from_settings(cls, settings: Settings) -> "FoundryClient":
        # The SDK's own retries are off: GuardedLLM retries transient errors once, with backoff.
        sdk = anthropic.AsyncAnthropicFoundry(
            api_key=settings.foundry_api_key,
            resource=settings.foundry_resource,
            max_retries=0,
        )
        return cls(sdk)

    def __init__(self, sdk, *, max_tokens: int = MAX_TOKENS):
        self.sdk = sdk
        self.max_tokens = max_tokens

    async def complete(
        self,
        *,
        step: str,
        model: str,
        system: str,
        user: str,
        schema: type[BaseModel] | None = None,
    ) -> LLMResult:
        request = {
            "model": model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if schema is not None:
            response = await self.sdk.messages.parse(**request, output_format=schema)
            parsed = response.parsed_output
        else:
            response = await self.sdk.messages.create(**request)
            parsed = None
        text = "".join(block.text for block in response.content if block.type == "text")
        return LLMResult(
            parsed=parsed,
            raw_text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=response.model,
        )
