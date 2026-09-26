"""Explicit stubs for features whose data does not exist yet. They never fake a result.

POST /api/predictions/delay      503: the delay models are flagged INVALID (occupancy_pct leakage)
POST /api/predictions/crowding   503: no Phase 7 pipeline or full prediction set yet
GET  /api/recommendations        503: no Phase 7 recommendation engine yet

Each returns HTTP 503 with `"stub": true`, so a frontend can show "not available yet"
without treating it as an outage. Replace a stub only when its data or model is real.
"""

from flask import Blueprint, jsonify

from src.security import permission_required

bp = Blueprint("stubs", __name__, url_prefix="/api")

REASONS = {
    "predictions.delay": "unavailable - underlying models flagged invalid (occupancy_pct leakage), pending retrain",
    "predictions.crowding": "unavailable - Phase 7 pipeline and full prediction set not yet produced",
    "recommendations": "unavailable - Phase 7 recommendation engine not yet built",
}


def _unavailable(feature: str):
    return jsonify(status="unavailable", stub=True, feature=feature, reason=REASONS[feature]), 503


@bp.post("/predictions/delay")
@permission_required("predictions:use")
def predict_delay():
    return _unavailable("predictions.delay")


@bp.post("/predictions/crowding")
@permission_required("predictions:use")
def predict_crowding():
    return _unavailable("predictions.crowding")


@bp.get("/recommendations")
@permission_required("recommendations:read")
def recommendations():
    return _unavailable("recommendations")
