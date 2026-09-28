"""load_once (CMD-028): concurrent callers share one model load instead of each loading a copy."""

import threading
import time

from src.services.model_serving import load_once


def test_concurrent_callers_load_once():
    calls = []

    @load_once
    def slow_load(name):
        calls.append(name)
        time.sleep(0.2)          # an unpickle in progress
        return {"model": name}

    results = []
    threads = [threading.Thread(target=lambda: results.append(slow_load("occupancy"))) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert calls == ["occupancy"]
    assert all(r is results[0] for r in results)


def test_failed_load_is_not_cached():
    attempts = []

    @load_once
    def missing(name):
        attempts.append(name)
        raise FileNotFoundError(name)

    for _ in range(2):
        try:
            missing("x")
        except FileNotFoundError:
            pass
    assert attempts == ["x", "x"]
