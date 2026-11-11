from datetime import UTC, datetime

import pytest

from app.repository import ReportRepository
from app.schemas import ReportIn

NOW = datetime(2026, 11, 11, 9, 0, tzinfo=UTC)


def make_report(**overrides) -> ReportIn:
    data = {
        "engineer_name": "Ada Ruiz",
        "station": "PROP",
        "wind_knots": 12.5,
        "temp_c": 9.0,
        "fuel_pct": 99.1,
        "note": "LOX valve slow to close on cycle 3.",
    }
    return ReportIn.model_validate({**data, **overrides})


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "mission.db")


def test_create_then_get_round_trips_every_field(db_path):
    repo = ReportRepository(db_path)

    report_id = repo.create(make_report(), now=NOW)
    stored = repo.get(report_id)

    assert stored["id"] == report_id
    assert stored["engineer_name"] == "Ada Ruiz"
    assert stored["station"] == "PROP"
    assert (stored["wind_knots"], stored["temp_c"], stored["fuel_pct"]) == (12.5, 9.0, 99.1)
    assert stored["note"] == "LOX valve slow to close on cycle 3."
    assert stored["status"] == "processing"
    assert stored["created_at"] == NOW.isoformat()


def test_get_unknown_id_returns_none(db_path):
    assert ReportRepository(db_path).get(999) is None


def test_list_returns_newest_first(db_path):
    repo = ReportRepository(db_path)
    first = repo.create(make_report(engineer_name="First"), now=NOW)
    second = repo.create(make_report(engineer_name="Second"), now=NOW.replace(minute=5))

    assert [r["id"] for r in repo.list()] == [second, first]


def test_reports_survive_reopening_the_database_file(db_path):
    report_id = ReportRepository(db_path).create(make_report(), now=NOW)

    reopened = ReportRepository(db_path)

    assert reopened.get(report_id)["engineer_name"] == "Ada Ruiz"


def test_creates_missing_parent_directory(tmp_path):
    repo = ReportRepository(str(tmp_path / "nested" / "dir" / "mission.db"))

    assert repo.get(repo.create(make_report(), now=NOW)) is not None


def test_fail_stale_processing_marks_only_processing_reports(db_path):
    repo = ReportRepository(db_path)
    stuck = repo.create(make_report(), now=NOW)
    done = repo.create(make_report(), now=NOW)
    repo.set_status(done, "ready")

    changed = repo.fail_stale_processing()

    assert changed == 1
    assert repo.get(stuck)["status"] == "failed"
    assert repo.get(done)["status"] == "ready"
