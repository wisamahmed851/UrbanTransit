"""UrbanTransit IQ Flask application factory.

Run (inside WSL, repo root, venv active):

    flask run                      # FLASK_APP comes from .flaskenv
    python src/app.py              # same, using FLASK_HOST / FLASK_PORT from .env

`create_app` works like Laravel's `bootstrap/app.php` or NestJS's `NestFactory.create`:
it builds the app, wires extensions, registers route groups (Blueprints) and the global
error handler.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask  # noqa: E402

from config import settings  # noqa: E402
from src.config import BaseConfig  # noqa: E402
from src.errors import register_error_handlers  # noqa: E402
from src.extensions import cors, db, jwt, migrate  # noqa: E402

MIGRATIONS_DIR = str(Path(__file__).resolve().parent.parent / "database" / "migrations")


def create_app(config_object: type = BaseConfig) -> Flask:
    """Build a configured app. Tests pass `TestingConfig` (SQLite in memory)."""
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db, directory=MIGRATIONS_DIR)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    from src import models, security  # noqa: F401  (tables for Flask-Migrate; JWT callbacks)
    from src.blueprints import admin, analytics, auth, health, ml, reports, stubs
    from src.cli import register_cli

    for module in (health, auth, admin, analytics, ml, reports, stubs):
        app.register_blueprint(module.bp)
    register_error_handlers(app)
    register_cli(app)
    return app


if __name__ == "__main__":
    create_app().run(host=settings.FLASK_HOST, port=settings.FLASK_PORT)
