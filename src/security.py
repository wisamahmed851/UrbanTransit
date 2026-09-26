"""JWT authentication and role/permission guards.

Tokens carry only the user id (plus role names for the frontend's convenience). Every
protected request reloads the user from MySQL, so a deactivated account or a changed role
takes effect immediately rather than when the token expires.

Usage, like a NestJS guard or Laravel `->middleware('can:...')`:

    @bp.get("/things")
    @permission_required("analytics:read")
    def list_things(): ...
"""

from functools import wraps

from flask_jwt_extended import current_user, verify_jwt_in_request

from src.errors import ApiError, error_response
from src.extensions import db, jwt
from src.models.rbac import User


@jwt.user_identity_loader
def _identity(user: User) -> str:
    return str(user.id)


@jwt.additional_claims_loader
def _claims(user: User) -> dict:
    return {"roles": user.role_names}


@jwt.user_lookup_loader
def _load_user(_header: dict, payload: dict) -> User | None:
    user = db.session.get(User, int(payload["sub"]))
    return user if user is not None and user.is_active else None


@jwt.user_lookup_error_loader
def _user_gone(_header, _payload):
    return error_response(401, "account_unavailable", "The account no longer exists or is deactivated.")


@jwt.unauthorized_loader
def _missing_token(reason: str):
    return error_response(401, "unauthorized", "Missing or malformed Authorization header.", {"reason": reason})


@jwt.invalid_token_loader
def _invalid_token(reason: str):
    return error_response(401, "invalid_token", "The token is invalid.", {"reason": reason})


@jwt.expired_token_loader
def _expired_token(_header, _payload):
    return error_response(401, "token_expired", "The token has expired; log in again.")


def _require(check, describe: str):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            if not check(current_user):
                raise ApiError(403, "forbidden", f"Requires {describe}.")
            return view(*args, **kwargs)
        return wrapper
    return decorator


def login_required(view):
    """Any active, authenticated user."""
    return _require(lambda user: True, "an authenticated user")(view)


def permission_required(*permissions: str):
    """The user's roles must grant every listed permission."""
    return _require(lambda user: set(permissions) <= set(user.permission_names),
                    "permission " + ", ".join(permissions))


def role_required(*roles: str):
    """The user must hold at least one of the listed roles."""
    return _require(lambda user: bool(set(roles) & set(user.role_names)), "role " + " or ".join(roles))
