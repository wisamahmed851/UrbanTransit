"""Phase 6 model evidence (read-only). Metrics are shown for transparency, not endorsement.

GET /api/models/metrics    flattened metric rows; filters: task, algorithm, split_type,
                           metric_name, source_file, validity_flag
GET /api/models/clusters   the 4 K-Means (k=4) cluster profiles

Every `delay_severity` row has validity_flag = INVALID: those models use `occupancy_pct`
(a same-trip outcome) as an input, so their scores overstate what a model could do before
departure. They must not back predictions until retrained without it. The response lists
this under `warnings` whenever such rows are included.
"""

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from src.extensions import db
from src.models.ml import ClusterProfile, ModelMetric
from src.security import permission_required

bp = Blueprint("ml", __name__, url_prefix="/api/models")

METRIC_FILTERS = ("task", "algorithm", "split_type", "metric_name", "source_file", "validity_flag")


@bp.get("/metrics")
@permission_required("models:read")
def metrics():
    query = select(ModelMetric).order_by(ModelMetric.source_file, ModelMetric.id)
    for param in METRIC_FILTERS:
        if request.args.get(param):
            query = query.where(getattr(ModelMetric, param) == request.args[param])
    rows = db.session.execute(query).scalars().all()
    invalid = sorted({(r.task, r.validity_note) for r in rows if r.validity_flag == "INVALID"})
    return jsonify(
        total=len(rows),
        warnings=[{"task": task, "validity_flag": "INVALID",
                   "message": f"{task} metrics do not reflect a valid model: {note}."} for task, note in invalid],
        rows=[r.to_dict() for r in rows],
        source="models/spark/metrics/*.json (Phase 6), flattened by database/metrics_normaliser.py",
    )


@bp.get("/clusters")
@permission_required("models:read")
def clusters():
    rows = db.session.execute(select(ClusterProfile).order_by(ClusterProfile.prediction)).scalars().all()
    return jsonify(
        algorithm="kmeans",
        k=len(rows),
        clusters=[r.to_dict() for r in rows],
        notes=[
            "`prediction` is the cluster id; values are mean train-period route features per cluster.",
            "No route-to-cluster assignment has been produced yet, so this endpoint cannot say which routes are in a cluster.",
        ],
        source="reports/phase6_cluster_profiles.csv (Phase 6)",
    )
