"""Users, roles and permissions (role-based access control).

A user has one or more roles; a role grants a set of permissions. Endpoints check
permissions (`analytics:read`), not role names, so a role can change without code edits.
The default role -> permission map lives in `config/rbac.yaml` and is applied with
`flask rbac seed`. Laravel analogy: spatie/laravel-permission's tables.
"""

from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from src.extensions import db

user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


def utcnow() -> datetime:
    """Timezone-aware 'now' in UTC (stored as naive UTC by MySQL DATETIME)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Permission(db.Model):
    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)   # e.g. "analytics:read"
    description = db.Column(db.String(255))


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)   # admin | operator | analyst | evaluator
    description = db.Column(db.String(255))
    permissions = db.relationship("Permission", secondary=role_permissions, lazy="selectin")


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    last_login_at = db.Column(db.DateTime)
    roles = db.relationship("Role", secondary=user_roles, lazy="selectin")

    def set_password(self, password: str) -> None:
        """Store a salted hash (Werkzeug scrypt), never the password itself."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def role_names(self) -> list[str]:
        return sorted(r.name for r in self.roles)

    @property
    def permission_names(self) -> list[str]:
        return sorted({p.name for r in self.roles for p in r.permissions})

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "is_active": self.is_active,
            "roles": self.role_names,
            "permissions": self.permission_names,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }
