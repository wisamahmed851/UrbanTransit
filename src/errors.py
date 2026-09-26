"""Central JSON error handling.

Every error leaves the API in one shape:

    {"error": {"code": "not_found", "message": "...", "details": {...}}}

Laravel analogy: `app/Exceptions/Handler::render`; NestJS: a global `ExceptionFilter`.
"""

import logging

from flask import Flask, jsonify
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

log = logging.getLogger(__name__)


class ApiError(Exception):
    """An expected error with an HTTP status, a machine-readable code and optional details."""

    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def error_response(status: int, code: str, message: str, details: dict | None = None):
    """Build the standard error body and status."""
    body = {"code": code, "message": message}
    if details:
        body["details"] = details
    return jsonify(error=body), status


def register_error_handlers(app: Flask) -> None:
    """Attach the handlers for our own errors, HTTP errors, DB conflicts and crashes."""

    @app.errorhandler(ApiError)
    def _api_error(err: ApiError):
        return error_response(err.status, err.code, err.message, err.details)

    @app.errorhandler(HTTPException)
    def _http_error(err: HTTPException):
        code = (err.name or "error").lower().replace(" ", "_")
        return error_response(err.code or 500, code, err.description or err.name)

    @app.errorhandler(IntegrityError)
    def _integrity_error(err: IntegrityError):
        from src.extensions import db

        db.session.rollback()
        return error_response(409, "conflict", "The change conflicts with existing data.",
                              {"database": str(err.orig)})

    @app.errorhandler(Exception)
    def _unexpected(err: Exception):
        log.exception("Unhandled error")
        return error_response(500, "internal_error", "Unexpected server error.")
