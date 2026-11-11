from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

STATIONS = ("PROP", "GNC", "TELEM", "RANGE", "WX")
NOTE_MAX_CHARS = 2000

Station = Literal["PROP", "GNC", "TELEM", "RANGE", "WX"]
# Strict so "12" and true are rejected rather than coerced; out-of-limit values are fine.
Reading = Annotated[float, Field(strict=True, allow_inf_nan=False)]
NonNegativeReading = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=0)]


class ReportIn(BaseModel):
    engineer_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    station: Station
    wind_knots: NonNegativeReading
    temp_c: Reading
    fuel_pct: NonNegativeReading
    note: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=NOTE_MAX_CHARS)
    ]
