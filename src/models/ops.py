"""Operational metadata: audit trail, model registry and job runs.

`model_versions` and `job_runs` are created empty on purpose. No Phase 6 model has been
chosen for serving yet, and no job writes to `job_runs` yet; see
documentation/backend_api.md.
"""

from src.extensions import db
from src.models.rbac import utcnow


class AuditLog(db.Model):
    """Who did what, to which entity, when. Written by `src.services.audit.record`."""

    __tablename__ = "audit_log"

    id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True)
    actor = db.Column(db.String(64), nullable=False)      # username, or "anonymous" for failed logins
    action = db.Column(db.String(64), nullable=False)     # e.g. "auth.login", "routes.update"
    entity = db.Column(db.String(128))                    # e.g. "routes/R001"
    timestamp = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    details_json = db.Column(db.JSON)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "actor": self.actor,
            "action": self.action,
            "entity": self.entity,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details_json,
        }


class ModelVersion(db.Model):
    """Registry of models approved for serving. Empty until a valid model is registered."""

    __tablename__ = "model_versions"

    id = db.Column(db.Integer, primary_key=True)
    task = db.Column(db.String(64), nullable=False)
    algorithm = db.Column(db.String(128), nullable=False)
    version = db.Column(db.String(32), nullable=False)
    metrics_json = db.Column(db.JSON)
    is_active = db.Column(db.Boolean, nullable=False, default=False)
    registered_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (db.UniqueConstraint("task", "algorithm", "version"),)


class JobRun(db.Model):
    """History of pipeline/loader runs. Empty until a job is wired to record itself."""

    __tablename__ = "job_runs"

    id = db.Column(db.Integer, primary_key=True)
    job_name = db.Column(db.String(128), nullable=False)
    status = db.Column(db.String(32), nullable=False)    # running | success | failed
    started_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    finished_at = db.Column(db.DateTime)
    log_path = db.Column(db.String(512))
