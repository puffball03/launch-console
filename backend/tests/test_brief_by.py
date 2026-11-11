from datetime import UTC, datetime

import pytest

from app.rules.brief_by import brief_by

FILED_AT = datetime(2026, 11, 11, 9, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("severity", "minutes"),
    [("high", 5), ("medium", 15), ("low", 30)],
)
def test_brief_by_time_follows_severity(severity, minutes):
    result = brief_by(severity, has_violations=False, filed_at=FILED_AT)

    assert result.minutes == minutes
    assert result.effective_severity == severity


@pytest.mark.parametrize("severity", ["high", "medium", "low"])
def test_any_limit_violation_counts_as_high(severity):
    result = brief_by(severity, has_violations=True, filed_at=FILED_AT)

    assert result.effective_severity == "high"
    assert result.minutes == 5


def test_violation_forced_high_comes_from_the_limits_verdict():
    """End to end through the real limits code: wind 26 with a model 'low' still gets 5 minutes."""
    from app.rules.limits import check_limits

    limits = check_limits(wind_knots=26, temp_c=10, fuel_pct=99)
    result = brief_by("low", has_violations=bool(limits.violations), filed_at=FILED_AT)

    assert result.minutes == 5


@pytest.mark.parametrize(
    ("severity", "has_violations", "due"),
    [
        ("high", False, datetime(2026, 11, 11, 9, 5, tzinfo=UTC)),
        ("medium", False, datetime(2026, 11, 11, 9, 15, tzinfo=UTC)),
        ("low", False, datetime(2026, 11, 11, 9, 30, tzinfo=UTC)),
        ("low", True, datetime(2026, 11, 11, 9, 5, tzinfo=UTC)),
    ],
)
def test_deadline_is_filed_at_plus_minutes(severity, has_violations, due):
    assert brief_by(severity, has_violations=has_violations, filed_at=FILED_AT).due_at == due


@pytest.mark.parametrize("severity", ["unknown", "critical", "", "HIGH "])
def test_unrecognised_severity_is_treated_as_high(severity):
    result = brief_by(severity, has_violations=False, filed_at=FILED_AT)

    assert result.effective_severity == "high"
    assert result.minutes == 5
