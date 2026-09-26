"""Model metrics normalisation on the real Phase 6 files, the models API, and the stubs."""

import json
from pathlib import Path

import pytest

from database.load_model_metrics import read_cluster_rows
from database.metrics_normaliser import normalise
from src.extensions import db
from src.models.ml import ClusterProfile, ModelMetric

METRICS_DIR = Path(__file__).resolve().parent.parent / "models" / "spark" / "metrics"
FILES = sorted(METRICS_DIR.glob("*.json"))


def rows_of(name: str) -> list[dict]:
    return normalise(name, json.loads((METRICS_DIR / name).read_text(encoding="utf-8")))


@pytest.mark.parametrize("path", FILES, ids=[p.stem for p in FILES])
def test_every_real_file_normalises(path):
    rows = normalise(path.name, json.loads(path.read_text(encoding="utf-8")))
    assert rows
    for row in rows:
        assert isinstance(row["metric_value"], float)
        assert row["validity_flag"] == ("INVALID" if row["task"] == "delay_severity" else None)


def test_layouts():
    sample = {(r["split_type"], r["metric_name"]): r for r in rows_of("crowding_flag_gbt_sample.json")}
    assert sample[("test_full", "macro_f1")]["metric_value"] == 0.687051
    assert sample[("test_full", "macro_f1")]["extra_json"]["rows"] == 299504
    assert sample[("test_full", "macro_f1")]["extra_json"]["training_fraction"] == 0.1

    weighted = {(r["split_type"], r["metric_name"]): r
                for r in rows_of("delay_severity_random_forest_full_weighted_enhanced_v4_depth12.json")}
    assert weighted[("test", "macro_f1")]["metric_value"] == 0.695002
    assert weighted[("test", "per_class_f1[Severe]")]["metric_value"] == 0.632618
    assert "confusion_matrix_long" in weighted[("test", "accuracy")]["extra_json"]

    legacy = {r["metric_name"] for r in rows_of("delay_severity_random_forest.json")}
    assert "weighted_f1" in legacy and "macro_f1" not in legacy      # names kept as written

    xgb = rows_of("delay_severity_xgboost_gpu.json")
    assert {r["split_type"] for r in xgb} == {"test", "validation_selection"}

    (degenerate,) = rows_of("route_clustering_bisecting_kmeans_k4.json")
    assert degenerate["metric_name"] == "actual_clusters" and degenerate["extra_json"]["status"] == "skipped_degenerate_solution"
    (kmeans,) = rows_of("route_clustering_kmeans_k4.json")
    assert (kmeans["metric_name"], kmeans["metric_value"], kmeans["extra_json"]["k"]) == ("silhouette", 0.514014, 4)


@pytest.fixture
def loaded(app):
    with app.app_context():
        rows = [r for p in FILES for r in normalise(p.name, json.loads(p.read_text(encoding="utf-8")))]
        db.session.execute(ModelMetric.__table__.insert(), rows)
        db.session.execute(ClusterProfile.__table__.insert(), read_cluster_rows())
        db.session.commit()
        return len(rows)


def test_metrics_api_warns_about_invalid_delay_models(client, auth, loaded):
    h = auth("analyst")
    body = client.get("/api/models/metrics", headers=h).get_json()
    assert body["total"] == loaded
    assert [w["task"] for w in body["warnings"]] == ["delay_severity"]
    body = client.get("/api/models/metrics?task=daily_boardings&split_type=test&metric_name=mae", headers=h).get_json()
    # 4 regressors + the strict-prior trailing-28-day baseline
    assert body["warnings"] == [] and body["total"] == 5


def test_clusters_api(client, auth, loaded):
    body = client.get("/api/models/clusters", headers=auth("evaluator")).get_json()
    assert body["k"] == 4
    assert [c["routes"] for c in body["clusters"]] == [32, 60, 20, 4]
    assert "route_id" not in body["clusters"][0]


@pytest.mark.parametrize("method,url,feature", [
    ("post", "/api/predictions/delay", "predictions.delay"),
    ("post", "/api/predictions/crowding", "predictions.crowding"),
])
def test_stubs_are_explicit(client, auth, method, url, feature):
    res = getattr(client, method)(url, json={}, headers=auth("operator"))
    body = res.get_json()
    assert res.status_code == 503
    assert body["stub"] is True and body["status"] == "unavailable" and body["feature"] == feature
    assert body["reason"].startswith("unavailable - ")


def test_recommendations_are_generated_pipeline_artifacts(client, auth):
    res = client.get("/api/recommendations", headers=auth("operator"))
    body = res.get_json()
    assert res.status_code == 200
    assert body["total"] == 140
    assert body["rows"][0]["evidence"]
