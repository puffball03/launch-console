import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal

from app.config import Settings
from app.llm.base import LLMClient, LLMResult
from app.pipeline.checks import run_checks
from app.pipeline.draft_loop import DraftFacts, run_draft_loop
from app.pipeline.guard import PREVIEW_CHARS, GuardedLLM
from app.pipeline.sort import sort_report
from app.pricing import cost_for_role
from app.repository import ReportRepository, TraceRow
from app.rules.brief_by import brief_by
from app.rules.limits import check_limits


def _plain(amount: Decimal) -> str:
    """Canonical text for a stored cost: no trailing zeros, no exponent ("0", "0.00035")."""
    return format(amount.normalize(), "f")


def _code_row(step: str, started: float, given: dict, produced: dict) -> TraceRow:
    return TraceRow(
        step=step,
        kind="code",
        model=None,
        status="ok",
        input_tokens=0,
        output_tokens=0,
        cost_usd="0",
        duration_ms=round((time.perf_counter() - started) * 1000),
        input_preview=json.dumps(given)[:PREVIEW_CHARS],
        output_preview=json.dumps(produced)[:PREVIEW_CHARS],
        error=None,
    )


def _model_row(
    guard: GuardedLLM, step: str, role: str, deployment: str, result: LLMResult | None, status: str, error: str | None
) -> TraceRow:
    call = guard.calls.get(step)
    tokens_in = result.input_tokens if result else 0
    tokens_out = result.output_tokens if result else 0
    return TraceRow(
        step=step,
        kind="model",
        model=result.model if result else deployment,
        # A step with no reply at all (the call itself failed) is an error card, not a fallback.
        status="error" if result is None and status != "ok" else status,
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        cost_usd=_plain(cost_for_role(role, input_tokens=tokens_in, output_tokens=tokens_out)),
        duration_ms=call.duration_ms if call else 0,
        input_preview=call.input_preview if call else None,
        output_preview=call.output_preview if call else None,
        error=error,
    )


async def run_pipeline(
    report_id: int,
    *,
    repo: ReportRepository,
    llm: LLMClient,
    settings: Settings,
    timeout: float = 30.0,
    retries: int = 1,
    backoff: float = 0.5,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """Run every step for one report and store facts, trace and briefing. Never raises: an
    unexpected failure marks the report failed with an error card on the trace."""
    try:
        await _run(report_id, repo, GuardedLLM(llm, timeout=timeout, retries=retries, backoff=backoff, sleep=sleep), settings)
    except Exception as exc:  # noqa: BLE001 - background task: record it, never crash the server
        repo.set_status(report_id, "failed")
        repo.add_trace_step(
            report_id,
            TraceRow("pipeline", "code", None, "error", 0, 0, "0", 0, None, None, f"{type(exc).__name__}: {exc}"),
        )


async def _run(report_id: int, repo: ReportRepository, guard: GuardedLLM, settings: Settings) -> None:
    report = repo.get(report_id)
    note = report["note"]

    started = time.perf_counter()
    readings = {k: report[k] for k in ("wind_knots", "temp_c", "fuel_pct")}
    limits = check_limits(**readings)
    violations = [asdict(v) for v in limits.violations]
    repo.add_trace_step(report_id, _code_row("limits", started, readings, {"verdict": limits.verdict, "violations": violations}))

    sort = await sort_report(guard, model=settings.model_fast, note=note)
    repo.add_trace_step(report_id, _model_row(guard, "sort", sort.role, settings.model_fast, sort.result, sort.status, sort.error))

    started = time.perf_counter()
    deadline = brief_by(sort.severity, has_violations=bool(limits.violations), filed_at=datetime.fromisoformat(report["created_at"]))
    repo.add_trace_step(
        report_id,
        _code_row(
            "brief_by",
            started,
            {"severity": sort.severity, "violations": len(violations)},
            {"effective_severity": deadline.effective_severity, "minutes": deadline.minutes},
        ),
    )

    checks = await run_checks(guard, model=settings.model_fast, note=note)
    for check in checks.checks:
        repo.add_trace_step(
            report_id, _model_row(guard, check.step, check.role, settings.model_fast, check.result, check.status, check.error)
        )
    missing = next(c for c in checks.checks if c.step == "check_missing")

    repo.save_facts(
        report_id,
        verdict=limits.verdict,
        violations=violations,
        subsystem=sort.subsystem,
        severity=sort.severity,
        effective_severity=deadline.effective_severity,
        brief_by_minutes=deadline.minutes,
        brief_by_at=deadline.due_at.isoformat(),
        flagged=checks.flagged,
        checks=[{"step": c.step, "flagged": c.flagged, "reason": c.reason, "status": c.status} for c in checks.checks],
        prescreen_hits=list(checks.prescreen_hits),
    )

    facts = DraftFacts(
        verdict=limits.verdict,
        violations=limits.violations,
        subsystem=sort.subsystem,
        effective_severity=deadline.effective_severity,
        brief_by_minutes=deadline.minutes,
        brief_by_at=deadline.due_at,
        flagged=checks.flagged,
        missing_details=missing.reason if missing.flagged and missing.status == "ok" else None,
    )
    loop = await run_draft_loop(guard, model=settings.model_smart, note=note, facts=facts)
    for step in loop.steps:
        repo.add_trace_step(report_id, _model_row(guard, step.step, step.role, settings.model_smart, step.result, step.status, step.error))

    if loop.status == "pending":
        repo.save_briefing(
            report_id, loop.briefing, rounds=loop.rounds, reviewer_satisfied=loop.reviewer_satisfied, final_feedback=loop.final_feedback
        )
        repo.set_status(report_id, "ready")
    else:
        repo.set_status(report_id, "briefing_failed")
