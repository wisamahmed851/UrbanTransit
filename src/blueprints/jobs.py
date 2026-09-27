"""Read-only operational job monitoring.

Kept outside the generic ``/api/admin/<entity>`` reference-data routes so job
history can never be mistaken for an editable reference entity.
"""

from flask import Blueprint, jsonify, request
from sqlalchemy import func, select

from src.extensions import db
from src.models.ops import JobRun
from src.security import permission_required
from src.services.requests import int_arg

bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")


@bp.get("")
@permission_required("audit:read")
def job_runs():
    """Recent tracked Spark and loader jobs, newest first."""
    status = request.args.get("status")
    query = select(JobRun).order_by(JobRun.id.desc())
    if status:
        query = query.where(JobRun.status == status)
    limit, offset = int_arg("limit", 100, 1, 1000), int_arg("offset", 0, 0)
    total = db.session.execute(select(func.count()).select_from(query.order_by(None).subquery())).scalar_one()
    rows = db.session.execute(query.limit(limit).offset(offset)).scalars()
    return jsonify(entries=[row.to_dict() for row in rows], total=total, limit=limit, offset=offset)

import os

@bp.get("/<int:job_id>/log")
@permission_required("audit:read")
def job_log(job_id: int):
    """Get the last 100 lines of a job's log file."""
    job = db.session.get(JobRun, job_id)
    if not job or not job.log_path or not os.path.exists(job.log_path):
        return jsonify(log="No log available.")
    try:
        with open(job.log_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            return jsonify(log="".join(lines[-100:]))
    except Exception as e:
        return jsonify(log=str(e))
