"""Network map data: route lines, stops and a replay of the 7-day GPS sample.

GET /api/network/geometry            routes (LineStrings) and stops (Points) as GeoJSON
GET /api/network/replay              the replay window: first/last ping, days, vehicles
GET /api/network/vehicles?at=...     bus positions at a moment of the replay window

The GPS data are simulated AVL pings covering 10-16 Nov 2025 only. There is no real-time
feed, so every response names itself a replay of that sample. Nothing here is "live".
"""

import time
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy import and_, func, select

from src.errors import ApiError
from src.extensions import db
from src.models.analytics import ANALYTICS_TABLES
from src.models.network import GpsEvent, RouteStop
from src.models.reference import Route, Stop
from src.security import permission_required
from src.services.analytics_query import to_json_value
from src.services.requests import int_arg

bp = Blueprint("network", __name__, url_prefix="/api/network")

REPLAY_SOURCE = "Replay of simulated GPS pings (gps_events, 7-day sample, 10-16 Nov 2025). Not real-time."
CACHE_SECONDS = 600
_cache: dict[str, tuple[float, dict]] = {}


def _cached(key: str, build):
    """Geometry and the replay window change only when the loader runs; keep them 10 minutes."""
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]
    value = build()
    _cache[key] = (time.monotonic(), value)
    return value


def _geometry() -> dict:
    perf = ANALYTICS_TABLES["route_performance"]
    stop_perf = ANALYTICS_TABLES["stop_performance"]

    meta = {r.route_id: r for r in db.session.execute(
        select(Route.route_id, Route.route_code, Route.route_name, Route.route_type,
               perf.c.route_class, perf.c.composite_score, perf.c.overcrowded_flag, perf.c.med_daily_boardings)
        .outerjoin(perf, perf.c.route_id == Route.route_id))}

    lines: dict[tuple[str, int], list[list[float]]] = {}
    for r in db.session.execute(
            select(RouteStop.route_id, RouteStop.direction, Stop.longitude, Stop.latitude)
            .join(Stop, Stop.stop_id == RouteStop.stop_id)
            .order_by(RouteStop.route_id, RouteStop.direction, RouteStop.stop_sequence)):
        lines.setdefault((r.route_id, r.direction), []).append([r.longitude, r.latitude])

    routes = []
    for (route_id, direction), coords in lines.items():
        m = meta.get(route_id)
        routes.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "route_id": route_id, "direction": direction,
                "route_code": m.route_code if m else None, "route_name": m.route_name if m else None,
                "route_type": m.route_type if m else None, "route_class": m.route_class if m else None,
                "composite_score": to_json_value(m.composite_score) if m else None,
                "overcrowded_flag": bool(m.overcrowded_flag) if m and m.overcrowded_flag is not None else None,
                "med_daily_boardings": to_json_value(m.med_daily_boardings) if m else None,
            },
        })

    stops = []
    for s in db.session.execute(
            select(Stop.stop_id, Stop.stop_name, Stop.stop_type, Stop.zone, Stop.latitude, Stop.longitude,
                   stop_perf.c.est_boardings_per_day, stop_perf.c.routes_serving, stop_perf.c.trips_serving_per_day,
                   stop_perf.c.is_bottleneck)
            .outerjoin(stop_perf, stop_perf.c.stop_id == Stop.stop_id)):
        stops.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [s.longitude, s.latitude]},
            "properties": {
                "stop_id": s.stop_id, "stop_name": s.stop_name, "stop_type": s.stop_type, "zone": s.zone,
                "est_boardings_per_day": to_json_value(s.est_boardings_per_day),
                "routes_serving": s.routes_serving, "trips_serving_per_day": to_json_value(s.trips_serving_per_day),
                "is_bottleneck": bool(s.is_bottleneck) if s.is_bottleneck is not None else None,
            },
        })
    return {"routes": {"type": "FeatureCollection", "features": routes},
            "stops": {"type": "FeatureCollection", "features": stops}}


def _replay_window() -> dict:
    first, last, vehicles, pings = db.session.execute(
        select(func.min(GpsEvent.event_time), func.max(GpsEvent.event_time),
               func.count(GpsEvent.vehicle_id.distinct()), func.count())).one()
    days = db.session.execute(select(GpsEvent.event_date, func.count()).group_by(GpsEvent.event_date)
                              .order_by(GpsEvent.event_date)).all()
    return {
        "start": first.isoformat() if first else None,
        "end": last.isoformat() if last else None,
        "days": [{"date": d.isoformat(), "pings": n} for d, n in days],
        "vehicles": vehicles,
        "pings": pings,
        "source": REPLAY_SOURCE,
    }


@bp.get("/geometry")
@permission_required("analytics:read")
def geometry():
    return jsonify(_cached("geometry", _geometry))


@bp.get("/replay")
@permission_required("analytics:read")
def replay():
    return jsonify(_cached("replay", _replay_window))


@bp.get("/vehicles")
@permission_required("analytics:read")
def vehicles():
    """Latest ping of each bus in the `window` seconds up to `at` (a moment inside the replay)."""
    window = _cached("replay", _replay_window)
    if not window["start"]:
        raise ApiError(404, "no_replay_data", "No GPS replay data is loaded.")
    raw = request.args.get("at", "")
    try:
        at = datetime.fromisoformat(raw)
    except ValueError:
        raise ApiError(400, "invalid_parameter", "'at' must be a date-time like 2025-11-12T08:15:00.") from None
    start, end = datetime.fromisoformat(window["start"]), datetime.fromisoformat(window["end"])
    if not start <= at <= end:
        raise ApiError(400, "outside_replay_window", "The replay only covers the GPS sample window.",
                       {"start": window["start"], "end": window["end"]})
    seconds = int_arg("window", 180, 30, 900)

    latest = (select(GpsEvent.vehicle_id, func.max(GpsEvent.event_time).label("t"))
              .where(GpsEvent.event_time > at - timedelta(seconds=seconds), GpsEvent.event_time <= at)
              .group_by(GpsEvent.vehicle_id).subquery())
    rows = db.session.execute(
        select(GpsEvent, Route.route_code, Route.route_type)
        .join(latest, and_(latest.c.vehicle_id == GpsEvent.vehicle_id, latest.c.t == GpsEvent.event_time))
        .outerjoin(Route, Route.route_id == GpsEvent.route_id)
        .order_by(GpsEvent.vehicle_id, GpsEvent.event_id)).all()

    seen, out = set(), []
    for ev, route_code, route_type in rows:
        if ev.vehicle_id in seen:          # two pings in the same second: keep one
            continue
        seen.add(ev.vehicle_id)
        out.append({
            "vehicle_id": ev.vehicle_id, "trip_id": ev.trip_id, "route_id": ev.route_id,
            "route_code": route_code, "route_type": route_type, "stop_id": ev.stop_id,
            "event_type": ev.event_type, "event_time": ev.event_time.isoformat(),
            "longitude": ev.longitude, "latitude": ev.latitude, "speed_kmh": ev.speed_kmh,
        })
    return jsonify(at=at.isoformat(), window_seconds=seconds, active=len(out), vehicles=out, source=REPLAY_SOURCE)
