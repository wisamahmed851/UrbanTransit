"""UrbanTransit IQ Flask application (Phase 0: health check only)."""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, jsonify  # noqa: E402

from config import settings  # noqa: E402


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.SECRET_KEY

    @app.get("/health")
    def health():
        return jsonify(
            status="ok",
            service="UrbanTransit IQ",
            time=datetime.now(timezone.utc).isoformat(),
        )

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host=settings.FLASK_HOST, port=settings.FLASK_PORT)
