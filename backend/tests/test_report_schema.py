import pytest
from pydantic import ValidationError

from app.schemas import ReportIn

VALID = {
    "engineer_name": "Ada Ruiz",
    "station": "PROP",
    "wind_knots": 12.5,
    "temp_c": 9,
    "fuel_pct": 99.1,
    "note": "LOX valve slow to close on cycle 3.",
}


def report(**overrides):
    return {**VALID, **overrides}


def error_fields(exc: ValidationError) -> set[str]:
    return {str(err["loc"][0]) for err in exc.errors()}


def test_valid_report_is_accepted():
    parsed = ReportIn.model_validate(report())

    assert parsed.station == "PROP"
    assert parsed.wind_knots == 12.5


def test_name_and_note_are_trimmed():
    parsed = ReportIn.model_validate(report(engineer_name="  Ada  ", note="  valve  "))

    assert (parsed.engineer_name, parsed.note) == ("Ada", "valve")


@pytest.mark.parametrize("field", ["engineer_name", "note"])
@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_name_or_note_is_rejected(field, blank):
    with pytest.raises(ValidationError) as exc:
        ReportIn.model_validate(report(**{field: blank}))

    assert error_fields(exc.value) == {field}


@pytest.mark.parametrize("field", list(VALID))
def test_every_field_is_required(field):
    data = report()
    del data[field]

    with pytest.raises(ValidationError) as exc:
        ReportIn.model_validate(data)

    assert error_fields(exc.value) == {field}


def test_unknown_station_is_rejected():
    with pytest.raises(ValidationError) as exc:
        ReportIn.model_validate(report(station="MOON"))

    assert error_fields(exc.value) == {"station"}


@pytest.mark.parametrize("field", ["wind_knots", "temp_c", "fuel_pct"])
@pytest.mark.parametrize("bad", ["12", "abc", None, True, float("nan"), float("inf")])
def test_reading_must_be_a_finite_number(field, bad):
    with pytest.raises(ValidationError) as exc:
        ReportIn.model_validate(report(**{field: bad}))

    assert error_fields(exc.value) == {field}


@pytest.mark.parametrize("field", ["wind_knots", "fuel_pct"])
def test_negative_wind_or_fuel_is_rejected(field):
    with pytest.raises(ValidationError) as exc:
        ReportIn.model_validate(report(**{field: -0.1}))

    assert error_fields(exc.value) == {field}


def test_negative_temperature_is_allowed():
    assert ReportIn.model_validate(report(temp_c=-12)).temp_c == -12


def test_note_over_2000_characters_is_rejected():
    with pytest.raises(ValidationError) as exc:
        ReportIn.model_validate(report(note="x" * 2001))

    assert error_fields(exc.value) == {"note"}


def test_note_of_exactly_2000_characters_is_accepted():
    assert len(ReportIn.model_validate(report(note="x" * 2000)).note) == 2000


@pytest.mark.parametrize(
    "overrides",
    [{"wind_knots": 30}, {"temp_c": 1}, {"fuel_pct": 100.01}, {"fuel_pct": 50}],
)
def test_out_of_limit_readings_are_accepted(overrides):
    """Limits decide the verdict; validation only rejects input that isn't a reading."""
    ReportIn.model_validate(report(**overrides))
