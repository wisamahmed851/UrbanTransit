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
singleton in the container (`functools.cache`, once per worker process).
"""

import json
from datetime import date
from functools import cache
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


@cache
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
        "metrics_source": "model_versions (re-scored on this server)" if row else "training record",
        "meets_srs_target": test["accuracy"] >= targets["classification_accuracy"]
        or test["macro_f1"] >= targets["classification_macro_f1"],
        "srs_target": f"accuracy >= {targets['classification_accuracy']} or macro F1 >= {targets['classification_macro_f1']} (SRS NFR 4)",
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
        "hour": ctx.hour, "day_of_week": day.weekday(), "weekend": int(day.weekday() >= 5),
        "distance_km": ctx.distance_km, "planned_runtime_min": ctx.planned_runtime_min,
        "headway_min": ctx.headway_min, "scheduled_runtime_min": ctx.scheduled_runtime_min,
        "route_id": ctx.route_id, "vehicle_id": vehicle_id or ctx.vehicle_id, "direction": ctx.direction,
        "route_type": ctx.route_type, "vehicle_type": vehicle_type,
    }
    history = {"crowding_flag": "prior_route_crowding_rate", "delay_severity": "prior_route_delay_mean"}[task]
    row[history] = getattr(ctx, history)
    m = load_classifier(task)
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


def delay_bands_match_model() -> bool:
    """True when config/thresholds.yaml still uses the 5/10/20-minute bands the model was trained on."""
    bands = [b["below_minutes"] for b in settings.load_thresholds()["delay_severity"]]
    return bands == [5, 10, 20, None]


def predict_delay(route_id: str, direction: int, day: date, hour: int, vehicle_id: str | None = None) -> dict:
    ctx = find_context(route_id, direction, day, hour)
    row = feature_row("delay_severity", ctx, day, vehicle_id)
    m = load_classifier("delay_severity")
    proba = predict_proba("delay_severity", [row])[0]
    order = ["On Time", "Minor", "Moderate", "Severe"]
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
                       "bands": "mean trip delay: On Time < 5 min, Minor 5-10, Moderate 10-20, Severe >= 20"},
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
