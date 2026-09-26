"""All database models. Importing this package registers every table on `db.metadata`,
which is what Flask-Migrate compares against MySQL when generating a migration."""

from src.models.analytics import ANALYTICS_SCHEMAS, ANALYTICS_TABLES  # noqa: F401
from src.models.ml import ClusterProfile, ModelMetric  # noqa: F401
from src.models.network import GpsEvent, RouteStop  # noqa: F401
from src.models.ops import AuditLog, JobRun, ModelVersion  # noqa: F401
from src.models.rbac import Permission, Role, User  # noqa: F401
from src.models.reference import REFERENCE_MODELS, Route, Stop, Vehicle  # noqa: F401
