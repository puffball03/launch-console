from dataclasses import dataclass
from datetime import datetime, timedelta

BRIEF_BY_MINUTES = {"high": 5, "medium": 15, "low": 30}


@dataclass(frozen=True)
class BriefBy:
    effective_severity: str
    minutes: int
    due_at: datetime


def brief_by(severity: str, *, has_violations: bool, filed_at: datetime) -> BriefBy:
    """Brief-by time from severity. Any launch-limit violation counts as high.

    A severity this table doesn't know is also treated as high: when unsure, brief sooner.
    """
    effective = "high" if has_violations or severity not in BRIEF_BY_MINUTES else severity
    minutes = BRIEF_BY_MINUTES[effective]
    return BriefBy(
        effective_severity=effective,
        minutes=minutes,
        due_at=filed_at + timedelta(minutes=minutes),
    )
