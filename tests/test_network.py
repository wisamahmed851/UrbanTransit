"""Network map endpoints: geometry, replay window, vehicle positions at a moment."""

from datetime import date, datetime

import pytest

from src.blueprints import network
from src.extensions import db
from src.models.network import GpsEvent, RouteStop


@pytest.fixture
def replay(app):
    network._cache.clear()
    with app.app_context():
        db.session.add_all([
            RouteStop(route_id="R001", direction=0, stop_sequence=1, stop_id="S0001", distance_from_start_km=0.0,
                      scheduled_offset_min=0.0, is_timing_point=True, dq_flags=[]),
            RouteStop(route_id="R001", direction=0, stop_sequence=2, stop_id="S0002", distance_from_start_km=18.5,
                      scheduled_offset_min=40.0, is_timing_point=True, dq_flags=[]),
        ])
        pings = [  # vehicle, time, lon, lat
            ("G1", "V0001", "2025-11-12 08:00:00", 67.01, 24.86),
            ("G2", "V0001", "2025-11-12 08:02:00", 67.05, 24.87),   # latest for V0001 at 08:02
            ("G3", "V0002", "2025-11-12 07:40:00", 67.10, 24.88),   # too old for a 3-minute window
            ("G4", "V0003", "2025-11-12 08:02:30", 67.12, 24.89),   # after `at`
        ]
        db.session.add_all([GpsEvent(event_id=e, vehicle_id=v, trip_id="T1", route_id="R001", stop_id=None,
                                     event_time=datetime.fromisoformat(t), event_type="in_transit",
                                     longitude=lon, latitude=lat, speed_kmh=21.5, dq_flags=[],
                                     event_date=date(2025, 11, 12)) for e, v, t, lon, lat in pings])
        db.session.commit()
    yield
    network._cache.clear()


def test_geometry_builds_ordered_route_lines_and_stops(client, auth, replay):
    body = client.get("/api/network/geometry", headers=auth("analyst")).get_json()
    (line,) = body["routes"]["features"]
    assert line["geometry"]["coordinates"] == [[67.01, 24.86], [67.16, 24.90]]
    assert line["properties"]["route_type"] == "brt" and line["properties"]["route_class"] == "High Performing"
    assert len(body["stops"]["features"]) == 2


def test_replay_window_is_labelled_as_replay(client, auth, replay):
    body = client.get("/api/network/replay", headers=auth("analyst")).get_json()
    assert body["start"] == "2025-11-12T07:40:00" and body["end"] == "2025-11-12T08:02:30"
    assert body["vehicles"] == 3 and body["days"] == [{"date": "2025-11-12", "pings": 4}]
    assert "Not real-time" in body["source"]


def test_vehicles_at_a_moment(client, auth, replay):
    body = client.get("/api/network/vehicles?at=2025-11-12T08:02:10", headers=auth("analyst")).get_json()
    assert body["active"] == 1
    (bus,) = body["vehicles"]
    assert (bus["vehicle_id"], bus["longitude"], bus["route_type"]) == ("V0001", 67.05, "brt")
    wider = client.get("/api/network/vehicles?at=2025-11-12T08:02:10&window=900", headers=auth("analyst")).get_json()
    assert wider["active"] == 1          # V0002's ping is 22 minutes old, still outside 15 minutes


def test_vehicles_rejects_bad_or_outside_times(client, auth, replay):
    h = auth("analyst")
    res = client.get("/api/network/vehicles?at=2026-01-01T08:00:00", headers=h)
    assert res.status_code == 400 and res.get_json()["error"]["code"] == "outside_replay_window"
    assert client.get("/api/network/vehicles?at=yesterday", headers=h).status_code == 400
    assert client.get("/api/network/vehicles?at=2025-11-12T08:00:00&window=5", headers=h).status_code == 400
    assert client.get("/api/network/geometry").status_code == 401
