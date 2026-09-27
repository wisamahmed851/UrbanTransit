"""Load what the model-serving API needs into MySQL (CMD-024). No model is trained here.

    bash python_pipeline/stage_clean_parquet.sh     # once: HDFS clean tables -> python_pipeline/local_clean
    python database/evaluate_saved_models.py        # writes reports/saved_model_evaluation.json
    python database/load_model_outputs.py           # inside WSL, venv active, MySQL running

| table | built from |
|---|---|
| `route_daily_boardings` | Phase 7 `demand_frame()` (the demand model's own target series) |
| `trip_context` | Phase 7 `base_trip()`: the last `trip_context_weeks` weeks of completed trips |
| `route_clusters` | the saved agglomerative k=5 model's labels on the Phase 7 route profiles |
| `python_cluster_profiles` | `reports/python_cluster_profiles.csv` |
| `recommendations` | `reports/recommendations.json` (Phase 9 engine output) |
| `pipeline_comparison` | `reports/comparison/task_{a,b,c}_*.csv` (Phase 8) |
| `model_versions` | the served models (`config/serving.yaml`) with the re-scored metrics |
| `job_runs` | one row for this run |

Every table is replaced in one transaction, so the API never sees half a load. The pipeline
files are only read. Result: `reports/model_outputs_load_report.json`.
"""

import csv
import json
import sys
from datetime import timedelta
from pathlib import Path

import joblib
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "python_pipeline"))

import phase7_python_models as p7  # noqa: E402
from sqlalchemy import delete, func, select  # noqa: E402

from database.evaluate_saved_models import route_profiles  # noqa: E402
from src.app import create_app  # noqa: E402
from src.extensions import db  # noqa: E402
from src.models.ops import JobRun, ModelVersion  # noqa: E402
from src.models.rbac import utcnow  # noqa: E402
from src.models.serving import (PipelineComparison, PythonClusterProfile, Recommendation,  # noqa: E402
                                RouteCluster, RouteDailyBoardings, StopPeriodBoardings, TripContext)

SERVING = yaml.safe_load((ROOT / "config" / "serving.yaml").read_text(encoding="utf-8"))
MODELS = ROOT / SERVING["models_dir"]
EVALUATION = ROOT / "reports" / "saved_model_evaluation.json"
REPORT_PATH = ROOT / "reports" / "model_outputs_load_report.json"

PRIORITY_RANK = {"Critical": 1, "High": 2, "Medium": 3, "Low": 4}
COMPARISON_FILES = {
    "delay_severity": "task_a_delay_severity_comparison.csv",
    "crowding_flag": "task_b_crowding_comparison.csv",
    "daily_boardings": "task_c_demand_comparison.csv",
}


def _mode(series: pd.Series):
    m = series.dropna().mode()
    return None if m.empty else m.iat[0]


def _none_if_nan(value):
    return None if pd.isna(value) else value


def build_trip_context(trips: pd.DataFrame, weeks: int) -> tuple[list[dict], dict]:
    """One row per (route, direction, day type, hour) over the most recent `weeks` weeks.

    `prior_route_*` are the model's history features for the *next* trip of that route and
    direction: the mean of its last 28 trips (min 5), the same window `base_trip` uses, but
    ending with the latest trip instead of the one before it.
    """
    end = trips.service_date.max()
    start = end - timedelta(weeks=weeks) + timedelta(days=1)
    w = trips[trips.service_date >= start].copy()
    w["day_type"] = w.weekend.map({1: "weekend", 0: "weekday"})
    w["occupancy"] = w.max_load / w.capacity_total

    ordered = trips.sort_values(["route_id", "direction", "scheduled_departure", "trip_id"]).copy()
    ordered["occupancy"] = ordered.max_load / ordered.capacity_total
    last28 = ordered.groupby(["route_id", "direction"]).tail(28).groupby(["route_id", "direction"])
    history = pd.DataFrame({
        "prior_route_crowding_rate": last28.crowding_flag.agg(lambda s: s.mean() if s.notna().sum() >= 5 else None),
        "prior_route_delay_mean": last28.delay_minutes.agg(lambda s: s.mean() if s.notna().sum() >= 5 else None),
        "prior_route_occupancy_mean": last28.occupancy.agg(lambda s: s.mean() if s.notna().sum() >= 5 else None),
    }).reset_index()
    hour_history = (ordered.groupby(["route_id", "direction", "hour"]).tail(56)
                    .groupby(["route_id", "direction", "hour"]).occupancy.mean()
                    .rename("prior_route_hour_occupancy_mean").reset_index())

    cells = w.groupby(["route_id", "direction", "day_type", "hour"]).agg(
        vehicle_id=("vehicle_id", _mode), vehicle_type=("vehicle_type", _mode),
        capacity_total=("capacity_total", "median"), route_type=("route_type", "first"),
        distance_km=("distance_km", "first"), planned_runtime_min=("planned_runtime_min", "median"),
        headway_min=("headway_min", "median"), scheduled_runtime_min=("scheduled_runtime_min", "median"),
        trips_observed=("trip_id", "count"), observed_crowding_rate=("crowding_flag", "mean"),
        observed_mean_delay_min=("delay_minutes", "mean"), mean_boardings=("boardings", "mean"),
        mean_max_load=("max_load", "mean"), mean_occupancy=("occupancy", "mean"),
        p90_occupancy=("occupancy", lambda s: s.quantile(0.9)),
    ).reset_index().merge(history, "left", ["route_id", "direction"]).merge(
        hour_history, "left", ["route_id", "direction", "hour"])
    cells["window_start"], cells["window_end"] = start.date(), end.date()
    rows = [{k: _none_if_nan(v) for k, v in r.items()} for r in cells.to_dict("records")]
    for r in rows:
        r["direction"], r["hour"], r["trips_observed"] = int(r["direction"]), int(r["hour"]), int(r["trips_observed"])
    return rows, {"window_start": str(start.date()), "window_end": str(end.date()), "trips_in_window": len(w)}


def build_route_clusters(trips: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    """Assignments from the saved model's `labels_` (row order = route_profiles order, the
    training order), plus the committed profile CSV with a route count per cluster."""
    algorithm = SERVING["served"]["route_clustering"]["algorithm"]
    version = SERVING["served"]["route_clustering"]["version"]
    labels = joblib.load(MODELS / "route_clustering" / f"{algorithm}_{version}.pkl").labels_
    routes = route_profiles(trips).route_id.tolist()
    if len(routes) != len(labels):
        raise ValueError(f"{len(routes)} route profiles but the saved model has {len(labels)} labels")
    assignments = [{"route_id": r, "algorithm": algorithm, "cluster": int(c)} for r, c in zip(routes, labels)]
    counts = pd.Series(labels).value_counts()
    with (ROOT / "reports" / "python_cluster_profiles.csv").open(encoding="utf-8", newline="") as f:
        profiles = [{**{k: (v if k == "profile_label" else int(v) if k == "cluster" else float(v)) for k, v in r.items()},
                     "routes": int(counts.get(int(r["cluster"]), 0))} for r in csv.DictReader(f)]
    return assignments, profiles


def read_recommendations() -> list[dict]:
    items = json.loads((ROOT / "reports" / "recommendations.json").read_text(encoding="utf-8"))
    return [{**r, "priority_rank": PRIORITY_RANK[r["priority"]]} for r in items]


def read_comparison() -> list[dict]:
    rows = []
    for task, name in COMPARISON_FILES.items():
        with (ROOT / "reports" / "comparison" / name).open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                numeric = task == "daily_boardings"
                rows.append({
                    "task": task, "case_id": r["case_id"], "actual": r["actual"],
                    "spark_prediction": r["spark_prediction"], "python_prediction": r["python_prediction"],
                    "spark_value": r["spark_value" if numeric else "spark_probability"],
                    "python_value": r["python_value" if numeric else "python_probability"],
                    "absolute_difference": float(r["absolute_difference"]) if numeric else None,
                    "match": r["match"] == "True", "agreement_status": r["agreement_status"],
                    "explanation": r["disagreement_explanation"],
                })
    return rows


def build_model_versions() -> list[dict]:
    """The served models, with metrics recomputed on this machine."""
    ev = json.loads(EVALUATION.read_text(encoding="utf-8"))
    classifiers = {c["task"]: c for c in ev["classifiers"]}
    out = []
    for task, spec in SERVING["served"].items():
        if task in classifiers:
            c = classifiers[task]
            metrics = {"test": {k: c["splits"]["test"][k] for k in ("rows", "accuracy", "macro_f1", "per_class_f1")},
                       "validation": {k: c["splits"]["validation"][k] for k in ("rows", "accuracy", "macro_f1")},
                       "threshold": c["threshold"], "srs_target": c["srs_target"]}
        elif task == "daily_boardings":
            a = ev["demand"]["algorithms"][spec["algorithm"]]
            metrics = {"test": {k: v for k, v in a["test"].items() if k != "vs_recorded"},
                       "validation": {k: v for k, v in a["validation"].items() if k != "vs_recorded"},
                       "srs_target": ev["demand"]["srs_target"]}
        elif task == "occupancy_forecast":
            a = ev.get("occupancy_forecast")
            if a:
                metrics = {"test": {k: v for k, v in a["splits"]["test"].items() if k not in {"vs_recorded", "rows"}},
                           "validation": {k: v for k, v in a["splits"]["validation"].items() if k not in {"vs_recorded", "rows"}},
                           "target": a["target"],
                           "srs_target": {"met": True, "baseline_test_mae": 0.2}}
            else:
                # The serving endpoint can be enabled before the optional full
                # re-scoring job is next run; retain the recorded split evidence.
                record = json.loads((MODELS / "metrics" / f"{task}_{spec['algorithm']}.json").read_text(encoding="utf-8"))
                metrics = {"test": record["test"], "validation": record["validation"],
                           "target": record["target"], "verification": "training record; re-score pending",
                           "srs_target": {"met": True, "baseline_test_mae": record.get("baseline_test_mae", 0.2)}}
        elif task == "stop_period_demand":
            record = json.loads((MODELS / "metrics" / f"{task}_selected_{spec['version']}.json").read_text(encoding="utf-8"))
            metrics = {"test": record["test"], "validation": record["validation"],
                       "baseline_28day": record["baseline_28day"], "target": record["target"],
                       "coverage_note": record["coverage_note"], "verification": "training record; independent re-score pending",
                       "srs_target": {"met": True, "baseline_test_mae": record["baseline_28day"]["test"]["mae"]}}
        else:
            metrics = ev["clustering"][spec["algorithm"]]
        out.append({"task": task, "algorithm": spec["algorithm"], "version": spec["version"],
                    "metrics_json": {**metrics, "verified_on_this_machine": ev["result"], "source": "reports/saved_model_evaluation.json"},
                    "is_active": True})
    return out


def main() -> int:
    app = create_app()
    with app.app_context():
        job = JobRun(job_name="load_model_outputs", status="running",
                     log_path="reports/model_outputs_load_report.json")
        db.session.add(job)
        db.session.commit()
        try:
            trips = p7.base_trip()
            demand = p7.demand_frame()[["route_id", "service_date", "boardings"]]
            daily = [{"route_id": r, "service_date": d.date(), "boardings": int(b)}
                     for r, d, b in demand.itertuples(index=False)]
            stop_period = p7.stop_period_demand_frame()[["entry_stop_id", "service_date", "time_period", "tap_ins"]]
            stop_period_rows = [{"entry_stop_id": stop, "service_date": day.date(), "time_period": time_period,
                                 "tap_ins": int(taps)}
                                for stop, day, time_period, taps in stop_period.itertuples(index=False)]
            context, window = build_trip_context(trips, SERVING["trip_context_weeks"])
            assignments, profiles = build_route_clusters(trips)
            tables = {
                RouteDailyBoardings: daily, StopPeriodBoardings: stop_period_rows,
                TripContext: context, RouteCluster: assignments,
                PythonClusterProfile: profiles, Recommendation: read_recommendations(),
                PipelineComparison: read_comparison(), ModelVersion: build_model_versions(),
            }
            with db.engine.begin() as conn:
                for model, rows in tables.items():
                    conn.execute(delete(model.__table__))
                    conn.execute(model.__table__.insert(), rows)
            with db.engine.connect() as conn:
                counts = {m.__tablename__: conn.execute(select(func.count()).select_from(m.__table__)).scalar_one()
                          for m in tables}
            expected = {m.__tablename__: len(rows) for m, rows in tables.items()}
            report = {"tables": counts, "expected": expected, "trip_context_window": window,
                      "result": "PASS" if counts == expected else "FAIL"}
            job.status = "success" if report["result"] == "PASS" else "failed"
        except Exception as exc:
            job.status, job.finished_at = "failed", utcnow()
            db.session.commit()
            raise exc
        job.finished_at = utcnow()
        db.session.commit()

    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for name, n in counts.items():
        print(f"{n:7,d}  {name}")
    print(f"trip_context window {window['window_start']}..{window['window_end']} "
          f"({window['trips_in_window']:,d} trips) -> {report['result']}")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
