from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas import NAME_MAX_CHARS, NOTE_MAX_CHARS, REASON_MAX_CHARS, STATIONS

LABELS = {
    "engineer_name": "Name",
    "station": "Station",
    "wind_knots": "Wind",
    "temp_c": "Temperature",
    "fuel_pct": "Fuel",
    "note": "Note",
    "approver_name": "Approver name",
    "reason": "Reason",
}

MAX_CHARS = {
    "engineer_name": NAME_MAX_CHARS,
    "note": NOTE_MAX_CHARS,
    "approver_name": NAME_MAX_CHARS,
    "reason": REASON_MAX_CHARS,
}


def _message(field: str, error_type: str, fallback: str) -> str:
    label = LABELS.get(field, field)
    if error_type in ("missing", "string_too_short"):
        return f"{label} is required."
    if error_type == "string_too_long" and field in MAX_CHARS:
        return f"{label} must be {MAX_CHARS[field]} characters or fewer."
    if error_type == "literal_error":
        return f"{label} must be one of {', '.join(STATIONS)}."
    if error_type in ("float_type", "finite_number", "float_parsing"):
        return f"{label} must be a number."
    if error_type == "greater_than_equal":
        return f"{label} cannot be negative."
    return fallback


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Turn Pydantic errors into one plain message per form field."""
    errors: dict[str, str] = {}
    for err in exc.errors():
        loc = err.get("loc", ())
        field = str(loc[1]) if len(loc) > 1 and loc[0] == "body" else "_body"
        if field == "_body":
            errors.setdefault(field, "Request body must be a JSON object with the report fields.")
        else:
            errors.setdefault(field, _message(field, err["type"], err["msg"]))
    return JSONResponse(status_code=422, content={"detail": "Invalid report", "errors": errors})
