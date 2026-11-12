import html
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

        # Only the numbered loop steps (draft_2, review_3) fall back to their base rule.
        numbered = re.fullmatch(r"(draft|review)_\d+", step)
        rule = DEMO_RULES.get(step) or (DEMO_RULES.get(numbered.group(1)) if numbered else None)
        if self.demo_mode and rule is not None:
            return _demo_result(call, rule(call.user))

        raise UnscriptedStepError(f"FakeLLM has no script for step {step!r}")


# Deliberately separate from app/rules/injection.py: this stands in for the *model's*
# injection check, which the code pre-screen backs up independently.
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
DEMO_HIGH = r"leak|fire|fail|abort|lightning|explo|overpressure"
DEMO_MEDIUM = r"slow|intermittent|drop|delay|degrad"


def _demo_sort(note: str) -> dict:
    def has(pattern: str) -> bool:
        # Keywords match the start of a word, so "leak" also catches leaks, leaking and leaked.
        return re.search(rf"\b(?:{pattern})\w*", note, re.IGNORECASE) is not None

    subsystem = next((name for name, words in DEMO_SUBSYSTEMS if has(words)), "other")
    severity = "high" if has(DEMO_HIGH) else "medium" if has(DEMO_MEDIUM) else "low"
    return {"subsystem": subsystem, "severity": severity}


def _demo_check_missing(note: str) -> dict:
    words = re.findall(r"[A-Za-z0-9-]+", note)
    if len(words) < 8 or not re.search(r"\d", note):
        return {"flagged": True, "reason": "Add the component, a reading or time, and how far from normal."}
    return {"flagged": False, "reason": "The note gives a component, a time and a reading."}


def _demo_check_panic(note: str) -> dict:
    shouting = len(re.findall(r"\b[A-Z]{4,}\b", note)) >= 2
    if shouting or "!!" in note or re.search(r"\b(?:panic|disaster|catastroph)\w*", note, re.IGNORECASE):
        return {"flagged": True, "reason": "The tone is alarmist; lead with the facts."}
    return {"flagged": False, "reason": "The tone is factual."}


def _demo_draft(prompt: str) -> dict:
    match = re.search(r"<note>\n(.*)\n</note>", prompt, re.DOTALL)
    note = html.unescape(match.group(1)) if match else ""
    # Read the verdict from the code-written facts block only; the note could contain the phrase.
    facts = re.search(r"<facts>\n(.*?)\n</facts>", prompt, re.DOTALL)
    verdict = "NO-GO" if facts and "verdict: no_go" in facts.group(1) else "GO"
    first_sentence = re.split(r"(?<=[.!?])\s", note.strip(), maxsplit=1)[0]
    return {
        "headline": f"{verdict}: {first_sentence}"[:80],
        "situation": note.strip()[:300] or "No details given.",
        "impact_on_launch": "Launch limits are violated." if verdict == "NO-GO" else "No launch limit is violated.",
        "recommended_action": "Hold and reassess." if verdict == "NO-GO" else "Continue and monitor.",
        "open_questions": [],
    }


def _demo_review(prompt: str) -> dict:
    return {"pass": True, "feedback": "Demo reviewer: accurate and brief."}


DEMO_RULES: dict[str, Callable[[str], dict]] = {
    "sort": _demo_sort,
    "check_injection": _demo_check_injection,
    "check_missing": _demo_check_missing,
    "check_panic": _demo_check_panic,
    "draft": _demo_draft,
    "review": _demo_review,
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
