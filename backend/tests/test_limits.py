import pytest

from app.rules.limits import Violation, check_limits

NOMINAL = {"wind_knots": 10, "temp_c": 15, "fuel_pct": 99}


def readings(**overrides):
    return {**NOMINAL, **overrides}


@pytest.mark.parametrize(
    ("wind", "verdict"),
    [
        (25, "go"),  # exactly on the limit
        (25.01, "no_go"),  # just past it
        (0, "go"),
    ],
)
def test_wind_limit_is_25_knots_inclusive(wind, verdict):
    assert check_limits(**readings(wind_knots=wind)).verdict == verdict


def test_wind_violation_names_field_value_and_limit():
    result = check_limits(**readings(wind_knots=26))

    assert result.violations == (Violation(field="wind_knots", value=26, limit="<= 25"),)


@pytest.mark.parametrize(
    ("temp", "verdict"),
    [
        (4, "go"),  # exactly on the limit
        (3.99, "no_go"),  # just past it
        (-10, "no_go"),
    ],
)
def test_temperature_limit_is_4c_inclusive(temp, verdict):
    assert check_limits(**readings(temp_c=temp)).verdict == verdict


@pytest.mark.parametrize(
    ("fuel", "verdict"),
    [
        (98, "go"),  # lower edge
        (100, "go"),  # upper edge
        (97.99, "no_go"),  # just below
        (100.01, "no_go"),  # just above
    ],
)
def test_fuel_limit_is_98_to_100_inclusive(fuel, verdict):
    assert check_limits(**readings(fuel_pct=fuel)).verdict == verdict


def test_temperature_violation_names_field_value_and_limit():
    result = check_limits(**readings(temp_c=3.99))

    assert result.violations == (Violation(field="temp_c", value=3.99, limit=">= 4"),)


@pytest.mark.parametrize("fuel", [97.99, 100.01])
def test_fuel_violation_names_field_value_and_limit(fuel):
    result = check_limits(**readings(fuel_pct=fuel))

    assert result.violations == (Violation(field="fuel_pct", value=fuel, limit="98 to 100"),)


def test_all_nominal_is_go_with_no_violations():
    result = check_limits(**NOMINAL)

    assert result.verdict == "go"
    assert result.violations == ()


def test_every_violation_is_listed_not_just_the_first():
    result = check_limits(wind_knots=30, temp_c=2, fuel_pct=90)

    assert result.verdict == "no_go"
    assert [v.field for v in result.violations] == ["wind_knots", "temp_c", "fuel_pct"]


@pytest.mark.parametrize("field", ["wind_knots", "temp_c", "fuel_pct"])
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_reading_is_never_go(field, bad):
    result = check_limits(**readings(**{field: bad}))

    assert result.verdict == "no_go"
    assert [v.field for v in result.violations] == [field]


def test_limits_module_never_touches_models_or_app_code():
    """The verdict must come from plain code: no model client, no pipeline, no app imports."""
    import ast
    from pathlib import Path

    import app.rules.limits as limits

    tree = ast.parse(Path(limits.__file__).read_text())
    imported = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }

    assert not {m for m in imported if m and (m == "app" or m.startswith("app."))}
