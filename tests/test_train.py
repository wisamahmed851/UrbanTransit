"""POST /api/train (CMD-025): admin only, one run at a time, input validated. Training never runs here."""

import pytest

from src.blueprints import train


@pytest.fixture
def no_training(monkeypatch):
    """Record the requested pipelines instead of training; keep the lock held like a real run."""
    started = []
    monkeypatch.setattr(train, "_run_training", lambda pipeline: started.append(pipeline))
    yield started
    if train._running.locked():
        train._running.release()


@pytest.mark.parametrize("role", ["operator", "analyst", "evaluator"])
def test_only_admin_can_train(client, auth, no_training, role):
    assert client.post("/api/train", json={"pipeline": "python"}, headers=auth(role)).status_code == 403
    assert no_training == []


def test_admin_starts_one_run_at_a_time(client, auth, no_training):
    h = auth("admin")
    res = client.post("/api/train", json={"pipeline": "python"}, headers=h)
    assert res.status_code == 202 and no_training == ["python"]
    busy = client.post("/api/train", json={"pipeline": "spark"}, headers=h)
    assert busy.status_code == 409 and busy.get_json()["error"]["code"] == "training_running"
    assert no_training == ["python"]


def test_unknown_pipeline_is_rejected(client, auth, no_training):
    res = client.post("/api/train", json={"pipeline": "everything"}, headers=auth("admin"))
    assert res.status_code == 400 and no_training == []
