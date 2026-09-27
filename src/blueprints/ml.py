"""Model evidence (read-only): Spark and Python.

GET /api/models/metrics     flattened metric rows; filters: pipeline, task, algorithm,
                 split_type, metric_name, source_file, validity_flag
GET /api/models/clusters     the 4 Spark K-Means (k=4) cluster profiles
GET /api/models/clusters/python the 5 Python clusters with their routes (served model)
GET /api/models/versions     the model registry: which saved models the API serves
GET /api/models/evaluation    the re-scoring of the saved Python models on this server

Every Spark `delay_severity` row has validity_flag = INVALID: those models use `occupancy_pct`
(a same-trip outcome) as an input, so their scores overstate what a model could do before
departure. They must not back predictions until retrained without it. The response lists
this under `warnings` whenever such rows are included.
"""

import json

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from config import settings
from src.errors import ApiError
from src.extensions import db
from src.models.ml import ClusterProfile, ModelMetric
from src.models.ops import ModelVersion
from src.models.serving import PythonClusterProfile, RouteCluster
from src.security import permission_required

bp = Blueprint("ml", __name__, url_prefix="/api/models")

METRIC_FILTERS = ("pipeline", "task", "algorithm", "split_type", "metric_name", "source_file", "validity_flag")


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
    source="models/spark/metrics/*.json and models/python/metrics/*.json , "
        "flattened by database/metrics_normaliser.py",
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
    source="reports/phase6_cluster_profiles.csv ",
  )


@bp.get("/clusters/python")
@permission_required("models:read")
def python_clusters():
  profiles = db.session.execute(select(PythonClusterProfile).order_by(PythonClusterProfile.cluster)).scalars().all()
  members = db.session.execute(select(RouteCluster).order_by(RouteCluster.route_id)).scalars().all()
  return jsonify(
    algorithm=members[0].algorithm if members else None, k=len(profiles),
    clusters=[{**p.to_dict(), "route_ids": [m.route_id for m in members if m.cluster == p.cluster]} for p in profiles],
    notes=["Values are mean train-period route features per cluster (occupancy as a share of capacity).",
        "Routes are assigned by the saved model's own labels, not re-clustered by the API."],
    source="models/python/route_clustering and reports/python_cluster_profiles.csv",
  )


@bp.get("/versions")
@permission_required("models:read")
def versions():
  rows = db.session.execute(select(ModelVersion).order_by(ModelVersion.task)).scalars().all()
  return jsonify(rows=[{"task": r.task, "algorithm": r.algorithm, "version": r.version, "is_active": r.is_active,
             "registered_at": r.registered_at.isoformat(), "metrics": r.metrics_json} for r in rows])


@bp.get("/evaluation")
@permission_required("models:read")
def evaluation():
  path = settings.REPORTS_DIR / "saved_model_evaluation.json"
  if not path.exists():
    raise ApiError(404, "not_found", "No evaluation yet: run python database/evaluate_saved_models.py.")
  return jsonify(json.loads(path.read_text(encoding="utf-8")))
