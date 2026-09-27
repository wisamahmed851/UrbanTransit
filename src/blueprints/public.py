"""Public, unauthenticated figures for the website's landing page (CMD-026).

GET /api/public/summary   network size, service window, route classes, recommendations,
                          served-model accuracy and pipeline agreement

Only network-level totals and model scores, all read from the loaded tables: no passenger,
card, user or trip-level data. Cached for 10 minutes. Laravel analogy: a public route
outside the `auth` middleware group.
"""

import time
from collections import Counter

from flask import Blueprint, jsonify
from sqlalchemy import func, select

from src.extensions import db
from src.models.analytics import ANALYTICS_TABLES
from src.models.ops import ModelVersion
from src.models.reference import Route, Stop, Vehicle
from src.models.serving import PipelineComparison, Recommendation

bp = Blueprint("public", __name__, url_prefix="/api/public")

_cache: dict = {}
TTL_SECONDS = 600


def _count(model) -> int:
    return db.session.execute(select(func.count()).select_from(model)).scalar_one()


def _summary() -> dict:
    days = ANALYTICS_TABLES["eda_peak_days"]
    first, last, avg = db.session.execute(select(
        func.min(days.c.service_date), func.max(days.c.service_date), func.avg(days.c.est_system_boardings))).one()
    perf = ANALYTICS_TABLES["route_performance"]
    classes = dict(db.session.execute(select(perf.c.route_class, func.count()).group_by(perf.c.route_class)).all())
    priorities = Counter(p for (p,) in db.session.execute(select(Recommendation.priority)).all())
    matches = db.session.execute(select(PipelineComparison.match)).scalars().all()
    models = []
    for v in db.session.execute(select(ModelVersion).filter_by(is_active=True).order_by(ModelVersion.task)).scalars():
        test = (v.metrics_json or {}).get("test") or {}
        models.append({"task": v.task, "algorithm": v.algorithm,
                       "accuracy": test.get("accuracy"), "macro_f1": test.get("macro_f1"), "mae": test.get("mae"),
                       "r2": test.get("r2")})
    return {
        "network": {"routes": _count(Route), "stops": _count(Stop), "vehicles": _count(Vehicle)},
        "service": {"first_day": first.isoformat() if first else None, "last_day": last.isoformat() if last else None,
                    "avg_daily_boardings": round(float(avg)) if avg is not None else None},
        "route_classes": {k: v for k, v in classes.items() if k},
        "recommendations": {"total": sum(priorities.values()), "by_priority": dict(priorities)},
        "pipeline_agreement": round(sum(matches) / len(matches), 4) if matches else None,
        "comparison_cases": len(matches),
        "models": models,
        "source": "UrbanTransit IQ analytics tables (network-level totals only)",
    }


@bp.get("/summary")
def summary():
    hit = _cache.get("summary")
    if not hit or time.monotonic() - hit[0] > TTL_SECONDS:
        hit = (time.monotonic(), _summary())
        _cache["summary"] = hit
    return jsonify(hit[1])
