"""Shared pytest fixtures: an app on in-memory SQLite, seeded RBAC, one user per role.

The real MySQL data is never touched. Analytics fixture rows follow the real Parquet
schemas (src/models/analytics.py) with values taken from the loaded tables.
"""

import sys
import warnings
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import exc as sa_exc

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.app import create_app  # noqa: E402
from src.cli import seed_rbac  # noqa: E402
from src.config import TestingConfig  # noqa: E402
from src.extensions import db  # noqa: E402
from src.models.analytics import ANALYTICS_TABLES  # noqa: E402
from src.models.rbac import Role, User  # noqa: E402
from src.models.reference import Route, Stop, Vehicle  # noqa: E402

PASSWORD = "correct-horse-1"
ROLES = ("admin", "operator", "analyst", "evaluator")

# SQLite stores DECIMAL as float; the MySQL behaviour is covered by database/verify_mysql_load.py.
warnings.filterwarnings("ignore", category=sa_exc.SAWarning, message=".*Decimal.*")


def _seed_reference():
    db.session.add_all([
        Stop(stop_id="S0001", stop_name="Saddar Hub", latitude=24.86, longitude=67.01, zone="A",
             stop_type="hub", has_shelter=True, opened_date=date(2025, 9, 1), dq_flags=[]),
        Stop(stop_id="S0002", stop_name="Airport Terminal", latitude=24.90, longitude=67.16, zone="C",
             stop_type="terminal", has_shelter=True, opened_date=date(2025, 9, 1), dq_flags=[]),
        Vehicle(vehicle_id="V0001", registration_no="KHI-1001", vehicle_type="standard", capacity_seated=40,
                capacity_total=80, depot="North Depot", fuel_type="diesel", commission_date=date(2020, 1, 1),
                has_apc=True, status="active", dq_flags=[]),
    ])
    db.session.flush()
    db.session.add(Route(route_id="R001", route_code="BRT1", route_name="Saddar Hub - Airport Terminal",
                         route_type="brt", origin_stop_id="S0001", destination_stop_id="S0002", distance_km=18.5,
                         base_fare=30.0, fare_per_km=2.0, launch_date=date(2025, 9, 1), status="active", dq_flags=[]))


def _seed_analytics():
    t = ANALYTICS_TABLES
    with db.engine.begin() as conn:
        conn.execute(t["route_performance"].insert(), [
            {"route_id": "R001", "route_class": "High Performing", "composite_score": 71.2,
             "med_late_share": Decimal("0.0512"), "underutilization_score": Decimal("88.5"), "overcrowded_flag": True},
            {"route_id": "R002", "route_class": "Low Performing", "composite_score": 38.4,
             "med_late_share": Decimal("0.1875"), "underutilization_score": Decimal("40.0"), "overcrowded_flag": False},
        ])
        conn.execute(t["route_reliability"].insert(), [{"route_id": "R001", "on_time_rate": 0.81}])
        conn.execute(t["od_matrix"].insert(), [
            {"origin_stop_id": "S0001", "destination_stop_id": "S0002", "route_id": "R001", "direction": 0,
             "time_period": "morning_peak", "day_class": "weekday", "card_journeys": 12, "est_passengers": 360.5},
            {"origin_stop_id": "S0002", "destination_stop_id": "S0001", "route_id": "R001", "direction": 1,
             "time_period": "evening_peak", "day_class": "weekday", "card_journeys": 9, "est_passengers": 270.0},
            {"origin_stop_id": "S0003", "destination_stop_id": "S0004", "route_id": "R002", "direction": 0,
             "time_period": "midday", "day_class": "weekend", "card_journeys": 3, "est_passengers": 90.0},
        ])
        conn.execute(t["eda_peak_days"].insert(), [
            {"service_date": date(2025, 10, 12), "day_class": "weekend", "est_system_boardings": 1.0e6},
            {"service_date": date(2026, 3, 1), "day_class": "weekday", "est_system_boardings": 9.0e5},
        ])


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        seed_rbac()
        for role in ROLES:
            user = User(username=role, roles=[db.session.execute(db.select(Role).filter_by(name=role)).scalar_one()])
            user.set_password(PASSWORD)
            db.session.add(user)
        _seed_reference()
        db.session.commit()
        _seed_analytics()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth(client):
    """auth("analyst") -> headers with a bearer token for that user."""
    def headers(username: str) -> dict:
        res = client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
        assert res.status_code == 200, res.get_json()
        return {"Authorization": f"Bearer {res.get_json()['access_token']}"}
    return headers
