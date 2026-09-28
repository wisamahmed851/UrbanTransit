"""Model serving (CMD-024): predictions, crowding-risk list, forecasts, what-if, recommendations,
the Spark-vs-Python comparison and the model registry.

Prediction, forecast and what-if tests call the real saved Phase 7 models. The binaries are
not in git (models.zip), so those tests are skipped where `models/python` lacks them. The
MySQL tables are seeded here with small rows shaped like the loaded ones.
"""

from datetime import date, timedelta
from pathlib import Path

import pytest

from src.extensions import db
from src.models.ops import ModelVersion
from src.models.serving import (PipelineComparison, PythonClusterProfile, Recommendation, RouteCluster,
                                RouteDailyBoardings, StopPeriodBoardings, TripContext)

MODELS = Path(__file__).resolve().parent.parent / "models" / "python"
needs_models = pytest.mark.skipif(
    not all((MODELS / f).exists() for f in ("crowding_flag/random_forest_v1.pkl", "delay_severity/xgboost_v1.pkl",
                                            "daily_boardings/xgboost_v1.pkl")),
    reason="saved Phase 7 model binaries are not present (unzip models.zip into models/)")
needs_occupancy_model = pytest.mark.skipif(
    not all((MODELS / f).exists() for f in ("occupancy_forecast/xgboost_v1.pkl", "occupancy_forecast/xgboost_preprocessor_v1.pkl")),
    reason="saved numeric occupancy model is not present (run Phase 7 task e or unzip models.zip into models/)")
needs_stop_period_model = pytest.mark.skipif(
    not all((MODELS / f).exists() for f in ("stop_period_demand/random_forest_v1.pkl", "stop_period_demand/random_forest_preprocessor_v1.pkl")),
    reason="saved stop-period demand model is not present (run Phase 7 task f or unzip models.zip into models/)")

TRIP = {"route_id": "R001", "direction": 0, "service_date": "2026-09-29", "hour": 8}   # a Tuesday


def context(hour: int, day_type: str = "weekday", **overrides) -> TripContext:
    values = dict(route_id="R001", direction=0, day_type=day_type, hour=hour, vehicle_id="V0001",
                  vehicle_type="standard", capacity_total=80.0, route_type="brt", distance_km=18.5,
                  planned_runtime_min=55.0, headway_min=10.0, scheduled_runtime_min=55.0,
                  prior_route_crowding_rate=0.2, prior_route_delay_mean=2.5,
                  prior_route_occupancy_mean=0.77, prior_route_hour_occupancy_mean=0.81,
                  prior_route_hour_delay_mean=3.25, prior_route_hour_severe_rate=0.15, trips_observed=40,
                  observed_crowding_rate=0.25, observed_mean_delay_min=2.1, mean_boardings=70.0,
                  mean_max_load=64.0, mean_occupancy=0.8, p90_occupancy=0.95,
                  window_start=date(2026, 7, 7), window_end=date(2026, 8, 31))
    return TripContext(**{**values, **overrides})


@pytest.fixture
def served(app):
    with app.app_context():
        db.session.add_all([context(8), context(9, mean_max_load=30.0), context(8, "weekend"),
                            context(8, route_id="R002", headway_min=20.0, mean_max_load=90.0)])
        start = date(2026, 6, 1)
        db.session.add_all(RouteDailyBoardings(route_id="R001", service_date=start + timedelta(days=i),
                                               boardings=1000 + (300 if (start + timedelta(days=i)).weekday() < 5 else 0) + i)
                           for i in range(92))                   # 2026-06-01 .. 2026-08-31
        db.session.add_all(StopPeriodBoardings(entry_stop_id="S0001", service_date=start + timedelta(days=i),
                                               time_period="am_peak", tap_ins=20 + (4 if (start + timedelta(days=i)).weekday() < 5 else 0) + i % 3)
                           for i in range(92))
        db.session.add_all([
            Recommendation(recommendation_id="REC-001", subject_id="R011", category="CAPACITY", priority="High",
                           priority_rank=2, action="Allocate higher-capacity vehicle or add trips.",
                           evidence="Route R011 (morning_peak): p90 load is 91.0", estimated_impact="(Estimate) ..."),
            Recommendation(recommendation_id="REC-140", subject_id="R107", category="FREQUENCY", priority="Critical",
                           priority_rank=1, action="Increase frequency during identified peak periods.",
                           evidence="Route R107 (evening_peak): avg utilization 125.3%", estimated_impact=None),
        ])
        db.session.add_all([
            PipelineComparison(task="crowding_flag", case_id="T1", actual="1.0", spark_prediction="1.0",
                               python_prediction="1.0", match=True, agreement_status="BothCorrect"),
            PipelineComparison(task="crowding_flag", case_id="T2", actual="0.0", spark_prediction="0.0",
                               python_prediction="1.0", match=False, agreement_status="SparkOnlyCorrect"),
            PipelineComparison(task="daily_boardings", case_id="R001_2026-07-02", actual="100", spark_prediction="95",
                               python_prediction="97", absolute_difference=2.0, match=True, agreement_status="BothCorrect"),
        ])
        db.session.add_all([RouteCluster(route_id="R001", algorithm="kmeans_k5", cluster=4),
                            PythonClusterProfile(cluster=4, avg_occupancy=0.43, profile_label="Very-high-demand trunk routes", routes=1)])
        db.session.add(ModelVersion(task="crowding_flag", algorithm="random_forest", version="v1", is_active=True,
                                    metrics_json={"test": {"accuracy": 0.9027, "macro_f1": 0.7613}}))
        db.session.commit()
    return app


# ---- permissions -------------------------------------------------------------------------

@pytest.mark.parametrize("method,url", [
    ("post", "/api/predictions/crowding"), ("post", "/api/predictions/occupancy"), ("post", "/api/predictions/delay"), ("post", "/api/whatif"),
    ("get", "/api/predictions/crowding-risk?date=2026-09-29"),
])
def test_analyst_cannot_run_predictions(client, auth, served, method, url):
    assert getattr(client, method)(url, json=TRIP, headers=auth("analyst")).status_code == 403


def test_evaluator_reads_recommendations(client, auth, served):
    assert client.get("/api/recommendations", headers=auth("evaluator")).status_code == 200


# ---- predictions -------------------------------------------------------------------------

@needs_models
def test_crowding_prediction(client, auth, served):
    body = client.post("/api/predictions/crowding", json=TRIP, headers=auth("operator")).get_json()
    p = body["prediction"]
    assert 0 <= p["probability"] <= 1 and p["crowded"] == (p["probability"] >= p["threshold"])
    assert p["threshold"] == pytest.approx(0.70)
    assert body["estimate"] is True and body["trip"]["day_type"] == "weekday"
    assert set(body["inputs"]) == {"hour", "minute_of_day", "day_of_week", "weekend", "month", "day_of_year",
                                   "distance_km", "planned_runtime_min", "headway_min",
                                   "scheduled_runtime_min", "prior_route_crowding_rate", "route_id", "vehicle_id",
                                   "direction", "route_type", "vehicle_type"}
    assert body["inputs"]["day_of_week"] == 1 and body["inputs"]["weekend"] == 0
    assert body["model"]["metrics_source"].startswith("model_versions")
    assert body["model"]["meets_srs_target"] is True                 # accuracy 0.90 >= 0.85


@needs_occupancy_model
def test_numeric_occupancy_prediction(client, auth, served):
    body = client.post("/api/predictions/occupancy", json=TRIP, headers=auth("operator")).get_json()
    p = body["prediction"]
    assert body["task"] == "occupancy_forecast" and body["estimate"] is True
    assert 0 <= p["occupancy_ratio"] <= 1.5
    assert p["estimated_peak_load"] == pytest.approx(p["occupancy_ratio"] * p["capacity_total"], abs=0.11)
    assert "prior_route_occupancy_mean" in body["inputs"]
    assert "prior_route_hour_occupancy_mean" in body["inputs"]
    assert "max_load" not in body["inputs"] and "boardings" not in body["inputs"]
    assert body["model"]["test_mae"] >= 0 and body["model"]["test_rmse"] >= 0


@needs_models
def test_delay_prediction_is_labelled_below_target(client, auth, served):
    body = client.post("/api/predictions/delay", json=TRIP, headers=auth("operator")).get_json()
    probs = body["prediction"]["probabilities"]
    assert [p["severity"] for p in probs] == ["On Time", "Minor", "Moderate", "Severe"]
    assert sum(p["probability"] for p in probs) == pytest.approx(1, abs=1e-3)
    assert body["prediction"]["severity"] == max(probs, key=lambda p: p["probability"])["severity"]
    assert body["inputs"]["prior_route_hour_delay_mean"] == 3.25
    assert body["inputs"]["prior_route_hour_severe_rate"] == 0.15
    assert body["model"]["meets_srs_target"] is False and body["warnings"]


@needs_models
def test_prediction_without_service_is_404(client, auth, served):
    res = client.post("/api/predictions/crowding", json={**TRIP, "hour": 3}, headers=auth("operator"))
    assert res.status_code == 404
    assert res.get_json()["error"]["details"]["hours_with_service"] == [8, 9]


@pytest.mark.parametrize("change", [{"hour": 24}, {"direction": 2}, {"service_date": "tomorrow"}, {"hour": "eight"}])
def test_prediction_validation(client, auth, served, change):
    res = client.post("/api/predictions/crowding", json={**TRIP, **change}, headers=auth("operator"))
    assert res.status_code == 400 and res.get_json()["error"]["code"] == "invalid_parameter"


@needs_models
def test_crowding_risk_list(client, auth, served):
    body = client.get("/api/predictions/crowding-risk?date=2026-09-29", headers=auth("operator")).get_json()
    assert body["cells"] == 3                                        # the weekday cells only
    probs = [r["probability"] for r in body["rows"]]
    assert probs == sorted(probs, reverse=True)
    assert body["flagged"] == sum(r["flagged"] for r in body["rows"])


# ---- forecasts ---------------------------------------------------------------------------

@needs_models
def test_route_forecast(client, auth, served):
    body = client.get("/api/forecasts/demand?route_id=R001&horizon=10&history=30", headers=auth("analyst")).get_json()
    assert body["last_observed_date"] == "2026-08-31" and len(body["history"]) == 30
    assert [f["date"] for f in body["forecast"]][:2] == ["2026-09-01", "2026-09-02"] and len(body["forecast"]) == 10
    assert all(f["predicted"] >= 0 for f in body["forecast"])
    assert body["backtest"][0]["date"] == "2026-07-02" and len(body["backtest"]) == 61
    assert set(body["backtest_errors"]) == {"model", "baseline_28day"}


def test_forecast_parameters(client, auth, served):
    h = auth("analyst")
    assert client.get("/api/forecasts/demand", headers=h).status_code == 400
    assert client.get("/api/forecasts/demand?route_id=R001&horizon=0", headers=h).status_code == 400
    assert client.get("/api/forecasts/demand?route_id=R001&horizon=999", headers=h).status_code == 400


@needs_models
def test_network_forecast(client, auth, served):
    body = client.get("/api/forecasts/demand/network?horizon=7", headers=auth("analyst")).get_json()
    assert body["routes"] == 1 and len(body["forecast"]) == 7
    assert body["by_route"][0]["route_id"] == "R001"


@needs_stop_period_model
def test_stop_period_forecast(client, auth, served):
    h = auth("analyst")
    body = client.get("/api/forecasts/demand/stop-period?stop_id=S0001&period=am_peak&horizon=7&history=30", headers=h).get_json()
    assert body["stop_id"] == "S0001" and body["time_period"] == "am_peak"
    assert len(body["history"]) == 30 and len(body["forecast"]) == 7
    assert all(r["predicted"] >= 0 for r in body["forecast"])
    options = client.get("/api/forecasts/demand/stop-period/options", headers=h).get_json()
    assert options["stops"] == [{"stop_id": "S0001", "periods": ["am_peak"]}]


# ---- what-if -----------------------------------------------------------------------------

def whatif(client, auth, scenario, params=None, **trip):
    return client.post("/api/whatif", json={**TRIP, **trip, "scenario": scenario, "params": params or {}},
                       headers=auth("operator"))


@needs_models
def test_whatif_increase_frequency(client, auth, served):
    body = whatif(client, auth, "increase_frequency", {"trips": 2}).get_json()
    b, a = body["baseline"], body["result"]
    assert (b["trips_per_hour"], a["trips_per_hour"]) == (6.0, 8.0)
    assert a["headway_min"] == 7.5 and a["waiting_time_min"] < b["waiting_time_min"]
    assert a["occupancy"] == pytest.approx(b["occupancy"] * 6 / 8, abs=1e-3)       # same demand, more trips
    assert a["demand_per_hour"] == b["demand_per_hour"] and body["estimate"] is True


@needs_models
def test_whatif_capacity_and_demand(client, auth, served):
    body = whatif(client, auth, "change_vehicle_capacity", {"capacity": 160}).get_json()
    assert body["result"]["occupancy"] == pytest.approx(body["baseline"]["occupancy"] / 2, abs=1e-3)
    assert body["result"]["crowding_probability"] == body["baseline"]["crowding_probability"]
    body = whatif(client, auth, "increase_demand", {"percent": 50}).get_json()
    assert body["result"]["demand_per_hour"] == pytest.approx(body["baseline"]["demand_per_hour"] * 1.5, abs=0.2)


@needs_models
def test_whatif_shift_moves_to_next_hour(client, auth, served):
    body = whatif(client, auth, "shift_trip_time", {"minutes": 45}).get_json()
    assert body["result"]["hour"] == 9
    assert body["result"]["peak_load_per_trip"] == 30.0                            # the 09:00 cell's load


@pytest.mark.parametrize("scenario,params,code", [
    ("add_new_stop", {}, "unsupported_scenario"),
    ("increase_frequency", {"trips": 0}, "invalid_parameter"),
    ("change_vehicle_capacity", {"capacity": "big"}, "invalid_parameter"),
])
def test_whatif_rejects_bad_input(client, auth, served, scenario, params, code):
    if code != "unsupported_scenario" and not MODELS.joinpath("crowding_flag/xgboost_v1.pkl").exists():
        pytest.skip("saved models not present")
    res = whatif(client, auth, scenario, params)
    assert res.status_code == 400 and res.get_json()["error"]["code"] == code


# ---- recommendations, comparison, registry ------------------------------------------------

def test_recommendations_most_urgent_first(client, auth, served):
    body = client.get("/api/recommendations", headers=auth("analyst")).get_json()
    assert [r["recommendation_id"] for r in body["rows"]] == ["REC-140", "REC-001"]
    assert body["summary"]["by_priority"] == {"High": 1, "Critical": 1}
    body = client.get("/api/recommendations?category=CAPACITY", headers=auth("analyst")).get_json()
    assert body["total"] == 1 and body["rows"][0]["subject_id"] == "R011"
    assert client.get("/api/recommendations?q=utilization", headers=auth("analyst")).get_json()["total"] == 1


def test_comparison_rates_are_counted(client, auth, served):
    body = client.get("/api/comparison", headers=auth("evaluator")).get_json()
    crowd = next(t for t in body["tasks"] if t["task"] == "crowding_flag")
    assert (crowd["cases"], crowd["agreement_rate"], crowd["spark_correct_rate"], crowd["python_correct_rate"]) == (2, 0.5, 1.0, 0.5)
    assert body["overall_agreement_rate"] == pytest.approx(2 / 3, abs=1e-4)
    cases = client.get("/api/comparison/crowding_flag?match=false", headers=auth("evaluator")).get_json()
    assert cases["total"] == 1 and cases["rows"][0]["case_id"] == "T2"
    assert client.get("/api/comparison/nope", headers=auth("evaluator")).status_code == 404


def test_registry_and_python_clusters(client, auth, served):
    h = auth("evaluator")
    rows = client.get("/api/models/versions", headers=h).get_json()["rows"]
    assert rows[0]["task"] == "crowding_flag" and rows[0]["is_active"] is True
    body = client.get("/api/models/clusters/python", headers=h).get_json()
    assert body["clusters"][0]["route_ids"] == ["R001"] and body["algorithm"] == "kmeans_k5"
