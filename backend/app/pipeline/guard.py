import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel

from app.llm.base import LLMClient, LLMResult

PREVIEW_CHARS = 500


@dataclass
class StepCall:
    """What the trace needs about one model step, beyond its tokens."""

    attempts: int
    duration_ms: int
    input_preview: str
    output_preview: str
    error: str | None = None


class GuardedLLM:
    """Wraps any LLMClient: a timeout and retries with backoff on every call, and a record of
    each step's duration, attempts and short previews for the trace. Steps stay unaware of it."""

    def __init__(
        self,
        inner: LLMClient,
        *,
        timeout: float = 30.0,
        retries: int = 1,
        backoff: float = 0.5,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        retryable: Callable[[BaseException], bool] = lambda exc: True,
    ):
        self.inner = inner
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.sleep = sleep
        self.retryable = retryable
        self.calls: dict[str, StepCall] = {}

    async def complete(
        self,
        *,
        step: str,
        model: str,
        system: str,
        user: str,
        schema: type[BaseModel] | None = None,
    ) -> LLMResult:
        started = time.perf_counter()
        call = StepCall(attempts=0, duration_ms=0, input_preview=user[:PREVIEW_CHARS], output_preview="")
        self.calls[step] = call
        try:
            for attempt in range(self.retries + 1):
                call.attempts = attempt + 1
                try:
                    result = await asyncio.wait_for(
                        self.inner.complete(step=step, model=model, system=system, user=user, schema=schema),
                        timeout=self.timeout,
                    )
                except Exception as exc:  # noqa: BLE001 - retried, then re-raised for the step to handle
                    call.error = f"{type(exc).__name__}: {exc}"
                    if attempt == self.retries or not self.retryable(exc):
                        raise
                    await self.sleep(self.backoff * 2**attempt)
                    continue
                call.error = None
                call.output_preview = result.raw_text[:PREVIEW_CHARS]
                return result
        finally:
            call.duration_ms = round((time.perf_counter() - started) * 1000)
        raise AssertionError("unreachable")
