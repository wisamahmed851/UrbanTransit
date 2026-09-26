"""Forecasts, recommendations and the Spark-vs-Python comparison (CMD-024).

GET /api/forecasts/demand?route_id=R001&horizon=14&history=90   one route: history, backtest, forecast
GET /api/forecasts/demand/network?horizon=14                    all routes: daily total and growth by route
GET /api/recommendations?category=&priority=&subject_id=&q=     Phase 9 recommendations, most urgent first
GET /api/comparison                                             Phase 8 agreement summary per task
GET /api/comparison/<task>?agreement_status=&match=             the compared cases of one task

Recommendations and comparison cases are the pipeline's own outputs, loaded into MySQL by
database/load_model_outputs.py; the API does not alter them. Agreement rates are counted
from the loaded cases, not copied from the report text.
"""

from collections import Counter

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_, select

from src.errors import ApiError
from src.extensions import db
from src.models.serving import PipelineComparison, Recommendation
from src.security import permission_required
from src.services import forecasting
from src.services.model_serving import serving_config
from src.services.requests import int_arg

bp = Blueprint("insights", __name__, url_prefix="/api")

COMPARISON_TASKS = {
    "delay_severity": {
        "title": "Delay severity (task A)",
        "caveat": "The Spark side is the Phase 6 delay model flagged INVALID (occupancy_pct, a same-trip outcome, "
                  "is one of its inputs), so its higher agreement with the actual label is not a fair comparison.",
    },
    "crowding_flag": {
        "title": "Crowding flag (task B)",
        "caveat": "Python predicts with its tuned 0.70 threshold, Spark with 0.50; part of the disagreement is that choice.",
    },
    "daily_boardings": {
        "title": "Daily boardings (task C)",
        "caveat": "A case matches when both predictions are within 10% of the actual value. The actual value in "
                  "this file is the Spark target; the Python model was trained on raw APC boardings, which can differ.",
    },
}


def horizon_arg() -> int:
    cfg = serving_config()["forecast"]
    return int_arg("horizon", cfg["default_horizon_days"], 1, cfg["max_horizon_days"])


@bp.get("/forecasts/demand")
@permission_required("analytics:read")
def demand_forecast():
    route_id = (request.args.get("route_id") or "").strip().upper()
    if not route_id:
        raise ApiError(400, "missing_fields", "'route_id' is required.", {"missing": ["route_id"]})
    history = int_arg("history", serving_config()["forecast"]["default_history_days"], 7, 365)
    return jsonify(forecasting.route_forecast(route_id, horizon_arg(), history))


@bp.get("/forecasts/demand/network")
@permission_required("analytics:read")
def network_forecast():
    return jsonify(forecasting.network_forecast(horizon_arg()))


@bp.get("/recommendations")
@permission_required("recommendations:read")
def recommendations():
    query = select(Recommendation)
    for field in ("category", "priority", "subject_id"):
        if request.args.get(field):
            query = query.where(getattr(Recommendation, field) == request.args[field].strip())
    if request.args.get("q"):
        like = f"%{request.args['q'].strip()}%"
        query = query.where(or_(Recommendation.action.like(like), Recommendation.evidence.like(like),
                                Recommendation.subject_id.like(like)))
    total = db.session.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    limit, offset = int_arg("limit", 50, 1, 500), int_arg("offset", 0)
    rows = db.session.execute(query.order_by(Recommendation.priority_rank, Recommendation.recommendation_id)
                              .limit(limit).offset(offset)).scalars().all()
    everything = db.session.execute(select(Recommendation.priority, Recommendation.category)).all()
    return jsonify(
        total=total, limit=limit, offset=offset, rows=[r.to_dict() for r in rows],
        summary={"total": len(everything), "by_priority": dict(Counter(p for p, _ in everything)),
                 "by_category": dict(Counter(c for _, c in everything))},
        source="reports/recommendations.json (Phase 9 rule-based engine, rules in config/thresholds.yaml)",
    )


def task_summary(task: str, rows: list[PipelineComparison]) -> dict:
    status = Counter(r.agreement_status for r in rows)
    n = len(rows)
    return {
        "task": task, **COMPARISON_TASKS[task], "cases": n,
        "agreement_rate": round(sum(r.match for r in rows) / n, 4) if n else None,
        "spark_correct_rate": round((status["BothCorrect"] + status["SparkOnlyCorrect"]) / n, 4) if n else None,
        "python_correct_rate": round((status["BothCorrect"] + status["PyOnlyCorrect"]) / n, 4) if n else None,
        "by_status": dict(status),
    }


@bp.get("/comparison")
@permission_required("models:read")
def comparison():
    rows = db.session.execute(select(PipelineComparison)).scalars().all()
    tasks = [task_summary(t, [r for r in rows if r.task == t]) for t in COMPARISON_TASKS]
    n = sum(t["cases"] for t in tasks)
    overall = round(sum(t["agreement_rate"] * t["cases"] for t in tasks if t["cases"]) / n, 4) if n else None
    return jsonify(tasks=tasks, cases=n, overall_agreement_rate=overall,
                   source="reports/comparison/task_*.csv (Phase 8); rates counted from the loaded cases")


@bp.get("/comparison/<task>")
@permission_required("models:read")
def comparison_cases(task: str):
    if task not in COMPARISON_TASKS:
        raise ApiError(404, "not_found", f"Unknown comparison task '{task}'.", {"tasks": list(COMPARISON_TASKS)})
    query = select(PipelineComparison).filter_by(task=task)
    if request.args.get("agreement_status"):
        query = query.filter_by(agreement_status=request.args["agreement_status"])
    if request.args.get("match") in ("true", "false"):
        query = query.filter_by(match=request.args["match"] == "true")
    total = db.session.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    limit, offset = int_arg("limit", 100, 1, 1000), int_arg("offset", 0)
    rows = db.session.execute(query.order_by(PipelineComparison.id).limit(limit).offset(offset)).scalars().all()
    return jsonify(task=task, total=total, limit=limit, offset=offset, rows=[r.to_dict() for r in rows])
