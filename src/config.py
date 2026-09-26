"""Flask configuration classes.

All values come from `config/settings.py` (which reads `.env`), so nothing is defined
twice. Laravel analogy: `config/*.php` reading `env()`; NestJS: `ConfigModule`.
"""

from datetime import timedelta

from sqlalchemy.engine import URL

from config import settings


def mysql_url() -> URL:
    """SQLAlchemy URL for MySQL. `URL.create` escapes special characters in the password."""
    return URL.create(
        "mysql+pymysql",
        username=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        database=settings.MYSQL_DATABASE,
        query={"charset": "utf8mb4"},
    )


class BaseConfig:
    """Settings shared by every environment."""

    SECRET_KEY = settings.SECRET_KEY
    JWT_SECRET_KEY = settings.JWT_SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=settings.JWT_ACCESS_TOKEN_MINUTES)
    SQLALCHEMY_DATABASE_URI = mysql_url()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 3600}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = settings.CORS_ORIGINS
    JSON_SORT_KEYS = False
    # Page size limits for JSON list endpoints (CSV export streams everything).
    API_DEFAULT_LIMIT = 100
    API_MAX_LIMIT = 1000


class TestingConfig(BaseConfig):
    """In-memory SQLite so the test suite never touches the real MySQL data."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    SECRET_KEY = "test-secret"
    JWT_SECRET_KEY = "test-jwt-secret-with-at-least-32-bytes!"
