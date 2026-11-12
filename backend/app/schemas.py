from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

STATIONS = ("PROP", "GNC", "TELEM", "RANGE", "WX")
NAME_MAX_CHARS = 100
REASON_MAX_CHARS = 500
NOTE_MAX_CHARS = 2000

Station = Literal["PROP", "GNC", "TELEM", "RANGE", "WX"]
# Strict so "12" and true are rejected rather than coerced; out-of-limit values are fine.
Reading = Annotated[float, Field(strict=True, allow_inf_nan=False)]
NonNegativeReading = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=0)]


class ReportIn(BaseModel):
    engineer_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=NAME_MAX_CHARS)]
    station: Station
    wind_knots: NonNegativeReading
    temp_c: Reading
    fuel_pct: NonNegativeReading
    note: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=NOTE_MAX_CHARS)
    ]


ApproverName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=NAME_MAX_CHARS)]


class ApproveIn(BaseModel):
    approver_name: ApproverName


class RejectIn(BaseModel):
    approver_name: ApproverName
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=REASON_MAX_CHARS)] | None = None
