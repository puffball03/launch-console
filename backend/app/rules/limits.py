from dataclasses import dataclass
from math import isfinite
from typing import Literal

WIND_MAX_KNOTS = 25
TEMP_MIN_C = 4
FUEL_MIN_PCT = 98
FUEL_MAX_PCT = 100


@dataclass(frozen=True)
class Violation:
    field: str
    value: float
    limit: str


@dataclass(frozen=True)
class LimitsResult:
    verdict: Literal["go", "no_go"]
    violations: tuple[Violation, ...]


def check_limits(*, wind_knots: float, temp_c: float, fuel_pct: float) -> LimitsResult:
    """Launch limits in plain code. Edges are inclusive; every violation is listed.

    A non-finite reading (NaN or infinity) counts as a violation, because NaN fails
    every comparison and would otherwise pass as go.
    """
    violations = []
    if not isfinite(wind_knots) or wind_knots > WIND_MAX_KNOTS:
        violations.append(Violation("wind_knots", wind_knots, f"<= {WIND_MAX_KNOTS}"))
    if not isfinite(temp_c) or temp_c < TEMP_MIN_C:
        violations.append(Violation("temp_c", temp_c, f">= {TEMP_MIN_C}"))
    if not isfinite(fuel_pct) or not FUEL_MIN_PCT <= fuel_pct <= FUEL_MAX_PCT:
        violations.append(Violation("fuel_pct", fuel_pct, f"{FUEL_MIN_PCT} to {FUEL_MAX_PCT}"))

    return LimitsResult(verdict="no_go" if violations else "go", violations=tuple(violations))
