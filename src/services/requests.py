"""Small request-parsing helpers shared by the Blueprints (like a Laravel FormRequest)."""

from flask import request

from src.errors import ApiError


def json_body(required: tuple[str, ...] = ()) -> dict:
    """The JSON object body; 400 if it is missing, not an object, or lacks required keys."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "invalid_body", "Expected a JSON object body.")
    missing = [k for k in required if body.get(k) in (None, "")]
    if missing:
        raise ApiError(400, "missing_fields", "Required fields are missing.", {"missing": missing})
    return body


def int_arg(name: str, default: int, minimum: int = 0, maximum: int | None = None) -> int:
    """An integer query parameter with bounds; 400 on garbage."""
    raw = request.args.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ApiError(400, "invalid_parameter", f"'{name}' must be an integer.") from None
    if value < minimum or (maximum is not None and value > maximum):
        raise ApiError(400, "invalid_parameter", f"'{name}' must be between {minimum} and {maximum}.")
    return value
