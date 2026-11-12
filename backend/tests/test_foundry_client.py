"""FoundryClient against a stub of the anthropic SDK: no network, no key."""
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.llm.base import LLMClient
from app.llm.foundry import FoundryClient


class Sort(BaseModel):
    subsystem: str
    severity: str


def response(text="", parsed=None, input_tokens=120, output_tokens=18, model="claude-haiku-5-5", extra_blocks=()):
    blocks = [*extra_blocks, SimpleNamespace(type="text", text=text)]
    return SimpleNamespace(
        content=blocks,
        parsed_output=parsed,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        model=model,
    )


class StubMessages:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    async def _answer(self, kind, **kwargs):
        self.calls.append((kind, kwargs))
        if self.error:
            raise self.error
        return self.reply

    async def parse(self, **kwargs):
        return await self._answer("parse", **kwargs)

    async def create(self, **kwargs):
        return await self._answer("create", **kwargs)


def client(reply=None, error=None) -> tuple[FoundryClient, StubMessages]:
    messages = StubMessages(reply, error)
    return FoundryClient(SimpleNamespace(messages=messages)), messages


def ask(llm, schema=None, user="<note>\nValve fine.\n</note>"):
    return llm.complete(step="sort", model="mc-fast", system="Classify.", user=user, schema=schema)


async def test_maps_text_usage_and_model_into_an_llm_result():
    llm, _ = client(response(text="hello", input_tokens=321, output_tokens=12, model="claude-sonnet-5-5"))

    result = await ask(llm)

    assert (result.raw_text, result.input_tokens, result.output_tokens, result.model) == (
        "hello", 321, 12, "claude-sonnet-5-5",
    )
    assert result.parsed is None


async def test_ignores_non_text_blocks_such_as_thinking():
    thinking = SimpleNamespace(type="thinking", thinking="", signature="sig")
    llm, _ = client(response(text='{"subsystem": "weather", "severity": "low"}', extra_blocks=[thinking]))

    result = await ask(llm)

    assert result.raw_text == '{"subsystem": "weather", "severity": "low"}'


async def test_sends_the_deployment_system_prompt_and_user_message():
    llm, messages = client(response(text="ok"))

    await ask(llm, user="<note>\nLOX valve slow.\n</note>")

    kind, sent = messages.calls[0]
    assert kind == "create"
    assert sent["model"] == "mc-fast"
    assert sent["system"] == "Classify."
    assert sent["messages"] == [{"role": "user", "content": "<note>\nLOX valve slow.\n</note>"}]
    assert sent["max_tokens"] >= 1024


async def test_a_schema_uses_structured_output_and_returns_the_parsed_model():
    parsed = Sort(subsystem="propulsion", severity="medium")
    llm, messages = client(response(text=parsed.model_dump_json(), parsed=parsed))

    result = await ask(llm, schema=Sort)

    kind, sent = messages.calls[0]
    assert kind == "parse"
    assert sent["output_format"] is Sort
    assert result.parsed == parsed


async def test_a_reply_that_did_not_parse_leaves_parsed_empty_for_the_step_to_handle():
    llm, _ = client(response(text="I can't help with that.", parsed=None))

    result = await ask(llm, schema=Sort)

    assert result.parsed is None
    assert result.raw_text == "I can't help with that."


async def test_sdk_errors_propagate_so_the_pipeline_can_handle_them():
    llm, _ = client(error=RuntimeError("upstream down"))

    with pytest.raises(RuntimeError, match="upstream down"):
        await ask(llm)


def test_is_an_llm_client():
    assert isinstance(client()[0], LLMClient)


def _status_error(cls, status):
    import httpx

    request = httpx.Request("POST", "https://r.services.ai.azure.com/anthropic/v1/messages")
    return cls(f"HTTP {status}", response=httpx.Response(status, request=request), body=None)


def _transient():
    import anthropic
    import httpx

    request = httpx.Request("POST", "https://r.services.ai.azure.com/anthropic/v1/messages")
    return [
        TimeoutError("guard timeout"),
        anthropic.APITimeoutError(request=request),
        anthropic.APIConnectionError(request=request),
        _status_error(anthropic.RateLimitError, 429),
        _status_error(anthropic.InternalServerError, 503),
    ]


def _permanent():
    import anthropic

    return [
        _status_error(anthropic.AuthenticationError, 401),
        _status_error(anthropic.BadRequestError, 400),
        _status_error(anthropic.NotFoundError, 404),
        ValueError("bug"),
    ]


@pytest.mark.parametrize("exc", _transient(), ids=lambda e: type(e).__name__)
def test_timeouts_connection_rate_limit_and_5xx_are_retryable(exc):
    assert FoundryClient.is_retryable(exc) is True


@pytest.mark.parametrize("exc", _permanent(), ids=lambda e: type(e).__name__)
def test_auth_bad_request_and_bugs_are_not_retried(exc):
    assert FoundryClient.is_retryable(exc) is False


def test_from_settings_builds_a_foundry_sdk_client_without_its_own_retries(make_settings):
    import anthropic

    settings = make_settings(ANTHROPIC_FOUNDRY_API_KEY="test-key", ANTHROPIC_FOUNDRY_RESOURCE="mc-test")

    llm = FoundryClient.from_settings(settings)

    assert isinstance(llm.sdk, anthropic.AsyncAnthropicFoundry)
    assert llm.sdk.api_key == "test-key"
    assert "mc-test" in str(llm.sdk.base_url)
    assert llm.sdk.max_retries == 0  # GuardedLLM owns retries
