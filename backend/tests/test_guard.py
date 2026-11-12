import asyncio

import pytest

from app.llm.base import LLMClient, LLMResult
from app.llm.fake import FakeLLM
from app.pipeline.guard import PREVIEW_CHARS, GuardedLLM

OK = LLMResult(None, '{"ok": true}', 10, 2, "m")


def ask(llm, step="sort", user="hello"):
    return llm.complete(step=step, model="m", system="s", user=user, schema=None)


def failing_then(results):
    """A FakeLLM script entry that raises or returns each item in turn."""
    items = iter(results)

    def answer(call):
        item = next(items)
        if isinstance(item, BaseException):
            raise item
        return item

    return answer


class Sleeps:
    def __init__(self):
        self.waits = []

    async def __call__(self, seconds):
        self.waits.append(seconds)


async def test_passes_the_result_through_and_records_the_call():
    guard = GuardedLLM(FakeLLM({"sort": OK}), timeout=1, retries=1, backoff=0)

    result = await ask(guard)

    assert result is OK
    call = guard.calls["sort"]
    assert (call.attempts, call.error) == (1, None)
    assert call.duration_ms >= 0
    assert call.input_preview == "hello"
    assert call.output_preview == '{"ok": true}'


async def test_retries_once_after_a_failure():
    sleeps = Sleeps()
    inner = FakeLLM({"sort": failing_then([TimeoutError("slow"), OK])})
    guard = GuardedLLM(inner, timeout=1, retries=1, backoff=0.5, sleep=sleeps)

    result = await ask(guard)

    assert result is OK
    assert guard.calls["sort"].attempts == 2
    assert sleeps.waits == [0.5]


async def test_gives_up_after_the_retry_and_raises_the_last_error():
    inner = FakeLLM({"sort": failing_then([TimeoutError("slow"), RuntimeError("down")])})
    guard = GuardedLLM(inner, timeout=1, retries=1, backoff=0, sleep=Sleeps())

    with pytest.raises(RuntimeError, match="down"):
        await ask(guard)

    call = guard.calls["sort"]
    assert call.attempts == 2
    assert "down" in call.error


async def test_a_call_that_hangs_times_out():
    class Hangs:
        async def complete(self, **kwargs):
            await asyncio.sleep(10)

    guard = GuardedLLM(Hangs(), timeout=0.05, retries=1, backoff=0, sleep=Sleeps())

    with pytest.raises(TimeoutError):
        await ask(guard)
    assert guard.calls["sort"].attempts == 2


async def test_previews_are_truncated():
    big = LLMResult(None, "y" * 5000, 1, 1, "m")
    guard = GuardedLLM(FakeLLM({"sort": big}), timeout=1, retries=1, backoff=0)

    await ask(guard, user="x" * 5000)

    call = guard.calls["sort"]
    assert len(call.input_preview) == len(call.output_preview) == PREVIEW_CHARS


async def test_each_step_is_recorded_separately():
    guard = GuardedLLM(FakeLLM({"draft_1": OK, "review_1": OK}), timeout=1, retries=1, backoff=0)

    await ask(guard, step="draft_1")
    await ask(guard, step="review_1")

    assert set(guard.calls) == {"draft_1", "review_1"}


def test_guard_is_an_llm_client():
    assert isinstance(GuardedLLM(FakeLLM({})), LLMClient)
