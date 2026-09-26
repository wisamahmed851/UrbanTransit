"""Authentication: log in for a JWT, and read the current user.

POST /api/auth/login   {"username": "...", "password": "..."} -> {"access_token": "...", ...}
GET  /api/auth/me      the user behind the token, with roles and permissions
"""

from flask import Blueprint, current_app, jsonify
from flask_jwt_extended import create_access_token, current_user

from src.errors import ApiError
from src.extensions import db
from src.models.rbac import User, utcnow
from src.security import login_required
from src.services import audit
from src.services.requests import json_body

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/login")
def login():
    """Exchange username + password for a bearer token. Failures get one generic message."""
    body = json_body(required=("username", "password"))
    user = db.session.execute(db.select(User).filter_by(username=body["username"])).scalar_one_or_none()
    if user is None or not user.is_active or not user.check_password(body["password"]):
        audit.record("auth.login_failed", details={"username": body["username"]}, actor="anonymous", commit=True)
        raise ApiError(401, "invalid_credentials", "Invalid username or password.")

    user.last_login_at = utcnow()
    audit.record("auth.login", entity=f"users/{user.id}", actor=user.username)
    db.session.commit()
    expires = current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]
    return jsonify(
        access_token=create_access_token(identity=user),
        token_type="Bearer",
        expires_in=int(expires.total_seconds()),
        user=user.to_dict(),
    )


@bp.get("/me")
@login_required
def me():
    return jsonify(user=current_user.to_dict())
