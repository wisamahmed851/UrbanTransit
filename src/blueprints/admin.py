"""Admin screens: reference-data CRUD, user management and the audit log.

Reference data (routes / stops / vehicles), MySQL working copy of the Phase 3 clean tables:

    GET    /api/admin/<entity>              list (paged; ?q= searches id and name)   reference:read
    GET    /api/admin/<entity>/<id>         one row (+ its analytics summary)        reference:read
    POST   /api/admin/<entity>              create                                   reference:write
    PATCH  /api/admin/<entity>/<id>         partial update                           reference:write
    DELETE /api/admin/<entity>/<id>         delete (409 if still referenced)         reference:write

Users and audit:

    GET/POST /api/admin/users, PATCH /api/admin/users/<id>                           users:manage
    GET      /api/admin/audit-log                                                    audit:read

Edits are not written back to HDFS: the analytics pipeline keeps reading the clean
Parquet, so analytics reflect the data as it was when Phase 5 ran.
"""

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_, select

from src.errors import ApiError
from src.extensions import db
from src.models.analytics import ANALYTICS_TABLES
from src.models.ops import AuditLog
from src.models.rbac import Role, User
from src.models.reference import REFERENCE_MODELS, Route, Stop
from src.security import permission_required
from src.services import audit
from src.services.analytics_query import to_json_value
from src.services.reference_validation import validate
from src.services.requests import int_arg, json_body

bp = Blueprint("admin", __name__, url_prefix="/api/admin")

NAME_COLUMN = {"routes": "route_name", "stops": "stop_name", "vehicles": "registration_no"}
# Analytics rows shown with a reference row: (entity, table, key column).
SUMMARIES = {
    "routes": [("route_performance", "route_id"), ("route_reliability", "route_id")],
    "stops": [("stop_performance", "stop_id")],
}


def _model(entity: str):
    if entity not in REFERENCE_MODELS:
        raise ApiError(404, "unknown_entity", f"No reference entity '{entity}'.", {"available": sorted(REFERENCE_MODELS)})
    return REFERENCE_MODELS[entity]


def _get_or_404(model, key: str):
    row = db.session.get(model, key)
    if row is None:
        raise ApiError(404, "not_found", f"{model.__tablename__}/{key} does not exist.")
    return row


def _check_route_stops(values: dict) -> None:
    """Routes must start and end at existing stops (clear 400 rather than a raw FK error)."""
    for col in ("origin_stop_id", "destination_stop_id"):
        if col in values and db.session.get(Stop, values[col]) is None:
            raise ApiError(400, "validation_failed", "Invalid routes data.", {"fields": {col: "unknown stop_id"}})


def _summary(entity: str, key: str) -> dict:
    out = {}
    for table_name, column in SUMMARIES.get(entity, []):
        table = ANALYTICS_TABLES[table_name]
        row = db.session.execute(select(*[c for c in table.columns if c.name != "id"])
                                 .where(table.c[column] == key)).mappings().first()
        out[table_name] = {k: to_json_value(v) for k, v in row.items()} if row else None
    return out


# ---- reference data --------------------------------------------------------------------

@bp.get("/<entity>")
@permission_required("reference:read")
def list_entities(entity: str):
    model = _model(entity)
    pk = model.__mapper__.primary_key[0]
    query = select(model).order_by(pk)
    if request.args.get("q"):
        like = f"%{request.args['q']}%"
        query = query.where(or_(pk.like(like), getattr(model, NAME_COLUMN[entity]).like(like)))
    limit, offset = int_arg("limit", 100, 1, 1000), int_arg("offset", 0, 0)
    total = db.session.execute(select(func.count()).select_from(query.order_by(None).subquery())).scalar_one()
    rows = db.session.execute(query.limit(limit).offset(offset)).scalars()
    return jsonify(entity=entity, total=total, limit=limit, offset=offset, rows=[r.to_dict() for r in rows])


@bp.get("/<entity>/<key>")
@permission_required("reference:read")
def get_entity(entity: str, key: str):
    row = _get_or_404(_model(entity), key)
    return jsonify(row=row.to_dict(), analytics=_summary(entity, key))


@bp.post("/<entity>")
@permission_required("reference:write")
def create_entity(entity: str):
    model = _model(entity)
    values = validate(entity, model, json_body(), partial=False)
    pk = model.__mapper__.primary_key[0].name
    if db.session.get(model, values[pk]) is not None:
        raise ApiError(409, "conflict", f"{entity}/{values[pk]} already exists.")
    if model is Route:
        _check_route_stops(values)
    row = model(**values, dq_flags=[])
    db.session.add(row)
    audit.record(f"{entity}.create", entity=f"{entity}/{values[pk]}", details={"values": row.to_dict()})
    db.session.commit()
    return jsonify(row=row.to_dict()), 201


@bp.patch("/<entity>/<key>")
@permission_required("reference:write")
def update_entity(entity: str, key: str):
    model = _model(entity)
    row = _get_or_404(model, key)
    values = validate(entity, model, json_body(), partial=True)
    if model is Route:
        _check_route_stops(values)
    before = {k: to_json_value(getattr(row, k)) for k in values}
    for k, v in values.items():
        setattr(row, k, v)
    audit.record(f"{entity}.update", entity=f"{entity}/{key}",
                 details={"before": before, "after": {k: to_json_value(v) for k, v in values.items()}})
    db.session.commit()
    return jsonify(row=row.to_dict())


@bp.delete("/<entity>/<key>")
@permission_required("reference:write")
def delete_entity(entity: str, key: str):
    model = _model(entity)
    row = _get_or_404(model, key)
    if model is Stop:
        used = db.session.execute(select(Route.route_id).where(
            or_(Route.origin_stop_id == key, Route.destination_stop_id == key))).scalars().all()
        if used:
            raise ApiError(409, "conflict", f"stops/{key} is a terminus of routes {used}.", {"routes": used})
    audit.record(f"{entity}.delete", entity=f"{entity}/{key}", details={"deleted": row.to_dict()})
    db.session.delete(row)
    db.session.commit()
    return "", 204


# ---- users -----------------------------------------------------------------------------

def _roles(names) -> list[Role]:
    if not isinstance(names, list) or not names:
        raise ApiError(400, "validation_failed", "'roles' must be a non-empty list.")
    found = db.session.execute(select(Role).where(Role.name.in_(names))).scalars().all()
    missing = sorted(set(names) - {r.name for r in found})
    if missing:
        raise ApiError(400, "validation_failed", "Unknown roles.", {"unknown_roles": missing})
    return list(found)


@bp.get("/users")
@permission_required("users:manage")
def list_users():
    users = db.session.execute(select(User).order_by(User.id)).scalars()
    return jsonify(users=[u.to_dict() for u in users])


@bp.post("/users")
@permission_required("users:manage")
def create_user():
    body = json_body(required=("username", "password", "roles"))
    if len(body["password"]) < 8:
        raise ApiError(400, "validation_failed", "Password must be at least 8 characters.")
    if db.session.execute(select(User).filter_by(username=body["username"])).scalar_one_or_none():
        raise ApiError(409, "conflict", f"User '{body['username']}' already exists.")
    user = User(username=body["username"], email=body.get("email"), roles=_roles(body["roles"]))
    user.set_password(body["password"])
    db.session.add(user)
    db.session.flush()
    audit.record("users.create", entity=f"users/{user.id}", details={"username": user.username, "roles": user.role_names})
    db.session.commit()
    return jsonify(user=user.to_dict()), 201


@bp.patch("/users/<int:user_id>")
@permission_required("users:manage")
def update_user(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        raise ApiError(404, "not_found", f"users/{user_id} does not exist.")
    body = json_body()
    changes = {}
    if "roles" in body:
        user.roles = _roles(body["roles"])
        changes["roles"] = user.role_names
    if "is_active" in body:
        if not isinstance(body["is_active"], bool):
            raise ApiError(400, "validation_failed", "'is_active' must be true or false.")
        user.is_active = body["is_active"]
        changes["is_active"] = user.is_active
    if "email" in body:
        user.email = body["email"]
        changes["email"] = user.email
    if "password" in body:
        if not isinstance(body["password"], str) or len(body["password"]) < 8:
            raise ApiError(400, "validation_failed", "Password must be at least 8 characters.")
        user.set_password(body["password"])
        changes["password"] = "changed"
    audit.record("users.update", entity=f"users/{user_id}", details=changes)
    db.session.commit()
    return jsonify(user=user.to_dict())


# ---- audit log -------------------------------------------------------------------------

@bp.get("/audit-log")
@permission_required("audit:read")
def audit_log():
    query = select(AuditLog).order_by(AuditLog.id.desc())
    for param in ("actor", "action"):
        if request.args.get(param):
            query = query.where(getattr(AuditLog, param) == request.args[param])
    limit, offset = int_arg("limit", 100, 1, 1000), int_arg("offset", 0, 0)
    rows = db.session.execute(query.limit(limit).offset(offset)).scalars()
    return jsonify(entries=[r.to_dict() for r in rows], limit=limit, offset=offset)
