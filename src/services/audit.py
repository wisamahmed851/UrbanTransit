"""Write audit_log entries (who did what, to which entity, with which details)."""

from flask_jwt_extended import current_user

from src.extensions import db
from src.models.ops import AuditLog


def record(action: str, entity: str | None = None, details: dict | None = None,
           actor: str | None = None, commit: bool = False) -> AuditLog:
    """Add an audit entry to the current session.

    By default it commits together with the caller's change, so the change and its audit
    row are saved or rolled back as one unit. Pass `commit=True` for events with no
    other write (e.g. a failed login).
    """
    if actor is None:
        try:
            actor = current_user.username if current_user else "anonymous"
        except RuntimeError:          # no verified JWT in this request
            actor = "anonymous"
    entry = AuditLog(actor=actor, action=action, entity=entity, details_json=details)
    db.session.add(entry)
    if commit:
        db.session.commit()
    return entry
