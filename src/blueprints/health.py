"""Health check: is the app up and can it reach MySQL? Public (no token)."""

from datetime import datetime, timezone

from flask import Blueprint, jsonify
from sqlalchemy import text

from src.extensions import db

bp = Blueprint("health", __name__)


@bp.get("/health")
@bp.get("/api/health")
def health():
    """200 when MySQL answers `SELECT 1`, 503 otherwise."""
    try:
        db.session.execute(text("SELECT 1"))
        database = "ok"
    except Exception as err:  # noqa: BLE001 - report any connection failure as unhealthy
        database = f"error: {err.__class__.__name__}"
    status = 200 if database == "ok" else 503
    return jsonify(
        status="ok" if status == 200 else "degraded",
        service="UrbanTransit IQ",
        database=database,
        time=datetime.now(timezone.utc).isoformat(),
    ), status
