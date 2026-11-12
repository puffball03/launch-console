import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

VALID = {
    "engineer_name": "Ada Ruiz",
    "station": "PROP",
    "wind_knots": 12.5,
    "temp_c": 9,
    "fuel_pct": 99.1,
    "note": "LOX valve slow to close on cycle 3.",
}


@pytest.fixture
def client(make_settings):
    return TestClient(create_app(make_settings()))


def post(client, **overrides):
    return client.post("/api/reports", json={**VALID, **overrides})


def test_valid_report_is_saved_and_returned(client):
    response = post(client)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "processing"

    stored = client.get(f"/api/reports/{body['id']}").json()
    assert {k: stored[k] for k in VALID} == {**VALID, "temp_c": 9.0}


def test_saved_report_appears_in_the_list(client):
    report_id = post(client).json()["id"]

    assert [r["id"] for r in client.get("/api/reports").json()] == [report_id]


def test_unknown_report_is_404(client):
    assert client.get("/api/reports/999").status_code == 404


@pytest.mark.parametrize(
    ("overrides", "field", "message"),
    [
        ({"engineer_name": "  "}, "engineer_name", "Name is required."),
        ({"note": ""}, "note", "Note is required."),
        ({"station": "MOON"}, "station", "Station must be one of PROP, GNC, TELEM, RANGE, WX."),
        ({"wind_knots": "fast"}, "wind_knots", "Wind must be a number."),
        ({"temp_c": None}, "temp_c", "Temperature must be a number."),
        ({"wind_knots": -1}, "wind_knots", "Wind cannot be negative."),
        ({"fuel_pct": -5}, "fuel_pct", "Fuel cannot be negative."),
        ({"note": "x" * 2001}, "note", "Note must be 2000 characters or fewer."),
        ({"engineer_name": "A" * 101}, "engineer_name", "Name must be 100 characters or fewer."),
    ],
)
def test_bad_input_gets_a_clear_message_for_that_field(client, overrides, field, message):
    response = post(client, **overrides)

    assert response.status_code == 422
    assert response.json()["errors"] == {field: message}


def test_missing_field_is_named(client):
    data = {k: v for k, v in VALID.items() if k != "station"}

    response = client.post("/api/reports", json=data)

    assert response.status_code == 422
    assert response.json()["errors"] == {"station": "Station is required."}


def test_nan_in_json_is_rejected(client):
    raw = json.dumps(VALID).replace('"wind_knots": 12.5', '"wind_knots": NaN')

    response = client.post("/api/reports", content=raw, headers={"content-type": "application/json"})

    assert response.status_code == 422
    assert response.json()["errors"] == {"wind_knots": "Wind must be a number."}


def test_rejected_report_is_not_saved(client):
    post(client, station="MOON")

    assert client.get("/api/reports").json() == []


@pytest.mark.parametrize(
    "overrides", [{"wind_knots": 30}, {"temp_c": 1}, {"fuel_pct": 100.01}]
)
def test_out_of_limit_readings_are_accepted(client, overrides):
    assert post(client, **overrides).status_code == 201


def test_reports_are_still_there_after_a_restart(make_settings):
    settings = make_settings()
    report_id = post(TestClient(create_app(settings))).json()["id"]

    restarted = TestClient(create_app(settings))

    assert [r["id"] for r in restarted.get("/api/reports").json()] == [report_id]
    assert restarted.get(f"/api/reports/{report_id}").json()["engineer_name"] == "Ada Ruiz"


def test_restart_marks_reports_stuck_in_processing_as_failed(make_settings):
    from datetime import UTC, datetime

    from app.repository import ReportRepository
    from app.schemas import ReportIn

    settings = make_settings()
    # Filed but never processed, as if the server stopped mid-pipeline.
    report_id = ReportRepository(settings.db_path).create(ReportIn(**VALID), now=datetime.now(UTC))

    restarted = TestClient(create_app(settings))

    assert restarted.get(f"/api/reports/{report_id}").json()["status"] == "failed"
