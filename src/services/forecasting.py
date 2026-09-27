"""Daily passenger-demand forecast per route, from the saved Phase 7 regressor (CMD-024).

Phase 7 (`demand_frame`, `run_demand`) trained on one row per route and service day with
five inputs, all built from *earlier* days only:

    lag_1, lag_7, lag_28          boardings 1, 7 and 28 rows (days) before
    rolling_7_mean, rolling_28_mean   mean of the previous 7 / 28 days

This service rebuilds exactly those inputs from `route_daily_boardings`, then:

* **backtest**: one-step-ahead predictions over the test period (2026-07-02..2026-08-31),
  where every input is a real observed day, next to the 28-day-average baseline;
* **forecast**: `horizon` days after the last observed day, recursively: day t+1 uses the
  forecast of day t as its lag_1, and so on. Errors therefore grow with the horizon, and
  every forecast value is labelled an estimate.

The model is the one Phase 7 selected (lowest validation MAE): see config/serving.yaml.
"""

from datetime import date, timedelta
from functools import cache, lru_cache

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import func, select

from config import settings
from src.errors import ApiError
from src.extensions import db
from src.models.ops import ModelVersion
from src.models.serving import RouteDailyBoardings, StopPeriodBoardings
from src.services.model_serving import models_dir, serving_config

FEATURES = ["lag_1", "lag_7", "lag_28", "rolling_7_mean", "rolling_28_mean"]
STOP_PERIOD_FEATURES = ["day_of_week", "weekend", *FEATURES, "entry_stop_id", "time_period"]
TEST_PERIOD = (date(2026, 7, 2), date(2026, 8, 31))   # Phase 7 DATES["test"]


@cache
def load_regressor():
    spec = serving_config()["served"]["daily_boardings"]
    path = models_dir() / "daily_boardings" / f"{spec['algorithm']}_{spec['version']}.pkl"
    if not path.exists():
        raise ApiError(503, "model_unavailable",
                       "The saved demand model is not on this server. Unzip the shared models.zip into models/.",
                       {"missing": [str(path.relative_to(settings.PROJECT_ROOT))]})
    model = joblib.load(path)
    # Saved with n_jobs=-1: every predict() would start a worker pool, which costs far more
    # than the prediction itself for the small batches a recursive forecast makes.
    if hasattr(model, "n_jobs"):
        model.n_jobs = 1
    return spec, model


def next_features(history: list[float]) -> list[float]:
    """Inputs for the day after `history` (oldest first), as pandas shift()/rolling() gave them."""
    def lag(n):
        return history[-n] if len(history) >= n else np.nan
    return [lag(1), lag(7), lag(28), float(np.mean(history[-7:])), float(np.mean(history[-28:]))]


def route_series(route_ids: list[str] | None = None) -> dict[str, pd.Series]:
    query = select(RouteDailyBoardings.route_id, RouteDailyBoardings.service_date, RouteDailyBoardings.boardings)
    if route_ids:
        query = query.where(RouteDailyBoardings.route_id.in_(route_ids))
    rows = db.session.execute(query.order_by(RouteDailyBoardings.route_id, RouteDailyBoardings.service_date)).all()
    frame = pd.DataFrame(rows, columns=["route_id", "service_date", "boardings"])
    return {r: g.set_index("service_date").boardings.astype(float) for r, g in frame.groupby("route_id")}


def recursive_forecast(series: dict[str, pd.Series], horizon: int) -> dict[str, list[dict]]:
    """Forecast every route `horizon` days ahead, one step at a time, all routes per step."""
    _, model = load_regressor()
    routes = [r for r, s in series.items() if len(s) >= 28]
    histories = {r: series[r].tolist() for r in routes}
    out = {r: [] for r in routes}
    for step in range(1, horizon + 1):
        X = pd.DataFrame([next_features(histories[r]) for r in routes], columns=FEATURES)
        preds = np.clip(model.predict(X), 0, None)
        for r, p in zip(routes, preds):
            histories[r].append(float(p))
            out[r].append({"date": (series[r].index[-1] + timedelta(days=step)).isoformat(), "predicted": round(float(p), 1)})
    return out


def backtest(s: pd.Series) -> list[dict]:
    """One-step-ahead predictions for the test-period days of one route, with the baseline."""
    _, model = load_regressor()
    values, dates = s.tolist(), list(s.index)
    idx = [i for i, d in enumerate(dates) if TEST_PERIOD[0] <= d <= TEST_PERIOD[1] and i >= 28]
    if not idx:
        return []
    X = pd.DataFrame([next_features(values[:i]) for i in idx], columns=FEATURES)
    preds = model.predict(X)
    return [{"date": dates[i].isoformat(), "actual": values[i], "predicted": round(float(p), 1),
             "baseline": round(float(X.rolling_28_mean.iloc[k]), 1)} for k, (i, p) in enumerate(zip(idx, preds))]


def errors(rows: list[dict], key: str) -> dict:
    a = np.array([r["actual"] for r in rows]); p = np.array([r[key] for r in rows])
    if not len(a):
        return {}
    nonzero = a != 0
    return {"mae": round(float(np.abs(a - p).mean()), 1), "rmse": round(float(np.sqrt(((a - p) ** 2).mean())), 1),
            "mape": round(float(np.abs((a[nonzero] - p[nonzero]) / a[nonzero]).mean() * 100), 2) if nonzero.any() else None}


def model_card() -> dict:
    spec, _ = load_regressor()
    row = db.session.execute(select(ModelVersion).filter_by(task="daily_boardings", algorithm=spec["algorithm"],
                                                             version=spec["version"])).scalar_one_or_none()
    metrics = (row.metrics_json or {}) if row else {}
    return {"task": "daily_boardings", "algorithm": spec["algorithm"], "version": spec["version"],
            "pipeline": "python (Phase 7)", "features": FEATURES,
            "test": metrics.get("test"), "srs_target": metrics.get("srs_target")}


def check_horizon(horizon: int) -> None:
    cap = serving_config()["forecast"]["max_horizon_days"]
    if not 1 <= horizon <= cap:
        raise ApiError(400, "invalid_parameter", f"'horizon' must be between 1 and {cap} days.")


def route_forecast(route_id: str, horizon: int, history_days: int) -> dict:
    check_horizon(horizon)
    series = route_series([route_id]).get(route_id)
    if series is None or len(series) < 28:
        raise ApiError(404, "not_found", f"Route {route_id} has no daily boardings history (28 days needed).")
    bt = backtest(series)
    return {
        "route_id": route_id, "estimate": True, "horizon_days": horizon,
        "last_observed_date": series.index[-1].isoformat(),
        "history": [{"date": d.isoformat(), "actual": v} for d, v in series.iloc[-history_days:].items()],
        "backtest": bt, "backtest_errors": {"model": errors(bt, "predicted"), "baseline_28day": errors(bt, "baseline")},
        "forecast": recursive_forecast({route_id: series}, horizon)[route_id],
        "model": model_card(),
        "notes": ["Boardings are automatic passenger counts on completed trips, summed per day (the Phase 7 target).",
                  "Backtest: each day predicted from real earlier days only (test period, not used in training).",
                  "Forecast: recursive; each day feeds the next, so uncertainty grows with the horizon."],
    }


def data_version() -> tuple:
    """Changes whenever route_daily_boardings is reloaded, so cached forecasts are recomputed."""
    return tuple(db.session.execute(select(func.count(), func.max(RouteDailyBoardings.service_date),
                                           func.sum(RouteDailyBoardings.boardings))).one())


def network_forecast(horizon: int) -> dict:
    """All routes forecast together: the daily network total and the routes with the most growth.
    The result depends only on the loaded data and the horizon, so it is cached per process."""
    check_horizon(horizon)
    return _network_forecast(horizon, data_version())


@cache
def load_stop_period_regressor():
    """Load the independent ticket tap-in model and its fitted preprocessor."""
    spec = serving_config()["served"].get("stop_period_demand")
    if not spec:
        raise ApiError(503, "model_unavailable", "The stop-period demand model has not been trained yet.")
    base = models_dir() / "stop_period_demand"
    model_path = base / f"{spec['algorithm']}_{spec['version']}.pkl"
    prep_path = base / f"{spec['algorithm']}_preprocessor_{spec['version']}.pkl"
    missing = [p for p in (model_path, prep_path) if not p.exists()]
    if missing:
        raise ApiError(503, "model_unavailable", "The saved stop-period demand model is not on this server.",
                       {"missing": [str(p.relative_to(settings.PROJECT_ROOT)) for p in missing]})
    model, encoder = joblib.load(model_path), joblib.load(prep_path)
    if hasattr(model, "n_jobs"):
        model.n_jobs = 1
    return spec, model, encoder


def stop_period_series(stop_id: str, time_period: str) -> pd.Series | None:
    rows = db.session.execute(
        select(StopPeriodBoardings.service_date, StopPeriodBoardings.tap_ins)
        .where(StopPeriodBoardings.entry_stop_id == stop_id, StopPeriodBoardings.time_period == time_period)
        .order_by(StopPeriodBoardings.service_date)
    ).all()
    if not rows:
        return None
    return pd.Series([float(v) for _, v in rows], index=[d for d, _ in rows], dtype=float)


def next_stop_features(history: list[float], forecast_date: date, stop_id: str, time_period: str) -> dict:
    base = next_features(history)
    return {"day_of_week": forecast_date.weekday(), "weekend": int(forecast_date.weekday() >= 5),
            **dict(zip(FEATURES, base)), "entry_stop_id": stop_id, "time_period": time_period}


def stop_period_model_card() -> dict:
    spec, _, _ = load_stop_period_regressor()
    row = db.session.execute(select(ModelVersion).filter_by(task="stop_period_demand", algorithm=spec["algorithm"],
                                                             version=spec["version"])).scalar_one_or_none()
    metrics = (row.metrics_json or {}) if row else {}
    return {"task": "stop_period_demand", "algorithm": spec["algorithm"], "version": spec["version"],
            "pipeline": "python (ticket tap-ins)", "features": STOP_PERIOD_FEATURES,
            "test": metrics.get("test"), "baseline_28day": metrics.get("baseline_28day"),
            "coverage_note": "Smart-card and mobile-QR tap-ins only; cash riders are not observed."}


def stop_period_forecast(stop_id: str, time_period: str, horizon: int, history_days: int) -> dict:
    check_horizon(horizon)
    series = stop_period_series(stop_id, time_period)
    if series is None or len(series) < 28:
        raise ApiError(404, "not_found", f"Stop {stop_id} has no {time_period} tap-in history (28 days needed).")
    _, model, encoder = load_stop_period_regressor()
    history = series.tolist()
    rows = []
    for step in range(1, horizon + 1):
        forecast_date = series.index[-1] + timedelta(days=step)
        raw = pd.DataFrame([next_stop_features(history, forecast_date, stop_id, time_period)], columns=STOP_PERIOD_FEATURES)
        predicted = max(0.0, float(model.predict(encoder.transform(raw))[0]))
        history.append(predicted)
        rows.append({"date": forecast_date.isoformat(), "predicted": round(predicted, 1)})
    return {
        "stop_id": stop_id, "time_period": time_period, "estimate": True, "horizon_days": horizon,
        "last_observed_date": series.index[-1].isoformat(),
        "history": [{"date": d.isoformat(), "actual": v} for d, v in series.iloc[-history_days:].items()],
        "forecast": rows, "model": stop_period_model_card(),
        "notes": ["Target: observed ticket entry tap-ins, not all passenger boardings.",
                  "Forecast is recursive: each estimated day becomes history for the next day."],
    }


def stop_period_options() -> dict:
    rows = db.session.execute(select(StopPeriodBoardings.entry_stop_id, StopPeriodBoardings.time_period)
                              .distinct().order_by(StopPeriodBoardings.entry_stop_id, StopPeriodBoardings.time_period)).all()
    by_stop: dict[str, list[str]] = {}
    for stop_id, time_period in rows:
        by_stop.setdefault(stop_id, []).append(time_period)
    return {"stops": [{"stop_id": stop_id, "periods": periods} for stop_id, periods in by_stop.items()],
            "period_order": ["early", "am_peak", "midday", "pm_peak", "evening"],
            "source": "clean ticket entry tap-ins"}


@lru_cache(maxsize=16)
def _network_forecast(horizon: int, _version: tuple) -> dict:
    series = route_series()
    fc = recursive_forecast(series, horizon)
    total: dict[str, float] = {}
    for rows in fc.values():
        for r in rows:
            total[r["date"]] = total.get(r["date"], 0.0) + r["predicted"]
    growth = []
    for route, rows in fc.items():
        recent = float(series[route].iloc[-28:].mean())
        ahead = float(np.mean([r["predicted"] for r in rows]))
        growth.append({"route_id": route, "recent_28day_mean": round(recent, 1), "forecast_mean": round(ahead, 1),
                       "change_pct": round((ahead - recent) / recent * 100, 1) if recent else None,
                       "peak_day": max(rows, key=lambda r: r["predicted"])["date"],
                       "peak_value": max(r["predicted"] for r in rows)})
    growth.sort(key=lambda g: -g["forecast_mean"])
    last = max(s.index[-1] for s in series.values())
    history = pd.concat(series.values(), axis=1).sum(axis=1).sort_index().iloc[-56:]
    return {
        "estimate": True, "horizon_days": horizon, "routes": len(fc), "last_observed_date": last.isoformat(),
        "history": [{"date": d.isoformat(), "actual": round(float(v), 1)} for d, v in history.items()],
        "forecast": [{"date": d, "predicted": round(v, 1)} for d, v in sorted(total.items())],
        "by_route": growth, "model": model_card(),
    }
