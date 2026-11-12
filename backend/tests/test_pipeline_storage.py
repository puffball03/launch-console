import sqlite3
from datetime import UTC, datetime

import pytest

from app.pipeline.draft_loop import FinalBriefing
from app.repository import ReportRepository, TraceRow
from app.rules.limits import Violation
from app.schemas import ReportIn

NOW = datetime(2026, 11, 12, 9, 0, tzinfo=UTC)
REPORT = ReportIn(
    engineer_name="Ada", station="WX", wind_knots=30, temp_c=10, fuel_pct=99, note="Gusts at the tower."
)


@pytest.fixture
def repo(tmp_path):
    return ReportRepository(str(tmp_path / "mission.db"))


@pytest.fixture
def report_id(repo):
    return repo.create(REPORT, now=NOW)


def row(step="sort", cost="0.00035", **overrides) -> TraceRow:
    values = dict(
        step=step, kind="model", model="mc-fast", status="ok", input_tokens=1000, output_tokens=500,
        cost_usd=cost, duration_ms=120, input_preview="in", output_preview="out", error=None,
    )
    return TraceRow(**{**values, **overrides})


def test_pipeline_facts_are_saved_on_the_report(repo, report_id):
    repo.save_facts(
        report_id,
        verdict="no_go",
        violations=[{"field": "wind_knots", "value": 30, "limit": "<= 25"}],
        subsystem="weather",
        severity="low",
        effective_severity="high",
        brief_by_minutes=5,
        brief_by_at="2026-11-12T09:05:00+00:00",
        flagged=True,
        checks=[{"step": "check_injection", "flagged": True, "reason": "r", "status": "ok"}],
        prescreen_hits=["system prefix"],
    )

    stored = repo.get(report_id)
    assert stored["verdict"] == "no_go"
    assert stored["violations"] == [{"field": "wind_knots", "value": 30, "limit": "<= 25"}]
    assert stored["flagged"] is True
    assert stored["checks"][0]["step"] == "check_injection"
    assert stored["prescreen_hits"] == ["system prefix"]
    assert (stored["effective_severity"], stored["brief_by_minutes"]) == ("high", 5)


def test_a_new_report_has_no_facts_yet(repo, report_id):
    stored = repo.get(report_id)

    assert stored["violations"] == [] and stored["checks"] == [] and stored["flagged"] is False


def test_trace_rows_come_back_in_the_order_they_were_added(repo, report_id):
    repo.add_trace_step(report_id, row("limits", kind="code", model=None, cost="0", input_tokens=0, output_tokens=0))
    repo.add_trace_step(report_id, row("sort"))
    repo.add_trace_step(report_id, row("brief_by", kind="code", model=None, cost="0"))

    trace = repo.list_trace(report_id)
    assert [(t["seq"], t["step"]) for t in trace] == [(1, "limits"), (2, "sort"), (3, "brief_by")]
    assert trace[1]["cost_usd"] == "0.00035"


@pytest.mark.parametrize("bad", ["NaN", "-0.01", "Infinity", "abc"])
def test_a_trace_cost_must_be_a_finite_non_negative_amount(repo, report_id, bad):
    with pytest.raises(ValueError):
        repo.add_trace_step(report_id, row(cost=bad))


def test_trace_is_kept_per_report(repo, report_id):
    other = repo.create(REPORT, now=NOW)
    repo.add_trace_step(report_id, row("sort"))

    assert repo.list_trace(other) == []


def briefing() -> FinalBriefing:
    return FinalBriefing(
        headline="NO-GO: wind over limit",
        situation="Gusts hit 30 kt.",
        impact_on_launch="Hold.",
        recommended_action="Re-check in 15 min.",
        open_questions=("Trend?",),
        verdict="no_go",
        violations=(Violation("wind_knots", 30, "<= 25"),),
        brief_by_minutes=5,
        brief_by_at=datetime(2026, 11, 12, 9, 5, tzinfo=UTC),
    )


def test_briefing_is_saved_pending_with_its_review_outcome(repo, report_id):
    repo.save_briefing(report_id, briefing(), rounds=2, reviewer_satisfied=False, final_feedback="Add trend.")

    stored = repo.get_briefing(report_id)
    assert stored["status"] == "pending"
    assert stored["headline"] == "NO-GO: wind over limit"
    assert stored["open_questions"] == ["Trend?"]
    assert stored["verdict"] == "no_go"
    assert stored["violations"] == [{"field": "wind_knots", "value": 30, "limit": "<= 25"}]
    assert (stored["rounds"], stored["reviewer_satisfied"], stored["final_feedback"]) == (2, False, "Add trend.")
    assert stored["decided_by"] is None


def test_report_without_a_briefing_returns_none(repo, report_id):
    assert repo.get_briefing(report_id) is None


def test_only_one_briefing_per_report(repo, report_id):
    repo.save_briefing(report_id, briefing(), rounds=1, reviewer_satisfied=True, final_feedback="ok")

    with pytest.raises(sqlite3.IntegrityError):
        repo.save_briefing(report_id, briefing(), rounds=1, reviewer_satisfied=True, final_feedback="ok")


def test_trace_and_briefing_survive_reopening_the_database(tmp_path):
    path = str(tmp_path / "mission.db")
    first = ReportRepository(path)
    report_id = first.create(REPORT, now=NOW)
    first.add_trace_step(report_id, row("sort"))
    first.save_briefing(report_id, briefing(), rounds=1, reviewer_satisfied=True, final_feedback="ok")

    reopened = ReportRepository(path)

    assert [t["step"] for t in reopened.list_trace(report_id)] == ["sort"]
    assert reopened.get_briefing(report_id)["status"] == "pending"
