from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from app.llm.base import LLMClient, LLMResult
from app.pipeline.prompting import UNTRUSTED_NOTE_RULE, wrap_note

ROLE = "fast"

SYSTEM = f"""You sort anomaly reports for a launch Flight Director.
Classify the report by subsystem and severity. Reply only with the JSON the schema asks for.

{UNTRUSTED_NOTE_RULE}"""


class Sort(BaseModel):
    subsystem: Literal["propulsion", "avionics", "telemetry", "ground_systems", "weather", "other"]
    severity: Literal["high", "medium", "low"]


@dataclass(frozen=True)
class SortOutcome:
    subsystem: str
    severity: str
    status: Literal["ok", "fallback"]
    result: LLMResult | None
    error: str | None = None
    role: str = ROLE


# Unsure means urgent: an unusable reply gets the shortest brief-by time.
FALLBACK_SUBSYSTEM = "unknown"
FALLBACK_SEVERITY = "high"


def _fallback(result: LLMResult | None, error: str) -> SortOutcome:
    return SortOutcome(
        subsystem=FALLBACK_SUBSYSTEM,
        severity=FALLBACK_SEVERITY,
        status="fallback",
        result=result,
        error=error,
    )


async def sort_report(llm: LLMClient, *, model: str, note: str) -> SortOutcome:
    try:
        result = await llm.complete(step="sort", model=model, system=SYSTEM, user=wrap_note(note), schema=Sort)
    except Exception as exc:  # noqa: BLE001 - any model failure falls back; the trace records why
        return _fallback(None, f"{type(exc).__name__}: {exc}")

    # Check in code even when the client already parsed it.
    try:
        if result.parsed is not None:
            sort = Sort.model_validate(result.parsed.model_dump())
        else:
            sort = Sort.model_validate_json(result.raw_text)
    except Exception as exc:  # noqa: BLE001 - any unusable reply falls back, so the step never raises
        return _fallback(result, f"Invalid sort reply: {exc}")

    return SortOutcome(subsystem=sort.subsystem, severity=sort.severity, status="ok", result=result)
