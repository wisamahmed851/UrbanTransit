"""Predictions and what-if scenarios from the saved Phase 7 models (CMD-024). They replace the 503 stubs.

POST /api/predictions/crowding        {route_id, direction, service_date, hour, vehicle_id?}
POST /api/predictions/delay           same body
GET  /api/predictions/crowding-risk   ?date=YYYY-MM-DD&route_id=&limit=  every cell of that day type, riskiest first
GET  /api/whatif/scenarios            the supported scenario types
POST /api/whatif                      {scenario, route_id, direction, service_date, hour, params{}}

Every answer is labelled an estimate and carries the model's name, version, test metrics and
whether it meets the SRS accuracy target. The delay model does not meet it, and its answers
say so. Controllers stay thin (Laravel: controller -> service class); the work is in
src/services/model_serving.py and src/services/whatif.py.
"""

from datetime import date

from flask import Blueprint, jsonify, request

from src.errors import ApiError
from src.security import permission_required
from src.services import model_serving, whatif
from src.services.audit import record
from src.services.requests import int_arg, json_body

bp = Blueprint("predictions", __name__, url_prefix="/api")


def parse_date(value, field: str = "service_date") -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ApiError(400, "invalid_parameter", f"'{field}' must be a date (YYYY-MM-DD).") from None


def trip_request(body: dict) -> tuple[str, int, date, int]:
    """route_id, direction (0/1), service_date and hour (0-23) from a JSON body."""
    try:
        direction, hour = int(body["direction"]), int(body["hour"])
    except (TypeError, ValueError):
        raise ApiError(400, "invalid_parameter", "'direction' and 'hour' must be integers.") from None
    if direction not in (0, 1):
        raise ApiError(400, "invalid_parameter", "'direction' must be 0 or 1.")
    if not 0 <= hour <= 23:
        raise ApiError(400, "invalid_parameter", "'hour' must be between 0 and 23.")
    return str(body["route_id"]).strip().upper(), direction, parse_date(body["service_date"]), hour


@bp.post("/predictions/crowding")
@permission_required("predictions:use")
def predict_crowding():
    body = json_body(required=("route_id", "direction", "service_date", "hour"))
    result = model_serving.predict_crowding(*trip_request(body), vehicle_id=body.get("vehicle_id") or None)
    record("predictions.crowding", f"routes/{result['trip']['route_id']}", {**result["trip"], **result["prediction"]}, commit=True)
    return jsonify(result)


@bp.post("/predictions/delay")
@permission_required("predictions:use")
def predict_delay():
    body = json_body(required=("route_id", "direction", "service_date", "hour"))
    result = model_serving.predict_delay(*trip_request(body), vehicle_id=body.get("vehicle_id") or None)
    record("predictions.delay", f"routes/{result['trip']['route_id']}",
           {**result["trip"], "severity": result["prediction"]["severity"]}, commit=True)
    return jsonify(result)


@bp.get("/predictions/crowding-risk")
@permission_required("predictions:use")
def crowding_risk():
    day = parse_date(request.args.get("date") or "", "date")
    route_id = (request.args.get("route_id") or "").strip().upper() or None
    limit = int_arg("limit", 50, 1, 5000)
    result = model_serving.crowding_risk_for_day(day, route_id)
    return jsonify({**result, "rows": result["rows"][:limit], "limit": limit})


@bp.get("/whatif/scenarios")
@permission_required("predictions:use")
def scenarios():
    return jsonify(scenarios=[{"type": k, "description": v} for k, v in whatif.SCENARIOS.items()])


@bp.post("/whatif")
@permission_required("predictions:use")
def run_whatif():
    body = json_body(required=("scenario", "route_id", "direction", "service_date", "hour"))
    params = body.get("params") or {}
    if not isinstance(params, dict):
        raise ApiError(400, "invalid_parameter", "'params' must be an object.")
    route_id, direction, day, hour = trip_request(body)
    result = whatif.simulate(str(body["scenario"]), route_id, direction, day, hour, params)
    record("whatif.run", f"routes/{route_id}", result["scenario"], commit=True)
    return jsonify(result)
