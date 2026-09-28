"""Serve the saved Phase 7 (Python) classifiers: crowding risk and delay severity (CMD-024).

The models were trained by `python_pipeline/phase7_python_models.py` and are loaded from
`models/python/<task>/<algorithm>_v1.pkl` with their fitted preprocessor. Nothing is
retrained here and no prediction is made up: every number in a response comes from
`model.predict_proba` on a feature row built the way Phase 7 built its training rows.

A request names only a route, direction, date and hour. The other inputs the model was
trained on (headway, planned runtime, the vehicle usually assigned, the route's recent
crowding or delay history) are read from `trip_context`, the typical trip for that
route/direction/day type/hour over the last weeks of data (`database/load_model_outputs.py`).
The response lists every input, so a reviewer can see exactly what the model was given.

Laravel analogy: a service class the controller calls; the loaded models are cached like a
singleton in the container (`load_once`: once per worker process, also under concurrent calls).
"""

import json
from datetime import date
import threading
from functools import cache, wraps
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
from sqlalchemy import select

from config import settings
from src.errors import ApiError
from src.extensions import db
from src.models.ops import ModelVersion
from src.models.reference import Vehicle
from src.models.serving import TripContext

SERVING_FILE = settings.PROJECT_ROOT / "config" / "serving.yaml"

# What the crowding label means in Phase 7 (`base_trip`): the trip's highest load above 90% of
# the vehicle's total capacity.
CROWDING_MEANING = "crowded = the trip's highest on-board load exceeds 90% of the vehicle's total capacity"


@cache
def serving_config() -> dict:
    return yaml.safe_load(SERVING_FILE.read_text(encoding="utf-8"))


def models_dir() -> Path:
    return settings.PROJECT_ROOT / serving_config()["models_dir"]


def load_once(fn):
    """Cache a model loader, and make concurrent callers wait for a load already in progress.

    `functools.cache` alone lets two threads miss the cache together: the startup warm-up and
    the first request each unpickled their own copy (the 622 MB occupancy forest twice, on an
    8 GB machine). Failed loads are not cached, so a missing file is reported on every call.
    """
    lock, results = threading.Lock(), {}

    @wraps(fn)
    def wrapper(*args):
        if args in results:
            return results[args]
        with lock:
            if args not in results:
                results[args] = fn(*args)
        return results[args]

    wrapper.cache_clear = results.clear
    return wrapper


@load_once
def load_classifier(task: str) -> dict:
    """The served model for `task`, its preprocessor and its recorded training metadata."""
    spec = serving_config()["served"][task]
    folder, name = models_dir() / task, f"{spec['algorithm']}_{spec['version']}"
    model_file, prep_file = folder / f"{name}.pkl", folder / f"{spec['algorithm']}_preprocessor_{spec['version']}.pkl"
    record_file = models_dir() / "metrics" / f"{task}_{spec['algorithm']}.json"
    missing = [str(p.relative_to(settings.PROJECT_ROOT)) for p in (model_file, prep_file, record_file) if not p.exists()]
    if missing:
        raise ApiError(503, "model_unavailable",
                       "The saved model files are not on this server. Unzip the shared models.zip into models/.",
                       {"missing": missing})
    record = json.loads(record_file.read_text(encoding="utf-8"))
    model = joblib.load(model_file)
    if hasattr(model, "n_jobs"):
        model.n_jobs = 1          # saved with n_jobs=-1; a thread pool per small request only costs time
    return {
        "task": task, "algorithm": spec["algorithm"], "version": spec["version"],
        "file": str(model_file.relative_to(settings.PROJECT_ROOT)),
        "model": model, "preprocessor": joblib.load(prep_file),
        "numeric": record["features"]["numeric"], "categorical": record["features"]["categorical"],
        "labels": record["test"]["confusion_matrix"]["labels"],   # sorted class names, the order of predict_proba
        "threshold": record.get("threshold"),
        "recorded_test": {k: record["test"][k] for k in ("accuracy", "macro_f1", "per_class_f1")},
    }


@load_once
def load_regressor(task: str) -> dict:
    """Load a numeric Phase 7 predictor and its fitted feature preprocessor."""
    spec = serving_config()["served"][task]
    folder, name = models_dir() / task, f"{spec['algorithm']}_{spec['version']}"
    model_file, prep_file = folder / f"{name}.pkl", folder / f"{spec['algorithm']}_preprocessor_{spec['version']}.pkl"
    record_file = models_dir() / "metrics" / f"{task}_{spec['algorithm']}.json"
    missing = [str(p.relative_to(settings.PROJECT_ROOT)) for p in (model_file, prep_file, record_file) if not p.exists()]
    if missing:
        raise ApiError(503, "model_unavailable",
                       "The saved model files are not on this server. Train the occupancy forecast or unzip the shared models.zip into models/.",
                       {"missing": missing})
    record = json.loads(record_file.read_text(encoding="utf-8"))
    model = joblib.load(model_file)
    if hasattr(model, "n_jobs"):
        model.n_jobs = 1
    return {
        "task": task, "algorithm": spec["algorithm"], "version": spec["version"],
        "file": str(model_file.relative_to(settings.PROJECT_ROOT)), "model": model,
        "preprocessor": joblib.load(prep_file), "numeric": record["features"]["numeric"],
        "categorical": record["features"]["categorical"], "recorded_test": record["test"],
        "target": record.get("target"), "target_definition": record.get("target_definition"),
    }


def model_card(task: str) -> dict:
    """Name, version and test metrics of the served model, plus whether it meets the SRS target.

    Metrics come from `model_versions` (re-scored on this machine by
    `database/evaluate_saved_models.py`), or from the training record if the registry is empty.
    """
    m = load_classifier(task)
    targets = serving_config()["srs_targets"]
    row = db.session.execute(select(ModelVersion).filter_by(task=task, algorithm=m["algorithm"], version=m["version"])).scalar_one_or_none()
    test = (row.metrics_json or {}).get("test") if row else None
    test = test or m["recorded_test"]
    return {
        "task": task, "algorithm": m["algorithm"], "version": m["version"], "file": m["file"],
        "pipeline": "python (Phase 7)", "trained_on": "2025-09-01..2026-05-01, chronological split",
        "test_accuracy": test["accuracy"], "test_macro_f1": test["macro_f1"],
        "test_within_one_band_accuracy": test.get("within_one_band_accuracy"),
        "metrics_source": "model_versions (re-score report: reports/saved_model_evaluation.json)" if row else "training record",
        "meets_srs_target": test["accuracy"] >= targets["classification_accuracy"]
        or test["macro_f1"] >= targets["classification_macro_f1"],
        "srs_target": f"accuracy >= {targets['classification_accuracy']} or macro F1 >= {targets['classification_macro_f1']} (SRS NFR 4)",
    }


def regression_model_card(task: str) -> dict:
    """A model card for numeric forecasts; classification accuracy/F1 do not apply."""
    m = load_regressor(task)
    row = db.session.execute(select(ModelVersion).filter_by(
        task=task, algorithm=m["algorithm"], version=m["version"])).scalar_one_or_none()
    test = ((row.metrics_json or {}).get("test") if row else None) or m["recorded_test"]
    return {
        "task": task, "algorithm": m["algorithm"], "version": m["version"], "file": m["file"],
        "pipeline": "python (Phase 7)", "trained_on": "2025-09-01..2026-05-01, chronological split",
        "test_mae": test["mae"], "test_rmse": test["rmse"], "test_r2": test["r2"],
        "metrics_source": "model_versions (re-score report: reports/saved_model_evaluation.json)" if row else "training record",
        "target": m["target"], "target_definition": m["target_definition"],
    }


def day_type_of(day: date) -> str:
    return "weekend" if day.weekday() >= 5 else "weekday"


def find_context(route_id: str, direction: int, day: date, hour: int) -> TripContext:
    ctx = db.session.execute(select(TripContext).filter_by(
        route_id=route_id, direction=direction, day_type=day_type_of(day), hour=hour)).scalar_one_or_none()
    if ctx is None:
        hours = db.session.execute(select(TripContext.hour).filter_by(
            route_id=route_id, direction=direction, day_type=day_type_of(day)).order_by(TripContext.hour)).scalars().all()
        raise ApiError(404, "no_scheduled_service",
                       f"Route {route_id} direction {direction} has no {day_type_of(day)} trips departing at {hour:02d}:00 "
                       "in the recent data, so there is no trip to predict.",
                       {"hours_with_service": hours})
    return ctx


def feature_row(task: str, ctx: TripContext, day: date, vehicle_id: str | None = None) -> dict:
    """The model's input row, column for column as `run_classification` built it."""
    vehicle_type = ctx.vehicle_type
    if vehicle_id and vehicle_id != ctx.vehicle_id:
        vehicle = db.session.get(Vehicle, vehicle_id)
        if vehicle is None:
            raise ApiError(404, "not_found", f"Vehicle {vehicle_id} does not exist.")
        vehicle_type = vehicle.vehicle_type
    row = {
        "hour": ctx.hour, "minute_of_day": ctx.hour * 60 + 30,
        "day_of_week": day.weekday(), "weekend": int(day.weekday() >= 5),
        "month": day.month, "day_of_year": day.timetuple().tm_yday,
        "distance_km": ctx.distance_km, "planned_runtime_min": ctx.planned_runtime_min,
        "headway_min": ctx.headway_min, "scheduled_runtime_min": ctx.scheduled_runtime_min,
        "capacity_total": ctx.capacity_total,
        "route_id": ctx.route_id, "vehicle_id": vehicle_id or ctx.vehicle_id, "direction": ctx.direction,
        "route_type": ctx.route_type, "vehicle_type": vehicle_type,
    }
    history = {"crowding_flag": "prior_route_crowding_rate", "delay_severity": "prior_route_delay_mean",
               "occupancy_forecast": "prior_route_occupancy_mean"}[task]
    # The context window's observed occupancy is historical input for the next trip;
    # it is not the requested trip's outcome.
    row[history] = getattr(ctx, history)
    if task == "occupancy_forecast":
        row["prior_route_hour_occupancy_mean"] = ctx.prior_route_hour_occupancy_mean
        row["prior_route_occupancy_lag1"] = ctx.prior_route_occupancy_mean
        row["prior_route_occupancy_mean_3"] = ctx.prior_route_occupancy_mean
        row["prior_route_day_occupancy_mean"] = ctx.prior_route_hour_occupancy_mean
    if task == "delay_severity":
        # The delay model's route-hour history (CMD-028; the served v1 file was retrained with it).
        row["prior_route_hour_delay_mean"] = ctx.prior_route_hour_delay_mean
        row["prior_route_hour_severe_rate"] = ctx.prior_route_hour_severe_rate
        row["prior_route_delay_lag1"] = ctx.prior_route_delay_mean
        row["prior_route_delay_mean_3"] = ctx.prior_route_delay_mean
        row["prior_route_day_delay_mean"] = ctx.prior_route_hour_delay_mean
        row["prior_vehicle_delay_lag1"] = ctx.prior_route_delay_mean
    m = load_regressor(task) if task == "occupancy_forecast" else load_classifier(task)
    return {k: row[k] for k in m["numeric"] + m["categorical"]}


def predict_proba(task: str, rows: list[dict]) -> np.ndarray:
    m = load_classifier(task)
    frame = pd.DataFrame(rows, columns=m["numeric"] + m["categorical"])
    frame[m["numeric"]] = frame[m["numeric"]].astype(float)
    return m["model"].predict_proba(m["preprocessor"].transform(frame))


def observed(ctx: TripContext) -> dict:
    """What actually happened in this route/direction/day type/hour cell in the recent window."""
    return {
        "window": f"{ctx.window_start}..{ctx.window_end}", "trips": ctx.trips_observed,
        "crowded_trip_share": ctx.observed_crowding_rate, "mean_occupancy": ctx.mean_occupancy,
        "p90_occupancy": ctx.p90_occupancy, "mean_boardings": ctx.mean_boardings,
        "mean_delay_min": ctx.observed_mean_delay_min,
    }


def predict_crowding(route_id: str, direction: int, day: date, hour: int, vehicle_id: str | None = None) -> dict:
    ctx = find_context(route_id, direction, day, hour)
    row = feature_row("crowding_flag", ctx, day, vehicle_id)
    m = load_classifier("crowding_flag")
    probability = float(predict_proba("crowding_flag", [row])[0][m["labels"].index("1.0")])
    card = model_card("crowding_flag")
    warnings = [] if card["meets_srs_target"] else [f"The crowding model is below the SRS target ({card['srs_target']})."]
    if card["test_macro_f1"] < serving_config()["srs_targets"]["classification_macro_f1"]:
        warnings.append(f"Macro F1 is {card['test_macro_f1']:.2f}: the model finds crowded trips less reliably "
                        "than uncrowded ones, so a 'not crowded' answer is the more dependable one.")
    return {
        "task": "crowding_flag", "estimate": True,
        "trip": {"route_id": route_id, "direction": direction, "service_date": day.isoformat(),
                 "hour": hour, "day_type": day_type_of(day)},
        "prediction": {"crowded": probability >= m["threshold"], "probability": round(probability, 4),
                       "threshold": m["threshold"], "meaning": CROWDING_MEANING},
        "inputs": row, "observed": observed(ctx), "model": card, "warnings": warnings,
    }


def predict_occupancy(route_id: str, direction: int, day: date, hour: int, vehicle_id: str | None = None) -> dict:
    """Estimate peak on-board occupancy for a future scheduled trip."""
    ctx = find_context(route_id, direction, day, hour)
    row = feature_row("occupancy_forecast", ctx, day, vehicle_id)
    m = load_regressor("occupancy_forecast")
    # Retain meaningful overload forecasts, but prevent negative / unusable display values.
    frame = pd.DataFrame([row], columns=m["numeric"] + m["categorical"])
    frame[m["numeric"]] = frame[m["numeric"]].astype(float)
    ratio = float(np.clip(m["model"].predict(m["preprocessor"].transform(frame))[0], 0.0, 1.5))
    capacity = row.get("capacity_total") or ctx.capacity_total
    return {
        "task": "occupancy_forecast", "estimate": True,
        "trip": {"route_id": route_id, "direction": direction, "service_date": day.isoformat(),
                 "hour": hour, "day_type": day_type_of(day)},
        "prediction": {"occupancy_ratio": round(ratio, 4), "estimated_peak_load": round(ratio * float(capacity), 1),
                       "capacity_total": capacity, "crowded_at_90pct": ratio > 0.90,
                       "meaning": "estimated maximum on-board load as a share of assigned vehicle capacity"},
        "inputs": row, "observed": observed(ctx), "model": regression_model_card("occupancy_forecast"),
        "warnings": ["This is a pre-departure estimate based on schedule and prior-route history; it is not a live passenger count."],
    }


def delay_bands_match_model() -> bool:
    """True when the configured four labels retain the model's 5/10/20-minute contract."""
    contract = settings.delay_severity_contract()
    return contract["labels"] == ["On Time", "Minor", "Moderate", "Severe"] and contract["cutpoints_minutes"] == [5, 10, 20]


def delay_band_description() -> str:
    """Human-readable API wording generated from the configured label contract."""
    contract = settings.delay_severity_contract()
    labels, cuts = contract["labels"], contract["cutpoints_minutes"]
    pieces = [f"{labels[0]} < {cuts[0]} min"]
    pieces.extend(f"{labels[index]} {cuts[index - 1]}-{cuts[index]} min" for index in range(1, len(cuts)))
    pieces.append(f"{labels[-1]} >= {cuts[-1]} min")
    return "mean trip delay: " + ", ".join(pieces) + f" ({contract['excluded_label']} is not a generated label)"


def predict_delay(route_id: str, direction: int, day: date, hour: int, vehicle_id: str | None = None) -> dict:
    ctx = find_context(route_id, direction, day, hour)
    row = feature_row("delay_severity", ctx, day, vehicle_id)
    m = load_classifier("delay_severity")
    proba = predict_proba("delay_severity", [row])[0]
    order = settings.delay_severity_contract()["labels"]
    probabilities = [{"severity": s, "probability": round(float(proba[m["labels"].index(s)]), 4)} for s in order]
    card = model_card("delay_severity")
    warnings = []
    if not card["meets_srs_target"]:
        warnings.append(f"Indicative only: this model is below the SRS target (test accuracy {card['test_accuracy']:.2f}, "
                        f"macro F1 {card['test_macro_f1']:.2f}; target {card['srs_target']}).")
    if not delay_bands_match_model():
        warnings.append("config/thresholds.yaml delay bands differ from the 5/10/20-minute bands the model was "
                        "trained on; the classes below use the training bands until the model is retrained.")
    return {
        "task": "delay_severity", "estimate": True,
        "trip": {"route_id": route_id, "direction": direction, "service_date": day.isoformat(),
                 "hour": hour, "day_type": day_type_of(day)},
        "prediction": {"severity": max(probabilities, key=lambda p: p["probability"])["severity"],
                       "probabilities": probabilities,
                       "bands": delay_band_description()},
        "inputs": row, "observed": observed(ctx), "model": card, "warnings": warnings,
    }


def crowding_risk_for_day(day: date, route_id: str | None = None) -> dict:
    """Score every route/direction/hour that runs on this day type; highest risk first."""
    query = select(TripContext).filter_by(day_type=day_type_of(day))
    if route_id:
        query = query.filter_by(route_id=route_id)
    cells = db.session.execute(query.order_by(TripContext.route_id, TripContext.direction, TripContext.hour)).scalars().all()
    if not cells:
        return {"service_date": day.isoformat(), "day_type": day_type_of(day), "cells": 0, "flagged": 0, "rows": []}
    m = load_classifier("crowding_flag")
    proba = predict_proba("crowding_flag", [feature_row("crowding_flag", c, day) for c in cells])[:, m["labels"].index("1.0")]
    rows = [{"route_id": c.route_id, "direction": c.direction, "hour": c.hour, "vehicle_id": c.vehicle_id,
             "probability": round(float(p), 4), "flagged": bool(p >= m["threshold"]),
             "observed_crowded_share": c.observed_crowding_rate, "observed_mean_occupancy": c.mean_occupancy,
             "trips_observed": c.trips_observed} for c, p in zip(cells, proba)]
    rows.sort(key=lambda r: -r["probability"])
    return {"service_date": day.isoformat(), "day_type": day_type_of(day), "threshold": m["threshold"],
            "cells": len(rows), "flagged": sum(r["flagged"] for r in rows), "rows": rows,
            "model": model_card("crowding_flag"), "estimate": True}
