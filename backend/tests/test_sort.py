import json

import pytest
from pydantic import BaseModel

from app.llm.base import LLMResult
from app.llm.fake import FakeLLM
from app.pipeline.sort import Sort, sort_report

NOTE = "LOX valve slow to close on cycle 3."


def reply(raw: str, parsed=None, tokens=(120, 20)) -> LLMResult:
    return LLMResult(parsed=parsed, raw_text=raw, input_tokens=tokens[0], output_tokens=tokens[1], model="mc-fast")


async def run(script) -> tuple:
    llm = FakeLLM({"sort": script})
    outcome = await sort_report(llm, model="mc-fast", note=NOTE)
    return outcome, llm


async def test_valid_parsed_reply_is_used():
    outcome, _ = await run(reply("", parsed=Sort(subsystem="propulsion", severity="medium")))

    assert (outcome.subsystem, outcome.severity) == ("propulsion", "medium")
    assert outcome.status == "ok"


async def test_valid_json_text_is_parsed_in_code():
    outcome, _ = await run(reply(json.dumps({"subsystem": "telemetry", "severity": "low"})))

    assert (outcome.subsystem, outcome.severity) == ("telemetry", "low")
    assert outcome.status == "ok"


async def test_outcome_keeps_the_model_result_for_the_trace():
    outcome, _ = await run(reply('{"subsystem": "weather", "severity": "high"}', tokens=(321, 12)))

    assert (outcome.result.input_tokens, outcome.result.output_tokens) == (321, 12)


async def test_sort_runs_in_the_fast_role_with_the_schema():
    outcome, llm = await run(reply('{"subsystem": "weather", "severity": "high"}'))

    call = llm.calls[0]
    assert (call.step, call.model, call.schema) == ("sort", "mc-fast", Sort)
    assert outcome.role == "fast"


class OtherShape(BaseModel):
    category: str


@pytest.mark.parametrize(
    "bad_reply",
    [
        reply('{"subsystem": "plumbing", "severity": "high"}'),  # not a known subsystem
        reply('{"subsystem": "propulsion", "severity": "catastrophic"}'),  # not a known severity
        reply('{"subsystem": "propulsion"}'),  # missing field
        reply("Sure! It's a propulsion issue, medium severity."),  # not JSON
        reply("", parsed=OtherShape(category="propulsion")),  # parsed into the wrong shape
    ],
    ids=["unknown-subsystem", "unknown-severity", "missing-field", "not-json", "wrong-shape"],
)
async def test_invalid_reply_falls_back_to_unknown_high(bad_reply):
    outcome, _ = await run(bad_reply)

    assert (outcome.subsystem, outcome.severity) == ("unknown", "high")
    assert outcome.status == "fallback"
    assert outcome.error


async def test_invalid_reply_still_keeps_its_tokens_for_cost():
    outcome, _ = await run(reply("not json", tokens=(200, 9)))

    assert outcome.status == "fallback"
    assert (outcome.result.input_tokens, outcome.result.output_tokens) == (200, 9)


async def test_model_error_falls_back_with_no_result():
    outcome, _ = await run(TimeoutError("model timed out"))

    assert (outcome.subsystem, outcome.severity) == ("unknown", "high")
    assert outcome.status == "fallback"
    assert outcome.result is None
    assert "model timed out" in outcome.error


async def test_note_reaches_the_model_wrapped_as_untrusted_data():
    from app.pipeline.prompting import UNTRUSTED_NOTE_RULE, wrap_note

    _, llm = await run(reply('{"subsystem": "propulsion", "severity": "low"}'))

    call = llm.calls[0]
    assert call.user == wrap_note(NOTE)
    assert UNTRUSTED_NOTE_RULE in call.system


@pytest.mark.parametrize(
    ("note", "subsystem", "severity"),
    [
        ("LOX valve leak at the engine section.", "propulsion", "high"),
        ("Telemetry link dropped intermittently for 4 s.", "telemetry", "medium"),
        ("Guidance IMU drift is within tolerance.", "avionics", "low"),
        ("Lightning cell 12 nm from the pad.", "weather", "high"),
        ("Tower umbilical arm is slow to retract.", "ground_systems", "medium"),
        ("Coffee machine on level 2 is out.", "other", "low"),
        ("Engine failure on pad.", "propulsion", "high"),
        ("Fuel line leaking near the turbopump.", "propulsion", "high"),
        ("Two small fires reported by the GSE crew.", "ground_systems", "high"),
        ("Pad crane test aborted after alarm.", "ground_systems", "high"),
        ("Downlink delays seen on the backup antenna.", "telemetry", "medium"),
    ],
)
async def test_demo_mode_sorts_by_keywords(note, subsystem, severity):
    outcome = await sort_report(FakeLLM.demo(), model="mc-fast", note=note)

    assert outcome.status == "ok"
    assert (outcome.subsystem, outcome.severity) == (subsystem, severity)
