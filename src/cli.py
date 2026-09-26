"""Flask CLI commands (Laravel: Artisan commands; NestJS: a nest-commander command).

    flask rbac seed                                  # roles + permissions from config/rbac.yaml
    flask users create alice --role analyst          # prompts for the password twice
"""

from pathlib import Path

import click
import yaml
from flask import Flask

from src.extensions import db
from src.models.rbac import Permission, Role, User

RBAC_FILE = Path(__file__).resolve().parent.parent / "config" / "rbac.yaml"


def seed_rbac() -> tuple[int, int]:
    """Create or update every permission and role in config/rbac.yaml. Idempotent."""
    spec = yaml.safe_load(RBAC_FILE.read_text(encoding="utf-8"))
    perms = {}
    for name, description in spec["permissions"].items():
        perm = db.session.execute(db.select(Permission).filter_by(name=name)).scalar_one_or_none()
        perm = perm or Permission(name=name)
        perm.description = description
        db.session.add(perm)
        perms[name] = perm
    for name, role_spec in spec["roles"].items():
        role = db.session.execute(db.select(Role).filter_by(name=name)).scalar_one_or_none() or Role(name=name)
        role.description = role_spec.get("description")
        granted = role_spec["permissions"]
        unknown = [] if granted == "all" else [p for p in granted if p not in perms]
        if unknown:
            raise click.ClickException(f"role {name}: unknown permissions {unknown}")
        role.permissions = list(perms.values()) if granted == "all" else [perms[p] for p in granted]
        db.session.add(role)
    db.session.commit()
    return len(spec["permissions"]), len(spec["roles"])


def register_cli(app: Flask) -> None:
    rbac = click.Group("rbac", help="Roles and permissions.")
    users = click.Group("users", help="User accounts.")

    @rbac.command("seed")
    def rbac_seed():
        """Apply config/rbac.yaml."""
        n_perms, n_roles = seed_rbac()
        click.echo(f"RBAC seeded: {n_perms} permissions, {n_roles} roles")

    @users.command("create")
    @click.argument("username")
    @click.option("--email", default=None)
    @click.option("--role", "roles", multiple=True, required=True, help="repeatable: admin, operator, analyst, evaluator")
    @click.password_option()
    def users_create(username, email, roles, password):
        """Create a user with one or more roles (run `flask rbac seed` first)."""
        found = db.session.execute(db.select(Role).where(Role.name.in_(roles))).scalars().all()
        missing = set(roles) - {r.name for r in found}
        if missing:
            raise click.ClickException(f"unknown roles {sorted(missing)}; run `flask rbac seed` first")
        user = User(username=username, email=email, roles=list(found))
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"created user {username} (id {user.id}) with roles {sorted(roles)}")

    app.cli.add_command(rbac)
    app.cli.add_command(users)
