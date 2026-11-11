import json
import re
from collections.abc import Callable, Mapping

from pydantic import BaseModel

from app.llm.base import LLMCall, LLMResult

Scripted = LLMResult | BaseException | Callable[[LLMCall], LLMResult]


class UnscriptedStepError(LookupError):
    pass


class FakeLLM:
    """Scripted stand-in for the model: each step name maps to a result, an exception, or a callable.

    In demo mode, steps without a script are answered by simple keyword rules so the
    app is usable with no API key. Each pipeline ticket adds the rule for its own step.
    """

    def __init__(self, script: Mapping[str, Scripted], *, demo: bool = False):
        self.script = dict(script)
        self.demo_mode = demo
        self.calls: list[LLMCall] = []

    @classmethod
    def demo(cls, script: Mapping[str, Scripted] | None = None) -> "FakeLLM":
        return cls(script or {}, demo=True)

    async def complete(
        self,
        *,
        step: str,
        model: str,
        system: str,
        user: str,
        schema: type[BaseModel] | None = None,
    ) -> LLMResult:
        call = LLMCall(step=step, model=model, system=system, user=user, schema=schema)
        self.calls.append(call)

        if step in self.script:
            scripted = self.script[step]
            if isinstance(scripted, BaseException):
                raise scripted
            if callable(scripted):
                return scripted(call)
            return scripted

        if self.demo_mode and step in DEMO_RULES:
            return _demo_result(call, DEMO_RULES[step](call.user))

        raise UnscriptedStepError(f"FakeLLM has no script for step {step!r}")


INJECTION_HINTS = re.compile(
    r"ignore (all |any )?(previous|prior|above) instructions|you are now|system:|set (the )?verdict",
    re.IGNORECASE,
)


def _demo_check_injection(note: str) -> dict:
    if INJECTION_HINTS.search(note):
        return {"flagged": True, "reason": "Note contains text addressed to the system."}
    return {"flagged": False, "reason": "No instructions found in the note."}


# First match wins, so weather is checked before the pad and tower words of ground systems.
DEMO_SUBSYSTEMS = [
    ("propulsion", r"lox|fuel|valve|engine|turbopump|propellant|thrust"),
    ("telemetry", r"telemetry|link|signal|downlink|antenna"),
    ("avionics", r"guidance|imu|avionics|flight computer|gnc"),
    ("weather", r"wind|weather|lightning|gust|cloud|rain"),
    ("ground_systems", r"pad|tower|umbilical|ground|crane|gse"),
]
DEMO_HIGH = r"leak|fire|fail|failed|abort|lightning|explosion|overpressure"
DEMO_MEDIUM = r"slow|intermittent|intermittently|dropped|delay|delayed|degraded"


def _demo_sort(note: str) -> dict:
    def has(pattern: str) -> bool:
        return re.search(rf"\b(?:{pattern})\b", note, re.IGNORECASE) is not None

    subsystem = next((name for name, words in DEMO_SUBSYSTEMS if has(words)), "other")
    severity = "high" if has(DEMO_HIGH) else "medium" if has(DEMO_MEDIUM) else "low"
    return {"subsystem": subsystem, "severity": severity}


DEMO_RULES: dict[str, Callable[[str], dict]] = {
    "sort": _demo_sort,
    "check_injection": _demo_check_injection,
}


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _demo_result(call: LLMCall, reply: dict) -> LLMResult:
    raw = json.dumps(reply)
    return LLMResult(
        parsed=call.schema.model_validate(reply) if call.schema else None,
        raw_text=raw,
        input_tokens=_estimate_tokens(call.system + call.user),
        output_tokens=_estimate_tokens(raw),
        model=call.model,
    )
